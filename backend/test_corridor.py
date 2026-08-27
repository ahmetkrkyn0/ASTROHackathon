"""Corridor contract tests."""

from __future__ import annotations

import numpy as np
import pytest

from app.constants import get_rover
from app.corridor import build_corridor, clearance_map
from app.schemas import Corridor

SHAPE = (20, 20)
RES_M = 80.0


def _grids(blocked: tuple[tuple[int, int], ...] = ()) -> dict:
    traversable = np.ones(SHAPE, dtype=bool)
    for r, c in blocked:
        traversable[r, c] = False
    return {
        "slope": np.full(SHAPE, 5.0),
        "thermal": np.full(SHAPE, -60.0),
        "shadow_ratio": np.full(SHAPE, 0.1),
        "traversable": traversable,
        "metadata": {
            "origin": {"x": 156000.0, "y": 28000.0},
            "resolution_m": RES_M,
            "shape": list(SHAPE),
        },
    }


def test_clearance_map_is_zero_on_blocked_cells():
    traversable = np.ones(SHAPE, dtype=bool)
    traversable[10, 10] = False
    clearance = clearance_map(traversable, RES_M)
    assert clearance[10, 10] == pytest.approx(0.0)
    assert clearance[10, 11] == pytest.approx(RES_M)


def test_clearance_map_scales_with_resolution():
    traversable = np.ones((5, 5), dtype=bool)
    traversable[2, 2] = False
    assert clearance_map(traversable, 10.0)[2, 3] == pytest.approx(10.0)
    assert clearance_map(traversable, 40.0)[2, 3] == pytest.approx(40.0)


def test_build_corridor_returns_one_waypoint_per_path_pixel():
    path = [(2, 2), (3, 3), (4, 4), (5, 5)]
    corridor = build_corridor(path, _grids(), get_rover())
    assert isinstance(corridor, Corridor)
    assert len(corridor.waypoints) == len(path)


def test_segment_arrays_have_one_entry_per_segment():
    path = [(2, 2), (3, 3), (4, 4), (5, 5)]
    corridor = build_corridor(path, _grids(), get_rover())
    n_segments = len(path) - 1
    assert len(corridor.half_width_m) == n_segments
    assert len(corridor.max_slope_deg) == n_segments
    assert len(corridor.energy_budget_wh) == n_segments
    assert len(corridor.thermal_budget_K_s) == n_segments


def test_waypoints_are_projected_metres_not_pixels():
    path = [(0, 0), (0, 1)]
    corridor = build_corridor(path, _grids(), get_rover())
    x0, y0 = corridor.waypoints[0]
    x1, y1 = corridor.waypoints[1]
    assert x0 == pytest.approx(156000.0)
    assert y0 == pytest.approx(28000.0)
    assert x1 - x0 == pytest.approx(RES_M)


def test_half_width_is_capped():
    path = [(5, 5), (6, 6), (7, 7)]
    corridor = build_corridor(path, _grids(), get_rover(), max_half_width_m=120.0)
    assert max(corridor.half_width_m) <= 120.0


def test_half_width_shrinks_near_obstacles():
    path = [(5, 5), (6, 6), (7, 7)]
    open_corridor = build_corridor(path, _grids(), get_rover())
    tight_corridor = build_corridor(
        path, _grids(blocked=((6, 7), (7, 8), (5, 6))), get_rover()
    )
    assert min(tight_corridor.half_width_m) < min(open_corridor.half_width_m)


def test_energy_budget_is_positive_and_finite():
    path = [(2, 2), (3, 3), (4, 4)]
    corridor = build_corridor(path, _grids(), get_rover())
    assert all(0.0 < e < float("inf") for e in corridor.energy_budget_wh)


def test_fallback_points_exist_for_every_waypoint():
    path = [(2, 2), (3, 3), (4, 4)]
    corridor = build_corridor(path, _grids(), get_rover())
    assert len(corridor.fallback_points) == len(path)


def test_short_path_of_one_pixel_is_rejected():
    with pytest.raises(ValueError):
        build_corridor([(1, 1)], _grids(), get_rover())


# ── Faz 2 review fix: C2 -- row axis must point south (1.23 km error) ──


def test_waypoint_row_axis_points_south():
    """origin_y is the raster's TOP edge; increasing row must DECREASE y.

    Regression guard for the 1.23 km corridor placement error: the original
    test only checked the column axis, so an inverted row axis passed.
    """
    path = [(0, 0), (1, 0)]
    corridor = build_corridor(path, _grids(), get_rover())
    _, y0 = corridor.waypoints[0]
    _, y1 = corridor.waypoints[1]
    assert y0 == pytest.approx(28000.0)
    assert y1 - y0 == pytest.approx(-RES_M)


def test_waypoint_row_axis_matches_pipeline_convention():
    """corridor must agree with process_lunar_data.window_center_latlon."""
    path = [(0, 0), (10, 0)]
    corridor = build_corridor(path, _grids(), get_rover())
    _, y_at_row_10 = corridor.waypoints[1]
    assert y_at_row_10 == pytest.approx(28000.0 - 10 * RES_M)


def test_fallback_points_use_the_same_row_convention():
    path = [(0, 0), (1, 1), (2, 2)]
    corridor = build_corridor(path, _grids(), get_rover())
    for (_, y) in corridor.fallback_points:
        assert y <= 28000.0  # never north of the top edge


# ── Faz 2 review fix: M1 -- Corridor must stay strict-JSON serialisable ──


def test_energy_budget_stays_finite_on_absurd_slopes():
    """edge_energy_wh returns inf at >=90 deg; that must not reach the JSON."""
    grids = _grids()
    grids["slope"] = np.full(SHAPE, 95.0)
    corridor = build_corridor([(1, 1), (2, 2)], grids, get_rover())
    assert all(np.isfinite(e) for e in corridor.energy_budget_wh)


def test_corridor_is_strict_json_serialisable():
    import json

    grids = _grids()
    grids["slope"] = np.full(SHAPE, 95.0)
    corridor = build_corridor([(1, 1), (2, 2)], grids, get_rover())
    json.dumps(corridor.model_dump(), allow_nan=False)
