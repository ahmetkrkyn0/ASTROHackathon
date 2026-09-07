"""POST /api/stress-test: SHERPA's Monte Carlo traverse evaluation of a
/api/plan-4d route, on a synthetic grid without kernels (static sky)."""

from __future__ import annotations

import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.constants import get_rover
from app.main import app

SHAPE = (16, 16)

_client = TestClient(app)


def _grids(slope=None):
    rover = get_rover()
    return {
        "elevation": np.zeros(SHAPE),
        "slope": np.full(SHAPE, 3.0) if slope is None else slope,
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
            "cost_weights": {
                "w_slope": 0.409,
                "w_energy": 0.259,
                "w_shadow": 0.142,
                "w_thermal": 0.19,
            },
        },
    }


@pytest.fixture()
def client():
    app.state.grids = _grids()
    yield _client
    app.state.grids = None


# A coarse-grid route at coarsen=4 (4x4 planner cells): three moves, one wait.
ROUTE = [[0, 0, 0], [0, 1, 1], [0, 1, 2], [1, 2, 3], [2, 3, 4]]


def _body(**overrides) -> dict:
    body = {
        "path_states": ROUTE,
        "rover_id": "lpr_1",
        "coarsen": 4,
        "slice_hours": 1.0,
        "n_runs": 200,
        "seed": 1,
    }
    body.update(overrides)
    return body


def test_stress_test_returns_the_full_summary_on_a_static_sky(client):
    response = client.post("/api/stress-test", json=_body(label="fast"))
    assert response.status_code == 200, response.text
    payload = response.json()
    for key in (
        "label", "rover_id", "coarsen", "slice_hours", "start_utc", "initial_soc_pct",
        "n_runs", "seed", "route", "perturbations", "sky_model", "safe_haven_model",
        "rates", "failures", "metrics", "histograms", "per_state", "outages",
        "nominal", "verdict", "timing_ms",
    ):
        assert key in payload, key
    assert payload["label"] == "fast"
    assert payload["n_runs"] == 200 and payload["seed"] == 1
    assert payload["route"] == {
        "n_states": 5, "move_steps": 3, "wait_steps": 1,
        "planned_duration_h": 4.0,
        "odometry_m": pytest.approx(80.0 * 4 * (1 + 2 * 2 ** 0.5), abs=1e-3),
        "ends_at_safe_haven": None,
    }
    # No epoch: the sky is the long-run layer held constant, and it says so.
    assert payload["sky_model"]["model"] == "static"
    assert payload["sky_model"]["time_varying"] is False
    assert "epoch" in payload["sky_model"]["reason"]
    assert payload["sky_model"]["n_slices_extended"] >= 4
    assert payload["safe_haven_model"]["model"] == "unavailable"
    # No Earth field on this grid: the DSN margin is unknown, not zero.
    assert payload["metrics"]["time_to_dsn_shadow_min_h"] is None
    assert payload["metrics"]["duration_h"]["n"] == 200
    assert payload["rates"]["completion"]["count"] + sum(payload["failures"].values()) == 200
    assert payload["perturbations"]["speed_sigma"] == 0.2
    assert payload["perturbations"]["source"]
    assert payload["nominal"]["reached"] is True
    assert set(payload["timing_ms"]) == {"sky", "runs", "total"}
    # JSON-safe throughout.
    json.dumps(payload, allow_nan=False)


def test_the_same_seed_gives_the_same_answer(client):
    a = client.post("/api/stress-test", json=_body()).json()
    b = client.post("/api/stress-test", json=_body()).json()
    c = client.post("/api/stress-test", json=_body(seed=2)).json()
    for payload in (a, b, c):
        payload.pop("timing_ms")
    assert a == b
    assert a != c


def test_perturbation_overrides_are_applied_and_echoed(client):
    payload = client.post(
        "/api/stress-test",
        json=_body(perturbations={"speed_sigma": 0.5, "dsn_outage_probability": 1.0}),
    ).json()
    assert payload["perturbations"]["speed_sigma"] == 0.5
    assert payload["perturbations"]["dsn_outage_probability"] == 1.0
    assert payload["perturbations"]["power_draw_sigma"] == 0.2  # default kept
    assert payload["outages"]["dsn"]["runs"] == 200
    assert payload["metrics"]["speed_multiplier"]["min"] < 0.5


def test_the_initial_state_of_charge_is_honoured(client):
    payload = client.post("/api/stress-test", json=_body(initial_soc_pct=0.5)).json()
    assert payload["initial_soc_pct"] == 0.5
    assert payload["nominal"]["min_battery_pct"] <= 50.0 + 1e-6
    assert payload["metrics"]["initial_soc_pct"]["max"] <= 50.0 + 1e-6


@pytest.mark.parametrize(
    "path_states, fragment",
    [
        ([[0, 0, 0], [3, 3, 1]], "adjacent"),
        ([[0, 0, 1], [0, 1, 2]], "slice 0"),
        ([[0, 0, 0], [0, 1, 0]], "increase"),
        ([[0, 0, 0], [0, 9, 1]], "outside"),
        ([[0, 0, 0]], "two"),
    ],
)
def test_a_malformed_route_is_a_422_with_the_reason(client, path_states, fragment):
    response = client.post("/api/stress-test", json=_body(path_states=path_states))
    assert response.status_code == 422
    assert fragment in response.json()["detail"]


def test_a_route_through_an_impassable_block_is_a_422():
    # grids_for_rover derives traversability from the rover's slope limit,
    # so the block is closed the way the planner would see it closed.
    slope = np.full(SHAPE, 3.0)
    slope[4:8, 4:8] = 40.0  # coarse cell (1, 1), over LPR-1's 25 deg limit
    app.state.grids = _grids(slope)
    try:
        response = _client.post(
            "/api/stress-test", json=_body(path_states=[[0, 0, 0], [1, 1, 1]])
        )
    finally:
        app.state.grids = None
    assert response.status_code == 422
    assert "traversable" in response.json()["detail"]


def test_request_validation(client):
    assert client.post("/api/stress-test", json={"path_states": ROUTE}).status_code == 422
    assert client.post("/api/stress-test", json=_body(n_runs=0)).status_code == 422
    assert client.post("/api/stress-test", json=_body(n_runs=20001)).status_code == 422
    assert client.post("/api/stress-test", json=_body(coarsen=5)).status_code == 422
    assert client.post("/api/stress-test", json=_body(rover_id="nope")).status_code in (404, 422)
    assert client.post(
        "/api/stress-test", json=_body(perturbations={"speed_sigma": -1.0})
    ).status_code == 422


def test_without_grids_the_endpoint_answers_503():
    app.state.grids = None
    assert _client.post("/api/stress-test", json=_body()).status_code == 503
