"""The ROS 2 safety monitor node (D3): message-to-sample conversion.

Needs a ROS 2 installation (rclpy and the message packages); skipped
otherwise. The monitor's decision logic is tested without ROS in
test_safety_monitor.py (SafetyMonitorSession) -- this file only checks the
shell converts standard messages into the sample the session expects.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("rclpy")
pytest.importorskip("lunapath_msgs")
sensor_msgs = pytest.importorskip("sensor_msgs.msg")
nav_msgs = pytest.importorskip("nav_msgs.msg")
std_msgs = pytest.importorskip("std_msgs.msg")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lunapath_ros.safety_monitor_node import MOVING_SPEED_MS, sample_from_messages  # noqa: E402


def test_sample_from_messages_converts_units_and_flags():
    battery = sensor_msgs.BatteryState()
    battery.percentage = 0.55
    battery.power_supply_status = sensor_msgs.BatteryState.POWER_SUPPLY_STATUS_CHARGING
    temperature = sensor_msgs.Temperature()
    temperature.temperature = -12.5
    shadow = std_msgs.Float32()
    shadow.data = 0.7
    odometry = nav_msgs.Odometry()
    odometry.twist.twist.linear.x = 0.05

    sample = sample_from_messages(2.5, battery=battery, temperature=temperature, shadow=shadow, odometry=odometry)
    assert sample["t_h"] == 2.5
    assert sample["soc_pct"] == pytest.approx(55.0)
    assert sample["charging"] is True
    assert sample["inner_temp_c"] == pytest.approx(-12.5)
    assert sample["shadow_ratio"] == pytest.approx(0.7)
    assert sample["moving"] is True


def test_sample_from_messages_omits_what_it_was_not_given():
    odometry = nav_msgs.Odometry()
    odometry.twist.twist.linear.x = MOVING_SPEED_MS / 2.0
    sample = sample_from_messages(0.0, odometry=odometry)
    assert set(sample) == {"t_h", "moving"} and sample["moving"] is False


def test_unknown_battery_percentage_is_not_a_soc():
    battery = sensor_msgs.BatteryState()
    battery.percentage = float("nan")
    sample = sample_from_messages(0.0, battery=battery)
    assert "soc_pct" not in sample
