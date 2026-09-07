"""Binary terrain transport for the 3-D viewer.

``/api/layers`` hands a browser a nested list of Python floats. For the
shipped 500x500 grid that is ~4.25 MB of text describing 1.00 MB of numbers,
which is why the endpoint is capped at a 65 536-cell preview and why the
frontend defaults to ``downsample=2``. A 3-D engine wants the opposite
trade: the whole field, at native resolution, already in the memory layout
the GPU consumes.

This module is that second representation. It does not replace the JSON
layer -- a 2-D map overlay is well served by one -- it sits beside it::

    GET /api/terrain                    scene manifest, one call
    GET /api/layers/{name}?format=f32   raw little-endian float32

The manifest exists because the binary payload is deliberately headerless:
a ``Float32Array`` and nothing else, so ``new Float32Array(await
r.arrayBuffer())`` is the whole decode. Everything needed to interpret it --
shape, georeference, per-layer range and units -- comes from the manifest,
with the same values repeated in ``X-Layer-*`` response headers so a caller
that fetches one layer in isolation is never guessing.

No-data convention: **NaN, and only NaN.** The grids carry two kinds of
absent value -- NaN where a field is undefined, and +inf in ``cost`` where a
cell is impassable (about 60 000 of them in the current shipped grid). The JSON path
flattens both to ``null``; float32 would carry the infinity through to a
colour ramp or a vertex position, where it is a silently broken render
rather than a visible hole. Both become NaN here, and the count is
reported.
"""

from __future__ import annotations

from typing import Any, Iterable

import numpy as np

# Little-endian float32, stated rather than inherited. Every platform this
# runs on today is little-endian, so ``astype(np.float32)`` would produce
# identical bytes -- but the wire format is a contract with a browser, and a
# contract that happens to hold is not the same as one that is declared.
BINARY_DTYPE = np.dtype("<f4")
BINARY_DTYPE_NAME = "float32"
BINARY_ENDIAN = "little"
BINARY_ORDER = "row-major"
BINARY_NODATA = "NaN"
BINARY_MEDIA_TYPE = "application/octet-stream"

#: Response headers the binary layer endpoint sets. Listed here so the CORS
#: middleware can expose exactly these -- a browser cannot read a custom
#: header on a cross-origin response unless the server names it in
#: ``Access-Control-Expose-Headers``, and the frontend runs on a different
#: origin from the API in every configuration except the Vite dev proxy.
BINARY_LAYER_HEADERS = (
    "X-Layer-Name",
    "X-Layer-Dtype",
    "X-Layer-Endian",
    "X-Layer-Order",
    "X-Layer-Rows",
    "X-Layer-Cols",
    "X-Layer-Downsample",
    "X-Layer-Resolution-M",
    "X-Layer-Min",
    "X-Layer-Max",
    "X-Layer-Nodata",
    "X-Layer-Validity",
)

#: Response headers ``GET /api/illumination-series?format=f32`` sets on its
#: binary payload. A separate tuple from ``BINARY_LAYER_HEADERS`` because the
#: series payload has an extra (time) axis a single layer does not -- listed
#: here, same as that tuple, so the CORS middleware can expose exactly these.
SERIES_HEADERS = (
    "X-Series-Field",
    "X-Series-Slices",
    "X-Series-Rows",
    "X-Series-Cols",
    "X-Series-Downsample",
    "X-Series-Resolution-M",
    "X-Series-Dtype",
    "X-Series-Endian",
    "X-Series-Order",
)

#: Physical unit of each layer, for axis labels and legend text. The 3-D
#: viewer colours several of these and displaces geometry with another;
#: without units it has to hard-code the strings it prints beside the
#: numbers.
LAYER_UNITS: dict[str, str] = {
    "elevation": "m",
    "slope": "deg",
    "aspect": "deg",
    "thermal": "degC",
    "thermal_min": "degC",
    "shadow_ratio": "fraction",
    "cost": "dimensionless",
    "traversable": "boolean",
    "earth_visibility": "fraction",
    # The DEM-clone ensemble (B3): present only with the clone cache.
    "p_traversable": "fraction",
    "slope_sigma": "deg",
    "elevation_sigma": "m",
    "slope_sigma_nasa": "deg",
    # NASA's measured products (C4): present only with the roughness cache.
    "roughness": "m",
    "psr": "boolean",
    # The recovery policy's fields (B1): served by GET /api/survival, never
    # by the manifest -- they depend on a goal, an epoch and a battery.
    "survival_probability": "fraction",
    "best_action": "code",
    # The thermal dwell (C6): served by GET /api/thermal-dwell, never by the
    # manifest -- it depends on an epoch, a rover and an inner temperature.
    "max_dwell_h": "h",
    "dwell_side": "code",
}

#: What each layer means to someone building the scene, in one line.
LAYER_DESCRIPTIONS: dict[str, str] = {
    "elevation": "Surface height above the sphere datum; the displacement field.",
    "slope": "Terrain slope magnitude.",
    "aspect": "Downhill azimuth, degrees clockwise from grid north.",
    "thermal": "Annual peak surface temperature.",
    "thermal_min": "Cold-end equilibrium surface temperature.",
    "shadow_ratio": "Fraction of the sampled window the cell spends shadowed.",
    "cost": "Weighted multi-criteria traverse cost; NaN where impassable.",
    "traversable": "1.0 passable, 0.0 not.",
    "earth_visibility": (
        "Fraction of the sampled span in which the Earth is above the local "
        "horizon: where a direct-to-Earth radio link is geometrically possible."
    ),
    "p_traversable": (
        "Fraction of NASA's DEM clones in which the cell passes this rover's "
        "slope and cold-end gates: 1 certainly passable, 0 certainly not."
    ),
    "slope_sigma": "Standard deviation of the slope across the DEM-clone ensemble.",
    "elevation_sigma": (
        "NASA PGDA's total elevation uncertainty (toterr) for the DEM: the "
        "adjustment's error model, not a measurement."
    ),
    "slope_sigma_nasa": "NASA PGDA's slope uncertainty (slperr) for the DEM.",
    "roughness": (
        "NASA LOLA LDRM roughness (PGDA product 90): spread of LOLA spot height "
        "residuals around a plane fit within a 100 m window, posted at 50 m/px; every "
        "5 m cell carries its 50 m pixel's value -- a hectometre-scale block statistic, "
        "not the cell's own roughness."
    ),
    "psr": (
        "NASA PGDA PSR map (LPSR, 20 m/px): 1.0 inside a permanently shadowed region, "
        "0.0 outside. A measured product and a check of shadow_ratio, not a planning input."
    ),
    "survival_probability": (
        "Probability that the optimal recovery policy from this coarse block, at the "
        "requested hour and state of charge, reaches the safe set (goal or safe haven "
        "with the required charge) before the horizon under the assumed Poisson fault "
        "model (B1; MODEL). NaN where the block is impassable."
    ),
    "best_action": (
        "The recovery policy's action code at that block, hour and charge: 0-7 a move "
        "(N, S, W, E, NW, NE, SW, SE), 8 wait, 254 already safe, 255 none (failed or "
        "impassable)."
    ),
    "max_dwell_h": (
        "Hours a rover arriving at this coarse block at the requested hour with its "
        "nominal inner temperature may stand still before the first-order lag toward the "
        "cell's surface-derived inner temperature leaves the tightest declared "
        "battery/electronics envelope (C6; MODEL, uncalibrated). Capped at the lookahead "
        "where open-ended; NaN where the block is impassable."
    ),
    "dwell_side": (
        "Which side of the envelope the dwell ends on: 0 none within the lookahead, "
        "1 cold, 2 hot. NaN where impassable."
    ),
}

#: Layers both representations serve, in the order the manifest lists them.
TERRAIN_LAYERS: tuple[str, ...] = (
    "elevation",
    "slope",
    "aspect",
    "thermal",
    "thermal_min",
    "shadow_ratio",
    "cost",
    "traversable",
    # Optional: present only when scripts/build_earth_visibility_cache.py
    # has run. terrain_manifest skips layers the grids do not carry.
    "earth_visibility",
    # Optional: present only when scripts/build_dem_clone_cache.py has run
    # (B3). Same rule: absent from the manifest, not published as unknown.
    "p_traversable",
    "slope_sigma",
    "elevation_sigma",
    "slope_sigma_nasa",
    # NASA's measured roughness and PSR layers (C4), when cached.
    "roughness",
    "psr",
)


def encode_layer_f32(layer: np.ndarray) -> bytes:
    """Serialise one grid as headerless little-endian float32, row-major.

    ``bool`` arrays (``traversable``) become 1.0/0.0 so the caller decodes
    every layer into the same ``Float32Array`` -- one code path in the
    client, one texture format on the GPU.
    """
    values = np.asarray(layer, dtype=np.float64)
    # Both flavours of absent value collapse to NaN here; see module docstring.
    values = np.where(np.isfinite(values), values, np.nan)
    cast = np.ascontiguousarray(values, dtype=BINARY_DTYPE)
    # A finite float64 beyond float32 range (~3.4e38) overflows to +/-inf on
    # the cast above, silently reintroducing exactly the value this function
    # exists to remove. No layer reaches that magnitude today, but the "NaN,
    # and only NaN" promise is stated as absolute -- so enforce it after the
    # cast, not just before.
    cast[~np.isfinite(cast)] = np.float32(np.nan)
    return cast.tobytes()


def layer_stats(layer: np.ndarray) -> dict[str, Any]:
    """Finite range and no-data count for one grid.

    The range is what a colour ramp normalises against and what an elevation
    displacement scales by, so it is computed over the *finite* values only:
    a single infinity in ``cost`` would otherwise collapse every other cell
    to one end of the ramp.
    """
    values = np.asarray(layer, dtype=np.float64)
    finite = np.isfinite(values)
    nodata = int(values.size - int(finite.sum()))
    if not finite.any():
        return {"min": None, "max": None, "nodata": nodata, "cells": int(values.size)}
    return {
        "min": float(np.min(values[finite])),
        "max": float(np.max(values[finite])),
        "nodata": nodata,
        "cells": int(values.size),
    }


def suggested_vertical_exaggeration(
    relief_m: float, span_m: float, target_ratio: float = 0.2
) -> float:
    """A starting z-scale for the mesh, snapped to a readable number.

    Relief that is a fifth of the span reads as terrain at 1:1; much flatter
    than that and a true-scale render looks like a painted plane, which is
    the usual reason a DEM viewer ships an exaggeration slider with no idea
    where to set it. This answers "where does the slider start", not "what
    is correct" -- 1.0 is always correct, and is what this returns whenever
    the ground is already dramatic enough to show itself.
    """
    if relief_m <= 0.0 or span_m <= 0.0:
        return 1.0
    ratio = relief_m / span_m
    if ratio >= target_ratio:
        return 1.0
    raw = target_ratio / ratio
    # Snap up the 1-2-5 ladder so the default is a number a person would
    # have typed, not 3.7183.
    ladder = (1.0, 1.5, 2.0, 3.0, 5.0, 7.5, 10.0, 15.0, 20.0, 30.0, 50.0)
    for step in ladder:
        if raw <= step:
            return step
    return 50.0


def binary_layer_headers(
    layer_name: str,
    layer: np.ndarray,
    downsample: int,
    resolution_m: float,
    validity: str | None,
) -> dict[str, str]:
    """``X-Layer-*`` headers describing one binary payload.

    Duplicates what the manifest already says. That redundancy is the
    point: a layer fetched on its own stays self-describing, and a client
    that never calls ``/api/terrain`` can still size its ``Float32Array``
    and normalise its ramp.
    """
    array = np.asarray(layer)
    stats = layer_stats(array)
    rows, cols = int(array.shape[0]), int(array.shape[1])
    headers = {
        "X-Layer-Name": layer_name,
        "X-Layer-Dtype": BINARY_DTYPE_NAME,
        "X-Layer-Endian": BINARY_ENDIAN,
        "X-Layer-Order": BINARY_ORDER,
        "X-Layer-Rows": str(rows),
        "X-Layer-Cols": str(cols),
        "X-Layer-Downsample": str(int(downsample)),
        # The *effective* pitch of the returned grid, not the source grid: a
        # caller that asked for downsample=4 needs 20 m to place its
        # vertices, and recomputing it from two other headers is exactly the
        # arithmetic that ends up wrong in one of the three places it is done.
        "X-Layer-Resolution-M": repr(float(resolution_m) * int(downsample)),
        "X-Layer-Nodata": str(stats["nodata"]),
    }
    if stats["min"] is not None:
        headers["X-Layer-Min"] = repr(stats["min"])
        headers["X-Layer-Max"] = repr(stats["max"])
    if validity:
        headers["X-Layer-Validity"] = str(validity)
    return headers


def terrain_manifest(
    grids: dict[str, Any],
    rover_id: str,
    rover_name: str,
    weights: dict[str, float] | None = None,
    layer_names: Iterable[str] = TERRAIN_LAYERS,
    binary_query: str = "",
) -> dict[str, Any]:
    """Everything a 3-D scene needs before it fetches a single byte of grid.

    One call: mesh dimensions, the georeference that ties the mesh to the
    Moon, the elevation range the displacement scales by, the decode
    contract, and per-layer range/units/validity with the URL to fetch each.
    """
    metadata = dict(grids.get("metadata") or {})
    # The elevation array's own shape is authoritative -- it is what
    # binary_layer_headers reports per-layer, byte for byte. metadata["shape"]
    # is expected to agree, but a client sizes its Float32Array off THIS
    # manifest; if the two ever drift, trusting the array keeps
    # bytes_per_layer honest even though the mismatch itself would still be
    # worth investigating.
    sample = np.asarray(grids["elevation"])
    rows, cols = int(sample.shape[0]), int(sample.shape[1])
    resolution_m = float(metadata.get("resolution_m", 1.0))
    validity = dict(metadata.get("layer_validity") or {})

    layers: dict[str, Any] = {}
    for name in layer_names:
        if name not in grids:
            continue
        stats = layer_stats(grids[name])
        suffix = f"&{binary_query}" if binary_query else ""
        layers[name] = {
            "units": LAYER_UNITS.get(name, ""),
            "description": LAYER_DESCRIPTIONS.get(name, ""),
            "validity": validity.get(name),
            "min": stats["min"],
            "max": stats["max"],
            "nodata": stats["nodata"],
            "binary_url": f"/api/layers/{name}?format=f32{suffix}",
            "json_url": f"/api/layers/{name}",
        }

    elevation = np.asarray(grids["elevation"], dtype=np.float64)
    finite_elev = elevation[np.isfinite(elevation)]
    if finite_elev.size:
        elev_min = float(finite_elev.min())
        elev_max = float(finite_elev.max())
    else:
        elev_min = elev_max = 0.0
    relief = elev_max - elev_min
    span_row = rows * resolution_m
    span_col = cols * resolution_m

    manifest: dict[str, Any] = {
        "grid": {
            "rows": rows,
            "cols": cols,
            "resolution_m": resolution_m,
            "span_m": [span_row, span_col],
            "cells": rows * cols,
        },
        "georeference": {
            "origin": metadata.get("origin"),
            "crs": metadata.get("crs"),
            "window_offset": metadata.get("window_offset"),
            # Row 0 is the grid's north edge and col 0 its west edge; a
            # viewer that builds a PlaneGeometry in XY and forgets this
            # renders the site mirrored, which looks plausible and is wrong.
            "row_axis": "north-to-south",
            "col_axis": "west-to-east",
        },
        "elevation": {
            "min_m": elev_min,
            "max_m": elev_max,
            "relief_m": relief,
            "vertical_exaggeration_suggested": suggested_vertical_exaggeration(
                relief, max(span_row, span_col)
            ),
        },
        "binary_format": {
            "dtype": BINARY_DTYPE_NAME,
            "endian": BINARY_ENDIAN,
            "order": BINARY_ORDER,
            "nodata": BINARY_NODATA,
            "bytes_per_layer": rows * cols * BINARY_DTYPE.itemsize,
            "decode": "new Float32Array(await (await fetch(url)).arrayBuffer())",
        },
        "rover": {"id": rover_id, "name": rover_name},
        "weights": weights,
        "layers": layers,
    }
    # The DEM-clone ensemble's pedigree (B3): NASA's product, the clone
    # count, what was held fixed. Present exactly when the p_* layers are.
    if metadata.get("dem_uncertainty") is not None:
        manifest["dem_uncertainty"] = metadata["dem_uncertainty"]
    return manifest
