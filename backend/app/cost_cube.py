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

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from .costmap import MIN_CELL_COST, PlanContext, default_cost_map


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

    # Only layers that read shadow_ratio vary across slices; slope, energy and
    # thermal read grids that are constant in time. Re-evaluating all four per
    # slice made a 168-slice cube cost ~22 s -- the np.vectorize layers
    # dominate. Evaluate the invariant layers once and add the varying ones
    # per slice. (Faz 3 review, M3.)
    #
    # Which layers vary is PROBED, not assumed from the layer name: a layer
    # that reads shadow_ratio under a different name would otherwise be
    # silently frozen at one value, producing a time-invariant cube that looks
    # correct. Probing keeps this honest as new CostLayers are added.
    def _context(shadow: np.ndarray) -> PlanContext:
        return PlanContext(
            slope=slope_c,
            thermal=thermal_c,
            shadow_ratio=shadow,
            traversable=traversable_c,
            resolution_m=resolution_c,
            rover=rover,
        )

    zeros = np.zeros_like(slope_c, dtype=np.float64)
    ones = np.ones_like(slope_c, dtype=np.float64)

    invariant = np.zeros_like(slope_c, dtype=np.float64)
    varying: list[Any] = []
    for layer in cost_map.layers:
        at_zero = np.asarray(layer.contribution(_context(zeros)), dtype=np.float64)
        at_one = np.asarray(layer.contribution(_context(ones)), dtype=np.float64)
        if np.allclose(at_zero, at_one, equal_nan=True):
            invariant = invariant + layer.weight * at_zero
        else:
            varying.append(layer)

    # The invalid mask depends on shadow only through NaN, so it is rebuilt
    # per slice; everything else in it is time-invariant.
    base_invalid = ~traversable_c | np.isnan(slope_c) | np.isnan(thermal_c)

    slices: list[np.ndarray] = []
    for snapshot in shadow_ratio_series:
        shadow_c = coarsen_grid(np.asarray(snapshot, dtype=np.float64), coarsen)
        accumulator = invariant.copy()
        for layer in varying:
            accumulator = accumulator + layer.weight * layer.contribution(
                _context(shadow_c)
            )
        out = np.maximum(accumulator, MIN_CELL_COST)
        out[base_invalid | np.isnan(shadow_c)] = np.inf
        slices.append(out)

    return np.stack(slices, axis=0)


from .cost_engine import edge_travel_time_s, f_shadow_cell, resolve_weights


def wait_cost(
    illum_frac: float,
    dt_hours: float,
    rover: Mapping[str, Any],
    weights: Mapping[str, float],
) -> float:
    """Cost of holding position for one time slice.

    Waiting in sunlight recharges the battery and costs nothing on the
    energy axis; waiting in shadow drains state of charge and accumulates
    shadow exposure. Modelling this is what turns "go faster" into
    "stop, let the Sun come, then cross".
    """
    frac = min(1.0, max(0.0, float(illum_frac)))
    dt = max(0.0, float(dt_hours))

    solar_in_w = float(rover["p_solar_w"]) * frac
    idle_w = float(rover["p_idle_w"])
    heater_w = float(rover["p_heater_w"])
    net_w = solar_in_w - idle_w - heater_w

    delta_soc = net_w * dt / float(rover["e_cap_wh"])
    energy_penalty = max(0.0, -delta_soc)
    shadow_penalty = f_shadow_cell(1.0 - frac) * dt

    return float(
        weights["w_energy"] * energy_penalty + weights["w_shadow"] * shadow_penalty
    )


def build_wait_cost_cube(
    illum_frac_series: Sequence[np.ndarray],
    rover: Mapping[str, Any],
    dt_hours: float,
    weights: Mapping[str, float] | None = None,
    coarsen: int = 1,
) -> np.ndarray:
    """(T, H', W') cost of waiting one slice in each cell at each time."""
    if len(illum_frac_series) == 0:
        raise ValueError("illum_frac_series must contain at least one snapshot")

    resolved = resolve_weights(weights, rover)

    # wait_cost is a pure scalar function of the illumination fraction, and
    # illumination grids are highly repetitive (whole regions share a value,
    # and the endpoint currently repeats one snapshot across every slice).
    # Evaluating it per cell per slice cost ~5 s for a 168-slice cube; solving
    # it once per DISTINCT value and gathering makes the cube size irrelevant.
    # (Faz 3 review, M3.)
    coarse = [
        coarsen_grid(np.asarray(frac, dtype=np.float64), coarsen)
        for frac in illum_frac_series
    ]
    stacked = np.stack(coarse, axis=0)
    unique, inverse = np.unique(stacked, return_inverse=True)
    table = np.array(
        [wait_cost(value, dt_hours, rover, resolved) for value in unique],
        dtype=np.float64,
    )
    return table[inverse].reshape(stacked.shape)


def auto_slice_hours(
    slope: np.ndarray,
    traversable: np.ndarray,
    resolution_m: float,
    rover: Mapping[str, Any],
    percentile: float = 50.0,
) -> float:
    """Time-slice length matched to how long crossing one cell actually takes.

    The 4-D planner advances time in whole slices
    (``d_slices = ceil(travel_time / slice_hours)``), so a slice much longer
    than an edge traversal collapses every move to exactly one slice: the
    time axis then counts STEPS rather than hours and the slope-dependent
    travel time -- the whole reason ``edge_travel_time_s`` is consulted --
    becomes invisible. On the production grid a 1 h slice did exactly that
    at every resolution from 5 m to 320 m. (Faz 3 review, C1.)

    Sizing a slice at the typical edge traversal keeps ``arrival_slice`` a
    real clock and lets a steep edge cost more slices than a flat one.
    Impassable cells are excluded: they routinely carry near-vertical
    slopes that the rover will never drive and whose traversal time is
    infinite.
    """
    slope_arr = np.asarray(slope, dtype=np.float64)
    passable = np.asarray(traversable, dtype=bool)

    candidates = slope_arr[passable & np.isfinite(slope_arr)]
    if candidates.size == 0:
        # Nothing drivable: fall back to a flat edge so the caller still gets
        # a positive, finite slice length instead of a degenerate clock.
        reference_slope = 0.0
    else:
        reference_slope = float(np.percentile(candidates, percentile))

    travel_s = edge_travel_time_s(reference_slope, float(resolution_m), rover)
    if not math.isfinite(travel_s) or travel_s <= 0.0:
        travel_s = edge_travel_time_s(0.0, float(resolution_m), rover)

    return float(travel_s / 3600.0)
