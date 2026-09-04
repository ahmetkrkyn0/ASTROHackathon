"""The continuous-illumination corridor (A2) on the checked-in Site11 grid.

test_illumination_corridor.py pins the pruning on hand-built volumes. This
file asks what the corridor says about Site11 with the real horizon cube
and NAIF kernels, and skips wherever the gitignored inputs are not on disk
(mirrors test_safe_haven_real_grid.py).

Measured 4 Sep 2026 (probe, then scripts/illumination_corridor_report.py):
on VIPER's best lunar day (2027-05-30) 40.5 percent of the coarse
traversable volume is lit under the "all" rule, yet the standard
haven-to-haven pair starts in a block that is dark at the first slice and
ends in one that is never lit -- so the corridor rule refuses it, by
design. A pair picked inside the corridor plans with zero shadow hours
and the full shadow-endurance margin. The lunar night of 2026-09-13 has
no lit block at all.
"""

from __future__ import annotations

import os
import pathlib
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import illumination_corridor as ic
from app.constants import get_rover
from app.data_loader import _P1_PROCESSED_DIR, load_preprocessed_grids
from app.illumination_series import build_shadow_series
from app.main import PlanWeights, _coarse_geometry, app
from app.rover_grids import grids_for_rover

_KERNELS = pathlib.Path(__file__).resolve().parent.parent / "kernels" / "lunapath.tm"
_HORIZON = os.path.join(_P1_PROCESSED_DIR, "horizon_map.npy")
_METADATA = os.path.join(_P1_PROCESSED_DIR, "metadata.json")

needs_real_inputs = pytest.mark.skipif(
    not (_KERNELS.exists() and os.path.exists(_HORIZON) and os.path.exists(_METADATA)),
    reason="NAIF kernels, horizon_map.npy or the processed grids are not on disk",
)

COARSEN = 4
VIPER_EPOCH = "2027-05-30T00:00:00"
NIGHT_EPOCH = "2026-09-13T00:00:00"
NIGHT_START, NIGHT_GOAL = (186, 34), (494, 450)
START = {"row": 358, "col": 494}
GOAL = {"row": 206, "col": 426}
# Under the slip curve (C3) the unconstrained plan to GOAL is refused for the
# battery reserve; the corridor block is read from the nearest feasible
# haven-to-haven leg. The corridor RULE is still tested on the standard pair
# (its start block is dark at the first slice either way).
VIPER_LEG_GOAL = {"row": 346, "col": 462}
#: The horizon and slice pinned so the test can rebuild the endpoint's
#: corridor to pick a pair inside it (the default horizon depends on the pair).
HORIZON_HOURS = 8.0
SLICE_HOURS = 0.1


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


def _plan(client, **body):
    return client.post("/api/plan-4d", json=body)


def _fine_centre(cell):
    return {"row": int(cell[0]) * COARSEN + COARSEN // 2, "col": int(cell[1]) * COARSEN + COARSEN // 2}


@needs_real_inputs
def test_viper_epoch_has_a_corridor_but_the_standard_route_starts_in_the_dark(client):
    free = _plan(client, start=START, goal=VIPER_LEG_GOAL, rover_id="nasa_viper", start_utc=VIPER_EPOCH)
    assert free.status_code == 200, free.text
    payload = free.json()
    block = payload["illumination_corridor"]
    assert block["provenance"]["shadow_model"] == "spice_horizon"
    assert block["enforced"] is False
    assert 0 < block["voxels"]["corridor"] <= block["voxels"]["lit_safe"]
    assert block["components"]["count"] >= 1
    assert block["start"]["in_corridor_t0"] is False
    assert block["route"]["inside"] is False
    assert payload["metrics"]["states_outside_corridor"] >= 1
    assert max(payload["path_dark_hours"]) > 0.0

    refused = _plan(
        client, start=START, goal=GOAL, rover_id="nasa_viper", start_utc=VIPER_EPOCH,
        require_continuous_illumination=True,
    )
    assert refused.status_code == 404, refused.text
    detail = refused.json()["detail"].lower()
    assert "corridor" in detail
    assert "start block" in detail


@needs_real_inputs
def test_a_pair_inside_the_corridor_plans_with_zero_shadow_and_the_full_margin(client, grids):
    rover = get_rover("nasa_viper")
    grids_for_plan = grids_for_rover(grids, "nasa_viper", PlanWeights().model_dump())
    geometry = _coarse_geometry(grids_for_plan, COARSEN)
    n_slices = int(np.ceil(HORIZON_HOURS / SLICE_HOURS))
    series, provenance = build_shadow_series(
        np.asarray(grids_for_plan["shadow_ratio"], dtype=np.float64),
        grids_for_plan["metadata"], n_slices, SLICE_HOURS, VIPER_EPOCH,
    )
    assert provenance["model"] == "spice_horizon"
    corridor = ic.build_corridor(
        series, geometry.traversable, geometry.elevation, geometry.slope,
        geometry.resolution_m, rover, COARSEN, SLICE_HOURS,
    )
    pair = ic.corridor_pair(corridor, near=(START["row"] // COARSEN, START["col"] // COARSEN))
    assert pair is not None, "no corridor block at the first slice of VIPER's epoch"
    start, goal, info = pair
    assert info["goal_chebyshev_cells"] >= 2

    started = time.perf_counter()
    enforced = _plan(
        client, start=_fine_centre(start), goal=_fine_centre(goal), rover_id="nasa_viper",
        start_utc=VIPER_EPOCH, horizon_hours=HORIZON_HOURS, slice_hours=SLICE_HOURS,
        require_continuous_illumination=True,
    )
    assert enforced.status_code == 200, enforced.text
    payload = enforced.json()
    block = payload["illumination_corridor"]
    assert block["enforced"] is True and block["route"]["inside"] is True
    assert block["start"]["in_corridor_t0"] is True
    assert block["goal"]["reachable_in_corridor"] is True
    assert all(d == 0.0 for d in payload["path_dark_hours"])
    assert payload["metrics"]["max_continuous_shadow_h"] == 0.0
    assert payload["metrics"]["states_outside_corridor"] == 0
    assert payload["metrics"]["max_dwell_hours"] > 0.0
    # D3's shadow-endurance requirement reads back the full endurance.
    by_id = {e["id"]: e for e in payload["safety_margins"]["requirements"]}
    assert by_id["LP-R01"]["rho"] == pytest.approx(float(rover["h_max_shadow_h"]), abs=1e-6)

    free = _plan(
        client, start=_fine_centre(start), goal=_fine_centre(goal), rover_id="nasa_viper",
        start_utc=VIPER_EPOCH, horizon_hours=HORIZON_HOURS, slice_hours=SLICE_HOURS,
    )
    assert free.status_code == 200, free.text
    assert free.json()["metrics"]["nodes_expanded"] >= 1
    assert time.perf_counter() - started < 120.0


@needs_real_inputs
def test_the_lunar_night_has_no_corridor_at_all(client):
    body = dict(
        start={"row": NIGHT_START[0], "col": NIGHT_START[1]},
        goal={"row": NIGHT_GOAL[0], "col": NIGHT_GOAL[1]},
        rover_id="lpr_1", start_utc=NIGHT_EPOCH,
    )
    free = _plan(client, **body)
    assert free.status_code == 200, free.text  # on battery, as before
    block = free.json()["illumination_corridor"]
    assert block["voxels"]["lit_safe"] == 0 and block["voxels"]["corridor"] == 0
    assert block["slices"]["first_lit"] is None
    assert block["components"]["count"] == 0
    refused = _plan(client, require_continuous_illumination=True, **body)
    assert refused.status_code == 404, refused.text
    assert "no block is lit" in refused.json()["detail"].lower()
