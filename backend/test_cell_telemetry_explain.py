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
