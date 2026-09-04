"""cell-telemetry cost breakdown tests."""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.constants import get_rover
from app.main import app

SHAPE = (8, 8)


@pytest.fixture()
def client():
    rover = get_rover()
    grids = {
        "elevation": np.zeros(SHAPE),
        "slope": np.full(SHAPE, 5.0),
        "aspect": np.zeros(SHAPE),
        "thermal": np.full(SHAPE, -60.0),
        "shadow_ratio": np.full(SHAPE, 0.5),
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
            "layer_validity": {"thermal": "MODEL", "shadow_ratio": "DERIVED"},
        },
    }
    with TestClient(app) as test_client:
        # startup lifespan runs on context enter and nulls app.state.grids when
        # no .npy files exist; inject the synthetic grids afterwards.
        app.state.grids = grids
        yield test_client
    app.state.grids = None


def test_cell_telemetry_returns_cost_breakdown(client):
    response = client.get("/api/cell-telemetry", params={"row": 3, "col": 3})
    assert response.status_code == 200
    payload = response.json()

    breakdown = payload["cost_breakdown"]
    assert set(breakdown) == {"slope", "energy", "shadow", "thermal", "total"}
    parts = sum(v for k, v in breakdown.items() if k != "total")
    assert breakdown["total"] == pytest.approx(max(parts, 0.01), abs=1e-9)


def test_cell_telemetry_keeps_existing_fields(client):
    payload = client.get("/api/cell-telemetry", params={"row": 3, "col": 3}).json()
    for key in ("row", "col", "lon", "lat", "altitude_m", "thermal_c", "resolution_m"):
        assert key in payload


def test_cell_telemetry_exposes_layer_validity(client):
    payload = client.get("/api/cell-telemetry", params={"row": 0, "col": 0}).json()
    assert payload["layer_validity"]["thermal"] == "MODEL"


# ── Faz 2 review fix: C1 -- blocked cells must return 200, not 500 ──


def test_blocked_cell_returns_200_with_null_breakdown():
    """Regression: inf in cost_breakdown made JSONResponse raise -> HTTP 500."""
    rover = get_rover()
    blocked = {
        "elevation": np.zeros(SHAPE),
        "slope": np.full(SHAPE, 40.0),
        "aspect": np.zeros(SHAPE),
        "thermal": np.full(SHAPE, -200.0),
        "shadow_ratio": np.full(SHAPE, 0.5),
        "traversable": np.zeros(SHAPE, dtype=bool),
        "cost": np.full(SHAPE, np.inf),
        "metadata": {
            "origin": {"x": 156000.0, "y": 28000.0},
            "resolution_m": 80.0,
            "shape": list(SHAPE),
            "crs": "test",
            "default_rover_id": rover["id"],
            "cost_weights": {
                "w_slope": 0.409, "w_energy": 0.259,
                "w_shadow": 0.142, "w_thermal": 0.19,
            },
        },
    }
    with TestClient(app) as c:
        app.state.grids = blocked
        response = c.get("/api/cell-telemetry", params={"row": 3, "col": 3})
        assert response.status_code == 200
        assert response.json()["cost_breakdown"]["total"] is None
    app.state.grids = None


def test_response_body_is_strict_json(client):
    """Infinity/NaN are Python-only extensions; browsers reject them."""
    import json
    body = client.get("/api/cell-telemetry", params={"row": 3, "col": 3}).text
    json.loads(
        body,
        parse_constant=lambda c: pytest.fail(f"non-standard JSON constant: {c}"),
    )


# ── A1: time-to-safe-haven in the cell tooltip ────────────────────────────────


def test_cell_telemetry_has_no_safe_haven_without_an_epoch(client):
    payload = client.get("/api/cell-telemetry", params={"row": 3, "col": 3}).json()
    assert payload["safe_haven"] is None
    assert payload["safe_haven_model"]["model"] == "unavailable"
    assert "epoch" in payload["safe_haven_model"]["reason"]


def test_cell_telemetry_says_when_the_map_cannot_be_built(client):
    payload = client.get(
        "/api/cell-telemetry",
        params={"row": 3, "col": 3, "start_utc": "2026-09-07T00:00:00"},
    ).json()
    assert payload["safe_haven"] is None
    assert "horizon_map.npy" in payload["safe_haven_model"]["reason"]


def test_cell_telemetry_reports_the_haven_verdict_and_the_time_to_one(client, monkeypatch):
    import app.main as main_module

    def _fake(grids, rover_id, start_utc, span_hours=708.7, step_hours=2.0):
        safe = np.zeros(SHAPE, dtype=bool)
        safe[0, 0] = True
        tts = np.full(SHAPE, 1.5)
        tts[0, 0] = 0.0
        tts[7, 7] = np.inf
        layers = {
            "safe_haven": safe,
            "max_dark_hours_without_dte": np.where(safe, 20.0, 70.0),
            "earth_below_hours": np.full(SHAPE, 310.0),
            "ever_lit": np.ones(SHAPE, dtype=bool),
        }
        info = {"model": "spice_horizon", "h_max_shadow_h": 50.0, "rover_id": rover_id}
        return layers, tts, info

    monkeypatch.setattr(main_module, "safe_haven_for_grids", _fake)
    params = {"start_utc": "2026-09-07T00:00:00"}

    haven = client.get("/api/cell-telemetry", params={"row": 0, "col": 0, **params}).json()
    assert haven["safe_haven_model"]["model"] == "spice_horizon"
    assert haven["safe_haven"] == {
        "is_safe_haven": True,
        "max_dark_hours_without_dte_h": 20.0,
        "earth_below_hours": 310.0,
        "time_to_safe_haven_h": 0.0,
        "h_max_shadow_h": 50.0,
    }

    plain = client.get("/api/cell-telemetry", params={"row": 3, "col": 3, **params}).json()
    assert plain["safe_haven"]["is_safe_haven"] is False
    assert plain["safe_haven"]["time_to_safe_haven_h"] == 1.5

    cut_off = client.get("/api/cell-telemetry", params={"row": 7, "col": 7, **params}).json()
    assert cut_off["safe_haven"]["time_to_safe_haven_h"] is None
