"""Sun azimuth/elevation geometry tests (no SPICE kernels required)."""

from __future__ import annotations

import numpy as np
import pytest

from app.ephemeris import (
    grid_azimuth_to_true_azimuth,
    sun_azel_from_vector,
    true_azimuth_to_grid_azimuth,
    true_north_grid_azimuth,
)

# The real south-polar-stereographic WKT the pipeline is running against,
# copied verbatim from lunapath/data/processed/metadata.json's "crs" field.
LUNAR_SOUTH_POLAR_WKT = (
    'PROJCS["unnamed",GEOGCS["unnamed ellipse",DATUM["unknown",'
    'SPHEROID["unnamed",1737400,0]],PRIMEM["Greenwich",0],'
    'UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]]],'
    'PROJECTION["Polar_Stereographic"],PARAMETER["latitude_of_origin",-90],'
    'PARAMETER["central_meridian",0],PARAMETER["false_easting",0],'
    'PARAMETER["false_northing",0],UNIT["metre",1],'
    'AXIS["Easting",NORTH],AXIS["Northing",NORTH]]'
)


def test_sun_overhead_at_equator_prime_meridian():
    az, el = sun_azel_from_vector(np.array([1.0, 0.0, 0.0]), lat_deg=0.0, lon_deg=0.0)
    assert el == pytest.approx(90.0, abs=1e-6)


def test_sun_due_east_at_equator_prime_meridian():
    az, el = sun_azel_from_vector(np.array([0.0, 1.0, 0.0]), lat_deg=0.0, lon_deg=0.0)
    assert el == pytest.approx(0.0, abs=1e-6)
    assert az == pytest.approx(90.0, abs=1e-6)


def test_sun_due_north_at_equator_prime_meridian():
    az, el = sun_azel_from_vector(np.array([0.0, 0.0, 1.0]), lat_deg=0.0, lon_deg=0.0)
    assert el == pytest.approx(0.0, abs=1e-6)
    assert az == pytest.approx(0.0, abs=1e-6)


def test_at_south_pole_body_x_axis_is_local_north():
    """At lat=-90 the +X body direction lies on the local horizon, due North."""
    az, el = sun_azel_from_vector(np.array([1.0, 0.0, 0.0]), lat_deg=-90.0, lon_deg=0.0)
    assert el == pytest.approx(0.0, abs=1e-6)
    assert az == pytest.approx(0.0, abs=1e-6)


def test_south_pole_sun_is_low_not_overhead():
    """A Sun vector 1.5 deg above the local horizon at the south pole."""
    elev_rad = np.radians(1.5)
    vec = np.array([np.cos(elev_rad), 0.0, -np.sin(elev_rad)])
    az, el = sun_azel_from_vector(vec, lat_deg=-90.0, lon_deg=0.0)
    assert el == pytest.approx(1.5, abs=1e-6)


def test_azimuth_is_normalised_to_zero_360():
    az, _ = sun_azel_from_vector(np.array([0.0, -1.0, 0.0]), lat_deg=0.0, lon_deg=0.0)
    assert 0.0 <= az < 360.0
    assert az == pytest.approx(270.0, abs=1e-6)


def test_zero_vector_is_rejected():
    with pytest.raises(ValueError):
        sun_azel_from_vector(np.zeros(3), lat_deg=-88.0, lon_deg=0.0)


# --- true-north -> grid-north azimuth conversion (final review, C1) ---------


def _circular_delta(a_deg: float, b_deg: float) -> float:
    """Smallest absolute angular separation between two bearings."""
    return abs((float(a_deg) - float(b_deg) + 180.0) % 360.0 - 180.0)


def test_grid_north_matches_true_north_on_central_meridian():
    """The two frames coincide exactly on the projection's central meridian."""
    az = true_north_grid_azimuth(-89.0, 0.0, LUNAR_SOUTH_POLAR_WKT)
    assert _circular_delta(az, 0.0) < 1e-3


def test_grid_north_diverges_off_the_central_meridian():
    """90 deg off the central meridian, grid north is 90 deg from true north.

    This is the whole point of the conversion: away from the central meridian
    the horizon bins and the Sun azimuth are in different frames.
    """
    az = true_north_grid_azimuth(-89.0, 90.0, LUNAR_SOUTH_POLAR_WKT)
    assert _circular_delta(az, 90.0) < 1e-3


def test_grid_north_at_the_real_processed_window_center():
    """Ground truth for the window in lunapath/data/processed/metadata.json.

    origin (-15500, -4000), 5.0 m/px, 500x500 -> center (-89.4991897,
    -110.2248594). Independently reproduced by the Faz 1 final reviewer as
    ~249.8 deg; a ~110 deg offset from true north, i.e. ~22 of 72 horizon bins.
    """
    az = true_north_grid_azimuth(
        -89.4991897, -110.2248594, LUNAR_SOUTH_POLAR_WKT
    )
    assert az == pytest.approx(249.775, abs=0.05)


def test_grid_north_is_insensitive_to_the_step_size():
    """A numeric derivative must not depend on the probe step length."""
    values = [
        true_north_grid_azimuth(
            -89.4991897, -110.2248594, LUNAR_SOUTH_POLAR_WKT, step_deg=step
        )
        for step in (1e-6, 1e-5, 1e-4, 1e-3)
    ]
    for value in values[1:]:
        assert _circular_delta(value, values[0]) < 1e-3


def test_grid_north_azimuth_is_normalised_to_zero_360():
    for lon in (-179.0, -110.2248594, 0.0, 45.0, 179.0):
        az = true_north_grid_azimuth(-89.0, lon, LUNAR_SOUTH_POLAR_WKT)
        assert 0.0 <= az < 360.0


def test_true_azimuth_zero_maps_to_the_grid_north_bearing():
    """A Sun due TRUE north sits at whatever bearing grid-frame north is."""
    assert true_azimuth_to_grid_azimuth(0.0, 249.775141) == pytest.approx(
        249.775141
    )


def test_true_azimuth_rotates_by_the_grid_north_offset():
    assert true_azimuth_to_grid_azimuth(90.0, 249.775141) == pytest.approx(
        339.775141
    )


def test_true_azimuth_to_grid_azimuth_wraps_past_360():
    assert true_azimuth_to_grid_azimuth(180.0, 249.775141) == pytest.approx(
        69.775141
    )
    assert true_azimuth_to_grid_azimuth(350.0, 20.0) == pytest.approx(10.0)


def test_true_azimuth_to_grid_azimuth_is_identity_on_central_meridian():
    """With no convergence, the conversion must be a no-op."""
    for true_az in (0.0, 45.0, 123.4, 359.9):
        assert true_azimuth_to_grid_azimuth(true_az, 0.0) == pytest.approx(true_az)


# ── grid_azimuth_to_true_azimuth: the inverse rotation, for aspect grids ──────


def test_grid_azimuth_to_true_azimuth_is_the_exact_inverse_roundtrip():
    grid_north_az = 249.775141
    for true_az in (0.0, 45.0, 123.4, 210.0, 359.9):
        grid_az = true_azimuth_to_grid_azimuth(true_az, grid_north_az)
        assert grid_azimuth_to_true_azimuth(grid_az, grid_north_az) == pytest.approx(
            true_az
        )


def test_grid_azimuth_to_true_azimuth_wraps_past_zero():
    # A grid azimuth smaller than the offset must wrap around 360, not go
    # negative.
    assert grid_azimuth_to_true_azimuth(10.0, 20.0) == pytest.approx(350.0)


def test_grid_azimuth_to_true_azimuth_is_identity_on_central_meridian():
    for grid_az in (0.0, 45.0, 123.4, 359.9):
        assert grid_azimuth_to_true_azimuth(grid_az, 0.0) == pytest.approx(grid_az)


def test_grid_azimuth_to_true_azimuth_returns_a_python_float_for_scalar_input():
    out = grid_azimuth_to_true_azimuth(90.0, 249.775141)
    assert isinstance(out, float)


def test_grid_azimuth_to_true_azimuth_vectorises_over_an_aspect_grid():
    """The thermal path needs to rotate a whole (H, W) aspect grid in one
    call, unlike true_azimuth_to_grid_azimuth which only ever rotates
    individual sun samples."""
    grid_north_az = 249.775141
    aspect_grid = np.array([[0.0, 90.0], [180.0, 270.0]])
    out = grid_azimuth_to_true_azimuth(aspect_grid, grid_north_az)
    assert out.shape == aspect_grid.shape
    expected = np.mod(aspect_grid - grid_north_az, 360.0)
    assert np.allclose(out, expected)
