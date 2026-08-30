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
80 m/px orbital DEM cannot resolve the 30 cm rocks a real LiDAR sees. A
scan at LiDAR-realistic ranges (tens of metres) barely leaves the origin
cell on that grid. This module exists to prove the Corridor contract
(app.corridor) actually feeds a downstream consumer -- it is an interface
test, not a perception simulation.
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


def _nearest_elevation(elevation: np.ndarray, row: float, col: float) -> float | None:
    height, width = elevation.shape
    r, c = int(round(row)), int(round(col))
    if not (0 <= r < height and 0 <= c < width):
        return None
    value = elevation[r, c]
    return float(value) if np.isfinite(value) else None


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

    LIMITATION: on the 80 m/px orbital DEM this is an interface rehearsal,
    not perception -- a 30 m scan does not even reach the neighbouring cell.
    """
    elev = np.asarray(elevation, dtype=np.float64)
    origin_elevation = _nearest_elevation(elev, origin_row, origin_col)
    if origin_elevation is None:
        raise ValueError("origin_row/origin_col fall outside the elevation grid")
    sensor_z = origin_elevation + float(sensor_height_m)

    step_m = float(range_step_m) if range_step_m else max(resolution_m / 4.0, 0.5)
    n_steps = max(1, int(round(float(max_range_m) / step_m)))

    points: list[tuple[float, float, float]] = []
    for a_i in range(int(n_azimuth)):
        az_rad = 2.0 * np.pi * a_i / n_azimuth
        d_row = -np.cos(az_rad)   # azimuth 0 = North = decreasing row
        d_col = np.sin(az_rad)    # azimuth 90 = East = increasing column

        for elev_deg in elevation_angles_deg:
            tan_elev = np.tan(np.radians(float(elev_deg)))

            for step in range(1, n_steps + 1):
                distance_m = step * step_m
                row = origin_row + d_row * distance_m / resolution_m
                col = origin_col + d_col * distance_m / resolution_m
                ground_z = _nearest_elevation(elev, row, col)
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
