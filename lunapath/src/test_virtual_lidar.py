#!/usr/bin/env python3
"""Virtual LiDAR scan unit tests. No DEM file, no ROS, no GPU required."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

_BACKEND_ROOT = str(Path(__file__).resolve().parent.parent.parent / "backend")
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from virtual_lidar import virtual_scan

# Fine resolution keeps the scan geometry (not the LunaPath 80 m grid) under
# test -- see the module-level limitation notice for why 80 m is unusable
# at LiDAR-scale ranges.
RES_M = 2.0
SHAPE = (60, 60)
ORIGIN = (30.0, 30.0)


def _approx(expected: float, tol: float):
    """Local tolerance helper.

    Deliberately NOT named pytest_* -- pytest treats module-level
    pytest_-prefixed functions as plugin hook implementations and errors
    out at collection time.
    """

    class _Approx:
        def __eq__(self, other):
            return abs(other - expected) <= tol

    return _Approx()


def _flat_grid() -> np.ndarray:
    return np.zeros(SHAPE, dtype=np.float64)


def test_downward_beam_hits_flat_ground_at_the_analytic_range():
    """sensor_height / tan(|angle|) is the exact flat-ground intercept."""
    elev = _flat_grid()
    scan = virtual_scan(
        elev, RES_M, *ORIGIN,
        sensor_height_m=1.0,
        n_azimuth=4,
        elevation_angles_deg=(-10.0,),
        max_range_m=20.0,
        range_step_m=0.05,
    )
    assert scan.shape[0] == 4  # one hit per azimuth
    expected_range = 1.0 / math.tan(math.radians(10.0))
    for east, north, _up in scan:
        assert math.hypot(east, north) == _approx(expected_range, 0.15)


def test_horizontal_beam_over_flat_ground_never_returns():
    """angle = 0 on flat terrain below sensor height: no intersection."""
    elev = _flat_grid()
    scan = virtual_scan(
        elev, RES_M, *ORIGIN,
        sensor_height_m=1.0,
        n_azimuth=8,
        elevation_angles_deg=(0.0,),
        max_range_m=20.0,
        range_step_m=0.1,
    )
    assert scan.shape == (0, 3)


def test_upward_beams_over_flat_ground_never_return():
    elev = _flat_grid()
    scan = virtual_scan(
        elev, RES_M, *ORIGIN,
        sensor_height_m=1.0,
        n_azimuth=8,
        elevation_angles_deg=(5.0, 10.0),
        max_range_m=20.0,
    )
    assert scan.shape == (0, 3)


def test_north_hit_lands_on_the_north_axis():
    """azimuth 0 = North: the hit point's north component should dominate."""
    elev = _flat_grid()
    scan = virtual_scan(
        elev, RES_M, *ORIGIN,
        sensor_height_m=1.0,
        n_azimuth=4,               # indices at 0, 90, 180, 270 deg
        elevation_angles_deg=(-10.0,),
        max_range_m=20.0,
        range_step_m=0.05,
    )
    north_hit = scan[0]
    assert north_hit[1] > 0.0          # north component positive
    assert abs(north_hit[0]) < 1e-3    # east component ~ 0


def test_east_hit_lands_on_the_east_axis():
    elev = _flat_grid()
    scan = virtual_scan(
        elev, RES_M, *ORIGIN,
        sensor_height_m=1.0,
        n_azimuth=4,
        elevation_angles_deg=(-10.0,),
        max_range_m=20.0,
        range_step_m=0.05,
    )
    east_hit = scan[1]  # index 1 of 4 = 90 deg = East
    assert east_hit[0] > 0.0
    assert abs(east_hit[1]) < 1e-3


def test_output_count_never_exceeds_beam_count():
    elev = _flat_grid()
    elev[35:, :] = -100.0  # a cliff south of the origin: guaranteed misses there
    scan = virtual_scan(
        elev, RES_M, *ORIGIN,
        n_azimuth=16,
        elevation_angles_deg=(-15.0, -5.0),
        max_range_m=15.0,
    )
    assert scan.shape[0] <= 16 * 2


def test_output_dtype_and_shape_when_empty():
    elev = _flat_grid()
    scan = virtual_scan(
        elev, RES_M, *ORIGIN,
        n_azimuth=4,
        elevation_angles_deg=(10.0,),
        max_range_m=5.0,
    )
    assert scan.shape == (0, 3)
    assert scan.dtype == np.float32


def test_origin_outside_grid_is_rejected():
    elev = _flat_grid()
    try:
        virtual_scan(elev, RES_M, 9999.0, 9999.0, max_range_m=5.0)
    except ValueError:
        return
    raise AssertionError("expected ValueError for an out-of-grid origin")


def test_a_ridge_produces_a_shorter_range_than_flat_ground():
    """A rise ahead should be hit sooner than the flat-ground intercept."""
    elev = _flat_grid()
    # Raise ground north of the origin so a downward beam meets it early.
    # The ridge must start *inside* the flat-ground intercept
    # (1.0 / tan(10 deg) ~= 5.67 m ~= 2.8 px at 2 m/px), otherwise the beam
    # has already returned off flat ground before reaching it and both
    # scans measure the same range.
    elev[:28, :] = 3.0
    scan_ridge = virtual_scan(
        elev, RES_M, *ORIGIN,
        sensor_height_m=1.0,
        n_azimuth=4,
        elevation_angles_deg=(-10.0,),
        max_range_m=20.0,
        range_step_m=0.05,
    )
    scan_flat = virtual_scan(
        _flat_grid(), RES_M, *ORIGIN,
        sensor_height_m=1.0,
        n_azimuth=4,
        elevation_angles_deg=(-10.0,),
        max_range_m=20.0,
        range_step_m=0.05,
    )
    north_ridge = math.hypot(scan_ridge[0][0], scan_ridge[0][1])
    north_flat = math.hypot(scan_flat[0][0], scan_flat[0][1])
    assert north_ridge < north_flat
