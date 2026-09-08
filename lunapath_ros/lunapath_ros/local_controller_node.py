"""Fail-closed ROS 2 executor for validated ``lunapath_msgs/LocalPlan``.

This is intentionally a small bridge, not a replacement for Nav2. It follows
the planner's global path, temporarily prioritises bounded ``LOCAL_DETOUR``
waypoints, and publishes zero velocity on a replan/localization trigger. It
is disabled by default; a hardware integration must explicitly opt in and put
the output behind its normal velocity/safety mux.
"""

from __future__ import annotations

import math

import rclpy
from geometry_msgs.msg import Twist
from lunapath_msgs.msg import LocalPlan, ReplanTrigger
from nav_msgs.msg import Odometry, Path
from rclpy.node import Node

from lunapath_ros.local_control import ControlLimits, Pose2D, step_local_route


def _yaw_from_quaternion(q) -> float:
    """REP-103 quaternion to planar yaw."""
    return math.atan2(
        2.0 * (float(q.w) * float(q.z) + float(q.x) * float(q.y)),
        1.0 - 2.0 * (float(q.y) ** 2 + float(q.z) ** 2),
    )


class LocalController(Node):
    def __init__(self) -> None:
        super().__init__("lunapath_local_controller")
        self.declare_parameter("enabled", False)
        self.declare_parameter("local_plan_topic", "local_plan")
        self.declare_parameter("global_path_topic", "global_path")
        self.declare_parameter("odom_topic", "odom")
        self.declare_parameter("cmd_vel_topic", "cmd_vel")
        self.declare_parameter("replan_trigger_topic", "replan_triggers")
        self.declare_parameter("map_frame", "moon_map")
        self.declare_parameter("strict_frame_id", True)
        self.declare_parameter("control_hz", 10.0)
        self.declare_parameter("max_linear_m_s", 0.15)
        self.declare_parameter("max_angular_rad_s", 0.45)
        self.declare_parameter("waypoint_tolerance_m", 0.20)

        self._enabled = bool(self.get_parameter("enabled").value)
        self._map_frame = str(self.get_parameter("map_frame").value)
        self._strict_frame_id = bool(self.get_parameter("strict_frame_id").value)
        self._limits = ControlLimits(
            max_linear_m_s=max(0.0, float(self.get_parameter("max_linear_m_s").value)),
            max_angular_rad_s=max(0.0, float(self.get_parameter("max_angular_rad_s").value)),
            waypoint_tolerance_m=max(0.001, float(self.get_parameter("waypoint_tolerance_m").value)),
        )
        self._global_waypoints: list[tuple[float, float]] = []
        self._global_next_waypoint = 0
        self._local_waypoints: list[tuple[float, float]] = []
        self._local_next_waypoint = 0
        self._pose: Pose2D | None = None
        self._motion_allowed = False

        self._cmd_pub = self.create_publisher(
            Twist, str(self.get_parameter("cmd_vel_topic").value), 10
        )
        self.create_subscription(
            LocalPlan, str(self.get_parameter("local_plan_topic").value), self._on_plan, 10
        )
        self.create_subscription(
            Path, str(self.get_parameter("global_path_topic").value), self._on_global_path, 10
        )
        self.create_subscription(
            Odometry, str(self.get_parameter("odom_topic").value), self._on_odometry, 10
        )
        self.create_subscription(
            ReplanTrigger,
            str(self.get_parameter("replan_trigger_topic").value),
            self._on_replan_trigger,
            10,
        )
        hz = max(1.0, float(self.get_parameter("control_hz").value))
        self.create_timer(1.0 / hz, self._on_control_timer)
        self._publish_stop()
        state = "ENABLED" if self._enabled else "DISABLED (safe default)"
        self.get_logger().warning(
            f"route controller {state}; follows global/local paths in '{self._map_frame}'"
        )

    def _frame_ok(self, frame_id: str, kind: str) -> bool:
        if not self._strict_frame_id or frame_id == self._map_frame:
            return True
        self.get_logger().error(
            f"rejecting {kind} in frame '{frame_id}'; expected '{self._map_frame}'"
        )
        return False

    def _stop_all(self, reason: str) -> None:
        self._global_waypoints = []
        self._global_next_waypoint = 0
        self._local_waypoints = []
        self._local_next_waypoint = 0
        self._motion_allowed = False
        self._publish_stop()
        self.get_logger().warning(f"route motion stopped: {reason}")

    def _on_global_path(self, message: Path) -> None:
        if not self._frame_ok(message.header.frame_id, "global Path"):
            self._stop_all("global path frame mismatch")
            return
        if not message.poses:
            self._stop_all("empty global path")
            return
        self._global_waypoints = [
            (float(item.pose.position.x), float(item.pose.position.y)) for item in message.poses
        ]
        self._global_next_waypoint = 0
        self._local_waypoints = []
        self._local_next_waypoint = 0
        self._motion_allowed = self._enabled
        self._publish_stop()
        self.get_logger().info(f"accepted {len(self._global_waypoints)} global path waypoints")

    def _on_plan(self, message: LocalPlan) -> None:
        if not self._frame_ok(message.header.frame_id, "LocalPlan"):
            self._stop_all("LocalPlan frame mismatch")
            return
        if message.decision in ("STOP_AND_REPLAN", "STOP_UNCERTAIN"):
            self._stop_all(f"local decision is {message.decision}")
            return
        if message.decision == "FOLLOW":
            self._local_waypoints = []
            self._local_next_waypoint = 0
            self._motion_allowed = self._enabled and bool(self._global_waypoints)
            return
        if message.decision != "LOCAL_DETOUR" or not message.waypoints:
            self._stop_all(f"unsupported local decision {message.decision or 'empty'}")
            return
        self._local_waypoints = [(float(p.x), float(p.y)) for p in message.waypoints]
        self._local_next_waypoint = 0
        self._motion_allowed = self._enabled
        self._publish_stop()  # never carry a command across a route replacement
        self.get_logger().info(f"accepted {len(self._local_waypoints)} local-detour waypoints")

    def _on_odometry(self, message: Odometry) -> None:
        if not self._frame_ok(message.header.frame_id, "Odometry"):
            self._pose = None
            self._stop_all("odometry frame mismatch")
            return
        position = message.pose.pose.position
        self._pose = Pose2D(
            x_m=float(position.x),
            y_m=float(position.y),
            heading_rad=_yaw_from_quaternion(message.pose.pose.orientation),
        )

    def _on_replan_trigger(self, message: ReplanTrigger) -> None:
        if message.recommended_action != "continue":
            self._stop_all(
                f"replan trigger {message.trigger_id or 'unknown'}: {message.recommended_action}"
            )

    def _publish_stop(self) -> None:
        self._cmd_pub.publish(Twist())

    def _on_control_timer(self) -> None:
        if not self._enabled or not self._motion_allowed or self._pose is None:
            self._publish_stop()
            return
        local_active = bool(self._local_waypoints)
        waypoints = self._local_waypoints if local_active else self._global_waypoints
        next_index = self._local_next_waypoint if local_active else self._global_next_waypoint
        step = step_local_route(self._pose, waypoints, next_index, self._limits)
        if local_active:
            self._local_next_waypoint = step.next_waypoint_index
        else:
            self._global_next_waypoint = step.next_waypoint_index
        if step.complete:
            if local_active and self._global_waypoints:
                self._local_waypoints = []
                self._local_next_waypoint = 0
                self.get_logger().info("local detour complete; resuming global path")
                return
            self._stop_all("route complete")
            return
        command = Twist()
        command.linear.x = step.command.linear_m_s
        command.angular.z = step.command.angular_rad_s
        self._cmd_pub.publish(command)


def main() -> None:
    rclpy.init()
    node = LocalController()
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
