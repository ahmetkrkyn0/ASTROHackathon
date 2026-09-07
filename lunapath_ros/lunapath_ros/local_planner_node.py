"""Bridge corridor, odometry and LiDAR observations into a ``LocalPlan``."""

from __future__ import annotations

import rclpy
from geometry_msgs.msg import Point
from lunapath_msgs.msg import Corridor, LocalPlan, ObservedObstacles, ReplanTrigger
from nav_msgs.msg import Odometry
from rclpy.node import Node

from lunapath_ros.local_planning import LocalObstacle, MapPoint, plan_local_detour
from lunapath_ros.pose_monitor import LATCHED_QOS


class LocalPlanner(Node):
    """Publish only decisions derived from current, LiDAR-sourced observations."""

    def __init__(self) -> None:
        super().__init__("lunapath_local_planner")
        self.declare_parameter("corridor_topic", "corridor")
        self.declare_parameter("odom_topic", "odom")
        self.declare_parameter("observed_obstacles_topic", "observed_obstacles")
        self.declare_parameter("local_plan_topic", "local_plan")
        self.declare_parameter("replan_trigger_topic", "replan_triggers")
        self.declare_parameter("map_frame", "moon_map")
        self.declare_parameter("max_observation_age_s", 2.0)
        self.declare_parameter("rover_radius_m", 0.35)
        self.declare_parameter("safety_margin_m", 0.25)
        self.declare_parameter("min_confidence", 0.65)

        self._map_frame = str(self.get_parameter("map_frame").value)
        self._max_age_s = max(0.0, float(self.get_parameter("max_observation_age_s").value))
        self._kwargs = {
            "rover_radius_m": max(0.0, float(self.get_parameter("rover_radius_m").value)),
            "safety_margin_m": max(0.0, float(self.get_parameter("safety_margin_m").value)),
            "min_confidence": min(1.0, max(0.0, float(self.get_parameter("min_confidence").value))),
        }
        self._corridor: Corridor | None = None
        self._pose: MapPoint | None = None
        self._obstacles: list[LocalObstacle] = []
        self._obstacle_messages = []
        self._last_observation_s: float | None = None
        self._last_signature: tuple | None = None
        self._last_stop_signature: tuple | None = None

        self._plan_pub = self.create_publisher(
            LocalPlan, str(self.get_parameter("local_plan_topic").value), 10
        )
        self._trigger_pub = self.create_publisher(
            ReplanTrigger, str(self.get_parameter("replan_trigger_topic").value), 10
        )
        self.create_subscription(
            Corridor, str(self.get_parameter("corridor_topic").value), self._on_corridor, LATCHED_QOS
        )
        self.create_subscription(
            Odometry, str(self.get_parameter("odom_topic").value), self._on_odometry, 10
        )
        self.create_subscription(
            ObservedObstacles,
            str(self.get_parameter("observed_obstacles_topic").value),
            self._on_obstacles,
            10,
        )
        self.create_timer(0.1, self._evaluate)
        self.get_logger().info("local planner up: LiDAR observations are the only obstacle input")

    def _frame_ok(self, frame_id: str, kind: str) -> bool:
        if frame_id == self._map_frame:
            return True
        self.get_logger().warning(f"dropping {kind} in '{frame_id}', expected '{self._map_frame}'")
        return False

    def _on_corridor(self, message: Corridor) -> None:
        # Corridor.crs is a projected-CRS label, not a ROS frame id. The
        # existing message has no Header, so planner_node's configured map
        # frame is the contract and the output retains ``self._map_frame``.
        self._corridor = message

    def _on_odometry(self, message: Odometry) -> None:
        if not self._frame_ok(message.header.frame_id, "Odometry"):
            self._pose = None
            return
        position = message.pose.pose.position
        self._pose = MapPoint(float(position.x), float(position.y))

    def _on_obstacles(self, message: ObservedObstacles) -> None:
        if not self._frame_ok(message.header.frame_id, "ObservedObstacles"):
            return
        self._obstacles = [
            LocalObstacle(
                MapPoint(float(entry.center.x), float(entry.center.y)),
                max(0.0, float(entry.radius_m)),
                min(1.0, max(0.0, float(entry.confidence))),
            )
            for entry in message.obstacles
            if entry.source == "lidar"
        ]
        self._obstacle_messages = list(message.obstacles)
        stamp = message.header.stamp
        self._last_observation_s = float(stamp.sec) + float(stamp.nanosec) * 1e-9

    def _observations_fresh(self) -> bool:
        if self._last_observation_s is None:
            return False
        now = self.get_clock().now().nanoseconds * 1e-9
        return now - self._last_observation_s <= self._max_age_s

    def _evaluate(self) -> None:
        if self._corridor is None or self._pose is None:
            return
        obstacles = self._obstacles if self._observations_fresh() else []
        decision = plan_local_detour(
            self._pose,
            [MapPoint(float(point.x), float(point.y)) for point in self._corridor.waypoints],
            [float(width) for width in self._corridor.half_width_m],
            obstacles,
            **self._kwargs,
        )
        signature = (
            decision.decision,
            tuple((round(point.x_m, 2), round(point.y_m, 2)) for point in decision.waypoints),
            decision.reason,
        )
        if signature == self._last_signature:
            return
        self._last_signature = signature
        message = LocalPlan()
        message.header.frame_id = self._map_frame
        message.header.stamp = self.get_clock().now().to_msg()
        message.decision = decision.decision
        message.waypoints = [Point(x=point.x_m, y=point.y_m, z=0.0) for point in decision.waypoints]
        message.observed_obstacles = self._obstacle_messages if obstacles else []
        message.nearest_obstacle_m = float(decision.nearest_obstacle_m or 0.0)
        message.corridor_deviation_m = float(decision.corridor_deviation_m)
        message.reason = decision.reason
        self._plan_pub.publish(message)

        if decision.decision == "STOP_AND_REPLAN" and signature != self._last_stop_signature:
            self._last_stop_signature = signature
            trigger = ReplanTrigger()
            trigger.trigger_id = "local_obstacle_blocked_corridor"
            trigger.detail = decision.reason
            trigger.recommended_action = "replan"
            trigger.stamp = message.header.stamp
            self._trigger_pub.publish(trigger)
            self.get_logger().warning(f"local detour unavailable: {decision.reason}")


def main() -> None:
    rclpy.init()
    node = LocalPlanner()
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
