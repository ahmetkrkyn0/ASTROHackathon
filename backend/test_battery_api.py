"""C2 over the API: the three request flags, the response block, the refusals
and ``GET /api/battery-model``.

These run on the synthetic fixture grid, so they pin the CONTRACT -- shapes,
defaults, reasons and the five 422s -- and never a route. Site11's numbers are
measured in test_battery_real_grid.py and in the research report.
"""

from __future__ import annotations

import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import battery as B
from app.constants import get_rover
from app.main import app

SHAPE = (16, 16)

# Built once so the startup handler runs and fails gracefully (no .npy files);
# grids are injected per-test afterwards, mirroring test_plan_4d_endpoint.py.
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


# ── the catalogue ───────────────────────────────────────────────────────────


def test_the_rover_catalogue_publishes_availability_and_the_promoted_tau(client):
    response = client.get("/api/rovers")
    assert response.status_code == 200
    entries = {entry["id"]: entry for entry in response.json()["rovers"]}

    assert entries["lpr_1"]["thermal_tau_s"] == 7200.0
    assert entries["luvmi_m"]["thermal_tau_s"] is None
    # Correcting the declared-only label must not delete the number.
    assert "thermal_tau_s" not in entries["lpr_1"]["declared_only"]

    block = entries["luvmi_m"]["battery_model"]
    assert block["cold_capacity"]["available"] is False
    assert "freeze point" in block["cold_capacity"]["reason"]
    assert block["hibernation"]["available"] is False
    assert block["hibernation"]["p_hibernate_w"] is None
    assert block["validity"] == "MODEL"

    lpr = entries["lpr_1"]["battery_model"]
    assert lpr["hibernation"]["dark_rate"] == pytest.approx(108.0 / 65.0)
    assert lpr["heater"]["available"] is True
    assert lpr["heater"]["source"].startswith("assumption:")


def test_the_whole_catalogue_still_serialises_without_nan(client):
    response = client.get("/api/rovers")
    json.dumps(response.json(), allow_nan=False)


# ── GET /api/battery-model ──────────────────────────────────────────────────


def test_the_endpoint_reports_the_curve_the_heater_and_the_claim_limit(client):
    response = client.get("/api/battery-model?rover_id=lpr_1")
    assert response.status_code == 200
    body = response.json()

    assert body["rover_id"] == "lpr_1"
    assert body["battery"]["validity"] == "MODEL"
    assert "85 percent" in body["battery"]["claim"]        # and why it is not used
    assert body["battery"]["jsc_survival_temperature_check"]["quoted_pct"] == 26.0

    curve = body["curve"]
    assert len(curve) == 11
    assert curve[0]["usable_fraction"] == 0.0
    assert curve[0]["inner_c"] == pytest.approx(B.BATTERY_FREEZE_C)
    assert curve[-1]["usable_fraction"] == 1.0
    assert curve[-1]["endurance_h"] == 50.0
    fractions = [row["usable_fraction"] for row in curve]
    assert fractions == sorted(fractions)

    heater = body["heater"]
    assert heater["available"] is True
    assert heater["set_point_c"] == 0.0
    assert heater["sizing_surface_c"] == -150.0
    rows = {row["surface_c"]: row for row in heater["by_surface"]}
    assert rows[-150.0]["delta_t_w"] == pytest.approx(25.0)
    assert rows[-150.0]["radiative_w"] == pytest.approx(25.0)
    assert rows[0.0]["delta_t_w"] == 0.0

    assert body["survival_envelope"]["lo_c"] == pytest.approx(B.BATTERY_FREEZE_C)
    assert body["state"]["shadow_endurance_h"] == 50.0


def test_the_endpoint_answers_for_a_profile_that_cannot_use_the_models(client):
    response = client.get("/api/battery-model?rover_id=luvmi_m")
    assert response.status_code == 200
    body = response.json()
    assert body["curve"] == []
    assert body["battery"]["catalogue"]["cold_capacity"]["available"] is False
    assert body["state"]["usable_fraction"] is None


def test_the_endpoint_takes_a_state_and_a_shape(client):
    warm = client.get("/api/battery-model?rover_id=lpr_1&inner_c=-20&soc_pct=100").json()
    assert warm["state"]["usable_fraction"] == pytest.approx(0.726589, abs=1e-6)
    assert warm["state"]["components_past_operating_limit"] == ["battery", "electronics"]

    convex = client.get(
        "/api/battery-model?rover_id=lpr_1&inner_c=-20&shape_exponent=2"
    ).json()
    assert convex["state"]["usable_fraction"] < warm["state"]["usable_fraction"]


def test_an_unknown_rover_is_a_422_not_a_500(client):
    assert client.get("/api/battery-model?rover_id=nope").status_code == 422


# ── the plan endpoints ──────────────────────────────────────────────────────


def test_the_default_plan_4d_carries_the_block_unapplied(client):
    response = client.post(
        "/api/plan-4d",
        json={"start": {"row": 0, "col": 0}, "goal": {"row": 12, "col": 12}, "coarsen": 4},
    )
    assert response.status_code == 200, response.text
    block = response.json()["battery"]
    assert block["applied"] is False
    assert block["requested"] == {
        "battery_model": "constant",
        "heater_power_model": "constant",
        "allow_hibernate": False,
    }
    assert block["catalogue"]["heater"]["available"] is True
    assert block["route"]["hibernate_steps"] == 0


def test_the_two_d_plan_says_why_a_temperature_model_cannot_apply_there(client):
    response = client.post(
        "/api/plan",
        json={"start": {"row": 0, "col": 0}, "goal": {"row": 12, "col": 12}},
    )
    assert response.status_code == 200, response.text
    block = response.json()["battery"]
    assert block["applied"] is False
    assert "no epoch" in block["reason"]
    assert "/api/plan-4d" in block["reason"]


def test_a_heater_power_model_without_the_thermostat_is_a_422(client):
    response = client.post(
        "/api/plan-4d",
        json={
            "start": {"row": 0, "col": 0},
            "goal": {"row": 12, "col": 12},
            "coarsen": 4,
            "heater_power_model": "radiative",
        },
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "thermostat_assumed" in detail
    assert "one device" in detail


def test_the_derating_is_a_422_for_a_profile_whose_anchors_contradict(client):
    response = client.post(
        "/api/plan-4d",
        json={
            "start": {"row": 0, "col": 0},
            "goal": {"row": 12, "col": 12},
            "coarsen": 4,
            "rover_id": "luvmi_m",
            "battery_model": "temperature_derated",
        },
    )
    assert response.status_code == 422
    assert "freeze point" in response.json()["detail"]


def test_hibernation_is_a_422_for_a_profile_that_declares_no_draw(client):
    response = client.post(
        "/api/plan-4d",
        json={
            "start": {"row": 0, "col": 0},
            "goal": {"row": 12, "col": 12},
            "coarsen": 4,
            "rover_id": "luvmi_m",
            "allow_hibernate": True,
        },
    )
    assert response.status_code == 422
    assert "p_hibernate_w" in response.json()["detail"]


def test_an_out_of_range_shape_exponent_is_refused_by_the_schema(client):
    for value in (0.0, -1.0, 99.0):
        response = client.post(
            "/api/plan-4d",
            json={
                "start": {"row": 0, "col": 0},
                "goal": {"row": 12, "col": 12},
                "coarsen": 4,
                "battery_shape_exponent": value,
            },
        )
        assert response.status_code == 422


def test_a_requested_model_that_applies_reports_applied_true(client):
    response = client.post(
        "/api/plan-4d",
        json={
            "start": {"row": 0, "col": 0},
            "goal": {"row": 12, "col": 12},
            "coarsen": 4,
            "heater_model": "thermostat_assumed",
            "heater_power_model": "radiative",
        },
    )
    assert response.status_code == 200, response.text
    block = response.json()["battery"]
    assert block["applied"] is True
    assert block["requested"]["heater_power_model"] == "radiative"


def test_the_route_block_names_the_limitation_it_does_not_cover(client):
    """SHERPA's margins are computed on nameplate charge at constant
    housekeeping power, so under a derated battery they are not the planner's
    own numbers. Said in the response rather than left to be discovered."""
    response = client.post(
        "/api/plan-4d",
        json={"start": {"row": 0, "col": 0}, "goal": {"row": 12, "col": 12}, "coarsen": 4},
    )
    assert response.json()["battery"]["route"]["margins_use_nameplate_charge"] is True


def test_every_plan_4d_response_still_serialises_without_nan(client):
    response = client.post(
        "/api/plan-4d",
        json={
            "start": {"row": 0, "col": 0},
            "goal": {"row": 12, "col": 12},
            "coarsen": 4,
            "heater_model": "thermostat_assumed",
            "heater_power_model": "delta_t",
        },
    )
    assert response.status_code == 200, response.text
    json.dumps(response.json(), allow_nan=False)
