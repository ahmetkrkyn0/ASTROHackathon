"""Publish measured-vs-planned traverse status without changing the plan."""

from __future__ import annotations

import math

import rclpy
from lunapath_msgs.msg import ActiveMission, ExecutionStatus
from nav_msgs.msg import Odometry, Path
from rclpy.node import Node
from sensor_msgs.msg import BatteryState

from app.constants import get_rover
from lunapath_ros.pose_monitor import LATCHED_QOS
from lunapath_ros.route_progress import energy_used_from_soc_wh, integrate_displacement_m, polyline_length_m


class ExecutionMonitor(Node):
    """A read-only reconciliation stream for operators and safety tooling."""

    def __init__(self) -> None:
        super().__init__("lunapath_execution_monitor")
        self.declare_parameter("odom_topic", "odom")
        self.declare_parameter("battery_topic", "battery_state")
        self.declare_parameter("global_path_topic", "global_path")
        self.declare_parameter("execution_status_topic", "execution_status")
        self.declare_parameter("map_frame", "moon_map")
        self._map_frame = str(self.get_parameter("map_frame").value)
        self._mission: ActiveMission | None = None
        self._path_length_m = math.nan
        self._travelled_m = 0.0
        self._last_xy: tuple[float, float] | None = None
        self._soc_pct: float | None = None
        self._initial_soc_pct: float | None = None
        self._capacity_wh: float | None = None
        self._publisher = self.create_publisher(
            ExecutionStatus, str(self.get_parameter("execution_status_topic").value), 10
        )
        self.create_subscription(ActiveMission, "active_mission", self._on_mission, LATCHED_QOS)
        self.create_subscription(Path, str(self.get_parameter("global_path_topic").value), self._on_path, LATCHED_QOS)
        self.create_subscription(Odometry, str(self.get_parameter("odom_topic").value), self._on_odometry, 10)
        self.create_subscription(BatteryState, str(self.get_parameter("battery_topic").value), self._on_battery, 10)
        self.create_timer(1.0, self._publish)

    def _on_mission(self, message: ActiveMission) -> None:
        if message.header.frame_id != self._map_frame:
            self.get_logger().error("active mission frame mismatch; not reconciling")
            return
        self._mission = message
        self._travelled_m = 0.0
        self._last_xy = None
        self._initial_soc_pct = self._soc_pct
        try:
            self._capacity_wh = float(get_rover(message.rover_id or None)["e_cap_wh"])
        except Exception as exc:
            self._capacity_wh = None
            self.get_logger().warning(f"cannot resolve rover battery capacity: {exc}")

    def _on_path(self, message: Path) -> None:
        if message.header.frame_id != self._map_frame:
            self._path_length_m = math.nan
            return
        self._path_length_m = polyline_length_m([
            (float(item.pose.position.x), float(item.pose.position.y)) for item in message.poses
        ])

    def _on_odometry(self, message: Odometry) -> None:
        if message.header.frame_id != self._map_frame:
            return
        position = message.pose.pose.position
        self._travelled_m, self._last_xy = integrate_displacement_m(
            self._travelled_m, self._last_xy, (float(position.x), float(position.y))
        )

    def _on_battery(self, message: BatteryState) -> None:
        percentage = float(message.percentage)
        if math.isfinite(percentage) and 0.0 <= percentage <= 1.0:
            self._soc_pct = percentage * 100.0
            if self._initial_soc_pct is None:
                self._initial_soc_pct = self._soc_pct

    def _publish(self) -> None:
        if self._mission is None:
            return
        metrics = self._mission.metrics
        status = ExecutionStatus()
        status.header.frame_id = self._map_frame
        status.header.stamp = self.get_clock().now().to_msg()
        status.planned_distance_km = float(metrics.total_distance_km)
        status.planned_energy_wh = float(metrics.total_energy_consumed_wh)
        status.planned_elapsed_hours = float(metrics.total_elapsed_hours)
        status.travelled_distance_m = float(self._travelled_m)
        status.actual_soc_pct = math.nan if self._soc_pct is None else float(self._soc_pct)
        status.has_battery_measurement = (
            self._soc_pct is not None and self._initial_soc_pct is not None and self._capacity_wh is not None
        )
        status.actual_energy_consumed_wh = (
            energy_used_from_soc_wh(self._initial_soc_pct, self._soc_pct, self._capacity_wh)
            if status.has_battery_measurement else math.nan
        )
        if not math.isfinite(self._path_length_m):
            status.status = "waiting_for_global_path"
        elif status.has_battery_measurement:
            status.status = "measured_vs_planned"
        else:
            status.status = "odometry_only_battery_unavailable"
        self._publisher.publish(status)


def main() -> None:
    rclpy.init()
    node = ExecutionMonitor()
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
