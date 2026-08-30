"""POST /api/pose: the closed loop the Phase 7 plan asks for.

pose -> corridor fix -> trigger -> replan, end to end against the real
app, with the corridor coming from a real /api/plan call rather than a
hand-built fixture. The plan's acceptance criterion is that
corridor_violation and localization_uncertainty fire from an actual
pose, and that /api/replan can consume the pose endpoint's output
unchanged.
"""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.constants import get_rover
from app.main import app

_SHAPE = (30, 30)


def _synthetic_grids() -> dict:
    rover = get_rover()
    return {
        "elevation": np.zeros(_SHAPE),
        "slope": np.full(_SHAPE, 3.0),
        "aspect": np.zeros(_SHAPE),
        "thermal": np.full(_SHAPE, -60.0),
        "shadow_ratio": np.full(_SHAPE, 0.2),
        "traversable": np.ones(_SHAPE, dtype=bool),
        "cost": np.full(_SHAPE, 0.3),
        "metadata": {
            "origin": {"x": 156000.0, "y": 28000.0},
            "resolution_m": 80.0,
            "shape": list(_SHAPE),
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


def _pose_body(x_m, y_m, **overrides) -> dict:
    body = {
        "x_m": x_m,
        "y_m": y_m,
        "heading_deg": 90.0,
        "covariance_m": 2.0,
        "heading_covariance_deg": 1.0,
        "timestamp_utc": "2026-08-30T12:00:00Z",
        "source": "dead_reckoning",
        "distance_travelled_m": 0.0,
    }
    body.update(overrides)
    return body


@pytest.fixture()
def client():
    """A client with synthetic grids injected and a corridor planned.

    Grids go in AFTER the lifespan runs -- startup loads the real 500x500
    grid over anything staged earlier (see test_route_analysis).
    """
    previous_grids = getattr(app.state, "grids", None)
    previous_corridor = getattr(app.state, "active_corridor", None)
    app.state.active_corridor = None
    try:
        with TestClient(app) as test_client:
            app.state.grids = _synthetic_grids()
            yield test_client
    finally:
        app.state.grids = previous_grids
        app.state.active_corridor = previous_corridor


def _plan(client) -> dict:
    response = client.post(
        "/api/plan",
        json={"start": {"row": 2, "col": 2}, "goal": {"row": 2, "col": 25}},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _corridor_start_xy(plan_payload) -> tuple[float, float]:
    return tuple(plan_payload["corridor"]["waypoints"][0])


def test_pose_without_an_active_corridor_is_a_409(client):
    response = client.post("/api/pose", json={"pose": _pose_body(0.0, 0.0)})
    assert response.status_code == 409
    assert "plan" in response.json()["detail"].lower()


def test_a_pose_on_the_route_recommends_continue(client):
    plan_payload = _plan(client)
    x0, y0 = _corridor_start_xy(plan_payload)

    response = client.post("/api/pose", json={"pose": _pose_body(x0, y0)})

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["corridor_fix"]["inside"] is True
    assert payload["fired_triggers"] == []
    assert payload["recommended_action"] == "continue"


def test_a_pose_off_the_corridor_fires_corridor_violation(client):
    plan_payload = _plan(client)
    x0, y0 = _corridor_start_xy(plan_payload)
    half_width = plan_payload["corridor"]["half_width_m"][0]

    response = client.post(
        "/api/pose",
        json={"pose": _pose_body(x0, y0 + half_width + 50.0)},
    )

    payload = response.json()
    fired = {t["trigger_id"] for t in payload["fired_triggers"]}
    assert "corridor_violation" in fired
    assert payload["corridor_fix"]["inside"] is False
    assert payload["recommended_action"] == "replan"


def test_a_wide_covariance_recommends_stopping_to_localize(client):
    plan_payload = _plan(client)
    x0, y0 = _corridor_start_xy(plan_payload)

    response = client.post(
        "/api/pose",
        json={"pose": _pose_body(x0, y0, covariance_m=500.0)},
    )

    payload = response.json()
    fired = {t["trigger_id"] for t in payload["fired_triggers"]}
    assert "localization_uncertainty" in fired
    # Replanning from an untrusted pose plans from a lie; the endpoint
    # must say so rather than recommending a replan.
    assert payload["recommended_action"] == "stop_and_localize"


def test_slip_fires_when_progress_lags_the_odometers_claim(client):
    plan_payload = _plan(client)
    x0, y0 = _corridor_start_xy(plan_payload)

    # Standing at the route start while claiming 400 m of wheel travel:
    # along-track progress is ~0 of 400 claimed.
    response = client.post(
        "/api/pose",
        json={"pose": _pose_body(x0, y0, distance_travelled_m=400.0)},
    )

    payload = response.json()
    fired = {t["trigger_id"] for t in payload["fired_triggers"]}
    assert "slip_accumulation" in fired
    assert "slip_accumulation" in payload["evaluated"]


def test_an_absolute_fix_is_not_slip_checked(client):
    plan_payload = _plan(client)
    x0, y0 = _corridor_start_xy(plan_payload)

    response = client.post(
        "/api/pose",
        json={
            "pose": _pose_body(
                x0, y0, source="skyline_fix", distance_travelled_m=400.0
            )
        },
    )

    payload = response.json()
    assert "slip_accumulation" not in payload["evaluated"]
    assert {t["trigger_id"] for t in payload["fired_triggers"]} == set()


def test_extra_plan_state_reaches_the_other_triggers(client):
    plan_payload = _plan(client)
    x0, y0 = _corridor_start_xy(plan_payload)

    response = client.post(
        "/api/pose",
        json={
            "pose": _pose_body(x0, y0),
            "state": {"actual_soc": 0.3, "planned_soc": 0.8},
        },
    )

    payload = response.json()
    fired = {t["trigger_id"] for t in payload["fired_triggers"]}
    assert "soc_deviation" in fired
    assert payload["recommended_action"] == "replan"


def test_an_invalid_pose_is_rejected_with_422(client):
    _plan(client)
    response = client.post(
        "/api/pose",
        json={"pose": _pose_body(0.0, 0.0, source="magnetic_compass")},
    )
    assert response.status_code == 422


def test_the_closed_loop_pose_to_replan(client):
    """The acceptance criterion itself: /api/pose's trigger_state feeds
    /api/replan unchanged, and the replan actually happens."""
    plan_payload = _plan(client)
    x0, y0 = _corridor_start_xy(plan_payload)
    half_width = plan_payload["corridor"]["half_width_m"][0]

    pose_response = client.post(
        "/api/pose",
        json={"pose": _pose_body(x0, y0 + half_width + 50.0)},
    )
    pose_payload = pose_response.json()
    assert pose_payload["recommended_action"] == "replan"

    replan_response = client.post(
        "/api/replan",
        json={
            "current": {"row": 5, "col": 5},
            "goal": {"row": 2, "col": 25},
            "state": pose_payload["trigger_state"],
        },
    )

    assert replan_response.status_code == 200, replan_response.text
    replan_payload = replan_response.json()
    assert replan_payload["replanned"] is True
    fired = {t["trigger_id"] for t in replan_payload["triggers"]}
    assert "corridor_violation" in fired
    assert replan_payload["plan"]["status"] == "success"


def test_a_new_plan_replaces_the_active_corridor(client):
    first = _plan(client)
    response = client.post(
        "/api/plan",
        json={"start": {"row": 25, "col": 2}, "goal": {"row": 25, "col": 25}},
    )
    assert response.status_code == 200
    second = response.json()
    assert second["corridor"]["waypoints"][0] != first["corridor"]["waypoints"][0]

    # A pose at the SECOND route's start must be inside now.
    x0, y0 = _corridor_start_xy(second)
    payload = client.post("/api/pose", json={"pose": _pose_body(x0, y0)}).json()
    assert payload["corridor_fix"]["inside"] is True
