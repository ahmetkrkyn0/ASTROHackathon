#!/usr/bin/env python3
"""Synthetic LiDAR scan from the orbital DEM.

NOT a perception simulator. A single-origin, first-return ray march over
the same elevation model app.horizon uses for shadow geometry (same
distance-stepping + optional curvature-correction maths), specialised to
one rover pose and many beams instead of every cell as an origin. It is
not the same function call as horizon_map -- that one is vectorised across
every grid cell simultaneously for the whole-grid shadow computation, and
forcing it into a per-origin loop would defeat that vectorisation. This
module reuses the geometry, not the vectorised code path.

LIMITATION -- restate this wherever this module's output is used: an
The current working input (Site11) is 5 m/px, read at runtime from processed
metadata rather than assumed here. That is fine enough for a tens-of-metres
scan to cross several DEM cells and measure resolved slopes/ridges, but it
still cannot resolve the sub-metre rocks a rover LiDAR sees. This module is
therefore the orbital-DEM side of the simulation; the 3-D scene adds explicit
metre-scale rock meshes for the local perception demonstration.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

import numpy as np

_BACKEND_ROOT = str(Path(__file__).resolve().parent.parent.parent / "backend")
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from app.horizon import MOON_RADIUS_M  # noqa: E402

DEFAULT_ELEVATION_ANGLES_DEG: tuple[float, ...] = tuple(
    float(v) for v in np.linspace(-15.0, 0.0, 16)
)


def _sample_elevation(elevation: np.ndarray, row: float, col: float) -> float | None:
    """Bilinear elevation at a fractional pixel coordinate.

    A 0.5 m ray step on a 5 m grid should not see ten copies of one flat cell
    followed by a vertical wall at the next pixel boundary. Interpolation
    represents the continuous surface implied between DEM sample centres.
    Nodata only invalidates contributors whose interpolation weight is nonzero.
    """
    height, width = elevation.shape
    if not (0.0 <= row <= height - 1 and 0.0 <= col <= width - 1):
        return None

    r0, c0 = int(np.floor(row)), int(np.floor(col))
    r1, c1 = min(r0 + 1, height - 1), min(c0 + 1, width - 1)
    fr, fc = row - r0, col - c0
    samples = (
        (elevation[r0, c0], (1.0 - fr) * (1.0 - fc)),
        (elevation[r0, c1], (1.0 - fr) * fc),
        (elevation[r1, c0], fr * (1.0 - fc)),
        (elevation[r1, c1], fr * fc),
    )
    value = 0.0
    for sample, weight in samples:
        if weight == 0.0:
            continue
        if not np.isfinite(sample):
            return None
        value += float(sample) * weight
    return value


def virtual_scan(
    elevation: np.ndarray,
    resolution_m: float,
    origin_row: float,
    origin_col: float,
    sensor_height_m: float = 1.0,
    n_azimuth: int = 180,
    elevation_angles_deg: Sequence[float] = DEFAULT_ELEVATION_ANGLES_DEG,
    max_range_m: float = 30.0,
    range_step_m: float | None = None,
    curvature: bool = False,
    moon_radius_m: float = MOON_RADIUS_M,
) -> np.ndarray:
    """First-return synthetic LiDAR points, rover-centred (east, north, up) metres.

    A beam is a "no return" (omitted from the output) if it never crosses
    the terrain within max_range_m -- exactly like a real LiDAR beam aimed
    at open sky. Azimuth convention matches app.horizon: 0 = North
    (decreasing row), 90 = East (increasing column).

    The current 5 m/px working DEM resolves terrain relief, not sub-metre
    hazards. ``resolution_m`` remains an explicit runtime input so another DEM
    can be used without changing this function.
    """
    elev = np.asarray(elevation, dtype=np.float64)
    if not np.isfinite(resolution_m) or resolution_m <= 0:
        raise ValueError("resolution_m must be positive and finite")
    origin_elevation = _sample_elevation(elev, origin_row, origin_col)
    if origin_elevation is None:
        raise ValueError("origin_row/origin_col fall outside the elevation grid")
    sensor_z = origin_elevation + float(sensor_height_m)

    # Site11 is 5 m/px: resolution/10 gives 0.5 m ray samples. The clamp keeps
    # finer DEMs useful without exploding work on coarse legacy inputs.
    step_m = (
        float(range_step_m)
        if range_step_m is not None
        else min(max(float(resolution_m) / 10.0, 0.25), 1.0)
    )
    if not np.isfinite(step_m) or step_m <= 0:
        raise ValueError("range_step_m must be positive and finite")
    if not np.isfinite(max_range_m) or max_range_m <= 0:
        raise ValueError("max_range_m must be positive and finite")
    # Ceil plus the clamp below guarantees one final sample exactly at range;
    # non-divisible steps must never overshoot the advertised sensor range.
    n_steps = max(1, int(np.ceil(float(max_range_m) / step_m)))

    points: list[tuple[float, float, float]] = []
    for a_i in range(int(n_azimuth)):
        az_rad = 2.0 * np.pi * a_i / n_azimuth
        d_row = -np.cos(az_rad)   # azimuth 0 = North = decreasing row
        d_col = np.sin(az_rad)    # azimuth 90 = East = increasing column

        for elev_deg in elevation_angles_deg:
            tan_elev = np.tan(np.radians(float(elev_deg)))

            for step in range(1, n_steps + 1):
                distance_m = min(step * step_m, float(max_range_m))
                row = origin_row + d_row * distance_m / resolution_m
                col = origin_col + d_col * distance_m / resolution_m
                ground_z = _sample_elevation(elev, row, col)
                if ground_z is None:
                    break  # ray left the grid: no return

                if curvature:
                    ground_z -= (distance_m * distance_m) / (2.0 * moon_radius_m)

                beam_z = sensor_z + tan_elev * distance_m
                if ground_z >= beam_z:
                    east_m = d_col * distance_m
                    north_m = -d_row * distance_m
                    points.append((east_m, north_m, beam_z - sensor_z))
                    break

    if not points:
        return np.empty((0, 3), dtype=np.float32)
    return np.asarray(points, dtype=np.float32)
