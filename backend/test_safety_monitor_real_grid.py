"""The formal safety monitor (D3) on the checked-in Site11 grid.

test_safety_monitor*.py pin the semantics on synthetic traces. This file
asks the real routes the questions only real data can answer, and skips
wherever the gitignored inputs (processed grids, horizon cube, NAIF
kernels) are not on disk:

* on VIPER's haven-to-haven plan the monitor's margins are exactly the
  planner's own arrays read back (dark hours, battery, haven margin), and
  every rule the planner ENFORCED comes out satisfied;
* on the 2-D plan the shadow margin is the simulation summary's
  max_continuous_shadow_h (same 0.2 threshold), the SOC margin its
  min_battery_pct, the slope margin its worst grade;
* /api/compare ranks every profile it simulated;
* RTAMT and the built-in engine agree to the last bit on real traces.
"""

from __future__ import annotations

import os
import pathlib
import time

import pytest
from fastapi.testclient import TestClient

from app import safety_monitor as sm
from app.data_loader import _P1_PROCESSED_DIR, load_preprocessed_grids
from app.main import app

_KERNELS = pathlib.Path(__file__).resolve().parent.parent / "kernels" / "lunapath.tm"
_HORIZON = os.path.join(_P1_PROCESSED_DIR, "horizon_map.npy")
_METADATA = os.path.join(_P1_PROCESSED_DIR, "metadata.json")

needs_real_grid = pytest.mark.skipif(
    not (_KERNELS.exists() and os.path.exists(_HORIZON) and os.path.exists(_METADATA)),
    reason="NAIF kernels, horizon_map.npy or the processed grids are not on disk",
)

_client = TestClient(app)

START = {"row": 358, "col": 494}
GOAL = {"row": 206, "col": 426}
# Under the slip curve (C3) VIPER's 40-move leg to (206, 426) is refused for
# the battery reserve (test_slip_calibration_real_grid); the 4-D margins are
# read back on the nearest feasible haven-to-haven leg instead. The 2-D
# tests keep the standard pair.
VIPER_LEG_GOAL = {"row": 346, "col": 462}
VIPER_4D = {
    "rover_id": "nasa_viper",
    "start_utc": "2027-05-30T00:00:00",
    "start": START,
    "goal": VIPER_LEG_GOAL,
    "coarsen": 4,
    "require_safe_haven": True,
}


@pytest.fixture(scope="module")
def client():
    app.state.grids = load_preprocessed_grids()
    yield _client
    app.state.grids = None


def _by_id(block):
    return {entry["id"]: entry for entry in block["requirements"]}


@needs_real_grid
def test_viper_plan_4d_margins_are_the_planners_own_arrays_read_back(client):
    started = time.perf_counter()
    response = client.post("/api/plan-4d", json=VIPER_4D)
    elapsed = time.perf_counter() - started
    assert response.status_code == 200, response.text
    payload = response.json()
    block = payload["safety_margins"]
    r = _by_id(block)
    rover_h_max = 96.0
    assert block["monitor"]["trace"]["kind"] == "4d"
    assert block["monitor"]["trace"]["n_samples"] == len(payload["path_states"])
    assert r["LP-R01"]["rho"] == pytest.approx(rover_h_max - max(payload["path_dark_hours"]), abs=1e-4)
    assert r["LP-R02"]["rho"] == pytest.approx(min(payload["path_battery_pct"]) - 20.0, abs=1e-4)
    haven = payload["metrics"]["min_haven_margin_h"]
    if haven is None:
        assert r["LP-R09"]["open_ended"] is True
    else:
        assert r["LP-R09"]["rho"] == pytest.approx(haven, abs=1e-4)
    # Everything the planner enforced on this route must read back satisfied.
    for rid in ("LP-R01", "LP-R02", "LP-R06", "LP-R07", "LP-R09", "LP-R10"):
        assert r[rid]["applicable"] is True, rid
        assert r[rid]["satisfied"] is True, (rid, r[rid])
    assert r["LP-R08"]["applicable"] is True
    if sm.rtamt_available():
        assert block["monitor"]["engine"] == "rtamt"
        assert block["monitor"]["cross_check"]["max_abs_diff"] == 0.0
    assert block["min_margin"] is not None
    assert elapsed < 60.0


@needs_real_grid
def test_lpr1_without_a_reachable_haven_violates_the_leg_rule_unboundedly(client):
    # B5: on 2026-09-28 no safe haven is reachable from any state of this
    # route while the Earth link ends in ~184 h -- the leg rule cannot be
    # met at all, and the monitor must say so rather than call None "open".
    body = dict(VIPER_4D, goal=GOAL, rover_id="lpr_1", start_utc="2026-09-28T00:00:00", require_safe_haven=False)
    response = client.post("/api/plan-4d", json=body)
    assert response.status_code == 200, response.text
    payload = response.json()
    if all(v is None for v in payload["path_time_to_haven_h"]) and any(
        v is not None for v in payload["path_hours_until_earthset"]
    ):
        entry = _by_id(payload["safety_margins"])["LP-R09"]
        assert entry["satisfied"] is False and entry["rho"] is None
        assert "unbounded" in entry["reason"]
        assert "LP-R09" in payload["safety_margins"]["violated"]
    else:
        pytest.skip("the shipped haven map now finds a haven for LPR-1 on this day; nothing to assert")


@needs_real_grid
def test_viper_plan_2d_margins_are_the_simulation_summary_read_back(client):
    response = client.post("/api/plan", json={"start": START, "goal": GOAL, "rover_id": "nasa_viper"})
    assert response.status_code == 200, response.text
    payload = response.json()
    summary = payload["summary"]
    block = payload["safety_margins"]
    r = _by_id(block)
    assert block["monitor"]["trace"]["kind"] == "2d"
    assert r["LP-R01"]["rho"] == pytest.approx(96.0 - summary["max_continuous_shadow_h"], abs=1e-3)
    assert r["LP-R02"]["rho"] == pytest.approx(summary["min_battery_pct"] - 20.0, abs=1e-2)
    worst_grade = max(summary["max_slope_deg"], summary["max_segment_slope_deg"])
    assert r["LP-R06"]["rho"] == pytest.approx(20.0 - worst_grade, abs=1e-2)
    assert r["LP-R07"]["applicable"] is True and r["LP-R07"]["threshold"] == 15.0
    assert r["LP-R10"]["satisfied"] is (not summary["stranded"])
    assert r["LP-R08"]["applicable"] is False and r["LP-R09"]["applicable"] is False
    assert block["monitor"]["trace"]["stranded"] == summary["stranded"]
    if sm.rtamt_available():
        assert block["monitor"]["cross_check"]["max_abs_diff"] == 0.0


@needs_real_grid
def test_compare_ranks_every_profile_it_simulated(client):
    response = client.post("/api/compare", json={"start": [START["row"], START["col"]], "goal": [GOAL["row"], GOAL["col"]], "rover_id": "nasa_viper"})
    assert response.status_code == 200, response.text
    payload = response.json()
    simulated = [r for r in payload["results"] if r.get("safety_margins")]
    assert simulated
    ranking = payload["comparison"]["safety_margin_ranking"]
    assert [entry["label"] for entry in ranking] and {e["label"] for e in ranking} == {r["profile_id"] for r in simulated}
    for result in simulated:
        r = _by_id(result["safety_margins"])
        assert r["LP-R01"]["rho"] == pytest.approx(96.0 - result["simulation_summary"]["max_continuous_shadow_h"], abs=1e-3)
        # The boolean verdict and the signed margin must agree on the shadow rule.
        boolean = result["constraint_check"]["max_shadow_h"]["satisfied"]
        if boolean is not None and result["constraint_check"]["max_shadow_h"]["limit"] == 96.0:
            assert boolean == (r["LP-R01"]["rho"] >= 0.0)
