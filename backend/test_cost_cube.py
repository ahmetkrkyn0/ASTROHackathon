"""Time-sliced cost cube tests."""

from __future__ import annotations

import numpy as np
import pytest

from app.constants import get_rover
from app.cost_cube import build_cost_cube, coarsen_grid, coarsen_traversable

SHAPE = (8, 8)


def _base_grids() -> dict:
    return {
        "slope": np.full(SHAPE, 4.0),
        "thermal": np.full(SHAPE, -60.0),
        "traversable": np.ones(SHAPE, dtype=bool),
        "metadata": {"resolution_m": 80.0, "shape": list(SHAPE)},
    }


def test_coarsen_grid_averages_blocks():
    grid = np.arange(16, dtype=np.float64).reshape(4, 4)
    out = coarsen_grid(grid, factor=2)
    assert out.shape == (2, 2)
    assert out[0, 0] == pytest.approx(np.mean([0, 1, 4, 5]))


def test_coarsen_grid_factor_one_is_identity():
    grid = np.arange(9, dtype=np.float64).reshape(3, 3)
    assert np.array_equal(coarsen_grid(grid, factor=1), grid)


def test_coarsen_grid_rejects_non_divisible_shape():
    with pytest.raises(ValueError):
        coarsen_grid(np.zeros((5, 4)), factor=2)


def test_coarsen_traversable_is_conservative():
    """A coarse cell is passable only if every fine cell inside it is."""
    fine = np.ones((4, 4), dtype=bool)
    fine[0, 0] = False
    out = coarsen_traversable(fine, factor=2)
    assert out.shape == (2, 2)
    assert not out[0, 0]
    assert out[1, 1]


def test_cost_cube_has_one_slice_per_shadow_series_entry():
    series = [np.full(SHAPE, r) for r in (0.0, 0.5, 1.0)]
    cube = build_cost_cube(_base_grids(), series, get_rover())
    assert cube.shape == (3, *SHAPE)


def test_cost_cube_is_monotonic_in_shadow():
    """More shadow at a given cell must never make it cheaper."""
    series = [np.full(SHAPE, r) for r in (0.0, 0.5, 1.0)]
    cube = build_cost_cube(_base_grids(), series, get_rover())
    assert cube[0, 4, 4] < cube[1, 4, 4] < cube[2, 4, 4]


def test_cost_cube_applies_coarsening():
    series = [np.zeros(SHAPE), np.ones(SHAPE)]
    cube = build_cost_cube(_base_grids(), series, get_rover(), coarsen=2)
    assert cube.shape == (2, 4, 4)


def test_cost_cube_rejects_empty_series():
    with pytest.raises(ValueError):
        build_cost_cube(_base_grids(), [], get_rover())


def test_cost_cube_rejects_shape_mismatch():
    with pytest.raises(ValueError):
        build_cost_cube(_base_grids(), [np.zeros((4, 4))], get_rover())


from app.cost_cube import build_wait_cost_cube, wait_cost
from app.cost_engine import resolve_weights


def test_waiting_in_full_sun_is_free():
    """Solar input exceeds idle+heater draw -> no energy penalty."""
    rover = get_rover()
    weights = resolve_weights(None, rover)
    assert wait_cost(1.0, 1.0, rover, weights) == pytest.approx(0.0, abs=1e-12)


def test_waiting_in_full_shadow_costs_more_than_in_sun():
    rover = get_rover()
    weights = resolve_weights(None, rover)
    assert wait_cost(0.0, 1.0, rover, weights) > wait_cost(1.0, 1.0, rover, weights)


def test_wait_cost_grows_with_duration():
    rover = get_rover()
    weights = resolve_weights(None, rover)
    assert wait_cost(0.0, 2.0, rover, weights) > wait_cost(0.0, 1.0, rover, weights)


def test_wait_cost_is_never_negative():
    rover = get_rover()
    weights = resolve_weights(None, rover)
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        assert wait_cost(frac, 1.0, rover, weights) >= 0.0


def test_wait_cost_cube_shape_matches_series_and_coarsening():
    series = [np.ones(SHAPE), np.zeros(SHAPE)]
    cube = build_wait_cost_cube(series, get_rover(), dt_hours=1.0, coarsen=2)
    assert cube.shape == (2, 4, 4)
    assert (cube[1] > cube[0]).all()
