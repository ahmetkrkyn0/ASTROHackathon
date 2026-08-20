"""Sun azimuth/elevation geometry tests (no SPICE kernels required)."""

from __future__ import annotations

import numpy as np
import pytest

from app.ephemeris import sun_azel_from_vector


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
