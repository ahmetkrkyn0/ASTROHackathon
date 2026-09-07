"""DEM error propagation (B3): the pure pieces, on synthetic inputs.

NASA's PGDA publishes 100 statistical clones of every 5 m/px south-polar
DEM. app.uncertainty runs each clone through LunaPath's own derivation
chain -- the same slope operator, the same traversability rule, the same
horizon marcher, the same energy arithmetic -- and reads off probabilities
and bands. These tests pin that chain on small hand-made grids; nothing
here needs the clone cache, the horizon cube or the NAIF kernels.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.horizon import horizon_map, march_distances_cells


# ── Task 0: the slope operator and the strided horizon ─────────────────────


def test_slope_deg_from_elevation_is_the_pipelines_gradient_formula():
    """The one formula both P1 and load_and_preprocess_dem use, exposed so
    every clone is sloped exactly like the production grid."""
    from app.data_loader import slope_deg_from_elevation

    rng = np.random.default_rng(3)
    elevation = rng.normal(0.0, 5.0, size=(9, 11)).cumsum(axis=1)
    res = 5.0
    dy, dx = np.gradient(elevation, res)
    expected = np.degrees(np.arctan(np.sqrt(dx**2 + dy**2)))
    np.testing.assert_array_equal(slope_deg_from_elevation(elevation, res), expected)


def _bumpy(shape=(40, 40), seed=11):
    rng = np.random.default_rng(seed)
    rows, cols = np.mgrid[: shape[0], : shape[1]]
    terrain = 30.0 * np.sin(rows / 4.0) * np.cos(cols / 5.0)
    terrain += rng.normal(0.0, 2.0, size=shape)
    return terrain


def test_strided_horizon_is_the_full_horizon_sampled_at_the_stride_cells():
    elev = _bumpy()
    roi = (6, 34, 5, 37)
    full = horizon_map(elev, 5.0, n_azimuth=8, max_range_m=120.0, roi=roi)
    strided = horizon_map(elev, 5.0, n_azimuth=8, max_range_m=120.0, roi=roi, stride=4)
    np.testing.assert_array_equal(strided, full[:, ::4, ::4])
    assert strided.shape == (8, 7, 8)


def test_explicit_steps_replace_the_computed_march():
    elev = _bumpy()
    by_range = horizon_map(elev, 5.0, n_azimuth=6, max_range_m=15.0)
    by_steps = horizon_map(
        elev, 5.0, n_azimuth=6, max_range_m=9999.0, steps_cells=np.array([1.0, 2.0, 3.0])
    )
    np.testing.assert_array_equal(by_steps, by_range)


def test_near_and_far_steps_partition_the_full_march():
    from app.uncertainty import near_far_steps

    full = march_distances_cells(5.0, 10000.0, 200)
    near, far = near_far_steps(5.0, near_range_m=1000.0, max_range_m=10000.0, max_steps=200)
    np.testing.assert_array_equal(np.concatenate([near, far]), full)
    assert near.size > 0 and far.size > 0
    assert near.max() * 5.0 <= 1000.0
    assert far.min() * 5.0 > 1000.0


def test_the_max_of_near_and_far_passes_is_the_single_pass_horizon():
    """The clone pipeline marches the near field on the clone and the far
    field on the surface once; with the steps partitioned this way the two
    maxima ARE the one-pass cube, not an approximation of it."""
    from app.uncertainty import near_far_steps

    elev = _bumpy((48, 48))
    roi = (10, 38, 10, 38)
    near, far = near_far_steps(5.0, near_range_m=40.0, max_range_m=150.0, max_steps=60)
    one_pass = horizon_map(elev, 5.0, n_azimuth=12, max_range_m=150.0, max_steps=60, roi=roi)
    near_cube = horizon_map(elev, 5.0, n_azimuth=12, roi=roi, steps_cells=near)
    far_cube = horizon_map(elev, 5.0, n_azimuth=12, roi=roi, steps_cells=far)
    np.testing.assert_array_equal(np.maximum(near_cube, far_cube), one_pass)
    # The far pass alone is not the whole story -- the near field matters.
    assert (near_cube > far_cube).any()


# ── Task 1: the clone cache and the synthetic fallback ─────────────────────


def test_pgda_urls_name_nasas_site_products():
    from app.uncertainty import clone_url, slperr_url, toterr_url

    assert clone_url("Site11", 7) == (
        "https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site11/Clones/"
        "Site11_final_adj_5mpp_0007_err.tif"
    )
    assert clone_url("Site11", 100).endswith("_0100_err.tif")
    assert toterr_url("Site11") == (
        "https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/Site11/Site11_final_adj_5mpp_toterr.tif"
    )
    assert slperr_url("Site01").endswith("/Site01/Site01_final_adj_5mpp_slperr.tif")
    with pytest.raises(ValueError):
        clone_url("Site11", 0)


def test_synthetic_clones_follow_the_surface_and_nasas_sigma():
    from app.uncertainty import synthetic_clones

    rng = np.random.default_rng(2)
    surface = rng.normal(800.0, 20.0, size=(40, 40))
    sigma_z = 0.4 + 0.2 * rng.random((40, 40))
    clones = synthetic_clones(surface, sigma_z, n=60, seed=5)
    assert clones.shape == (60, 40, 40)
    assert clones.dtype == np.float32
    error = clones.astype(np.float64) - surface[None]
    assert abs(float(error.mean())) < 0.05
    ratio = error.std(axis=0) / sigma_z
    assert 0.85 < float(ratio.mean()) < 1.15
    # Spatially correlated, as NASA's clones are (0.88 at one cell on Site11).
    field = error[0]
    lag1 = np.corrcoef(field[:, :-1].ravel(), field[:, 1:].ravel())[0, 1]
    assert lag1 > 0.5
    np.testing.assert_array_equal(synthetic_clones(surface, sigma_z, n=60, seed=5), clones)
    assert not np.array_equal(synthetic_clones(surface, sigma_z, n=60, seed=6), clones)


def test_synthetic_clones_refuse_to_invent_a_sigma():
    from app.uncertainty import synthetic_clones

    surface = np.zeros((8, 8))
    with pytest.raises(ValueError):
        synthetic_clones(surface, None, n=3, seed=0)
    with pytest.raises(ValueError):
        synthetic_clones(surface, np.full((8, 8), -1.0), n=3, seed=0)
    with pytest.raises(ValueError):
        synthetic_clones(surface, np.ones((4, 4)), n=3, seed=0)


def test_dem_clone_cache_round_trips_and_exposes_the_window(tmp_path):
    from app.uncertainty import (
        DEM_CLONES_FILENAME,
        DEM_CLONES_META_FILENAME,
        load_dem_clones,
        write_dem_clones,
    )

    assert load_dem_clones(str(tmp_path)) is None
    padded = np.arange(3 * 12 * 12, dtype=np.float32).reshape(3, 12, 12)
    meta = {
        "provenance": "synthetic",
        "site": "Site11",
        "window": {"row0": 2, "col0": 2, "rows": 8, "cols": 8},
        "near_range_m": 10.0,
        "clone_indices": [1, 2, 3],
    }
    write_dem_clones(str(tmp_path), padded, meta)
    assert (tmp_path / DEM_CLONES_FILENAME).exists()
    assert (tmp_path / DEM_CLONES_META_FILENAME).exists()

    clones = load_dem_clones(str(tmp_path), expected_shape=(8, 8))
    assert clones.n_clones == 3
    assert clones.elevation.shape == (3, 12, 12)
    assert clones.window.shape == (3, 8, 8)
    np.testing.assert_array_equal(clones.window, padded[:, 2:10, 2:10])
    assert clones.meta["provenance"] == "synthetic"
    assert clones.clone_indices == [1, 2, 3]
    with pytest.raises(ValueError):
        load_dem_clones(str(tmp_path), expected_shape=(9, 9))


def test_clone_horizon_cache_round_trips(tmp_path):
    from app.uncertainty import (
        CLONE_HORIZONS_FILENAME,
        load_clone_horizons,
        write_clone_horizons,
    )

    assert load_clone_horizons(str(tmp_path)) == (None, None)
    cubes = np.zeros((2, 4, 3, 3), dtype=np.float32)
    meta = {"stride": 4, "row_offset": 2, "col_offset": 2, "n_azimuth": 4}
    write_clone_horizons(str(tmp_path), cubes, meta)
    assert (tmp_path / CLONE_HORIZONS_FILENAME).exists()
    loaded, loaded_meta = load_clone_horizons(str(tmp_path))
    assert loaded.shape == (2, 4, 3, 3)
    assert loaded_meta["stride"] == 4
    bad = tmp_path / "bad"
    write_clone_horizons(str(bad), cubes, meta)
    del loaded  # a memmap holds the file open on Windows
    np.save(bad / CLONE_HORIZONS_FILENAME, np.zeros((4, 3, 3), dtype=np.float32))
    with pytest.raises(ValueError):
        load_clone_horizons(str(bad))


# ── Task 8 helpers: the cache builder's geometry and its clone check ───────


def test_padded_box_pads_the_window_and_clips_at_the_raster_edge():
    from app.uncertainty import padded_box

    box = padded_box(row_off=2400, col_off=2500, rows=500, cols=500, pad=200, raster_rows=3200, raster_cols=3200)
    assert (box["row0"], box["col0"], box["rows"], box["cols"]) == (2200, 2300, 900, 900)
    assert box["window"] == {"row0": 200, "col0": 200, "rows": 500, "cols": 500}
    # Near the raster's edge the pad is clipped and the window box says where it landed.
    box = padded_box(row_off=50, col_off=2650, rows=500, cols=500, pad=200, raster_rows=3200, raster_cols=3200)
    assert (box["row0"], box["col0"], box["rows"], box["cols"]) == (0, 2450, 750, 750)
    assert box["window"] == {"row0": 50, "col0": 200, "rows": 500, "cols": 500}
    assert box["pad_clipped"] is True
    with pytest.raises(ValueError):
        padded_box(row_off=50, col_off=2800, rows=500, cols=500, pad=200, raster_rows=3200, raster_cols=3200)


def test_clone_check_accepts_a_clone_of_this_window_and_rejects_another():
    from app.uncertainty import clone_check

    rng = np.random.default_rng(9)
    surface = rng.normal(800.0, 30.0, size=(30, 30))
    sigma = np.full((30, 30), 0.4)
    good = surface + sigma * rng.standard_normal((30, 30))
    check = clone_check(good, surface, sigma)
    assert check["ok"] is True
    assert abs(check["mean_error_m"]) < 0.1
    assert 0.7 < check["rms_ratio"] < 1.3
    # A window cut from the wrong place differs by metres, not decimetres.
    wrong = np.roll(surface, 3, axis=1)
    assert clone_check(wrong, surface, sigma)["ok"] is False
    # A copy of the surface is not a clone either (zero error).
    assert clone_check(surface.copy(), surface, sigma)["ok"] is False


# ── Task 2: P_traversable, slope sigma and the per-rover layer cache ───────


def _stack_with_slopes(slopes_deg: list[float], shape=(6, 6), res=5.0):
    """Clones whose gradient is a plane of the requested slope, so the
    interior slope of clone k is exactly slopes_deg[k]."""
    cols = np.arange(shape[1], dtype=np.float64) * res
    return np.stack(
        [np.tile(cols * np.tan(np.radians(s)), (shape[0], 1)) for s in slopes_deg]
    ).astype(np.float32)


def test_ensemble_slopes_apply_the_pipelines_operator_to_every_clone():
    from app.data_loader import slope_deg_from_elevation
    from app.uncertainty import ensemble_slopes

    clones = _stack_with_slopes([5.0, 15.0, 30.0])
    slopes = ensemble_slopes(clones, 5.0)
    assert slopes.shape == clones.shape
    for k in range(3):
        np.testing.assert_allclose(slopes[k], slope_deg_from_elevation(clones[k], 5.0), atol=1e-6)
    assert slopes[1, 2, 2] == pytest.approx(15.0, abs=1e-3)


def test_traversable_probability_is_the_fraction_of_clones_that_pass():
    from app.constants import get_rover
    from app.traversability import compute_traversability_bool
    from app.uncertainty import traversable_probability

    viper = get_rover("nasa_viper")      # 20 deg
    lpr = get_rover("lpr_1")             # 25 deg
    slopes = np.stack([np.full((4, 4), s) for s in (10.0, 22.0, 28.0)])
    thermal = np.full((4, 4), -60.0)
    thermal_min = np.full((4, 4), -100.0)
    elevation = np.zeros((4, 4))

    p, masks = traversable_probability(slopes, thermal, elevation, viper, thermal_min)
    assert p.dtype == np.float32 and p.shape == (4, 4)
    assert float(p[1, 1]) == pytest.approx(1.0 / 3.0)
    for k in range(3):
        np.testing.assert_array_equal(
            masks[k],
            compute_traversability_bool(slopes[k], thermal, elevation, rover=viper, thermal_min=thermal_min),
        )
    p_lpr, _ = traversable_probability(slopes, thermal, elevation, lpr, thermal_min)
    assert float(p_lpr[1, 1]) == pytest.approx(2.0 / 3.0)

    # The cold-end gate is a property of the (held) thermal field, not the clone.
    cold = thermal_min.copy()
    cold[0, 0] = -170.0
    p_cold, _ = traversable_probability(slopes, thermal, elevation, lpr, cold)
    assert float(p_cold[0, 0]) == 0.0
    # NaN elevation is impassable in every clone.
    holed = elevation.copy()
    holed[3, 3] = np.nan
    p_nan, _ = traversable_probability(slopes, thermal, holed, lpr, thermal_min)
    assert float(p_nan[3, 3]) == 0.0


def test_slope_sigma_is_the_ensemble_standard_deviation():
    from app.uncertainty import slope_sigma

    slopes = np.stack([np.full((3, 3), s) for s in (10.0, 12.0, 14.0)])
    sigma = slope_sigma(slopes)
    assert sigma.dtype == np.float32
    np.testing.assert_allclose(sigma, np.std(slopes, axis=0), atol=1e-6)


def _synthetic_grids(processed_dir: str, shape=(8, 8), res=5.0, amplitude=3.0) -> dict:
    """A small grid whose slopes straddle the rovers' limits at the default
    *amplitude* (metres per cell of random walk); a smaller amplitude gives
    a gentle, fully passable grid."""
    from app.constants import get_rover
    from app.data_loader import derive_thermal_fields

    rng = np.random.default_rng(4)
    elevation = 100.0 + rng.normal(0.0, 1.0, size=shape).cumsum(axis=1) * float(amplitude)
    dy, dx = np.gradient(elevation, res)
    slope = np.degrees(np.arctan(np.hypot(dx, dy)))
    shadow = np.full(shape, 0.3)
    sunlit = np.full(shape, 20.0)
    thermal, thermal_min = derive_thermal_fields(sunlit, shadow)
    rover = get_rover()
    return {
        "elevation": elevation,
        "slope": slope,
        "aspect": np.zeros(shape),
        "thermal": np.asarray(thermal, dtype=np.float64),
        "thermal_min": np.asarray(thermal_min, dtype=np.float64),
        "thermal_sunlit_peak": sunlit,
        "shadow_ratio": shadow,
        "traversable": np.ones(shape, dtype=bool),
        "cost": np.full(shape, 0.3),
        "metadata": {
            "origin": {"x": -32500.0, "y": 11000.0},
            "resolution_m": res,
            "shape": list(shape),
            "crs": "test",
            "processed_dir": processed_dir,
            "default_rover_id": rover["id"],
            "cost_weights": {"w_slope": 0.409, "w_energy": 0.259, "w_shadow": 0.142, "w_thermal": 0.19},
            "layer_validity": {"elevation": "MEASURED", "slope": "DERIVED", "traversable": "DERIVED"},
        },
    }


def _write_synthetic_cache(processed_dir, grids, n=6, seed=0, provenance="synthetic"):
    import os

    from app.uncertainty import (
        ELEVATION_SIGMA_FILENAME,
        SLOPE_SIGMA_NASA_FILENAME,
        synthetic_clones,
        write_dem_clones,
    )

    surface = grids["elevation"]
    sigma = np.full(surface.shape, 0.4, dtype=np.float32)
    os.makedirs(processed_dir, exist_ok=True)
    np.save(os.path.join(processed_dir, ELEVATION_SIGMA_FILENAME), sigma)
    np.save(os.path.join(processed_dir, SLOPE_SIGMA_NASA_FILENAME), np.full(surface.shape, 1.8, dtype=np.float32))
    clones = synthetic_clones(surface, sigma, n, seed)
    rows, cols = surface.shape
    write_dem_clones(
        processed_dir,
        clones,
        {
            "site": "Site11",
            "provenance": provenance,
            "product_url": "https://pgda.gsfc.nasa.gov/products/78",
            "window": {"row0": 0, "col0": 0, "rows": rows, "cols": cols},
            "near_range_m": 0.0,
            "clone_indices": list(range(1, n + 1)),
            "fetched_utc": "2026-09-04T00:00:00Z",
        },
    )
    return clones


def test_uncertainty_layers_are_computed_per_rover_and_cached(tmp_path):
    from app.uncertainty import clear_uncertainty_cache, uncertainty_layers_for_grids

    clear_uncertainty_cache()
    grids = _synthetic_grids(str(tmp_path))
    layers, info = uncertainty_layers_for_grids(grids, "lpr_1")
    assert layers is None
    assert info["model"] == "unavailable" and "build_dem_clone_cache" in info["reason"]

    _write_synthetic_cache(str(tmp_path), grids)
    layers, info = uncertainty_layers_for_grids(grids, "lpr_1")
    assert info["model"] == "synthetic"
    assert info["n_clones"] == 6
    assert set(layers) >= {"p_traversable", "slope_sigma", "elevation_sigma", "slope_sigma_nasa", "clone_traversable"}
    assert layers["p_traversable"].shape == (8, 8)
    assert layers["clone_traversable"].shape == (6, 8, 8)
    assert float(layers["p_traversable"].min()) >= 0.0 and float(layers["p_traversable"].max()) <= 1.0
    assert float(layers["elevation_sigma"][0, 0]) == pytest.approx(0.4)
    # Same request, same objects: the cache hit.
    again, _ = uncertainty_layers_for_grids(grids, "lpr_1")
    assert again["p_traversable"] is layers["p_traversable"]
    # Another rover is another computation (a 20 deg limit is stricter than 25).
    viper, _ = uncertainty_layers_for_grids(grids, "nasa_viper")
    assert viper["p_traversable"] is not layers["p_traversable"]
    assert float(viper["p_traversable"].sum()) <= float(layers["p_traversable"].sum())


def test_with_uncertainty_layers_extends_the_grids_and_the_provenance(tmp_path):
    from app.uncertainty import clear_uncertainty_cache, with_uncertainty_layers

    clear_uncertainty_cache()
    grids = _synthetic_grids(str(tmp_path))
    assert with_uncertainty_layers(grids, "lpr_1") is grids

    _write_synthetic_cache(str(tmp_path), grids)
    extended = with_uncertainty_layers(grids, "lpr_1")
    assert extended is not grids and "p_traversable" not in grids
    validity = extended["metadata"]["layer_validity"]
    # A synthesised ensemble is labelled as such, like the elevation-proxy shadow.
    assert validity["p_traversable"] == "SYNTHETIC"
    assert validity["slope_sigma"] == "SYNTHETIC"
    assert validity["elevation_sigma"] == "MODEL"
    assert validity["slope_sigma_nasa"] == "MODEL"
    pedigree = extended["metadata"]["dem_uncertainty"]
    assert pedigree["model"] == "synthetic"
    assert pedigree["thermal_field_held_fixed"] is True

    # NASA's real clones: derived layers, from measured elevation and NASA's error model.
    clear_uncertainty_cache()
    real_dir = tmp_path / "real"
    real = _synthetic_grids(str(real_dir))
    _write_synthetic_cache(str(real_dir), real, provenance="nasa_pgda_clones")
    validity = with_uncertainty_layers(real, "lpr_1")["metadata"]["layer_validity"]
    assert validity["p_traversable"] == "DERIVED"
    assert validity["slope_sigma"] == "DERIVED"
    assert pedigree["n_clones"] == 6
    assert pedigree["product_url"].startswith("https://pgda.gsfc.nasa.gov")
    assert "clone_traversable" not in extended  # the stack is not a layer
    # The input's metadata is untouched.
    assert "dem_uncertainty" not in grids["metadata"]


# ── Task 3: P_illuminated and the route's passability across clones ────────


def _clone_cubes(horizons_deg=(10.0, 20.0, 30.0), n_azimuth=4, shape=(2, 2)):
    """One cube per clone with the given horizon in azimuth bin 0 (north)
    and a flat 0 deg horizon elsewhere; cell (1, 1) is a no-horizon sentinel."""
    cubes = np.zeros((len(horizons_deg), n_azimuth) + shape, dtype=np.float32)
    for k, h in enumerate(horizons_deg):
        cubes[k, 0] = h
        cubes[k, :, 1, 1] = -90.0
    return cubes


def test_illuminated_probability_is_the_fraction_of_clones_that_see_the_sun():
    from app.uncertainty import illuminated_probability

    cubes = _clone_cubes()
    assert float(illuminated_probability(cubes, 0.0, 15.0)[0, 0]) == pytest.approx(1.0 / 3.0)
    assert float(illuminated_probability(cubes, 0.0, 25.0)[0, 0]) == pytest.approx(2.0 / 3.0)
    assert float(illuminated_probability(cubes, 0.0, 35.0)[0, 0]) == pytest.approx(1.0)
    assert illuminated_probability(cubes, 0.0, 15.0).dtype == np.float32
    # Looking east the horizon is flat in every clone: lit whenever the Sun is up.
    assert float(illuminated_probability(cubes, 90.0, 0.5)[0, 0]) == pytest.approx(1.0)
    # The sentinel cell keeps illuminated_mask's rule: lit iff the Sun is above the horizontal.
    assert float(illuminated_probability(cubes, 0.0, -1.0)[1, 1]) == 0.0
    assert float(illuminated_probability(cubes, 0.0, 1.0)[1, 1]) == 1.0


def test_illuminated_probability_series_follows_the_track():
    from app.uncertainty import illuminated_probability_series, uncertain_fraction

    cubes = _clone_cubes()
    track = [
        {"azimuth_grid_deg": 0.0, "elevation_deg": 5.0},
        {"azimuth_grid_deg": 0.0, "elevation_deg": 15.0},
        {"azimuth_grid_deg": 0.0, "elevation_deg": 25.0},
        {"azimuth_grid_deg": 0.0, "elevation_deg": 35.0},
    ]
    series = illuminated_probability_series(cubes, track)
    assert series.shape == (4, 2, 2)
    np.testing.assert_allclose(series[:, 0, 0], [0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0], atol=1e-6)
    assert uncertain_fraction(np.array([[0.0, 0.5], [1.0, 0.9]])) == pytest.approx(0.5)
    assert uncertain_fraction(np.array([[0.0, 1.0]])) == 0.0


def test_route_traversable_probability_reads_the_clone_masks_at_the_route():
    from app.uncertainty import route_traversable_probability

    masks = np.ones((3, 8, 8), dtype=bool)
    masks[1, 1, 1] = False   # clone 1 closes a fine cell in coarse block (0, 0)
    masks[2, 5, 5] = False   # clone 2 closes a fine cell in coarse block (1, 1)
    per_state, feasible = route_traversable_probability(masks, [(0, 0), (1, 1), (1, 0)], coarsen=4)
    np.testing.assert_allclose(per_state, [2.0 / 3.0, 2.0 / 3.0, 1.0], atol=1e-6)
    np.testing.assert_array_equal(feasible, [True, False, False])
    # At coarsen 1 the cells are fine cells.
    per_state, feasible = route_traversable_probability(masks, [(1, 1), (0, 0)], coarsen=1)
    np.testing.assert_allclose(per_state, [2.0 / 3.0, 1.0], atol=1e-6)
    np.testing.assert_array_equal(feasible, [True, False, True])


# ── Task 4: the route band across clones ───────────────────────────────────

_ROUTE = [(0, 0, 0), (0, 1, 1), (1, 2, 2), (1, 2, 3)]   # two moves, then a planned wait


def _static_sky(n_states: int, shadow: float = 0.3, n_slices: int = 40, slice_hours: float = 1.0):
    from app.stress_test import RouteSky

    return RouteSky(np.full((n_slices, n_states), shadow), None, None, None, slice_hours, time_varying=False)


def _band(clone_slopes, sherpa=None, sky=None, nominal_slope=None):
    from app.constants import get_rover
    from app.uncertainty import route_band

    rover = get_rover("lpr_1")
    sky = sky or _static_sky(len(_ROUTE))
    return route_band(
        _ROUTE,
        clone_slopes,
        resolution_m=80.0,
        rover=rover,
        slice_hours=1.0,
        skies=sky,
        initial_soc_frac=1.0,
        nominal_slope=np.full((4, 4), 3.0) if nominal_slope is None else nominal_slope,
        nominal_sky=sky,
        sherpa=sherpa,
    )


def test_identical_clones_give_a_band_of_zero_width_at_the_nominal():
    band = _band(np.stack([np.full((4, 4), 3.0)] * 5))
    assert band["n_clones"] == 5 and band["clones_priced"] == 5 and band["unpriceable"] == []
    assert band["reached"]["count"] == 5 and band["reached"]["fraction"] == 1.0
    for key in ("duration_h", "drive_hours", "gross_drive_wh", "battery_used_wh",
                "min_battery_pct", "final_battery_pct", "max_continuous_shadow_h"):
        dist = band["metrics"][key]
        assert dist["n"] == 5, key
        assert dist["p5"] == dist["p50"] == dist["p95"], key
        assert dist["p50"] == pytest.approx(band["nominal"][key], abs=1e-4), key
        assert dist["std"] == pytest.approx(0.0, abs=1e-9), key
    assert band["nominal"]["reached"] is True
    assert band["route"]["n_states"] == 4 and band["route"]["move_steps"] == 2


def test_steeper_clones_take_longer_and_burn_more():
    band = _band(np.stack([np.full((4, 4), 3.0 + 5.0 * k) for k in range(4)]))
    drive = band["per_clone"]["drive_hours"]
    energies = band["per_clone"]["gross_drive_wh"]
    assert drive == sorted(drive) and len(set(drive)) == 4
    assert energies == sorted(energies) and len(set(energies)) == 4
    assert band["metrics"]["drive_hours"]["p95"] > band["metrics"]["drive_hours"]["p5"]
    # The executed timeline follows the plan's schedule (SHERPA's "ahead:
    # hold" policy), so a slope error shows in duration only once it
    # exceeds the slice slack; here it does not.
    assert band["metrics"]["duration_h"]["p95"] >= band["metrics"]["duration_h"]["p5"]
    assert band["metrics"]["gross_drive_wh"]["max"] > band["nominal"]["gross_drive_wh"]
    # A wait leg costs no drive: the planned wait at state 3 is not a move.
    assert band["route"]["wait_steps"] == 1


def test_a_clone_the_travel_model_cannot_price_is_dropped_and_named():
    slopes = np.stack([np.full((4, 4), 3.0)] * 3)
    slopes[1] = 95.0   # past vertical: edge_travel_time_s is infinite
    band = _band(slopes)
    assert band["clones_priced"] == 2
    assert band["unpriceable"] == [1]
    assert band["metrics"]["duration_h"]["n"] == 2


def test_sherpa_runs_pool_across_clones_and_repeat_with_the_seed():
    slopes = np.stack([np.full((4, 4), 3.0 + 2.0 * k) for k in range(3)])
    first = _band(slopes, sherpa={"n_runs": 40, "seed": 3})
    second = _band(slopes, sherpa={"n_runs": 40, "seed": 3})
    assert first["sherpa"] == second["sherpa"]
    sherpa = first["sherpa"]
    assert sherpa["n_runs_total"] == 120 and sherpa["n_runs_per_clone"] == 40
    assert sherpa["completion"]["count"] <= 120
    assert len(sherpa["completion"]["ci95"]) == 2
    assert sherpa["metrics"]["duration_h"]["n"] == 120
    assert "speed_sigma" in sherpa["perturbations"]
    assert _band(slopes)["sherpa"] is None


def test_the_band_is_json_safe():
    import json

    band = _band(np.stack([np.full((4, 4), 3.0 + k) for k in range(3)]), sherpa={"n_runs": 5, "seed": 0})
    text = json.dumps(band)
    assert "Infinity" not in text and "NaN" not in text
