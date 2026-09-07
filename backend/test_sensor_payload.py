"""LiDAR/sensor payload energy overhead tests."""

from __future__ import annotations

import pytest

from app.constants import get_rover
from app.sensor_payload import (
    apply_sensor_overhead_to_summary,
    sensor_energy_overhead_wh,
    with_sensor_payload,
)


def test_no_payload_costs_nothing():
    rover = get_rover("lpr_1")
    assert sensor_energy_overhead_wh(5.0, rover) == pytest.approx(0.0)


def test_payload_and_heater_scale_with_duration():
    rover = with_sensor_payload(get_rover("lpr_1"), payload_w=12.0, heater_w=8.0)
    assert sensor_energy_overhead_wh(2.0, rover) == pytest.approx(40.0)
    assert sensor_energy_overhead_wh(4.0, rover) == pytest.approx(80.0)


def test_negative_duration_is_clamped_to_zero():
    rover = with_sensor_payload(get_rover("lpr_1"), payload_w=12.0)
    assert sensor_energy_overhead_wh(-3.0, rover) == pytest.approx(0.0)


def test_with_sensor_payload_does_not_mutate_the_original():
    base = get_rover("lpr_1")
    variant = with_sensor_payload(base, payload_w=12.0, heater_w=8.0)
    assert base["sensor_payload_w"] is None
    assert variant["sensor_payload_w"] == pytest.approx(12.0)
    assert variant["sensor_heater_w"] == pytest.approx(8.0)


def test_with_sensor_payload_renames_the_variant():
    base = get_rover("lpr_1")
    variant = with_sensor_payload(base, payload_w=12.0)
    assert variant["id"] == "lpr_1_lidar"
    assert "LiDAR" in variant["name"]


def test_with_sensor_payload_preserves_other_fields():
    base = get_rover("lpr_1")
    variant = with_sensor_payload(base, payload_w=12.0)
    assert variant["e_cap_wh"] == base["e_cap_wh"]
    assert variant["slope_max_deg"] == base["slope_max_deg"]


def _summary(energy_wh: float, hours: float, final_pct: float) -> dict:
    return {
        "total_energy_consumed_wh": energy_wh,
        "total_elapsed_hours": hours,
        "final_battery_pct": final_pct,
        "waypoint_count": 12,
    }


def test_apply_sensor_overhead_increases_energy_consumed():
    rover = with_sensor_payload(get_rover("lpr_1"), payload_w=12.0, heater_w=8.0)
    summary = _summary(energy_wh=500.0, hours=3.0, final_pct=70.0)
    adjusted = apply_sensor_overhead_to_summary(summary, rover)
    assert adjusted["total_energy_consumed_wh"] == pytest.approx(500.0 + 60.0)
    assert adjusted["sensor_overhead_wh"] == pytest.approx(60.0)


def test_apply_sensor_overhead_reduces_final_battery():
    rover = with_sensor_payload(get_rover("lpr_1"), payload_w=12.0, heater_w=8.0)
    summary = _summary(energy_wh=500.0, hours=3.0, final_pct=70.0)
    adjusted = apply_sensor_overhead_to_summary(summary, rover)
    assert adjusted["final_battery_pct"] < summary["final_battery_pct"]


def test_apply_sensor_overhead_never_goes_below_zero_battery():
    rover = with_sensor_payload(get_rover("lpr_1"), payload_w=500.0)
    summary = _summary(energy_wh=500.0, hours=50.0, final_pct=5.0)
    adjusted = apply_sensor_overhead_to_summary(summary, rover)
    assert adjusted["final_battery_pct"] == pytest.approx(0.0)


def test_apply_sensor_overhead_does_not_mutate_the_input_summary():
    rover = with_sensor_payload(get_rover("lpr_1"), payload_w=12.0)
    summary = _summary(energy_wh=500.0, hours=3.0, final_pct=70.0)
    apply_sensor_overhead_to_summary(summary, rover)
    assert summary["total_energy_consumed_wh"] == pytest.approx(500.0)


def test_apply_sensor_overhead_preserves_unrelated_fields():
    rover = with_sensor_payload(get_rover("lpr_1"), payload_w=12.0)
    summary = _summary(energy_wh=500.0, hours=3.0, final_pct=70.0)
    adjusted = apply_sensor_overhead_to_summary(summary, rover)
    assert adjusted["waypoint_count"] == 12


def test_baseline_rover_summary_is_unchanged_by_zero_payload():
    rover = get_rover("lpr_1")
    summary = _summary(energy_wh=500.0, hours=3.0, final_pct=70.0)
    adjusted = apply_sensor_overhead_to_summary(summary, rover)
    assert adjusted["total_energy_consumed_wh"] == pytest.approx(500.0)
    assert adjusted["final_battery_pct"] == pytest.approx(70.0)
