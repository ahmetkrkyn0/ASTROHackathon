"""The thermal dwell (C6) on the checked-in production grid.

test_thermal_dwell.py pins the model on toy series; this file asks what it
says about Site11 with the real horizon cube and NAIF kernels, and skips
wherever the gitignored inputs are not on disk (mirrors
test_survival_real_grid.py). Pinned: the three standard 4-D routes are
unchanged without the constraint (41 / 116 / 8 moves, as every feature
since C3 has left them) and carry a consistent dwell block; the enforced
constraint answers 200 or a reasoned 404; the entrenchment countdown at
the lunar-night start; the coarse layer; the envelope cache, when built,
never shows a genuinely hot surface for LPR-1.
"""

from __future__ import annotations

import os
import pathlib

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import thermal_dwell as TD
from app.data_loader import _P1_PROCESSED_DIR, load_preprocessed_grids
from app.main import app

_KERNELS = pathlib.Path(__file__).resolve().parent.parent / "kernels" / "lunapath.tm"
_HORIZON = os.path.join(_P1_PROCESSED_DIR, "horizon_map.npy")
_METADATA = os.path.join(_P1_PROCESSED_DIR, "metadata.json")
_ENVELOPE = os.path.join(_P1_PROCESSED_DIR, TD.ENVELOPE_CACHE_FILENAME)

needs_real_inputs = pytest.mark.skipif(
    not (_KERNELS.exists() and os.path.exists(_HORIZON) and os.path.exists(_METADATA)),
    reason="NAIF kernels, horizon_map.npy or the processed grids are not on disk",
)
needs_envelope_cache = pytest.mark.skipif(
    not os.path.exists(_ENVELOPE),
    reason="thermal_envelope_heat1d.npz not on disk (run scripts/build_thermal_envelope_cache.py)",
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
def test_standard_routes_are_unchanged_and_carry_a_consistent_dwell_block(client):
    for body, moves in ((LPR1_DAY, 41), (NIGHT, 116), (VIPER_SHORT, 8)):
        response = client.post("/api/plan-4d", json=body)
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["metrics"]["move_steps"] == moves, (body, payload["metrics"])
        block = payload["thermal_dwell"]
        assert block["requested"] is False and block["applied"] is False
        assert block["dwell_model"]["model"] == TD.THERMAL_DWELL_MODEL_ID
        assert block["shadow_model"]["model"] == "spice_horizon"
        n = len(payload["path_states"])
        assert len(payload["path_inner_c"]) == n == len(payload["path_max_dwell_h"])
        assert payload["path_inner_c"][0] == 17.5
        assert payload["metrics"]["thermal_dwell_enforced"] is False
        cube = block["cube"]
        assert cube["traversable_blocks"] > 0
        assert 0.0 <= cube["fraction_unlimited"] <= 1.0
        assert abs(cube["fraction_unlimited"] + cube["fraction_cold_limited"] + cube["fraction_hot_limited"] - 1.0) < 1e-6
        r12 = next(e for e in payload["safety_margins"]["requirements"] if e["id"] == "LP-R12")
        assert r12["applicable"] is True


@needs_real_inputs
def test_day_route_dwell_fractions_agree_with_the_probe(client):
    # Probe of 5 Sep 2026 (spec): LPR-1's equilibrium inner temperature sits
    # in the envelope on 10-34 percent of the traversable cells depending on
    # the statistic; the cube at the first slice of the day epoch should land
    # in that neighbourhood, and the cold side dominates.
    payload = client.post("/api/plan-4d", json=LPR1_DAY).json()
    cube = payload["thermal_dwell"]["cube"]
    assert 0.02 <= cube["fraction_unlimited"] <= 0.6
    assert cube["fraction_cold_limited"] > cube["fraction_hot_limited"]
    assert cube["finite_median_h"] is not None and 0.1 <= cube["finite_median_h"] <= 6.0


@needs_real_inputs
def test_enforced_constraint_answers_200_or_a_reasoned_404(client):
    for body in (LPR1_DAY, NIGHT, VIPER_SHORT):
        response = client.post("/api/plan-4d", json={**body, "require_thermal_dwell": True})
        assert response.status_code in (200, 404), response.text
        if response.status_code == 200:
            payload = response.json()
            assert payload["thermal_dwell"]["applied"] is True
            assert payload["metrics"]["states_past_thermal_dwell"] == 0
            env = payload["thermal_dwell"]["envelope"]
            assert all(env["lo_c"] - 1e-6 <= v <= env["hi_c"] + 1e-6 for v in payload["path_inner_c"])
        else:
            detail = response.json()["detail"]
            assert "Thermal dwell:" in detail and "inner temperature" in detail


@needs_real_inputs
def test_entrenchment_countdown_at_the_lunar_night_start(client):
    body = {
        "current": NIGHT["start"],
        "goal": NIGHT["goal"],
        "rover_id": "lpr_1",
        "utc": NIGHT["start_utc"],
        "state": {"entrenched_hours": 0.1},
    }
    payload = client.post("/api/replan", json=body).json()
    block = payload["entrenchment"]
    assert block is not None and block["shadow_model"]["model"] == "spice_horizon"
    thermal = block["thermal"]
    assert thermal is not None and thermal["initial_inner_c"] == 17.5
    assert thermal["tolerable_h"] is None or thermal["tolerable_h"] > 0.0
    assert block["overall"]["level"] in ("ok", "warning", "critical", "fail")
    assert block["haven"] is None or "tolerable_h" in block["haven"]


@needs_real_inputs
def test_thermal_dwell_layer_on_the_coarse_grid(client):
    payload = client.get(
        "/api/thermal-dwell",
        params={"start_utc": LPR1_DAY["start_utc"], "rover_id": "lpr_1", "lookahead_hours": 6.0},
    ).json()
    assert payload["grid"]["rows"] == 125 and payload["grid"]["cols"] == 125
    assert payload["shadow_model"]["model"] == "spice_horizon"
    assert payload["summary"]["traversable_blocks"] > 10_000
    assert payload["fields"]["max_dwell_h"]["max"] <= 6.0 + 1e-6
    binary = client.get(
        "/api/thermal-dwell",
        params={"start_utc": LPR1_DAY["start_utc"], "lookahead_hours": 6.0, "format": "f32", "field": "side"},
    )
    values = np.frombuffer(binary.content, dtype="<f4")
    assert values.size == 125 * 125 and set(np.unique(values[np.isfinite(values)])) <= {0.0, 1.0, 2.0}


@needs_real_inputs
@needs_envelope_cache
def test_envelope_cache_has_no_genuinely_hot_surface_for_lpr1(client):
    payload = client.get("/api/thermal-envelope", params={"rover_id": "lpr_1"}).json()
    sampled = [c for c in payload["cells"] if c["verdict"] != "unsampled"]
    assert len(sampled) > 100
    assert max(c["surface_c_max"] for c in sampled) < 60.0
    # The 'hot-limited' bins are the offset model's -25..0 C band, never a
    # surface warm enough to reach the hot branch of the envelope.
    for cell in payload["cells"]:
        if cell["verdict"] == "hot_limited":
            assert cell["surface_c_max"] < 0.0
    assert payload["counts"]["unlimited"] > 0 and payload["meta"]["lat_deg"] < -88.0
