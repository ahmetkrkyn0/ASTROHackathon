"""Regression tests for the round-2 independent review findings.

One test (or group) per finding, named for it. Each asserts the
behaviour the finding said was wrong, so a regression re-breaks the
specific thing rather than something adjacent.

Companion to test_review_fixes.py, which covers round 1.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.constants import get_rover
from app.main import PoseRequest, ReplanRequest, app
from app.replan_triggers import evaluate_triggers_detailed

_NAN = float("nan")


# ── H-1: NaN telemetry must not fail every trigger open ────────────────────


def test_h1_nan_telemetry_is_skipped_not_reported_as_checked():
    """Every comparison against NaN is False, so a NaN value used to make
    its trigger report "checked and clear" -- review #4's fail-open, via
    the value instead of the key."""
    result = evaluate_triggers_detailed(
        {
            "actual_soc": _NAN,
            "planned_soc": 0.8,
            "lateral_offset_m": _NAN,
            "half_width_m": 10.0,
            "localization_covariance_m": _NAN,
        }
    )
    assert result["fired"] == []
    assert result["evaluated"] == []
    skipped_ids = {entry["trigger_id"] for entry in result["skipped"]}
    assert {"soc_deviation", "corridor_violation", "localization_uncertainty"} <= (
        skipped_ids
    )


def _skip_entry(result, trigger_id):
    """The skipped list also holds triggers whose keys are absent, so a
    test must select its trigger rather than index position 0."""
    return next(
        entry for entry in result["skipped"] if entry["trigger_id"] == trigger_id
    )


def test_h1_infinite_telemetry_is_also_skipped():
    result = evaluate_triggers_detailed({"drift_minutes": float("inf")})
    assert result["evaluated"] == []
    assert "reason" in _skip_entry(result, "time_drift")


def test_h1_a_non_finite_value_does_not_suppress_its_healthy_neighbours():
    """Only the trigger whose input is broken is skipped; the rest still
    run. A blanket bail-out would be its own fail-open."""
    result = evaluate_triggers_detailed(
        {
            "actual_soc": 0.3,
            "planned_soc": 0.8,
            "lateral_offset_m": _NAN,
            "half_width_m": 10.0,
        }
    )
    assert [t.trigger_id for t in result["fired"]] == ["soc_deviation"]
    assert result["evaluated"] == ["soc_deviation"]
    assert "corridor_violation" in {e["trigger_id"] for e in result["skipped"]}


def test_h1_finite_telemetry_still_evaluates_normally():
    result = evaluate_triggers_detailed(
        {"lateral_offset_m": 50.0, "half_width_m": 10.0}
    )
    assert [t.trigger_id for t in result["fired"]] == ["corridor_violation"]


def test_h1_skipped_entries_explain_why():
    result = evaluate_triggers_detailed({"drift_minutes": _NAN})
    assert "non-finite" in _skip_entry(result, "time_drift")["reason"]


@pytest.mark.parametrize("model", [ReplanRequest, PoseRequest])
def test_h1_request_models_reject_non_finite_telemetry(model):
    """The boundary refuses it outright, so the caller is told rather
    than having to read a skipped list to find out."""
    payload = {"state": {"actual_soc": _NAN}}
    if model is ReplanRequest:
        payload |= {"current": {"row": 0, "col": 0}, "goal": {"row": 1, "col": 1}}
    else:
        payload |= {
            "pose": {
                "x_m": 0.0,
                "y_m": 0.0,
                "heading_deg": 0.0,
                "covariance_m": 1.0,
                "heading_covariance_deg": 1.0,
                "timestamp_utc": "2026-08-30T12:00:00Z",
                "source": "visual_odometry",
                "distance_travelled_m": 0.0,
            }
        }
    with pytest.raises(ValidationError):
        model(**payload)


def test_h1_a_bare_nan_literal_is_what_a_plain_client_sends():
    """Not a contrived input: json.dumps emits a bare NaN and json.loads
    accepts it, so this reaches the endpoint from ordinary client code."""
    assert json.dumps({"x": _NAN}) == '{"x": NaN}'
    assert math.isnan(json.loads('{"x": NaN}')["x"])


# ── H-2: /api/compare must not rank on a hardcoded-zero metric ─────────────


def test_h2_comparison_does_not_claim_an_energy_winner_from_a_zero_metric():
    from app.scenarios import compare_results

    def result(profile_id, cost):
        return {
            "profile_id": profile_id,
            "error": None,
            "metrics": {
                "total_energy_wh": 0.0,  # hardcoded by _compute_path_metrics
                "total_shadow_hours": 0.0,
                "total_weighted_cost": cost,
                "max_thermal_risk": 0.1,
                "max_slope_deg": 5.0,
                "total_distance_m": 100.0,
            },
        }

    forward = compare_results([result("balanced", 5.0), result("shadow", 4.0)])
    reversed_ = compare_results([result("shadow", 4.0), result("balanced", 5.0)])

    # The ranking must not depend on list order...
    assert (
        forward["most_efficient_profile"] == reversed_["most_efficient_profile"]
    )
    # ...and must not assert an energy fact the metric cannot support.
    assert "least energy" not in forward["recommendation"]


def test_h2_the_efficiency_ranking_uses_a_real_quantity():
    from app.scenarios import compare_results

    def result(profile_id, cost):
        return {
            "profile_id": profile_id,
            "error": None,
            "metrics": {
                "total_energy_wh": 0.0,
                "total_shadow_hours": 0.0,
                "total_weighted_cost": cost,
                "max_thermal_risk": 0.1,
                "max_slope_deg": 5.0,
                "total_distance_m": 100.0,
            },
        }

    comparison = compare_results(
        [result("expensive", 9.0), result("cheap", 2.0)]
    )
    assert comparison["most_efficient_profile"] == "cheap"


# ── H-3: Diviner reprojection window must sit on the model grid ───────────


def _diviner_module():
    """Import scripts/diviner_validation.py by path.

    It lives outside the backend package (it is an operator script, not
    an app module), so it is loaded directly rather than imported.
    """
    import importlib.util
    from pathlib import Path

    path = (
        Path(__file__).resolve().parent.parent / "scripts" / "diviner_validation.py"
    )
    spec = importlib.util.spec_from_file_location("diviner_validation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_h3_diviner_destination_transform_uses_origin_y_as_the_top_edge():
    """metadata.origin.y IS the top edge (pixel_to_map_xy(0,0) -> origin.y).
    Adding rows*resolution displaced the sampling window one full window
    height north, silently validating against the wrong terrain."""
    import rasterio

    destination_transform = _diviner_module().destination_transform

    metadata = {
        "origin": {"x": 0.0, "y": 1000.0},
        "resolution_m": 10.0,
        "shape": [100, 100],
        "crs": "test",
    }
    transform = destination_transform(metadata)
    assert isinstance(transform, rasterio.Affine)
    # from_origin(west, north): f is the northern (top) edge.
    # origin.y is row 0's CENTRE (grid_frame), so the raster edge sits
    # half a cell north of it -- not a full window height (the H-3 bug).
    assert transform.f == pytest.approx(1000.0 + 10.0 / 2.0)


def test_h3_transform_matches_grid_frame_for_every_row():
    """The destination grid and grid_frame must agree about where each
    row sits, or the comparison is misaligned by construction."""
    from app.grid_frame import pixel_to_map_xy

    destination_transform = _diviner_module().destination_transform

    metadata = {
        "origin": {"x": 500.0, "y": 2000.0},
        "resolution_m": 5.0,
        "shape": [40, 40],
        "crs": "test",
    }
    transform = destination_transform(metadata)
    for row in (0, 17, 39):
        # Cell centre of the destination raster for that row.
        _, y_centre = transform * (0.5, row + 0.5)
        _, y_expected = pixel_to_map_xy(row, 0, metadata)
        assert y_centre == pytest.approx(y_expected)


# ── M-2: thermal risk must use the requested rover ────────────────────────


def _plan_grids(shape=(20, 20)):
    rover = get_rover()
    return {
        "elevation": np.zeros(shape),
        "slope": np.full(shape, 3.0),
        "aspect": np.zeros(shape),
        "thermal": np.full(shape, -60.0),
        "shadow_ratio": np.full(shape, 0.2),
        "traversable": np.ones(shape, dtype=bool),
        "cost": np.full(shape, 0.3),
        "metadata": {
            "origin": {"x": 156000.0, "y": 28000.0},
            "resolution_m": 80.0,
            "shape": list(shape),
            "crs": "test",
            "default_rover_id": rover["id"],
            "cost_weights": {
                "w_slope": 0.409,
                "w_energy": 0.259,
                "w_shadow": 0.142,
                "w_thermal": 0.19,
            },
        },
    }


def test_m2_thermal_risk_reflects_the_requested_rovers_envelope():
    """-60 C is comfortable for luvmi_m (envelope -100..0) and risky for
    lpr_1. The metric used to report lpr_1's number for both."""
    from app.cost_engine import f_thermal
    from app.pathfinder import astar

    grids = _plan_grids()
    luvmi = get_rover("luvmi_m")

    plan = astar(grids, (2, 2), (15, 15), rover=luvmi)
    assert plan["error"] is None
    assert plan["metrics"]["max_thermal_risk"] == pytest.approx(
        f_thermal(-60.0, rover=luvmi), abs=1e-4
    )


def test_m2_the_default_rover_is_unchanged():
    from app.cost_engine import f_thermal
    from app.pathfinder import astar

    grids = _plan_grids()
    plan = astar(grids, (2, 2), (15, 15), rover=get_rover("lpr_1"))
    assert plan["metrics"]["max_thermal_risk"] == pytest.approx(
        f_thermal(-60.0, rover=get_rover("lpr_1")), abs=1e-4
    )


# ── M-7: min_battery_pct must show the dip, not the recharge ──────────────


def test_m7_min_battery_pct_records_the_depleted_value():
    """The recharge ran before the state was recorded, so a route that
    flattened the battery seven times reported a 100% minimum."""
    from app.simulation import simulate_path, summarize_simulation

    rover = dict(get_rover("lpr_1"))
    rover["e_cap_wh"] = 30.0  # small enough that every step depletes it

    shape = (1, 8)
    plan = {
        "path_pixels": [(0, i) for i in range(8)],
        "error": None,
        "metrics": {},
    }
    states = simulate_path(
        plan,
        np.full(shape, 0.3),
        np.full(shape, 3.0),
        np.full(shape, -60.0),
        np.zeros(shape),
        rover=rover,
        pixel_size_m=80.0,
    )
    summary = summarize_simulation(states)

    assert summary["total_recharges"] > 0
    assert summary["min_battery_pct"] < 100.0


def test_m7_a_route_that_never_recharges_is_unaffected():
    from app.simulation import simulate_path, summarize_simulation

    shape = (1, 4)
    plan = {
        "path_pixels": [(0, i) for i in range(4)],
        "error": None,
        "metrics": {},
    }
    states = simulate_path(
        plan,
        np.full(shape, 0.3),
        np.full(shape, 3.0),
        np.full(shape, -60.0),
        np.zeros(shape),
        rover=get_rover("lpr_1"),
        pixel_size_m=80.0,
    )
    summary = summarize_simulation(states)
    assert summary["total_recharges"] == 0
    assert summary["min_battery_pct"] == pytest.approx(
        min(state.battery_pct for state in states)
    )


# ── M-1: the 4-D planner must refuse diagonal corner-cutting ──────────────


def _checkerboard():
    """2x2 where only the diagonal connects -- the 2-D planner refuses it."""
    return np.array([[True, False], [False, True]])


def test_m1_the_4d_planner_refuses_the_squeeze_the_2d_planner_refuses():
    from app.pathfinder_4d import astar_4d

    traversable = _checkerboard()
    cost = np.where(traversable, 0.3, np.inf)
    cube = np.repeat(cost[None, :, :], 4, axis=0).astype(np.float64)

    result = astar_4d(
        cube,
        np.zeros_like(cube),
        traversable,
        (0, 0),
        (1, 1),
        resolution_m=80.0,
        slice_hours=1.0,
        rover=get_rover("lpr_1"),
    )
    assert result.get("error") is not None


def test_m1_bfs_move_count_agrees_with_the_planner():
    """move_count sizes the 4-D horizon; if it counts a route the planner
    cannot take, the horizon is sized for a plan that will not happen."""
    from app.pathfinder_4d import bfs_move_count

    assert bfs_move_count(_checkerboard(), (0, 0), (1, 1)) is None


def test_m1_an_open_diagonal_is_still_allowed():
    """The rule forbids squeezing between two blocked cells, not diagonal
    movement itself."""
    from app.pathfinder_4d import astar_4d, bfs_move_count

    traversable = np.ones((2, 2), dtype=bool)
    cost = np.full((2, 2), 0.3)
    cube = np.repeat(cost[None, :, :], 4, axis=0)

    assert bfs_move_count(traversable, (0, 0), (1, 1)) == 1
    result = astar_4d(
        cube,
        np.zeros_like(cube),
        traversable,
        (0, 0),
        (1, 1),
        resolution_m=80.0,
        slice_hours=1.0,
        rover=get_rover("lpr_1"),
    )
    assert result.get("error") is None


# ── M-3: PoseEstimate must reject a non-finite heading ────────────────────


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_m3_non_finite_heading_is_rejected(bad):
    """nan % 360 is nan and inf % 360 is nan, so the wrap validator
    accepted non-finite headings and stored them as NaN -- in the module
    whose docstring promises NaN is closed at the boundary."""
    from app.pose import PoseEstimate

    with pytest.raises(ValidationError):
        PoseEstimate(
            x_m=0.0,
            y_m=0.0,
            heading_deg=bad,
            covariance_m=1.0,
            heading_covariance_deg=1.0,
            timestamp_utc="2026-08-30T12:00:00Z",
            source="visual_odometry",
            distance_travelled_m=0.0,
        )


# ── L-9: a NaN azimuth bin must not kill the whole skyline match ──────────


def test_l9_a_partially_occluded_skyline_still_matches():
    """A mast or lander in view leaves NaN bins. Those used to poison
    every cell's score and return None -- indistinguishable from an empty
    search space."""
    from app.horizon import horizon_map
    from app.skyline import match_skyline

    rows = np.arange(24, dtype=np.float64)[:, None]
    cols = np.arange(24, dtype=np.float64)[None, :]
    dem = 40.0 * np.sin(rows / 3.0) + 25.0 * np.cos(cols / 4.0)
    cube = horizon_map(dem, 5.0, n_azimuth=16, max_range_m=200.0, max_steps=40)

    observed = cube[:, 7, 9].astype(np.float64).copy()
    observed[3] = np.nan  # one occluded bearing

    fix = match_skyline(observed, cube)
    assert fix is not None
    assert (fix.row, fix.col) == (7, 9)


def test_l9_an_all_nan_observation_is_still_refused():
    from app.horizon import horizon_map
    from app.skyline import match_skyline

    dem = np.zeros((12, 12))
    cube = horizon_map(dem, 5.0, n_azimuth=16, max_range_m=200.0, max_steps=40)
    with pytest.raises(ValueError):
        match_skyline(np.full(16, np.nan), cube)


# ── L-11: the baseline script's default start must be traversable ─────────


def test_l11_nav2_baseline_default_start_matches_its_sibling_scripts():
    import re
    from pathlib import Path

    source = (
        Path(__file__).resolve().parent.parent / "scripts" / "nav2_baseline.py"
    ).read_text(encoding="utf-8")
    match = re.search(r'"--start".*?default=\((\d+), (\d+)\)', source, re.S)
    assert match is not None
    assert (int(match.group(1)), int(match.group(2))) == (150, 150)


# ── L-4: "grids not loaded" must answer with one status code ──────────────


def test_l4_every_endpoint_reports_missing_grids_as_503():
    previous = getattr(app.state, "grids", None)
    try:
        with TestClient(app) as client:
            app.state.grids = None
            for path, body in (
                ("/api/plan", {"start": {"row": 0, "col": 0},
                               "goal": {"row": 1, "col": 1}}),
                ("/api/plan-multi", {"start": {"row": 0, "col": 0},
                                     "goal": {"row": 1, "col": 1}}),
                ("/api/compare", {"start": {"row": 0, "col": 0},
                                  "goal": {"row": 1, "col": 1}}),
            ):
                response = client.post(path, json=body)
                assert response.status_code == 503, f"{path} -> {response.status_code}"
    finally:
        app.state.grids = previous
