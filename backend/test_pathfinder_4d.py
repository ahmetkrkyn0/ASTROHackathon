"""4-D (row, col, time) A* tests."""

from __future__ import annotations

import numpy as np
import pytest

from app.constants import get_rover
from app.pathfinder_4d import astar_4d

RES_M = 80.0
SLICE_H = 1.0


def _uniform_case(n_slices=6, shape=(1, 4), cost=0.01, wait=0.01):
    cost_cube = np.full((n_slices, *shape), cost, dtype=np.float64)
    wait_cube = np.full((n_slices, *shape), wait, dtype=np.float64)
    traversable = np.ones(shape, dtype=bool)
    return cost_cube, wait_cube, traversable


def _run(cost_cube, wait_cube, traversable, start=(0, 0), goal=(0, 3)):
    return astar_4d(
        cost_cube,
        wait_cube,
        traversable,
        start=start,
        goal=goal,
        resolution_m=RES_M,
        slice_hours=SLICE_H,
        rover=get_rover(),
    )


def test_finds_a_direct_path_on_a_uniform_cube():
    result = _run(*_uniform_case())
    assert result["error"] is None
    assert result["path_pixels"][0] == (0, 0)
    assert result["path_pixels"][-1] == (0, 3)
    assert result["metrics"]["wait_steps"] == 0


def test_path_states_carry_monotonically_increasing_time():
    result = _run(*_uniform_case())
    times = [t for _, _, t in result["path_states"]]
    assert times == sorted(times)
    assert times[0] == 0


def test_blocked_goal_returns_an_error():
    cost_cube, wait_cube, traversable = _uniform_case()
    traversable[0, 3] = False
    result = _run(cost_cube, wait_cube, traversable)
    assert result["error"] is not None
    assert result["path_pixels"] == []


def test_out_of_bounds_start_returns_an_error():
    result = _run(*_uniform_case(), start=(0, 9))
    assert result["error"] is not None


def test_exhausted_time_horizon_returns_an_error():
    """Two slices cannot cover a three-move path."""
    result = _run(*_uniform_case(n_slices=2))
    assert result["error"] is not None


def test_metrics_report_expansion_and_timing():
    result = _run(*_uniform_case())
    assert result["metrics"]["nodes_expanded"] > 0
    assert result["metrics"]["computation_time_ms"] >= 0.0
    assert result["metrics"]["move_steps"] == 3
    assert result["metrics"]["arrival_slice"] >= 3


def _shadow_then_sun_case():
    """A 1x4 corridor whose middle is expensive until slice 3.

    Sitting still at the start is nearly free (lit, charging), so the
    cheapest plan is: wait for the Sun, then cross.
    """
    n_slices, shape = 8, (1, 4)
    cost_cube = np.full((n_slices, *shape), 0.01, dtype=np.float64)
    cost_cube[:3, 0, 1] = 40.0
    cost_cube[:3, 0, 2] = 40.0
    wait_cube = np.full((n_slices, *shape), 0.001, dtype=np.float64)
    traversable = np.ones(shape, dtype=bool)
    return cost_cube, wait_cube, traversable


def test_planner_chooses_to_wait_for_the_sun():
    result = _run(*_shadow_then_sun_case())
    assert result["error"] is None
    assert result["metrics"]["wait_steps"] > 0, "planner should hold for the Sun"
    assert result["path_pixels"][-1] == (0, 3)


def test_waiting_plan_is_cheaper_than_crossing_immediately():
    """Sanity: the wait is an optimisation, not an artefact."""
    cost_cube, wait_cube, traversable = _shadow_then_sun_case()
    waited = _run(cost_cube, wait_cube, traversable)

    # Same cube, but waiting is made prohibitively expensive.
    expensive_wait = np.full_like(wait_cube, 1e6)
    rushed = _run(cost_cube, expensive_wait, traversable)

    assert waited["metrics"]["wait_steps"] > 0
    assert rushed["metrics"]["wait_steps"] == 0
    assert waited["metrics"]["total_cost"] < rushed["metrics"]["total_cost"]


def test_planner_does_not_wait_when_there_is_nothing_to_gain():
    """A uniformly cheap cube must produce a straight, wait-free plan."""
    result = _run(*_uniform_case(n_slices=8))
    assert result["metrics"]["wait_steps"] == 0


# ── Review findings: JSON safety and degenerate start/goal ────────────────────


def test_error_result_is_strict_json_serialisable():
    """``inf`` is not valid JSON; a caller that serialises an error result
    directly must not get a 500. Same root cause as the Faz 2 C1 finding."""
    import json

    cost_cube, wait_cube, traversable = _uniform_case()
    traversable[0, 3] = False
    result = _run(cost_cube, wait_cube, traversable)

    assert result["error"] is not None
    json.dumps(result, allow_nan=False)


def test_error_result_reports_total_cost_as_none():
    cost_cube, wait_cube, traversable = _uniform_case()
    traversable[0, 3] = False
    result = _run(cost_cube, wait_cube, traversable)
    assert result["metrics"]["total_cost"] is None


def test_successful_result_is_strict_json_serialisable():
    import json

    result = _run(*_uniform_case())
    assert result["error"] is None
    json.dumps(result, allow_nan=False)


# ── bfs_move_count: exact reachability for horizon sizing and diagnosis ───────


def test_bfs_move_count_on_open_grid_is_chebyshev_distance():
    from app.pathfinder_4d import bfs_move_count

    mask = np.ones((10, 10), dtype=bool)
    assert bfs_move_count(mask, (0, 0), (3, 5)) == 5  # diagonal covers 3, 2 more east


def test_bfs_move_count_is_zero_for_identical_start_and_goal():
    from app.pathfinder_4d import bfs_move_count

    mask = np.ones((4, 4), dtype=bool)
    assert bfs_move_count(mask, (2, 2), (2, 2)) == 0


def test_bfs_move_count_is_none_when_start_is_blocked():
    from app.pathfinder_4d import bfs_move_count

    mask = np.ones((4, 4), dtype=bool)
    mask[0, 0] = False
    assert bfs_move_count(mask, (0, 0), (3, 3)) is None


def test_bfs_move_count_is_none_when_goal_is_blocked():
    from app.pathfinder_4d import bfs_move_count

    mask = np.ones((4, 4), dtype=bool)
    mask[3, 3] = False
    assert bfs_move_count(mask, (0, 0), (3, 3)) is None


def test_bfs_move_count_is_none_when_out_of_bounds():
    from app.pathfinder_4d import bfs_move_count

    mask = np.ones((4, 4), dtype=bool)
    assert bfs_move_count(mask, (0, 0), (9, 9)) is None


def test_bfs_move_count_is_none_across_a_disconnecting_wall():
    from app.pathfinder_4d import bfs_move_count

    mask = np.ones((5, 5), dtype=bool)
    mask[2, :] = False  # a full-width wall with no gap
    assert bfs_move_count(mask, (0, 0), (4, 4)) is None


def test_bfs_move_count_routes_around_a_wall_with_a_gap():
    from app.pathfinder_4d import bfs_move_count

    mask = np.ones((5, 5), dtype=bool)
    mask[2, :] = False
    mask[2, 4] = True  # single gap at the east edge
    distance = bfs_move_count(mask, (0, 0), (4, 0))
    assert distance is not None
    assert distance > 4  # longer than the straight Chebyshev distance of 4


# ── MOVE/WAIT unit parity with the real cube builders (Faz 1-2-3 review, M2) ──
#
# The scenarios above hand-pick cost_cube/wait_cube values (40.0 vs 0.001)
# that prove the WAIT *mechanism* works, but not that it is *calibrated*: on
# the real grid, build_cost_cube's MOVE edges and build_wait_cost_cube's WAIT
# edges came out ~6500x apart in magnitude (MOVE in distance_m * MRU, WAIT in
# dt_hours * MRU), so a real illumination cube could never make waiting
# competitive. These tests build both cubes through the actual production
# functions -- not hand-set numbers -- so a regression that reintroduces the
# unit mismatch fails here even though the mechanism-only tests above
# wouldn't catch it.


def _real_cubes_shadowed_corridor(
    shadow_len: int, n_shadow_slices: int, corridor_len: int
):
    """A corridor whose first *shadow_len* cells are shadowed for the first
    *n_shadow_slices* slices, then lit for the rest of the horizon. Built
    entirely through app.cost_cube's real functions and the default rover,
    not through hand-picked cost values."""
    from app.cost_cube import auto_slice_hours, build_cost_cube, build_wait_cost_cube

    shape = (1, corridor_len)
    rover = get_rover()
    slope = np.full(shape, 3.0)
    thermal = np.full(shape, -60.0)
    traversable = np.ones(shape, dtype=bool)
    base_grids = {
        "slope": slope,
        "thermal": thermal,
        "traversable": traversable,
        "metadata": {"resolution_m": 80.0, "shape": list(shape)},
    }
    n_slices = n_shadow_slices + corridor_len + 2
    shadow_series, illum_series = [], []
    for t in range(n_slices):
        shadow = np.zeros(shape)
        if t < n_shadow_slices:
            shadow[0, 1 : 1 + shadow_len] = 1.0
        shadow_series.append(shadow)
        illum_series.append(1.0 - shadow)

    slice_hours = auto_slice_hours(slope, traversable, 80.0, rover)
    cost_cube = build_cost_cube(base_grids, shadow_series, rover, coarsen=1)
    wait_cube = build_wait_cost_cube(illum_series, rover, slice_hours, coarsen=1)
    return cost_cube, wait_cube, traversable, slope, slice_hours, corridor_len


def test_planner_chooses_to_wait_with_real_cost_cubes():
    """A long-enough shadowed stretch makes waiting for real sunlight (real
    build_cost_cube/build_wait_cost_cube numbers, real rover constants) the
    cheaper choice -- not just in a hand-tuned toy cube."""
    cost_cube, wait_cube, traversable, slope, slice_hours, corridor_len = (
        _real_cubes_shadowed_corridor(shadow_len=10, n_shadow_slices=3, corridor_len=12)
    )
    result = astar_4d(
        cost_cube,
        wait_cube,
        traversable,
        start=(0, 0),
        goal=(0, corridor_len - 1),
        resolution_m=80.0,
        slice_hours=slice_hours,
        rover=get_rover(),
        slope_grid=slope,
    )
    assert result["error"] is None
    assert result["metrics"]["wait_steps"] > 0


def test_real_cube_wait_is_cheaper_than_rushing():
    """Sanity mirror of test_waiting_plan_is_cheaper_than_crossing_immediately,
    but against the real cube builders instead of hand-picked values."""
    cost_cube, wait_cube, traversable, slope, slice_hours, corridor_len = (
        _real_cubes_shadowed_corridor(shadow_len=10, n_shadow_slices=3, corridor_len=12)
    )
    rover = get_rover()
    kwargs = dict(
        traversable=traversable,
        start=(0, 0),
        goal=(0, corridor_len - 1),
        resolution_m=80.0,
        slice_hours=slice_hours,
        rover=rover,
        slope_grid=slope,
    )
    waited = astar_4d(cost_cube, wait_cube, **kwargs)
    rushed = astar_4d(cost_cube, np.full_like(wait_cube, 1e6), **kwargs)

    assert waited["metrics"]["wait_steps"] > 0
    assert rushed["metrics"]["wait_steps"] == 0
    assert waited["metrics"]["total_cost"] < rushed["metrics"]["total_cost"]
