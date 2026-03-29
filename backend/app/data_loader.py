"""DEM → grid pipeline with .npy caching, plus direct P1 grid loading."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from scipy.ndimage import uniform_filter

from .constants import DEFAULT_TARGET_RESOLUTION_M
from .cost_engine import compute_cost_grid, resolve_weights
from .thermal_grid import generate_thermal_grid
from .traversability import compute_traversability_bool

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
CACHE_DIR = os.path.join(DATA_DIR, "cache")

# P1 processed output directory
_P1_PROCESSED_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "lunapath", "data", "processed",
)

_GRID_KEYS: tuple[str, ...] = (
    "elevation",
    "slope",
    "aspect",
    "thermal",
    "shadow_ratio",
    "cost",
)


def load_preprocessed_grids(
    processed_dir: str | None = None,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Load pre-computed .npy grids produced by the P1 pipeline.

    This is the preferred loading method — it reuses the grids that
    ``lunapath/src/process_lunar_data.py`` already generated, avoiding
    duplicate DEM processing.

    If *weights* differ from the stored cost weights the cost grid is
    recomputed on the fly (cheap, <1 s for 500×500).
    """
    d = processed_dir or _P1_PROCESSED_DIR

    meta_path = os.path.join(d, "metadata.json")
    if not os.path.exists(meta_path):
        raise FileNotFoundError(
            f"metadata.json not found in {d}. Run the P1 pipeline first."
        )

    with open(meta_path, encoding="utf-8") as f:
        metadata = json.load(f)

    # Map between .npy file stem and the key used in the grids dict
    _FILE_TO_KEY = {
        "elevation_grid": "elevation",
        "slope_grid": "slope",
        "aspect_grid": "aspect",
        "thermal_grid": "thermal",
        "shadow_ratio_grid": "shadow_ratio",
        "traversability_grid": "traversable",
        "cost_grid": "cost",
    }

    result: dict[str, Any] = {}
    for file_stem, key in _FILE_TO_KEY.items():
        npy_path = os.path.join(d, f"{file_stem}.npy")
        if not os.path.exists(npy_path):
            raise FileNotFoundError(f"Required grid file missing: {npy_path}")
        arr = np.load(npy_path)
        if key == "traversable":
            result[key] = arr.astype(bool)
        else:
            result[key] = arr.astype(np.float64)

    resolved = resolve_weights(weights)
    stored_weights = metadata.get("cost_weights", {})

    # Recompute cost grid if requested weights differ from what P1 used
    if weights is not None and resolved != stored_weights:
        result["cost"] = compute_cost_grid(
            result["slope"],
            result["thermal"],
            result["shadow_ratio"],
            float(metadata["resolution_m"]),
            traversable=result["traversable"],
            weights=resolved,
        )
        cost_weights = resolved
    else:
        cost_weights = stored_weights or resolved

    result["metadata"] = {
        "origin": metadata.get("origin"),
        "resolution_m": float(metadata["resolution_m"]),
        "shape": metadata["shape"],
        "crs": metadata.get("crs", "unknown"),
        "source": "preprocessed",
        "processed_dir": d,
        "cost_weights": cost_weights,
        "cost_model": metadata.get("cost_model", "weighted_cell_cost_without_barrier"),
    }

    return result


def load_and_preprocess_dem(
    dem_path: str,
    target_resolution_m: float = DEFAULT_TARGET_RESOLUTION_M,
    use_cache: bool = True,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Load raw DEM and produce all grid layers.

    Returns dict with keys:
        elevation, slope, aspect, thermal, shadow_ratio, cost, traversable, metadata
    """
    resolved_weights = resolve_weights(weights)
    cache_key = _cache_key(dem_path, target_resolution_m, resolved_weights)
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

    # Traversability (canonical logic from traversability module)
    traversable = compute_traversability_bool(slope, thermal, elevation)
    cost = compute_cost_grid(
        slope,
        thermal,
        shadow_ratio,
        actual_resolution,
        traversable=traversable,
        weights=resolved_weights,
    )

    result: dict[str, Any] = {
        "elevation": elevation,
        "slope": slope,
        "aspect": aspect,
        "thermal": thermal,
        "shadow_ratio": shadow_ratio,
        "cost": cost,
        "traversable": traversable,
        "metadata": {
            "origin": {
                "x": float(transform.c),
                "y": float(transform.f),
            },
            "resolution_m": float(actual_resolution),
            "shape": list(elevation.shape),
            "crs": str(crs),
            "source": "dem",
            "dem_path": dem_path,
            "cost_weights": resolved_weights,
            "cost_model": "weighted_cell_cost_without_barrier",
        },
    }

    if use_cache:
        _save_cache(cache_key, result)

    return result


# ── Cache ────────────────────────────────────────────────────────────────────

def _cache_key(
    dem_path: str,
    resolution: float,
    weights: dict[str, float],
) -> str:
    basename = os.path.splitext(os.path.basename(dem_path))[0]
    weight_blob = json.dumps(weights, sort_keys=True)
    weight_hash = hashlib.md5(weight_blob.encode("utf-8")).hexdigest()[:8]
    return f"{basename}_{int(resolution)}m_{weight_hash}"


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
