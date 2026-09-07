"""/api/plan-4d endpoint tests."""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.constants import get_rover
from app.main import app

SHAPE = (16, 16)

# Built once so the startup handler runs and fails gracefully (no .npy files);
# grids are injected per-test afterwards, mirroring test_plan_endpoint.py.
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


def test_plan_4d_returns_a_path(client):
    response = client.post("/api/plan-4d", json=_body())
    assert response.status_code == 200
    payload = response.json()
    assert payload["path_pixels"]
    assert payload["metrics"]["arrival_slice"] is not None


def test_plan_4d_reports_wait_steps(client):
    payload = client.post("/api/plan-4d", json=_body()).json()
    assert "wait_steps" in payload["metrics"]


def test_plan_4d_echoes_time_configuration(client):
    payload = client.post("/api/plan-4d", json=_body(n_slices=12)).json()
    assert payload["n_slices"] == 12
    assert payload["slice_hours"] == 1.0
    assert payload["coarsen"] == 4


def test_plan_4d_rejects_non_divisible_coarsen(client):
    response = client.post("/api/plan-4d", json=_body(coarsen=5))
    assert response.status_code == 422


# ── Review findings: coordinate space and degenerate start/goal ───────────────


def test_path_pixels_are_fine_grid_coordinates(client):
    """``path_pixels`` must be in the same space as /api/plan.

    The planner solves on a coarsened grid, but the caller asked in fine
    pixels and a local planner will convert these with the fine
    ``resolution_m``/``origin``. Returning coarse indices under the same
    field name is a 4x scale error waiting to happen.
    """
    payload = client.post("/api/plan-4d", json=_body()).json()
    rows, cols = SHAPE
    for row, col in payload["path_pixels"]:
        assert 0 <= row < rows
        assert 0 <= col < cols
    # A 16x16 grid at coarsen=4 has coarse indices 0..3; a fine path to
    # (12, 12) must reach beyond that range.
    assert max(max(r, c) for r, c in payload["path_pixels"]) > 3


def test_path_pixels_end_near_the_requested_goal(client):
    payload = client.post("/api/plan-4d", json=_body()).json()
    last_row, last_col = payload["path_pixels"][-1]
    # Within one coarse block of the requested (12, 12).
    assert abs(last_row - 12) < 4
    assert abs(last_col - 12) < 4


def test_response_reports_the_effective_planning_resolution(client):
    payload = client.post("/api/plan-4d", json=_body()).json()
    assert payload["effective_resolution_m"] == pytest.approx(80.0 * 4)


def test_coarse_path_is_still_available_under_its_own_name(client):
    payload = client.post("/api/plan-4d", json=_body()).json()
    assert payload["path_pixels_coarse"]
    assert len(payload["path_pixels_coarse"]) == len(payload["path_pixels"])


def test_start_and_goal_in_the_same_coarse_cell_is_rejected(client):
    """(0,0) and (3,3) both collapse to coarse (0,0) at coarsen=4."""
    response = client.post(
        "/api/plan-4d", json=_body(goal={"row": 3, "col": 3})
    )
    assert response.status_code == 422
    assert "coarse" in response.json()["detail"].lower()


def test_identical_start_and_goal_is_rejected(client):
    response = client.post(
        "/api/plan-4d", json=_body(start={"row": 4, "col": 4}, goal={"row": 4, "col": 4})
    )
    assert response.status_code == 422


# ── Review finding C1: the time axis must advance in real hours ───────────────


def test_slice_hours_is_derived_from_the_grid_when_omitted(client):
    """Omitting slice_hours must produce a slice sized to one cell crossing,
    not the 1 h default that collapsed every move to a single slice."""
    body = _body()
    body.pop("slice_hours")
    payload = client.post("/api/plan-4d", json=body).json()

    from app.cost_engine import edge_travel_time_s

    rover = get_rover()
    # 80 m fine cells at coarsen=4 -> 320 m coarse edges at slope 3 deg.
    expected = edge_travel_time_s(3.0, 320.0, rover) / 3600.0
    assert payload["slice_hours"] == pytest.approx(expected, rel=0.2)
    assert payload["slice_hours_source"] == "auto"


def test_explicit_slice_hours_is_still_honoured(client):
    payload = client.post("/api/plan-4d", json=_body(slice_hours=2.0)).json()
    assert payload["slice_hours"] == 2.0
    assert payload["slice_hours_source"] == "request"


def test_auto_slice_hours_makes_arrival_slice_a_clock(client):
    """With an auto slice the horizon is real time, so the response can
    report it in hours rather than in steps."""
    body = _body()
    body.pop("slice_hours")
    payload = client.post("/api/plan-4d", json=body).json()

    arrival = payload["metrics"]["arrival_slice"]
    assert payload["metrics"]["arrival_hours"] == pytest.approx(
        arrival * payload["slice_hours"]
    )
    assert payload["horizon_hours"] == pytest.approx(
        payload["n_slices"] * payload["slice_hours"]
    )


def test_horizon_can_be_requested_in_hours(client):
    """n_slices is a memory knob; the mission cares about hours. With an
    auto slice a fixed slice count no longer means a fixed horizon."""
    body = _body(horizon_hours=6.0)
    body.pop("n_slices")
    payload = client.post("/api/plan-4d", json=body).json()
    assert payload["horizon_hours"] == pytest.approx(6.0, rel=0.05)
    assert payload["n_slices"] > 1


def test_horizon_hours_and_n_slices_are_mutually_exclusive(client):
    response = client.post(
        "/api/plan-4d", json=_body(horizon_hours=6.0, n_slices=24)
    )
    assert response.status_code == 422
    assert "horizon_hours" in response.json()["detail"]


def test_horizon_hours_is_capped_to_bound_memory(client):
    """On a fine grid a physical slice is ~2 minutes, so a week-long horizon
    is thousands of slices and two float64 cubes of hundreds of MB. The cap
    must refuse rather than allocate. (Faz 3 review, C1.)"""
    body = _body(horizon_hours=168.0, slice_hours=0.05)
    body.pop("n_slices")
    response = client.post("/api/plan-4d", json=body)
    assert response.status_code == 422
    assert "slices" in response.json()["detail"].lower()


def test_horizon_within_the_cap_is_accepted(client):
    body = _body(horizon_hours=20.0, slice_hours=0.05)
    body.pop("n_slices")
    payload = client.post("/api/plan-4d", json=body).json()
    assert payload["n_slices"] == 400
    assert payload["horizon_hours"] == pytest.approx(20.0)


# ── Battery and shadow endurance in the response ─────────────────────────────


def test_plan_4d_reports_a_battery_profile_and_honours_initial_soc(client):
    payload = client.post("/api/plan-4d", json=_body(initial_soc_pct=0.5)).json()
    assert payload["path_battery_pct"][0] == pytest.approx(50.0)
    assert len(payload["path_battery_pct"]) == len(payload["path_states"])
    assert len(payload["path_dark_hours"]) == len(payload["path_states"])
    metrics = payload["metrics"]
    assert "min_battery_pct" in metrics
    assert "final_battery_pct" in metrics
    assert "max_continuous_shadow_h" in metrics
    assert "energy_drawn_wh" in metrics and "energy_charged_wh" in metrics


def test_plan_4d_defaults_to_a_full_battery(client):
    payload = client.post("/api/plan-4d", json=_body()).json()
    assert payload["path_battery_pct"][0] == pytest.approx(100.0)


def test_plan_4d_rejects_initial_soc_outside_the_unit_interval(client):
    for bad in (0.0, 1.5, -0.2):
        response = client.post("/api/plan-4d", json=_body(initial_soc_pct=bad))
        assert response.status_code == 422, bad


def test_plan_4d_starting_under_the_reserve_waits_to_charge(client):
    """The fixture is 70 percent lit, so a rover parked at 10 percent charges
    at ~240 W -- while driving a 12 degree slope draws more than the array
    gives back. The right plan is to wait until the reserve is covered, not
    to refuse."""
    app.state.grids["slope"] = np.full(SHAPE, 12.0)
    response = client.post("/api/plan-4d", json=_body(initial_soc_pct=0.1))
    assert response.status_code == 200, response.json()
    payload = response.json()
    assert payload["path_battery_pct"][0] == pytest.approx(10.0)
    assert payload["metrics"]["final_battery_pct"] > 10.0
    assert payload["metrics"]["wait_steps"] > 0
    # Waiting under the reserve is allowed (it charges); every MOVE must
    # end at or above it.
    reserve_pct = get_rover()["soc_min_pct"] * 100.0
    states, battery = payload["path_states"], payload["path_battery_pct"]
    moves_end_at = [
        battery[i + 1]
        for i in range(len(states) - 1)
        if states[i][:2] != states[i + 1][:2]
    ]
    assert moves_end_at, "the route must contain at least one move"
    assert min(moves_end_at) >= reserve_pct - 1e-6


# ── A4: Direct-to-Earth visibility through the endpoint ────────────────────


def test_plan_4d_says_when_earth_visibility_could_not_be_computed(client):
    """The fixture has no horizon cube and no long-run layer: the plan is
    still made, and the response says the Earth field was unavailable
    rather than pretending every cell had a link."""
    payload = client.post("/api/plan-4d", json=_body()).json()
    assert payload["earth_model"]["model"] == "unavailable"
    assert payload["earth_model"]["reason"]
    assert payload["path_earth_visible"] is None
    assert payload["metrics"]["earth_visibility_enforced"] is False
    assert payload["metrics"]["moves_out_of_earth_view"] is None


def test_requiring_earth_visibility_without_a_field_is_a_422(client):
    response = client.post(
        "/api/plan-4d", json=_body(require_earth_visibility=True)
    )
    assert response.status_code == 422
    assert "Earth visibility" in response.json()["detail"]


def _earth_series_with_a_dark_band(open_from_slice: int | None):
    """(16, 16) slices with fine columns 8..11 -- coarse column 2 at
    coarsen=4 -- out of Earth view until *open_from_slice* (never, if None).
    Goal (12, 12) sits in coarse column 3, so the band is the only way."""

    def _fake(base, metadata, n_slices, slice_hours, start_utc=None):
        series = []
        for index in range(int(n_slices)):
            snapshot = np.ones(SHAPE, dtype=np.float64)
            if open_from_slice is None or index < open_from_slice:
                snapshot[:, 8:12] = 0.0
            series.append(snapshot)
        return series, {"model": "spice_horizon", "time_varying": True}

    return _fake


def test_plan_4d_enforces_earth_visibility_when_asked(client, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(
        main_module, "build_earth_visibility_series", _earth_series_with_a_dark_band(None)
    )
    response = client.post(
        "/api/plan-4d",
        json=_body(require_earth_visibility=True, start_utc="2026-09-01T00:00:00"),
    )
    assert response.status_code == 404
    detail = response.json()["detail"]
    assert "Earth visibility" in detail


def test_plan_4d_waits_for_the_link_when_asked(client, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(
        main_module, "build_earth_visibility_series", _earth_series_with_a_dark_band(12)
    )
    response = client.post(
        "/api/plan-4d",
        json=_body(require_earth_visibility=True, start_utc="2026-09-01T00:00:00"),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["earth_model"]["model"] == "spice_horizon"
    assert payload["metrics"]["earth_visibility_enforced"] is True
    assert payload["metrics"]["moves_out_of_earth_view"] == 0
    assert len(payload["path_earth_visible"]) == len(payload["path_states"])
    assert all(payload["path_earth_visible"])
    # The band (coarse column 2) is entered only once the link is open.
    # How the planner passes the time before that -- a WAIT edge or a
    # shuffle between two linked cells -- is a pricing question the 1 h
    # fixture slice does not settle; the rule is what is pinned here.
    band_arrivals = [t for _r, c, t in payload["path_states"] if c == 2]
    assert band_arrivals and min(band_arrivals) >= 12
    assert payload["metrics"]["arrival_slice"] >= 12


def test_plan_4d_reports_earth_view_along_an_unconstrained_route(client, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(
        main_module, "build_earth_visibility_series", _earth_series_with_a_dark_band(None)
    )
    payload = client.post(
        "/api/plan-4d", json=_body(start_utc="2026-09-01T00:00:00")
    ).json()
    assert payload["metrics"]["earth_visibility_enforced"] is False
    assert payload["metrics"]["moves_out_of_earth_view"] >= 1
    assert False in payload["path_earth_visible"]


# ── A1: the safe-haven rule through the endpoint ─────────────────────────────


def test_plan_4d_says_when_the_safe_haven_map_could_not_be_computed(client):
    """No epoch, no horizon cube: the plan is made, the haven fields are
    None, and the SHERPA margins that CAN be computed still are (the
    battery is always known; a static, never-dark shadow field gives no
    time-to-shadow; no Earth series gives no time-to-DSN-shadow)."""
    payload = client.post("/api/plan-4d", json=_body()).json()
    assert payload["safe_haven_model"]["model"] == "unavailable"
    assert payload["safe_haven_model"]["reason"]
    assert payload["path_time_to_haven_h"] is None
    assert payload["path_hours_until_earthset"] is None
    assert payload["path_haven_margin_h"] is None
    metrics = payload["metrics"]
    assert metrics["safe_haven_enforced"] is False
    assert metrics["min_haven_margin_h"] is None
    assert metrics["ends_at_safe_haven"] is None
    assert metrics["time_to_zero_soc_min_h"] > 0.0
    assert metrics["time_to_sun_shadow_min_h"] is None
    assert metrics["time_to_dsn_shadow_min_h"] is None


def test_requiring_a_safe_haven_without_a_map_is_a_422(client):
    response = client.post("/api/plan-4d", json=_body(require_safe_haven=True))
    assert response.status_code == 422
    assert "safe haven" in response.json()["detail"]


def _fake_safe_haven_map(monkeypatch):
    """Havens: the top-left coarse block only (fine rows/cols 0..3)."""
    import app.main as main_module

    def _fake(grids, rover_id, start_utc, span_hours=708.7, step_hours=2.0):
        safe = np.zeros(SHAPE, dtype=bool)
        safe[:4, :4] = True
        layers = {
            "safe_haven": safe,
            "max_dark_hours_without_dte": np.where(safe, 10.0, 90.0),
            "earth_below_hours": np.full(SHAPE, 300.0),
            "ever_lit": np.ones(SHAPE, dtype=bool),
        }
        info = {
            "model": "spice_horizon",
            "start_utc": start_utc,
            "span_hours": span_hours,
            "step_hours": step_hours,
            "n_steps": 355,
            "rover_id": rover_id,
            "h_max_shadow_h": 50.0,
            "safe_haven_cells": 16,
            "traversable_cells": 256,
            "safe_haven_fraction": 16 / 256,
            "earth_below_fraction": 0.42,
        }
        return layers, np.where(safe, 0.0, 1.0), info

    monkeypatch.setattr(main_module, "safe_haven_for_grids", _fake)


def _earth_series_closing_at(close_slice: int | None):
    """Every cell linked until *close_slice*, unlinked from then on (never
    unlinked when None)."""
    import app.main as main_module

    def _fake(base, metadata, n_slices, slice_hours, start_utc=None):
        series = []
        for index in range(int(n_slices)):
            value = 1.0 if (close_slice is None or index < close_slice) else 0.0
            series.append(np.full(SHAPE, value))
        return series, {"model": "spice_horizon", "time_varying": True}

    return _fake


def test_plan_4d_enforces_the_safe_haven_rule_when_asked(client, monkeypatch):
    """The link closes 3 h in; the goal block is three diagonal 320 m
    steps (1.9 h of driving) from the only haven. Arriving there at 3 h
    is arriving with no way back: refused, with the reason named."""
    import app.main as main_module

    _fake_safe_haven_map(monkeypatch)
    monkeypatch.setattr(
        main_module, "build_earth_visibility_series", _earth_series_closing_at(3)
    )
    response = client.post(
        "/api/plan-4d",
        json=_body(require_safe_haven=True, start_utc="2026-09-01T00:00:00"),
    )
    assert response.status_code == 404, response.text
    detail = response.json()["detail"]
    assert "safe haven" in detail


def test_plan_4d_under_the_haven_rule_succeeds_when_the_link_holds(client, monkeypatch):
    import app.main as main_module

    _fake_safe_haven_map(monkeypatch)
    monkeypatch.setattr(
        main_module, "build_earth_visibility_series", _earth_series_closing_at(None)
    )
    response = client.post(
        "/api/plan-4d",
        json=_body(require_safe_haven=True, start_utc="2026-09-01T00:00:00"),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["safe_haven_model"]["model"] == "spice_horizon"
    assert payload["safe_haven_model"]["coarse_safe_haven_cells"] == 1
    metrics = payload["metrics"]
    assert metrics["safe_haven_enforced"] is True
    assert metrics["states_past_haven_deadline"] == 0
    assert metrics["ends_at_safe_haven"] is False
    assert metrics["edges_rejected"]["safe_haven_deadline"] == 0
    n_states = len(payload["path_states"])
    assert len(payload["path_time_to_haven_h"]) == n_states
    assert payload["path_time_to_haven_h"][0] == 0.0
    assert payload["path_time_to_haven_h"][-1] > 0.0
    # No Earthset within the horizon or the lookahead: open-ended.
    assert all(value is None for value in payload["path_hours_until_earthset"])
    assert metrics["min_haven_margin_h"] is None
    assert metrics["time_to_dsn_shadow_min_h"] is None


def test_plan_4d_reports_the_haven_margin_without_enforcing_it(client, monkeypatch):
    import app.main as main_module

    _fake_safe_haven_map(monkeypatch)
    monkeypatch.setattr(
        main_module, "build_earth_visibility_series", _earth_series_closing_at(3)
    )
    payload = client.post(
        "/api/plan-4d", json=_body(start_utc="2026-09-01T00:00:00")
    ).json()
    metrics = payload["metrics"]
    assert metrics["safe_haven_enforced"] is False
    assert metrics["states_past_haven_deadline"] >= 1
    assert metrics["min_haven_margin_h"] < 0.0
    assert metrics["time_to_dsn_shadow_min_h"] == 0.0
    assert payload["path_hours_until_earthset"][0] == pytest.approx(3.0)



# ── The continuous-illumination corridor (A2) ────────────────────────────────


def _shadow_series_lit_until(lit_until: int | None):
    """Every fine cell lit (shadow 0) for slices before *lit_until*, dark from
    then on (never dark when None); labelled as the real SPICE series."""

    def _fake(base, metadata, n_slices, slice_hours, start_utc=None):
        series = []
        for index in range(int(n_slices)):
            value = 0.0 if (lit_until is None or index < lit_until) else 1.0
            series.append(np.full(SHAPE, value))
        return series, {"model": "spice_horizon", "time_varying": True, "start_utc": start_utc}

    return _fake


def _shadow_series_with_a_dark_goal_block():
    """Lit everywhere except the coarse block holding the default goal."""

    def _fake(base, metadata, n_slices, slice_hours, start_utc=None):
        series = []
        for _ in range(int(n_slices)):
            snap = np.zeros(SHAPE)
            snap[12:16, 12:16] = 1.0
            series.append(snap)
        return series, {"model": "spice_horizon", "time_varying": True}

    return _fake


def test_plan_4d_always_reports_the_illumination_corridor(client):
    payload = client.post("/api/plan-4d", json=_body()).json()
    block = payload["illumination_corridor"]
    assert block["enforced"] is False and block["lit_rule"] == "all"
    assert block["provenance"]["shadow_model"] == "static"
    assert block["provenance"]["time_varying"] is False
    assert "model" in block["provenance"]["claim"]
    assert "10.8" in block["provenance"]["uncertainty_note"]
    assert block["n_slices"] == 24
    assert block["grid"] == {"rows": 4, "cols": 4, "resolution_m": 320.0}
    metrics = payload["metrics"]
    assert "max_dwell_hours" in metrics
    assert "continuous_illumination" in metrics["edges_rejected"]
    assert metrics["continuous_illumination_enforced"] is False
    assert metrics["states_outside_corridor"] is not None


def test_requiring_continuous_illumination_on_a_static_series_is_a_422(client):
    response = client.post("/api/plan-4d", json=_body(require_continuous_illumination=True))
    assert response.status_code == 422
    assert "static" in response.json()["detail"].lower()


def test_plan_4d_refuses_when_the_corridor_closes_before_the_window_ends(client, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "build_shadow_series", _shadow_series_lit_until(3))
    response = client.post(
        "/api/plan-4d",
        json=_body(require_continuous_illumination=True, start_utc="2026-09-01T00:00:00"),
    )
    assert response.status_code == 404, response.text
    detail = response.json()["detail"].lower()
    assert "corridor" in detail
    assert "start" in detail


def test_plan_4d_inside_the_corridor_never_enters_shadow(client, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "build_shadow_series", _shadow_series_lit_until(None))
    response = client.post(
        "/api/plan-4d",
        json=_body(require_continuous_illumination=True, start_utc="2026-09-01T00:00:00"),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    block = payload["illumination_corridor"]
    assert block["enforced"] is True
    assert block["provenance"]["shadow_model"] == "spice_horizon"
    assert block["route"]["inside"] is True
    assert block["route"]["states_inside"] == len(payload["path_states"])
    # Everything lit and connected: nothing to prune.
    assert block["voxels"]["corridor"] == block["voxels"]["lit_safe"] > 0
    assert block["start"]["in_corridor_t0"] is True
    assert block["goal"]["reachable_in_corridor"] is True
    assert all(d == 0.0 for d in payload["path_dark_hours"])
    metrics = payload["metrics"]
    assert metrics["max_dwell_hours"] > 0.0
    assert metrics["max_dwell_hours"] == block["route"]["max_dwell_hours"]
    assert metrics["continuous_illumination_enforced"] is True
    assert metrics["edges_rejected"]["continuous_illumination"] == 0
    assert metrics["states_outside_corridor"] == 0


def test_plan_4d_names_a_goal_the_corridor_never_reaches(client, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "build_shadow_series", _shadow_series_with_a_dark_goal_block())
    refused = client.post(
        "/api/plan-4d",
        json=_body(require_continuous_illumination=True, start_utc="2026-09-01T00:00:00"),
    )
    assert refused.status_code == 404, refused.text
    detail = refused.json()["detail"].lower()
    assert "corridor" in detail and "goal" in detail
    # Unenforced, the same request succeeds and the block says where it leaves.
    free = client.post("/api/plan-4d", json=_body(start_utc="2026-09-01T00:00:00"))
    assert free.status_code == 200, free.text
    payload = free.json()
    block = payload["illumination_corridor"]
    assert block["goal"]["corridor_slices"] == 0
    assert block["goal"]["reachable_in_corridor"] is False
    assert block["route"]["inside"] is False
    assert payload["metrics"]["states_outside_corridor"] >= 1
    assert payload["metrics"]["continuous_illumination_enforced"] is False


def test_plan_4d_accepts_the_majority_lit_rule_and_rejects_others(client, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "build_shadow_series", _shadow_series_lit_until(None))
    payload = client.post(
        "/api/plan-4d", json=_body(lit_rule="majority", start_utc="2026-09-01T00:00:00")
    ).json()
    assert payload["illumination_corridor"]["lit_rule"] == "majority"
    assert client.post("/api/plan-4d", json=_body(lit_rule="mostly")).status_code == 422


def test_plan_4d_combines_the_corridor_with_the_safe_haven_rule(client, monkeypatch):
    import app.main as main_module

    _fake_safe_haven_map(monkeypatch)
    monkeypatch.setattr(
        main_module, "build_earth_visibility_series", _earth_series_closing_at(None)
    )
    monkeypatch.setattr(main_module, "build_shadow_series", _shadow_series_lit_until(None))
    response = client.post(
        "/api/plan-4d",
        json=_body(
            require_safe_haven=True,
            require_continuous_illumination=True,
            start_utc="2026-09-01T00:00:00",
        ),
    )
    assert response.status_code == 200, response.text
    metrics = response.json()["metrics"]
    assert metrics["safe_haven_enforced"] is True
    assert metrics["continuous_illumination_enforced"] is True
    assert metrics["states_past_haven_deadline"] == 0



# ── GET /api/illumination-corridor ───────────────────────────────────────────

_CORRIDOR_QUERY = "/api/illumination-corridor?start_utc=2026-09-01T00:00:00&n_slices=6&slice_hours=1.0&coarsen=4"


def test_illumination_corridor_manifest_describes_the_cube(client, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "build_shadow_series", _shadow_series_lit_until(None))
    response = client.get(_CORRIDOR_QUERY)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["n_slices"] == 6 and payload["slice_hours"] == 1.0
    assert payload["slice_hours_source"] == "request"
    assert payload["lit_rule"] == "all" and payload["coarsen"] == 4
    assert payload["grid"] == {"rows": 4, "cols": 4, "resolution_m": 320.0, "coarsen": 4}
    assert payload["shadow_model"]["model"] == "spice_horizon"
    assert payload["binary_format"]["shape"] == [6, 4, 4]
    assert payload["binary_format"]["order"] == "slice-major, then row-major"
    assert set(payload["fields"]) == {"corridor", "lit_safe", "dwell_hours"}
    for name, entry in payload["fields"].items():
        assert "format=f32" in entry["binary_url"] and f"field={name}" in entry["binary_url"]
    block = payload["corridor"]
    assert block["voxels"]["corridor"] == block["voxels"]["lit_safe"] == 6 * 16
    assert block["start"] is None and block["goal"] is None and block["route"]["inside"] is None
    assert "claim" in block["provenance"]


def test_illumination_corridor_binary_is_the_cube_as_float32(client, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "build_shadow_series", _shadow_series_lit_until(3))
    manifest = client.get(_CORRIDOR_QUERY).json()
    response = client.get(_CORRIDOR_QUERY + "&format=f32&field=corridor")
    assert response.status_code == 200, response.text
    assert len(response.content) == 6 * 4 * 4 * 4
    assert response.headers["X-Series-Field"] == "corridor"
    assert response.headers["X-Series-Slices"] == "6"
    assert response.headers["X-Series-Rows"] == "4" and response.headers["X-Series-Cols"] == "4"
    assert float(response.headers["X-Series-Resolution-M"]) == 320.0
    assert response.headers["X-Series-Coarsen"] == "4"
    assert response.headers["X-Series-Lit-Rule"] == "all"
    cube = np.frombuffer(response.content, dtype="<f4").reshape(6, 4, 4)
    assert set(np.unique(cube).tolist()) <= {0.0, 1.0}
    # Lit until slice 3 and dark after: nothing survives the backward pass.
    assert cube.sum() == manifest["corridor"]["voxels"]["corridor"] == 0
    lit = client.get(_CORRIDOR_QUERY + "&format=f32&field=lit_safe")
    assert np.frombuffer(lit.content, dtype="<f4").sum() == 3 * 16


def test_illumination_corridor_dwell_field_is_in_hours(client, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "build_shadow_series", _shadow_series_lit_until(None))
    response = client.get(_CORRIDOR_QUERY + "&format=f32&field=dwell_hours")
    assert response.status_code == 200, response.text
    cube = np.frombuffer(response.content, dtype="<f4").reshape(6, 4, 4)
    assert cube[0].max() == pytest.approx(6.0)  # six 1 h slices inside from t=0
    assert cube[5].max() == pytest.approx(1.0)


def test_illumination_corridor_validates_its_query(client, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "build_shadow_series", _shadow_series_lit_until(None))
    assert client.get(_CORRIDOR_QUERY + "&format=f32&field=nope").status_code == 422
    assert client.get(_CORRIDOR_QUERY + "&lit_rule=mostly").status_code == 422
    assert client.get(_CORRIDOR_QUERY + "&lit_rule=majority").json()["lit_rule"] == "majority"
    assert client.get("/api/illumination-corridor?start_utc=2026-09-01T00:00:00&coarsen=5").status_code == 422


def test_illumination_corridor_without_an_epoch_is_labelled_static(client):
    response = client.get("/api/illumination-corridor?n_slices=6&coarsen=4")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["shadow_model"]["model"] == "static"
    assert payload["slice_hours_source"] == "auto" and payload["slice_hours"] > 0.0
    assert payload["corridor"]["provenance"]["time_varying"] is False
