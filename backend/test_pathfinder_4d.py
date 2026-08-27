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
