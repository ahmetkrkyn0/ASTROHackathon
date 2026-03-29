"""High-performance multi-criteria A* planner for lunar rover navigation.

Two operating modes:
  1. **Grid-cost mode** (default): Uses the pre-computed cost grid produced by
     ``cost_engine.compute_cost_grid``.  Edge cost is the trapezoidal average
     of the two endpoint cell costs multiplied by the physical distance.
     This is fast (~0.5-2 s on 500×500) and suitable for interactive use.

  2. **Physics mode** (``use_physics_cost=True``): Computes the full per-edge
     cost from ``cost_engine.total_edge_cost`` including slope, energy, shadow,
     thermal penalties and the log-barrier term.  Accurate but slower.

Both modes respect the same API contract expected by ``main.py``.

Reference: docs/lunapath_referans_belgesi_2.md  §2.2, §8 Phase 3.
"""

from __future__ import annotations

import heapq
import math
import time

import numpy as np

from . import constants as C
from .cost_engine import (
    edge_energy_wh,
    edge_shadow_hours,
    f_thermal,
    resolve_weights,
    total_edge_cost,
)

# ── Pre-computed neighbor offsets ────────────────────────────────────────────
# (d_row, d_col, distance_multiplier, is_diagonal)
# Cardinal: mult = 1.0,  Diagonal: mult = sqrt(2)
_SQRT2 = math.sqrt(2)

_NEIGHBORS: tuple[tuple[int, int, float, bool], ...] = (
    (-1,  0, 1.0,    False),  # N
    ( 1,  0, 1.0,    False),  # S
    ( 0, -1, 1.0,    False),  # W
    ( 0,  1, 1.0,    False),  # E
    (-1, -1, _SQRT2, True),   # NW
    (-1,  1, _SQRT2, True),   # NE
    ( 1, -1, _SQRT2, True),   # SW
    ( 1,  1, _SQRT2, True),   # SE
)


# ── Public API ──────────────────────────────────────────────────────────────

def astar(
    grids: dict,
    start: tuple[int, int],
    goal: tuple[int, int],
    weights: dict[str, float] | None = None,
    constraints: dict | None = None,
    use_physics_cost: bool = False,
) -> dict:
    """Run weighted A* and return path plus metrics.

    Parameters
    ----------
    grids : dict
        Must contain at minimum: ``elevation``, ``thermal``, ``shadow_ratio``,
        ``traversable``, ``metadata`` (with ``resolution_m``).  If *grid-cost
        mode* is used (default), ``cost`` must also be present.
    start, goal : (row, col)
    weights : optional weight overrides
    constraints : optional constraint overrides
    use_physics_cost : bool
        If True, use the full physics-based edge cost function instead of the
        pre-computed cost grid.  Slower but includes log-barrier and cumulative
        energy/shadow tracking.

    Returns
    -------
    dict with keys: path_pixels, metrics, error
    """
    t0 = time.perf_counter()

    # ── Unpack grids ────────────────────────────────────────────────────────
    elevation = np.asarray(grids["elevation"], dtype=np.float64)
    thermal   = np.asarray(grids["thermal"],   dtype=np.float64)
    shadow_ratio = np.asarray(grids["shadow_ratio"], dtype=np.float64)
    traversable  = np.asarray(grids["traversable"],  dtype=bool)
    resolution   = float(grids["metadata"]["resolution_m"])
    rows, cols   = elevation.shape

    resolved_weights = resolve_weights(weights)

    # Constraints with safe defaults
    cons = {
        "max_shadow_h":  C.H_MAX_SHADOW_H,
        "max_slope_deg": C.SLOPE_MAX_DEG,
        "max_energy_wh": C.E_CAP_WH * 0.74,
        "min_soc":       C.SOC_MIN_PCT,
    }
    if constraints:
        cons.update(constraints)

    # ── Bounds / traversability validation ───────────────────────────────────
    if not _in_bounds(start, rows, cols):
        return _empty_result("Start out of bounds")
    if not _in_bounds(goal, rows, cols):
        return _empty_result("Goal out of bounds")
    if not traversable[start]:
        return _empty_result("Start is not traversable")
    if not traversable[goal]:
        return _empty_result("Goal is not traversable")

    # ── Mode selection ──────────────────────────────────────────────────────
    if use_physics_cost:
        return _astar_physics(
            elevation, thermal, shadow_ratio, traversable,
            resolution, rows, cols, start, goal,
            resolved_weights, cons, t0,
        )
    else:
        # Grid-cost mode: requires pre-computed cost layer
        cost_grid = grids.get("cost")
        if cost_grid is None:
            return _empty_result("cost grid missing — load grids first or use use_physics_cost=True")
        cost_grid = np.asarray(cost_grid, dtype=np.float64)
        return _astar_grid(
            elevation, thermal, shadow_ratio, traversable, cost_grid,
            resolution, rows, cols, start, goal,
            resolved_weights, cons, t0,
        )


# ═══════════════════════════════════════════════════════════════════════════
#  GRID-COST MODE — fast, uses pre-computed cost grid
# ═══════════════════════════════════════════════════════════════════════════

def _astar_grid(
    elevation: np.ndarray,
    thermal: np.ndarray,
    shadow_ratio: np.ndarray,
    traversable: np.ndarray,
    cost_grid: np.ndarray,
    resolution: float,
    rows: int, cols: int,
    start: tuple[int, int],
    goal: tuple[int, int],
    weights: dict[str, float],
    cons: dict,
    t0: float,
) -> dict:
    """A* over the pre-computed cost grid with trapezoidal edge cost."""

    # ── Octile heuristic with admissible scaling ────────────────────────────
    # Minimum finite cell cost across the grid
    finite_costs = cost_grid[np.isfinite(cost_grid)]
    if finite_costs.size == 0:
        return _empty_result("No finite-cost cells in grid")
    min_cost = float(finite_costs.min())

    # Cardinal step cost lower bound:  resolution * (1 + min_cost)
    # Diagonal step cost lower bound:  resolution * sqrt(2) * (1 + min_cost)
    # Octile distance gives exact minimum steps, scaled by this lower bound.
    h_cardinal = resolution * (1.0 + min_cost)
    h_diag     = resolution * _SQRT2 * (1.0 + min_cost)
    goal_r, goal_c = goal

    def heuristic(r: int, c: int) -> float:
        dr = abs(goal_r - r)
        dc = abs(goal_c - c)
        # Octile: min(dr,dc) diagonal steps + |dr-dc| cardinal steps
        if dr < dc:
            return dr * h_diag + (dc - dr) * h_cardinal
        else:
            return dc * h_diag + (dr - dc) * h_cardinal

    # ── Data structures (flat arrays for speed) ─────────────────────────────
    total_cells = rows * cols
    INF32 = np.float32(np.inf)

    g_score   = np.full(total_cells, INF32, dtype=np.float32)
    came_from = np.full(total_cells, -1, dtype=np.int32)
    closed    = np.zeros(total_cells, dtype=np.bool_)

    start_idx = start[0] * cols + start[1]
    goal_idx  = goal_r * cols + goal_c
    g_score[start_idx] = 0.0

    # Flat views of input grids
    trav_flat    = traversable.ravel()
    cost_flat    = cost_grid.ravel()
    elev_flat    = elevation.ravel()
    thermal_flat = thermal.ravel()

    max_slope_deg = float(cons["max_slope_deg"])

    # ── Priority queue: (f_score, -h_score_for_tiebreak, flat_index) ────────
    h_start = heuristic(start[0], start[1])
    open_set: list[tuple[float, float, int]] = []
    heapq.heappush(open_set, (h_start, -h_start, start_idx))

    nodes_expanded = 0
    found = False

    # ── Main loop ───────────────────────────────────────────────────────────
    while open_set:
        _, _, cur_idx = heapq.heappop(open_set)

        if closed[cur_idx]:
            continue  # lazy duplicate skip
        closed[cur_idx] = True
        nodes_expanded += 1

        # Early exit
        if cur_idx == goal_idx:
            found = True
            break

        cur_r = cur_idx // cols
        cur_c = cur_idx % cols
        cur_g = float(g_score[cur_idx])
        cur_cost_val = float(cost_flat[cur_idx])

        for d_row, d_col, dist_mult, is_diag in _NEIGHBORS:
            nr = cur_r + d_row
            nc = cur_c + d_col

            # Bounds check
            if nr < 0 or nr >= rows or nc < 0 or nc >= cols:
                continue

            n_idx = nr * cols + nc

            # Skip closed or blocked
            if closed[n_idx] or not trav_flat[n_idx]:
                continue

            # Diagonal corner-cutting check:
            # both adjacent cardinal cells must be traversable
            if is_diag:
                adj1 = (cur_r + d_row) * cols + cur_c
                adj2 = cur_r * cols + (cur_c + d_col)
                if not trav_flat[adj1] or not trav_flat[adj2]:
                    continue

            # Slope hard-block (edge-based from elevation difference)
            dz = abs(elev_flat[n_idx] - elev_flat[cur_idx])
            d_horiz = resolution * dist_mult
            edge_slope = math.degrees(math.atan2(dz, d_horiz))
            if edge_slope > max_slope_deg:
                continue

            # Neighbor cost must be finite (traversable cells with inf cost
            # come from cost_engine marking them blocked)
            n_cost_val = float(cost_flat[n_idx])
            if not math.isfinite(n_cost_val):
                continue

            # Trapezoidal edge cost:
            #   cost(u→v) = distance(u,v) * (1 + (cost[u] + cost[v]) / 2)
            edge_cost = d_horiz * (1.0 + (cur_cost_val + n_cost_val) * 0.5)

            tentative_g = cur_g + edge_cost
            if tentative_g >= g_score[n_idx]:
                continue

            g_score[n_idx] = np.float32(tentative_g)
            came_from[n_idx] = cur_idx

            h = heuristic(nr, nc)
            f = tentative_g + h
            # Tie-break: prefer lower h (closer to goal)
            heapq.heappush(open_set, (f, -h, n_idx))

    comp_time_ms = (time.perf_counter() - t0) * 1000.0

    if not found:
        return _empty_result("No path found", comp_time_ms, nodes_expanded)

    # ── Path reconstruction + metrics ───────────────────────────────────────
    path_pixels = _reconstruct_flat(came_from, goal_idx, cols)

    metrics = _compute_path_metrics(
        path_pixels, elevation, thermal, shadow_ratio, resolution, g_score[goal_idx],
        comp_time_ms, nodes_expanded,
    )

    return {
        "path_pixels": path_pixels,
        "metrics": metrics,
        "error": None,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  PHYSICS MODE — full per-edge cost with log-barrier
# ═══════════════════════════════════════════════════════════════════════════

def _astar_physics(
    elevation: np.ndarray,
    thermal: np.ndarray,
    shadow_ratio: np.ndarray,
    traversable: np.ndarray,
    resolution: float,
    rows: int, cols: int,
    start: tuple[int, int],
    goal: tuple[int, int],
    weights: dict[str, float],
    cons: dict,
    t0: float,
) -> dict:
    """A* using full physics-based edge cost (log-barrier + cumulative tracking)."""

    total_cells = rows * cols
    INF32 = np.float32(np.inf)

    g_score    = np.full(total_cells, INF32, dtype=np.float32)
    energy_acc = np.full(total_cells, INF32, dtype=np.float32)
    shadow_acc = np.full(total_cells, INF32, dtype=np.float32)
    came_from  = np.full(total_cells, -1, dtype=np.int32)
    closed     = np.zeros(total_cells, dtype=np.bool_)

    start_idx = start[0] * cols + start[1]
    goal_r, goal_c = goal
    goal_idx = goal_r * cols + goal_c

    g_score[start_idx]    = 0.0
    energy_acc[start_idx] = 0.0
    shadow_acc[start_idx] = 0.0

    # Flat views
    trav_flat    = traversable.ravel()
    elev_flat    = elevation.ravel()
    thermal_flat = thermal.ravel()
    shadow_flat  = shadow_ratio.ravel()

    max_slope_deg  = min(C.SLOPE_MAX_DEG, float(cons["max_slope_deg"]))
    max_energy_wh  = float(cons["max_energy_wh"])
    max_shadow_h   = float(cons["max_shadow_h"])
    min_soc        = float(cons["min_soc"])

    # Heuristic: octile × w_slope × f_slope(0°) ≈ w_slope × 0.018
    # This is admissible because it underestimates the minimum possible edge cost
    h_weight = weights["w_slope"] * 0.018 * resolution

    def heuristic(r: int, c: int) -> float:
        dr = abs(goal_r - r)
        dc = abs(goal_c - c)
        if dr < dc:
            return (dr * _SQRT2 + (dc - dr)) * h_weight
        return (dc * _SQRT2 + (dr - dc)) * h_weight

    h_start = heuristic(start[0], start[1])
    open_set: list[tuple[float, float, int]] = []
    heapq.heappush(open_set, (h_start, -h_start, start_idx))

    nodes_expanded = 0
    found = False

    while open_set:
        _, _, cur_idx = heapq.heappop(open_set)

        if closed[cur_idx]:
            continue
        closed[cur_idx] = True
        nodes_expanded += 1

        if cur_idx == goal_idx:
            found = True
            break

        cur_r = cur_idx // cols
        cur_c = cur_idx % cols
        cur_g      = float(g_score[cur_idx])
        cur_energy = float(energy_acc[cur_idx])
        cur_shadow = float(shadow_acc[cur_idx])

        for d_row, d_col, dist_mult, is_diag in _NEIGHBORS:
            nr = cur_r + d_row
            nc = cur_c + d_col
            if nr < 0 or nr >= rows or nc < 0 or nc >= cols:
                continue

            n_idx = nr * cols + nc
            if closed[n_idx] or not trav_flat[n_idx]:
                continue

            # Diagonal corner-cutting check
            if is_diag:
                adj1 = (cur_r + d_row) * cols + cur_c
                adj2 = cur_r * cols + (cur_c + d_col)
                if not trav_flat[adj1] or not trav_flat[adj2]:
                    continue

            d_horiz = resolution * dist_mult
            dz = elev_flat[n_idx] - elev_flat[cur_idx]
            edge_slope = math.degrees(math.atan2(abs(dz), d_horiz))
            if edge_slope > max_slope_deg:
                continue

            # Energy constraint
            ee = edge_energy_wh(edge_slope, d_horiz)
            if math.isinf(ee):
                continue
            new_energy = cur_energy + ee
            if new_energy > max_energy_wh:
                continue
            soc = 1.0 - new_energy / C.E_CAP_WH
            if soc < min_soc:
                continue

            # Shadow constraint
            es = edge_shadow_hours(float(shadow_flat[n_idx]), edge_slope, d_horiz)
            if math.isinf(es):
                continue
            new_shadow = cur_shadow + es
            if new_shadow > max_shadow_h:
                continue

            # Full physics edge cost
            ec = total_edge_cost(
                edge_slope, d_horiz, new_shadow,
                float(thermal_flat[n_idx]),
                weights=weights, soc=soc,
            )
            if math.isinf(ec):
                continue

            tentative_g = cur_g + ec
            if tentative_g >= g_score[n_idx]:
                continue

            g_score[n_idx]    = np.float32(tentative_g)
            energy_acc[n_idx] = np.float32(new_energy)
            shadow_acc[n_idx] = np.float32(new_shadow)
            came_from[n_idx]  = cur_idx

            h = heuristic(nr, nc)
            heapq.heappush(open_set, (tentative_g + h, -h, n_idx))

    comp_time_ms = (time.perf_counter() - t0) * 1000.0

    if not found:
        return _empty_result("No path found", comp_time_ms, nodes_expanded)

    path_pixels = _reconstruct_flat(came_from, goal_idx, cols)

    metrics = _compute_path_metrics(
        path_pixels, elevation, thermal, shadow_ratio, resolution,
        g_score[goal_idx], comp_time_ms, nodes_expanded,
    )
    # Add physics-mode specific metrics
    metrics["total_energy_wh"]    = round(float(energy_acc[goal_idx]), 2)
    metrics["total_shadow_hours"] = round(float(shadow_acc[goal_idx]), 4)

    return {
        "path_pixels": path_pixels,
        "metrics": metrics,
        "error": None,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _reconstruct_flat(
    came_from: np.ndarray, goal_idx: int, cols: int,
) -> list[list[int]]:
    """Reconstruct path from flat came_from array."""
    path: list[list[int]] = []
    idx = goal_idx
    while idx != -1:
        path.append([idx // cols, idx % cols])
        idx = int(came_from[idx])
    path.reverse()
    return path


def _compute_path_metrics(
    path_pixels: list[list[int]],
    elevation: np.ndarray,
    thermal: np.ndarray,
    shadow_ratio: np.ndarray,
    resolution: float,
    total_cost: float,
    comp_time_ms: float,
    nodes_expanded: int,
) -> dict:
    """Compute summary metrics from a reconstructed path."""
    max_slope = 0.0
    total_distance = 0.0
    total_energy = 0.0
    total_shadow = 0.0
    path_temperatures: list[float] = []

    for row, col in path_pixels:
        path_temperatures.append(float(thermal[row, col]))

    for i in range(1, len(path_pixels)):
        pr, pc = path_pixels[i - 1]
        cr, cc = path_pixels[i]
        is_diag = abs(cr - pr) + abs(cc - pc) == 2
        dist_mult = _SQRT2 if is_diag else 1.0
        d_horiz = resolution * dist_mult

        dz = float(elevation[cr, cc] - elevation[pr, pc])
        seg_slope = math.degrees(math.atan2(abs(dz), d_horiz))
        total_distance += math.sqrt(d_horiz**2 + dz**2)
        max_slope = max(max_slope, seg_slope)

        # Energy estimate
        ee = edge_energy_wh(seg_slope, d_horiz)
        if math.isfinite(ee):
            total_energy += ee

        # Shadow estimate
        es = edge_shadow_hours(float(shadow_ratio[cr, cc]), seg_slope, d_horiz)
        if math.isfinite(es):
            total_shadow += es

    max_thermal_risk = 0.0
    min_temp = 0.0
    if path_temperatures:
        max_thermal_risk = max(f_thermal(t) for t in path_temperatures)
        min_temp = min(path_temperatures)

    return {
        "total_distance_m":    round(total_distance, 2),
        "total_energy_wh":     round(total_energy, 2),
        "total_shadow_hours":  round(total_shadow, 4),
        "max_slope_deg":       round(max_slope, 2),
        "max_thermal_risk":    round(max_thermal_risk, 4),
        "min_surface_temp_c":  round(min_temp, 2),
        "total_weighted_cost": round(float(total_cost), 4),
        "path_length_nodes":   len(path_pixels),
        "computation_time_ms": round(comp_time_ms, 1),
        "nodes_expanded":      nodes_expanded,
    }


def _empty_result(
    error: str,
    comp_time_ms: float = 0.0,
    nodes_expanded: int = 0,
) -> dict:
    return {
        "path_pixels": [],
        "metrics": {
            "total_distance_m":    0.0,
            "total_energy_wh":     0.0,
            "total_shadow_hours":  0.0,
            "max_slope_deg":       0.0,
            "max_thermal_risk":    0.0,
            "min_surface_temp_c":  0.0,
            "total_weighted_cost": 0.0,
            "path_length_nodes":   0,
            "computation_time_ms": round(comp_time_ms, 1),
            "nodes_expanded":      nodes_expanded,
        },
        "error": error,
    }


def _in_bounds(node: tuple[int, int], rows: int, cols: int) -> bool:
    return 0 <= node[0] < rows and 0 <= node[1] < cols
