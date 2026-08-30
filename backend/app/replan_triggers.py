"""Replan trigger taxonomy.

ESA ADE's ADAM module changes a nominal plan autonomously when a hazard is
recognised, but published material does not enumerate the triggers. This
module is that enumeration, as pure predicates with unit tests -- the
concrete evidence behind "we do replanning".

Each check is deliberately independent and side-effect free so it can run
on the ground, on the rover, or inside a test.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from .constants import inner_temperature_drop_k, soc_deviation_threshold

# Defaults for the DEFAULT rover. Every threshold that has a rover-specific
# derivation now takes one; these constants remain the value that derivation
# produces for lpr_1, so existing callers see no change.
# (Round 3 review, L-8.)
SOC_DEVIATION_THRESHOLD: float = 0.10        # fraction of capacity
INNER_TEMPERATURE_DROP_K: float = 5.0        # kelvin below prediction
TIME_DRIFT_MINUTES: float = 30.0
COMM_WINDOW_MINUTES: float = 15.0

# How many standard deviations of position error must fit inside the
# corridor. Comparing 1 sigma against the half-width means the trigger fires
# only once there is already roughly a one-in-three chance the rover is
# OUTSIDE its corridor -- late, for a safety check. Two sigma brings that to
# about one in twenty, the conventional engineering margin.
# (Round 3 review, L-9.)
LOCALIZATION_SIGMA_MULTIPLIER: float = 2.0


@dataclass(frozen=True)
class TriggerResult:
    trigger_id: str
    triggered: bool
    detail: str


def check_soc_deviation(
    actual_soc: float,
    planned_soc: float,
    rover: Mapping[str, Any] | None = None,
) -> TriggerResult:
    """Being behind the energy plan forces a replan; being ahead does not.

    The threshold is half the rover's own SOC reserve: a rover holding 30
    percent has more room to absorb a deviation than one holding 20, and a
    single global constant said otherwise. (Round 3 review, L-8.)
    """
    threshold = soc_deviation_threshold(rover)
    shortfall = float(planned_soc) - float(actual_soc)
    fired = shortfall > threshold
    return TriggerResult(
        "soc_deviation",
        fired,
        f"SOC {actual_soc:.3f} vs planned {planned_soc:.3f} "
        f"(shortfall {shortfall:.3f}, threshold {threshold:.3f})",
    )


def check_inner_temperature(
    actual_c: float,
    predicted_c: float,
    rover: Mapping[str, Any] | None = None,
) -> TriggerResult:
    """Scaled to the width of the battery envelope. (Round 3 review, L-8.)"""
    threshold = inner_temperature_drop_k(rover)
    drop = float(predicted_c) - float(actual_c)
    fired = drop > threshold
    return TriggerResult(
        "inner_temperature",
        fired,
        f"inner {actual_c:.2f} C vs predicted {predicted_c:.2f} C "
        f"(drop {drop:.2f} K, threshold {threshold:.2f} K)",
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
    covariance_m: float,
    half_width_m: float,
    sigma_multiplier: float = LOCALIZATION_SIGMA_MULTIPLIER,
) -> TriggerResult:
    """Fire when the position uncertainty no longer fits inside the corridor.

    *covariance_m* is a 1-sigma figure. Comparing it directly against the
    half-width fires only when the rover is already about as likely as not
    to be outside -- see LOCALIZATION_SIGMA_MULTIPLIER.
    (Round 3 review, L-9.)
    """
    bound_m = float(covariance_m) * float(sigma_multiplier)
    fired = bound_m > float(half_width_m)
    return TriggerResult(
        "localization_uncertainty",
        fired,
        f"position uncertainty {bound_m:.1f} m "
        f"({sigma_multiplier:g} sigma of {covariance_m:.1f} m) exceeds "
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
    # slip_accumulation used to be evaluated ONLY by
    # localization.evaluate_pose, so POST /api/replan neither ran it nor
    # listed it as skipped -- a trigger missing from the module that calls
    # itself "that enumeration", and invisible in the one place a caller
    # reads to learn what was actually checked. (Round 3 review, L-10.)
    "slip_accumulation": ("map_progress_m", "odometer_claim_m"),
}


def evaluate_triggers(
    state: Mapping[str, Any], rover: Mapping[str, Any] | None = None
) -> list[TriggerResult]:
    """Run every check whose inputs are present; return only fired triggers.

    Kept for callers that only want the fired list. Prefer
    :func:`evaluate_triggers_detailed` when you need to know whether a
    trigger was actually evaluated -- an empty list here means "nothing
    fired", which is NOT the same as "everything was checked".
    """
    return evaluate_triggers_detailed(state, rover)["fired"]


def _is_unusable(value: Any) -> bool:
    """True when *value* cannot be compared against a threshold.

    NaN and infinity are the cases that matter. Every comparison against
    NaN is False, so a NaN telemetry value makes its trigger's predicate
    False and the trigger reports "checked and clear" -- a fail-open
    answer from a safety mechanism, on telemetry that is visibly broken.
    A non-numeric value would raise instead; both are "not checkable".
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return True
    return not math.isfinite(float(value))


def evaluate_triggers_detailed(
    state: Mapping[str, Any], rover: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Evaluate every trigger, reporting the ones that could not be checked.

    Each check is guarded by the presence AND USABILITY of its telemetry
    keys, so a partial or malformed state produced an empty fired-list
    that read as "no replan needed" -- a fail-open answer from a safety
    mechanism. A telemetry packet missing actual_soc reported all-clear at
    1% battery, and nothing said so. Returning the skipped list lets the
    caller see the difference between "checked and clear" and "never
    checked". (Backend review, #4.)

    The usability half closes round 2's H-1: a bare ``NaN`` literal is
    legal JSON to Python's decoder, so a client can put NaN in any
    telemetry field and pass ``dict[str, float]`` validation. That value
    then makes every comparison False and the trigger was reported as
    EVALUATED -- the same fail-open shape as a missing key, arriving
    through the value instead. Non-finite values are now skipped with a
    reason, which also keeps the response JSON-serialisable: Starlette
    renders with allow_nan=False and a NaN echoed back in trigger_state
    took /api/pose down with a 500.
    """
    results: list[TriggerResult] = []
    skipped: list[dict[str, Any]] = []

    for trigger_id, required in _TRIGGER_INPUTS.items():
        missing = [key for key in required if key not in state]
        if missing:
            skipped.append({"trigger_id": trigger_id, "missing": missing})
            continue

        unusable = [key for key in required if _is_unusable(state[key])]
        if unusable:
            skipped.append(
                {
                    "trigger_id": trigger_id,
                    "missing": unusable,
                    "reason": "non-finite or non-numeric telemetry value",
                }
            )
            continue

        if trigger_id == "soc_deviation":
            results.append(
                check_soc_deviation(
                    state["actual_soc"], state["planned_soc"], rover
                )
            )
        elif trigger_id == "inner_temperature":
            results.append(
                check_inner_temperature(
                    state["actual_inner_c"], state["predicted_inner_c"], rover
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
        elif trigger_id == "slip_accumulation":
            from .slip_model import check_slip_accumulation

            results.append(
                check_slip_accumulation(
                    state["map_progress_m"], state["odometer_claim_m"]
                )
            )

    return {
        "fired": [result for result in results if result.triggered],
        "evaluated": [result.trigger_id for result in results],
        "skipped": skipped,
    }
