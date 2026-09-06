"""The thermal dwell (C6) on the wire, kernel-free.

A 16 x 16 synthetic grid at coarsen 4 (the /api/plan-4d fixture) whose
sunlit peak is -100 C everywhere under a long-run shadow ratio of 0.3,
which the regolith model couples to a -113.5 C equilibrium: for LPR-1 that
is an inner target of -53.5 C, so every block is cold-limited and the
envelope is left after 0.566 h (``_fixture_dwell_h``) -- shorter than the
fixture's 1 h slice, which makes the enforced constraint's refusal
deterministic. No horizon cube, so every shadow
series is static and the blocks say so. What is pinned: the request fields
and their bounds, the ``thermal_dwell`` block in both shapes, the
per-state lists, LP-R12 in ``safety_margins``, the enforced constraint's
404 and the thermostat assumption's 200, the cell card, the replan
countdown's levels and trigger, the coarse layer in JSON and binary, and
the envelope endpoint with and without its cache.
"""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import thermal_dwell as TD
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


def _fixture_dwell_h() -> float:
    """The dwell the fixture implies, from the model itself: the static
    series holds every block at its long-run equilibrium."""
    from app.thermal_model import shadowed_equilibrium_c

    rover = get_rover("lpr_1")
    surface = float(shadowed_equilibrium_c(np.array([-100.0]), np.array([0.3]))[0])
    hours, _side, _comp = TD.exit_time_h(
        np.array([17.5]), TD.inner_target_c(np.array([surface]), rover), TD.rover_envelope(rover), 7200.0
    )
    return float(hours[0])


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


def test_plan_4d_reports_thermal_dwell_by_default(client):
    response = client.post("/api/plan-4d", json=_body())
    assert response.status_code == 200, response.text
    payload = response.json()
    block = payload["thermal_dwell"]
    assert block["requested"] is False and block["applied"] is False
    assert block["validity"] == "MODEL" and block["thermal_lag_validity"] == "UNCALIBRATED"
    assert block["dwell_model"]["model"] == TD.THERMAL_DWELL_MODEL_ID and block["heater_model"] == "none"
    assert block["initial_inner_c"] == 17.5 and block["envelope"]["lo_c"] == 0.0
    assert block["cube"]["fraction_cold_limited"] == 1.0 and block["cube"]["finite_median_h"] == pytest.approx(_fixture_dwell_h(), abs=0.001)
    assert block["route"]["inner"]["states_outside"] >= 1 and block["route"]["inner"]["side"] == "cold"
    assert block["shadow_model"]["model"] == "static"
    n = len(payload["path_states"])
    assert len(payload["path_max_dwell_h"]) == n == len(payload["path_inner_c"]) == len(payload["path_dwell_margin_h"])
    assert len(payload["path_stay_hours"]) == n and payload["path_inner_c"][0] == 17.5
    assert payload["metrics"]["thermal_dwell_enforced"] is False
    assert payload["metrics"]["edges_rejected"]["thermal_dwell"] == 0
    r12 = next(e for e in payload["safety_margins"]["requirements"] if e["id"] == "LP-R12")
    assert r12["applicable"] is True
    assert block["quoted"]["case_matrix"] == 96 and block["claim"].startswith("MODEL")


def test_plan_4d_require_thermal_dwell_refuses_the_cold_fixture(client):
    response = client.post("/api/plan-4d", json=_body(require_thermal_dwell=True))
    assert response.status_code == 404, response.text
    detail = response.json()["detail"]
    assert "inner temperature" in detail and "require_thermal_dwell" in detail
    assert "Thermal dwell:" in detail


def test_plan_4d_thermostat_assumption_lets_the_cold_fixture_through(client):
    response = client.post(
        "/api/plan-4d", json=_body(require_thermal_dwell=True, heater_model="thermostat_assumed")
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    block = payload["thermal_dwell"]
    assert block["applied"] is True and block["heater_model"] == "thermostat_assumed"
    assert block["heater_source"].startswith("assumption:")
    assert block["cube"]["fraction_unlimited"] == 1.0
    assert payload["metrics"]["states_past_thermal_dwell"] == 0 and payload["metrics"]["thermal_dwell_enforced"] is True
    assert block["route"]["inner"]["states_outside"] == 0


def test_plan_4d_initial_inner_is_echoed_and_bounded(client):
    payload = client.post("/api/plan-4d", json=_body(initial_inner_c=5.0)).json()
    assert payload["thermal_dwell"]["initial_inner_c"] == 5.0 and payload["path_inner_c"][0] == 5.0
    assert client.post("/api/plan-4d", json=_body(initial_inner_c=500.0)).status_code == 422
    assert client.post("/api/plan-4d", json=_body(heater_model="magic")).status_code == 422


def test_plan_4d_rover_without_tau_reports_unavailable_and_refuses_the_constraint(client):
    payload = client.post("/api/plan-4d", json=_body(rover_id="luvmi_m")).json()
    block = payload["thermal_dwell"]
    assert block["dwell_model"]["model"] == "unavailable" and "thermal_tau_s" in block["dwell_model"]["reason"]
    assert payload["path_max_dwell_h"] is None and payload["path_inner_c"] is None and block["cube"] is None
    response = client.post("/api/plan-4d", json=_body(rover_id="luvmi_m", require_thermal_dwell=True))
    assert response.status_code == 422 and "thermal_tau_s" in response.json()["detail"]


# ── /api/cell-telemetry ──────────────────────────────────────────────────────


def test_cell_telemetry_thermal_dwell_card(client):
    off = client.get("/api/cell-telemetry", params={"row": 3, "col": 3}).json()
    assert off["thermal_dwell"] is None and "not requested" in off["thermal_dwell_model"]["reason"]
    on = client.get(
        "/api/cell-telemetry",
        params={"row": 3, "col": 3, "thermal_dwell": "true", "start_utc": "2026-09-28T00:00:00"},
    ).json()
    card = on["thermal_dwell"]
    assert card["side"] == "cold" and card["component"] == "battery"
    assert card["max_dwell_h"] == pytest.approx(_fixture_dwell_h(), rel=1e-6) and card["open_ended"] is False
    assert card["envelope_verdict"]["cold_end"] == "cold" and card["initial_inner_c"] == 17.5
    assert card["lookahead_h"] == 24.0 and card["shadow_model"]["model"] == "static"
    countdown = card["tolerable_entrenched"]
    assert countdown["haven"] is None and countdown["overall"]["limiting"] == "thermal"
    assert countdown["overall"]["tolerable_h"] == pytest.approx(card["max_dwell_h"])
    assert on["thermal_dwell_model"]["model"] == TD.THERMAL_DWELL_MODEL_ID
    warm = client.get(
        "/api/cell-telemetry",
        params={"row": 3, "col": 3, "thermal_dwell": "true", "heater_model": "thermostat_assumed"},
    ).json()["thermal_dwell"]
    assert warm["open_ended"] is True and warm["max_dwell_h"] is None


def test_cell_telemetry_thermal_dwell_without_tau_is_verdict_only(client):
    card = client.get(
        "/api/cell-telemetry", params={"row": 3, "col": 3, "thermal_dwell": "true", "rover_id": "luvmi_m"}
    ).json()
    assert card["thermal_dwell"]["max_dwell_h"] is None
    assert card["thermal_dwell"]["envelope_verdict"]["peak"] == "inside"  # -100 sits on LUVMI-M's [-100, 0] bound
    assert card["thermal_dwell_model"]["model"] == "unavailable" and card["thermal_dwell"]["tolerable_entrenched"] is None


# ── /api/replan ──────────────────────────────────────────────────────────────


def _replan_body(entrenched: float, utc: str | None = "2026-09-28T00:00:00") -> dict:
    return {
        "current": {"row": 3, "col": 3},
        "goal": {"row": 12, "col": 12},
        "rover_id": "lpr_1",
        "utc": utc,
        "state": {"entrenched_hours": entrenched},
    }


def test_replan_entrenchment_countdown_levels_and_trigger(client):
    ok = client.post("/api/replan", json=_replan_body(0.1)).json()
    block = ok["entrenchment"]
    assert block["overall"]["level"] == "ok" and block["overall"]["limiting"] == "thermal"
    assert block["thermal"]["tolerable_h"] == pytest.approx(_fixture_dwell_h(), rel=1e-6) and block["haven"] is None
    assert ok["replanned"] is False and "entrenchment" in ok["evaluated"]
    warning = client.post("/api/replan", json=_replan_body(0.4)).json()
    assert warning["entrenchment"]["overall"]["level"] == "warning" and warning["replanned"] is False
    critical = client.post("/api/replan", json=_replan_body(0.47)).json()
    assert critical["entrenchment"]["overall"]["level"] == "critical" and critical["replanned"] is True
    assert any(t["trigger_id"] == "entrenchment" and "critical" in t["detail"] for t in critical["triggers"])
    failed = client.post("/api/replan", json=_replan_body(5.0)).json()
    assert failed["entrenchment"]["overall"]["level"] == "fail" and failed["entrenchment"]["overall"]["remaining_h"] < 0


def test_replan_entrenchment_needs_utc_and_the_field(client):
    no_utc = client.post("/api/replan", json=_replan_body(1.0, utc=None)).json()
    assert no_utc["entrenchment"] is None and "utc" in no_utc["entrenchment_model"]["reason"]
    assert any(s["trigger_id"] == "entrenchment" for s in no_utc["skipped"])
    body = _replan_body(1.0)
    del body["state"]["entrenched_hours"]
    plain = client.post("/api/replan", json=body).json()
    assert plain["entrenchment"] is None and "entrenched_hours" in plain["entrenchment_model"]["reason"]
    given = client.post(
        "/api/replan", json={**_replan_body(1.0), "state": {"entrenched_hours": 1.0, "tolerable_entrenched_hours": 4.0}}
    ).json()
    assert given["entrenchment"]["overall"]["limiting"] == "thermal"  # the block is still computed
    assert any(t["trigger_id"] == "entrenchment" for t in given["triggers"]) is False  # 1 of 4 h: ok


def test_replan_entrenchment_uses_the_actual_inner_temperature_when_given(client):
    warm = client.post(
        "/api/replan", json={**_replan_body(0.1), "state": {"entrenched_hours": 0.1, "actual_inner_c": 30.0}}
    ).json()["entrenchment"]["thermal"]
    cold = client.post(
        "/api/replan", json={**_replan_body(0.1), "state": {"entrenched_hours": 0.1, "actual_inner_c": 5.0}}
    ).json()["entrenchment"]["thermal"]
    assert warm["initial_inner_c"] == 30.0 and cold["initial_inner_c"] == 5.0
    assert warm["tolerable_h"] > cold["tolerable_h"]


# ── GET /api/thermal-dwell ───────────────────────────────────────────────────


def test_thermal_dwell_layer_json_and_binary(client):
    js = client.get("/api/thermal-dwell", params={"start_utc": "2026-09-28T00:00:00", "lookahead_hours": 4})
    assert js.status_code == 200, js.text
    payload = js.json()
    assert payload["grid"]["rows"] == 4 and payload["grid"]["coarsen"] == 4
    assert set(payload["fields"]) == {"max_dwell_h", "side", "open_ended"}
    assert payload["summary"]["fraction_cold_limited"] == 1.0 and payload["summary"]["traversable_blocks"] == 16
    assert payload["dwell_model"]["model"] == TD.THERMAL_DWELL_MODEL_ID and payload["shadow_model"]["model"] == "static"
    assert payload["fields"]["max_dwell_h"]["units"] == "h" and "binary_url" in payload["fields"]["side"]
    binary = client.get(
        "/api/thermal-dwell",
        params={"start_utc": "2026-09-28T00:00:00", "lookahead_hours": 4, "format": "f32", "field": "max_dwell_h"},
    )
    assert binary.status_code == 200
    assert binary.headers["X-Layer-Validity"] == "MODEL" and len(binary.content) == 4 * 4 * 4
    values = np.frombuffer(binary.content, dtype="<f4")
    assert np.allclose(values, _fixture_dwell_h(), atol=1e-4)
    assert client.get("/api/thermal-dwell", params={"start_utc": "2026-09-28T00:00:00", "rover_id": "luvmi_m"}).status_code == 422
    assert client.get("/api/thermal-dwell", params={"start_utc": "2026-09-28T00:00:00", "t_hours": 170, "lookahead_hours": 4}).status_code == 422


def test_thermal_dwell_layer_open_ended_is_capped_at_the_lookahead(client):
    payload = client.get(
        "/api/thermal-dwell",
        params={"start_utc": "2026-09-28T00:00:00", "lookahead_hours": 4, "heater_model": "thermostat_assumed"},
    ).json()
    assert payload["summary"]["fraction_unlimited"] == 1.0
    assert payload["fields"]["max_dwell_h"]["max"] == pytest.approx(4.0)
    assert payload["fields"]["open_ended"]["max"] == 1.0


# ── GET /api/thermal-envelope ────────────────────────────────────────────────


def test_envelope_endpoint_needs_the_cache_and_serves_it(client, tmp_path, monkeypatch):
    from app import main as main_module

    monkeypatch.setattr(main_module, "envelope_cache_path", lambda metadata: None)
    missing = client.get("/api/thermal-envelope")
    assert missing.status_code == 422 and "build_thermal_envelope_cache" in missing.json()["detail"]
    samples = {
        "el_deg": np.array([0.5, 0.5, 2.0]),
        "s_par_deg": np.array([5.0, 5.0, 20.0]),
        "surface_c": np.array([-50.0, -55.0, -20.0]),
        "slope_deg": np.array([5.0, 5.0, 20.0]),
    }
    binned = TD.bin_envelope(samples, TD.ENVELOPE_EL_EDGES, TD.ENVELOPE_SPAR_EDGES)
    path = tmp_path / TD.ENVELOPE_CACHE_FILENAME
    TD.save_envelope_cache(str(path), binned, {"lat_deg": -88.92, "slopes_deg": [5.0, 20.0], "ndays": 13})
    monkeypatch.setattr(main_module, "envelope_cache_path", lambda metadata: str(path))
    payload = client.get("/api/thermal-envelope", params={"rover_id": "lpr_1"}).json()
    assert payload["counts"]["unlimited"] == 1 and payload["counts"]["hot_limited"] == 1
    assert payload["quoted"]["case_matrix"] == 96 and payload["meta"]["lat_deg"] == -88.92
    assert payload["axes"]["s_par_deg"]["edges"][0] == -30.0 and payload["rover_id"] == "lpr_1"
    hot = next(c for c in payload["cells"] if c["verdict"] == "hot_limited")
    assert hot["surface_c_max"] == -20.0 and hot["inner_c"] == 40.0 and hot["dwell_h"] > 0
