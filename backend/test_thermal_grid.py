"""Dedicated tests for app.thermal_grid, the SYNTHETIC fallback model.

It is a heuristic, and these assert the properties a heuristic still has to
have: stability against the crop, the right directional response, and a
bounded output. (Round 3 review, L-19.)
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))

from app.thermal_grid import (
    ELEV_REF_MAX_M,
    ELEV_REF_MIN_M,
    T_HIGH_C,
    T_LOW_C,
    generate_thermal_grid,
)


def _inputs(shape=(6, 6), elevation=500.0, slope=0.0, aspect=0.0):
    return (
        np.full(shape, elevation, dtype=np.float64),
        np.full(shape, slope, dtype=np.float64),
        np.full(shape, aspect, dtype=np.float64),
    )


def test_output_is_float32_and_shaped_like_the_input():
    grid = generate_thermal_grid(*_inputs(), 10.0)
    assert grid.shape == (6, 6)
    assert grid.dtype == np.float32


def test_temperature_rises_with_elevation():
    low = generate_thermal_grid(*_inputs(elevation=-1000.0), 10.0)
    high = generate_thermal_grid(*_inputs(elevation=3000.0), 10.0)
    assert high.mean() > low.mean()


def test_the_elevation_reference_is_fixed_not_window_relative():
    """The same elevation must yield the same temperature regardless of what
    else is in the window. (Round 3 review, L-3.)"""
    flat = generate_thermal_grid(*_inputs(elevation=500.0), 10.0)

    elevation, slope, aspect = _inputs(elevation=500.0)
    elevation[0, 0] = 3500.0  # one outlier that used to rescale everything
    with_outlier = generate_thermal_grid(elevation, slope, aspect, 10.0)

    assert with_outlier[3, 3] == pytest.approx(flat[3, 3], abs=1e-3)


def test_elevation_outside_the_reference_band_is_clamped():
    below = generate_thermal_grid(*_inputs(elevation=ELEV_REF_MIN_M - 5000.0), 10.0)
    above = generate_thermal_grid(*_inputs(elevation=ELEV_REF_MAX_M + 5000.0), 10.0)
    assert below.min() >= -250.0
    assert above.max() <= 130.0
    assert below.mean() < above.mean()


def test_a_slope_facing_the_sun_is_warmer_than_one_facing_away():
    elevation, slope, _ = _inputs(slope=20.0)
    facing = np.full(elevation.shape, 90.0)   # faces grid east
    away = np.full(elevation.shape, 270.0)    # faces grid west

    warm = generate_thermal_grid(
        elevation, slope, facing, 10.0, sun_azimuth_grid_deg=90.0
    )
    cold = generate_thermal_grid(
        elevation, slope, away, 10.0, sun_azimuth_grid_deg=90.0
    )
    assert warm.mean() > cold.mean()


def test_the_aspect_term_has_no_effect_on_flat_ground():
    elevation, slope, _ = _inputs(slope=0.0)
    north = generate_thermal_grid(elevation, slope, np.zeros_like(elevation), 10.0)
    south = generate_thermal_grid(
        elevation, slope, np.full_like(elevation, 180.0), 10.0
    )
    assert north == pytest.approx(south)


def test_a_rising_neighbour_casts_the_local_shadow_penalty():
    elevation = np.full((5, 5), 500.0)
    elevation[2, 2] = 400.0  # a pit: every neighbour rises above it
    slope = np.zeros((5, 5))
    aspect = np.zeros((5, 5))
    grid = generate_thermal_grid(elevation, slope, aspect, 10.0)
    assert grid[2, 2] < grid[0, 0]


def test_the_output_stays_inside_the_declared_band():
    rng = np.random.default_rng(11)
    elevation = rng.uniform(-4000.0, 5000.0, (20, 20))
    slope = rng.uniform(0.0, 40.0, (20, 20))
    aspect = rng.uniform(0.0, 360.0, (20, 20))
    grid = generate_thermal_grid(elevation, slope, aspect, 10.0)
    assert grid.min() >= -250.0
    assert grid.max() <= 130.0
    assert T_LOW_C < T_HIGH_C
