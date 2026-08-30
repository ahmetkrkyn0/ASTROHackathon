"""How far the rover can drive before its position estimate outgrows
the corridor.

The uncertainty model is deliberately the simplest one that answers the
question: ``sigma(d) = sigma_0 + drift_rate * d``, a linear growth in
1-sigma horizontal error with distance travelled. Real error growth is
messier (terrain-dependent, partly stochastic, direction-correlated),
but the published mission figures come as "percent of distance
travelled", which IS a linear rate -- so a linear model is the honest
container for them, and anything fancier would be precision the inputs
do not have.

``check_localization_uncertainty`` fires when covariance exceeds the
corridor half-width. Setting sigma(d) equal to the half-width and
solving for d therefore gives the distance at which that trigger is
GUARANTEED to fire even with everything working nominally -- the
distance budget between absolute fixes. That number, compared per
odometry source against a real corridor's widths, is what
scripts/localization_budget.py tabulates.

Drift rates carried here, with sources (see Phase 7 plan 2.1):

- dead reckoning (wheel + IMU): ~10 percent of distance -- MER-class,
  Maimone et al., "Two years of Visual Odometry on the Mars Exploration
  Rovers".
- visual odometry: 0.5 percent -- inside the 0.22-2.45 percent
  ATE-per-distance band published for M2020-class VO.
- VO + skyline resets: drift still accumulates BETWEEN fixes, but each
  confident skyline match bounds it; the budget question becomes "how
  far between fixes", which is the same formula applied per leg.
"""

from __future__ import annotations

from dataclasses import dataclass

# (label, drift as a fraction of distance travelled, source note)
DRIFT_RATES: tuple[tuple[str, float, str], ...] = (
    (
        "dead_reckoning",
        0.10,
        "MER wheel+IMU dead reckoning, ~10% of distance (Maimone et al.)",
    ),
    (
        "visual_odometry",
        0.005,
        "M2020-class VO, 0.22-2.45% band, 0.5% taken as representative",
    ),
)


@dataclass(frozen=True)
class DistanceBudget:
    """How far one odometry source can go before a given half-width."""

    source: str
    drift_rate: float
    sigma_0_m: float
    half_width_m: float
    distance_m: float  # inf when drift is zero and sigma_0 < half-width
    note: str


def distance_until_uncertainty_exceeds(
    half_width_m: float,
    drift_rate: float,
    sigma_0_m: float = 0.0,
) -> float:
    """Distance at which ``sigma_0 + drift_rate * d`` reaches *half_width_m*.

    Returns 0.0 when the initial uncertainty already exceeds the
    half-width (the trigger would fire before the first metre), and inf
    when drift is zero and the initial uncertainty fits -- an absolute
    source holding its fix indefinitely.
    """
    half_width = float(half_width_m)
    sigma_0 = float(sigma_0_m)
    rate = float(drift_rate)

    if half_width < 0.0:
        raise ValueError("half_width_m must be non-negative")
    if rate < 0.0:
        raise ValueError("drift_rate must be non-negative")
    if sigma_0 < 0.0:
        raise ValueError("sigma_0_m must be non-negative")

    headroom = half_width - sigma_0
    if headroom <= 0.0:
        return 0.0
    if rate == 0.0:
        return float("inf")
    return headroom / rate


def budget_for_source(
    source: str,
    drift_rate: float,
    half_width_m: float,
    sigma_0_m: float = 0.0,
    note: str = "",
) -> DistanceBudget:
    return DistanceBudget(
        source=source,
        drift_rate=float(drift_rate),
        sigma_0_m=float(sigma_0_m),
        half_width_m=float(half_width_m),
        distance_m=distance_until_uncertainty_exceeds(
            half_width_m, drift_rate, sigma_0_m
        ),
        note=note,
    )
