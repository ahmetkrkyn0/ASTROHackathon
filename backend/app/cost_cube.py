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

from .constants import THERMAL_MIN_TRAVERSABLE_C
from .costmap import PlanContext, default_cost_map
from .thermal_model import couple_shadow_to_thermal


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
    couple_thermal: bool = True,
) -> np.ndarray:
    """(T, H', W') cost cube, one slice per shadow-ratio snapshot.

    *couple_thermal* recomputes the surface temperature from each slice's own
    illumination (``thermal_model.couple_shadow_to_thermal``) instead of
    holding the annual field fixed. Pass False only when *base_grids* already
    carries a per-slice thermal field of its own.
    """
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

    # Every layer is evaluated per slice. The optimisation this replaces --
    # evaluating "invariant" layers once -- rested on the assumption that
    # only the shadow layer varies with time. That stopped being true when
    # thermal became a function of illumination (round 3, H-3): a cell that
    # is dark at slice t is genuinely COLDER at slice t, and freezing the
    # thermal layer at one value hid exactly the physics the 4-D planner
    # exists to reason about. The layers are true NumPy now (review #8
    # removed np.vectorize), so per-slice evaluation costs a handful of
    # array ops per slice rather than the ~22 s that made the optimisation
    # necessary in the first place.
    slices: list[np.ndarray] = []
    for snapshot in shadow_ratio_series:
        shadow_c = coarsen_grid(np.asarray(snapshot, dtype=np.float64), coarsen)
        thermal_slice = (
            np.asarray(
                couple_shadow_to_thermal(thermal_c, shadow_c), dtype=np.float64
            )
            if couple_thermal
            else thermal_c
        )

        # A cell whose temperature at THIS slice is outside the traversable
        # band is impassable at this slice and passable later -- which is
        # what finally gives the WAIT edge something to buy. Before the
        # coupling, shadow only made a cell more expensive, never
        # impassable, so waiting could never pay for the time it costs.
        #
        # It is folded into the slice's OWN traversable mask rather than
        # applied afterwards, so CostMap.total is the single place that
        # decides passability and a caller can reproduce the slice exactly
        # by building the same PlanContext.
        traversable_slice = traversable_c & (
            thermal_slice >= THERMAL_MIN_TRAVERSABLE_C
        )
        context = PlanContext(
            slope=slope_c,
            thermal=thermal_slice,
            shadow_ratio=shadow_c,
            traversable=traversable_slice,
            resolution_m=resolution_c,
            rover=rover,
        )
        slices.append(cost_map.total(context))

    return np.stack(slices, axis=0)


from .cost_engine import (
    edge_travel_time_s,
    f_shadow_cell,
    housekeeping_power_w,
    resolve_weights,
)


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

    Time is in the total, not just the penalties. A MOVE edge costs
    ``travel_hours * (1 + weighted cell cost)``; a WAIT used to cost only
    the weighted penalties, so a slice spent in full sunlight came out at
    exactly 0.0 -- waiting was free, the planner had no reason to prefer
    arriving sooner, and ties between "go now" and "wait indefinitely, then
    go" were broken by heap insertion order rather than by the objective.
    Both edge families now cost hours scaled the same way. The heuristic
    stays admissible: a WAIT costs at least ``dt`` and closes no distance,
    so a distance-based lower bound is still a lower bound.
    (Round 3 review, M-2.)

    Housekeeping power comes from ``cost_engine.housekeeping_power_w``, so
    the heater load here matches the one the energy penalty and the
    simulator use. It previously charged full heater power even in full
    sunlight. (Round 3 review, M-9.)
    """
    frac = min(1.0, max(0.0, float(illum_frac)))
    dt = max(0.0, float(dt_hours))

    solar_in_w = float(rover["p_solar_w"]) * frac
    net_w = solar_in_w - housekeeping_power_w(1.0 - frac, rover)

    # Rate form, so the dt factor is applied once, at the end.
    soc_drain_per_hour = max(0.0, -net_w / float(rover["e_cap_wh"]))
    shadow_penalty = f_shadow_cell(1.0 - frac)

    return float(
        dt
        * (
            1.0
            + weights["w_energy"] * soc_drain_per_hour
            + weights["w_shadow"] * shadow_penalty
        )
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
