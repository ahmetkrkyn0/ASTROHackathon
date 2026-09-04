"""The DEM-clone ensemble (B3) on the checked-in Site11 grid.

test_uncertainty*.py pin the derivation chain on synthetic inputs. This
file asks the real cache -- NASA's clones for the shipped window, fetched by
scripts/build_dem_clone_cache.py -- the questions that only real data can
answer, and skips wherever the gitignored inputs are not on disk:

* the cached clones ARE clones of this window (zero-mean error, RMS equal
  to NASA's own toterr, spatially correlated);
* our ensemble slope sigma agrees with NASA's published slperr;
* p_traversable has the structure the planner expects;
* the surface DEM's two-pass horizon reproduces the production cube
  exactly, so the clone cubes are comparable to it;
* VIPER's haven-to-haven route gets its band end to end, in seconds.
"""

from __future__ import annotations

import os
import pathlib
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.data_loader import _P1_PROCESSED_DIR, load_preprocessed_grids
from app.main import app
from app.rover_grids import grids_for_rover
from app.uncertainty import (
    CLONE_HORIZONS_FILENAME,
    DEM_CLONES_FILENAME,
    DEM_CLONES_META_FILENAME,
    ELEVATION_SIGMA_FILENAME,
    clear_uncertainty_cache,
    load_clone_horizons,
    load_dem_clones,
    uncertain_fraction,
    uncertainty_layers_for_grids,
)

_KERNELS = pathlib.Path(__file__).resolve().parent.parent / "kernels" / "lunapath.tm"
_HORIZON = os.path.join(_P1_PROCESSED_DIR, "horizon_map.npy")
_METADATA = os.path.join(_P1_PROCESSED_DIR, "metadata.json")
_CLONES = os.path.join(_P1_PROCESSED_DIR, DEM_CLONES_FILENAME)
_CLONES_META = os.path.join(_P1_PROCESSED_DIR, DEM_CLONES_META_FILENAME)
_SIGMA = os.path.join(_P1_PROCESSED_DIR, ELEVATION_SIGMA_FILENAME)
_CLONE_HORIZONS = os.path.join(_P1_PROCESSED_DIR, CLONE_HORIZONS_FILENAME)

needs_clones = pytest.mark.skipif(
    not (os.path.exists(_METADATA) and os.path.exists(_CLONES) and os.path.exists(_CLONES_META) and os.path.exists(_SIGMA)),
    reason="the DEM clone cache (scripts/build_dem_clone_cache.py) is not on disk",
)
needs_clone_horizons = pytest.mark.skipif(
    not (
        _KERNELS.exists() and os.path.exists(_HORIZON) and os.path.exists(_CLONES)
        and os.path.exists(_CLONE_HORIZONS) and os.path.exists(_METADATA)
    ),
    reason="NAIF kernels, horizon_map.npy or the clone horizon cubes are not on disk",
)

#: The lunar day and pair B5 stress-tested: VIPER haven to haven (A1).
_EPOCH_VIPER = "2027-05-30T00:00:00"
_VIPER_START = {"row": 358, "col": 494}
_VIPER_GOAL = {"row": 206, "col": 426}


@pytest.fixture(scope="module")
def grids():
    clear_uncertainty_cache()
    return load_preprocessed_grids()


@pytest.fixture()
def client(grids):
    previous = getattr(app.state, "grids", None)
    with TestClient(app) as test_client:
        app.state.grids = grids
        yield test_client
    app.state.grids = previous


@needs_clones
def test_the_cached_clones_are_clones_of_this_window(grids):
    """clone - surface is zero-mean, its RMS is NASA's toterr RMS, and it is
    spatially correlated -- the three signatures of a real clone."""
    surface = np.asarray(grids["elevation"], dtype=np.float64)
    clones = load_dem_clones(_P1_PROCESSED_DIR, expected_shape=surface.shape)
    assert clones.meta["provenance"] == "nasa_pgda_clones"
    assert clones.n_clones >= 5
    toterr = np.load(_SIGMA).astype(np.float64)
    rms_sigma = float(np.sqrt(np.nanmean(toterr**2)))
    ratios = []
    for k in range(clones.n_clones):
        error = np.asarray(clones.window[k], dtype=np.float64) - surface
        assert abs(float(error.mean())) < 0.1, k
        ratios.append(float(np.sqrt(np.mean(error**2))) / rms_sigma)
    assert 0.8 < min(ratios) and max(ratios) < 1.2, (min(ratios), max(ratios))
    error = np.asarray(clones.window[0], dtype=np.float64) - surface
    lag1 = np.corrcoef(error[:, :-1].ravel(), error[:, 1:].ravel())[0, 1]
    assert lag1 > 0.5
    print(
        f"\n{clones.n_clones} clones: RMS(error)/RMS(toterr) {min(ratios):.3f}-{max(ratios):.3f}, "
        f"lag-1 correlation {lag1:.3f}, toterr median {np.nanmedian(toterr):.3f} m"
    )


@needs_clones
def test_the_ensemble_slope_sigma_agrees_with_nasas_slperr(grids):
    for_rover = grids_for_rover(grids, "nasa_viper")
    layers, info = uncertainty_layers_for_grids(for_rover, "nasa_viper")
    assert layers is not None, info
    assert info["model"] == "nasa_pgda_clones"
    ours = np.asarray(layers["slope_sigma"], dtype=np.float64)
    nasa = np.asarray(layers["slope_sigma_nasa"], dtype=np.float64)
    ratio = float(np.median(ours)) / float(np.median(nasa))
    assert 0.5 < ratio < 2.0, ratio
    corr = np.corrcoef(ours.ravel(), nasa.ravel())[0, 1]
    assert corr > 0.3
    print(
        f"\nslope sigma: ours median {np.median(ours):.3f} deg vs NASA slperr median "
        f"{np.median(nasa):.3f} deg (ratio {ratio:.3f}, correlation {corr:.3f}); "
        f"{info['n_clones']} clones"
    )


@needs_clones
@pytest.mark.parametrize("rover_id", ["nasa_viper", "lpr_1"])
def test_p_traversable_has_the_planners_structure(grids, rover_id):
    for_rover = grids_for_rover(grids, rover_id)
    layers, info = uncertainty_layers_for_grids(for_rover, rover_id)
    assert layers is not None, info
    p = np.asarray(layers["p_traversable"], dtype=np.float64)
    base = np.asarray(for_rover["traversable"], dtype=bool)
    assert p.shape == base.shape
    assert 0.0 <= p.min() and p.max() <= 1.0
    uncertain = uncertain_fraction(p)
    assert uncertain > 0.0
    # The ensemble and the shipped DEM disagree only at the margin.
    assert float(((p == 1.0) & ~base).mean()) < 0.01
    assert float(((p == 0.0) & base).mean()) < 0.01
    print(
        f"\n{rover_id}: certain-pass {float((p == 1.0).mean()):.4f}, certain-fail "
        f"{float((p == 0.0).mean()):.4f}, uncertain {uncertain:.4f} of cells; "
        f"base passable {float(base.mean()):.4f}"
    )


@needs_clone_horizons
def test_the_surface_two_pass_horizon_is_the_production_cube(grids):
    cubes, meta = load_clone_horizons(_P1_PROCESSED_DIR)
    assert meta["surf_check_max_abs_deg"] is not None
    assert meta["surf_check_max_abs_deg"] <= 1e-3
    assert meta["far_field_held_fixed"] is True
    stride, offset = int(meta["stride"]), int(meta["row_offset"])
    base = np.load(_HORIZON, mmap_mode="r")
    sampled = np.asarray(base[:, offset::stride, offset::stride], dtype=np.float64)
    assert tuple(cubes.shape[1:]) == sampled.shape
    diff = np.asarray(cubes[0], dtype=np.float64) - sampled
    # The clone's near field moves the horizon; the far field is shared.
    # Measured on Site11: mean |diff| 0.70 deg -- the adjacent cell often IS
    # the horizon at 5 m/px, and two cells' errors differ by ~0.22 m
    # (sigma 0.45 m, correlation 0.88), which is 2.5 deg at 5 m.
    assert float(np.abs(diff).max()) > 0.05
    assert float(np.abs(diff).mean()) < 5.0
    print(
        f"\nclone 1 vs surface horizon: mean |diff| {np.abs(diff).mean():.4f} deg, "
        f"p95 {np.percentile(np.abs(diff), 95):.3f} deg, max {np.abs(diff).max():.3f} deg; "
        f"neglected far-field shift <= {meta['neglected_horizon_shift_deg_max']} deg"
    )


@needs_clone_horizons
def test_uncertainty_series_on_the_real_grid(client):
    response = client.get(
        "/api/uncertainty-series",
        params={"start_utc": _EPOCH_VIPER, "n_slices": 24, "slice_hours": 1.0},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["model"] == "clone_horizon"
    assert payload["grid"]["rows"] == 125 and payload["grid"]["stride"] == 4
    fractions = payload["per_slice"]["uncertain_fraction"]
    assert len(fractions) == 24 and max(fractions) > 0.0
    print(
        f"\nP_illuminated {_EPOCH_VIPER}, 24 h: uncertain fraction p50 {np.median(fractions):.4f}, "
        f"max {max(fractions):.4f}; mean lit {np.mean(payload['per_slice']['mean']):.3f}; "
        f"{payload['n_clones']} clones"
    )


@needs_clone_horizons
def test_vipers_haven_to_haven_route_gets_its_dem_band(client):
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
    assert "uncertainty" in plan
    assert plan["uncertainty"]["n_clones"] >= 5

    t0 = time.perf_counter()
    response = client.post(
        "/api/dem-uncertainty",
        json={
            "path_states": plan["path_states"],
            "rover_id": "nasa_viper",
            "coarsen": 4,
            "slice_hours": plan["slice_hours"],
            "start_utc": _EPOCH_VIPER,
            "label": "viper haven to haven",
        },
    )
    elapsed = time.perf_counter() - t0
    assert response.status_code == 200, response.text
    out = response.json()
    assert out["sky_model"]["model"] == "clone_horizon", out["sky_model"]
    assert out["clones_priced"] == out["n_clones"]
    assert out["metrics"]["gross_drive_wh"]["n"] == out["n_clones"]
    assert out["nominal"]["reached"] is True
    assert abs(out["nominal"]["duration_h"] - plan["metrics"]["arrival_hours"]) <= plan["slice_hours"] + 1e-6
    assert out["metrics"]["gross_drive_wh"]["p95"] >= out["metrics"]["gross_drive_wh"]["p5"]
    assert elapsed < 60.0, elapsed
    m = out["metrics"]
    print(
        f"\nVIPER band over {out['n_clones']} clones: drive energy p5/p50/p95 "
        f"{m['gross_drive_wh']['p5']:.0f}/{m['gross_drive_wh']['p50']:.0f}/{m['gross_drive_wh']['p95']:.0f} Wh "
        f"(nominal {out['nominal']['gross_drive_wh']:.0f}), duration p5/p95 "
        f"{m['duration_h']['p5']:.2f}/{m['duration_h']['p95']:.2f} h, min battery p5 "
        f"{m['min_battery_pct']['p5']:.1f} %, route feasible {out['route_feasible']['fraction']}, "
        f"reached {out['reached']['fraction']}; {elapsed:.1f} s"
    )
