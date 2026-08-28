"""/api/plan-4d endpoint tests."""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.constants import get_rover
from app.main import app

SHAPE = (16, 16)

# Built once so the startup handler runs and fails gracefully (no .npy files);
# grids are injected per-test afterwards, mirroring test_plan_endpoint.py.
_client = TestClient(app)


@pytest.fixture()
def client():
    rover = get_rover()
    app.state.grids = {
        "elevation": np.zeros(SHAPE),
        "slope": np.full(SHAPE, 3.0),
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
    yield _client
    app.state.grids = None


def _body(**overrides) -> dict:
    body = {
        "start": {"row": 0, "col": 0},
        "goal": {"row": 12, "col": 12},
        "n_slices": 24,
        "slice_hours": 1.0,
        "coarsen": 4,
    }
    body.update(overrides)
    return body


def test_plan_4d_returns_a_path(client):
    response = client.post("/api/plan-4d", json=_body())
    assert response.status_code == 200
    payload = response.json()
    assert payload["path_pixels"]
    assert payload["metrics"]["arrival_slice"] is not None


def test_plan_4d_reports_wait_steps(client):
    payload = client.post("/api/plan-4d", json=_body()).json()
    assert "wait_steps" in payload["metrics"]


def test_plan_4d_echoes_time_configuration(client):
    payload = client.post("/api/plan-4d", json=_body(n_slices=12)).json()
    assert payload["n_slices"] == 12
    assert payload["slice_hours"] == 1.0
    assert payload["coarsen"] == 4


def test_plan_4d_rejects_non_divisible_coarsen(client):
    response = client.post("/api/plan-4d", json=_body(coarsen=5))
    assert response.status_code == 422


# ── Review findings: coordinate space and degenerate start/goal ───────────────


def test_path_pixels_are_fine_grid_coordinates(client):
    """``path_pixels`` must be in the same space as /api/plan.

    The planner solves on a coarsened grid, but the caller asked in fine
    pixels and a local planner will convert these with the fine
    ``resolution_m``/``origin``. Returning coarse indices under the same
    field name is a 4x scale error waiting to happen.
    """
    payload = client.post("/api/plan-4d", json=_body()).json()
    rows, cols = SHAPE
    for row, col in payload["path_pixels"]:
        assert 0 <= row < rows
        assert 0 <= col < cols
    # A 16x16 grid at coarsen=4 has coarse indices 0..3; a fine path to
    # (12, 12) must reach beyond that range.
    assert max(max(r, c) for r, c in payload["path_pixels"]) > 3


def test_path_pixels_end_near_the_requested_goal(client):
    payload = client.post("/api/plan-4d", json=_body()).json()
    last_row, last_col = payload["path_pixels"][-1]
    # Within one coarse block of the requested (12, 12).
    assert abs(last_row - 12) < 4
    assert abs(last_col - 12) < 4


def test_response_reports_the_effective_planning_resolution(client):
    payload = client.post("/api/plan-4d", json=_body()).json()
    assert payload["effective_resolution_m"] == pytest.approx(80.0 * 4)


def test_coarse_path_is_still_available_under_its_own_name(client):
    payload = client.post("/api/plan-4d", json=_body()).json()
    assert payload["path_pixels_coarse"]
    assert len(payload["path_pixels_coarse"]) == len(payload["path_pixels"])


def test_start_and_goal_in_the_same_coarse_cell_is_rejected(client):
    """(0,0) and (3,3) both collapse to coarse (0,0) at coarsen=4."""
    response = client.post(
        "/api/plan-4d", json=_body(goal={"row": 3, "col": 3})
    )
    assert response.status_code == 422
    assert "coarse" in response.json()["detail"].lower()


def test_identical_start_and_goal_is_rejected(client):
    response = client.post(
        "/api/plan-4d", json=_body(start={"row": 4, "col": 4}, goal={"row": 4, "col": 4})
    )
    assert response.status_code == 422


# ── Review finding C1: the time axis must advance in real hours ───────────────


def test_slice_hours_is_derived_from_the_grid_when_omitted(client):
    """Omitting slice_hours must produce a slice sized to one cell crossing,
    not the 1 h default that collapsed every move to a single slice."""
    body = _body()
    body.pop("slice_hours")
    payload = client.post("/api/plan-4d", json=body).json()

    from app.cost_engine import edge_travel_time_s

    rover = get_rover()
    # 80 m fine cells at coarsen=4 -> 320 m coarse edges at slope 3 deg.
    expected = edge_travel_time_s(3.0, 320.0, rover) / 3600.0
    assert payload["slice_hours"] == pytest.approx(expected, rel=0.2)
    assert payload["slice_hours_source"] == "auto"


def test_explicit_slice_hours_is_still_honoured(client):
    payload = client.post("/api/plan-4d", json=_body(slice_hours=2.0)).json()
    assert payload["slice_hours"] == 2.0
    assert payload["slice_hours_source"] == "request"


def test_auto_slice_hours_makes_arrival_slice_a_clock(client):
    """With an auto slice the horizon is real time, so the response can
    report it in hours rather than in steps."""
    body = _body()
    body.pop("slice_hours")
    payload = client.post("/api/plan-4d", json=body).json()

    arrival = payload["metrics"]["arrival_slice"]
    assert payload["metrics"]["arrival_hours"] == pytest.approx(
        arrival * payload["slice_hours"]
    )
    assert payload["horizon_hours"] == pytest.approx(
        payload["n_slices"] * payload["slice_hours"]
    )


def test_horizon_can_be_requested_in_hours(client):
    """n_slices is a memory knob; the mission cares about hours. With an
    auto slice a fixed slice count no longer means a fixed horizon."""
    body = _body(horizon_hours=6.0)
    body.pop("n_slices")
    payload = client.post("/api/plan-4d", json=body).json()
    assert payload["horizon_hours"] == pytest.approx(6.0, rel=0.05)
    assert payload["n_slices"] > 1


def test_horizon_hours_and_n_slices_are_mutually_exclusive(client):
    response = client.post(
        "/api/plan-4d", json=_body(horizon_hours=6.0, n_slices=24)
    )
    assert response.status_code == 422
    assert "horizon_hours" in response.json()["detail"]


def test_horizon_hours_is_capped_to_bound_memory(client):
    """On a fine grid a physical slice is ~2 minutes, so a week-long horizon
    is thousands of slices and two float64 cubes of hundreds of MB. The cap
    must refuse rather than allocate. (Faz 3 review, C1.)"""
    body = _body(horizon_hours=168.0, slice_hours=0.05)
    body.pop("n_slices")
    response = client.post("/api/plan-4d", json=body)
    assert response.status_code == 422
    assert "slices" in response.json()["detail"].lower()


def test_horizon_within_the_cap_is_accepted(client):
    body = _body(horizon_hours=20.0, slice_hours=0.05)
    body.pop("n_slices")
    payload = client.post("/api/plan-4d", json=body).json()
    assert payload["n_slices"] == 400
    assert payload["horizon_hours"] == pytest.approx(20.0)
