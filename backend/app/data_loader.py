"""DEM → grid pipeline with .npy caching."""

from __future__ import annotations

import json
import os
from typing import Any

import numpy as np
import rasterio
from scipy.ndimage import uniform_filter

from .constants import DEFAULT_TARGET_RESOLUTION_M, SLOPE_MAX_DEG
from .thermal_grid import generate_thermal_grid

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
CACHE_DIR = os.path.join(DATA_DIR, "cache")

_GRID_KEYS: tuple[str, ...] = (
    "elevation",
    "slope",
    "aspect",
    "thermal",
    "shadow_ratio",
)


def load_and_preprocess_dem(
    dem_path: str,
    target_resolution_m: float = DEFAULT_TARGET_RESOLUTION_M,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Load raw DEM and produce all grid layers.

    Returns dict with keys:
        elevation, slope, aspect, thermal, shadow_ratio, traversable, metadata
    """
    cache_key = _cache_key(dem_path, target_resolution_m)
    if use_cache:
        cached = _load_cache(cache_key)
        if cached is not None:
            return cached

    with rasterio.open(dem_path) as src:
        elevation_raw = src.read(1).astype(np.float32)
        transform = src.transform
        crs = src.crs
        native_resolution = abs(transform.a)

    # Downsampling for performance
    if native_resolution < target_resolution_m:
        factor = max(1, int(target_resolution_m / native_resolution))
        elevation = uniform_filter(elevation_raw, size=factor)[::factor, ::factor]
        actual_resolution = native_resolution * factor
    else:
        elevation = elevation_raw
        actual_resolution = native_resolution

    elevation = np.where(elevation < -1e6, np.nan, elevation)

    # Slope (degrees)
    dy, dx = np.gradient(elevation, actual_resolution)
    slope = np.degrees(np.arctan(np.sqrt(dx**2 + dy**2)))

    # Aspect (degrees, 0°=North clockwise)
    aspect = np.degrees(np.arctan2(-dx, dy))
    aspect = (aspect + 360) % 360

    # Synthetic thermal grid
    thermal = generate_thermal_grid(elevation, slope, aspect, actual_resolution)

    # Shadow proxy (elevation-based)
    elev_min = np.nanmin(elevation)
    elev_max = np.nanmax(elevation)
    elev_norm = (elevation - elev_min) / (elev_max - elev_min + 1e-10)
    shadow_ratio = (1.0 - elev_norm).astype(np.float32)

    # Traversability
    traversable = np.ones_like(elevation, dtype=bool)
    traversable[slope > SLOPE_MAX_DEG] = False
    traversable[thermal < -150.0] = False
    traversable[np.isnan(elevation)] = False

    result: dict[str, Any] = {
        "elevation": elevation,
        "slope": slope,
        "aspect": aspect,
        "thermal": thermal,
        "shadow_ratio": shadow_ratio,
        "traversable": traversable,
        "metadata": {
            "resolution_m": float(actual_resolution),
            "shape": list(elevation.shape),
            "crs": str(crs),
            "dem_source": dem_path,
        },
    }

    if use_cache:
        _save_cache(cache_key, result)

    return result


# ── Coordinate helpers ───────────────────────────────────────────────────────

def pixel_to_geo(row: int, col: int, transform) -> tuple[float, float]:
    """Grid (row, col) → geographic (x, y)."""
    x = transform.c + col * transform.a + row * transform.e
    y = transform.f + col * transform.d + row * transform.e
    return x, y


def geo_to_pixel(x: float, y: float, transform) -> tuple[int, int]:
    """Geographic (x, y) → grid (row, col)."""
    col = int((x - transform.c) / transform.a)
    row = int((y - transform.f) / transform.e)
    return row, col


# ── Cache ────────────────────────────────────────────────────────────────────

def _cache_key(dem_path: str, resolution: float) -> str:
    basename = os.path.splitext(os.path.basename(dem_path))[0]
    return f"{basename}_{int(resolution)}m"


def _save_cache(key: str, data: dict[str, Any]) -> None:
    path = os.path.join(CACHE_DIR, key)
    os.makedirs(path, exist_ok=True)
    for name in _GRID_KEYS:
        np.save(os.path.join(path, f"{name}.npy"), data[name])
    np.save(os.path.join(path, "traversable.npy"), data["traversable"].astype(np.uint8))
    with open(os.path.join(path, "metadata.json"), "w") as f:
        json.dump(data["metadata"], f)


def _load_cache(key: str) -> dict[str, Any] | None:
    path = os.path.join(CACHE_DIR, key)
    meta_file = os.path.join(path, "metadata.json")
    if not os.path.exists(meta_file):
        return None
    with open(meta_file) as f:
        metadata = json.load(f)
    result: dict[str, Any] = {"metadata": metadata}
    for name in _GRID_KEYS:
        fpath = os.path.join(path, f"{name}.npy")
        if not os.path.exists(fpath):
            return None
        result[name] = np.load(fpath)
    trav = os.path.join(path, "traversable.npy")
    if not os.path.exists(trav):
        return None
    result["traversable"] = np.load(trav).astype(bool)
    return result
