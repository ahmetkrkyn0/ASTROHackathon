"""The recovery policy on the wire (B1), kernel-free.

A 16 x 16 synthetic grid at coarsen 4 (the /api/plan-4d fixture); no horizon
cube, so every shadow series is static and the field says so. What is
pinned: the request fields and their bounds, the ``survival`` block in both
its shapes, beta refusing a route, the cell card, the replan suggestion and
the ``/api/survival`` layer in JSON and binary.
"""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import survival as S
from app.constants import get_rover
from app.main import app

SHAPE = (16, 16)
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
    S.clear_survival_cache()
    yield _client
    app.state.grids = None
    S.clear_survival_cache()


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


# ── /api/plan-4d ─────────────────────────────────────────────────────────────


def test_plan_4d_without_survival_says_not_requested(client):
    response = client.post("/api/plan-4d", json=_body())
    assert response.status_code == 200, response.text
    payload = response.json()
    block = payload["survival"]
    assert block["requested"] is False and block["applied"] is False
    assert block["validity"] == "MODEL" and block["model"] == S.SURVIVAL_MODEL_ID
    assert payload["path_survival_prob"] is None and payload["path_recovery_prob"] is None
    assert payload["metrics"]["execution_failure_probability"] is None


def test_plan_4d_reports_survival_when_asked(client):
    response = client.post("/api/plan-4d", json=_body(report_survival=True))
    assert response.status_code == 200, response.text
    payload = response.json()
    block = payload["survival"]
    assert block["requested"] is True and block["applied"] is False and block["beta"] is None
    assert block["failure_model"]["rate_per_km"] == 0.2 and block["failure_model"]["recovery_h"] == 10.0
    assert block["failure_model"]["source"].startswith("assumption:")
    assert block["safe_set"] == "leg" and block["field"]["n_states"] > 0
    assert block["field"]["n_states"] <= S.MAX_SURVIVAL_STATES
    assert block["shadow_model"]["model"] == "static"
    assert block["haven_model"]["model"] == "unavailable"
    assert len(payload["path_survival_prob"]) == len(payload["path_states"])
    assert len(payload["path_recovery_prob"]) == len(payload["path_states"])
    route = block["route"]
    assert 0.0 <= route["execution_failure_probability"] <= 1.0
    assert route["execution_failure_probability"] == payload["metrics"]["execution_failure_probability"]
    assert 0.0 <= route["min_recovery_prob"] <= 1.0 and route["moves_refused"] == 0
    assert "claim" in block and block["references"][0]["id"] == "lamarre_acta_2023"
    # The plan itself is the unconstrained one.
    plain = client.post("/api/plan-4d", json=_body()).json()
    assert plain["path_states"] == payload["path_states"]


def test_plan_4d_enforces_beta(client):
    ok = client.post("/api/plan-4d", json=_body(max_failure_probability=0.5))
    assert ok.status_code == 200, ok.text
    block = ok.json()["survival"]
    assert block["applied"] is True and block["beta"] == 0.5
    assert ok.json()["metrics"]["execution_failure_probability"] <= 0.5
    assert ok.json()["metrics"]["survival_enforced"] is True
    tight = client.post(
        "/api/plan-4d", json=_body(max_failure_probability=1e-9, failure_rate_per_km=5.0)
    )
    assert tight.status_code == 404, tight.text
    detail = tight.json()["detail"]
    assert "max_failure_probability" in detail and "Chance constraint" in detail


def test_plan_4d_without_faults_is_deterministic_and_binds_nowhere(client):
    response = client.post(
        "/api/plan-4d", json=_body(max_failure_probability=0.01, failure_rate_per_km=0.0)
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["metrics"]["execution_failure_probability"] == 0.0
    assert all(value == 1.0 for value in payload["path_recovery_prob"])
    assert payload["survival"]["route"]["moves_refused"] == 0


def test_plan_4d_honours_the_survival_options(client):
    response = client.post(
        "/api/plan-4d",
        json=_body(
            report_survival=True,
            survival_soc_bins=10,
            survival_horizon_hours=30.0,
            recovery_hours=2.0,
            failure_rate_per_km=1.0,
            survival_safe_set="leg",
        ),
    )
    assert response.status_code == 200, response.text
    field = response.json()["survival"]["field"]
    assert field["n_soc_bins"] == 10 and field["horizon_hours"] == pytest.approx(30.0, abs=field["step_hours"])
    assert response.json()["survival"]["failure_model"] == {
        **response.json()["survival"]["failure_model"],
        "rate_per_km": 1.0,
        "recovery_h": 2.0,
    }


def test_plan_4d_haven_set_without_a_haven_map_is_a_422(client):
    response = client.post("/api/plan-4d", json=_body(report_survival=True, survival_safe_set="haven"))
    assert response.status_code == 422, response.text
    assert "safe haven" in response.json()["detail"]


def test_plan_4d_validates_the_survival_fields(client):
    for bad in (
        {"max_failure_probability": 1.0},
        {"max_failure_probability": 0.0},
        {"survival_safe_set": "goal"},
        {"survival_horizon_hours": 500.0},
        {"survival_soc_bins": 4},
        {"survival_soc_bins": 100},
        {"failure_rate_per_km": -1.0},
        {"recovery_hours": 0.0},
    ):
        response = client.post("/api/plan-4d", json=_body(**bad))
        assert response.status_code == 422, (bad, response.text)


# ── /api/cell-telemetry ─────────────────────────────────────────────────────


def test_cell_telemetry_survival_block(client):
    plain = client.get("/api/cell-telemetry", params={"row": 2, "col": 2})
    assert plain.status_code == 200 and plain.json()["survival"] is None
    assert plain.json()["survival_model"]["model"] == "unavailable"
    response = client.get(
        "/api/cell-telemetry",
        params={
            "row": 2, "col": 2, "start_utc": "2026-09-01T00:00:00", "survival": "true",
            "goal_row": 13, "goal_col": 13, "soc_pct": 0.8, "t_hours": 0.0,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    block = payload["survival"]
    assert 0.0 <= block["p_safe"] <= 1.0
    assert block["best_action_name"] in S.ACTION_NAMES + ("safe", "none")
    assert block["soc_frac"] == 0.8 and block["safe_set"] == "leg" and block["block"] == [0, 0]
    assert payload["survival_model"]["model"] == S.SURVIVAL_MODEL_ID
    assert payload["survival_model"]["validity"] == "MODEL"
    assert payload["safe_haven"] is None  # A1 still needs the horizon cube


def test_cell_telemetry_survival_needs_a_goal_for_the_leg_set(client):
    response = client.get(
        "/api/cell-telemetry",
        params={"row": 2, "col": 2, "start_utc": "2026-09-01T00:00:00", "survival": "true"},
    )
    assert response.status_code == 422, response.text


# ── /api/replan ─────────────────────────────────────────────────────────────


def test_replan_recovery_suggestion(client):
    body = {
        "current": {"row": 2, "col": 2},
        "goal": {"row": 13, "col": 13},
        "state": {"actual_soc": 0.9},
        "force": True,
        "utc": "2026-09-01T00:00:00",
        "recovery_policy": True,
    }
    response = client.post("/api/replan", json=body)
    assert response.status_code == 200, response.text
    payload = response.json()
    suggestion = payload["recovery_suggestion"]
    assert suggestion["action_name"] and suggestion["soc_frac"] == 0.9
    assert suggestion["validity"] == "MODEL" and suggestion["failure_model"]["source"].startswith("assumption:")
    assert suggestion["block"] == [0, 0]
    assert payload["replanned"] is True and payload["plan"]["geojson"]["geometry"]["coordinates"]
    body.pop("recovery_policy")
    assert client.post("/api/replan", json=body).json()["recovery_suggestion"] is None
    body["recovery_policy"] = True
    body.pop("utc")
    without_epoch = client.post("/api/replan", json=body).json()
    assert without_epoch["recovery_suggestion"] is None
    assert without_epoch["survival_model"]["model"] == "unavailable"


# ── GET /api/survival ───────────────────────────────────────────────────────


def test_survival_layer_json_and_binary(client):
    params = {"start_utc": "2026-09-01T00:00:00", "goal_row": 13, "goal_col": 13, "horizon_hours": 6.0}
    response = client.get("/api/survival", params=params)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["grid"]["rows"] == 4 and payload["grid"]["cols"] == 4 and payload["grid"]["coarsen"] == 4
    assert set(payload["fields"]) == {"p_safe", "best_action"}
    assert payload["survival_model"]["validity"] == "MODEL"
    assert payload["survival_model"]["shadow_model"]["model"] == "static"
    assert 0.0 <= payload["summary"]["mean_p_safe"] <= 1.0
    assert payload["summary"]["fraction_at_least_0_5"] >= payload["summary"]["fraction_at_least_0_95"]
    assert payload["fields"]["p_safe"]["binary_url"].startswith("/api/survival?")
    binary = client.get("/api/survival", params={**params, "format": "f32", "field": "p_safe"})
    assert binary.status_code == 200, binary.text
    assert binary.headers["X-Layer-Validity"] == "MODEL"
    assert len(binary.content) == 4 * 4 * 4
    values = np.frombuffer(binary.content, dtype="<f4").reshape(4, 4)
    assert np.nanmin(values) >= 0.0 and np.nanmax(values) <= 1.0
    codes = client.get("/api/survival", params={**params, "format": "f32", "field": "best_action"})
    assert codes.status_code == 200 and len(codes.content) == 4 * 4 * 4


def test_survival_layer_validation(client):
    assert client.get("/api/survival", params={"start_utc": "2026-09-01T00:00:00"}).status_code == 422
    assert client.get(
        "/api/survival",
        params={"start_utc": "2026-09-01T00:00:00", "goal_row": 13, "goal_col": 13, "horizon_hours": 500.0},
    ).status_code == 422
    assert client.get(
        "/api/survival",
        params={"start_utc": "2026-09-01T00:00:00", "goal_row": 13, "goal_col": 13, "safe_set": "haven"},
    ).status_code == 422  # no haven map without the horizon cube
    assert client.get(
        "/api/survival",
        params={"start_utc": "2026-09-01T00:00:00", "goal_row": 40, "goal_col": 40},
    ).status_code == 422
