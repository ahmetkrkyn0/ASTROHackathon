"""Skyline matching tests.

The ambiguity tests are the ones that matter. A matcher that returns the
best-scoring cell on featureless terrain is reporting confident nonsense,
and the Phase 7 plan makes reporting that uncertainty a hard requirement.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.horizon import horizon_map
from app.skyline import (
    DEFAULT_AMBIGUITY_LIMIT,
    SkylineFix,
    expected_sun_angles,
    match_skyline,
)

_RESOLUTION_M = 5.0
_N_AZIMUTH = 16


def _ridged_dem(size: int = 24) -> np.ndarray:
    """A DEM with enough structure that cells look different from each other."""
    rows = np.arange(size, dtype=np.float64)[:, None]
    cols = np.arange(size, dtype=np.float64)[None, :]
    return (
        40.0 * np.sin(rows / 3.0)
        + 25.0 * np.cos(cols / 4.0)
        + 0.6 * rows * cols / size
    )


def _cube(dem: np.ndarray) -> np.ndarray:
    return horizon_map(
        dem, _RESOLUTION_M, n_azimuth=_N_AZIMUTH, max_range_m=200.0, max_steps=40
    )


def _metadata(shape) -> dict:
    return {
        "origin": {"x": 1000.0, "y": 2000.0},
        "resolution_m": _RESOLUTION_M,
        "shape": list(shape),
        "crs": "test",
    }


def test_a_cells_own_horizon_matches_that_cell():
    """The basic correctness claim: take the horizon the DEM says cell
    (7, 9) sees, and the matcher must return (7, 9)."""
    dem = _ridged_dem()
    cube = _cube(dem)
    observed = cube[:, 7, 9]

    fix = match_skyline(observed, cube)

    assert fix is not None
    assert (fix.row, fix.col) == (7, 9)
    assert fix.score == pytest.approx(0.0, abs=1e-6)


def test_an_exact_match_is_reported_as_confident():
    cube = _cube(_ridged_dem())
    fix = match_skyline(cube[:, 5, 5], cube)
    assert fix.is_confident


def test_a_noisy_observation_still_lands_in_the_neighbourhood():
    """Real observations are not exact. A small perturbation must not
    throw the match across the map."""
    dem = _ridged_dem()
    cube = _cube(dem)
    rng = np.random.default_rng(0)
    observed = cube[:, 10, 12] + rng.normal(0.0, 0.5, size=_N_AZIMUTH)

    fix = match_skyline(observed, cube)

    assert abs(fix.row - 10) <= 2
    assert abs(fix.col - 12) <= 2


def test_featureless_terrain_is_reported_as_ambiguous():
    """The failure this module exists to prevent: on a flat plateau every
    cell's horizon is identical, so the matcher must say it cannot tell
    them apart rather than returning a confident cell."""
    flat = np.zeros((20, 20), dtype=np.float64)
    cube = _cube(flat)

    fix = match_skyline(cube[:, 8, 8], cube)

    assert fix is not None
    assert not fix.is_confident
    assert fix.ambiguity_ratio >= DEFAULT_AMBIGUITY_LIMIT


def test_structured_terrain_is_less_ambiguous_than_flat_terrain():
    ridged_cube = _cube(_ridged_dem())
    flat_cube = _cube(np.zeros((24, 24), dtype=np.float64))

    ridged = match_skyline(ridged_cube[:, 9, 9], ridged_cube)
    flat = match_skyline(flat_cube[:, 9, 9], flat_cube)

    assert ridged.ambiguity_ratio < flat.ambiguity_ratio


def test_a_low_confidence_match_is_still_returned():
    """The caller is told the best guess AND that it is unreliable --
    silence would be a worse answer than a labelled one."""
    flat = np.zeros((12, 12), dtype=np.float64)
    cube = _cube(flat)
    fix = match_skyline(cube[:, 4, 4], cube)
    assert isinstance(fix, SkylineFix)
    assert not fix.confident


def test_the_search_mask_restricts_the_result_to_masked_cells():
    dem = _ridged_dem()
    cube = _cube(dem)
    mask = np.zeros(dem.shape, dtype=bool)
    mask[15:20, 15:20] = True

    fix = match_skyline(cube[:, 3, 3], cube, search_mask=mask)

    assert fix is not None
    assert mask[fix.row, fix.col]


def test_an_empty_search_mask_returns_no_match():
    dem = _ridged_dem()
    cube = _cube(dem)
    fix = match_skyline(cube[:, 3, 3], cube, search_mask=np.zeros(dem.shape, bool))
    assert fix is None


def test_a_mask_containing_the_true_cell_still_finds_it():
    dem = _ridged_dem()
    cube = _cube(dem)
    mask = np.zeros(dem.shape, dtype=bool)
    mask[5:12, 5:12] = True

    fix = match_skyline(cube[:, 8, 8], cube, search_mask=mask)

    assert (fix.row, fix.col) == (8, 8)


def test_metadata_converts_the_match_to_crs_metres():
    dem = _ridged_dem()
    cube = _cube(dem)
    fix = match_skyline(cube[:, 6, 6], cube, metadata=_metadata(dem.shape))
    assert np.isfinite(fix.x_m)
    assert np.isfinite(fix.y_m)


def test_without_metadata_the_cell_is_still_reported():
    dem = _ridged_dem()
    cube = _cube(dem)
    fix = match_skyline(cube[:, 6, 6], cube)
    assert (fix.row, fix.col) == (6, 6)
    assert np.isnan(fix.x_m)


def test_an_azimuth_bin_mismatch_is_rejected():
    cube = _cube(_ridged_dem())
    with pytest.raises(ValueError, match="azimuth"):
        match_skyline(np.zeros(_N_AZIMUTH + 3), cube)


def test_a_two_dimensional_cube_is_rejected():
    with pytest.raises(ValueError):
        match_skyline(np.zeros(4), np.zeros((4, 4)))


def test_a_two_dimensional_observation_is_rejected():
    cube = _cube(_ridged_dem())
    with pytest.raises(ValueError):
        match_skyline(np.zeros((2, _N_AZIMUTH)), cube)


def test_a_mask_of_the_wrong_shape_is_rejected():
    cube = _cube(_ridged_dem())
    with pytest.raises(ValueError, match="search_mask"):
        match_skyline(cube[:, 0, 0], cube, search_mask=np.ones((3, 3), dtype=bool))


def test_ambiguity_ratio_ignores_the_winners_immediate_neighbours():
    """Adjacent cells always look nearly identical, so if neighbours
    counted as runner-ups every correct match would read as ambiguous."""
    cube = _cube(_ridged_dem())
    fix = match_skyline(cube[:, 11, 11], cube)
    assert fix.is_confident


def test_the_fix_serialises_to_a_dict():
    cube = _cube(_ridged_dem())
    fix = match_skyline(cube[:, 4, 7], cube)
    payload = fix.to_dict()
    assert payload["row"] == 4
    assert "ambiguity_ratio" in payload
    assert "confident" in payload


# --- expected_sun_angles (requires NAIF kernels on disk) -------------------

import json
import pathlib

_KERNELS = pathlib.Path(__file__).resolve().parent.parent / "kernels" / "lunapath.tm"
_needs_kernels = pytest.mark.skipif(
    not _KERNELS.exists(), reason="NAIF kernels not fetched"
)


@_needs_kernels
def test_expected_sun_angles_returns_finite_angles():
    az, el = expected_sun_angles("2026-08-30T12:00:00", -69.4, 32.3)
    assert 0.0 <= az < 360.0
    assert -90.0 <= el <= 90.0


@_needs_kernels
def test_the_sun_stays_low_at_the_south_pole():
    """At 69.4 S the sun cannot be high in the sky -- solar elevation is
    bounded by roughly (90 - |lat|) plus the small lunar obliquity. A
    result outside that band would mean a frame error, not weather."""
    _, el = expected_sun_angles("2026-08-30T12:00:00", -69.4, 32.3)
    assert el < 25.0


@_needs_kernels
def test_grid_frame_and_true_frame_azimuths_differ_by_the_longitude():
    """For a polar stereographic CRS centred on the pole, grid north and
    true north diverge by exactly the site longitude. The two outputs of
    expected_sun_angles must show that rotation -- if they agree, the
    crs_wkt path silently returned the wrong frame (the Phase 2 bug)."""
    metadata_path = (
        pathlib.Path(__file__).resolve().parent.parent
        / "lunapath" / "data" / "processed" / "metadata.json"
    )
    if not metadata_path.exists():
        pytest.skip("processed metadata not present")
    crs = json.loads(metadata_path.read_text(encoding="utf-8"))["crs"]

    lon = 32.3
    true_az, _ = expected_sun_angles("2026-08-30T12:00:00", -69.4, lon)
    grid_az, _ = expected_sun_angles("2026-08-30T12:00:00", -69.4, lon, crs_wkt=crs)

    difference = (grid_az - true_az) % 360.0
    assert difference == pytest.approx(lon, abs=0.1)
