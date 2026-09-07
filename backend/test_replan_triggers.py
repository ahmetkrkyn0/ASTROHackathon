"""Replan trigger taxonomy tests."""

from __future__ import annotations

import pytest

from app.replan_triggers import (
    TriggerResult,
    check_comm_window,
    check_corridor_violation,
    check_inner_temperature,
    check_localization_uncertainty,
    check_soc_deviation,
    check_time_drift,
    evaluate_triggers,
)


def test_soc_deviation_fires_beyond_ten_points():
    assert check_soc_deviation(actual_soc=0.60, planned_soc=0.75).triggered
    assert not check_soc_deviation(actual_soc=0.70, planned_soc=0.75).triggered


def test_soc_deviation_ignores_being_ahead_of_plan():
    assert not check_soc_deviation(actual_soc=0.95, planned_soc=0.75).triggered


def test_inner_temperature_fires_five_kelvin_below_prediction():
    assert check_inner_temperature(actual_c=-6.0, predicted_c=0.0).triggered
    assert not check_inner_temperature(actual_c=-3.0, predicted_c=0.0).triggered


def test_time_drift_fires_after_thirty_minutes():
    assert check_time_drift(drift_minutes=45.0).triggered
    assert check_time_drift(drift_minutes=-45.0).triggered
    assert not check_time_drift(drift_minutes=10.0).triggered


def test_corridor_violation_fires_outside_half_width():
    assert check_corridor_violation(lateral_offset_m=120.0, half_width_m=100.0).triggered
    assert not check_corridor_violation(lateral_offset_m=80.0, half_width_m=100.0).triggered


def test_comm_window_fires_when_closing():
    assert check_comm_window(minutes_remaining=5.0, threshold_minutes=15.0).triggered
    assert not check_comm_window(minutes_remaining=30.0, threshold_minutes=15.0).triggered


def test_localization_uncertainty_fires_above_half_width():
    assert check_localization_uncertainty(
        covariance_m=150.0, half_width_m=100.0
    ).triggered
    assert not check_localization_uncertainty(
        covariance_m=40.0, half_width_m=100.0
    ).triggered


def test_every_trigger_returns_a_named_result():
    result = check_soc_deviation(actual_soc=0.1, planned_soc=0.9)
    assert isinstance(result, TriggerResult)
    assert result.trigger_id == "soc_deviation"
    assert result.detail


def test_evaluate_triggers_returns_only_fired_triggers():
    fired = evaluate_triggers(
        {
            "actual_soc": 0.50,
            "planned_soc": 0.75,
            "actual_inner_c": 0.0,
            "predicted_inner_c": 0.0,
            "drift_minutes": 2.0,
            "lateral_offset_m": 10.0,
            "half_width_m": 100.0,
            "comm_minutes_remaining": 120.0,
            "localization_covariance_m": 5.0,
        }
    )
    assert [r.trigger_id for r in fired] == ["soc_deviation"]


def test_evaluate_triggers_skips_missing_inputs():
    assert evaluate_triggers({}) == []


import numpy as np
from fastapi.testclient import TestClient

from app.constants import get_rover
from app.main import app

_SHAPE = (30, 30)


@pytest.fixture()
def replan_client():
    rover = get_rover()
    grids = {
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
    with TestClient(app) as test_client:
        app.state.grids = grids
        yield test_client
    app.state.grids = None


def _body(state: dict) -> dict:
    return {
        "current": {"row": 5, "col": 5},
        "goal": {"row": 25, "col": 25},
        "state": state,
    }


def test_replan_is_a_noop_when_no_trigger_fires(replan_client):
    payload = replan_client.post(
        "/api/replan", json=_body({"actual_soc": 0.8, "planned_soc": 0.82})
    ).json()
    assert payload["replanned"] is False
    assert payload["triggers"] == []


def test_replan_produces_a_new_route_when_a_trigger_fires(replan_client):
    payload = replan_client.post(
        "/api/replan", json=_body({"actual_soc": 0.40, "planned_soc": 0.75})
    ).json()
    assert payload["replanned"] is True
    assert payload["triggers"][0]["trigger_id"] == "soc_deviation"
    coordinates = payload["plan"]["geojson"]["geometry"]["coordinates"]
    assert len(coordinates) >= 2


# ── A4: comm_minutes_remaining computed from the Earth geometry ────────────
#
# check_comm_window has existed since Phase 4 with its input expected from
# outside. With an epoch and the horizon cube the backend now computes it
# from where the rover is and where the Earth is. Faked here: the geometry
# is pinned in test_earth_visibility.py; this is the wiring.


def _fake_window(minutes: float, visible: bool = True):
    def _window(metadata, row, col, utc, **kwargs):
        return {
            "utc": utc,
            "row": row,
            "col": col,
            "visible_now": visible,
            "minutes_remaining": minutes if visible else None,
            "minutes_until_visible": None if visible else minutes,
            "next_change_utc": None,
            "search_limited": False,
            "trigger_minutes_remaining": minutes if visible else 0.0,
            "earth_elevation_deg": 3.0,
            "earth_azimuth_true_deg": 100.0,
            "earth_azimuth_grid_deg": 350.0,
            "horizon_deg": 1.0,
        }

    return _window


def test_replan_computes_the_comm_window_from_the_epoch(replan_client, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "comm_window_from_metadata", _fake_window(5.0))
    body = _body({"actual_soc": 0.8, "planned_soc": 0.8})
    body["utc"] = "2026-09-03T12:00:00"
    payload = replan_client.post("/api/replan", json=body).json()

    assert payload["replanned"] is True
    assert [t["trigger_id"] for t in payload["triggers"]] == ["comm_window"]
    assert "5.0 min" in payload["triggers"][0]["detail"]
    assert payload["comm_window"]["row"] == 5 and payload["comm_window"]["col"] == 5
    assert payload["comm_window"]["utc"] == "2026-09-03T12:00:00"
    assert payload["comm_window"]["trigger_minutes_remaining"] == 5.0


def test_replan_keeps_a_caller_supplied_comm_value(replan_client, monkeypatch):
    """Telemetry from the radio beats geometry from the map; the computed
    window is still reported beside it."""
    import app.main as main_module

    monkeypatch.setattr(main_module, "comm_window_from_metadata", _fake_window(5.0))
    body = _body({"actual_soc": 0.8, "planned_soc": 0.8, "comm_minutes_remaining": 90.0})
    body["utc"] = "2026-09-03T12:00:00"
    payload = replan_client.post("/api/replan", json=body).json()

    assert payload["replanned"] is False
    assert "comm_window" in payload["evaluated"]
    assert payload["comm_window"]["trigger_minutes_remaining"] == 5.0


def test_replan_without_a_horizon_cube_still_reports_comm_as_skipped(replan_client):
    body = _body({"actual_soc": 0.8, "planned_soc": 0.8})
    body["utc"] = "2026-09-03T12:00:00"
    payload = replan_client.post("/api/replan", json=body).json()

    assert payload["replanned"] is False
    assert payload["comm_window"] is None
    assert "comm_window" in [entry["trigger_id"] for entry in payload["skipped"]]


def test_replan_without_an_epoch_does_not_compute_a_window(replan_client, monkeypatch):
    import app.main as main_module

    calls = []

    def _spy(metadata, row, col, utc, **kwargs):
        calls.append((row, col, utc))
        return None

    monkeypatch.setattr(main_module, "comm_window_from_metadata", _spy)
    payload = replan_client.post(
        "/api/replan", json=_body({"actual_soc": 0.8, "planned_soc": 0.8})
    ).json()
    assert calls == []
    assert payload["comm_window"] is None
