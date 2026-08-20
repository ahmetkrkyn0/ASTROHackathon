"""Illumination field tests."""

from __future__ import annotations

import numpy as np
import pytest

from app.illumination import (
    illuminated_mask,
    illumination_fraction,
    shadow_ratio_from_illumination,
)

N_AZ = 8
SHAPE = (5, 5)


def _flat_horizon(value_deg: float = 0.0) -> np.ndarray:
    return np.full((N_AZ, *SHAPE), value_deg, dtype=np.float32)


def test_sun_above_flat_horizon_lights_everything():
    mask = illuminated_mask(_flat_horizon(0.0), sun_az_deg=90.0, sun_elev_deg=5.0)
    assert mask.shape == SHAPE
    assert mask.all()


def test_sun_below_flat_horizon_darkens_everything():
    mask = illuminated_mask(_flat_horizon(0.0), sun_az_deg=90.0, sun_elev_deg=-5.0)
    assert not mask.any()


def test_only_the_matching_azimuth_bin_blocks():
    """A ridge in one azimuth must not shadow the Sun coming from another."""
    horizon = _flat_horizon(0.0)
    horizon[2] = 10.0  # index 2 of 8 bins -> 90 deg = East
    blocked = illuminated_mask(horizon, sun_az_deg=90.0, sun_elev_deg=5.0)
    clear = illuminated_mask(horizon, sun_az_deg=0.0, sun_elev_deg=5.0)
    assert not blocked.any()
    assert clear.all()


def test_azimuth_snaps_to_nearest_bin_and_wraps():
    horizon = _flat_horizon(0.0)
    horizon[0] = 10.0  # 0 deg = North
    assert not illuminated_mask(horizon, 359.0, 5.0).any()
    assert not illuminated_mask(horizon, 361.0, 5.0).any()


def test_illumination_fraction_averages_over_samples():
    horizon = _flat_horizon(0.0)
    samples = [(90.0, 5.0), (90.0, -5.0), (90.0, 5.0), (90.0, -5.0)]
    frac = illumination_fraction(horizon, samples)
    assert frac.shape == SHAPE
    assert frac.dtype == np.float32
    assert frac == pytest.approx(0.5)


def test_illumination_fraction_rejects_empty_sample_list():
    with pytest.raises(ValueError):
        illumination_fraction(_flat_horizon(0.0), [])


def test_shadow_ratio_is_complement_of_illumination():
    frac = np.array([[0.0, 0.25, 1.0]], dtype=np.float32)
    ratio = shadow_ratio_from_illumination(frac)
    assert ratio == pytest.approx(np.array([[1.0, 0.75, 0.0]], dtype=np.float32))
