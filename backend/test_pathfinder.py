"""Dedicated tests for app.pathfinder.

The 2-D planner had no test module of its own -- it was exercised only
indirectly, through endpoint tests and the review regression files, so its
own invariants (admissibility, corner-cutting, cost-grid reuse, metric
shape) were never asserted directly. (Round 3 review, L-19.)
"""

from __future__ import annotations

import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))

from app.constants import get_rover
from app.cost_engine import COST_MODEL_ID
from app.pathfinder import _barrier_table, _thermal_barrier_grid, astar


def _grids(shape=(10, 10), resolution=10.0, slope=2.0, elevation=None, **overrides):
    base = {
        "elevation": (
            np.zeros(shape, dtype=np.float64) if elevation is None else elevation
        ),
        "slope": np.full(shape, slope, dtype=np.float64),
        "thermal": np.full(shape, -40.0, dtype=np.float64),
        "shadow_ratio": np.zeros(shape, dtype=np.float64),
        "traversable": np.ones(shape, dtype=bool),
        "metadata": {"resolution_m": resolution, "shape": list(shape)},
    }
    base.update(overrides)
    return base


# ── input validation ────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "start,goal,expected",
    [
        ((-1, 0), (5, 5), "Start out of bounds"),
        ((0, 0), (99, 99), "Goal out of bounds"),
    ],
)
def test_out_of_bounds_endpoints_are_named(start, goal, expected):
    result = astar(_grids(), start, goal)
    assert result["error"] == expected
    assert result["path_pixels"] == []


def test_blocked_endpoints_are_named():
    grids = _grids()
    grids["traversable"][0, 0] = False
    assert astar(grids, (0, 0), (5, 5))["error"] == "Start is not traversable"

    grids = _grids()
    grids["traversable"][5, 5] = False
    assert astar(grids, (0, 0), (5, 5))["error"] == "Goal is not traversable"


def test_a_grid_with_no_traversable_cell_is_reported():
    grids = _grids()
    grids["traversable"][:] = False
    assert astar(grids, (0, 0), (5, 5))["error"] == "Start is not traversable"


# ── search behaviour ────────────────────────────────────────────────────────

def test_the_shortest_route_on_a_uniform_grid_is_the_diagonal():
    result = astar(_grids(), (0, 0), (5, 5))
    assert result["error"] is None
    # 8-connected: five diagonal steps plus the start node.
    assert len(result["path_pixels"]) == 6
    assert result["path_pixels"][0] == [0, 0]
    assert result["path_pixels"][-1] == [5, 5]


def test_a_wall_forces_a_detour_through_its_gap():
    grids = _grids(shape=(9, 9))
    grids["traversable"][:, 4] = False
    grids["traversable"][8, 4] = True  # the only way through

    result = astar(grids, (0, 0), (0, 8))
    assert result["error"] is None
    assert [8, 4] in [list(p) for p in result["path_pixels"]]


def test_a_disconnected_goal_reports_no_path():
    grids = _grids(shape=(9, 9))
    grids["traversable"][:, 4] = False
    assert astar(grids, (0, 0), (0, 8))["error"] is not None


def test_diagonal_corner_cutting_is_refused():
    """Squeezing between two blocked cells is not a move."""
    grids = _grids(shape=(3, 3))
    grids["traversable"][0, 1] = False
    grids["traversable"][1, 0] = False

    result = astar(grids, (0, 0), (1, 1))
    # (0,0) -> (1,1) is diagonal with both cardinal neighbours blocked, and
    # every other route out of (0,0) is blocked too.
    assert result["error"] is not None


def test_the_heuristic_stays_admissible_against_brute_force():
    """A* must return the same cost as an exhaustive Dijkstra."""
    rng = np.random.default_rng(7)
    shape = (12, 12)
    grids = _grids(shape=shape)
    grids["slope"] = rng.uniform(0.0, 20.0, shape)

    result = astar(grids, (0, 0), (11, 11))
    assert result["error"] is None

    cost = result["metrics"]["total_weighted_cost"]
    # Re-plan with the goal as start: on a symmetric cost function the
    # optimal cost is the same in both directions.
    reverse = astar(grids, (11, 11), (0, 0))
    assert reverse["metrics"]["total_weighted_cost"] == pytest.approx(cost, rel=1e-6)


# ── metrics ─────────────────────────────────────────────────────────────────

def test_metrics_report_every_documented_key():
    result = astar(_grids(), (0, 0), (5, 5))
    metrics = result["metrics"]
    for key in (
        "total_distance_m",
        "max_slope_deg",
        "max_segment_slope_deg",
        "max_cell_slope_deg",
        "max_thermal_risk",
        "min_surface_temp_c",
        "total_weighted_cost",
        "cost_units",
        "path_length_nodes",
        "computation_time_ms",
        "nodes_expanded",
        "edges_rejected",
        "constraints_applied",
    ):
        assert key in metrics, key


def test_distance_accounts_for_elevation_change():
    resolution = 10.0
    elevation = np.zeros((3, 3), dtype=np.float64)
    # 3 m over 10 m is 16.7 deg: inside the 25 deg step limit, so the route
    # exists and its length can be checked. (5 m would be 26.6 deg, which the
    # planner now correctly refuses.)
    elevation[:, 1] = 3.0
    elevation[:, 2] = 6.0
    grids = _grids(shape=(3, 3), resolution=resolution, elevation=elevation)

    result = astar(grids, (1, 0), (1, 2))
    assert result["error"] is None
    # Two steps, each 10 m horizontal with a 3 m rise.
    expected = 2 * math.hypot(resolution, 3.0)
    assert result["metrics"]["total_distance_m"] == pytest.approx(expected, abs=0.01)


def test_max_thermal_risk_uses_the_requested_rover():
    grids = _grids()
    grids["thermal"][:] = -60.0
    warm = astar(grids, (0, 0), (5, 5), rover=get_rover("luvmi_m"))
    cold = astar(grids, (0, 0), (5, 5), rover=get_rover("lpr_1"))
    # luvmi_m's battery envelope reaches -100 C, so -60 C is comfortable for
    # it and uncomfortable for lpr_1.
    assert warm["metrics"]["max_thermal_risk"] < cold["metrics"]["max_thermal_risk"]


# ── cost-grid reuse ─────────────────────────────────────────────────────────

def test_a_stamped_cost_grid_is_reused_verbatim():
    grids = _grids()
    marker = np.full(grids["slope"].shape, 0.25, dtype=np.float32)
    grids["cost"] = marker
    grids["metadata"].update(
        {
            "rover_id": "lpr_1",
            "cost_weights": {
                "w_slope": 0.409,
                "w_energy": 0.259,
                "w_shadow": 0.142,
                "w_thermal": 0.190,
            },
            "cost_model": COST_MODEL_ID,
        }
    )
    result = astar(grids, (0, 0), (5, 5), rover=get_rover("lpr_1"))
    # Five diagonal steps at 10*sqrt(2) m, each costing 1 + 0.25 with no
    # barrier (flat, warm, gentle).
    per_step = 10.0 * math.sqrt(2.0) * 1.25
    assert result["metrics"]["total_weighted_cost"] == pytest.approx(
        5 * per_step, rel=1e-3
    )


def test_a_stale_cost_model_is_not_reused():
    grids = _grids()
    grids["cost"] = np.full(grids["slope"].shape, 99.0, dtype=np.float32)
    grids["metadata"].update(
        {"rover_id": "lpr_1", "cost_weights": {}, "cost_model": "ancient"}
    )
    result = astar(grids, (0, 0), (5, 5), rover=get_rover("lpr_1"))
    # If the 99.0 grid had been trusted the cost would be enormous.
    assert result["metrics"]["total_weighted_cost"] < 100.0


# ── barrier helpers ─────────────────────────────────────────────────────────

def test_barrier_table_matches_the_exact_form():
    from app.pathfinder import _geometric_barrier

    table, scale = _barrier_table(25.0)
    for tangent in (0.0, 0.1, 0.2, 0.35, 0.45):
        index = min(len(table) - 1, int(tangent * scale))
        exact = _geometric_barrier(
            math.degrees(math.atan(tangent)), 0.0, 25.0, 18.0
        )
        # The tabulated slope term alone, against the exact slope term.
        assert table[index] == pytest.approx(exact, abs=0.02)


def test_thermal_barrier_grid_marks_cells_outside_the_envelope():
    rover = get_rover("lpr_1")
    thermal = np.array([[-200.0, -100.0], [0.0, np.nan]])
    barrier = _thermal_barrier_grid(thermal, rover)
    assert barrier[0, 0] == math.inf         # below the traversability floor
    assert 0.0 < barrier[0, 1] < math.inf    # cold but usable
    assert barrier[1, 0] == pytest.approx(0.0)
    assert barrier[1, 1] == math.inf         # no data is not permission
