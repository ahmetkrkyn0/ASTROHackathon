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

    # min_battery_pct used to pass through untouched while final_battery_pct
    # dropped, so the adjusted summary could report a MINIMUM above its own
    # final value -- an impossible battery curve. The overhead accumulates
    # over the traverse, so the honest post-hoc bound is the same shift
    # applied to the minimum. The risk-level counters
    # (critical_steps_count / high_or_above_steps_count) still describe the
    # UNADJUSTED curve and are dropped rather than left silently stale: this
    # is a scoping adjustment, not a re-simulation. (Backend review, #12.)
    if "min_battery_pct" in summary:
        base_min_pct = float(summary["min_battery_pct"])
        adjusted["min_battery_pct"] = round(max(0.0, base_min_pct - overhead_pct), 2)

    if overhead_wh > 0.0:
        for stale in ("critical_steps_count", "high_or_above_steps_count"):
            if stale in adjusted:
                adjusted[stale] = None
        adjusted["risk_counts_valid"] = False

    return adjusted
