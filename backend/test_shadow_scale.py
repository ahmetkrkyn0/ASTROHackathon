"""Shadow term scale regression tests.

The AHP weight for shadow is 0.142 (LPR-1). Before the Task 2 fix,
compute_cost_grid fed f_shadow a SINGLE-EDGE duration (0.111 h) normalised
against h_max_shadow_h (50 h), producing a contribution of ~0.00005 -- i.e.
the criterion was effectively dead.

Since round 3's H-4 fix, ShadowLayer is no longer the ONLY layer that reads
illumination: the energy term measures net battery draw, which depends on
the solar input a cell offers. So a fully shadowed cell costs w_shadow more
on the shadow axis PLUS whatever the energy axis adds -- and the tests below
assert that decomposition rather than a single weight.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.constants import get_rover
from app.cost_engine import compute_cost_grid, f_shadow_cell

RESOLUTION_M = 80.0
# -120 C keeps the cell traversable (> -150 C) while making f_thermal ~1.0,
# so the total cost stays well above the max(0.01, cost) clamp.
THERMAL_C = -120.0
# The cell slope the helper below uses; the energy term needs it to compute
# its own shadow response.
SLOPE_DEG = 0.0


def _cost_for_shadow_ratio(ratio: float) -> float:
    shape = (1, 1)
    slope = np.full(shape, SLOPE_DEG, dtype=np.float64)
    thermal = np.full(shape, THERMAL_C, dtype=np.float64)
    shadow = np.full(shape, ratio, dtype=np.float64)
    traversable = np.ones(shape, dtype=bool)
    grid = compute_cost_grid(
        slope, thermal, shadow, RESOLUTION_M, traversable=traversable
    )
    return float(grid[0, 0])


def test_fully_shadowed_cell_costs_both_shadow_driven_terms():
    """shadow_ratio 0 -> 1 must move the cell cost by w_shadow PLUS the
    energy term's own response to shadow.

    This asserted w_shadow alone, on the premise that ShadowLayer was the
    only layer reading illumination. That premise was the H-4 finding: the
    energy layer read slope only, which made it rank-identical to the slope
    layer (measured Spearman 1.000000) and left a quarter of the AHP weight
    vector unable to reorder anything. Energy now measures the NET battery
    draw -- draw minus the solar the cell offers -- so darkness costs energy
    too, and the total delta is the sum of the two contributions.
    (Round 3 review, H-4.)
    """
    from app.cost_engine import f_energy_cell

    rover = get_rover()
    w_shadow = float(rover["w_shadow"])
    w_energy = float(rover["w_energy"])

    delta = _cost_for_shadow_ratio(1.0) - _cost_for_shadow_ratio(0.0)

    shadow_part = w_shadow * (f_shadow_cell(1.0) - f_shadow_cell(0.0))
    energy_part = w_energy * (
        f_energy_cell(SLOPE_DEG, rover, 1.0) - f_energy_cell(SLOPE_DEG, rover, 0.0)
    )
    assert shadow_part == pytest.approx(w_shadow, rel=1e-9)
    assert energy_part > 0.0, "energy must respond to shadow"
    assert delta == pytest.approx(shadow_part + energy_part, rel=1e-6)


def test_shadow_cost_is_monotonic():
    """More shadow must never cost less."""
    costs = [_cost_for_shadow_ratio(r) for r in (0.0, 0.25, 0.5, 0.75, 1.0)]
    assert costs == sorted(costs)
    assert costs[-1] > costs[0]


def test_f_shadow_cell_endpoints():
    """Fully lit -> 0, fully shadowed -> 1 (MRU normalisation)."""
    assert f_shadow_cell(0.0) == pytest.approx(0.0, abs=1e-12)
    assert f_shadow_cell(1.0) == pytest.approx(1.0, abs=1e-12)


def test_f_shadow_cell_midpoint_matches_exponential_shape():
    """Same exponential shape as f_shadow: (e^(3r) - 1) / (e^3 - 1)."""
    assert f_shadow_cell(0.5) == pytest.approx(0.182426, abs=1e-6)


def test_f_shadow_cell_clamps_out_of_range_input():
    assert f_shadow_cell(-0.3) == pytest.approx(0.0, abs=1e-12)
    assert f_shadow_cell(1.7) == pytest.approx(1.0, abs=1e-12)
