"""Odometry consumer: nav_msgs/Odometry in, ReplanTrigger out.

This node is the ROS twin of ``POST /api/pose``. It subscribes to any
odometry publisher -- a wheel-odometry EKF, KISS-ICP, a stereo VO node --
converts each message into the ``PoseEstimate`` contract, locates it in
the corridor last published by the planner, and publishes one
``lunapath_msgs/ReplanTrigger`` per fired trigger.

No odometry library is imported here, deliberately. ``nav_msgs/Odometry``
is the standard interface every odometry stack publishes, so LunaPath
stays agnostic about which one is driving -- swap KISS-ICP for a stereo
pipeline and this node does not change. That is the contract-based design
the Phase 7 plan asks for, and it also keeps the licence surface at zero
(no GPL odometry code is linked, only a message type is consumed).

All decision logic lives in ``app.localization.evaluate_pose`` -- the
same function the FastAPI endpoint calls -- so the trigger policy cannot
drift between the two shells. This file is subscription plumbing only.
"""

from __future__ import annotations

import math

import rclpy
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)

from nav_msgs.msg import Odometry

from app.localization import evaluate_pose
from app.pose import PoseEstimate
from app.schemas import Corridor
from lunapath_msgs.msg import Corridor as CorridorMsg
from lunapath_msgs.msg import ReplanTrigger
from lunapath_ros.conversions import msg_to_corridor, odometry_to_pose_estimate

# The corridor is planned once and consumed for the whole traverse, so the
# planner publishes it latched (transient_local): a monitor started after
# the plan still receives it.
LATCHED_QOS = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
)


class PoseMonitor(Node):
    def __init__(self) -> None:
        super().__init__("lunapath_pose_monitor")
        self.declare_parameter("odom_topic", "odom")
        # The label decides more than provenance: app.localization only runs
        # the slip check for sources whose distance claim is a WHEEL
        # measurement (pose.SLIP_CHECKABLE_SOURCES). Visual and LiDAR
        # odometry estimate body motion from the world and have already
        # corrected for slip, so comparing their distance against corridor
        # progress would measure path tortuosity under a trigger named
        # "slip". Label the publisher honestly. (Round 3 review, M-4.)
        self.declare_parameter("pose_source", "visual_odometry")
        # Negative means "not configured": odometry with unknown covariance
        # is then rejected rather than assigned invented confidence.
        self.declare_parameter("fallback_covariance_m", -1.0)

        self._pose_source = str(self.get_parameter("pose_source").value)
        fallback = float(self.get_parameter("fallback_covariance_m").value)
        self._fallback_covariance_m = fallback if fallback >= 0.0 else None

        self._corridor: Corridor | None = None
        self._travelled_m = 0.0
        self._last_xy: tuple[float, float] | None = None
        self._last_along_track_m: float | None = None

        self._trigger_pub = self.create_publisher(
            ReplanTrigger, "replan_triggers", 10
        )
        self.create_subscription(
            CorridorMsg, "corridor", self._on_corridor, LATCHED_QOS
        )
        odom_topic = str(self.get_parameter("odom_topic").value)
        self.create_subscription(Odometry, odom_topic, self._on_odometry, 10)

        self.get_logger().info(
            f"pose monitor up: odometry from '{odom_topic}' "
            f"(source label: {self._pose_source}), corridor from 'corridor'"
        )

    # ── corridor intake ────────────────────────────────────────────────

    def _on_corridor(self, message: CorridorMsg) -> None:
        try:
            self._corridor = Corridor(**msg_to_corridor(message))
        except Exception as exc:  # malformed corridor: keep the old one
            self.get_logger().error(f"rejecting corridor message: {exc}")
            return
        # A new route restarts the traverse; the travelled-distance
        # integral belongs to the corridor it was driven against.
        self._travelled_m = 0.0
        self._last_xy = None
        self._last_along_track_m = None
        self.get_logger().info(
            f"active corridor set: {len(self._corridor.waypoints)} waypoints"
        )

    # ── odometry intake ────────────────────────────────────────────────

    def _on_odometry(self, message: Odometry) -> None:
        x = float(message.pose.pose.position.x)
        y = float(message.pose.pose.position.y)
        if self._last_xy is not None:
            self._travelled_m += math.hypot(x - self._last_xy[0], y - self._last_xy[1])
        self._last_xy = (x, y)
        # NOTE: this integral is the displacement of the POSE STREAM, so it
        # is a genuine odometer claim only when the publisher is wheel
        # odometry (pose_source="dead_reckoning"). For a VO or LiDAR
        # publisher it is the same estimate the corridor projection uses,
        # and evaluate_pose correctly declines to slip-check it.
        # (Round 3 review, M-4.)

        if self._corridor is None:
            # Nothing to judge against; distance keeps integrating so the
            # slip check is honest once a corridor arrives.
            return

        try:
            pose = PoseEstimate(
                **odometry_to_pose_estimate(
                    message,
                    source=self._pose_source,
                    distance_travelled_m=self._travelled_m,
                    fallback_covariance_m=self._fallback_covariance_m,
                )
            )
        except ValueError as exc:
            # Unknown covariance with no fallback configured, or a value
            # the contract rejects. Refusing loudly beats judging a route
            # against a pose that lies about its own certainty.
            self.get_logger().warning(f"dropping odometry message: {exc}")
            return

        # The last segment is a progress prior: on a switchback the
        # globally nearest segment can be the outbound leg running
        # alongside, which teleports along-track and false-fires slip.
        # (Round 2 review, M-4.)
        result = evaluate_pose(
            pose,
            self._corridor,
            previous_along_track_m=self._last_along_track_m,
        )
        self._last_along_track_m = result["corridor_fix"].along_track_m

        for trigger in result["fired"]:
            message_out = ReplanTrigger()
            message_out.trigger_id = trigger.trigger_id
            message_out.detail = trigger.detail
            message_out.recommended_action = result["recommended_action"]
            message_out.stamp = self.get_clock().now().to_msg()
            self._trigger_pub.publish(message_out)

        if result["fired"]:
            fired_ids = ", ".join(t.trigger_id for t in result["fired"])
            self.get_logger().warning(
                f"triggers fired: {fired_ids} -> {result['recommended_action']}"
            )


def main() -> None:
    rclpy.init()
    node = PoseMonitor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            node.destroy_node()
        except KeyboardInterrupt:
            pass
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
