"""Regression tests for the backend review findings.

One test (or small group) per numbered finding in BACKEND_REVIEW.md, named so
a failure points straight back at the finding it protects. These are the
tests whose absence let the findings survive: #1 in particular went unnoticed
because nothing asserted that a weight the API accepts actually changes
anything.
"""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.constants import ROVERS, get_rover
from app.cost_engine import (
    compute_cost_grid,
    f_energy_cell,
    f_slope,
    f_thermal,
)
from app.costmap import PlanContext, default_cost_map
from app.main import app
from app.rover_grids import grids_for_rover
from app.traversability import compute_traversability_bool


# ── #1  f_energy_cell is a real MRU criterion, not an inert term ───────────

def test_energy_penalty_is_zero_on_flat_ground():
    assert f_energy_cell(0.0, get_rover("lpr_1")) == pytest.approx(0.0)


def test_energy_penalty_reaches_one_at_the_slope_limit():
    for rover_id in ROVERS:
        rover = get_rover(rover_id)
        limit = float(rover["slope_max_deg"])
        assert f_energy_cell(limit, rover) == pytest.approx(1.0)


def test_energy_penalty_is_monotonic_and_bounded():
    rover = get_rover("lpr_1")
    values = [f_energy_cell(float(s), rover) for s in range(0, 26)]
    assert all(0.0 <= v <= 1.0 for v in values)
    assert all(b >= a for a, b in zip(values, values[1:]))


def test_energy_penalty_is_infinite_above_the_slope_limit():
    rover = get_rover("lpr_1")
    assert f_energy_cell(float(rover["slope_max_deg"]) + 1.0, rover) == float("inf")


def test_energy_penalty_is_independent_of_grid_resolution():
    """The old f_energy scaled with edge length, so the same terrain scored
    differently at 5 m and 80 m. A ratio cannot. (Review #1.)"""
    rover = get_rover("lpr_1")
    shape = (12, 12)
    slope = np.full(shape, 12.0)
    thermal = np.full(shape, -60.0)
    shadow = np.full(shape, 0.2)
    trav = np.ones(shape, dtype=bool)

    fine = compute_cost_grid(slope, thermal, shadow, 5.0, traversable=trav, rover=rover)
    coarse = compute_cost_grid(slope, thermal, shadow, 80.0, traversable=trav, rover=rover)
    assert np.allclose(fine, coarse)


def test_energy_contributes_a_meaningful_share_of_cell_cost():
    """The bug was a term worth 0.04% of cost while weighted 25.9%."""
    rover = get_rover("lpr_1")
    weights = {"w_slope": 0.409, "w_energy": 0.259, "w_shadow": 0.142, "w_thermal": 0.190}
    energy = weights["w_energy"] * f_energy_cell(10.0, rover)
    slope = weights["w_slope"] * f_slope(10.0, rover)
    thermal = weights["w_thermal"] * f_thermal(-100.0, rover)
    assert energy > 0.1 * slope
    assert energy > 0.1 * thermal


def test_energy_weight_changes_the_cost_grid():
    """The end-to-end symptom: sweeping w_energy changed nothing at all."""
    rover = get_rover("lpr_1")
    rng = np.random.default_rng(0)
    shape = (24, 24)
    slope = rng.uniform(0.0, 24.0, shape)
    thermal = np.full(shape, -60.0)
    shadow = np.full(shape, 0.2)
    trav = np.ones(shape, dtype=bool)

    def grid(w_energy: float) -> np.ndarray:
        return compute_cost_grid(
            slope, thermal, shadow, 5.0,
            traversable=trav,
            weights={"w_slope": 0.409, "w_energy": w_energy,
                     "w_shadow": 0.142, "w_thermal": 0.190},
            rover=rover,
        )

    assert not np.allclose(grid(0.0), grid(2.0))


# ── #2  traversability is recomputed, never trusted from a label ───────────

def _fake_grids(shape=(16, 16)) -> dict:
    rng = np.random.default_rng(1)
    slope = rng.uniform(0.0, 30.0, shape)
    thermal = np.full(shape, -60.0)
    return {
        "slope": slope,
        "thermal": thermal,
        "shadow_ratio": np.full(shape, 0.2),
        "elevation": np.zeros(shape),
        "traversable": np.ones(shape, dtype=bool),  # deliberately wrong
        "cost": np.zeros(shape),
        "metadata": {
            "origin": {"x": 0.0, "y": 0.0},
            "resolution_m": 5.0,
            "shape": list(shape),
            "default_rover_id": "nasa_viper",
            "cost_weights": {},
        },
    }


def test_mislabelled_metadata_does_not_yield_an_over_permissive_mask():
    """metadata claiming 'nasa_viper' does not make an all-true mask correct."""
    grids = _fake_grids()
    out = grids_for_rover(grids, "nasa_viper")
    truth = compute_traversability_bool(
        grids["slope"], grids["thermal"], grids["elevation"],
        rover=get_rover("nasa_viper"),
    )
    assert np.array_equal(out["traversable"], truth)
    assert not (out["traversable"] & ~truth).any()


def test_every_rover_gets_its_own_slope_limit_enforced():
    grids = _fake_grids()
    for rover_id in ROVERS:
        rover = get_rover(rover_id)
        out = grids_for_rover(grids, rover_id)
        passable_slopes = np.asarray(grids["slope"])[out["traversable"]]
        assert passable_slopes.max(initial=0.0) <= float(rover["slope_max_deg"])


def test_cost_is_recomputed_when_the_stored_mask_disagrees():
    """A stale cost grid must not survive a mask that no longer matches it."""
    grids = _fake_grids()
    out = grids_for_rover(grids, "nasa_viper")
    assert not np.array_equal(out["cost"], grids["cost"])
    assert np.isinf(out["cost"][~out["traversable"]]).all()


# ── #3  the DEM path cannot escape the DEM directory ──────────────────────

@pytest.mark.parametrize(
    "attack",
    [
        "../../../../etc/passwd",
        "..\\..\\..\\Windows\\win.ini",
        "/etc/shadow",
        "C:\\Windows\\win.ini",
        "../README.md",
    ],
)
def test_load_dem_rejects_paths_outside_the_dem_directory(attack):
    client = TestClient(app)
    response = client.post("/api/load-dem", json={"dem_file": attack})
    assert response.status_code == 422
    assert "DEM directory" in response.json()["detail"]


def test_load_dem_still_reports_a_missing_file_as_404():
    """The guard must not swallow the ordinary not-found case."""
    client = TestClient(app)
    response = client.post("/api/load-dem", json={"dem_file": "no_such_dem.tif"})
    assert response.status_code == 404
