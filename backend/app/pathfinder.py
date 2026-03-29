"""High-performance A* pathfinder for the LunaPath lunar rover.

Two-phase design:
  1. Precompute per-cell cost grid via cost_engine.compute_cost_grid()
     (multi-criteria: slope, energy, shadow, thermal + AHP weights).
  2. Run A* with trapezoidal edge interpolation over the cost grid.

Edge cost formula:
  cost(u→v) = distance(u,v) * (1 + (cost_grid[u] + cost_grid[v]) / 2)

Heuristic: Octile distance scaled by (1 + MIN_COST) — admissible & consistent.

Optimisations:
  - NumPy float32/bool/int32 arrays for g_score, closed, came_from
  - heapq with lazy duplicate strategy (no decrease-key)
  - Precomputed 8-direction offset table
  - Diagonal corner-cutting safety checks
  - Tie-breaking: (f, h, counter) — prefer nodes closer to goal
  - Early exit on goal expansion
"""

from __future__ import annotations

import heapq
import math
import time
from typing import Any

import numpy as np

from .cost_engine import compute_cost_grid, f_thermal
from .constants import get_rover

# ── Grid resolution (metres per cell) ──────────────────────────────────────
_CELL_M = 80.0  # 80 m per grid cell (cardinal)
_DIAG_M = _CELL_M * math.sqrt(2)  # ≈ 113.14 m (diagonal)

# ── 8-direction offsets: (dr, dc, distance_m, is_diagonal) ─────────────────
# Precomputed tuple — zero per-iteration allocation.
_OFFSETS: tuple[tuple[int, int, float, bool], ...] = (
    (-1,  0, _CELL_M, False),   # N
    ( 1,  0, _CELL_M, False),   # S
    ( 0, -1, _CELL_M, False),   # W
    ( 0,  1, _CELL_M, False),   # E
    (-1, -1, _DIAG_M, True),    # NW
    (-1,  1, _DIAG_M, True),    # NE
    ( 1, -1, _DIAG_M, True),    # SW
    ( 1,  1, _DIAG_M, True),    # SE
)


# ════════════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ════════════════════════════════════════════════════════════════════════════

def astar(
    grids: dict[str, Any],
    start: tuple[int, int],
    goal: tuple[int, int],
    weights: dict[str, float] | None = None,
    constraints: dict | None = None,
    rover: dict[str, Any] | None = None,
) -> dict:
    """Run optimised A* and return path + metrics.

    Parameters
    ----------
    grids : dict
        Must contain keys: elevation, slope (or slope_grid), thermal,
        shadow_ratio, traversable, metadata (with resolution_m).
    start, goal : (row, col)
    weights : optional AHP weight overrides
    constraints : optional constraint overrides (unused in fast mode,
                  kept for API compat)

    Returns
    -------
    dict with keys: path_pixels, metrics, error
    """
    t0 = time.perf_counter()

    # ── Unpack grids ────────────────────────────────────────────────────
    traversable = np.asarray(grids["traversable"], dtype=bool)
    rows, cols = traversable.shape
    resolution = float(grids["metadata"]["resolution_m"])

    # Slope grid — accept both naming conventions
    slope_grid = np.asarray(
        grids.get("slope", grids.get("slope_grid", np.zeros((rows, cols)))),
        dtype=np.float64,
    )
    thermal_grid = np.asarray(grids["thermal"], dtype=np.float64)
    shadow_grid = np.asarray(grids["shadow_ratio"], dtype=np.float64)
    elevation = np.asarray(grids["elevation"], dtype=np.float64)

    # ── Bounds / traversability pre-checks ──────────────────────────────
    if not _in_bounds(start[0], start[1], rows, cols):
        return _empty_result("Start out of bounds")
    if not _in_bounds(goal[0], goal[1], rows, cols):
        return _empty_result("Goal out of bounds")
    if not traversable[start]:
        return _empty_result("Start is not traversable")
    if not traversable[goal]:
        return _empty_result("Goal is not traversable")

    # ── Phase 1: Precompute cost grid ───────────────────────────────────
    # Each traversable cell → [0.01, ∞), blocked cells → inf.
    rover_cfg = get_rover() if rover is None else rover
    cost_grid = compute_cost_grid(
        slope_grid, thermal_grid, shadow_grid,
        resolution_m=resolution,
        traversable=traversable,
        weights=weights,
        rover=rover_cfg,
    ).astype(np.float32)

    # Derive MIN_COST for heuristic scaling (admissibility guarantee)
    finite_mask = np.isfinite(cost_grid)
    if not np.any(finite_mask):
        return _empty_result("No traversable cells")
    min_cost = float(np.min(cost_grid[finite_mask]))  # ≥ 0.01

    # ── Phase 2: A* search ──────────────────────────────────────────────
    result = _astar_core(
        cost_grid, traversable, elevation, thermal_grid,
        start, goal, rows, cols, resolution, min_cost,
    )

    comp_ms = (time.perf_counter() - t0) * 1000.0
    if result is None:
        return _empty_result("No path found", comp_ms)

    path_pixels, nodes_expanded = result

    # ── Post-process metrics ────────────────────────────────────────────
    metrics = _compute_path_metrics(
        path_pixels, elevation, thermal_grid, cost_grid, resolution, comp_ms,
        nodes_expanded,
    )

    return {
        "path_pixels": path_pixels,
        "metrics": metrics,
        "error": None,
    }


# ════════════════════════════════════════════════════════════════════════════
#  A* CORE — tight inner loop
# ════════════════════════════════════════════════════════════════════════════

def _astar_core(
    cost_grid: np.ndarray,
    traversable: np.ndarray,
    elevation: np.ndarray,
    thermal: np.ndarray,
    start: tuple[int, int],
    goal: tuple[int, int],
    rows: int,
    cols: int,
    resolution: float,
    min_cost: float,
) -> tuple[list[list[int]], int] | None:
    """Inner A* loop. Returns (path_pixels, nodes_expanded) or None."""

    # Distance multipliers relative to resolution
    cardinal_dist = resolution
    diagonal_dist = resolution * math.sqrt(2)

    # Update offsets with actual resolution
    offsets = (
        (-1,  0, cardinal_dist, False),
        ( 1,  0, cardinal_dist, False),
        ( 0, -1, cardinal_dist, False),
        ( 0,  1, cardinal_dist, False),
        (-1, -1, diagonal_dist, True),
        (-1,  1, diagonal_dist, True),
        ( 1, -1, diagonal_dist, True),
        ( 1,  1, diagonal_dist, True),
    )

    # ── Heuristic: octile distance × (1 + min_cost) ────────────────────
    gr, gc = goal
    h_scale = 1.0 + min_cost  # admissible scaling factor

    def heuristic(r: int, c: int) -> float:
        dr = abs(r - gr)
        dc = abs(c - gc)
        # octile = cardinal_dist * (dr+dc) + (diagonal_dist - 2*cardinal_dist) * min(dr,dc)
        return h_scale * (
            cardinal_dist * (dr + dc)
            + (diagonal_dist - 2.0 * cardinal_dist) * min(dr, dc)
        )

    # ── NumPy-backed storage ────────────────────────────────────────────
    total_cells = rows * cols

    g_score = np.full(total_cells, np.inf, dtype=np.float32)
    closed = np.zeros(total_cells, dtype=np.bool_)
    came_from = np.full(total_cells, -1, dtype=np.int32)

    # Flatten helpers
    start_idx = start[0] * cols + start[1]
    goal_idx = goal[0] * cols + goal[1]

    g_score[start_idx] = 0.0
    h_start = heuristic(start[0], start[1])

    # Priority queue: (f_score, h_score, counter, flat_index)
    # Tie-break: lower h preferred (closer to goal)
    counter = 0
    open_heap: list[tuple[float, float, int, int]] = []
    heapq.heappush(open_heap, (h_start, h_start, counter, start_idx))

    nodes_expanded = 0

    # ── Flat cost/traversable views for fast indexing ───────────────────
    cost_flat = cost_grid.ravel()
    trav_flat = traversable.ravel()

    while open_heap:
        f_cur, _, _, cur_idx = heapq.heappop(open_heap)

        # Lazy duplicate skip
        if closed[cur_idx]:
            continue
        closed[cur_idx] = True
        nodes_expanded += 1

        # Early exit
        if cur_idx == goal_idx:
            return _reconstruct_path(came_from, goal_idx, cols), nodes_expanded

        cur_r = cur_idx // cols
        cur_c = cur_idx % cols
        cur_g = float(g_score[cur_idx])
        cur_cost = float(cost_flat[cur_idx])

        for dr, dc, dist, is_diag in offsets:
            nr = cur_r + dr
            nc = cur_c + dc

            # Bounds check
            if nr < 0 or nr >= rows or nc < 0 or nc >= cols:
                continue

            n_idx = nr * cols + nc

            # Skip closed or non-traversable
            if closed[n_idx] or not trav_flat[n_idx]:
                continue

            # ── Diagonal corner-cutting safety ──────────────────────
            if is_diag:
                # Both adjacent cardinal cells must be traversable
                adj1_idx = cur_r * cols + nc  # (cur_r, nc)
                adj2_idx = nr * cols + cur_c  # (nr, cur_c)
                if not trav_flat[adj1_idx] or not trav_flat[adj2_idx]:
                    continue

            # ── Trapezoidal edge cost ───────────────────────────────
            n_cost = float(cost_flat[n_idx])
            edge_cost = dist * (1.0 + (cur_cost + n_cost) * 0.5)

            tentative_g = cur_g + edge_cost
            if tentative_g >= g_score[n_idx]:
                continue

            g_score[n_idx] = tentative_g
            came_from[n_idx] = cur_idx
            h_val = heuristic(nr, nc)
            counter += 1
            heapq.heappush(
                open_heap,
                (tentative_g + h_val, h_val, counter, n_idx),
            )

    return None  # No path found


# ════════════════════════════════════════════════════════════════════════════
#  PATH RECONSTRUCTION
# ════════════════════════════════════════════════════════════════════════════

def _reconstruct_path(
    came_from: np.ndarray,
    goal_idx: int,
    cols: int,
) -> list[list[int]]:
    """Walk came_from chain backwards and return [[row,col], ...] start→goal."""
    path: list[list[int]] = []
    idx = goal_idx
    while idx != -1:
        r = idx // cols
        c = idx % cols
        path.append([r, c])
        idx = int(came_from[idx])
    path.reverse()
    return path


# ════════════════════════════════════════════════════════════════════════════
#  METRICS
# ════════════════════════════════════════════════════════════════════════════

def _compute_path_metrics(
    path_pixels: list[list[int]],
    elevation: np.ndarray,
    thermal: np.ndarray,
    cost_grid: np.ndarray,
    resolution: float,
    comp_ms: float,
    nodes_expanded: int,
) -> dict:
    """Compute post-hoc path metrics for API response."""
    if len(path_pixels) < 2:
        return _zero_metrics(comp_ms, nodes_expanded)

    total_distance = 0.0
    max_slope = 0.0
    total_weighted_cost = 0.0
    path_temps: list[float] = []

    for i, (r, c) in enumerate(path_pixels):
        path_temps.append(float(thermal[r, c]))
        if i == 0:
            continue

        pr, pc = path_pixels[i - 1]
        is_diag = abs(r - pr) + abs(c - pc) == 2
        d_horiz = resolution * (math.sqrt(2) if is_diag else 1.0)
        dz = float(elevation[r, c] - elevation[pr, pc])
        seg_slope = math.degrees(math.atan2(abs(dz), d_horiz))
        total_distance += math.sqrt(d_horiz ** 2 + dz ** 2)
        max_slope = max(max_slope, seg_slope)

        # Accumulate trapezoidal cost
        c_prev = float(cost_grid[pr, pc])
        c_cur = float(cost_grid[r, c])
        total_weighted_cost += d_horiz * (1.0 + (c_prev + c_cur) * 0.5)

    goal_r, goal_c = path_pixels[-1]

    return {
        "total_distance_m": round(total_distance, 2),
        "total_energy_wh": 0.0,  # Not tracked in fast mode
        "total_shadow_hours": 0.0,  # Not tracked in fast mode
        "max_slope_deg": round(max_slope, 2),
        "max_thermal_risk": round(
            max(f_thermal(t) for t in path_temps), 4
        ),
        "min_surface_temp_c": round(min(path_temps), 2),
        "total_weighted_cost": round(total_weighted_cost, 4),
        "path_length_nodes": len(path_pixels),
        "computation_time_ms": round(comp_ms, 1),
        "nodes_expanded": nodes_expanded,
    }


def _zero_metrics(comp_ms: float = 0.0, nodes_expanded: int = 0) -> dict:
    return {
        "total_distance_m": 0.0,
        "total_energy_wh": 0.0,
        "total_shadow_hours": 0.0,
        "max_slope_deg": 0.0,
        "max_thermal_risk": 0.0,
        "min_surface_temp_c": 0.0,
        "total_weighted_cost": 0.0,
        "path_length_nodes": 0,
        "computation_time_ms": round(comp_ms, 1),
        "nodes_expanded": nodes_expanded,
    }


# ════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════════════════════════

def _empty_result(error: str, comp_time_ms: float = 0.0) -> dict:
    return {
        "path_pixels": [],
        "metrics": _zero_metrics(comp_time_ms),
        "error": error,
    }


def _in_bounds(r: int, c: int, rows: int, cols: int) -> bool:
    return 0 <= r < rows and 0 <= c < cols
