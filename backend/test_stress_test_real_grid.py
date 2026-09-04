"""The Monte Carlo stress test (B5) on the checked-in production grid.

test_stress_test*.py pin the protocol on synthetic routes and skies. This
file asks two things of Site11 with the real horizon cube and NAIF kernels,
and skips wherever the gitignored inputs are not on disk:

* the route-local sky the stress test builds is exactly the planner's cube
  read at the route's cells -- otherwise the runs would be about a
  different sky than the plan;
* VIPER's haven-to-haven route on the lunar day where a tenth of the site
  qualifies (A1) survives SHERPA's protocol end to end, in seconds.
"""

from __future__ import annotations

import os
import pathlib
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.cost_cube import coarsen_grid, coarsen_traversable
from app.data_loader import _P1_PROCESSED_DIR, load_preprocessed_grids
from app.earth_visibility import build_earth_visibility_series
from app.illumination_series import build_shadow_series, horizon_cache_path
from app.main import app
from app.rover_grids import grids_for_rover
from app.stress_test import route_sky_columns

_KERNELS = pathlib.Path(__file__).resolve().parent.parent / "kernels" / "lunapath.tm"
_HORIZON = os.path.join(_P1_PROCESSED_DIR, "horizon_map.npy")
_METADATA = os.path.join(_P1_PROCESSED_DIR, "metadata.json")

needs_real_inputs = pytest.mark.skipif(
    not (_KERNELS.exists() and os.path.exists(_HORIZON) and os.path.exists(_METADATA)),
    reason="NAIF kernels, horizon_map.npy or the processed grids are not on disk",
)

#: The lunar day where NASA VIPER's 96 h endurance buys a tenth of the site
#: as havens (A1), and the haven-to-haven pair its probe planned: coarse
#: (89,123) -> (51,106) at coarsen 4, i.e. these fine block centres.
_EPOCH_VIPER = "2027-05-30T00:00:00"
_VIPER_START = {"row": 358, "col": 494}
# The A1 pair's goal was (206, 426). Under the slip curve (C3) that 40-move
# leg is refused -- it would take the battery below the 20 percent reserve
# (test_slip_calibration_real_grid locks that verdict) -- so the protocol is
# exercised on the nearest haven-to-haven leg the curve leaves feasible:
# 8 coarse moves, ending at a haven, found by scanning the haven map from
# the same start by drive time.
_VIPER_GOAL = {"row": 346, "col": 462}
#: A lit, linked epoch on the way into the September night (A4 / A1).
_EPOCH_SUNRISE = "2026-09-22T00:00:00"


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
def test_route_sky_columns_are_the_planners_cubes_read_at_the_route(grids):
    """Twelve random traversable coarse cells over 24 half-hour slices at
    sunrise: the block-mean shadow and the block-AND Earth link the stress
    test computes for its cells equal what /api/plan-4d would have put in
    its cubes for them."""
    coarsen, n_slices, slice_hours = 4, 24, 0.5
    for_rover = grids_for_rover(grids, "lpr_1")
    metadata = for_rover["metadata"]
    coarse_passable = coarsen_traversable(for_rover["traversable"], coarsen)
    rng = np.random.default_rng(5)
    candidates = np.argwhere(coarse_passable)
    cells = [tuple(int(v) for v in candidates[i]) for i in rng.choice(len(candidates), 12, replace=False)]

    shadow_series, provenance = build_shadow_series(
        np.asarray(for_rover["shadow_ratio"], dtype=np.float64),
        metadata, n_slices, slice_hours, _EPOCH_SUNRISE,
    )
    assert provenance["time_varying"], provenance
    earth_series, earth_provenance = build_earth_visibility_series(
        None, metadata, n_slices, slice_hours, _EPOCH_SUNRISE
    )
    assert earth_provenance["time_varying"], earth_provenance
    rows = np.asarray([r for r, _ in cells])
    cols = np.asarray([c for _, c in cells])
    planner_shadow = np.stack(
        [coarsen_grid(snapshot, coarsen)[rows, cols] for snapshot in shadow_series]
    )
    planner_earth = np.stack(
        [coarsen_traversable(np.asarray(s) > 0.5, coarsen)[rows, cols] for s in earth_series]
    )

    horizon = np.load(horizon_cache_path(metadata), mmap_mode="r")
    t0 = time.perf_counter()
    shadow, earth = route_sky_columns(
        horizon, metadata, cells, coarsen, _EPOCH_SUNRISE, n_slices, slice_hours
    )
    elapsed = time.perf_counter() - t0
    np.testing.assert_allclose(shadow, planner_shadow, atol=1e-12)
    np.testing.assert_array_equal(earth, planner_earth)
    # The sky at some point varies over the day -- the comparison is not
    # between two constants.
    assert shadow.std() > 0.0
    assert elapsed < 5.0, elapsed


@needs_real_inputs
def test_vipers_haven_to_haven_route_survives_sherpas_protocol(client):
    """Plan a haven-to-haven leg from the A1 start under the leg rule (the
    nearest leg the slip curve leaves feasible, see _VIPER_GOAL), then
    stress it 1 000 times with SHERPA's defaults: the sky and the haven
    fields are the real ones, the
    unperturbed run reaches the haven, the summary is complete, and the
    whole thing takes seconds."""
    plan = client.post(
        "/api/plan-4d",
        json={
            "start": _VIPER_START,
            "goal": _VIPER_GOAL,
            "rover_id": "nasa_viper",
            "start_utc": _EPOCH_VIPER,
            "coarsen": 4,
            "require_safe_haven": True,
        },
    )
    assert plan.status_code == 200, plan.text
    plan = plan.json()
    assert plan["metrics"]["ends_at_safe_haven"] is True

    t0 = time.perf_counter()
    response = client.post(
        "/api/stress-test",
        json={
            "path_states": plan["path_states"],
            "rover_id": "nasa_viper",
            "coarsen": 4,
            "slice_hours": plan["slice_hours"],
            "start_utc": _EPOCH_VIPER,
            "n_runs": 1000,
            "seed": 0,
            "label": "viper haven to haven",
        },
    )
    elapsed = time.perf_counter() - t0
    assert response.status_code == 200, response.text
    out = response.json()

    assert out["sky_model"]["model"] == "spice_horizon"
    assert out["sky_model"]["n_slices_extended"] > plan["n_slices"]
    assert out["safe_haven_model"]["model"] == "spice_horizon"
    assert out["safe_haven_model"]["coarse_safe_haven_cells"] > 0
    assert out["route"]["n_states"] == len(plan["path_states"])
    assert out["route"]["ends_at_safe_haven"] is True
    assert out["nominal"]["reached"] is True
    # The nominal run's arrival agrees with the plan's clock to within a slice.
    assert abs(out["nominal"]["duration_h"] - plan["metrics"]["arrival_hours"]) <= plan["slice_hours"] + 1e-6
    # Every SHERPA margin is a number here: the Earth is up and the cells
    # go dark at some point in the extended horizon.
    for key in (
        "time_to_dsn_shadow_min_h",
        "time_to_zero_soc_min_h",
        "dsn_shadow_events",
        "states_past_haven_deadline",
        "min_battery_pct",
        "duration_h",
    ):
        assert out["metrics"][key] is not None and out["metrics"][key]["n"] == 1000, key
    assert out["rates"]["completion"]["count"] + sum(out["failures"].values()) == 1000
    assert len(out["per_state"]["alive_fraction"]) == out["route"]["n_states"]
    assert out["per_state"]["alive_fraction"][0] == 1.0
    assert elapsed < 20.0, elapsed
    print(
        f"\nVIPER haven->haven: {out['verdict']['text']} duration p50 "
        f"{out['metrics']['duration_h']['p50']} h, nominal {out['nominal']['duration_h']} h; "
        f"sky {out['timing_ms']['sky']:.0f} ms, runs {out['timing_ms']['runs']:.0f} ms, "
        f"total {out['timing_ms']['total']:.0f} ms"
    )
