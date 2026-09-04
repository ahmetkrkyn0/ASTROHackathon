"""safety_margins on /api/plan, /api/plan-4d, /api/compare, /api/plan-multi
and POST /api/safety-check -- synthetic grids, no kernels, no clone cache."""

from __future__ import annotations

import math

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import safety_monitor as sm
from app.constants import get_rover
from app.main import app
from test_plan_4d_endpoint import _earth_series_closing_at, _fake_safe_haven_map

SHAPE = (16, 16)
_client = TestClient(app)

REQ_IDS = [f"LP-R{i:02d}" for i in range(1, 12)]


def _grids():
    rover = get_rover()
    return {
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
            "cost_weights": {"w_slope": 0.409, "w_energy": 0.259, "w_shadow": 0.142, "w_thermal": 0.19},
        },
    }


@pytest.fixture()
def client():
    app.state.grids = _grids()
    yield _client
    app.state.grids = None


def _by_id(block):
    return {entry["id"]: entry for entry in block["requirements"]}


# ── /api/plan ──────────────────────────────────────────────────────────


def test_plan_response_carries_safety_margins(client):
    response = client.post("/api/plan", json={"start": {"row": 0, "col": 0}, "goal": {"row": 12, "col": 12}, "rover_id": "lpr_1"})
    assert response.status_code == 200, response.text
    payload = response.json()
    for key in ("status", "astar_metrics", "summary", "geojson", "corridor", "route_statistics", "execution", "rover", "waypoints"):
        assert key in payload
    block = payload["safety_margins"]
    assert block["monitor"]["engine"] in ("rtamt", "builtin")
    assert block["monitor"]["trace"]["kind"] == "2d"
    assert "not proven" in block["monitor"]["claim"]
    r = _by_id(block)
    assert list(r) == REQ_IDS
    summary = payload["summary"]
    # Shadow 0.3 > 0.2 everywhere: the whole drive is one continuous shadow.
    assert r["LP-R01"]["rho"] == pytest.approx(50.0 - summary["max_continuous_shadow_h"], abs=1e-3)
    assert r["LP-R02"]["rho"] == pytest.approx(summary["min_battery_pct"] - 20.0, abs=1e-2)
    assert r["LP-R06"]["rho"] == pytest.approx(25.0 - summary["max_segment_slope_deg"] if summary["max_segment_slope_deg"] > 3.0 else 22.0, abs=1e-2)
    assert r["LP-R07"]["applicable"] is True and r["LP-R07"]["rho"] == pytest.approx(18.0)
    assert r["LP-R10"]["satisfied"] is True and r["LP-R10"]["boundary"] is True
    assert r["LP-R11"]["applicable"] is True
    for rid in ("LP-R08", "LP-R09"):
        assert r[rid]["applicable"] is False and "signal" in r[rid]["reason"]
    assert block["n_applicable"] == 9
    assert block["verdict"] in ("satisfied", "violated")


def test_plan_safety_margins_follow_the_rover(client):
    viper = client.post("/api/plan", json={"start": {"row": 0, "col": 0}, "goal": {"row": 12, "col": 12}, "rover_id": "nasa_viper"}).json()
    r = _by_id(viper["safety_margins"])
    assert r["LP-R01"]["threshold"] == 96.0 and r["LP-R06"]["threshold"] == 20.0 and r["LP-R07"]["threshold"] == 15.0
    luvmi = client.post("/api/plan", json={"start": {"row": 0, "col": 0}, "goal": {"row": 12, "col": 12}, "rover_id": "luvmi_m"}).json()
    assert _by_id(luvmi["safety_margins"])["LP-R04"]["applicable"] is False


# ── /api/plan-4d ───────────────────────────────────────────────────────


def _body_4d(**overrides):
    body = {"start": {"row": 0, "col": 0}, "goal": {"row": 12, "col": 12}, "n_slices": 24, "slice_hours": 1.0, "coarsen": 4}
    body.update(overrides)
    return body


def test_plan_4d_response_carries_safety_margins(client):
    response = client.post("/api/plan-4d", json=_body_4d())
    assert response.status_code == 200, response.text
    payload = response.json()
    block = payload["safety_margins"]
    assert block["monitor"]["trace"]["kind"] == "4d"
    assert block["monitor"]["trace"]["n_samples"] == len(payload["path_states"])
    r = _by_id(block)
    assert r["LP-R01"]["rho"] == pytest.approx(50.0 - max(payload["path_dark_hours"]), abs=1e-6)
    assert r["LP-R02"]["rho"] == pytest.approx(min(payload["path_battery_pct"]) - 20.0, abs=1e-6)
    assert r["LP-R06"]["applicable"] and r["LP-R07"]["applicable"]
    assert r["LP-R10"]["satisfied"] is True
    # No Earth field and no haven map on a synthetic grid without kernels.
    assert payload["path_earth_visible"] is None
    assert r["LP-R08"]["applicable"] is False and r["LP-R09"]["applicable"] is False
    for key in ("path_pixels", "path_states", "metrics", "shadow_model", "earth_model", "safe_haven_model", "slice_hours"):
        assert key in payload


def test_plan_4d_checks_the_haven_and_dte_rules_when_the_fields_exist(client, monkeypatch):
    import app.main as main_module

    _fake_safe_haven_map(monkeypatch)
    monkeypatch.setattr(main_module, "build_earth_visibility_series", _earth_series_closing_at(3))
    payload = client.post("/api/plan-4d", json=_body_4d(start_utc="2026-09-01T00:00:00")).json()
    block = payload["safety_margins"]
    r = _by_id(block)
    assert r["LP-R09"]["applicable"] is True
    assert r["LP-R09"]["rho"] == pytest.approx(payload["metrics"]["min_haven_margin_h"], abs=1e-6)
    assert r["LP-R09"]["satisfied"] is False and "LP-R09" in block["violated"]
    assert block["verdict"] == "violated"
    assert r["LP-R08"]["applicable"] is True
    # Blind moves after the link closes at 3 h carry a negative link margin.
    assert r["LP-R08"]["satisfied"] is False


# ── /api/compare and /api/plan-multi ───────────────────────────────────


def test_compare_results_carry_safety_margins_and_a_ranking(client):
    response = client.post("/api/compare", json={"start": [0, 0], "goal": [12, 12], "rover_id": "lpr_1"})
    assert response.status_code == 200, response.text
    payload = response.json()
    results = payload["results"]
    assert results
    for result in results:
        assert "constraint_check" in result and "simulation_summary" in result
        if not result.get("error"):
            block = result["safety_margins"]
            assert block["monitor"]["trace"]["kind"] == "2d"
            assert _by_id(block)["LP-R02"]["rho"] == pytest.approx(result["simulation_summary"]["min_battery_pct"] - 20.0, abs=1e-2)
    comparison = payload["comparison"]
    for key in ("shortest_profile", "safest_profile", "most_efficient_profile", "recommendation"):
        assert key in comparison
    ranking = comparison["safety_margin_ranking"]
    assert [entry["label"] for entry in ranking] and set(e["label"] for e in ranking) == {r["profile_id"] for r in results}
    assert ranking[0]["verdict"] in ("satisfied", "violated")
    assert comparison["largest_min_margin_profile"] == ranking[0]["label"]


def test_plan_multi_results_carry_safety_margins(client):
    profiles = client.get("/api/profiles").json()
    profile_ids = [p["id"] for p in profiles] if isinstance(profiles, list) else list(profiles)
    response = client.post("/api/plan-multi", json={"start": [0, 0], "goal": [12, 12], "rover_id": "lpr_1", "profiles": profile_ids[:2] + ["nope"]})
    assert response.status_code == 200, response.text
    results = response.json()["results"]
    assert "safety_margins" in results[0]
    assert results[-1]["error"] and "safety_margins" not in results[-1]


# ── POST /api/safety-check ─────────────────────────────────────────────

SAMPLES = [
    {"t_h": 0.0, "soc_pct": 100.0, "inner_temp_c": 10.0, "in_shadow": False, "slope_deg": 5.0, "lateral_slope_deg": 3.0,
     "moving": False, "earth_link_h": 30.0, "haven_margin_h": 12.0, "dist_to_goal_m": 400.0, "extra": 1},
    {"t_h": 1.0, "soc_pct": 60.0, "inner_temp_c": 20.0, "in_shadow": True, "slope_deg": 12.0, "lateral_slope_deg": 6.0,
     "moving": True, "earth_link_h": 25.0, "haven_margin_h": 10.0, "dist_to_goal_m": 300.0},
    {"t_h": 3.0, "soc_pct": 30.0, "inner_temp_c": 33.0, "in_shadow": True, "slope_deg": 18.0, "lateral_slope_deg": 14.0,
     "moving": True, "earth_link_h": 20.0, "haven_margin_h": 7.0, "dist_to_goal_m": 100.0},
    {"t_h": 4.0, "soc_pct": 25.0, "inner_temp_c": 5.0, "in_shadow": False, "slope_deg": 3.0, "lateral_slope_deg": 1.0,
     "moving": True, "earth_link_h": 19.0, "haven_margin_h": 9.0, "dist_to_goal_m": 0.0},
]


def test_safety_check_evaluates_a_telemetry_trace():
    response = _client.post("/api/safety-check", json={"rover_id": "nasa_viper", "samples": SAMPLES})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["rover_id"] == "nasa_viper" and payload["n_samples"] == 4
    assert payload["ignored_keys"] == ["extra"]
    assert "soc_pct" in payload["signals_present"] and "shadow_continuous_h" in payload["signals_present"]
    block = payload["safety_margins"]
    r = _by_id(block)
    assert r["LP-R01"]["rho"] == pytest.approx(93.0) and r["LP-R07"]["rho"] == pytest.approx(1.0)
    assert block["min_margin"]["id"] == "LP-R07" and block["verdict"] == "satisfied"


def test_safety_check_can_force_the_builtin_engine_and_the_deadline():
    payload = _client.post(
        "/api/safety-check",
        json={"rover_id": "lpr_1", "samples": SAMPLES, "engine": "builtin", "recharge_deadline_h": 3.0},
    ).json()
    assert payload["safety_margins"]["monitor"]["engine"] == "builtin"
    assert payload["safety_margins"]["monitor"]["cross_check"] is None
    assert _by_id(payload["safety_margins"])["LP-R03"]["threshold"] == 3.0


def test_safety_check_incomplete_trace_leaves_the_goal_pending():
    payload = _client.post("/api/safety-check", json={"rover_id": "lpr_1", "samples": SAMPLES[:2], "complete": False}).json()
    r = _by_id(payload["safety_margins"])
    assert r["LP-R10"]["pending"] is True and r["LP-R10"]["satisfied"] is None
    assert payload["safety_margins"]["verdict"] == "pending"


@pytest.mark.parametrize(
    "body",
    [
        {"rover_id": "lpr_1", "samples": []},
        {"rover_id": "lpr_1", "samples": [{"t_h": 1.0, "soc_pct": 50.0}, {"t_h": 0.5, "soc_pct": 50.0}]},
        {"rover_id": "lpr_1", "samples": [{"t_h": 0.0, "soc_pct": float("nan")}]},
        {"rover_id": "lpr_1", "samples": [{"soc_pct": 50.0}]},
        {"rover_id": "lpr_1", "samples": SAMPLES, "engine": "z3"},
        {"rover_id": "lpr_1", "samples": SAMPLES, "recharge_deadline_h": 0.0},
        {"rover_id": "no_such_rover", "samples": SAMPLES},
    ],
)
def test_safety_check_rejects_malformed_requests(body):
    response = _client.post("/api/safety-check", json=body)
    assert response.status_code == 422, response.text


def test_safety_check_refuses_rtamt_when_it_is_not_installed(monkeypatch):
    monkeypatch.setattr(sm, "_import_rtamt", lambda: None)
    response = _client.post("/api/safety-check", json={"rover_id": "lpr_1", "samples": SAMPLES, "engine": "rtamt"})
    assert response.status_code == 422
    assert "rtamt" in response.json()["detail"]
    fallback = _client.post("/api/safety-check", json={"rover_id": "lpr_1", "samples": SAMPLES}).json()
    assert fallback["safety_margins"]["monitor"]["engine"] == "builtin"
