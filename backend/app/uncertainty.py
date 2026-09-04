"""DEM error propagation with NASA's statistical DEM clones (B3).

Every LunaPath layer descends from one elevation model: one slope, one
horizon, one shadow. NASA GSFC's Planetary Geodesy group (Barker, Mazarico
et al.; PGDA product 78) publishes, for every 5 m/px south-polar site DEM,
a Z-uncertainty map (``toterr``), a slope-uncertainty map (``slperr``) and
100 statistical clones -- full surface DEMs, each ``surface + toterr * xi``
with a spatially correlated unit-variance field ``xi`` (measured on Site11:
RMS(clone - surface) / RMS(toterr) = 1.00, correlation 0.88 at 5 m, gone by
100 m). This module runs the clones through LunaPath's OWN derivation
chain -- the pipeline's slope operator, the planner's traversability rule,
the horizon marcher, B5's energy arithmetic -- and reads off:

* per cell, the fraction of clones in which the cell is passable for a
  rover (``p_traversable``) and the ensemble slope sigma;
* per time slice, the fraction of clones in which the cell is lit
  (``p_illuminated``), from per-clone horizon cubes;
* for a planned route, the 5-95 percent band of duration, energy and
  continuous shadow across clones, and how many clones keep the route
  passable at all.

What is cloned and what is held fixed is stated, never implied. Slope and
traversability see the clone window; the thermal field is held (it is a
heat1d model, weakly slope-dependent and expensive). The horizon sees the
clone out to ``near_range_m`` (1 km by default) and the surface DEM's own
10 km context plus the LOLA 40 m far field beyond -- a ridge's height
error shifts the horizon by ``dz / d``, 0.26 deg at 100 m for the median
0.45 m error and 0.026 deg at 1 km, against a polar Sun that climbs
~0.009 deg/h; the neglected far-field shift is reported as a bound. The
Earth link and the safe-haven fields are not cloned (doc 11, section 2.3).

Nothing here fabricates a number: without the clone cache the loaders
return ``None`` and the API says ``unavailable``; the synthetic fallback
is labelled ``synthetic`` and refuses to run without NASA's ``toterr``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import numpy as np

from .horizon import march_distances_cells

# ── Cache files beside the processed grids ─────────────────────────────────
#: (N, R, C) float32: N clone surfaces over the planning window PLUS the
#: near-field pad the clone horizon marches over. The window sits inside
#: at ``meta["window"]`` (row0, col0, rows, cols).
DEM_CLONES_FILENAME: str = "dem_clones.npy"
#: Provenance of the clones: site, product URL, clone indices and URLs, the
#: window and pad, fetch date, per-clone checks, ``provenance``
#: (``nasa_pgda_clones`` | ``synthetic``).
DEM_CLONES_META_FILENAME: str = "dem_clones_meta.json"
#: NASA's Z-uncertainty (``toterr``) over the window, metres, (H, W) float32.
ELEVATION_SIGMA_FILENAME: str = "dem_elevation_sigma.npy"
#: NASA's slope-uncertainty (``slperr``) over the window, degrees.
SLOPE_SIGMA_NASA_FILENAME: str = "dem_slope_sigma_nasa.npy"
#: (N, A, h, w) float32: one horizon cube per clone on the 4-D planner's
#: block-centre grid (``meta["stride"]``, ``meta["row_offset"]``).
CLONE_HORIZONS_FILENAME: str = "dem_clone_horizons.npy"
CLONE_HORIZONS_META_FILENAME: str = "dem_clone_horizons_meta.json"
#: (A, h, w) float32: the far field every clone cube shares -- the surface
#: DEM's own context beyond ``near_range_m`` and the LOLA 40 m far field.
SURF_HORIZON_FAR_FILENAME: str = "dem_surf_horizon_far.npy"

# ── NASA PGDA product 78 ───────────────────────────────────────────────────
PGDA_PRODUCT_URL: str = "https://pgda.gsfc.nasa.gov/products/78"
PGDA_SITE_URL: str = "https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/{site}/"
PGDA_REFERENCE: str = (
    "Barker, Mazarico et al., High-Resolution LOLA Topography for Lunar South "
    "Pole Sites (PGDA product 78); Barker et al. 2021, PSS 203, 105119"
)
#: The published product-wide ranges, for the report's comparison only.
PGDA_MEDIAN_RMS_Z_ERROR_M: tuple[float, float] = (0.30, 0.50)
PGDA_MEDIAN_RMS_SLOPE_ERROR_DEG: tuple[float, float] = (1.5, 2.5)
N_PGDA_CLONES: int = 100


def clone_url(site: str, index: int) -> str:
    """URL of NASA's *index*-th (1-based) statistical clone for *site*.

    Despite the ``_err`` suffix each file is a FULL surface DEM -- measured
    on Site11: 528.8-954.6 m over the window, correlation 1.0000 with the
    surface -- so the error realisation is ``clone - surface``.
    """
    index = int(index)
    if not (1 <= index <= N_PGDA_CLONES):
        raise ValueError(f"clone index must be 1..{N_PGDA_CLONES}, got {index}")
    return f"{PGDA_SITE_URL.format(site=site)}Clones/{site}_final_adj_5mpp_{index:04d}_err.tif"


def toterr_url(site: str) -> str:
    """NASA's total Z-uncertainty map (metres) for *site*."""
    return f"{PGDA_SITE_URL.format(site=site)}{site}_final_adj_5mpp_toterr.tif"


def slperr_url(site: str) -> str:
    """NASA's slope-uncertainty map (degrees) for *site*."""
    return f"{PGDA_SITE_URL.format(site=site)}{site}_final_adj_5mpp_slperr.tif"


# ── The clone cache ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DemClones:
    """The clone stack as cached: padded surfaces and where the window is."""

    elevation: np.ndarray   # (N, R, C) float32, window + near-field pad
    meta: dict[str, Any]

    @property
    def n_clones(self) -> int:
        return int(self.elevation.shape[0])

    @property
    def clone_indices(self) -> list[int]:
        return [int(v) for v in self.meta.get("clone_indices", [])]

    @property
    def window_box(self) -> tuple[int, int, int, int]:
        """``(row0, col0, rows, cols)`` of the planning window inside the array."""
        box = self.meta["window"]
        return int(box["row0"]), int(box["col0"]), int(box["rows"]), int(box["cols"])

    @property
    def window(self) -> np.ndarray:
        """(N, H, W) view: the clones over the planning window only."""
        row0, col0, rows, cols = self.window_box
        return self.elevation[:, row0 : row0 + rows, col0 : col0 + cols]


def _read_json(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write_dem_clones(processed_dir: str, elevation: np.ndarray, meta: dict[str, Any]) -> None:
    """Write the clone stack and its provenance beside the processed grids."""
    stack = np.asarray(elevation, dtype=np.float32)
    if stack.ndim != 3:
        raise ValueError(f"the clone stack must be (N, R, C), got {stack.shape}")
    os.makedirs(processed_dir, exist_ok=True)
    np.save(os.path.join(processed_dir, DEM_CLONES_FILENAME), stack)
    with open(os.path.join(processed_dir, DEM_CLONES_META_FILENAME), "w", encoding="utf-8") as handle:
        json.dump(meta, handle, indent=2)


def load_dem_clones(
    processed_dir: str, expected_shape: tuple[int, int] | None = None
) -> DemClones | None:
    """The cached clone stack, ``None`` when the cache is absent.

    Raises ``ValueError`` when the cache is present but does not describe
    the loaded grid -- a stale cache is worse than no cache, because every
    probability computed from it would be about different ground.
    """
    stack_path = os.path.join(processed_dir, DEM_CLONES_FILENAME)
    meta_path = os.path.join(processed_dir, DEM_CLONES_META_FILENAME)
    if not (os.path.exists(stack_path) and os.path.exists(meta_path)):
        return None
    elevation = np.load(stack_path, mmap_mode="r")
    meta = _read_json(meta_path)
    if elevation.ndim != 3:
        raise ValueError(f"{stack_path} must be (N, R, C), got {elevation.shape}")
    box = meta.get("window") or {}
    try:
        row0, col0, rows, cols = (int(box[k]) for k in ("row0", "col0", "rows", "cols"))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{meta_path} has no usable 'window' box") from exc
    if row0 < 0 or col0 < 0 or row0 + rows > elevation.shape[1] or col0 + cols > elevation.shape[2]:
        raise ValueError(
            f"{meta_path} window {box} does not fit the {elevation.shape} clone stack"
        )
    if expected_shape is not None and (rows, cols) != tuple(int(v) for v in expected_shape):
        raise ValueError(
            f"DEM clone cache window {(rows, cols)} does not match the grid "
            f"{tuple(expected_shape)}; rebuild it with scripts/build_dem_clone_cache.py"
        )
    return DemClones(elevation=elevation, meta=meta)


def write_clone_horizons(processed_dir: str, cubes: np.ndarray, meta: dict[str, Any]) -> None:
    """Write the per-clone horizon cubes and their provenance."""
    stack = np.asarray(cubes, dtype=np.float32)
    if stack.ndim != 4:
        raise ValueError(f"clone horizons must be (N, A, h, w), got {stack.shape}")
    os.makedirs(processed_dir, exist_ok=True)
    np.save(os.path.join(processed_dir, CLONE_HORIZONS_FILENAME), stack)
    with open(
        os.path.join(processed_dir, CLONE_HORIZONS_META_FILENAME), "w", encoding="utf-8"
    ) as handle:
        json.dump(meta, handle, indent=2)


def load_clone_horizons(
    processed_dir: str,
) -> tuple[np.ndarray | None, dict[str, Any] | None]:
    """``(cubes (N, A, h, w) memmap, meta)`` or ``(None, None)`` when absent."""
    cube_path = os.path.join(processed_dir, CLONE_HORIZONS_FILENAME)
    meta_path = os.path.join(processed_dir, CLONE_HORIZONS_META_FILENAME)
    if not (os.path.exists(cube_path) and os.path.exists(meta_path)):
        return None, None
    cubes = np.load(cube_path, mmap_mode="r")
    if cubes.ndim != 4:
        raise ValueError(f"{cube_path} must be (N, A, h, w), got {cubes.shape}")
    return cubes, _read_json(meta_path)


# ── The cache builder's geometry and its clone check ───────────────────────


def padded_box(
    row_off: int,
    col_off: int,
    rows: int,
    cols: int,
    pad: int,
    raster_rows: int,
    raster_cols: int,
) -> dict[str, Any]:
    """The raster box to read for a window plus its near-field pad.

    ``row0/col0/rows/cols`` address the raw raster; ``window`` says where
    the planning window sits inside the array that read returns. The pad
    is clipped at the raster's edge and ``pad_clipped`` says so -- a clone
    horizon marched there sees less than *pad* of context in that direction.
    """
    row_off, col_off, rows, cols, pad = (int(v) for v in (row_off, col_off, rows, cols, pad))
    if pad < 0 or rows <= 0 or cols <= 0:
        raise ValueError("rows and cols must be positive and pad non-negative")
    if row_off < 0 or col_off < 0 or row_off + rows > int(raster_rows) or col_off + cols > int(raster_cols):
        raise ValueError(
            f"window ({row_off}, {col_off}, {rows}x{cols}) is outside the "
            f"{raster_rows}x{raster_cols} raster"
        )
    row0 = max(0, row_off - pad)
    col0 = max(0, col_off - pad)
    row1 = min(int(raster_rows), row_off + rows + pad)
    col1 = min(int(raster_cols), col_off + cols + pad)
    return {
        "row0": row0,
        "col0": col0,
        "rows": row1 - row0,
        "cols": col1 - col0,
        "pad": pad,
        "pad_clipped": bool(
            row_off - pad < 0 or col_off - pad < 0
            or row_off + rows + pad > int(raster_rows)
            or col_off + cols + pad > int(raster_cols)
        ),
        "window": {"row0": row_off - row0, "col0": col_off - col0, "rows": rows, "cols": cols},
    }


#: A clone of THIS window: its error against the surface is zero-mean and
#: its RMS is NASA's own toterr RMS. Outside these bounds the file is either
#: a different window (metres of difference) or a copy of the surface.
CLONE_CHECK_MAX_MEAN_M: float = 0.1
CLONE_CHECK_RMS_RATIO: tuple[float, float] = (0.7, 1.3)


def clone_check(
    clone_window: np.ndarray, surface: np.ndarray, sigma_z: np.ndarray | None
) -> dict[str, Any]:
    """Statistics of ``clone - surface`` over the window, and a verdict.

    ``rms_ratio`` is RMS(clone - surface) / RMS(sigma_z); ``None`` when no
    sigma is given, in which case only the mean is checked.
    """
    error = np.asarray(clone_window, dtype=np.float64) - np.asarray(surface, dtype=np.float64)
    finite = np.isfinite(error)
    if not finite.any():
        return {"mean_error_m": None, "rms_error_m": None, "rms_sigma_m": None, "rms_ratio": None, "ok": False}
    values = error[finite]
    mean = float(values.mean())
    rms = float(np.sqrt(np.mean(values**2)))
    rms_sigma = None
    ratio = None
    if sigma_z is not None:
        sig = np.asarray(sigma_z, dtype=np.float64)[finite]
        rms_sigma = float(np.sqrt(np.nanmean(sig**2)))
        ratio = rms / rms_sigma if rms_sigma > 0.0 else None
    ok = abs(mean) <= CLONE_CHECK_MAX_MEAN_M and rms > 0.0
    if ratio is not None:
        ok = ok and CLONE_CHECK_RMS_RATIO[0] <= ratio <= CLONE_CHECK_RMS_RATIO[1]
    return {
        "mean_error_m": round(mean, 4),
        "rms_error_m": round(rms, 4),
        "rms_sigma_m": None if rms_sigma is None else round(rms_sigma, 4),
        "rms_ratio": None if ratio is None else round(ratio, 4),
        "max_abs_error_m": round(float(np.abs(values).max()), 4),
        "ok": bool(ok),
    }


# ── The synthetic fallback ─────────────────────────────────────────────────

#: Gaussian kernel, in cells, of the synthetic error field. NASA's Site11
#: clones decorrelate over ~100 m (0.88 at 5 m, 0.34 at 25 m, 0.00 at
#: 100 m); a 2-cell kernel gives 0.78 at one cell and ~0 by 50 m -- the
#: right order, and stated as such in the provenance.
SYNTHETIC_CORRELATION_CELLS: float = 2.0


def synthetic_clones(
    surface: np.ndarray,
    sigma_z: np.ndarray | None,
    n: int,
    seed: int,
    correlation_cells: float = SYNTHETIC_CORRELATION_CELLS,
) -> np.ndarray:
    """``surface + sigma_z * xi`` for *n* spatially correlated unit fields.

    The offline fallback for a machine without network access. It needs
    NASA's own ``toterr`` for *sigma_z*: this function will not invent an
    error magnitude, and its output is labelled ``synthetic`` wherever it
    is used. Returns (n, H, W) float32; the same *seed* gives the same stack.
    """
    from scipy.ndimage import gaussian_filter

    base = np.asarray(surface, dtype=np.float64)
    if sigma_z is None:
        raise ValueError(
            "synthetic clones need NASA's Z-uncertainty map (toterr) as sigma_z; "
            "no error magnitude is invented"
        )
    sigma = np.asarray(sigma_z, dtype=np.float64)
    if sigma.shape != base.shape:
        raise ValueError(f"sigma_z {sigma.shape} must match the surface {base.shape}")
    if not np.all(np.isfinite(sigma)) or np.any(sigma < 0.0):
        raise ValueError("sigma_z must be finite and non-negative")
    count = int(n)
    if count < 1:
        raise ValueError("n must be at least 1")

    rng = np.random.default_rng(int(seed))
    out = np.empty((count,) + base.shape, dtype=np.float32)
    for index in range(count):
        white = rng.standard_normal(base.shape)
        field = gaussian_filter(white, sigma=float(correlation_cells), mode="reflect")
        scale = float(field.std())
        xi = field / scale if scale > 0.0 else white
        out[index] = base + sigma * xi
    return out


# ── Slope and passability, per clone ───────────────────────────────────────


def ensemble_slopes(clones_window: np.ndarray, resolution_m: float) -> np.ndarray:
    """(N, H, W) float32 slopes, one per clone, with the pipeline's operator."""
    from .data_loader import slope_deg_from_elevation

    stack = np.asarray(clones_window)
    if stack.ndim != 3:
        raise ValueError(f"clones must be (N, H, W), got {stack.shape}")
    out = np.empty(stack.shape, dtype=np.float32)
    for index in range(stack.shape[0]):
        out[index] = slope_deg_from_elevation(stack[index], resolution_m)
    return out


def traversable_probability(
    slopes: np.ndarray,
    thermal: np.ndarray,
    elevation: np.ndarray | None,
    rover: Any,
    thermal_min: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """``(P (H, W) float32, masks (N, H, W) bool)``: the fraction of clones in
    which each cell passes the planner's own gate for *rover*.

    The gate is :func:`app.traversability.compute_traversability_bool`,
    unchanged; only the slope varies by clone. The thermal field is held
    (see the module docstring), so a cell the cold-end gate closes has
    probability zero in every clone.
    """
    from .traversability import compute_traversability_bool

    stack = np.asarray(slopes, dtype=np.float64)
    masks = np.stack(
        [
            compute_traversability_bool(
                stack[index], thermal, elevation, rover=rover, thermal_min=thermal_min
            )
            for index in range(stack.shape[0])
        ]
    )
    return masks.mean(axis=0).astype(np.float32), masks


def slope_sigma(slopes: np.ndarray) -> np.ndarray:
    """Ensemble standard deviation of the slope, degrees, (H, W) float32."""
    return np.std(np.asarray(slopes, dtype=np.float64), axis=0).astype(np.float32)


# ── The per-rover layer cache ──────────────────────────────────────────────

#: Layers the ensemble publishes, in manifest order, with their provenance
#: for a cache of NASA's clones. p_traversable and slope_sigma are derived
#: by this module; the two sigma maps are NASA's own error-model outputs --
#: MODEL, not MEASURED: nobody measured a 0.4 m error, the adjustment's
#: covariance predicts one. A synthetic cache demotes the two derived layers
#: to SYNTHETIC, the label the elevation-proxy shadow already carries.
UNCERTAINTY_LAYERS: tuple[str, ...] = (
    "p_traversable",
    "slope_sigma",
    "elevation_sigma",
    "slope_sigma_nasa",
)
_LAYER_VALIDITY: dict[str, str] = {
    "p_traversable": "DERIVED",
    "slope_sigma": "DERIVED",
    "elevation_sigma": "MODEL",
    "slope_sigma_nasa": "MODEL",
}
_cache: dict[tuple, tuple[dict[str, np.ndarray], dict[str, Any]]] = {}
_CACHE_LIMIT = 8


def clear_uncertainty_cache() -> None:
    _cache.clear()


def _unavailable(reason: str) -> tuple[None, dict[str, Any]]:
    return None, {"model": "unavailable", "reason": reason}


def uncertainty_layers_for_grids(
    grids: dict[str, Any], rover_id: str
) -> tuple[dict[str, np.ndarray] | None, dict[str, Any]]:
    """``(layers, info)`` for the loaded grids and a rover.

    ``layers`` holds ``p_traversable``, ``slope_sigma``, the per-clone
    ``clone_traversable`` stack and, when cached, NASA's ``elevation_sigma``
    and ``slope_sigma_nasa``; ``None`` with ``info["model"] ==
    "unavailable"`` (and ``reason``) when there is no clone cache beside the
    processed grids or it does not describe them. ``info`` is the pedigree
    /api/terrain publishes: the NASA product, the clone count and indices,
    what was held fixed. Twenty clones through the gate is ~1 s, so results
    are kept in a small cache keyed by (processed_dir, cache mtime, rover,
    slope limit, shape).
    """
    from .constants import get_rover

    metadata = grids.get("metadata") or {}
    processed_dir = metadata.get("processed_dir")
    if not processed_dir:
        return _unavailable(
            "the loaded grids carry no processed_dir; the DEM clone cache lives "
            "beside the processed grids (scripts/build_dem_clone_cache.py)"
        )
    stack_path = os.path.join(str(processed_dir), DEM_CLONES_FILENAME)
    if not os.path.exists(stack_path):
        return _unavailable(
            f"no {DEM_CLONES_FILENAME} beside the processed grids; run "
            "scripts/build_dem_clone_cache.py to fetch NASA's DEM clones"
        )
    shape = tuple(int(v) for v in np.asarray(grids["elevation"]).shape)
    rover = get_rover(rover_id)
    key = (
        str(processed_dir),
        int(os.stat(stack_path).st_mtime_ns),
        str(rover_id),
        float(rover["slope_max_deg"]),
        shape,
    )
    hit = _cache.get(key)
    if hit is not None:
        return hit

    try:
        clones = load_dem_clones(str(processed_dir), expected_shape=shape)
        if clones is None:
            return _unavailable(
                f"{DEM_CLONES_FILENAME} has no {DEM_CLONES_META_FILENAME} beside it; "
                "rebuild with scripts/build_dem_clone_cache.py"
            )
        resolution_m = float(metadata["resolution_m"])
        slopes = ensemble_slopes(clones.window, resolution_m)
        p, masks = traversable_probability(
            slopes,
            grids["thermal"],
            grids.get("elevation"),
            rover,
            thermal_min=grids.get("thermal_min"),
        )
        layers: dict[str, np.ndarray] = {
            "p_traversable": p,
            "slope_sigma": slope_sigma(slopes),
            # The per-clone stacks the route band and the plan endpoints read;
            # not published as layers (with_uncertainty_layers skips them).
            "clone_traversable": masks,
            "clone_slopes": slopes,
        }
        for name, filename in (
            ("elevation_sigma", ELEVATION_SIGMA_FILENAME),
            ("slope_sigma_nasa", SLOPE_SIGMA_NASA_FILENAME),
        ):
            path = os.path.join(str(processed_dir), filename)
            if os.path.exists(path):
                sigma = np.load(path).astype(np.float32)
                if tuple(sigma.shape) != shape:
                    raise ValueError(f"{filename} {sigma.shape} does not match the grid {shape}")
                layers[name] = sigma
    except Exception as exc:
        # A stale or broken cache degrades to an honest "unavailable", never
        # to a probability layer about different ground (and never a 500).
        return _unavailable(f"DEM clone cache unusable ({exc}); rebuild with scripts/build_dem_clone_cache.py")

    meta = clones.meta
    provenance = str(meta.get("provenance", "unknown"))
    horizons_meta = None
    horizon_meta_path = os.path.join(str(processed_dir), CLONE_HORIZONS_META_FILENAME)
    if os.path.exists(horizon_meta_path):
        try:
            horizons_meta = _read_json(horizon_meta_path)
        except (OSError, ValueError):
            horizons_meta = None
    info: dict[str, Any] = {
        "model": provenance,
        "site": meta.get("site"),
        "product_url": meta.get("product_url", PGDA_PRODUCT_URL),
        "reference": meta.get("reference", PGDA_REFERENCE),
        "clone_kind": meta.get("clone_kind"),
        "fetched_utc": meta.get("fetched_utc"),
        "n_clones": clones.n_clones,
        "clone_indices": clones.clone_indices,
        "window_offset": meta.get("window_offset"),
        "near_range_m": meta.get("near_range_m"),
        "sigma": meta.get("sigma"),
        "error_across_clones": meta.get("error_across_clones"),
        "rover_id": str(rover_id),
        "slope_max_deg": float(rover["slope_max_deg"]),
        "thermal_field_held_fixed": True,
        "far_field_held_fixed": True,
        "earth_visibility_cloned": False,
        "layers": [name for name in UNCERTAINTY_LAYERS if name in layers],
        "clone_horizons": None
        if horizons_meta is None
        else {
            "n_clones": len(horizons_meta.get("clone_indices", [])),
            "stride": horizons_meta.get("stride"),
            "near_range_m": horizons_meta.get("near_range_m"),
            "neglected_horizon_shift_deg_max": horizons_meta.get("neglected_horizon_shift_deg_max"),
            "surf_check_max_abs_deg": horizons_meta.get("surf_check_max_abs_deg"),
        },
        "standard": "NASA-STD-7009 results uncertainty: input pedigree above",
    }
    if provenance == "synthetic":
        info["synthetic"] = meta.get("synthetic")
    if len(_cache) >= _CACHE_LIMIT:
        _cache.pop(next(iter(_cache)))
    _cache[key] = (layers, info)
    return layers, info


def with_uncertainty_layers(grids: dict[str, Any], rover_id: str) -> dict[str, Any]:
    """A copy of *grids* carrying the ensemble layers and their provenance,
    or *grids* itself when there is no clone cache."""
    from .traversability import weakest_validity

    layers, info = uncertainty_layers_for_grids(grids, rover_id)
    if layers is None:
        return grids
    out = dict(grids)
    metadata = dict(grids.get("metadata") or {})
    validity = dict(metadata.get("layer_validity") or {})
    synthetic = info.get("model") == "synthetic"
    for name in UNCERTAINTY_LAYERS:
        if name not in layers:
            continue
        out[name] = layers[name]
        label = _LAYER_VALIDITY[name]
        if name in ("p_traversable", "slope_sigma") and synthetic:
            label = "SYNTHETIC"
        if name == "p_traversable":
            # Inherits the held thermal field's provenance, as traversable does.
            label = weakest_validity(label, str(validity.get("thermal", "DERIVED")))
        validity[name] = label
    metadata["layer_validity"] = validity
    metadata["dem_uncertainty"] = info
    out["metadata"] = metadata
    return out


# ── Illumination across clones ─────────────────────────────────────────────


def illuminated_probability(cubes: np.ndarray, az_deg: float, elev_deg: float) -> np.ndarray:
    """(h, w) float32: the fraction of clone horizon cubes the Sun clears.

    Exactly :func:`app.illumination.illuminated_mask` applied to every
    clone's cube in turn -- its rules (nearest azimuth bin, the no-horizon
    sentinel) are reused, not restated.
    """
    return illuminated_probability_series(
        cubes, [{"azimuth_grid_deg": az_deg, "elevation_deg": elev_deg}]
    )[0]


def illuminated_probability_series(cubes: np.ndarray, track: Any) -> np.ndarray:
    """(T, h, w) float32 for a body track (``azimuth_grid_deg``,
    ``elevation_deg`` per slice, as ``body_track_for_series`` returns).

    One clone cube in memory at a time: *cubes* may be the memmapped cache
    (a hundred cubes are 450 MB at the production stride), and the lit
    count is accumulated clone by clone.
    """
    from .illumination import illuminated_mask

    if getattr(cubes, "ndim", None) != 4:
        raise ValueError(f"clone cubes must be (N, A, h, w), got {getattr(cubes, 'shape', None)}")
    n_clones = int(cubes.shape[0])
    height, width = int(cubes.shape[2]), int(cubes.shape[3])
    steps = [(float(entry["azimuth_grid_deg"]), float(entry["elevation_deg"])) for entry in track]
    if not steps:
        return np.zeros((0, height, width), dtype=np.float32)
    lit_count = np.zeros((len(steps), height, width), dtype=np.float64)
    for index in range(n_clones):
        cube = np.asarray(cubes[index])
        for step, (az_deg, elev_deg) in enumerate(steps):
            lit_count[step] += illuminated_mask(cube, az_deg, elev_deg)
    return (lit_count / float(n_clones)).astype(np.float32)


def uncertain_fraction(p: np.ndarray, lo: float = 0.05, hi: float = 0.95) -> float:
    """The fraction of finite cells whose probability is strictly between
    *lo* and *hi* -- the cells the ensemble cannot call either way."""
    # P is a count over clones, k / N, stored as float32: 5 / 100 reads
    # 0.0500000007 and would pass a strict "> 0.05". Rounding makes the
    # bounds exact for any N a cache can hold.
    arr = np.round(np.asarray(p, dtype=np.float64), 6)
    finite = np.isfinite(arr)
    if not finite.any():
        return 0.0
    return float(((arr > float(lo)) & (arr < float(hi)))[finite].mean())


# ── A route across clones ──────────────────────────────────────────────────


def route_traversable_probability(
    masks: np.ndarray, cells: Any, coarsen: int = 1
) -> tuple[np.ndarray, np.ndarray]:
    """``(per_state (S,) float32, feasible (N,) bool)``: per route cell the
    fraction of clones that pass it, and per clone whether every cell of the
    route passes. *cells* are on the planner's grid at *coarsen*; a coarse
    cell passes only when all its fine cells do (``coarsen_traversable``)."""
    from .cost_cube import coarsen_traversable

    stack = np.asarray(masks, dtype=bool)
    if stack.ndim != 3:
        raise ValueError(f"clone masks must be (N, H, W), got {stack.shape}")
    factor = max(1, int(coarsen))
    if factor > 1:
        stack = np.stack([coarsen_traversable(stack[k], factor) for k in range(stack.shape[0])])
    rows = np.asarray([int(cell[0]) for cell in cells])
    cols = np.asarray([int(cell[1]) for cell in cells])
    if rows.size == 0:
        return np.zeros(0, dtype=np.float32), np.ones(stack.shape[0], dtype=bool)
    at_route = stack[:, rows, cols]
    return at_route.mean(axis=0).astype(np.float32), at_route.all(axis=1)


#: The per-clone route metrics the band is built from.
BAND_METRICS: tuple[str, ...] = (
    "duration_h",
    "drive_hours",
    "gross_drive_wh",
    "battery_used_wh",
    "min_battery_pct",
    "final_battery_pct",
    "max_continuous_shadow_h",
)


def route_band(
    states: Any,
    clone_slopes: np.ndarray,
    resolution_m: float,
    rover: Any,
    slice_hours: float,
    skies: Any,
    initial_soc_frac: float = 1.0,
    nominal_slope: np.ndarray | None = None,
    nominal_sky: Any = None,
    sherpa: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """A planned route priced once per DEM clone: the 5-95 percent band.

    For clone *k* the route's legs are priced with the clone's slopes the
    way ``astar_4d`` priced them (:func:`app.stress_test.route_legs`), then
    driven once with every SHERPA uncertainty at its nominal value
    (:func:`app.stress_test.simulate_runs`) against ``skies[k]`` -- one
    :class:`~app.stress_test.RouteSky` per clone, or one shared sky. The
    band is therefore attributable to the DEM alone. A clone whose route
    has an edge the travel model cannot price (a 90 deg step) is dropped
    and named in ``unpriceable``; whether the clone still considers every
    route cell passable is a separate question, answered by
    :func:`route_traversable_probability`.

    *sherpa* -- ``{"n_runs", "seed", "perturbations"}`` -- adds the combined
    picture: ``n_runs`` SHERPA-perturbed runs per clone, pooled, with the
    completion rate's Wilson interval. Same seed, same result.
    """
    from .stress_test import (
        FAILURE_NAMES,
        PERTURBATION_SOURCE,
        SHERPA_DEFAULTS,
        RouteSky,
        _distribution,
        _nominal_samples,
        _nullable,
        _rate,
        route_legs,
        sample_perturbations,
        simulate_runs,
        wilson_interval,
    )

    stack = np.asarray(clone_slopes, dtype=np.float64)
    if stack.ndim != 3:
        raise ValueError(f"clone slopes must be (N, h, w), got {stack.shape}")
    n_clones = int(stack.shape[0])
    if isinstance(skies, RouteSky):
        sky_list = [skies] * n_clones
    else:
        sky_list = list(skies)
        if len(sky_list) != n_clones:
            raise ValueError(f"{len(sky_list)} skies for {n_clones} clones")

    e_cap_wh = float(rover["e_cap_wh"])
    pct = 100.0 / e_cap_wh if e_cap_wh > 0.0 else 0.0
    soc0 = float(initial_soc_frac)
    nominal_samples = _nominal_samples(soc0)

    def price(slope: np.ndarray, sky: RouteSky):
        legs = route_legs(states, slope, resolution_m, rover, slice_hours)
        run = simulate_runs(legs, sky, rover, nominal_samples)
        return legs, {
            "reached": bool(run.reached[0]),
            "first_failure": FAILURE_NAMES[int(run.first_failure[0])],
            "duration_h": _nullable(run.duration_h[0]),
            "drive_hours": _nullable(float(np.sum(legs.travel_h))),
            "gross_drive_wh": _nullable(float(np.sum(legs.traction_w * legs.travel_h))),
            "battery_used_wh": _nullable(soc0 * e_cap_wh - float(run.final_battery_wh[0])),
            "min_battery_pct": _nullable(max(0.0, float(run.min_battery_wh[0])) * pct),
            "final_battery_pct": _nullable(max(0.0, float(run.final_battery_wh[0])) * pct),
            "max_continuous_shadow_h": _nullable(run.max_dark_h[0]),
        }

    per_clone: dict[str, list] = {key: [] for key in BAND_METRICS}
    reached: list[bool] = []
    failures: list[str] = []
    unpriceable: list[int] = []
    priced: list[tuple[int, Any]] = []
    for index in range(n_clones):
        try:
            legs, metrics = price(stack[index], sky_list[index])
        except ValueError:
            unpriceable.append(index)
            continue
        priced.append((index, legs))
        reached.append(metrics["reached"])
        failures.append(metrics["first_failure"])
        for key in BAND_METRICS:
            per_clone[key].append(metrics[key])

    def _column(key: str) -> np.ndarray:
        return np.asarray(
            [np.nan if value is None else float(value) for value in per_clone[key]], dtype=np.float64
        )

    n_priced = len(priced)
    reached_count = int(sum(reached))
    low, high = wilson_interval(reached_count, n_priced) if n_priced else (0.0, 1.0)

    nominal = None
    nominal_legs = None
    if nominal_slope is not None:
        try:
            nominal_legs, nominal = price(
                np.asarray(nominal_slope, dtype=np.float64),
                nominal_sky if nominal_sky is not None else sky_list[0],
            )
        except ValueError:
            nominal = None
    reference_legs = nominal_legs if nominal_legs is not None else (priced[0][1] if priced else None)
    route_info = (
        None
        if reference_legs is None
        else {
            "n_states": reference_legs.n_states,
            "move_steps": reference_legs.n_moves,
            "wait_steps": reference_legs.n_waits,
            "planned_duration_h": round(reference_legs.planned_duration_h, 4),
            "odometry_m": round(reference_legs.odometry_m, 3),
        }
    )

    sherpa_block = None
    if sherpa is not None:
        n_runs = int(sherpa.get("n_runs", 200))
        seed = int(sherpa.get("seed", 0))
        perturbations = sherpa.get("perturbations") or SHERPA_DEFAULTS
        pooled = {
            "reached": [], "failure": [], "duration_h": [],
            "min_battery_wh": [], "final_battery_wh": [], "max_dark_h": [],
        }
        for offset, (index, legs) in enumerate(priced):
            rng = np.random.default_rng(seed + offset)
            samples = sample_perturbations(
                rng, n_runs, perturbations, soc0, legs.planned_duration_h
            )
            run = simulate_runs(legs, sky_list[index], rover, samples)
            pooled["reached"].append(run.reached)
            pooled["failure"].append(run.first_failure)
            pooled["duration_h"].append(run.duration_h)
            pooled["min_battery_wh"].append(run.min_battery_wh)
            pooled["final_battery_wh"].append(run.final_battery_wh)
            pooled["max_dark_h"].append(run.max_dark_h)
        if priced:
            joined = {key: np.concatenate(values) for key, values in pooled.items()}
        else:
            joined = {key: np.zeros(0) for key in pooled}
        failure_codes = joined["failure"].astype(np.int64) if joined["failure"].size else np.zeros(0, dtype=np.int64)
        sherpa_block = {
            "n_runs_per_clone": n_runs,
            "n_runs_total": int(n_runs * n_priced),
            "seed": seed,
            "completion": _rate(joined["reached"].astype(bool)),
            "failures": {
                name: int(np.count_nonzero(failure_codes == code))
                for code, name in enumerate(FAILURE_NAMES)
                if code > 0
            },
            "metrics": {
                "duration_h": _distribution(joined["duration_h"]),
                "min_battery_pct": _distribution(np.maximum(0.0, joined["min_battery_wh"]) * pct),
                "final_battery_pct": _distribution(np.maximum(0.0, joined["final_battery_wh"]) * pct),
                "max_continuous_shadow_h": _distribution(joined["max_dark_h"]),
            },
            "perturbations": {**perturbations.to_dict(), "source": PERTURBATION_SOURCE},
        }

    return {
        "n_clones": n_clones,
        "clones_priced": n_priced,
        "unpriceable": unpriceable,
        "route": route_info,
        "reached": {
            "count": reached_count,
            "fraction": round(reached_count / n_priced, 4) if n_priced else None,
            "ci95": [round(low, 4), round(high, 4)],
        },
        "failures": {
            name: int(sum(1 for f in failures if f == name)) for name in FAILURE_NAMES if name != "none"
        },
        "metrics": {key: _distribution(_column(key)) for key in BAND_METRICS},
        "per_clone": {
            **{key: list(per_clone[key]) for key in BAND_METRICS},
            "reached": list(reached),
            "clone_index": [index for index, _ in priced],
        },
        "nominal": nominal,
        "sherpa": sherpa_block,
    }


# ── The march, split in two ────────────────────────────────────────────────


def near_far_steps(
    resolution_m: float,
    near_range_m: float,
    max_range_m: float,
    max_steps: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Partition :func:`app.horizon.march_distances_cells` at *near_range_m*.

    ``(near, far)`` in cells: the near samples (``<= near_range_m``) are
    re-marched on every clone, the far ones (``> near_range_m``) once on the
    surface DEM. Their concatenation is exactly the single-pass march, so
    ``max(horizon(near), horizon(far))`` reproduces the production cube.
    """
    full = march_distances_cells(float(resolution_m), float(max_range_m), int(max_steps))
    distance_m = full * float(resolution_m)
    near = full[distance_m <= float(near_range_m)]
    far = full[distance_m > float(near_range_m)]
    if near.size == 0:
        raise ValueError(
            f"near_range_m={near_range_m} is below the first sample "
            f"({distance_m[0]:g} m); nothing would be re-marched on the clones"
        )
    return near, far
