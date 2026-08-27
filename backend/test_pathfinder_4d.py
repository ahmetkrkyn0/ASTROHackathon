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
