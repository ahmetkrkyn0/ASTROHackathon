"""Synthetic thermal grid generation from DEM data.

This is the FALLBACK surface-temperature model: it runs when heat1d is not
installed, and it is labelled ``SYNTHETIC`` wherever its output travels. It
is a heuristic, not physics, and nothing here pretends otherwise.
"""

from __future__ import annotations

import numpy as np

# Fixed elevation reference for the lunar south polar working area, in metres
# relative to the 1737.4 km sphere the DEM is referenced to.
#
# These replace a per-window ``nanmin``/``nanmax`` normalisation. That form
# made absolute temperature -- and therefore, through the -150 C
# traversability gate, PASSABILITY -- a function of where the raster happened
# to be cropped: the same terrain loaded inside a different window came back
# with different temperatures and a different traversable mask. A fixed
# reference makes the same cell yield the same value in every window that
# contains it, which is the property a physical field is supposed to have.
# (Round 3 review, L-3.)
ELEV_REF_MIN_M: float = -3000.0
ELEV_REF_MAX_M: float = 4000.0

# Temperature band the normalised elevation is mapped onto.
T_LOW_C: float = -180.0
T_HIGH_C: float = 80.0


def generate_thermal_grid(
    elevation_grid: np.ndarray,
    slope_grid: np.ndarray,
    aspect_grid: np.ndarray,
    resolution_m: float,
    sun_azimuth_grid_deg: float = 0.0,
) -> np.ndarray:
    """Generate synthetic surface temperature map from DEM.

    Lunar South Pole assumptions:
        - Low Sun angle; the aspect term below is the only directional input.
        - Low areas → more shadow → colder.
        - Slopes facing the Sun → warmer; slopes facing away → colder.

    Parameters
    ----------
    sun_azimuth_grid_deg
        Grid azimuth the Sun sits in (0 = grid North / decreasing row,
        90 = grid East, clockwise) -- the same convention ``app.horizon``
        and ``make_aspect_grid`` use.

        This used to be hardcoded to grid north. In a south polar
        stereographic CRS the equatorward (sunward) direction is a fixed
        offset from grid north that depends on the window's longitude: at
        the P1 window it is roughly 75 degrees away, i.e. nearly grid EAST,
        so the aspect correction was warming the wrong side of every ridge.
        The heat1d path already rotates its aspect through
        ``ephemeris.grid_azimuth_to_true_azimuth``; this path could not,
        because it had nowhere to put the angle. Now it does, and a caller
        that knows the CRS passes the real value. The default preserves the
        previous behaviour for callers that do not. (Round 3 review, L-4.)

    Returns (H, W) float32 array in °C.
    """
    H, W = elevation_grid.shape

    # Normalize elevation against a FIXED reference, not this window's own
    # extremes -- see ELEV_REF_MIN_M.
    elev_span = ELEV_REF_MAX_M - ELEV_REF_MIN_M
    elev_norm = np.clip((elevation_grid - ELEV_REF_MIN_M) / elev_span, 0.0, 1.0)

    T_base = T_LOW_C + elev_norm * (T_HIGH_C - T_LOW_C)

    # Aspect correction: a slope facing the Sun's azimuth gets the full
    # bonus, one facing away gets the full penalty.
    relative_rad = np.radians(
        np.asarray(aspect_grid, dtype=np.float64) - float(sun_azimuth_grid_deg)
    )
    sun_factor = np.cos(relative_rad)
    slope_weight = np.clip(slope_grid / 25.0, 0.0, 1.0)
    T_aspect_delta = sun_factor * slope_weight * 40.0

    # Local shadow proxy: terrain rising toward the Sun blocks it.
    #
    # This looked at the NORTH neighbour only, so a ridge to the east, west or
    # south cast no shadow at all, and row 0 could never be shadowed because
    # height_diff[0, :] was never written. Take the largest rise over the
    # 8-neighbourhood instead, which is direction-agnostic and leaves no row
    # structurally exempt. Still a proxy, not ray-casting: the real pipeline
    # uses app.horizon + SPICE, and this grid stays labelled SYNTHETIC.
    # (Backend review, #14.)
    padded = np.pad(elevation_grid, 1, mode="edge")
    max_rise = np.full_like(elevation_grid, -np.inf, dtype=np.float64)
    for d_row in (-1, 0, 1):
        for d_col in (-1, 0, 1):
            if d_row == 0 and d_col == 0:
                continue
            neighbour = padded[
                1 + d_row : 1 + d_row + H, 1 + d_col : 1 + d_col + W
            ]
            max_rise = np.maximum(max_rise, neighbour - elevation_grid)
    shadow_penalty = np.clip(max_rise / (resolution_m * 0.1), 0, 1) * (-30.0)

    T_surface = np.clip(T_base + T_aspect_delta + shadow_penalty, -250.0, 130.0)
    return T_surface.astype(np.float32)
