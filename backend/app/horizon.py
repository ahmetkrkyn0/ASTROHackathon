"""Topographic horizon angles from a DEM.

For every cell and every azimuth, the maximum elevation angle of the
terrain silhouette. Computed once from topography; a cell is shadowed at
time t when the Sun's elevation angle is below the horizon angle in the
Sun's azimuth (see :mod:`app.illumination`).

Azimuth convention matches ``make_aspect_grid``: index i is
``360 * i / n_azimuth`` degrees, 0 = North (decreasing row),
90 = East (increasing column).

The same ray-marching kernel backs the virtual LiDAR scan in Phase 5.

Sampling and range
------------------
An earlier revision marched one DEM cell per step and capped the step
count, so at 5 m/px the effective search range collapsed from the nominal
10 km to 1 km -- and at a polar site it is precisely the DISTANT ridge,
seen at a low elevation angle, that casts the long shadow. The march is
now spaced geometrically beyond a dense near field: every cell out to
``dense_range_m`` is still visited (so no near ridge can be stepped over),
and the remainder is log-spaced out to the full ``max_range_m``. Measured
on the production window this reached 10 km in fewer samples than the old
scheme needed for 1 km -- 117 s against 188 s. (Round 4 review, H-4/L-10.)
"""

from __future__ import annotations

import numpy as np

MOON_RADIUS_M: float = 1737400.0
_NO_HORIZON_DEG: float = -90.0

# Out to this distance every DEM cell along the ray is sampled. Beyond it
# the spacing grows geometrically: a ridge subtends fewer and fewer cells
# as it recedes, so uniform sampling there buys resolution nothing uses.
DEFAULT_DENSE_RANGE_M: float = 400.0


def march_distances_cells(
    resolution_m: float,
    max_range_m: float,
    max_steps: int,
    dense_range_m: float = DEFAULT_DENSE_RANGE_M,
    min_range_m: float = 0.0,
) -> np.ndarray:
    """Ray-march sample distances, in CELLS, from 1 out to ``max_range_m``.

    Dense (every cell) out to *dense_range_m*, geometric beyond it. Always
    reaches the full range: *max_steps* controls the far field's spacing,
    not how far the ray gets. Returns a strictly increasing float array.

    *min_range_m* drops every sample closer than that: the far-field pass
    of a two-scale horizon starts where the fine pass stopped, on a DEM
    too coarse to say anything useful about the ground nearby.
    """
    resolution_m = float(resolution_m)
    if resolution_m <= 0.0:
        raise ValueError("resolution_m must be positive")
    if float(min_range_m) < 0.0:
        raise ValueError("min_range_m must not be negative")
    if float(min_range_m) >= float(max_range_m):
        raise ValueError(
            f"min_range_m ({min_range_m}) must be below max_range_m ({max_range_m})"
        )
    far_cells = max(1.0, float(max_range_m) / resolution_m)
    dense_cells = min(far_cells, max(1.0, float(dense_range_m) / resolution_m))

    dense = np.arange(1.0, np.floor(dense_cells) + 1.0)
    remaining = max(1, int(max_steps) - dense.size)
    if far_cells <= dense_cells or remaining <= 0:
        steps = dense[dense <= far_cells] if dense.size else np.array([1.0])
    else:
        sparse = np.geomspace(dense_cells + 1.0, far_cells, remaining)
        steps = np.unique(np.rint(np.concatenate([dense, sparse])))
        steps = steps[steps >= 1.0]

    if float(min_range_m) > 0.0:
        near = steps < float(min_range_m) / resolution_m
        steps = steps[~near]
        if steps.size == 0:
            steps = np.array([np.ceil(float(min_range_m) / resolution_m)])
    return steps


def horizon_map(
    elevation: np.ndarray,
    resolution_m: float,
    n_azimuth: int = 72,
    max_range_m: float = 10000.0,
    max_steps: int = 200,
    moon_radius_m: float = MOON_RADIUS_M,
    curvature: bool = True,
    progress: bool = False,
    roi: tuple[int, int, int, int] | None = None,
    dense_range_m: float = DEFAULT_DENSE_RANGE_M,
    min_range_m: float = 0.0,
) -> np.ndarray:
    """Return (n_azimuth, H, W) float32 horizon elevation angles in degrees.

    min_range_m:
        Ignore terrain closer than this. Used by the far-field pass of the
        two-scale horizon (``scripts/build_horizon_cache.py --far-dem``):
        a wide, coarse DEM marched from the fine pass's range outward, so
        the far crater wall and the plateau beyond it -- which bring a
        rim's horizon back up from -20 deg to ~0 deg -- are not lost at the
        fine DEM's edge. Found by A4's comparison against NASA's LOLA
        Earth-visibility product.

    Parameters
    ----------
    roi:
        ``(row0, row1, col0, col1)`` half-open bounds. When given, horizon
        angles are returned only for that sub-rectangle -- but the rays are
        marched over the WHOLE *elevation* array. This is the difference
        between "the horizon of a 2.5 km crop" and "the horizon of a 2.5 km
        planning window standing in its real 16 km of terrain", and on the
        production site it is worth 260 additional permanently shadowed
        cells and a 37 percent wider shadow-ratio spread. Without it every
        ray leaves the DEM within a few hundred metres of the crop edge and
        reports no obstruction, which is not the same statement as "no
        obstruction exists". (Round 4 review, H-4.)

    Runtime scales as ``n_azimuth * len(steps) * roi_height * roi_width``.
    ``max_steps`` bounds the SAMPLE COUNT, not the range: see
    :func:`march_distances_cells`. Cache the result as ``horizon_map.npy``
    -- it depends only on elevation, not on time.
    """
    elev = np.asarray(elevation, dtype=np.float64)
    if elev.ndim != 2:
        raise ValueError(f"elevation must be 2-D, got shape {elev.shape}")
    height, width = elev.shape

    if roi is None:
        row0, row1, col0, col1 = 0, height, 0, width
    else:
        row0, row1, col0, col1 = (int(v) for v in roi)
        if not (0 <= row0 < row1 <= height and 0 <= col0 < col1 <= width):
            raise ValueError(
                f"roi {roi} is not inside the {height}x{width} elevation grid"
            )

    steps = march_distances_cells(
        resolution_m, max_range_m, max_steps, dense_range_m, min_range_m
    )
    rows = np.arange(row0, row1, dtype=np.float64)[:, None]
    cols = np.arange(col0, col1, dtype=np.float64)[None, :]
    base = elev[row0:row1, col0:col1]

    out = np.empty((n_azimuth, row1 - row0, col1 - col0), dtype=np.float32)

    for a_i in range(n_azimuth):
        az_rad = 2.0 * np.pi * a_i / n_azimuth
        d_row = -np.cos(az_rad)   # azimuth 0 = North = decreasing row
        d_col = np.sin(az_rad)    # azimuth 90 = East = increasing column

        best = np.full(base.shape, -np.inf, dtype=np.float64)

        for step in steps:
            rr = np.rint(rows + d_row * step).astype(np.int64)
            cc = np.rint(cols + d_col * step).astype(np.int64)
            inside = (rr >= 0) & (rr < height) & (cc >= 0) & (cc < width)
            rr_safe = np.clip(rr, 0, height - 1)
            cc_safe = np.clip(cc, 0, width - 1)

            distance_m = float(step) * float(resolution_m)
            dz = elev[rr_safe, cc_safe] - base
            if curvature:
                dz = dz - (distance_m * distance_m) / (2.0 * float(moon_radius_m))

            angle = np.degrees(np.arctan2(dz, distance_m))
            angle = np.where(inside & np.isfinite(angle), angle, -np.inf)
            np.maximum(best, angle, out=best)

        out[a_i] = np.where(np.isfinite(best), best, _NO_HORIZON_DEG).astype(np.float32)

        if progress:
            print(f"  horizon: azimuth {a_i + 1}/{n_azimuth}", flush=True)

    return out
