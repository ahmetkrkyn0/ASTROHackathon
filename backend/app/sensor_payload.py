"""LiDAR / active-sensor payload energy overhead.

LunaPath does not carry a sensor -- it plans for one. Carrying a LiDAR is
a continuous power draw and, in a permanently shadowed region, its own
heater load. This module is the one place a sensor genuinely enters the
cost model: not as perception, but as a resource-budget line item.

Deliberately post-hoc: it adjusts an already-computed simulation summary
rather than re-planning, matching the scope of a same-rover comparison
(spec 5.2) rather than a full route re-optimisation.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def sensor_energy_overhead_wh(duration_hours: float, rover: Mapping[str, Any]) -> float:
    """Extra energy a rover's sensor payload draws over *duration_hours*."""
    payload_w = float(rover.get("sensor_payload_w") or 0.0)
    heater_w = float(rover.get("sensor_heater_w") or 0.0)
    return (payload_w + heater_w) * max(0.0, float(duration_hours))


def with_sensor_payload(
    rover: Mapping[str, Any], payload_w: float, heater_w: float = 0.0
) -> dict[str, Any]:
    """Return a copy of *rover* carrying a LiDAR-class sensor payload."""
    variant = dict(rover)
    variant["sensor_payload_w"] = float(payload_w)
    variant["sensor_heater_w"] = float(heater_w)
    variant["id"] = f"{rover.get('id', 'rover')}_lidar"
    variant["name"] = f"{rover.get('name', 'Rover')} + LiDAR"
    return variant


def apply_sensor_overhead_to_summary(
    summary: Mapping[str, Any], rover: Mapping[str, Any]
) -> dict[str, Any]:
    """Adjust a simulate_path summary for the sensor payload *rover* carries.

    Recomputes total_energy_consumed_wh and final_battery_pct; every other
    field passes through unchanged. This is a scoping adjustment, not a
    re-simulation: good enough to compare two profiles, not to plan with.
    """
    duration_hours = float(summary.get("total_elapsed_hours", 0.0))
    overhead_wh = sensor_energy_overhead_wh(duration_hours, rover)
    e_cap_wh = float(rover.get("e_cap_wh") or 0.0)

    adjusted = dict(summary)
    base_energy_wh = float(summary.get("total_energy_consumed_wh", 0.0))
    adjusted["total_energy_consumed_wh"] = round(base_energy_wh + overhead_wh, 2)
    adjusted["sensor_overhead_wh"] = round(overhead_wh, 2)

    base_final_pct = float(summary.get("final_battery_pct", 0.0))
    overhead_pct = (100.0 * overhead_wh / e_cap_wh) if e_cap_wh > 0 else 0.0
    adjusted["final_battery_pct"] = round(max(0.0, base_final_pct - overhead_pct), 2)
    return adjusted
