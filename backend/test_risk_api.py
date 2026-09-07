"""risk_alpha on /api/plan and /api/plan-4d, the `risk` block, and the
/api/risk-sweep endpoint (B2) -- synthetic 16x16 grid, no kernels, no clone
cache (so the slope sigma source is "none" and the slope criterion stays
nominal; the real-grid test covers the clone path)."""

from __future__ import annotations

import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.constants import get_rover
from app.main import app
from app.risk import RISK_MEASURE_ID, cvar_multiplier

SHAPE = (16, 16)
_client = TestClient(app)


def _grids():
    rover = get_rover()
    rng = np.random.default_rng(21)
    # A gentle slope field with a steeper band, so the tail has something to
    # reorder; every cell stays passable for every catalogue rover.
    slope = rng.uniform(2.0, 6.0, SHAPE)
    slope[6:9, :] = rng.uniform(10.0, 14.0, (3, SHAPE[1]))
    return {
        "elevation": np.zeros(SHAPE),
        "slope": slope,
        "aspect": np.zeros(SHAPE),
        "thermal": np.full(SHAPE, -60.0),
        "shadow_ratio": rng.uniform(0.0, 0.6, SHAPE),
        "traversable": np.ones(SHAPE, dtype=bool),
        "cost": np.full(SHAPE, 0.3),
        "metadata": {
            "origin": {"x": 156000.0, "y": 28000.0},
            "resolution_m": 80.0,
            "shape": list(SHAPE),
            "crs": "test",
            "default_rover_id": rover["id"],
            "cost_weights": {"w_slope": 0.409, "w_energy": 0.259, "w_shadow": 0.142, "w_thermal": 0.19},
        },
    }


@pytest.fixture()
def client():
    app.state.grids = _grids()
    yield _client
    app.state.grids = None


START = {"row": 0, "col": 0}
GOAL = {"row": 14, "col": 14}


def _plan(client, **extra):
    body = {"start": START, "goal": GOAL, "rover_id": "lpr_1", **extra}
    return client.post("/api/plan", json=body)


def test_plan_with_alpha_carries_the_risk_block(client):
    response = _plan(client, risk_alpha=0.9)
    assert response.status_code == 200, response.text
    payload = response.json()
    block = payload["risk"]
    assert block["applied"] is True and block["alpha"] == 0.9
    assert block["validity"] == "MODEL" and block["measure"] == RISK_MEASURE_ID
    assert block["multiplier"] == pytest.approx(cvar_multiplier(0.9))
    # No clone cache on this grid: the slope criterion stays nominal and says so.
    assert block["criteria"] == {"slope": "nominal", "energy": "cvar"}
    assert block["sigma_sources"]["slope"]["source"] == "none"
    assert block["sigma_sources"]["slip"]["validity"] == "MODEL"
    route = block["route"]
    assert route["moves"] == payload["summary"]["waypoint_count"] - 1
    assert route["hours"] > 0.0 and route["risk_adjusted_hours"] >= route["hours"]
    assert route["mean_slip_cvar"] > route["mean_slip_mu"] > 0.0
    assert route["max_slip_cvar"] >= route["mean_slip_cvar"]
    assert route["slope_sigma_known_fraction"] == 0.0
    assert route["risk_adjusted_drawn_wh"] >= route["drawn_wh"] > 0.0
    assert "not a measured risk" in block["claim"].lower()
    # The existing contract is untouched.
    for key in ("summary", "slip_model", "geojson", "waypoints", "astar_metrics", "corridor"):
        assert key in payload
    json.dumps(payload, allow_nan=False)


def test_plan_without_alpha_reports_the_nominal_grid(client):
    payload = _plan(client).json()
    block = payload["risk"]
    assert block["applied"] is False and block["alpha"] is None and block["route"] is None
    assert block["multiplier"] is None
    assert block["criteria"] == {"slope": "nominal", "energy": "nominal"}
    assert block["sigma_sources"]["slope"]["source"] == "none"
    assert block["validity"] == "MODEL"
    json.dumps(payload, allow_nan=False)


@pytest.mark.parametrize("bad", [0.3, 0.499, 1.0, 1.5, "x", -0.9])
def test_alpha_outside_the_allowed_range_is_a_422(client, bad):
    assert _plan(client, risk_alpha=bad).status_code == 422
    body = {"start": START, "goal": GOAL, "rover_id": "lpr_1", "coarsen": 4, "n_slices": 24, "slice_hours": 1.0, "risk_alpha": bad}
    assert client.post("/api/plan-4d", json=body).status_code == 422


def test_alpha_changes_the_ranking_but_not_the_physics_of_a_route(client):
    """The same route priced under alpha must report the same hours and
    battery: alpha reorders cells, it never re-times them. On this grid the
    two routes coincide, which is exactly what makes the check possible."""
    nominal = _plan(client).json()
    tail = _plan(client, risk_alpha=0.99).json()
    if [w["row"] for w in tail["waypoints"]] == [w["row"] for w in nominal["waypoints"]] and [
        w["col"] for w in tail["waypoints"]
    ] == [w["col"] for w in nominal["waypoints"]]:
        assert tail["summary"]["total_elapsed_hours"] == nominal["summary"]["total_elapsed_hours"]
        assert tail["summary"]["total_energy_consumed_wh"] == nominal["summary"]["total_energy_consumed_wh"]
        assert tail["slip_model"]["route"]["mean_slip"] == nominal["slip_model"]["route"]["mean_slip"]
    # The risk block's own hours are the mean-slip drive hours the slip block
    # accounts for: slip added t*s per leg, so hours >= extra_hours.
    assert tail["risk"]["route"]["hours"] >= tail["slip_model"]["route"]["extra_hours"] > 0.0


def _plan_4d(client, **overrides):
    body = {"start": START, "goal": {"row": 12, "col": 12}, "coarsen": 4, "rover_id": "lpr_1", "n_slices": 24, "slice_hours": 1.0}
    body.update(overrides)
    response = client.post("/api/plan-4d", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_plan_4d_with_alpha_carries_the_risk_block_and_keeps_its_clock(client):
    nominal = _plan_4d(client)
    tail = _plan_4d(client, risk_alpha=0.99)
    assert nominal["risk"]["applied"] is False and nominal["risk"]["route"] is None
    block = tail["risk"]
    assert block["applied"] is True and block["alpha"] == 0.99
    assert block["criteria"] == {"slope": "nominal", "energy": "cvar"}
    route = block["route"]
    assert route["moves"] == tail["metrics"]["move_steps"]
    assert route["risk_adjusted_hours"] >= route["hours"] > 0.0
    assert route["mean_slip_cvar"] > route["mean_slip_mu"]
    if tail["path_states"] == nominal["path_states"]:
        assert tail["metrics"]["arrival_hours"] == nominal["metrics"]["arrival_hours"]
        assert tail["path_battery_pct"] == nominal["path_battery_pct"]
    for key in ("path_pixels", "path_states", "metrics", "slip_model", "illumination_corridor", "shadow_model"):
        assert key in tail
    json.dumps(tail, allow_nan=False)


# ── /api/risk-sweep ─────────────────────────────────────────────────────────


def _sweep(client, **extra):
    body = {"start": START, "goal": GOAL, "rover_id": "lpr_1", **extra}
    return client.post("/api/risk-sweep", json=body)


def test_risk_sweep_plans_the_nominal_and_every_alpha_side_by_side(client):
    response = _sweep(client)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["planner"] == "2d" and payload["rover_id"] == "lpr_1"
    assert payload["alphas"] == [None, 0.5, 0.9, 0.99]
    assert payload["validity"] == "MODEL" and payload["measure"] == RISK_MEASURE_ID
    results = payload["results"]
    assert [r["risk_alpha"] for r in results] == [None, 0.5, 0.9, 0.99]
    assert results[0]["risk"]["applied"] is False
    for entry in results:
        assert entry["error"] is None
        assert entry["waypoints"] and {"row", "col"} <= set(entry["waypoints"][0])
        assert entry["summary"]["waypoint_count"] == len(entry["waypoints"])
        assert entry["slip_model"]["applied"] is True
        assert 0.0 <= entry["overlap_with_nominal"] <= 1.0
        assert entry["plan_ms"] >= 0.0
        assert "astar_metrics" in entry
    assert results[0]["overlap_with_nominal"] == 1.0
    for entry in results[1:]:
        assert entry["risk"]["applied"] is True and entry["risk"]["alpha"] == entry["risk_alpha"]
        assert entry["risk"]["route"]["moves"] == entry["summary"]["waypoint_count"] - 1

    matrix = payload["risk_matrix"]
    assert matrix["route_alphas"] == [None, 0.5, 0.9, 0.99]
    assert matrix["eval_alphas"] == [0.5, 0.9, 0.99]
    for key in ("risk_adjusted_hours", "mean_slip_cvar", "max_slope_cvar_deg"):
        rows = matrix[key]
        assert len(rows) == 4 and all(len(row) == 3 for row in rows)
        # A route's tail figure grows with the alpha it is evaluated at.
        for row in rows:
            assert row[0] <= row[1] <= row[2]

    comparison = payload["comparison"]
    assert set(comparison["nominal"]) >= {"distance_km", "hours", "energy_wh", "min_battery_pct", "mean_slip", "max_slip"}
    deltas = comparison["deltas"]
    assert [d["risk_alpha"] for d in deltas] == [0.5, 0.9, 0.99]
    for delta in deltas:
        assert set(delta) >= {"risk_alpha", "distance_km", "hours", "energy_wh", "min_battery_pct", "mean_slip", "max_slip", "overlap_with_nominal"}
    assert comparison["lowest_risk_adjusted_hours_alpha"] in (None, 0.5, 0.9, 0.99)
    assert "not a measured risk" in payload["claim"].lower()
    assert "0.5" in payload["note"] and "mean" in payload["note"].lower()
    json.dumps(payload, allow_nan=False)


def test_risk_sweep_options_and_validation(client):
    payload = _sweep(client, alphas=[0.9, 0.9, 0.6], include_nominal=False).json()
    assert payload["alphas"] == [0.9, 0.6]  # duplicates dropped, order kept
    assert [r["risk_alpha"] for r in payload["results"]] == [0.9, 0.6]
    assert payload["comparison"] is None
    assert all(r["overlap_with_nominal"] is None for r in payload["results"])
    assert payload["risk_matrix"]["route_alphas"] == [0.9, 0.6]
    assert payload["risk_matrix"]["eval_alphas"] == [0.9, 0.6]

    assert _sweep(client, alphas=[]).status_code == 422
    assert _sweep(client, alphas=[0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99]).status_code == 422
    assert _sweep(client, alphas=[0.2]).status_code == 422
    assert _sweep(client, alphas=[1.0]).status_code == 422
    assert _sweep(client, goal={"row": 99, "col": 99}).status_code == 422
    assert client.post("/api/risk-sweep", json={"start": START, "goal": GOAL, "rover_id": "nope"}).status_code in (404, 422)


def test_risk_sweep_reports_a_refused_pair_per_alpha_without_failing(client):
    grids = _grids()
    grids["traversable"][:, 8] = False  # a wall: no route at any alpha
    grids["slope"][:, 8] = 60.0
    app.state.grids = grids
    response = _sweep(client)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert all(r["error"] for r in payload["results"])
    assert all(r["waypoints"] == [] for r in payload["results"])
    assert payload["comparison"] is None
    json.dumps(payload, allow_nan=False)
