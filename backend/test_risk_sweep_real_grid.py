"""B2 on the real Site11 grid: the nominal cost grid locked to the v4 build
bit for bit, the clone slope sigma reaching the risk tails, the standard
routes under an alpha sweep on /api/plan-4d, and /api/risk-sweep.

Skips without the processed grids, the horizon cube or the NAIF kernels
(the v4 lock and the clone-sigma check need only the grids and the clone
cache). Nothing here asserts a specific route or hour -- the report does
the measuring -- only the contract: alpha never changes the physics, the
tail never sits below the mean, and the sources are named.
"""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.constants import get_rover
from app.data_loader import _P1_PROCESSED_DIR, load_preprocessed_grids
from app.main import app
from app.rover_grids import grids_for_rover
from app.uncertainty import DEM_CLONES_FILENAME

_KERNELS = Path(__file__).resolve().parent.parent / "kernels" / "lunapath.tm"
_HAS_GRIDS = os.path.exists(os.path.join(_P1_PROCESSED_DIR, "metadata.json"))
_HAS_CLONES = os.path.exists(os.path.join(_P1_PROCESSED_DIR, DEM_CLONES_FILENAME))
_HAS_HORIZON = os.path.exists(os.path.join(_P1_PROCESSED_DIR, "horizon_map.npy"))

needs_grids = pytest.mark.skipif(not _HAS_GRIDS, reason="needs lunapath/data/processed")
needs_clones = pytest.mark.skipif(
    not (_HAS_GRIDS and _HAS_CLONES), reason="needs the DEM clone cache beside the processed grids"
)
needs_kernels = pytest.mark.skipif(
    not (_HAS_GRIDS and _HAS_HORIZON and _KERNELS.exists()),
    reason="needs lunapath/data/processed, horizon_map.npy and the NAIF kernels",
)

START = {"row": 358, "col": 494}
GOAL = {"row": 206, "col": 426}
VIPER_SHORT_GOAL = {"row": 346, "col": 462}

# SHA-256 of the v4 cost grid (default weights) as computed by the C3 build
# on 5 Sept 2026, before B2 touched the cost path. risk_alpha=None must
# reproduce it byte for byte. Since C4 the grid also carries NASA's LDRM
# roughness as a fifth term whenever its cache is beside the processed
# grids (v5; digests in test_roughness_real_grid); the four-term v4 grid
# is what the same code produces with that layer removed, so the lock is
# applied to the layer-less base grids here.
V4_COST_SHA256 = {
    "lpr_1": "0e74607d668efa227af0357fde24a53a95636a6bf13cd11af9d97ac92f5c7bd1",
    "nasa_viper": "8788936cee3f8cde6cff1db5370fd9a09776e62f50c69e59a1a95581375ad3cf",
}


def _digest(grid: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(np.asarray(grid, dtype=np.float64)).tobytes()).hexdigest()


def _four_term_base(grids: dict) -> dict:
    """The loaded grids without the C4 roughness layer (a no-op when the
    cache is absent)."""
    base = {k: v for k, v in grids.items() if k != "roughness"}
    base["metadata"] = {k: v for k, v in grids["metadata"].items() if k != "roughness"}
    return base


@needs_grids
def test_the_nominal_cost_grid_is_the_v4_grid_bit_for_bit():
    grids = _four_term_base(load_preprocessed_grids())
    for rover_id, digest in V4_COST_SHA256.items():
        assert _digest(grids_for_rover(grids, rover_id)["cost"]) == digest
        assert _digest(grids_for_rover(grids, rover_id, None, risk_alpha=None)["cost"]) == digest


@needs_clones
def test_the_clone_slope_sigma_reaches_the_risk_tails():
    grids = load_preprocessed_grids()
    nominal = grids_for_rover(grids, "lpr_1")
    tail = grids_for_rover(grids, "lpr_1", None, risk_alpha=0.9)
    assert tail["metadata"]["risk"]["slope_sigma_source"] == "dem_clones"
    assert tail["metadata"]["risk"]["n_clones"] >= 20
    assert tuple(np.asarray(tail["slope_sigma"]).shape) == tuple(np.asarray(grids["slope"]).shape)
    finite = np.isfinite(nominal["cost"])
    assert np.array_equal(np.isinf(nominal["cost"]), np.isinf(tail["cost"]))
    assert np.all(tail["cost"][finite] >= nominal["cost"][finite])
    assert np.mean(tail["cost"][finite] > nominal["cost"][finite]) > 0.5
    assert np.array_equal(nominal["traversable"], tail["traversable"])


@pytest.fixture()
def client():
    app.state.grids = load_preprocessed_grids()
    c = TestClient(app)
    yield c
    app.state.grids = None


def _plan_4d(client, rover_id, start_utc, goal, alpha, **extra):
    body = {"start": START, "goal": goal, "rover_id": rover_id, "start_utc": start_utc, **extra}
    if alpha is not None:
        body["risk_alpha"] = alpha
    response = client.post("/api/plan-4d", json=body)
    assert response.status_code == 200, response.text
    return response.json()


@needs_kernels
@pytest.mark.parametrize(
    "rover_id, start_utc, goal, extra",
    [
        ("lpr_1", "2026-09-28T00:00:00", GOAL, {}),
        ("nasa_viper", "2027-05-30T00:00:00", VIPER_SHORT_GOAL, {"require_safe_haven": True}),
    ],
)
def test_plan_4d_under_an_alpha_sweep_keeps_the_mean_physics(client, rover_id, start_utc, goal, extra):
    started = time.perf_counter()
    nominal = _plan_4d(client, rover_id, start_utc, goal, None, **extra)
    assert nominal["risk"]["applied"] is False and nominal["risk"]["route"] is None
    assert nominal["risk"]["sigma_sources"]["slope"]["source"] in ("dem_clones", "none")
    for alpha in (0.9, 0.99):
        payload = _plan_4d(client, rover_id, start_utc, goal, alpha, **extra)
        block = payload["risk"]
        assert block["applied"] is True and block["alpha"] == alpha and block["validity"] == "MODEL"
        if _HAS_CLONES:
            assert block["sigma_sources"]["slope"]["source"] == "dem_clones"
            assert block["criteria"] == {"slope": "cvar", "energy": "cvar"}
            assert block["route"]["slope_sigma_known_fraction"] > 0.9
        route = block["route"]
        assert route["moves"] == payload["metrics"]["move_steps"]
        assert route["risk_adjusted_hours"] >= route["hours"] > 0.0
        assert route["mean_slip_cvar"] > route["mean_slip_mu"] > 0.0
        # The slope tail is capped at the rover's own limit.
        assert route["max_slope_cvar_deg"] <= float(get_rover(rover_id)["slope_max_deg"]) + 1e-9
        assert route["hours_factor"] >= 1.0
        # Alpha reorders; it does not re-time. Same states => same clock and battery.
        if payload["path_states"] == nominal["path_states"]:
            assert payload["metrics"]["arrival_hours"] == nominal["metrics"]["arrival_hours"]
            assert payload["path_battery_pct"] == nominal["path_battery_pct"]
        assert payload["slip_model"]["applied"] is True
    assert time.perf_counter() - started < 240.0


@needs_kernels
def test_risk_sweep_on_the_standard_lpr1_pair(client):
    started = time.perf_counter()
    response = client.post("/api/risk-sweep", json={"start": START, "goal": GOAL, "rover_id": "lpr_1"})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["alphas"] == [None, 0.5, 0.9, 0.99]
    assert len(payload["results"]) == 4
    for entry in payload["results"]:
        assert entry["error"] is None and entry["plan_ms"] < 5000.0
        assert 0.0 <= entry["overlap_with_nominal"] <= 1.0
    assert payload["comparison"] is not None and len(payload["comparison"]["deltas"]) == 3
    hours = payload["risk_matrix"]["risk_adjusted_hours"]
    assert all(row[0] <= row[1] <= row[2] for row in hours)
    if _HAS_CLONES:
        assert payload["sigma_sources"]["slope"]["source"] == "dem_clones"
    assert time.perf_counter() - started < 60.0
