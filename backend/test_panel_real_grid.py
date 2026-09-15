"""The panel incidence model (C1) on the checked-in production grid.

test_panel.py pins the geometry on synthetic tracks; this file asks what it
says about Site11 with the real horizon cube and NAIF kernels, and skips
wherever the gitignored inputs are not on disk (mirrors
test_survival_real_grid.py). Pinned: the default panel model leaves the
standard 4-D routes exactly where every feature since C3 left them; the
cos i model is accepted and reports a gain consistent with the site's
geometry; the gain at a lunar-night epoch is zero and therefore changes
nothing; the counterfactual ratio the research note guessed at "~30x" is
measured here, with the window it belongs to.
"""

from __future__ import annotations

import math
import os
import pathlib

import pytest
from fastapi.testclient import TestClient

from app import panel as P
from app.constants import get_rover
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
def test_the_standard_routes_are_unchanged_under_the_default_panel_model(client):
    """The bit-equality lock: 41 / 116 moves, exactly where C3 through C6
    left them, with the panel block reported but not applied."""
    for body, moves in ((LPR1_DAY, 41), (NIGHT, 116)):
        response = client.post("/api/plan-4d", json=body)
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["metrics"]["move_steps"] == moves, (body, payload["metrics"])
        block = payload["panel"]
        assert block["applied"] is False
        assert block["model"] == "sun_pointed"
        assert block["requested"] == "sun_pointed"
        assert block["gain_series"] is None
        assert block["geometry"]["n_faces"] == 3
        assert block["geometry"]["source"].startswith("assumption:")


@needs_real_inputs
def test_the_cos_i_model_is_accepted_and_reports_a_gain_the_site_geometry_explains(
    client,
):
    response = client.post("/api/plan-4d", json={**LPR1_DAY, "panel_model": "cos_incidence"})
    assert response.status_code == 200, response.text
    payload = response.json()
    block = payload["panel"]
    assert block["applied"] is True and block["model"] == "cos_incidence"
    gain = block["gain"]
    assert gain["n_slices"] == len(block["gain_series"])
    # LPR-1's assumed array is three vertical body faces with the rover free
    # to turn, so at a 1.5-2 deg Sun it loses only the elevation cosine.
    assert 0.995 < gain["min"] <= gain["mean"] <= gain["max"] <= 1.0
    elevation = block["sun_elevation_deg"]
    assert 1.0 < elevation["min"] <= elevation["max"] < 2.5
    # The route itself does not move: the loss is under a percent.
    assert payload["metrics"]["move_steps"] == 41


@needs_real_inputs
def test_the_counterfactual_ratio_the_research_note_guessed_at(client):
    """The note said "~30x" between a vertical and a horizontal panel. It is
    not one number: it depends on the window. Measured here for the day
    route's own epoch."""
    response = client.get(
        "/api/panel-gain",
        params={
            "start_utc": "2026-09-28T00:00:00",
            "rover_id": "lpr_1",
            "n_slices": 48,
            "slice_hours": 0.5,
        },
    )
    assert response.status_code == 200, response.text
    counterfactuals = response.json()["panel"]["counterfactuals"]
    tracking = counterfactuals["polar_tracking"]["mean_when_sun_up"]
    horizontal = counterfactuals["horizontal"]["mean_when_sun_up"]
    assert 0.98 < tracking < 1.0
    # sin(1.6 deg) is about 0.028: a flat plate at this site collects a few
    # percent of its rating, whatever its rating is.
    assert 0.02 < horizontal < 0.04
    assert 25.0 < tracking / horizontal < 40.0
    assert counterfactuals["sun_pointed"]["mean"] == pytest.approx(1.0, abs=1e-12)
    assert (
        counterfactuals["body_three_face"]["mean"]
        > counterfactuals["polar_tracking"]["mean"]
    )


@needs_real_inputs
def test_at_a_lunar_night_epoch_the_gain_is_zero_and_changes_nothing(client):
    """A consistency check worth having: where there is no sunlight there is
    nothing to mis-point at, so cos i must leave the plan alone."""
    base = client.post("/api/plan-4d", json=NIGHT).json()
    gained = client.post(
        "/api/plan-4d", json={**NIGHT, "panel_model": "cos_incidence"}
    ).json()
    block = gained["panel"]
    assert block["applied"] is True
    assert block["sun_elevation_deg"]["max"] < 0.0
    assert max(block["gain_series"]) == 0.0
    assert gained["path_states"] == base["path_states"]
    assert gained["metrics"]["total_cost"] == base["metrics"]["total_cost"]
    assert gained["path_battery_pct"] == base["path_battery_pct"]


@needs_real_inputs
def test_the_viper_profile_behaves_identically_under_both_panel_models(client):
    """VIPER's own answer on this pair is whatever the corrected catalogue
    (4af6989: slope_max_deg 20 -> 15) makes it -- C1 only has to not change
    it. Asserting the two runs agree is the contract; asserting a move count
    would be asserting someone else's feature."""
    plain = client.post("/api/plan-4d", json=VIPER_SHORT)
    gained = client.post("/api/plan-4d", json={**VIPER_SHORT, "panel_model": "cos_incidence"})
    assert plain.status_code == gained.status_code
    if plain.status_code == 200:
        assert (
            gained.json()["metrics"]["move_steps"]
            == plain.json()["metrics"]["move_steps"]
        )
    else:
        assert gained.json()["detail"] == plain.json()["detail"]


@needs_real_inputs
def test_every_catalogued_rover_has_a_buildable_gain_at_this_site(client):
    for rover_id in ("lpr_1", "luvmi_m", "nasa_viper", "cnsa_yutu_2"):
        response = client.get(
            "/api/panel-gain",
            params={
                "start_utc": "2026-09-28T00:00:00",
                "rover_id": rover_id,
                "n_slices": 24,
                "slice_hours": 1.0,
            },
        )
        assert response.status_code == 200, (rover_id, response.text)
        block = response.json()["panel"]
        assert block["applied"] is True
        assert 0.98 < block["gain"]["mean"] <= 1.0, rover_id
        assert block["geometry"]["source"].startswith("assumption:")


@needs_real_inputs
def test_the_stress_test_prices_its_runs_at_the_same_gain_the_plan_used(client):
    """B5 re-simulates the plan on a continuous clock over a horizon LONGER
    than the plan's, so it builds its own gain series. Without this the stress
    test would be optimistic about exactly the income the plan discounted."""
    plan = client.post(
        "/api/plan-4d", json={**LPR1_DAY, "panel_model": "cos_incidence"}
    ).json()
    body = {
        "path_states": plan["path_states"],
        "rover_id": "lpr_1",
        "slice_hours": plan["slice_hours"],
        "start_utc": LPR1_DAY["start_utc"],
        "n_runs": 50,
        "coarsen": 4,
    }
    gained = client.post("/api/stress-test", json={**body, "panel_model": "cos_incidence"})
    assert gained.status_code == 200, gained.text
    block = gained.json()["sky_model"]["panel_model"]
    assert block["applied"] is True
    assert 0.0 <= block["min"] <= block["mean"] <= block["max"] <= 1.0
    # Its own slices, not the plan's: the stress test runs past the horizon.
    assert block["n_slices"] >= len(plan["panel"]["gain_series"])
    plain = client.post("/api/stress-test", json=body)
    assert plain.status_code == 200, plain.text
    assert plain.json()["sky_model"]["panel_model"]["applied"] is False


@needs_real_inputs
def test_the_site_latitude_lands_on_roverdevkits_polar_tilt_cap(grids):
    from app.illumination_series import _window_centre_latlon

    lat, _lon = _window_centre_latlon(grids["metadata"])
    assert lat == pytest.approx(-88.9205, abs=1e-3)
    assert P.polar_tilt_deg(lat) == 80.0
    # And the catalogue's polar-plate profiles were given that very number.
    assert get_rover("luvmi_m")["panel_tilt_deg"] == 80.0
    assert get_rover("cnsa_yutu_2")["panel_tilt_deg"] == 80.0


@needs_real_inputs
def test_the_corner_cross_check_is_stable_against_nasas_published_pair():
    check = P.viper_corner_check()
    assert check["model_ratio"] == pytest.approx(math.sqrt(2.0), abs=1e-9)
    assert check["predicted_on_corner_w"] == pytest.approx(452.5, abs=0.1)
    assert abs(check["difference_pct"]) < 1.0
