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


def test_sentinel_horizon_does_not_light_a_below_horizon_sun():
    """A -90 sentinel means "ray left the DEM", not "flat" (final review, M1).

    app.horizon writes _NO_HORIZON_DEG = -90 for grid-edge cells whose ray ran
    off the grid without finding an obstruction. Without an explicit elevation
    floor, a Sun 20 deg BELOW the horizontal reads as lit there (-20 > -90).
    """
    horizon = np.full((N_AZ, *SHAPE), -90.0, dtype=np.float32)
    mask = illuminated_mask(horizon, sun_az_deg=90.0, sun_elev_deg=-20.0)
    assert not mask.any(), f"{int(mask.sum())} cells wrongly lit by a sunk Sun"


def test_mixed_sentinel_and_real_horizon_below_zero_sun():
    """Only the real-horizon cells were ever correct; both must now be dark."""
    horizon = _flat_horizon(2.0)
    horizon[:, :, -1] = -90.0  # last column: rays ran off-grid
    mask = illuminated_mask(horizon, sun_az_deg=0.0, sun_elev_deg=-20.0)
    assert not mask.any()


def test_sun_exactly_at_zero_elevation_is_not_lit():
    """The floor is strict: a Sun on the horizontal is not illuminating."""
    horizon = np.full((N_AZ, *SHAPE), -90.0, dtype=np.float32)
    assert not illuminated_mask(horizon, 0.0, 0.0).any()


def test_positive_sun_over_sentinel_horizon_is_still_lit():
    """The floor must not darken genuinely lit off-grid cells."""
    horizon = np.full((N_AZ, *SHAPE), -90.0, dtype=np.float32)
    assert illuminated_mask(horizon, 0.0, 3.0).all()


def test_illumination_fraction_ignores_below_horizon_samples_at_sentinels():
    """End-to-end: half the track below 0 deg -> at most half illumination."""
    horizon = np.full((N_AZ, *SHAPE), -90.0, dtype=np.float32)
    samples = [(0.0, 5.0), (0.0, -5.0), (0.0, 3.0), (0.0, -20.0)]
    frac = illumination_fraction(horizon, samples)
    assert frac == pytest.approx(0.5)


def test_shadow_ratio_is_complement_of_illumination():
    frac = np.array([[0.0, 0.25, 1.0]], dtype=np.float32)
    ratio = shadow_ratio_from_illumination(frac)
    assert ratio == pytest.approx(np.array([[1.0, 0.75, 0.0]], dtype=np.float32))
