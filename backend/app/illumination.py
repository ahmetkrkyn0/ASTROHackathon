"""Illumination field I(x, y, t) from horizon geometry and Sun ephemeris.

A cell is lit when the Sun's elevation angle exceeds the terrain horizon
angle in the Sun's azimuth. This replaces the ``1 - normalize(elevation)``
shadow proxy in the P1 pipeline with real ray-cast geometry.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from .horizon import _NO_HORIZON_DEG as NO_HORIZON_DEG

# The sentinel is written as an exact float32 -90.0; the tolerance guards
# against a caller that stored the cube through a lossy round trip.
_SENTINEL_TOLERANCE_DEG: float = 1e-3


def _azimuth_bin(sun_az_deg: float, n_azimuth: int) -> int:
    """Nearest horizon azimuth bin for a Sun azimuth in degrees."""
    normalised = float(sun_az_deg) % 360.0
    return int(round(normalised / 360.0 * n_azimuth)) % n_azimuth


def illuminated_mask(
    horizon_deg: np.ndarray,
    sun_az_deg: float,
    sun_elev_deg: float,
) -> np.ndarray:
    """(H, W) boolean mask: True where the Sun clears the local horizon."""
    horizon = np.asarray(horizon_deg)
    if horizon.ndim != 3:
        raise ValueError(
            f"horizon_deg must be (n_azimuth, H, W), got shape {horizon.shape}"
        )
    bin_index = _azimuth_bin(sun_az_deg, horizon.shape[0])
    profile = horizon[bin_index]

    # app.horizon writes a -90 deg SENTINEL where a ray left the DEM without
    # finding any obstruction: that means "no data", not "flat ground", and
    # without special handling a Sun objectively below the horizontal read as
    # lit there because -20 > -90. (Faz 1 final review, M1.)
    #
    # The first fix was a blanket `sun_elev > 0` floor applied to EVERY cell,
    # which also threw away every case where the terrain genuinely drops away
    # and the horizon angle is legitimately negative. At -84 degrees latitude
    # that is exactly the peak-of-eternal-light geometry -- a ridge top whose
    # horizon sits below the horizontal, lit while the surrounding plain is
    # dark -- which is the single most valuable thing an illumination layer
    # can find. Applying the floor only where the sentinel actually appears
    # keeps the original fix and returns the real negative horizons.
    # (Round 3 review, M-11.)
    # For a cell with a real horizon profile, "lit" is simply "the Sun is
    # above it" -- negative profiles included.
    # For a SENTINEL cell the profile carries no information, so the best
    # available assumption is the one the sentinel actually encodes: no
    # obstruction was found, i.e. the horizon is at or below the horizontal.
    # Such a cell is lit exactly when the Sun is above the horizontal.
    sentinel = profile <= (NO_HORIZON_DEG + _SENTINEL_TOLERANCE_DEG)
    elevation = float(sun_elev_deg)
    return np.where(sentinel, elevation > 0.0, elevation > profile)


def illumination_fraction(
    horizon_deg: np.ndarray,
    sun_samples: Sequence[tuple[float, float]],
) -> np.ndarray:
    """(H, W) float32 in [0, 1]: fraction of samples in which a cell is lit.

    *sun_samples* is a sequence of ``(azimuth_deg, elevation_deg)`` pairs,
    typically from :func:`app.ephemeris.sun_track`.
    """
    if len(sun_samples) == 0:
        raise ValueError("sun_samples must contain at least one (az, elev) pair")

    horizon = np.asarray(horizon_deg)
    accumulator = np.zeros(horizon.shape[1:], dtype=np.float64)
    for az_deg, elev_deg in sun_samples:
        accumulator += illuminated_mask(horizon, az_deg, elev_deg)

    return (accumulator / float(len(sun_samples))).astype(np.float32)


def shadow_ratio_from_illumination(illum_frac: np.ndarray) -> np.ndarray:
    """Convert illumination fraction to the shadow ratio the cost engine wants.

    ``shadow_ratio`` is 0 for fully lit and 1 for fully shadowed, matching
    ``app.cost_engine.f_shadow_cell``.
    """
    frac = np.asarray(illum_frac, dtype=np.float32)
    return (1.0 - np.clip(frac, 0.0, 1.0)).astype(np.float32)
