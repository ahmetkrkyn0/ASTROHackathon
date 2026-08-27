"""Replan trigger taxonomy.

ESA ADE's ADAM module changes a nominal plan autonomously when a hazard is
recognised, but published material does not enumerate the triggers. This
module is that enumeration, as pure predicates with unit tests -- the
concrete evidence behind "we do replanning".

Each check is deliberately independent and side-effect free so it can run
on the ground, on the rover, or inside a test.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

SOC_DEVIATION_THRESHOLD: float = 0.10        # fraction of capacity
INNER_TEMPERATURE_DROP_K: float = 5.0        # kelvin below prediction
TIME_DRIFT_MINUTES: float = 30.0
COMM_WINDOW_MINUTES: float = 15.0


@dataclass(frozen=True)
class TriggerResult:
    trigger_id: str
    triggered: bool
    detail: str


def check_soc_deviation(actual_soc: float, planned_soc: float) -> TriggerResult:
    """Being behind the energy plan forces a replan; being ahead does not."""
    shortfall = float(planned_soc) - float(actual_soc)
    fired = shortfall > SOC_DEVIATION_THRESHOLD
    return TriggerResult(
        "soc_deviation",
        fired,
        f"SOC {actual_soc:.3f} vs planned {planned_soc:.3f} "
        f"(shortfall {shortfall:.3f}, threshold {SOC_DEVIATION_THRESHOLD})",
    )


def check_inner_temperature(actual_c: float, predicted_c: float) -> TriggerResult:
    drop = float(predicted_c) - float(actual_c)
    fired = drop > INNER_TEMPERATURE_DROP_K
    return TriggerResult(
        "inner_temperature",
        fired,
        f"inner {actual_c:.2f} C vs predicted {predicted_c:.2f} C "
        f"(drop {drop:.2f} K, threshold {INNER_TEMPERATURE_DROP_K} K)",
    )


def check_time_drift(drift_minutes: float) -> TriggerResult:
    """Illumination is a function of time; drifting off schedule invalidates it."""
    fired = abs(float(drift_minutes)) > TIME_DRIFT_MINUTES
    return TriggerResult(
        "time_drift",
        fired,
        f"schedule drift {drift_minutes:.1f} min "
        f"(threshold +/-{TIME_DRIFT_MINUTES} min)",
    )


def check_corridor_violation(
    lateral_offset_m: float, half_width_m: float
) -> TriggerResult:
    fired = float(lateral_offset_m) > float(half_width_m)
    return TriggerResult(
        "corridor_violation",
        fired,
        f"lateral offset {lateral_offset_m:.1f} m exceeds "
        f"corridor half-width {half_width_m:.1f} m",
    )


def check_comm_window(
    minutes_remaining: float, threshold_minutes: float = COMM_WINDOW_MINUTES
) -> TriggerResult:
    fired = float(minutes_remaining) < float(threshold_minutes)
    return TriggerResult(
        "comm_window",
        fired,
        f"{minutes_remaining:.1f} min of Earth visibility left "
        f"(threshold {threshold_minutes} min)",
    )


def check_localization_uncertainty(
    covariance_m: float, half_width_m: float
) -> TriggerResult:
    fired = float(covariance_m) > float(half_width_m)
    return TriggerResult(
        "localization_uncertainty",
        fired,
        f"position covariance {covariance_m:.1f} m exceeds "
        f"corridor half-width {half_width_m:.1f} m",
    )


def evaluate_triggers(state: Mapping[str, Any]) -> list[TriggerResult]:
    """Run every check whose inputs are present; return only fired triggers."""
    results: list[TriggerResult] = []

    if "actual_soc" in state and "planned_soc" in state:
        results.append(check_soc_deviation(state["actual_soc"], state["planned_soc"]))
    if "actual_inner_c" in state and "predicted_inner_c" in state:
        results.append(
            check_inner_temperature(state["actual_inner_c"], state["predicted_inner_c"])
        )
    if "drift_minutes" in state:
        results.append(check_time_drift(state["drift_minutes"]))
    if "lateral_offset_m" in state and "half_width_m" in state:
        results.append(
            check_corridor_violation(state["lateral_offset_m"], state["half_width_m"])
        )
    if "comm_minutes_remaining" in state:
        results.append(check_comm_window(state["comm_minutes_remaining"]))
    if "localization_covariance_m" in state and "half_width_m" in state:
        results.append(
            check_localization_uncertainty(
                state["localization_covariance_m"], state["half_width_m"]
            )
        )

    return [result for result in results if result.triggered]
