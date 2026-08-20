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


def test_max_steps_bounds_the_effective_range_at_fine_resolution():
    """At 5 m/px, a naive 10 km max_range_m would take 2000 steps.
    max_steps caps this so runtime is resolution-independent."""
    fine_res_m = 5.0
    cols = np.arange(40, dtype=np.float64)
    elevation = np.tile(cols * fine_res_m * np.tan(np.radians(10.0)), (40, 1))
    hz = horizon_map(
        elevation, fine_res_m, n_azimuth=4, max_range_m=10_000.0,
        max_steps=20, curvature=False,
    )
    # With only 20 steps at 5 m/px, the effective range is 100 m -- far
    # short of the 10 km nominal max_range_m.
    assert hz.shape == (4, 40, 40)


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
