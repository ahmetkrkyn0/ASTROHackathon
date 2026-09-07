"""The recovery policy (B1) on the checked-in production grid.

test_survival.py pins the dynamic programme on toy grids; this file asks
what it says about Site11 with the real horizon cube and NAIF kernels, and
skips wherever the gitignored inputs are not on disk (mirrors
test_safe_haven_real_grid.py). Pinned: the three standard 4-D routes are
unchanged without a beta (41 / 116 / 8 moves, as every feature since C3
has left them); with a beta the execution risk is bounded and the field
stays under its state cap; the strict haven set is non-empty for NASA
VIPER in the lunar day of 30 May 2027 (A1: 862 coarse haven blocks).
"""

from __future__ import annotations

import os
import pathlib

import pytest
from fastapi.testclient import TestClient

from app import survival as S
from app.data_loader import _P1_PROCESSED_DIR, load_preprocessed_grids
from app.main import app

_KERNELS = pathlib.Path(__file__).resolve().parent.parent / "kernels" / "lunapath.tm"
_HORIZON = os.path.join(_P1_PROCESSED_DIR, "horizon_map.npy")
_METADATA = os.path.join(_P1_PROCESSED_DIR, "metadata.json")

needs_real_inputs = pytest.mark.skipif(
    not (_KERNELS.exists() and os.path.exists(_HORIZON) and os.path.exists(_METADATA)),
    reason="NAIF kernels, horizon_map.npy or the processed grids are not on disk",
)

LPR1_DAY = {
    "start": {"row": 358, "col": 494},
    "goal": {"row": 206, "col": 426},
    "rover_id": "lpr_1",
    "start_utc": "2026-09-28T00:00:00",
}
NIGHT = {
    "start": {"row": 186, "col": 34},
    "goal": {"row": 494, "col": 450},
    "rover_id": "lpr_1",
    "start_utc": "2026-09-13T00:00:00",
}
VIPER_SHORT = {
    "start": {"row": 358, "col": 494},
    "goal": {"row": 346, "col": 462},
    "rover_id": "nasa_viper",
    "start_utc": "2027-05-30T00:00:00",
}


@pytest.fixture(scope="module")
def grids():
    return load_preprocessed_grids()


@pytest.fixture()
def client(grids):
    previous = getattr(app.state, "grids", None)
    with TestClient(app) as test_client:
        app.state.grids = grids
        yield test_client
    app.state.grids = previous


@needs_real_inputs
def test_standard_routes_are_unchanged_without_beta(client):
    for body, moves in ((LPR1_DAY, 41), (NIGHT, 116), (VIPER_SHORT, 8)):
        response = client.post("/api/plan-4d", json=body)
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["metrics"]["move_steps"] == moves, (body, payload["metrics"])
        assert payload["survival"]["requested"] is False
        assert payload["path_survival_prob"] is None


@needs_real_inputs
def test_beta_bounds_the_execution_risk_on_the_day_route(client):
    plain = client.post("/api/plan-4d", json={**LPR1_DAY, "report_survival": True})
    assert plain.status_code == 200, plain.text
    block = plain.json()["survival"]
    assert block["requested"] and not block["applied"]
    assert block["field"]["n_states"] <= S.MAX_SURVIVAL_STATES
    assert block["shadow_model"]["model"] == "spice_horizon"
    assert 0.0 <= block["route"]["execution_failure_probability"] < 1.0
    # The unconstrained plan is the pre-B1 plan.
    assert plain.json()["metrics"]["move_steps"] == 41

    bounded = client.post("/api/plan-4d", json={**LPR1_DAY, "max_failure_probability": 0.05})
    assert bounded.status_code in (200, 404), bounded.text
    if bounded.status_code == 200:
        metrics = bounded.json()["metrics"]
        assert metrics["execution_failure_probability"] <= 0.05
        assert metrics["survival_enforced"] is True
        assert bounded.json()["survival"]["applied"] is True
    else:
        assert "Chance constraint" in bounded.json()["detail"]


@needs_real_inputs
def test_without_faults_the_field_is_deterministic_on_site11(client):
    response = client.post(
        "/api/plan-4d", json={**VIPER_SHORT, "max_failure_probability": 0.01, "failure_rate_per_km": 0.0}
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["metrics"]["move_steps"] == 8
    assert payload["metrics"]["execution_failure_probability"] == 0.0
    assert all(value == 1.0 for value in payload["path_recovery_prob"])


@needs_real_inputs
def test_viper_haven_set_has_positive_p_safe_in_may_2027(client):
    response = client.get(
        "/api/survival",
        params={
            "start_utc": "2027-05-30T00:00:00",
            "rover_id": "nasa_viper",
            "safe_set": "haven",
            "horizon_hours": 24.0,
            "soc_pct": 1.0,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["survival_model"]["safe_cells"] > 0
    assert payload["summary"]["fraction_at_least_0_5"] > 0.0
    assert payload["grid"]["rows"] == 125


@needs_real_inputs
def test_lpr1_haven_set_is_empty_on_site11(client):
    response = client.get(
        "/api/survival",
        params={"start_utc": "2026-09-28T00:00:00", "rover_id": "lpr_1", "safe_set": "haven", "horizon_hours": 6.0},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["survival_model"]["safe_cells"] == 0
    assert payload["summary"]["fraction_zero"] == 1.0
