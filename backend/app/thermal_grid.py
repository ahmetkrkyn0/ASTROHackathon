"""Synthetic thermal grid generation from DEM data."""

import numpy as np


def generate_thermal_grid(
    elevation_grid: np.ndarray,
    slope_grid: np.ndarray,
    aspect_grid: np.ndarray,
    resolution_m: float,
) -> np.ndarray:
    """Generate synthetic surface temperature map from DEM.

    Lunar South Pole assumptions:
        - Low Sun angle; direction not modelled (the aspect term below is
          the only directional input, and it assumes sun from the north)
        - Low areas → more shadow → colder
        - North-facing slopes → more sun → warmer
        - South-facing slopes → less sun → colder

    Returns (H, W) float32 array in °C.
    """
    H, W = elevation_grid.shape

    # Normalize elevation [0, 1]
    elev_min = np.nanmin(elevation_grid)
    elev_max = np.nanmax(elevation_grid)
    elev_norm = (elevation_grid - elev_min) / (elev_max - elev_min + 1e-10)

    # Base temperature from elevation: -180°C (lowest) to +80°C (highest)
    T_base = -180.0 + elev_norm * 260.0

    # Aspect correction: sun from north → cos(aspect)
    aspect_rad = np.radians(aspect_grid)
    sun_factor = np.cos(aspect_rad)
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
    max_rise = np.full_like(elevation_grid, -np.inf)
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


