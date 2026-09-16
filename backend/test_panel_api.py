"""The panel incidence model (C1) on the wire, kernel-free.

The same 16 x 16 synthetic grid the other API suites use, at coarsen 4. It
has no horizon cube and no NAIF kernels, so no Sun track can be built here:
that is deliberate, because it pins the degraded contract -- every response
still carries the ``panel`` block, the block says why it is not applied, and
asking for ``panel_model="cos_incidence"`` is a reasoned 422 rather than a
silently ungained plan. What the model SAYS with a real Sun track is pinned
in test_panel.py (synthetically) and test_panel_real_grid.py (on Site11).
"""

from __future__ import annotations

import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import panel as P
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
        "thermal": np.full(SHAPE, -100.0),
        # /api/illumination-series animates the surface temperature and needs
        # the annual-peak layer the pipeline writes beside `thermal`.
        "thermal_sunlit_peak": np.full(SHAPE, -100.0),
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


# ── /api/plan-4d ────────────────────────────────────────────────────────────


def test_plan_4d_reports_the_panel_block_by_default(client):
    response = client.post("/api/plan-4d", json=_body())
    assert response.status_code == 200, response.text
    block = response.json()["panel"]
    assert block["requested"] == "sun_pointed"
    assert block["applied"] is False
    assert block["model"] == "sun_pointed"
    assert block["validity"] == "MODEL"
    assert block["model_id"] == P.PANEL_MODEL_ID
    # The geometry is published even when it steers nothing.
    assert block["geometry"]["n_faces"] == 3
    assert block["geometry"]["source"].startswith("assumption:")
    assert block["gain"]["n_slices"] == 0
    assert block["viper_corner_check"]["published_on_corner_w"] == 450.0


def test_plan_4d_refuses_cos_incidence_without_an_epoch(client):
    response = client.post("/api/plan-4d", json=_body(panel_model="cos_incidence"))
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "cos_incidence" in detail and "start_utc" in detail


def test_plan_4d_refuses_cos_incidence_when_no_sun_track_can_be_built(client):
    # An epoch but no kernels: the Sun track raises and the request is a 422
    # naming the cause, not a plan that silently ran at gain 1.
    response = client.post(
        "/api/plan-4d",
        json=_body(panel_model="cos_incidence", start_utc="2026-09-28T00:00:00"),
    )
    assert response.status_code == 422
    assert "Sun track" in response.json()["detail"]


def test_plan_4d_rejects_an_unknown_panel_model(client):
    response = client.post("/api/plan-4d", json=_body(panel_model="tilted"))
    assert response.status_code == 422


def test_the_default_plan_carries_every_pre_c1_field_unchanged(client):
    """"## Değişmeyenler" in the frontend contract only stays true if this
    does: the default response's existing keys must not move."""
    payload = client.post("/api/plan-4d", json=_body()).json()
    for key in (
        "path_states",
        "path_pixels",
        "metrics",
        "shadow_model",
        "earth_model",
        "safe_haven_model",
        "path_battery_pct",
        "path_dark_hours",
    ):
        assert key in payload
    assert payload["metrics"]["move_steps"] >= 1


# ── /api/plan (2-D) ─────────────────────────────────────────────────────────


def test_plan_2d_reports_the_block_and_says_why_it_can_never_apply(client):
    response = client.post(
        "/api/plan", json={"start": {"row": 0, "col": 0}, "goal": {"row": 12, "col": 12}}
    )
    assert response.status_code == 200, response.text
    block = response.json()["panel"]
    assert block["applied"] is False
    assert "no epoch" in block["reason"]
    assert "/api/plan-4d" in block["reason"]


# ── /api/panel-gain ─────────────────────────────────────────────────────────


def test_panel_gain_needs_an_epoch(client):
    response = client.get("/api/panel-gain")
    assert response.status_code == 422
    assert "start_utc" in response.json()["detail"]


def test_panel_gain_rejects_an_unknown_rover(client):
    response = client.get(
        "/api/panel-gain",
        params={"start_utc": "2026-09-28T00:00:00", "rover_id": "no_such_rover"},
    )
    assert response.status_code == 422


def test_panel_gain_reports_the_missing_sun_track_rather_than_guessing(client):
    response = client.get(
        "/api/panel-gain", params={"start_utc": "2026-09-28T00:00:00"}
    )
    assert response.status_code == 422
    assert "Sun track" in response.json()["detail"]


def test_panel_gain_bounds_its_query_parameters(client):
    base = {"start_utc": "2026-09-28T00:00:00"}
    assert client.get("/api/panel-gain", params={**base, "n_slices": 1}).status_code == 422
    assert client.get("/api/panel-gain", params={**base, "slice_hours": 0}).status_code == 422
    assert client.get("/api/panel-gain", params={**base, "slice_hours": 25}).status_code == 422


# ── /api/illumination-series ────────────────────────────────────────────────


def test_illumination_series_carries_the_panel_block_without_an_epoch(client):
    response = client.get("/api/illumination-series", params={"n_slices": 4})
    assert response.status_code == 200, response.text
    block = response.json()["panel"]
    assert block["applied"] is False
    assert "no Sun track" in block["reason"]


def test_illumination_series_names_whose_panel_it_is_describing(client):
    """The block used to publish the default profile's geometry with nothing
    in the response saying so, and a caller planning with another rover read
    it as its own."""
    for rover_id in ("lpr_1", "cnsa_yutu_2"):
        payload = client.get(
            "/api/illumination-series", params={"n_slices": 4, "rover_id": rover_id}
        ).json()
        assert payload["panel"]["rover_id"] == rover_id
    # lpr_1 is three body faces, cnsa_yutu_2 one polar plate: different blocks.
    lpr = client.get("/api/illumination-series", params={"n_slices": 4, "rover_id": "lpr_1"}).json()
    yutu = client.get(
        "/api/illumination-series", params={"n_slices": 4, "rover_id": "cnsa_yutu_2"}
    ).json()
    assert lpr["panel"]["geometry"]["n_faces"] == 3
    assert yutu["panel"]["geometry"]["n_faces"] == 1
    assert client.get(
        "/api/illumination-series", params={"n_slices": 4, "rover_id": "nope"}
    ).status_code == 422


def test_requested_is_a_property_of_the_request_not_of_the_outcome(client):
    """`applied = bool(requested and artefact is not None)` only means
    anything if `requested` says what the CALLER asked for. It used to be set
    from whether the gain happened to build, which inverts the rule."""
    default = client.get("/api/illumination-series", params={"n_slices": 4}).json()["panel"]
    assert default["requested"] == "sun_pointed"
    assert default["applied"] is False
    asked = client.get(
        "/api/illumination-series", params={"n_slices": 4, "panel_model": "cos_incidence"}
    ).json()["panel"]
    assert asked["requested"] == "cos_incidence"
    # Still not applied here: this fixture has no kernels, and the block says so.
    assert asked["applied"] is False
    assert asked["reason"]


# ── /api/stress-test ────────────────────────────────────────────────────────


def test_stress_test_reports_the_panel_model_and_refuses_to_pretend(client):
    """A static sky is a long-run shadow fraction. Pairing it with an
    instantaneous cos i is the incoherence /api/plan refuses, so the run says
    so rather than quietly applying a gain it cannot justify."""
    plan = client.post("/api/plan-4d", json=_body()).json()
    body = {
        "path_states": plan["path_states"],
        "slice_hours": plan["slice_hours"],
        "n_runs": 20,
        "coarsen": 4,
    }
    response = client.post("/api/stress-test", json={**body, "panel_model": "cos_incidence"})
    assert response.status_code == 200, response.text
    block = response.json()["sky_model"]["panel_model"]
    assert block["applied"] is False
    assert block["requested"] == "cos_incidence"
    assert "long-run shadow fraction" in block["reason"]
    # And the default says the same thing about itself.
    plain = client.post("/api/stress-test", json=body).json()
    assert plain["sky_model"]["panel_model"]["requested"] == "sun_pointed"


def test_stress_test_rejects_an_unknown_panel_model(client):
    plan = client.post("/api/plan-4d", json=_body()).json()
    response = client.post(
        "/api/stress-test",
        json={
            "path_states": plan["path_states"],
            "slice_hours": plan["slice_hours"],
            "panel_model": "sideways",
        },
    )
    assert response.status_code == 422


# ── /api/rovers ─────────────────────────────────────────────────────────────


def test_the_rover_catalogue_publishes_the_assumed_panel_geometry(client):
    response = client.get("/api/rovers")
    assert response.status_code == 200, response.text
    rovers = response.json()["rovers"]
    assert rovers
    for entry in rovers:
        block = entry["panel_model"]
        assert block["declared"] is True
        assert block["validity"] == "MODEL"
        assert block["source"].startswith("assumption:")
        assert block["reference_raw"] > 0.0
    json.dumps(rovers, allow_nan=False)
