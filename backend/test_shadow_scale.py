"""Shadow term scale regression tests.

The AHP weight for shadow is 0.142 (LPR-1). A fully shadowed cell must
therefore cost ~0.142 more than an identical fully lit cell. Before the
Task 2 fix, compute_cost_grid fed f_shadow a SINGLE-EDGE duration
(0.111 h) normalised against h_max_shadow_h (50 h), producing a
contribution of ~0.00005 -- i.e. the criterion was effectively dead.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.constants import get_rover
from app.cost_engine import compute_cost_grid

RESOLUTION_M = 80.0
# -120 C keeps the cell traversable (> -150 C) while making f_thermal ~1.0,
# so the total cost stays well above the max(0.01, cost) clamp.
THERMAL_C = -120.0


def _cost_for_shadow_ratio(ratio: float) -> float:
    shape = (1, 1)
    slope = np.zeros(shape, dtype=np.float64)
    thermal = np.full(shape, THERMAL_C, dtype=np.float64)
    shadow = np.full(shape, ratio, dtype=np.float64)
    traversable = np.ones(shape, dtype=bool)
    grid = compute_cost_grid(
        slope, thermal, shadow, RESOLUTION_M, traversable=traversable
    )
    return float(grid[0, 0])


def test_fully_shadowed_cell_costs_full_shadow_weight():
    """shadow_ratio 0 -> 1 must move the cell cost by ~w_shadow."""
    w_shadow = float(get_rover()["w_shadow"])
    delta = _cost_for_shadow_ratio(1.0) - _cost_for_shadow_ratio(0.0)
    assert delta == pytest.approx(w_shadow, rel=0.05)


def test_shadow_cost_is_monotonic():
    """More shadow must never cost less."""
    costs = [_cost_for_shadow_ratio(r) for r in (0.0, 0.25, 0.5, 0.75, 1.0)]
    assert costs == sorted(costs)
    assert costs[-1] > costs[0]
