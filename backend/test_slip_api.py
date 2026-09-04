"""slip_model blocks on /api/rovers, /api/plan, /api/plan-4d, /api/compare and
/api/plan-multi, and the slip-aware default horizon (C3) -- synthetic grids,
no kernels, no clone cache."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.constants import get_rover
from app.cost_engine import edge_travel_time_s
from app.main import DEFAULT_HORIZON_WAIT_PAD_SLICES, app
from app.slip_model import slip_ratio

SHAPE = (16, 16)
SLOPE_DEG = 3.0
_client = TestClient(app)


def _grids():
    rover = get_rover()
    return {
        "elevation": np.zeros(SHAPE),
        "slope": np.full(SHAPE, SLOPE_DEG),
        "aspect": np.zeros(SHAPE),
        "thermal": np.full(SHAPE, -60.0),
        "shadow_ratio": np.full(SHAPE, 0.3),
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


def test_rovers_publish_the_slip_model_block(client):
    body = client.get("/api/rovers").json()
    assert body["rovers"]
    for entry in body["rovers"]:
        block = entry["slip_model"]
        assert block["applied"] is True and block["validity"] == "MODEL"
        assert block["anchors"] and all(a["source"] for a in block["anchors"])
        assert len(block["table"]) == 6
        assert "not a measurement" in block["claim"].lower()
        assert "regolith" in entry["declared_only"]
    json.dumps(body, allow_nan=False)


def test_plan_carries_the_route_slip_block(client):
    rover = get_rover("lpr_1")
    response = client.post(
        "/api/plan", json={"start": {"row": 0, "col": 0}, "goal": {"row": 12, "col": 12}, "rover_id": "lpr_1"}
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    block = payload["slip_model"]
    assert block["applied"] is True and block["validity"] == "MODEL"
    route = block["route"]
    assert route["moves"] == payload["summary"]["waypoint_count"] - 1
    assert route["mean_slip"] == pytest.approx(slip_ratio(SLOPE_DEG, rover), rel=1e-6)
    assert route["max_slip"] == pytest.approx(slip_ratio(SLOPE_DEG, rover), rel=1e-6)
    assert route["distance_factor"] == pytest.approx(1.0 / (1.0 - slip_ratio(SLOPE_DEG, rover)), rel=1e-6)
    assert route["extra_hours"] > 0.0 and route["extra_drawn_wh"] > 0.0
    # The extra hours are the slip share of the simulated drive time.
    assert route["extra_hours"] == pytest.approx(
        payload["summary"]["total_elapsed_hours"] * slip_ratio(SLOPE_DEG, rover), rel=1e-3
    )
    json.dumps(payload, allow_nan=False)


def _plan_4d(client, **overrides):
    body = {"start": {"row": 0, "col": 0}, "goal": {"row": 12, "col": 12}, "coarsen": 4, "rover_id": "lpr_1"}
    body.update(overrides)
    response = client.post("/api/plan-4d", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_plan_4d_carries_the_route_slip_block(client):
    rover = get_rover("lpr_1")
    payload = _plan_4d(client, n_slices=24, slice_hours=1.0)
    block = payload["slip_model"]
    assert block["applied"] is True and block["validity"] == "MODEL"
    route = block["route"]
    assert route["moves"] == payload["metrics"]["move_steps"]
    assert route["mean_slip"] == pytest.approx(slip_ratio(SLOPE_DEG, rover), rel=1e-6)
    assert route["extra_drawn_wh"] is not None and route["extra_drawn_wh"] > 0.0
    # Hours the slip added: sum over moves of the planner's own edge time
    # times the slip there (t = t0 / (1 - s)  =>  t - t0 = t * s).
    expected = 0.0
    states = payload["path_states"]
    for (r0, c0, _t0), (r1, c1, _t1) in zip(states[:-1], states[1:]):
        if (r0, c0) == (r1, c1):
            continue
        distance = 320.0 * (math.sqrt(2.0) if (r0 != r1 and c0 != c1) else 1.0)
        expected += edge_travel_time_s(SLOPE_DEG, distance, rover) / 3600.0 * slip_ratio(SLOPE_DEG, rover)
    assert route["extra_hours"] == pytest.approx(expected, rel=1e-9)


def test_plan_4d_default_horizon_is_sized_from_the_fastest_gated_route(client):
    """ceil(fastest route hours / slice) + its moves + the wait pad: each
    move can lose at most one slice to rounding, so this is sufficient --
    and, unlike moves x slowest-conceivable-edge, it does not explode when
    the slowest edge is ten times slower than a typical one under slip."""
    from app.safe_haven import gated_shortest_drive

    rover = get_rover("lpr_1")
    payload = _plan_4d(client)
    coarse = (SHAPE[0] // 4, SHAPE[1] // 4)
    hours, moves = gated_shortest_drive(
        np.ones(coarse, dtype=bool), np.zeros(coarse), np.full(coarse, SLOPE_DEG), 320.0, rover, (0, 0), (3, 3)
    )
    expected = int(math.ceil(hours / payload["slice_hours"])) + moves + DEFAULT_HORIZON_WAIT_PAD_SLICES
    assert payload["n_slices"] == max(2, expected)
    assert payload["metrics"]["arrival_slice"] < payload["n_slices"]


def test_compare_and_plan_multi_results_carry_the_slip_block(client):
    response = client.post("/api/compare", json={"start": [0, 0], "goal": [12, 12], "rover_id": "lpr_1"})
    assert response.status_code == 200, response.text
    results = response.json()["results"]
    assert results
    for result in results:
        if not result.get("error"):
            assert result["slip_model"]["applied"] is True
            assert result["slip_model"]["route"]["moves"] > 0

    profiles = client.get("/api/profiles").json()
    profile_ids = [p["id"] for p in profiles] if isinstance(profiles, list) else list(profiles)
    response = client.post(
        "/api/plan-multi",
        json={"start": [0, 0], "goal": [12, 12], "rover_id": "lpr_1", "profiles": profile_ids[:2] + ["nope"]},
    )
    assert response.status_code == 200, response.text
    results = response.json()["results"]
    assert results[0]["slip_model"]["applied"] is True
    assert results[-1]["error"] and "slip_model" not in results[-1]
