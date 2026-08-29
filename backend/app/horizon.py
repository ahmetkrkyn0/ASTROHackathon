"""Topographic horizon angles from a DEM.

For every cell and every azimuth, the maximum elevation angle of the
terrain silhouette. Computed once from topography; a cell is shadowed at
time t when the Sun's elevation angle is below the horizon angle in the
Sun's azimuth (see :mod:`app.illumination`).

Azimuth convention matches ``make_aspect_grid``: index i is
``360 * i / n_azimuth`` degrees, 0 = North (decreasing row),
90 = East (increasing column).

The same ray-marching kernel backs the virtual LiDAR scan in Phase 5.
"""

from __future__ import annotations

import numpy as np

MOON_RADIUS_M: float = 1737400.0
_NO_HORIZON_DEG: float = -90.0


def horizon_map(
    elevation: np.ndarray,
    resolution_m: float,
    n_azimuth: int = 72,
    max_range_m: float = 10000.0,
    max_steps: int = 200,
    moon_radius_m: float = MOON_RADIUS_M,
    curvature: bool = True,
    progress: bool = False,
) -> np.ndarray:
    """Return (n_azimuth, H, W) float32 horizon elevation angles in degrees.

    Runtime scales as ``n_azimuth * n_steps * H * W``, where
    ``n_steps = min(round(max_range_m / resolution_m), max_steps)`` --
    whichever bound is tighter wins, so this is NOT a flat cost regardless
    of resolution. With the defaults (``max_range_m=10000``,
    ``max_steps=200``): at 80 m/px, ``n_steps = min(125, 200) = 125`` --
    bounded by ``max_range_m`` (effective range stays the full 10 km); at
    5 m/px, ``n_steps = min(2000, 200) = 200`` -- bounded by ``max_steps``
    instead (effective range drops to 1 km, well short of the nominal
    10 km). ``max_steps`` only becomes the active bound once
    ``resolution_m < max_range_m / max_steps`` (50 m at the defaults);
    coarser than that, ``max_range_m`` is what limits the cost, and the
    cost genuinely does grow as resolution gets finer within that regime.
    What ``max_steps`` guarantees is a hard ceiling: however fine
    *resolution_m* gets, runtime never exceeds the ``max_steps`` case.
    Cache the result as ``horizon_map.npy`` -- it depends only on
    elevation, not on time.
    """
    elev = np.asarray(elevation, dtype=np.float64)
    if elev.ndim != 2:
        raise ValueError(f"elevation must be 2-D, got shape {elev.shape}")
    height, width = elev.shape

    n_steps = max(1, int(round(float(max_range_m) / float(resolution_m))))
    n_steps = min(n_steps, int(max_steps))
    rows = np.arange(height, dtype=np.float64)[:, None]
    cols = np.arange(width, dtype=np.float64)[None, :]

    out = np.empty((n_azimuth, height, width), dtype=np.float32)

    for a_i in range(n_azimuth):
        az_rad = 2.0 * np.pi * a_i / n_azimuth
        d_row = -np.cos(az_rad)   # azimuth 0 = North = decreasing row
        d_col = np.sin(az_rad)    # azimuth 90 = East = increasing column

        best = np.full((height, width), -np.inf, dtype=np.float64)

        for step in range(1, n_steps + 1):
            rr = np.rint(rows + d_row * step).astype(np.int64)
            cc = np.rint(cols + d_col * step).astype(np.int64)
            inside = (rr >= 0) & (rr < height) & (cc >= 0) & (cc < width)
            rr_safe = np.clip(rr, 0, height - 1)
            cc_safe = np.clip(cc, 0, width - 1)

            distance_m = step * float(resolution_m)
            dz = elev[rr_safe, cc_safe] - elev
            if curvature:
                dz = dz - (distance_m * distance_m) / (2.0 * float(moon_radius_m))

            angle = np.degrees(np.arctan2(dz, distance_m))
            angle = np.where(inside & np.isfinite(angle), angle, -np.inf)
            np.maximum(best, angle, out=best)

        out[a_i] = np.where(np.isfinite(best), best, _NO_HORIZON_DEG).astype(np.float32)

        if progress:
            print(f"  horizon: azimuth {a_i + 1}/{n_azimuth}", flush=True)

    return out
