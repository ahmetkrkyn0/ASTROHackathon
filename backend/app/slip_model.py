"""Wheel slip: the gap between distance commanded and distance covered.

``cost_engine.edge_energy_wh`` assumes the rover covers exactly the
distance it was told to. On loose regolith it does not -- the wheels turn
further than the body advances, and the energy and time for a traverse
are correspondingly higher. Ignoring that makes every energy estimate
systematically optimistic, which is the P1 finding in
``docs/research/05_engel_kacinma.md`` 3.1.

Slip also happens to be the one odometry signal LunaPath can check
without any perception at all: commanded distance is something the
planner knows, travelled distance is something ``PoseEstimate`` reports,
and a growing divergence between them means the wheels are digging in.
That is why this module lives in Phase 7 rather than Phase 1.

Calibration status -- read this before quoting any number
---------------------------------------------------------
``I0`` and ``K`` are a rough literature-shaped approximation, NOT values
measured against lunar regolith. Following Phase 1's ``layer_validity``
convention, this module labels itself ``SLIP_MODEL_VALIDITY =
"UNCALIBRATED"`` and every consumer is expected to carry that label
through to its output.

What this model claims: energy and time on slopes are HIGHER than the
slip-free calculation, and the gap widens with slope. That direction is
solid and physically necessary.

What it does not claim: that the correction is the right SIZE. Do not
present "+22% at 20 degrees" as a measured result -- it is the output of
an uncalibrated exponential fit, and the honest phrasing is that the
model says the penalty is substantial and grows sharply, not that it is
precisely 22%.
"""

from __future__ import annotations

import math

from .replan_triggers import TriggerResult

SLIP_MODEL_VALIDITY: str = "UNCALIBRATED"

# i = I0 * exp(K * theta). I0 is the flat-ground slip a driven wheel shows
# on loose material; K sets how fast it worsens with slope.
I0: float = 0.02
K: float = 0.11

# Slip cannot reach 1.0 -- that is the wheels spinning with the rover
# stationary, where effective distance would divide by zero and energy
# would be infinite. Real vehicles bog down and stop before this; the cap
# keeps the arithmetic finite and the failure legible.
MAX_SLIP_RATIO: float = 0.9

# Ratio of travelled to commanded distance below which the rover is
# losing so much ground that the plan's distance assumptions no longer
# hold. From the trigger table in 05_engel_kacinma.md.
SLIP_ACCUMULATION_THRESHOLD: float = 0.75


def slip_ratio(slope_deg: float) -> float:
    """Fraction of wheel travel lost to slip on a *slope_deg* incline.

    0 means the rover advances exactly as commanded; 0.2 means it covers
    80 percent of the commanded distance. Uncalibrated -- see the module
    docstring.
    """
    slope = abs(float(slope_deg))
    return float(min(MAX_SLIP_RATIO, I0 * math.exp(K * slope)))


def effective_distance_m(distance_m: float, slope_deg: float) -> float:
    """Wheel distance needed to advance *distance_m* over the ground.

    Energy and travel time both scale with this rather than with the
    commanded distance, because the wheels turn the full amount whether
    or not the body keeps up.
    """
    return float(distance_m) / (1.0 - slip_ratio(slope_deg))


def slip_energy_multiplier(slope_deg: float) -> float:
    """Factor by which slip raises the energy and time of a traverse.

    ``edge_energy_wh`` is linear in travel time and travel time is linear
    in distance, so a single multiplier covers both.
    """
    return 1.0 / (1.0 - slip_ratio(slope_deg))


def check_slip_accumulation(
    travelled_m: float,
    commanded_m: float,
    threshold: float = SLIP_ACCUMULATION_THRESHOLD,
) -> TriggerResult:
    """Fire when measured progress falls below *threshold* of commanded.

    ``travelled_m`` is what odometry reports having covered;
    ``commanded_m`` is what the planner asked for. A ratio well under 1
    means the terrain is costing more than planned, and the remaining
    route's energy and time budgets are no longer trustworthy.
    """
    commanded = float(commanded_m)
    travelled = float(travelled_m)

    if commanded <= 0.0:
        # No distance was commanded, so there is no ratio to judge. Report
        # not-fired with the reason stated rather than dividing by zero or
        # returning a fired trigger on a vacuous comparison.
        return TriggerResult(
            "slip_accumulation",
            False,
            "no commanded distance to compare against",
        )

    ratio = travelled / commanded
    fired = ratio < float(threshold)
    return TriggerResult(
        "slip_accumulation",
        fired,
        f"travelled {travelled:.1f} m of {commanded:.1f} m commanded "
        f"(ratio {ratio:.2f}, threshold {threshold:.2f}); "
        f"slip model is {SLIP_MODEL_VALIDITY}",
    )
