"""C3 on the real Site11 grid: the standard routes with the slip curve
applied, against the same routes with the curve removed in-process.

Skips without the processed grids, the horizon cube or the NAIF kernels.
Nothing here asserts a specific number of hours -- the report does the
measuring -- only the direction slip must push every figure in, that the
response carries the model's label, and that the slip-aware default
horizon stays under the cube cap on the long lunar-night route.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.constants import ROVERS
from app.data_loader import _P1_PROCESSED_DIR, load_preprocessed_grids
from app.main import MAX_PLAN_4D_SLICES, app

_KERNELS = Path(__file__).resolve().parent.parent / "kernels" / "lunapath.tm"

pytestmark = pytest.mark.skipif(
    not os.path.exists(os.path.join(_P1_PROCESSED_DIR, "metadata.json"))
    or not os.path.exists(os.path.join(_P1_PROCESSED_DIR, "horizon_map.npy"))
    or not _KERNELS.exists(),
    reason="needs lunapath/data/processed, horizon_map.npy and the NAIF kernels",
)

START = {"row": 358, "col": 494}
GOAL = {"row": 206, "col": 426}
# The nearest haven-to-haven leg the slip curve leaves feasible for VIPER on
# 2027-05-30 (8 coarse moves, ends at a haven); the standard 40-move leg is
# refused under the curve -- see the test below.
VIPER_SHORT_GOAL = {"row": 346, "col": 462}
NIGHT = ({"row": 186, "col": 34}, {"row": 494, "col": 450})


def _fresh_grids() -> dict:
    """Load the grids and force the cost grid to be rebuilt under the
    CURRENT catalogue, so a slip-free run does not reuse a slip-inclusive
    grid from disk (or the reverse)."""
    grids = load_preprocessed_grids()
    grids.pop("cost", None)
    grids["metadata"]["cost_model"] = "rebuild-for-test"
    return grids


@pytest.fixture()
def client():
    app.state.grids = _fresh_grids()
    c = TestClient(app)
    yield c
    app.state.grids = None


def _plan(client, rover_id: str, start_utc: str, start=START, goal=GOAL, **extra):
    body = {"start": start, "goal": goal, "rover_id": rover_id, "start_utc": start_utc, **extra}
    response = client.post("/api/plan-4d", json=body)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize(
    "rover_id, start_utc, goal, extra",
    [
        ("nasa_viper", "2027-05-30T00:00:00", VIPER_SHORT_GOAL, {"require_safe_haven": True}),
        ("lpr_1", "2026-09-28T00:00:00", GOAL, {}),
    ],
)
def test_the_route_takes_longer_with_slip_than_without(
    client, monkeypatch, rover_id, start_utc, goal, extra
):
    started = time.perf_counter()
    with_slip = _plan(client, rover_id, start_utc, goal=goal, **extra)
    block = with_slip["slip_model"]
    assert block["applied"] is True and block["validity"] == "MODEL"
    assert block["route"]["moves"] == with_slip["metrics"]["move_steps"]
    assert block["route"]["extra_hours"] > 0.0
    assert 0.0 < block["route"]["mean_slip"] < 0.9
    assert with_slip["n_slices"] <= MAX_PLAN_4D_SLICES

    for rid in ROVERS:
        monkeypatch.setitem(ROVERS[rid], "slip_curve", None)
    app.state.grids = _fresh_grids()
    slip_free = _plan(client, rover_id, start_utc, goal=goal, **extra)
    assert slip_free["slip_model"]["applied"] is False

    # Slip lengthens the drive; whatever route the planner now prefers, the
    # clock and the drive energy it reports cannot be lower than slip-free.
    assert with_slip["metrics"]["arrival_hours"] > slip_free["metrics"]["arrival_hours"]
    assert min(with_slip["path_battery_pct"]) <= min(slip_free["path_battery_pct"]) + 1e-6
    assert time.perf_counter() - started < 180.0


def test_vipers_standard_leg_is_refused_under_the_curve_for_the_battery(client, monkeypatch):
    """The finding of the C3 report, locked: the A1 haven-to-haven leg that
    planned at 32 percent minimum battery slip-free (and only 1.4 percent of
    SHERPA runs within reserve) cannot be driven under the slip curve
    without breaching the 20 percent reserve. The refusal must say so, and
    the same request must still plan once the curve is removed."""
    response = client.post(
        "/api/plan-4d",
        json={"start": START, "goal": GOAL, "rover_id": "nasa_viper",
              "start_utc": "2027-05-30T00:00:00", "require_safe_haven": True},
    )
    assert response.status_code == 404, response.text
    detail = response.json()["detail"].lower()
    assert "reserve" in detail and "battery" in detail

    for rid in ROVERS:
        monkeypatch.setitem(ROVERS[rid], "slip_curve", None)
    app.state.grids = _fresh_grids()
    slip_free = _plan(client, "nasa_viper", "2027-05-30T00:00:00", require_safe_haven=True)
    assert slip_free["metrics"]["ends_at_safe_haven"] is True
    assert min(slip_free["path_battery_pct"]) > 20.0


def test_the_lunar_night_route_still_fits_the_default_horizon(client):
    """113 gated coarse moves at LPR-1's 25 deg limit: the old worst-edge
    sizing overshoots the cube cap under slip; the fastest-route sizing
    must not."""
    start, goal = NIGHT
    payload = _plan(client, "lpr_1", "2026-09-13T00:00:00", start=start, goal=goal)
    assert payload["n_slices"] <= MAX_PLAN_4D_SLICES
    assert payload["metrics"]["arrival_slice"] < payload["n_slices"]
    assert payload["slip_model"]["applied"] is True
