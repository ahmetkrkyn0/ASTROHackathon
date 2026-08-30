"""DEM → grid pipeline with .npy caching, plus direct P1 grid loading."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import rasterio

from .constants import DEFAULT_ROVER_ID, DEFAULT_TARGET_RESOLUTION_M
from .cost_engine import COST_MODEL_ID, compute_cost_grid, resolve_weights
from .thermal_grid import ELEV_REF_MAX_M, ELEV_REF_MIN_M, generate_thermal_grid
from .thermal_model import couple_shadow_to_thermal
from .traversability import compute_traversability_bool, weakest_validity

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

_VALIDITY_LAYERS: tuple[str, ...] = (
    "elevation",
    "slope",
    "aspect",
    "shadow_ratio",
    "thermal",
    "traversable",
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

    stored_validity = dict(metadata.get("layer_validity", {}))

    # ── Shadow coupling ──────────────────────────────────────────────────
    # The thermal layer P1 writes is a (slope x aspect) lookup at fixed
    # latitude: it never reads shadow_ratio, so a permanently shadowed cell
    # could be reported at +42.6 C and the -150 C traversability gate blocked
    # 150 cells out of 250 000. Couple the two layers here rather than only
    # in the pipeline, so the fix reaches the grids already on disk without a
    # re-run. Idempotent: a pipeline that already coupled them stamps
    # `thermal_shadow_coupled` and this is skipped. (Round 3 review, H-3.)
    thermal_validity = str(stored_validity.get("thermal", "UNKNOWN"))
    shadow_validity = str(stored_validity.get("shadow_ratio", "UNKNOWN"))
    already_coupled = bool(metadata.get("thermal_shadow_coupled", False))
    if not already_coupled:
        result["thermal"] = np.asarray(
            couple_shadow_to_thermal(result["thermal"], result["shadow_ratio"]),
            dtype=np.float64,
        )
        thermal_validity = weakest_validity(thermal_validity, shadow_validity)
        # The stored mask was built against the UNCOUPLED thermal grid, so it
        # calls cold traps passable. Rebuild it from the grid it is supposed
        # to describe -- ~0.05 s on the production grid.
        result["traversable"] = compute_traversability_bool(
            result["slope"], result["thermal"], result["elevation"]
        )

    resolved = resolve_weights(weights)
    stored_weights = metadata.get("cost_weights", {})

    # Recompute the cost grid when the weights differ from what P1 used, or
    # when the thermal layer was just coupled -- the stored grid describes the
    # uncoupled field either way. `cost_model` is stamped with THIS build's id
    # afterwards: leaving the file's stored value meant a freshly computed
    # grid was labelled stale and pathfinder recomputed it a second time.
    # (Round 3 review, L-5.)
    recomputed_cost = (weights is not None and resolved != stored_weights) or (
        not already_coupled
    )
    if recomputed_cost:
        result["cost"] = compute_cost_grid(
            result["slope"],
            result["thermal"],
            result["shadow_ratio"],
            float(metadata["resolution_m"]),
            traversable=result["traversable"],
            weights=resolved,
        )
        cost_weights = resolved
        cost_model = COST_MODEL_ID
    else:
        cost_weights = stored_weights or resolved
        # No default to the CURRENT model id: a P1 grid that predates
        # cost_model must read as "unknown", not as "matches this build".
        # (Review #5.)
        cost_model = metadata.get("cost_model", "unknown")

    validity = {
        layer: str(stored_validity.get(layer, "UNKNOWN"))
        for layer in _VALIDITY_LAYERS
    }
    validity["thermal"] = thermal_validity
    if not already_coupled:
        validity["traversable"] = weakest_validity(
            validity.get("slope", "UNKNOWN"), thermal_validity
        )
        validity["cost"] = weakest_validity(
            validity.get("slope", "UNKNOWN"), thermal_validity, shadow_validity
        )

    result["metadata"] = {
        "origin": metadata.get("origin"),
        "resolution_m": float(metadata["resolution_m"]),
        "shape": metadata["shape"],
        "crs": metadata.get("crs", "unknown"),
        "source": "preprocessed",
        "processed_dir": d,
        "default_rover_id": metadata.get("default_rover_id", DEFAULT_ROVER_ID),
        "cost_weights": cost_weights,
        "cost_model": cost_model,
        "thermal_shadow_coupled": True,
        "layer_validity": validity,
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
        elevation_raw = src.read(1).astype(np.float64)
        transform = src.transform
        crs = src.crs
        native_resolution = abs(transform.a)
        nodata = src.nodata

    # No-data is masked BEFORE any filtering. The box filter used to run on
    # the raw band and the sentinel was only removed afterwards, so a
    # -3.4e38 fill smeared across a whole factor x factor block, and a
    # moderate sentinel (-32768, which src.nodata knows about and the
    # < -1e6 test does not) blended into a PLAUSIBLE BUT WRONG elevation
    # that survived the test entirely. (Round 3 review, L-2.)
    elevation_raw = np.where(elevation_raw < -1e6, np.nan, elevation_raw)
    if nodata is not None and np.isfinite(nodata):
        elevation_raw = np.where(
            np.isclose(elevation_raw, float(nodata)), np.nan, elevation_raw
        )

    # Downsampling for performance
    if native_resolution < target_resolution_m:
        factor = max(1, int(target_resolution_m / native_resolution))
        elevation = _nanaware_box_downsample(elevation_raw, factor)
        actual_resolution = native_resolution * factor
    else:
        elevation = elevation_raw
        actual_resolution = native_resolution

    # Slope (degrees)
    dy, dx = np.gradient(elevation, actual_resolution)
    slope = np.degrees(np.arctan(np.sqrt(dx**2 + dy**2)))

    # Aspect (degrees, 0°=North clockwise)
    aspect = np.degrees(np.arctan2(-dx, dy))
    aspect = (aspect + 360) % 360

    # Synthetic thermal grid
    thermal = generate_thermal_grid(elevation, slope, aspect, actual_resolution)

    # Shadow proxy (elevation-based). Normalised against FIXED reference
    # bounds, not against this window's own min/max: the window-relative form
    # made every cell's shadow ratio -- and, through the thermal grid, its
    # traversability -- a function of where the raster happened to be cropped,
    # so the same terrain changed passability when loaded as part of a
    # different window. (Round 3 review, L-3.)
    elev_span = ELEV_REF_MAX_M - ELEV_REF_MIN_M
    elev_norm = np.clip((elevation - ELEV_REF_MIN_M) / elev_span, 0.0, 1.0)
    shadow_ratio = (1.0 - elev_norm).astype(np.float32)

    # Same radiative coupling the preprocessed path applies: a cell the
    # shadow layer calls dark cannot hold the sunlit peak temperature.
    # (Round 3 review, H-3.)
    thermal = np.asarray(
        couple_shadow_to_thermal(thermal, shadow_ratio), dtype=np.float64
    )

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
            "default_rover_id": DEFAULT_ROVER_ID,
            "cost_weights": resolved_weights,
            "cost_model": COST_MODEL_ID,
            "thermal_shadow_coupled": True,
            # This path only ever produces the synthetic thermal grid and the
            # elevation-proxy shadow ratio -- it does not touch the heat1d /
            # horizon / SPICE machinery -- so the honest provenance is
            # SYNTHETIC for those two layers. (Faz 1 final review, finding I4.)
            # traversable/cost are computed FROM those SYNTHETIC layers, so
            # they inherit the same weakest-link provenance rather than
            # claiming an unconditional "DERIVED". (Faz 1-2-3 review, L5.)
            "layer_validity": {
                "elevation": "MEASURED",
                "slope": "DERIVED",
                "aspect": "DERIVED",
                "shadow_ratio": "SYNTHETIC",
                "thermal": "SYNTHETIC",
                "traversable": weakest_validity("DERIVED", "SYNTHETIC"),
                "cost": weakest_validity("DERIVED", "SYNTHETIC"),
            },
        },
    }

    if use_cache:
        _save_cache(cache_key, result)

    return result


def _nanaware_box_downsample(array: np.ndarray, factor: int) -> np.ndarray:
    """Box-average by *factor*, ignoring NaN instead of spreading it.

    ``uniform_filter`` propagates a single NaN across its whole kernel, so
    one no-data pixel used to poison a factor-wide neighbourhood. Averaging
    the finite members of each block keeps a block with any real data, and
    yields NaN only for a block that is entirely no-data.
    """
    factor = max(1, int(factor))
    if factor == 1:
        return np.asarray(array, dtype=np.float64)
    arr = np.asarray(array, dtype=np.float64)
    height = (arr.shape[0] // factor) * factor
    width = (arr.shape[1] // factor) * factor
    trimmed = arr[:height, :width]
    blocks = trimmed.reshape(height // factor, factor, width // factor, factor)
    with np.errstate(invalid="ignore"):
        # All-NaN blocks legitimately produce NaN; the warning that comes
        # with them is noise, not information.
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            return np.nanmean(blocks, axis=(1, 3))


# ── Cache ────────────────────────────────────────────────────────────────────

def _cache_key(
    dem_path: str,
    resolution: float,
    weights: dict[str, float],
) -> str:
    """Cache key covering the DEM's identity, not just its basename.

    The old key was ``{basename}_{int(resolution)}m_{weight_hash}``, so
    /a/dem.tif and /b/dem.tif collided, an edited DEM reused its stale
    entry, and int() collapsed 80.0/80.4/80.9 onto one key. The full path,
    the file's size+mtime, the untruncated resolution and the cost model id
    all now feed the hash. (Backend review, #17.)
    """
    basename = os.path.splitext(os.path.basename(dem_path))[0]
    try:
        stat = os.stat(dem_path)
        identity = f"{os.path.abspath(dem_path)}|{stat.st_size}|{stat.st_mtime_ns}"
    except OSError:
        # Unreadable now: fall back to the path alone rather than crashing on
        # a cache lookup. A wrong-but-stable key is still better than a
        # basename collision.
        identity = os.path.abspath(dem_path)

    blob = json.dumps(
        {
            "identity": identity,
            "resolution": float(resolution),
            "weights": weights,
            "cost_model": COST_MODEL_ID,
            "thermal_shadow_coupled": True,
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
    return f"{basename}_{float(resolution):g}m_{digest}"


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
