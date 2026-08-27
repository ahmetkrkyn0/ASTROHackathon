"""Build the Corridor contract from a planned path."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from scipy.ndimage import distance_transform_edt

from .cost_engine import edge_energy_wh, edge_travel_time_s, surface_to_inner
from .schemas import Corridor

DEFAULT_SAFE_SHADOW_RATIO: float = 0.2
DEFAULT_MAX_HALF_WIDTH_M: float = 400.0


def clearance_map(traversable: np.ndarray, resolution_m: float) -> np.ndarray:
    """Distance in metres from every cell to the nearest impassable cell."""
    mask = np.asarray(traversable, dtype=bool)
    return distance_transform_edt(mask) * float(resolution_m)


def _pixel_to_metres(
    row: int, col: int, origin_x: float, origin_y: float, resolution_m: float
) -> tuple[float, float]:
    """Pixel centre in projected CRS metres.

    ``origin_y`` is the raster window's TOP edge (rasterio ``transform.f``)
    and rows increase southward, so the row term is subtracted. This matches
    ``process_lunar_data.window_center_latlon``; the ``+`` form placed
    waypoints up to 1.23 km off on the production grid. (Faz 2 review, C2.)
    """
    return (origin_x + col * resolution_m, origin_y - row * resolution_m)


def _safe_haven_indices(
    traversable: np.ndarray, shadow_ratio: np.ndarray, safe_shadow_ratio: float
) -> np.ndarray:
    """(2, H, W) index array pointing every cell at its nearest safe cell."""
    safe = np.asarray(traversable, dtype=bool) & (
        np.asarray(shadow_ratio) <= safe_shadow_ratio
    )
    if not safe.any():
        # No lit cell anywhere: fall back to nearest traversable cell.
        safe = np.asarray(traversable, dtype=bool)
    _distance, indices = distance_transform_edt(~safe, return_indices=True)
    return indices


def build_corridor(
    path_pixels: Sequence[tuple[int, int]],
    grids: Mapping[str, Any],
    rover: Mapping[str, Any],
    safe_shadow_ratio: float = DEFAULT_SAFE_SHADOW_RATIO,
    max_half_width_m: float = DEFAULT_MAX_HALF_WIDTH_M,
) -> Corridor:
    """Turn a pixel path into the contract a local planner can execute."""
    path = [(int(r), int(c)) for r, c in path_pixels]
    if len(path) < 2:
        raise ValueError("a corridor needs at least two waypoints")

    metadata = grids["metadata"]
    resolution_m = float(metadata["resolution_m"])
    origin = metadata.get("origin") or {}
    origin_x = float(origin.get("x", 0.0))
    origin_y = float(origin.get("y", 0.0))

    slope = np.asarray(grids["slope"], dtype=np.float64)
    thermal = np.asarray(grids["thermal"], dtype=np.float64)
    shadow_ratio = np.asarray(grids["shadow_ratio"], dtype=np.float64)
    traversable = np.asarray(grids["traversable"], dtype=bool)

    clearance = clearance_map(traversable, resolution_m)
    safe_indices = _safe_haven_indices(traversable, shadow_ratio, safe_shadow_ratio)
    bat_min_c = float(rover["bat_op_min_c"])

    waypoints = [
        _pixel_to_metres(r, c, origin_x, origin_y, resolution_m) for r, c in path
    ]

    fallback_points: list[tuple[float, float]] = []
    for r, c in path:
        safe_r = int(safe_indices[0, r, c])
        safe_c = int(safe_indices[1, r, c])
        fallback_points.append(
            _pixel_to_metres(safe_r, safe_c, origin_x, origin_y, resolution_m)
        )

    half_width_m: list[float] = []
    max_slope_deg: list[float] = []
    energy_budget_wh: list[float] = []
    thermal_budget_K_s: list[float] = []

    for (r0, c0), (r1, c1) in zip(path[:-1], path[1:]):
        diagonal = (r0 != r1) and (c0 != c1)
        distance_m = resolution_m * (math.sqrt(2.0) if diagonal else 1.0)

        half_width_m.append(
            float(min(min(clearance[r0, c0], clearance[r1, c1]), max_half_width_m))
        )

        segment_slope = float(max(slope[r0, c0], slope[r1, c1]))
        max_slope_deg.append(segment_slope)

        energy_budget_wh.append(
            float(edge_energy_wh(segment_slope, distance_m, rover))
        )

        travel_s = edge_travel_time_s(segment_slope, distance_m, rover)
        inner_c = surface_to_inner(float(thermal[r1, c1]), rover)
        margin_k = max(0.0, inner_c - bat_min_c)
        thermal_budget_K_s.append(
            float(margin_k * travel_s) if math.isfinite(travel_s) else 0.0
        )

    return Corridor(
        waypoints=waypoints,
        half_width_m=half_width_m,
        max_slope_deg=max_slope_deg,
        energy_budget_wh=energy_budget_wh,
        thermal_budget_K_s=thermal_budget_K_s,
        fallback_points=fallback_points,
        crs=str(metadata.get("crs", "unknown")),
    )
