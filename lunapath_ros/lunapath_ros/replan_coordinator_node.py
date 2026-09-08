"""Close the ROS replan loop without admitting unseen obstacle information."""

from __future__ import annotations

import rclpy
from geometry_msgs.msg import PoseStamped
from lunapath_msgs.action import PlanTraverse
from lunapath_msgs.msg import ActiveMission, ObservedObstacles, ReplanTrigger
from nav_msgs.msg import Odometry
from rclpy.action import ActionClient
from rclpy.node import Node

from lunapath_ros.pose_monitor import LATCHED_QOS


class ReplanCoordinator(Node):
    """Resend the active goal from live odometry after an approved trigger.

    The node does not invent goals or obstacle maps. It has no effect until an
    initial ``PlanTraverse`` success publishes an ``ActiveMission``. A new
    action result publishes the replacement corridor/global path, which is the
    only signal that allows the route controller to resume.
    """

    def __init__(self) -> None:
        super().__init__("lunapath_replan_coordinator")
        self.declare_parameter("odom_topic", "odom")
        self.declare_parameter("observed_obstacles_topic", "observed_obstacles")
        self.declare_parameter("replan_trigger_topic", "replan_triggers")
        self.declare_parameter("map_frame", "moon_map")
        self.declare_parameter("max_observation_age_s", 2.0)

        self._map_frame = str(self.get_parameter("map_frame").value)
        self._max_age_s = max(0.0, float(self.get_parameter("max_observation_age_s").value))
        self._mission: ActiveMission | None = None
        self._pose: PoseStamped | None = None
        self._observations = []
        self._observed_at_ns: int | None = None
        self._inflight = False
        self._client = ActionClient(self, PlanTraverse, "plan_traverse")

        self.create_subscription(ActiveMission, "active_mission", self._on_mission, LATCHED_QOS)
        self.create_subscription(Odometry, str(self.get_parameter("odom_topic").value), self._on_odometry, 10)
        self.create_subscription(
            ObservedObstacles,
            str(self.get_parameter("observed_obstacles_topic").value),
            self._on_observations,
            10,
        )
        self.create_subscription(
            ReplanTrigger,
            str(self.get_parameter("replan_trigger_topic").value),
            self._on_trigger,
            10,
        )
        self.get_logger().info("replan coordinator up; awaits ActiveMission and ReplanTrigger")

    def _on_mission(self, message: ActiveMission) -> None:
        if message.header.frame_id != self._map_frame:
            self.get_logger().error("rejecting ActiveMission in unexpected frame")
            return
        self._mission = message
        self.get_logger().info("active mission retained for trigger-driven replans")

    def _on_odometry(self, message: Odometry) -> None:
        if message.header.frame_id != self._map_frame:
            self._pose = None
            self.get_logger().warning("dropping odometry outside configured map frame")
            return
        pose = PoseStamped()
        pose.header = message.header
        pose.pose = message.pose.pose
        self._pose = pose

    def _on_observations(self, message: ObservedObstacles) -> None:
        if message.header.frame_id != self._map_frame:
            self.get_logger().warning("dropping obstacle batch outside configured map frame")
            return
        self._observations = [entry for entry in message.obstacles if entry.source == "lidar"]
        self._observed_at_ns = self.get_clock().now().nanoseconds

    def _fresh_observations(self):
        if self._observed_at_ns is None:
            return []
        age_s = (self.get_clock().now().nanoseconds - self._observed_at_ns) * 1e-9
        return self._observations if age_s <= self._max_age_s else []

    def _on_trigger(self, message: ReplanTrigger) -> None:
        if message.recommended_action != "replan":
            return
        if self._inflight:
            self.get_logger().warning("ignoring trigger while a replan is already in flight")
            return
        if self._mission is None or self._pose is None:
            self.get_logger().error("cannot replan: no active mission or map-frame odometry")
            return
        if not self._client.wait_for_server(timeout_sec=0.0):
            self.get_logger().error("cannot replan: /plan_traverse action server unavailable")
            return

        goal = PlanTraverse.Goal()
        goal.start = self._pose
        goal.goal = self._mission.goal
        goal.rover_id = self._mission.rover_id
        goal.weights = self._mission.weights
        goal.use_start = True
        goal.observed_obstacles = self._fresh_observations()
        self._inflight = True
        future = self._client.send_goal_async(goal)
        future.add_done_callback(self._on_goal_response)
        self.get_logger().warning(
            f"replan requested for {message.trigger_id}; "
            f"{len(goal.observed_obstacles)} fresh LiDAR observation(s) attached"
        )

    def _on_goal_response(self, future) -> None:
        try:
            handle = future.result()
        except Exception as exc:  # action transport boundary
            self._inflight = False
            self.get_logger().error(f"replan goal transport failed: {exc}")
            return
        if not handle.accepted:
            self._inflight = False
            self.get_logger().error("replan goal rejected by planner")
            return
        result_future = handle.get_result_async()
        result_future.add_done_callback(self._on_result)

    def _on_result(self, future) -> None:
        self._inflight = False
        try:
            wrapped = future.result()
            result = wrapped.result
        except Exception as exc:  # action transport boundary
            self.get_logger().error(f"replan result transport failed: {exc}")
            return
        if result.error_code != result.NONE:
            self.get_logger().error(f"replan failed: {result.error_msg}")
            return
        self.get_logger().info("replan succeeded; planner published replacement corridor and global_path")


def main() -> None:
    rclpy.init()
    node = ReplanCoordinator()
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
