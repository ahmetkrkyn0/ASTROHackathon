"""/api/plan corridor field tests."""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.constants import get_rover
from app.main import app

SHAPE = (30, 30)


@pytest.fixture()
def client():
    rover = get_rover()
    grids = {
        "elevation": np.zeros(SHAPE),
        "slope": np.full(SHAPE, 3.0),
        "aspect": np.zeros(SHAPE),
        "thermal": np.full(SHAPE, -60.0),
        "shadow_ratio": np.full(SHAPE, 0.2),
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
    with TestClient(app) as test_client:
        app.state.grids = grids
        yield test_client
    app.state.grids = None


def _plan(client):
    return client.post(
        "/api/plan",
        json={
            "start": {"row": 2, "col": 2},
            "goal": {"row": 25, "col": 25},
            "include_simulation": True,
        },
    )


def test_plan_response_contains_corridor(client):
    response = _plan(client)
    assert response.status_code == 200
    corridor = response.json()["corridor"]
    assert corridor is not None
    assert len(corridor["waypoints"]) >= 2
    assert len(corridor["half_width_m"]) == len(corridor["waypoints"]) - 1


def test_corridor_waypoints_are_metre_pairs(client):
    corridor = _plan(client).json()["corridor"]
    for point in corridor["waypoints"]:
        assert len(point) == 2
        assert all(isinstance(value, (int, float)) for value in point)


def test_existing_plan_fields_are_untouched(client):
    payload = _plan(client).json()
    for key in ("astar_metrics", "summary", "geojson"):
        assert key in payload
