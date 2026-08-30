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


# Which telemetry keys each trigger needs. Declared once so evaluate_triggers
# can report what it could NOT check instead of silently skipping it.
_TRIGGER_INPUTS: dict[str, tuple[str, ...]] = {
    "soc_deviation": ("actual_soc", "planned_soc"),
    "inner_temperature": ("actual_inner_c", "predicted_inner_c"),
    "time_drift": ("drift_minutes",),
    "corridor_violation": ("lateral_offset_m", "half_width_m"),
    "comm_window": ("comm_minutes_remaining",),
    "localization_uncertainty": ("localization_covariance_m", "half_width_m"),
}


def evaluate_triggers(state: Mapping[str, Any]) -> list[TriggerResult]:
    """Run every check whose inputs are present; return only fired triggers.

    Kept for callers that only want the fired list. Prefer
    :func:`evaluate_triggers_detailed` when you need to know whether a
    trigger was actually evaluated -- an empty list here means "nothing
    fired", which is NOT the same as "everything was checked".
    """
    return evaluate_triggers_detailed(state)["fired"]


def evaluate_triggers_detailed(state: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate every trigger, reporting the ones that could not be checked.

    Each check is guarded by the presence of its telemetry keys, so a
    partial or malformed state produced an empty fired-list that read as
    "no replan needed" -- a fail-open answer from a safety mechanism.
    A telemetry packet missing actual_soc reported all-clear at 1% battery,
    and nothing said so. Returning the skipped list lets the caller see the
    difference between "checked and clear" and "never checked".
    (Backend review, #4.)
    """
    results: list[TriggerResult] = []
    skipped: list[dict[str, Any]] = []

    for trigger_id, required in _TRIGGER_INPUTS.items():
        missing = [key for key in required if key not in state]
        if missing:
            skipped.append({"trigger_id": trigger_id, "missing": missing})
            continue

        if trigger_id == "soc_deviation":
            results.append(
                check_soc_deviation(state["actual_soc"], state["planned_soc"])
            )
        elif trigger_id == "inner_temperature":
            results.append(
                check_inner_temperature(
                    state["actual_inner_c"], state["predicted_inner_c"]
                )
            )
        elif trigger_id == "time_drift":
            results.append(check_time_drift(state["drift_minutes"]))
        elif trigger_id == "corridor_violation":
            results.append(
                check_corridor_violation(
                    state["lateral_offset_m"], state["half_width_m"]
                )
            )
        elif trigger_id == "comm_window":
            results.append(check_comm_window(state["comm_minutes_remaining"]))
        elif trigger_id == "localization_uncertainty":
            results.append(
                check_localization_uncertainty(
                    state["localization_covariance_m"], state["half_width_m"]
                )
            )

    return {
        "fired": [result for result in results if result.triggered],
        "evaluated": [result.trigger_id for result in results],
        "skipped": skipped,
    }
