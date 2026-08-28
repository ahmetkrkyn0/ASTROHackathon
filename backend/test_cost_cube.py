"""Time-sliced cost cube tests."""

from __future__ import annotations

import math

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


# ── Review finding M3: time-invariant layers must not be recomputed ───────────


def test_cost_cube_matches_a_per_slice_reference():
    """The optimised builder must agree with the naive one, bit for bit."""
    from app.costmap import PlanContext, default_cost_map

    grids = _base_grids()
    rover = get_rover()
    series = [np.full(SHAPE, r) for r in (0.0, 0.35, 0.8, 1.0)]

    cube = build_cost_cube(grids, series, rover)

    cost_map = default_cost_map(rover)
    for index, snapshot in enumerate(series):
        reference = cost_map.total(
            PlanContext(
                slope=np.asarray(grids["slope"], dtype=np.float64),
                thermal=np.asarray(grids["thermal"], dtype=np.float64),
                shadow_ratio=np.asarray(snapshot, dtype=np.float64),
                traversable=np.asarray(grids["traversable"], dtype=bool),
                resolution_m=80.0,
                rover=rover,
            )
        )
        assert np.allclose(cube[index], reference, equal_nan=True)


def test_cost_cube_matches_reference_with_coarsening_and_blocked_cells():
    from app.costmap import PlanContext, default_cost_map

    grids = _base_grids()
    traversable = np.ones(SHAPE, dtype=bool)
    traversable[0, 0] = False          # kills coarse block (0, 0)
    grids["traversable"] = traversable
    slope = np.asarray(grids["slope"], dtype=np.float64).copy()
    slope[4, 4] = 30.0                 # non-uniform: exercises how="max"
    grids["slope"] = slope

    rover = get_rover()
    series = [np.full(SHAPE, 0.2), np.full(SHAPE, 0.9)]
    cube = build_cost_cube(grids, series, rover, coarsen=2)

    from app.cost_cube import coarsen_grid, coarsen_traversable

    cost_map = default_cost_map(rover)
    for index, snapshot in enumerate(series):
        reference = cost_map.total(
            PlanContext(
                slope=coarsen_grid(slope, 2, how="max"),
                thermal=coarsen_grid(grids["thermal"], 2),
                shadow_ratio=coarsen_grid(np.asarray(snapshot, float), 2),
                traversable=coarsen_traversable(traversable, 2),
                resolution_m=160.0,
                rover=rover,
            )
        )
        assert np.allclose(cube[index], reference, equal_nan=True)
    assert np.isinf(cube[0, 0, 0])     # blocked block stays impassable


def test_cost_cube_does_not_rebuild_invariant_layers_per_slice():
    """Slope/energy/thermal do not vary with time; evaluating them once
    per slice is what made a 168-slice cube take ~22 s. (Faz 3 review, M3.)"""
    from app import cost_cube as module

    calls = {"n": 0}
    original = module.default_cost_map

    class _CountingMap:
        def __init__(self, inner):
            self._inner = inner
            self.layers = inner.layers

        def total(self, ctx):
            calls["n"] += 1
            return self._inner.total(ctx)

    module.default_cost_map = lambda *a, **k: _CountingMap(original(*a, **k))
    try:
        build_cost_cube(_base_grids(), [np.full(SHAPE, 0.3)] * 20, get_rover())
    finally:
        module.default_cost_map = original

    assert calls["n"] <= 1, f"cost_map.total() ran {calls['n']}x for 20 slices"


def test_wait_cost_cube_matches_scalar_wait_cost():
    """The vectorised/cached cube must agree with the scalar formula."""
    rover = get_rover()
    weights = resolve_weights(None, rover)
    series = [
        np.array([[0.0, 0.25], [0.5, 1.0]]),
        np.array([[1.0, 0.75], [0.1, 0.0]]),
    ]
    cube = build_wait_cost_cube(series, rover, dt_hours=1.5)
    for t, snapshot in enumerate(series):
        for r in range(2):
            for c in range(2):
                expected = wait_cost(snapshot[r, c], 1.5, rover, weights)
                assert cube[t, r, c] == pytest.approx(expected)


def test_wait_cost_cube_evaluates_each_distinct_value_once():
    """Cost scales with DISTINCT illumination values, not with cube size.

    A 168-slice cube used to evaluate wait_cost per cell per slice (~5 s);
    illumination grids repeat heavily, so solving each distinct value once
    makes the slice count almost free. (Faz 3 review, M3.)
    """
    import app.cost_cube as module

    calls = {"n": 0}
    original = module.wait_cost

    def counting(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    module.wait_cost = counting
    try:
        # 40 slices x 15625 cells, but only 3 distinct illumination values.
        grid = np.full((125, 125), 0.3)
        grid[:10] = 0.8
        grid[10:20] = 0.0
        module.build_wait_cost_cube([grid] * 40, get_rover(), dt_hours=1.0)
    finally:
        module.wait_cost = original

    assert calls["n"] == 3, f"wait_cost ran {calls['n']}x for 3 distinct values"


def test_cost_cube_honours_shadow_reading_layers_regardless_of_name():
    """A layer that reads shadow_ratio must stay time-varying even if it is
    not called "shadow". Keying the optimisation off the layer name froze
    such a layer at one value and produced a constant cube. (Faz 3 review, M3.)
    """
    import app.cost_cube as module
    from app.costmap import CostMap

    class _ShadowReadingLayer:
        name = "custom_illumination"
        validity = "MODEL"
        weight = 1.0

        def contribution(self, ctx):
            return np.asarray(ctx.shadow_ratio, dtype=np.float64)

    original = module.default_cost_map
    module.default_cost_map = lambda *a, **k: CostMap([_ShadowReadingLayer()])
    try:
        cube = module.build_cost_cube(
            _base_grids(), [np.zeros(SHAPE), np.ones(SHAPE)], get_rover()
        )
    finally:
        module.default_cost_map = original

    assert cube[1, 0, 0] > cube[0, 0, 0], "cube must vary with shadow"
    assert cube[1, 0, 0] == pytest.approx(1.0)



# ── Review finding C1: the time axis must advance in real hours ───────────────


def test_auto_slice_hours_matches_a_typical_edge_traversal():
    """A slice should be about as long as crossing one cell takes.

    With slice_hours=1.0 every move on any realistic grid rounded up to
    exactly one slice, so arrival_slice counted STEPS, not hours, and the
    slope-dependent travel time was invisible. (Faz 3 review, C1.)
    """
    from app.cost_cube import auto_slice_hours

    rover = get_rover()
    slope = np.full((8, 8), 19.0)
    traversable = np.ones((8, 8), dtype=bool)

    hours = auto_slice_hours(slope, traversable, resolution_m=20.0, rover=rover)

    from app.cost_engine import edge_travel_time_s

    expected = edge_travel_time_s(19.0, 20.0, rover) / 3600.0
    assert hours == pytest.approx(expected, rel=0.1)


def test_auto_slice_hours_scales_with_cell_size():
    from app.cost_cube import auto_slice_hours

    rover = get_rover()
    slope = np.full((8, 8), 10.0)
    traversable = np.ones((8, 8), dtype=bool)

    small = auto_slice_hours(slope, traversable, resolution_m=20.0, rover=rover)
    large = auto_slice_hours(slope, traversable, resolution_m=80.0, rover=rover)
    assert large == pytest.approx(small * 4, rel=0.05)


def test_auto_slice_hours_ignores_impassable_cells():
    """Blocked cells often carry extreme slopes; they must not set the clock."""
    from app.cost_cube import auto_slice_hours

    rover = get_rover()
    slope = np.full((8, 8), 10.0)
    slope[0, :] = 89.0                       # near-vertical, and blocked
    traversable = np.ones((8, 8), dtype=bool)
    traversable[0, :] = False

    hours = auto_slice_hours(slope, traversable, resolution_m=20.0, rover=rover)
    reference = auto_slice_hours(
        np.full((8, 8), 10.0), np.ones((8, 8), dtype=bool), 20.0, rover
    )
    assert hours == pytest.approx(reference)


def test_auto_slice_hours_is_positive_when_nothing_is_traversable():
    from app.cost_cube import auto_slice_hours

    rover = get_rover()
    hours = auto_slice_hours(
        np.full((4, 4), 10.0), np.zeros((4, 4), dtype=bool), 20.0, rover
    )
    assert hours > 0.0
    assert math.isfinite(hours)
