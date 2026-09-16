"""POST /api/reachable: the contract and every 422 it owes the caller (D6).

Runs on a small synthetic grid installed as ``app.state.grids``, so nothing
here needs the processed cache. The epoch-dependent paths are the exception:
without a horizon cube the shadow series cannot be time-varying, and the
endpoint is supposed to REFUSE rather than answer on a climatology -- so that
refusal is the thing asserted here and the real sweep is measured in
``test_reachability_real_grid.py``.
"""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app

SHAPE = (24, 24)
START_UTC = "2026-09-05T00:00:00"


def _grids() -> dict:
    height, width = SHAPE
    slope = np.full(SHAPE, 4.0, dtype=np.float64)
    elevation = np.zeros(SHAPE, dtype=np.float64)
    thermal = np.full(SHAPE, -20.0, dtype=np.float64)
    shadow = np.full(SHAPE, 0.4, dtype=np.float64)
    traversable = np.ones(SHAPE, dtype=bool)
    traversable[10, :] = False
    slope[10, :] = 60.0
    return {
        "metadata": {
            "shape": [height, width],
            "resolution_m": 5.0,
            "origin": {"x": 0.0, "y": 0.0},
            "default_rover_id": "lpr_1",
        },
        "elevation": elevation,
        "slope": slope,
        "aspect": np.zeros(SHAPE, dtype=np.float64),
        "shadow_ratio": shadow,
        "thermal": thermal,
        "traversable": traversable,
        "cost": np.ones(SHAPE, dtype=np.float64),
    }


@pytest.fixture()
def client():
    previous = getattr(app.state, "grids", None)
    app.state.grids = _grids()
    try:
        yield TestClient(app)
    finally:
        app.state.grids = previous


def _body(**overrides):
    body = {
        "start": {"row": 2, "col": 2},
        "rover_id": "lpr_1",
        "start_utc": START_UTC,
        "horizon_hours": 2.0,
        "coarsen": 4,
        "include_grids": False,
    }
    body.update(overrides)
    return body


# ── the refusals ─────────────────────────────────────────────────────────────


def test_a_static_shadow_series_is_refused_rather_than_answered(client):
    """The whole product is illumination-driven.

    ``build_shadow_series`` swallows every failure -- no kernel, no cache,
    no spiceypy -- and returns the long-run shadow FRACTION repeated. An
    isochrone on that measures the terrain and the battery while looking
    like a map of today, so it is a 422 that NAMES the model and the reason.
    Unlike /api/plan-4d there is nothing useful to degrade to.
    """
    response = client.post("/api/reachable", json=_body())
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "time-varying" in detail
    assert "static" in detail
    assert "climatology" in detail


def test_start_utc_is_required(client):
    body = _body()
    del body["start_utc"]
    assert client.post("/api/reachable", json=body).status_code == 422


def test_unknown_fields_are_refused(client):
    response = client.post("/api/reachable", json=_body(weights={"w_slope": 0.5}))
    assert response.status_code == 422


def test_weights_are_not_a_field_at_all(client):
    # Deliberate: no weight vector can make a block reachable or not, and
    # accepting one and ignoring it would be worse than refusing it.
    response = client.post("/api/reachable", json=_body(risk_alpha=0.9))
    assert response.status_code == 422


def test_a_start_charge_under_the_reserve_is_refused_with_the_reason(client):
    response = client.post("/api/reachable", json=_body(initial_soc_pct=0.1))
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "soc_min_pct" in detail
    assert "monotonicity" in detail


def test_a_grid_that_does_not_divide_is_refused(client):
    response = client.post("/api/reachable", json=_body(coarsen=5))
    assert response.status_code == 422
    assert "divisible" in response.json()["detail"]


def test_an_untraversable_start_block_is_refused(client):
    # Row 10 is a wall, so the coarse block containing it fails the
    # conservative AND that coarsen_traversable applies.
    response = client.post(
        "/api/reachable", json=_body(start={"row": 10, "col": 4})
    )
    assert response.status_code == 422
    assert "traversable" in response.json()["detail"]


def test_an_out_of_grid_start_is_refused_as_the_start(client):
    response = client.post("/api/reachable", json=_body(start={"row": 900, "col": 2}))
    assert response.status_code == 422
    # _validate_start_goal is handed the start twice; it must still say
    # "start", never "goal".
    assert "start" in response.json()["detail"]
    assert "goal" not in response.json()["detail"]


def test_band_edges_must_be_increasing_and_inside_the_horizon(client):
    response = client.post("/api/reachable", json=_body(band_hours=[2.0, 1.0]))
    assert response.status_code == 422
    assert "increasing" in response.json()["detail"]

    response = client.post("/api/reachable", json=_body(band_hours=[500.0]))
    assert response.status_code == 422
    assert "horizon" in response.json()["detail"]


def test_a_horizon_over_the_slice_cap_is_refused_with_the_number_that_fits(client):
    response = client.post(
        "/api/reachable", json=_body(horizon_hours=168.0, slice_hours=0.01)
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "slices" in detail
    assert "cap" in detail


def test_a_pathologically_short_slice_is_refused_by_the_work_bound(client):
    """A move costs ceil(travel_h / slice_hours) slices, so a very short
    slice multiplies the group count without changing the answer -- and
    without tripping any cap written in slices, blocks or bytes."""
    response = client.post(
        "/api/reachable", json=_body(horizon_hours=1.0, slice_hours=0.0002)
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "group" in detail or "slices" in detail


def test_later_hours_is_accepted_only_with_an_epoch(client):
    # start_utc is mandatory now, so the pairing is structural; this pins
    # that the field exists and validates.
    response = client.post("/api/reachable", json=_body(later_hours=-1.0))
    assert response.status_code == 422


def test_hold_slice_and_horizon_are_bounded(client):
    assert client.post("/api/reachable", json=_body(hold_slice_hours=0.0)).status_code == 422
    assert (
        client.post("/api/reachable", json=_body(hold_horizon_hours=100_000.0)).status_code
        == 422
    )


def test_include_grids_is_refused_when_the_response_would_be_a_raster(client):
    """/api/layers refuses a quarter-million JSON numbers; so does this."""
    # 67 600 blocks: over the 65 536-cell response ceiling and under the
    # 70 000-block sweep cap, so the grids check is the one that must fire.
    big = dict(_grids())
    big["metadata"] = {**big["metadata"], "shape": [260, 260]}
    for key in ("elevation", "slope", "aspect", "shadow_ratio", "thermal", "cost"):
        big[key] = np.zeros((260, 260), dtype=np.float64)
    big["traversable"] = np.ones((260, 260), dtype=bool)
    previous = app.state.grids
    app.state.grids = big
    try:
        response = client.post(
            "/api/reachable", json=_body(coarsen=1, include_grids=True)
        )
        assert response.status_code == 422
        assert "include_grids" in response.json()["detail"]
    finally:
        app.state.grids = previous


# ── the request model ────────────────────────────────────────────────────────


def test_request_defaults_are_the_documented_ones(client):
    from app.main import ReachableRequest

    model = ReachableRequest(start={"row": 1, "col": 1}, start_utc=START_UTC)
    assert model.rover_id == "lpr_1"
    assert model.coarsen == 4
    assert model.initial_soc_pct == 1.0
    assert model.include_grids is True
    assert model.later_hours is None
    assert model.hold_horizon_hours is None


def test_an_unknown_rover_is_a_422_not_a_500(client):
    response = client.post("/api/reachable", json=_body(rover_id="not_a_rover"))
    assert response.status_code == 422


# ── the endpoint exists and is additive ──────────────────────────────────────


def test_the_route_is_registered_once():
    paths = [route.path for route in app.routes if hasattr(route, "path")]
    assert paths.count("/api/reachable") == 1


def test_no_other_endpoint_changed_shape(client):
    # D6 is pure addition: the neighbours it sits between still answer.
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/rovers").status_code == 200
