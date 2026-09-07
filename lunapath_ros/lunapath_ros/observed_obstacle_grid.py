"""Apply only confirmed ROS LiDAR observations to a rover-adapted grid."""

from __future__ import annotations

import math
from typing import Any, Iterable

import numpy as np

from app.grid_frame import map_xy_to_pixel


def with_observed_obstacles(
    grids: dict[str, Any],
    observations: Iterable[Any],
    start: tuple[int, int],
    *,
    confidence_threshold: float = 0.65,
) -> tuple[dict[str, Any], int]:
    """Return a copied traversability mask with confirmed LiDAR discs blocked.

    Objects are intentionally duck-typed ROS messages. Invalid, out-of-map,
    non-LiDAR or low-confidence records are ignored; the live start cell is
    never blocked by an observation under the rover footprint.
    """
    metadata = grids["metadata"]
    resolution_m = float(metadata["resolution_m"])
    rows, cols = (int(value) for value in metadata["shape"])
    mask = np.array(grids["traversable"], dtype=bool, copy=True)
    applied = 0
    for observation in observations:
        if str(getattr(observation, "source", "")) != "lidar":
            continue
        confidence = float(getattr(observation, "confidence", 0.0))
        radius_m = float(getattr(observation, "radius_m", 0.0))
        if not math.isfinite(confidence) or not math.isfinite(radius_m):
            continue
        if confidence < confidence_threshold or radius_m <= 0.0:
            continue
        center = getattr(observation, "center", None)
        try:
            row, col = map_xy_to_pixel(float(center.x), float(center.y), metadata)
        except (AttributeError, TypeError, ValueError):
            continue
        radius_cells = max(1, math.ceil(radius_m / resolution_m))
        changed = False
        for dr in range(-radius_cells, radius_cells + 1):
            for dc in range(-radius_cells, radius_cells + 1):
                if math.hypot(dr * resolution_m, dc * resolution_m) > radius_m:
                    continue
                target = (row + dr, col + dc)
                if not (0 <= target[0] < rows and 0 <= target[1] < cols) or target == start:
                    continue
                mask[target] = False
                changed = True
        if changed:
            applied += 1
    return {**grids, "traversable": mask}, applied
