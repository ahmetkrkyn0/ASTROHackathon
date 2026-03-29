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
        - Sun at ~1.5° above horizon, roughly from north
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

    # Local shadow proxy: north neighbor higher → blocks sun
    shadow_penalty = np.zeros_like(elevation_grid)
    if H > 1:
        height_diff = np.zeros_like(elevation_grid)
        height_diff[1:, :] = elevation_grid[:-1, :] - elevation_grid[1:, :]
        shadow_penalty = np.clip(height_diff / (resolution_m * 0.1), 0, 1) * (-30.0)

    T_surface = np.clip(T_base + T_aspect_delta + shadow_penalty, -250.0, 130.0)
    return T_surface.astype(np.float32)


