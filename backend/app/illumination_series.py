"""Time-varying shadow series for the 4-D planner.

The 4-D planner exists to express one decision a static planner cannot:
"stop here, let the Sun come round, then cross". That decision is only
available if the cost cube actually CHANGES between slices -- and it did
not. ``main.plan_4d`` built its series as ``[base_shadow] * n_slices``, so
every slice of the cube was the same array, waiting bought nothing, and the
``wait_steps`` metric could only ever report zero for a reason having
nothing to do with the terrain. ``build_cost_cube``'s careful probe for
which layers vary with time correctly identified ShadowLayer as varying,
and was then handed T copies of one snapshot. (Round 3 review, M-1.)

This module produces the real series when the inputs for it exist, and says
plainly which of the two it produced. It never fabricates variation: a
static series is returned labelled ``static``, not disguised as physics.

What the real path needs
------------------------
1. A horizon cube -- ``(n_azimuth, H, W)`` from :func:`app.horizon.horizon_map`
   -- cached next to the processed grids as ``horizon_map.npy``. It depends
   only on elevation, so it is built once; ``scripts/build_horizon_cache.py``
   does that.
2. NAIF kernels, so :func:`app.ephemeris.sun_track` can say where the Sun is
   at each slice.

Without either, the caller gets the static series and a label saying so.
"""

from __future__ import annotations

import os
from typing import Any

import numpy as np

HORIZON_CACHE_FILENAME: str = "horizon_map.npy"


def horizon_cache_path(metadata: dict[str, Any]) -> str | None:
    """Where the horizon cube for these grids would live, if it exists."""
    processed_dir = metadata.get("processed_dir")
    if not processed_dir:
        return None
    path = os.path.join(str(processed_dir), HORIZON_CACHE_FILENAME)
    return path if os.path.exists(path) else None


def build_shadow_series(
    base_shadow: np.ndarray,
    metadata: dict[str, Any],
    n_slices: int,
    slice_hours: float,
    start_utc: str | None = None,
) -> tuple[list[np.ndarray], dict[str, Any]]:
    """Return ``(shadow_series, provenance)`` for *n_slices* time slices.

    ``provenance`` always carries ``model`` (``"spice_horizon"`` or
    ``"static"``), ``time_varying`` (bool) and, when static, ``reason``
    naming exactly what was missing. A caller that surfaces those fields
    cannot accidentally present a frozen cube as space-time planning.
    """
    base = np.asarray(base_shadow, dtype=np.float64)
    static = [base] * int(n_slices)

    if start_utc is None:
        return static, {
            "model": "static",
            "time_varying": False,
            "reason": (
                "no start epoch given; illumination is a function of time and "
                "cannot vary without one"
            ),
        }

    cache_path = horizon_cache_path(metadata)
    if cache_path is None:
        return static, {
            "model": "static",
            "time_varying": False,
            "reason": (
                f"no {HORIZON_CACHE_FILENAME} beside the processed grids; run "
                "scripts/build_horizon_cache.py to enable time-varying shadow"
            ),
        }

    try:
        series = _spice_shadow_series(
            base, metadata, cache_path, int(n_slices), float(slice_hours), start_utc
        )
    except Exception as exc:
        # Deliberately broad, and deliberately non-fatal: spiceypy maps SPICE
        # failures on to assorted builtin exception types, and a missing
        # kernel must degrade to the honest static series rather than take
        # /api/plan-4d down. The same reasoning as the P1 pipeline's
        # illumination fallback.
        return static, {
            "model": "static",
            "time_varying": False,
            "reason": f"real illumination unavailable ({exc})",
        }

    return series, {
        "model": "spice_horizon",
        "time_varying": True,
        "horizon_cache": cache_path,
        "start_utc": start_utc,
    }


def _spice_shadow_series(
    base_shadow: np.ndarray,
    metadata: dict[str, Any],
    cache_path: str,
    n_slices: int,
    slice_hours: float,
    start_utc: str,
) -> list[np.ndarray]:
    """One shadow grid per slice, from the horizon cube and the Sun's track."""
    from datetime import datetime, timedelta, timezone

    from .ephemeris import (
        sun_azel_from_vector,
        sun_vector_body,
        true_azimuth_to_grid_azimuth,
        true_north_grid_azimuth,
    )
    from .illumination import illuminated_mask

    import spiceypy as spice

    horizon = np.load(cache_path)
    if horizon.ndim != 3 or horizon.shape[1:] != base_shadow.shape:
        raise ValueError(
            f"horizon cache {horizon.shape} does not match the grid "
            f"{base_shadow.shape}"
        )

    lat_deg, lon_deg = _window_centre_latlon(metadata)
    crs_wkt = metadata.get("crs")
    north_grid_az = (
        true_north_grid_azimuth(lat_deg, lon_deg, str(crs_wkt))
        if crs_wkt and crs_wkt != "unknown"
        else 0.0
    )

    start = datetime.fromisoformat(start_utc.replace("Z", "+00:00"))
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)

    series: list[np.ndarray] = []
    for index in range(n_slices):
        moment = start + timedelta(hours=slice_hours * index)
        et = spice.str2et(moment.strftime("%Y-%m-%dT%H:%M:%S"))
        true_az, elev = sun_azel_from_vector(
            sun_vector_body(et), lat_deg, lon_deg
        )
        grid_az = true_azimuth_to_grid_azimuth(true_az, north_grid_az)
        lit = illuminated_mask(horizon, grid_az, elev)
        # A slice is an instant, so its shadow ratio is binary: lit or not.
        # The base grid's fractional values are a long-run average, which is
        # exactly the information the time axis is supposed to replace.
        series.append(np.where(lit, 0.0, 1.0))
    return series


def _window_centre_latlon(metadata: dict[str, Any]) -> tuple[float, float]:
    """Latitude and longitude of the grid's centre pixel."""
    from .serializer import pixel_to_lonlat

    shape = metadata.get("shape") or [0, 0]
    row = int(shape[0]) // 2
    col = int(shape[1]) // 2
    lon, lat = pixel_to_lonlat(row, col, metadata)
    return float(lat), float(lon)
