"""Time-sliced cost cube for the 4-D planner.

Illumination on the lunar pole changes on the scale of hours, so cost is
not one grid but a stack of them -- one per time slice. Cells whose only
time-varying input is shadow get re-costed per slice; slope, energy and
thermal terms are shared.

Coarsening is not an optimisation, it is a scale decision (spec 3.1):
a 500x500 grid across 168 hourly slices is 42 M states / ~1.3 GB. Solving
time on a coarse grid is correct because illumination does not vary at
80 m resolution.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from .costmap import PlanContext, default_cost_map


def coarsen_grid(grid: np.ndarray, factor: int, how: str = "mean") -> np.ndarray:
    """Block-reduce a 2-D grid by an integer factor."""
    arr = np.asarray(grid, dtype=np.float64)
    factor = int(factor)
    if factor <= 1:
        return arr
    height, width = arr.shape
    if height % factor or width % factor:
        raise ValueError(
            f"shape {arr.shape} is not divisible by coarsen factor {factor}"
        )
    blocks = arr.reshape(height // factor, factor, width // factor, factor)
    if how == "mean":
        return np.nanmean(blocks, axis=(1, 3))
    if how == "max":
        return np.nanmax(blocks, axis=(1, 3))
    raise ValueError(f"unknown reduction: {how!r}")


def coarsen_traversable(traversable: np.ndarray, factor: int) -> np.ndarray:
    """Conservative: a coarse cell is passable only if all fine cells are."""
    mask = np.asarray(traversable, dtype=bool)
    factor = int(factor)
    if factor <= 1:
        return mask
    height, width = mask.shape
    if height % factor or width % factor:
        raise ValueError(
            f"shape {mask.shape} is not divisible by coarsen factor {factor}"
        )
    blocks = mask.reshape(height // factor, factor, width // factor, factor)
    return blocks.all(axis=(1, 3))


def build_cost_cube(
    base_grids: Mapping[str, Any],
    shadow_ratio_series: Sequence[np.ndarray],
    rover: Mapping[str, Any],
    weights: Mapping[str, float] | None = None,
    coarsen: int = 1,
) -> np.ndarray:
    """(T, H', W') cost cube, one slice per shadow-ratio snapshot."""
    if len(shadow_ratio_series) == 0:
        raise ValueError("shadow_ratio_series must contain at least one snapshot")

    slope = np.asarray(base_grids["slope"], dtype=np.float64)
    thermal = np.asarray(base_grids["thermal"], dtype=np.float64)
    traversable = np.asarray(base_grids["traversable"], dtype=bool)
    resolution_m = float(base_grids["metadata"]["resolution_m"])

    for index, snapshot in enumerate(shadow_ratio_series):
        if np.asarray(snapshot).shape != slope.shape:
            raise ValueError(
                f"shadow snapshot {index} has shape {np.asarray(snapshot).shape}, "
                f"expected {slope.shape}"
            )

    slope_c = coarsen_grid(slope, coarsen, how="max")       # worst case per block
    thermal_c = coarsen_grid(thermal, coarsen, how="mean")
    traversable_c = coarsen_traversable(traversable, coarsen)
    resolution_c = resolution_m * max(1, int(coarsen))

    cost_map = default_cost_map(rover, weights)
    slices: list[np.ndarray] = []
    for snapshot in shadow_ratio_series:
        shadow_c = coarsen_grid(np.asarray(snapshot, dtype=np.float64), coarsen)
        context = PlanContext(
            slope=slope_c,
            thermal=thermal_c,
            shadow_ratio=shadow_c,
            traversable=traversable_c,
            resolution_m=resolution_c,
            rover=rover,
        )
        slices.append(cost_map.total(context))

    return np.stack(slices, axis=0)
