"""Illumination field I(x, y, t) from horizon geometry and Sun ephemeris.

A cell is lit when the Sun's elevation angle exceeds the terrain horizon
angle in the Sun's azimuth. This replaces the ``1 - normalize(elevation)``
shadow proxy in the P1 pipeline with real ray-cast geometry.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


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
    # The `> 0` floor matters at grid-edge cells: app.horizon writes a -90 deg
    # sentinel where a ray left the DEM without finding any obstruction, which
    # means "no data", not "flat". Without the floor, a Sun objectively BELOW
    # the horizontal still reads as lit there, because -20 > -90.
    # (Faz 1 final review, finding M1.)
    return (float(sun_elev_deg) > horizon[bin_index]) & (float(sun_elev_deg) > 0.0)


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
