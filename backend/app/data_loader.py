"""DEM → grid pipeline with optional U-Net ML enhancement and .npy caching.

The preprocessing math (slope, aspect, thermal) and all downstream cost-engine
formulas are FROZEN (v3.2).  This module only improves *input data quality*
by replacing the naive elevation-proxy shadow ratio and adding a micro-hazard
mask via a pre-trained U-Net segmentation model (ONNX).

ML integration contract
-----------------------
* Model  : ``unet_model.onnx`` (Kaggle lunar-terrain segmentation)
* Input  : 1×1×H×W  float32 grayscale image, pixel values [0, 1]
* Output : 1×2×H×W  float32  —  channel-0 = shadow probability,
                                  channel-1 = hazard probability
* If the model or image is missing the pipeline falls back to the
  original elevation-proxy heuristics — no crash, no behaviour change.

Caching
-------
Every grid set (including ML outputs) is persisted as ``.npy`` files under
``/data/cache/<dem_key>/``.  ONNX inference only runs on a cache miss.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any

import numpy as np
import rasterio
from numpy.typing import NDArray
from scipy.ndimage import uniform_filter

from .constants import DEFAULT_TARGET_RESOLUTION_M, SLOPE_MAX_DEG
from .thermal_grid import generate_thermal_grid

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
MODEL_DIR = os.path.join(DATA_DIR, "models")
DEFAULT_MODEL_PATH = os.path.join(MODEL_DIR, "unet_model.onnx")

# Grid arrays persisted to cache (order matters for load/save symmetry)
_GRID_KEYS: tuple[str, ...] = (
    "elevation",
    "slope",
    "aspect",
    "thermal",
    "shadow_ratio",
)


# ═══════════════════════════════════════════════════════════════════════════════
#  U-Net ONNX inference
# ═══════════════════════════════════════════════════════════════════════════════

def run_unet_inference(
    image_path: str,
    model_path: str = DEFAULT_MODEL_PATH,
    target_shape: tuple[int, int] | None = None,
) -> tuple[NDArray[np.bool_], NDArray[np.float32]]:
    """Run the pre-trained U-Net on a grayscale lunar image.

    Parameters
    ----------
    image_path : str
        Path to a single-channel optical/DEM-derived image (any format
        readable by rasterio or PIL-compatible loader).
    model_path : str
        Path to the exported ``unet_model.onnx``.
    target_shape : tuple[int, int] | None
        If provided, resize the model output to ``(H, W)`` so it aligns
        with the DEM grid.  Uses nearest-neighbour interpolation for the
        hazard mask and bilinear for the shadow ratio.

    Returns
    -------
    ml_hazard_mask : ndarray[bool]  (H, W)
        ``True`` where the model predicts a micro-hazard (boulder, crevasse).
    ml_shadow_ratio : ndarray[float32]  (H, W)
        Per-pixel shadow probability in [0, 1].

    Raises
    ------
    FileNotFoundError
        If *image_path* or *model_path* does not exist.
    RuntimeError
        If ONNX Runtime fails during inference.
    """
    import onnxruntime as ort  # deferred — not needed when cache hits

    if not os.path.isfile(model_path):
        raise FileNotFoundError(f"ONNX model not found: {model_path}")
    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    # ── Load image ────────────────────────────────────────────────────────
    image = _load_grayscale_image(image_path)          # (H_img, W_img) float32 [0,1]
    input_tensor = image[np.newaxis, np.newaxis, :, :]  # (1, 1, H, W)

    # ── ONNX inference ────────────────────────────────────────────────────
    sess = ort.InferenceSession(
        model_path,
        providers=["CPUExecutionProvider"],
    )
    input_name = sess.get_inputs()[0].name
    raw_output = sess.run(None, {input_name: input_tensor})[0]  # (1, 2, H, W)

    shadow_prob = raw_output[0, 0, :, :]   # channel 0 → shadow
    hazard_prob = raw_output[0, 1, :, :]   # channel 1 → hazard

    # Clip to valid range (model may produce slight out-of-bounds values)
    shadow_prob = np.clip(shadow_prob, 0.0, 1.0).astype(np.float32)
    hazard_prob = np.clip(hazard_prob, 0.0, 1.0).astype(np.float32)

    # ── Resize to DEM grid if needed ──────────────────────────────────────
    if target_shape is not None and shadow_prob.shape != target_shape:
        shadow_prob = _resize_grid(shadow_prob, target_shape, order=1)
        hazard_prob = _resize_grid(hazard_prob, target_shape, order=0)

    ml_hazard_mask = hazard_prob > 0.5      # threshold → boolean
    ml_shadow_ratio = shadow_prob

    return ml_hazard_mask, ml_shadow_ratio


# ═══════════════════════════════════════════════════════════════════════════════
#  Main preprocessing pipeline
# ═══════════════════════════════════════════════════════════════════════════════

def load_and_preprocess_dem(
    dem_path: str,
    target_resolution_m: float = DEFAULT_TARGET_RESOLUTION_M,
    use_cache: bool = True,
    image_path: str | None = None,
    model_path: str = DEFAULT_MODEL_PATH,
) -> dict[str, Any]:
    """Load raw DEM and produce all grid layers.

    When *image_path* and a valid *model_path* are provided the U-Net
    inference enriches shadow and traversability grids.  On any ML failure
    the pipeline falls back to the original elevation-proxy heuristics so
    the rest of the system (cost engine, A*) is never affected.

    Returns
    -------
    dict with keys:
        elevation, slope, aspect, thermal, shadow_ratio, traversable,
        ml_hazard_mask (if ML ran), metadata
    """
    cache_key = _cache_key(dem_path, target_resolution_m, image_path)
    if use_cache:
        cached = _load_cache(cache_key)
        if cached is not None:
            return cached

    # ── Read DEM ──────────────────────────────────────────────────────────
    with rasterio.open(dem_path) as src:
        elevation_raw = src.read(1).astype(np.float32)
        transform = src.transform
        crs = src.crs
        native_resolution = abs(transform.a)

    # ── Downsampling ──────────────────────────────────────────────────────
    if native_resolution < target_resolution_m:
        factor = max(1, int(target_resolution_m / native_resolution))
        elevation = uniform_filter(elevation_raw, size=factor)[::factor, ::factor]
        actual_resolution = native_resolution * factor
    else:
        elevation = elevation_raw
        actual_resolution = native_resolution

    elevation = np.where(elevation < -1e6, np.nan, elevation)

    # ── Slope & Aspect (FROZEN formulas) ──────────────────────────────────
    dy, dx = np.gradient(elevation, actual_resolution)
    slope = np.degrees(np.arctan(np.sqrt(dx**2 + dy**2)))
    aspect = np.degrees(np.arctan2(-dx, dy))
    aspect = (aspect + 360) % 360

    # ── Thermal grid (FROZEN) ─────────────────────────────────────────────
    thermal = generate_thermal_grid(elevation, slope, aspect, actual_resolution)

    # ── Shadow ratio + Hazard mask ────────────────────────────────────────
    ml_used = False
    ml_hazard_mask: NDArray[np.bool_] | None = None

    if image_path is not None:
        try:
            ml_hazard_mask, shadow_ratio = run_unet_inference(
                image_path,
                model_path,
                target_shape=elevation.shape,
            )
            ml_used = True
            logger.info("U-Net inference succeeded — using ML shadow & hazard grids")
        except Exception as exc:
            logger.warning("U-Net inference failed (%s), falling back to proxy", exc)

    if not ml_used:
        # Original elevation-proxy fallback (unchanged)
        elev_min = np.nanmin(elevation)
        elev_max = np.nanmax(elevation)
        elev_norm = (elevation - elev_min) / (elev_max - elev_min + 1e-10)
        shadow_ratio = (1.0 - elev_norm).astype(np.float32)

    # ── Traversability (FROZEN rules + ML hazard overlay) ─────────────────
    traversable = np.ones_like(elevation, dtype=bool)
    traversable[slope > SLOPE_MAX_DEG] = False
    traversable[thermal < -150.0] = False
    traversable[np.isnan(elevation)] = False
    if ml_hazard_mask is not None:
        traversable[ml_hazard_mask] = False

    # ── Assemble result ───────────────────────────────────────────────────
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
            "ml_enhanced": ml_used,
            "image_source": image_path,
        },
    }

    if ml_hazard_mask is not None:
        result["ml_hazard_mask"] = ml_hazard_mask

    if use_cache:
        _save_cache(cache_key, result)

    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  Coordinate helpers
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
#  Internal helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _load_grayscale_image(path: str) -> NDArray[np.float32]:
    """Load any rasterio-readable single-band image as float32 [0, 1]."""
    with rasterio.open(path) as src:
        band = src.read(1).astype(np.float32)
    bmin, bmax = np.nanmin(band), np.nanmax(band)
    if bmax - bmin < 1e-10:
        return np.zeros_like(band)
    return ((band - bmin) / (bmax - bmin)).astype(np.float32)


def _resize_grid(
    arr: NDArray[np.float32],
    target_shape: tuple[int, int],
    order: int = 1,
) -> NDArray[np.float32]:
    """Resize 2-D array to *target_shape* using scipy zoom.

    order=0 → nearest (for masks), order=1 → bilinear (for continuous).
    """
    from scipy.ndimage import zoom

    factors = (target_shape[0] / arr.shape[0], target_shape[1] / arr.shape[1])
    return zoom(arr, factors, order=order).astype(np.float32)


# ═══════════════════════════════════════════════════════════════════════════════
#  Cache layer
# ═══════════════════════════════════════════════════════════════════════════════

def _cache_key(
    dem_path: str,
    resolution: float,
    image_path: str | None = None,
) -> str:
    """Deterministic cache key incorporating DEM name + resolution + image hash."""
    basename = os.path.splitext(os.path.basename(dem_path))[0]
    key = f"{basename}_{int(resolution)}m"
    if image_path is not None:
        img_hash = hashlib.md5(image_path.encode()).hexdigest()[:8]
        key += f"_ml_{img_hash}"
    return key


def _save_cache(key: str, data: dict[str, Any]) -> None:
    path = os.path.join(CACHE_DIR, key)
    os.makedirs(path, exist_ok=True)

    for name in _GRID_KEYS:
        np.save(os.path.join(path, f"{name}.npy"), data[name])
    np.save(
        os.path.join(path, "traversable.npy"),
        data["traversable"].astype(np.uint8),
    )

    # ML grids (optional)
    if "ml_hazard_mask" in data:
        np.save(
            os.path.join(path, "ml_hazard_mask.npy"),
            data["ml_hazard_mask"].astype(np.uint8),
        )

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

    # ML grids (optional — present only if inference ran)
    hazard_path = os.path.join(path, "ml_hazard_mask.npy")
    if os.path.exists(hazard_path):
        result["ml_hazard_mask"] = np.load(hazard_path).astype(bool)

    return result
