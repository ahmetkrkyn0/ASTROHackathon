"""Topographic horizon map tests."""

from __future__ import annotations

import numpy as np
import pytest

from app.horizon import horizon_map

RES_M = 80.0


def test_flat_terrain_without_curvature_has_zero_horizon():
    elevation = np.zeros((12, 12), dtype=np.float64)
    hz = horizon_map(elevation, RES_M, n_azimuth=4, max_range_m=400.0, curvature=False)
    assert hz.shape == (4, 12, 12)
    interior = hz[:, 2:-2, 2:-2]
    assert np.allclose(interior, 0.0, atol=1e-6)


def test_flat_terrain_with_curvature_has_negative_horizon():
    """Sphere curvature drops distant ground below the local horizontal."""
    elevation = np.zeros((12, 12), dtype=np.float64)
    hz = horizon_map(elevation, RES_M, n_azimuth=4, max_range_m=800.0, curvature=True)
    interior = hz[:, 2:-2, 2:-2]
    assert (interior < 0.0).all()


def test_east_facing_ramp_gives_ten_degree_horizon_to_the_east():
    """elev = col * res * tan(10 deg) -> looking east, horizon is 10 deg."""
    cols = np.arange(16, dtype=np.float64)
    elevation = np.tile(cols * RES_M * np.tan(np.radians(10.0)), (16, 1))
    hz = horizon_map(elevation, RES_M, n_azimuth=4, max_range_m=800.0, curvature=False)
    # n_azimuth=4 -> index 1 is 90 deg = East
    east = hz[1, 4:12, 2:10]
    assert east == pytest.approx(10.0, abs=0.05)


def test_east_facing_ramp_gives_negative_horizon_to_the_west():
    cols = np.arange(16, dtype=np.float64)
    elevation = np.tile(cols * RES_M * np.tan(np.radians(10.0)), (16, 1))
    hz = horizon_map(elevation, RES_M, n_azimuth=4, max_range_m=800.0, curvature=False)
    # index 3 is 270 deg = West (downhill)
    west = hz[3, 4:12, 6:14]
    assert (west < 0.0).all()


def test_azimuth_count_defines_first_axis():
    elevation = np.zeros((8, 8), dtype=np.float64)
    hz = horizon_map(elevation, RES_M, n_azimuth=12, max_range_m=240.0)
    assert hz.shape[0] == 12
    assert hz.dtype == np.float32


def test_max_steps_blocks_distant_obstruction_but_higher_cap_does_not():
    """max_range_m bounds the reach; max_steps only bounds the SAMPLING.

    This test used to assert the opposite -- that a tight ``max_steps``
    stopped the ray short of a distant spike. That WAS the behaviour, and it
    was the bug: at 5 m/px the default cap silently cut the nominal 10 km
    search to 1 km, and at a polar site the distant ridge seen at a low
    elevation angle is exactly what casts the long shadow. The march is now
    dense near and geometric far, so it reaches the full range whatever the
    sample budget, and it is ``max_range_m`` that decides what the ray can
    see. (Round 4 review, H-4 / L-10.)
    """
    fine_res_m = 5.0
    grid_size = 40
    elevation = np.zeros((grid_size, grid_size), dtype=np.float64)

    # Place a tall spike at (20, 30): that's 150m east from column 0.
    # At 5 m/px: 30 pixels = 150m.
    spike_row, spike_col = 20, 30
    spike_height = 500.0  # Tall enough to create ~73° horizon at 150m distance.
    elevation[spike_row, spike_col] = spike_height

    # A 100 m range genuinely cannot reach a spike 150 m away.
    capped = horizon_map(
        elevation, fine_res_m, n_azimuth=4, max_range_m=100.0,
        max_steps=200, curvature=False,
    )

    # A 10 km range reaches it -- on a budget of 20 samples, which under the
    # old uniform march would have stopped at 100 m.
    uncapped = horizon_map(
        elevation, fine_res_m, n_azimuth=4, max_range_m=10_000.0,
        max_steps=20, curvature=False,
    )

    # From pixel (spike_row, 0) looking east (azimuth=1 at n_azimuth=4):
    # - Capped: ray reaches column 20, misses spike at column 30 -> low horizon
    # - Uncapped: ray reaches column 50, sees spike at column 30 -> high horizon

    horizon_capped = capped[1, spike_row, 0]
    horizon_uncapped = uncapped[1, spike_row, 0]

    # Capped should be close to 0 (only sees flat terrain).
    assert horizon_capped < 5.0, \
        f"Capped ray (20 steps=100m) should not see spike at 150m, got {horizon_capped}°"

    # Uncapped should be ~arctan(500/150) ≈ 73°.
    assert horizon_uncapped > 60.0, \
        f"Uncapped ray should see 500m spike at 150m distance (≈73°), got {horizon_uncapped}°"

    # Also verify they differ significantly.
    assert horizon_uncapped - horizon_capped > 50.0, \
        f"Difference should be >50°: {horizon_uncapped}° - {horizon_capped}° = {horizon_uncapped - horizon_capped}°"


def test_max_steps_does_not_affect_coarse_grids_within_budget():
    """At 80 m/px a 10 km range is only 125 steps -- max_steps=200 must
    not change the result versus no cap at all."""
    elevation = np.zeros((10, 10), dtype=np.float64)
    capped = horizon_map(
        elevation, RES_M, n_azimuth=4, max_range_m=800.0,
        max_steps=200, curvature=False,
    )
    uncapped = horizon_map(
        elevation, RES_M, n_azimuth=4, max_range_m=800.0,
        max_steps=1_000_000, curvature=False,
    )
    assert np.array_equal(capped, uncapped)
