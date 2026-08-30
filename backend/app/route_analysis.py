"""Route-level statistical summary, inspired by ETH lunar_planner's
PathAnalysis tool (spec 1.5).

simulate_path already produces a per-step RoverState sequence;
summarize_simulation reduces it to scalar totals. This module adds the
distribution view PathAnalysis has and LunaPath lacked: how much of the
route sits in each slope band, what fraction of steps were at each risk
level, and the thermal extremes actually crossed. Kept separate from
summarize_simulation so neither function's tested output changes shape.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .simulation import RoverState

DEFAULT_SLOPE_BINS_DEG: tuple[float, ...] = (0.0, 5.0, 10.0, 15.0, 20.0, 25.0)


def route_statistics(
    states: Sequence[RoverState],
    slope_bins_deg: Sequence[float] = DEFAULT_SLOPE_BINS_DEG,
) -> dict[str, Any]:
    """Distribution statistics over a simulated route."""
    if not states:
        return {
            "waypoint_count": 0,
            "slope_histogram": [],
            "risk_breakdown_pct": {},
            "min_surface_temp_c": None,
            "max_surface_temp_c": None,
        }

    bins = list(slope_bins_deg)
    if len(bins) < 2:
        raise ValueError("slope_bins_deg needs at least two edges")

    # Values outside the bin range fall into the nearest edge bin rather
    # than being dropped. With the default bins nothing lands outside --
    # traversability already caps slope at the rover's slope_max_deg (25
    # deg, the top edge) -- but callers may pass narrower bins, and a
    # histogram whose counts do not sum to waypoint_count would misreport
    # the route to whoever reads /api/plan.
    counts = [0] * (len(bins) - 1)
    last = len(bins) - 2
    for state in states:
        slope = state.slope_deg
        if slope < bins[0]:
            counts[0] += 1
            continue
        if slope >= bins[-1]:
            counts[last] += 1
            continue
        for i in range(len(bins) - 1):
            if bins[i] <= slope < bins[i + 1]:
                counts[i] += 1
                break

    total = len(states)
    histogram = [
        {
            "bin_low_deg": bins[i],
            "bin_high_deg": bins[i + 1],
            "count": counts[i],
            "pct": round(100.0 * counts[i] / total, 2),
        }
        for i in range(len(bins) - 1)
    ]

    risk_counts: dict[str, int] = {}
    for state in states:
        risk_counts[state.risk_level] = risk_counts.get(state.risk_level, 0) + 1
    risk_breakdown_pct = {
        level: round(100.0 * count / total, 2) for level, count in risk_counts.items()
    }

    temps = [state.surface_temp_c for state in states]

    return {
        "waypoint_count": total,
        "slope_histogram": histogram,
        "risk_breakdown_pct": risk_breakdown_pct,
        "min_surface_temp_c": round(min(temps), 2),
        "max_surface_temp_c": round(max(temps), 2),
    }
