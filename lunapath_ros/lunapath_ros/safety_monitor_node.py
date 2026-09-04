"""Formal safety monitor: telemetry in, ReplanTrigger out (D3).

The ROS twin of ``POST /api/safety-check``. It subscribes to the standard
telemetry messages a rover stack already publishes -- ``sensor_msgs/
BatteryState``, ``sensor_msgs/Temperature``, a ``std_msgs/Float32``
illumination estimate and ``nav_msgs/Odometry`` -- assembles one sample
per period and pushes it into ``app.safety_monitor.SafetyMonitorSession``,
the same catalogue and the same robustness engines the FastAPI shell runs
on planned routes. Every requirement that becomes violated is published
ONCE as a ``lunapath_msgs/ReplanTrigger`` (``trigger_id = "safety:LP-R02"``,
the robustness and unit in ``detail``): the formal, margin-bearing version
of ``replan_triggers.py``'s threshold checks.

No decision logic lives here, deliberately (see pose_monitor.py): the
verdicts cannot drift between the two shells. What is checked is a
CONCRETE flown prefix by runtime monitoring; nothing is proven.
"""

from __future__ import annotations

import math
from typing import Any

import rclpy
from rclpy.node import Node

from nav_msgs.msg import Odometry
from sensor_msgs.msg import BatteryState, Temperature
from std_msgs.msg import Float32

from app.constants import UnknownRoverError, get_rover
from app.safety_monitor import SafetyMonitorSession
from lunapath_msgs.msg import ReplanTrigger

#: Below this ground speed the rover counts as parked (LP-R08's scope).
MOVING_SPEED_MS = 1e-3


def sample_from_messages(
    t_h: float,
    battery: BatteryState | None = None,
    temperature: Temperature | None = None,
    shadow: Float32 | None = None,
    odometry: Odometry | None = None,
) -> dict[str, Any]:
    """One catalogue sample from the latest messages; only what was given
    appears, so an absent sensor makes its requirements 'not applicable'
    rather than silently satisfied.

    ``BatteryState.percentage`` is 0..1 (NaN when unknown, which is not a
    SOC); ``POWER_SUPPLY_STATUS_CHARGING`` is the charging flag LP-R03
    needs; ``Temperature`` is taken as the INNER temperature the envelope
    requirements are written against.
    """
    sample: dict[str, Any] = {"t_h": float(t_h)}
    if battery is not None:
        pct = float(battery.percentage)
        if math.isfinite(pct) and 0.0 <= pct <= 1.0:
            sample["soc_pct"] = pct * 100.0
        sample["charging"] = int(battery.power_supply_status) == int(
            BatteryState.POWER_SUPPLY_STATUS_CHARGING
        )
    if temperature is not None and math.isfinite(float(temperature.temperature)):
        sample["inner_temp_c"] = float(temperature.temperature)
    if shadow is not None and math.isfinite(float(shadow.data)):
        sample["shadow_ratio"] = float(shadow.data)
    if odometry is not None:
        linear = odometry.twist.twist.linear
        speed = math.sqrt(float(linear.x) ** 2 + float(linear.y) ** 2 + float(linear.z) ** 2)
        sample["moving"] = speed > MOVING_SPEED_MS
    return sample


class SafetyMonitor(Node):
    def __init__(self) -> None:
        super().__init__("lunapath_safety_monitor")
        self.declare_parameter("rover_id", "lpr_1")
        self.declare_parameter("period_s", 10.0)
        self.declare_parameter("engine", "auto")
        self.declare_parameter("battery_topic", "battery_state")
        self.declare_parameter("temperature_topic", "inner_temperature")
        self.declare_parameter("shadow_topic", "shadow_ratio")
        self.declare_parameter("odom_topic", "odom")

        rover_id = str(self.get_parameter("rover_id").value)
        try:
            rover = get_rover(rover_id)
        except UnknownRoverError as exc:
            raise SystemExit(str(exc)) from exc
        self._session = SafetyMonitorSession(rover, engine=str(self.get_parameter("engine").value))

        self._battery: BatteryState | None = None
        self._temperature: Temperature | None = None
        self._shadow: Float32 | None = None
        self._odometry: Odometry | None = None
        self._t0 = self.get_clock().now()

        self._trigger_pub = self.create_publisher(ReplanTrigger, "replan_triggers", 10)
        self.create_subscription(
            BatteryState, str(self.get_parameter("battery_topic").value), self._on_battery, 10
        )
        self.create_subscription(
            Temperature, str(self.get_parameter("temperature_topic").value), self._on_temperature, 10
        )
        self.create_subscription(
            Float32, str(self.get_parameter("shadow_topic").value), self._on_shadow, 10
        )
        self.create_subscription(
            Odometry, str(self.get_parameter("odom_topic").value), self._on_odometry, 10
        )
        period = float(self.get_parameter("period_s").value)
        self.create_timer(period, self._on_timer)
        self.get_logger().info(
            f"safety monitor up for {rover['name']} ({rover_id}): one sample every {period:g} s, "
            "triggers on 'replan_triggers'"
        )

    # ── telemetry intake: keep the latest of each ─────────────────────

    def _on_battery(self, message: BatteryState) -> None:
        self._battery = message

    def _on_temperature(self, message: Temperature) -> None:
        self._temperature = message

    def _on_shadow(self, message: Float32) -> None:
        self._shadow = message

    def _on_odometry(self, message: Odometry) -> None:
        self._odometry = message

    # ── one sample per period ─────────────────────────────────────────

    def _on_timer(self) -> None:
        if self._battery is None and self._temperature is None and self._shadow is None and self._odometry is None:
            return
        elapsed_h = (self.get_clock().now() - self._t0).nanoseconds / 3.6e12
        sample = sample_from_messages(
            elapsed_h,
            battery=self._battery,
            temperature=self._temperature,
            shadow=self._shadow,
            odometry=self._odometry,
        )
        try:
            result = self._session.push(sample)
        except ValueError as exc:
            self.get_logger().warning(f"dropping sample: {exc}")
            return

        block = result["safety_margins"]
        by_id = {entry["id"]: entry for entry in block["requirements"]}
        for rid in result["newly_violated"]:
            entry = by_id[rid]
            message_out = ReplanTrigger()
            message_out.trigger_id = f"safety:{rid}"
            message_out.detail = (
                f"{entry['name']}: rho={entry['rho']} {entry['unit']} "
                f"(threshold {entry['threshold']} from {entry['threshold_source']}; "
                f"{entry['stl']}); worst at t={entry['worst_at']['hours']} h; "
                f"engine {block['monitor']['engine']}; {block['monitor']['claim']}"
            )
            message_out.recommended_action = "replan"
            message_out.stamp = self.get_clock().now().to_msg()
            self._trigger_pub.publish(message_out)
            self.get_logger().warning(f"safety requirement violated: {message_out.trigger_id} -- {entry['name']}")

        margin = block.get("min_margin")
        if margin is not None:
            self.get_logger().debug(
                f"{result['n_samples']} samples, verdict {block['verdict']}, smallest margin "
                f"{margin['id']} rho={margin['rho']} {margin['unit']}"
            )


def main() -> None:
    rclpy.init()
    node = SafetyMonitor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
