"""D2 -- LunaPath on an external benchmark: MoonPlanBench (Chancán, Banerjee,
Nikolakopoulos, *Planetary Terrain Datasets and Benchmarks for Rover Path
Planning*, arXiv:2512.21438v1, Dec 2025; code github.com/mchancan/
PlanetaryPathBench).

What the benchmark is, as read from its repository on 5 Sept 2026:

* 36 occupancy grids = 12 LOLA polar DEM products (LDEM_45N_100M ...
  LDEM_875S_5M) x three slope/roughness thresholds (10, 15, 20 deg),
  down-sampled by 64 (paper, sect. 3.1.2). ``.npy`` uint8, non-zero =
  occupied (``run.py``: ``occ = (grid != 0)``). Not in the repository:
  fetched from the authors' Google Drive by
  ``scripts/build_moonplanbench_cache.py``. Licence: the arXiv paper is
  CC BY-NC-SA 4.0; the Drive folder carries no licence file of its own.
* Start and goal are not published as a list; they are DEFINED by
  ``adapters/_common.auto_select_start_goal`` (largest 8-connected free
  component, lexicographically smallest (y, x) start, farthest goal).
  :func:`auto_select_start_goal` reimplements it with the same BFS order.
* The reference planners (PythonRobotics Dijkstra / A* / Theta*) move on the
  8-neighbourhood with costs 1 and sqrt(2) and NO corner-cutting rule: a
  diagonal step between two occupied cells is legal. LunaPath (and the
  nav2 baseline) refuse it. Both motion models are run here, side by side.
* Metrics are PathBench's (``basic_testing.get_results``, ``analyzer``):
  success = agent's final cell equals the goal; path length = sum of
  Euclidean steps in cells; smoothness = mean absolute change of the
  unsigned heading angle (arccos of the x component) per trace point;
  clearance = mean distance from each trace point to the nearest occupied
  cell; distance left = last point to goal (start to goal when nothing was
  planned); planning time in seconds, 60 s limit; memory = tracemalloc
  peak. Averages of length / steps / time / smoothness / clearance are
  over SUCCESSFUL runs only; distance left and memory over all runs.

Claim limits live in :data:`CLAIM`; every number the paper reports is kept
in :data:`PAPER_TABLE_1` as a quotation and never mixed with a measurement.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import math
import os
import sys
import time
import tracemalloc
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import numpy as np
from scipy.ndimage import distance_transform_edt

from .constants import get_rover

# ── Dataset identity ───────────────────────────────────────────────────────

MOONPLANBENCH_DIR: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "lunapath", "data", "benchmarks", "moonplanbench",
)
META_FILENAME: str = "moonplanbench_meta.json"

VARIANTS: tuple[str, ...] = ("MoonPlanBench-10", "MoonPlanBench-15", "MoonPlanBench-20")
SLOPE_THRESHOLD_DEG: dict[str, int] = {"MoonPlanBench-10": 10, "MoonPlanBench-15": 15, "MoonPlanBench-20": 20}

# The 12 LOLA polar DEM products the maps are named after (PDS LOLA GDR
# polar stereographic products; the number is the product's native
# metres per pixel). Cell size on the benchmark map = native x 64.
LDEM_NATIVE_M_PER_PX: dict[str, int] = {
    "LDEM_45N_100M": 100, "LDEM_45S_100M": 100,
    "LDEM_60N_120M": 120, "LDEM_60S_120M": 120,
    "LDEM_75N_30M": 30, "LDEM_75S_30M": 30,
    "LDEM_80N_20M": 20, "LDEM_80S_20M": 20,
    "LDEM_85N_10M": 10, "LDEM_85S_10M": 10,
    "LDEM_875N_5M": 5, "LDEM_875S_5M": 5,
}
DOWNSAMPLE_FACTOR: int = 64  # paper sect. 3.1.2: "down-sample original DEMs images by a factor of 64"

DRIVE_ROOT_FOLDER_ID: str = "15srtIABvwBSbILQESVvAFPHMc3TCzS_R"  # README link
DRIVE_VARIANT_FOLDER_IDS: dict[str, str] = {
    "MoonPlanBench-10": "1R2dS_R6VWOr90S6pbZK9g3p67cFW1aju",
    "MoonPlanBench-15": "1_lHW90CaX2_hWdMlejBpgb_dlboaVlMN",
    "MoonPlanBench-20": "1-5NKaWLRS_M8UFlZdZoZjP-VMLoSkwKA",
}

PAPER_ARXIV: str = "2512.21438v1"
PAPER_URL: str = "https://arxiv.org/abs/2512.21438"
PAPER_TITLE: str = "Planetary Terrain Datasets and Benchmarks for Rover Path Planning"
PAPER_AUTHORS: str = "Marvin Chancán, Avijit Banerjee, George Nikolakopoulos (Luleå University of Technology)"
PAPER_DATE: str = "2025-12-24"
REPO_URL: str = "https://github.com/mchancan/PlanetaryPathBench"
REPO_COMMIT: str = "86dc4b63f14551e55607bad1ce520164d8a96359"  # main, 2025-12-18 "added ack"
DATA_LICENSE: str = (
    "CC BY-NC-SA 4.0 (the licence line of arXiv 2512.21438v1; the Drive folder and the "
    "repository root carry no licence file -- non-commercial use only)"
)
CODE_LICENSES: str = (
    "PathBench/ BSD-3-Clause (Toma et al.); planners derived from PythonRobotics (MIT); "
    "the authors' adapters and run.py carry no licence statement -- not vendored, only "
    "imported at run time from a local clone when --reference-dir is given"
)

# Table 1 of the paper, QUOTED. success %, path length (grid cells),
# planning time (s, their laptop: i7-1355U, Python 3.8, PathBench replay
# included), distance left (cells). Never a measurement of ours.
PAPER_TABLE_1: dict[str, dict[str, dict[str, float]]] = {
    "MoonPlanBench-10": {
        "Dijkstra": {"success_rate_pct": 100, "length_cells": 651.81, "time_s": 23.31, "dist_left": 0},
        "ThetaStar": {"success_rate_pct": 100, "length_cells": 654.81, "time_s": 31.90, "dist_left": 0},
        "AStar": {"success_rate_pct": 91, "length_cells": 639.94, "time_s": 30.82, "dist_left": 56.1},
        "RRT": {"success_rate_pct": 8, "length_cells": 554.01, "time_s": 36.32, "dist_left": 525.5},
        "Dynamic RRT": {"success_rate_pct": 8, "length_cells": 589.91, "time_s": 13.49, "dist_left": 525.5},
        "RRT Connect": {"success_rate_pct": 0, "length_cells": 0, "time_s": 0, "dist_left": 554.1},
    },
    "MoonPlanBench-15": {
        "Dijkstra": {"success_rate_pct": 100, "length_cells": 636.16, "time_s": 16.18, "dist_left": 0},
        "ThetaStar": {"success_rate_pct": 100, "length_cells": 639.14, "time_s": 23.26, "dist_left": 0},
        "AStar": {"success_rate_pct": 83, "length_cells": 621.25, "time_s": 32.45, "dist_left": 72.1},
        "RRT": {"success_rate_pct": 42, "length_cells": 731.14, "time_s": 13.11, "dist_left": 385.6},
        "Dynamic RRT": {"success_rate_pct": 50, "length_cells": 744.75, "time_s": 21.14, "dist_left": 333.8},
        "RRT Connect": {"success_rate_pct": 8, "length_cells": 766.27, "time_s": 5.65, "dist_left": 554.5},
    },
    "MoonPlanBench-20": {
        "Dijkstra": {"success_rate_pct": 100, "length_cells": 620.24, "time_s": 13.77, "dist_left": 0},
        "ThetaStar": {"success_rate_pct": 100, "length_cells": 623.17, "time_s": 12.36, "dist_left": 0},
        "AStar": {"success_rate_pct": 100, "length_cells": 620.24, "time_s": 19.52, "dist_left": 0},
        "RRT": {"success_rate_pct": 100, "length_cells": 776.42, "time_s": 6.13, "dist_left": 0},
        "Dynamic RRT": {"success_rate_pct": 100, "length_cells": 737.53, "time_s": 7.52, "dist_left": 0},
        "RRT Connect": {"success_rate_pct": 25, "length_cells": 789.26, "time_s": 5.91, "dist_left": 441.9},
    },
}

TIMEOUT_S: float = 60  # run.py PLANNER_TIMEOUT_SECONDS; applied after the fact here (see run_mode)
BENCHMARK_THERMAL_C: float = 0.0  # placeholder surface temperature; passes the -150 C gate, SYNTHETIC

MODES: tuple[str, ...] = ("dijkstra_cut", "dijkstra_nocut", "lunapath_single", "lunapath_multi")
MODE_LABELS: dict[str, str] = {
    "dijkstra_cut": "Saf mesafe Dijkstra, benchmark hareket modeli (köşe-kesme serbest)",
    "dijkstra_nocut": "Saf mesafe Dijkstra, LunaPath kuralı (köşe-kesme yasak; nav2 baseline)",
    "lunapath_single": "LunaPath A*, tek kriter (w_slope = 1)",
    "lunapath_multi": "LunaPath A*, çok kriter (rover varsayılan ağırlıkları)",
}
SINGLE_CRITERION_WEIGHTS: dict[str, float] = {
    "w_slope": 1.0, "w_energy": 0.0, "w_shadow": 0.0, "w_thermal": 0.0, "w_roughness": 0.0,
}

REFERENCE_PLANNERS: tuple[str, ...] = ("Dijkstra", "AStar", "ThetaStar")
_REFERENCE_ADAPTERS: dict[str, str] = {"Dijkstra": "dijkstra", "AStar": "a_star", "ThetaStar": "thetastar"}

CLAIM: str = (
    "MoonPlanBench maps are slope/roughness-thresholded occupancy grids only (no shadow, "
    "thermal, slip, roughness or Earth-visibility layer, no DEM released), at 320 m to "
    "7 680 m per cell: LunaPath's multi-criteria cost grid is a single value on them and "
    "its planner reduces to a shortest-path search with its own safety rules. Success here "
    "measures connectivity under a motion model, not rover route planning. The benchmark's "
    "reference planners allow diagonal moves between two occupied cells; LunaPath refuses "
    "them. Every paper figure is a quotation from arXiv 2512.21438v1, not our measurement."
)

_NEIGHBOURS_XY: tuple[tuple[int, int], ...] = (
    (1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1),
)  # (dx, dy), the order of adapters/_common._NEIGHBORS -- it decides BFS order and hence ties
_OFFSETS_RC: tuple[tuple[int, int], ...] = (
    (-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1),
)


# ── Maps ───────────────────────────────────────────────────────────────────


def cell_size_m(map_name: str) -> float:
    """Metres per benchmark cell: the LDEM product's native resolution times
    the paper's down-sampling factor. Derived from the file name; the maps
    carry no georeference of their own."""
    stem = os.path.basename(str(map_name))
    if stem.endswith(".npy"):
        stem = stem[:-4]
    try:
        native = LDEM_NATIVE_M_PER_PX[stem]
    except KeyError:
        raise ValueError(f"{map_name!r} is not one of the 12 MoonPlanBench LDEM products") from None
    return float(native * DOWNSAMPLE_FACTOR)


def load_occupancy(path: str | os.PathLike) -> np.ndarray:
    """Boolean occupancy, True = occupied (``run.py``: ``grid != 0``)."""
    arr = np.load(path, allow_pickle=False)
    if arr.ndim != 2:
        raise ValueError(f"{path}: occupancy map must be 2-D, got shape {arr.shape}")
    return np.asarray(arr != 0, dtype=bool)


def auto_select_start_goal(occ: np.ndarray) -> tuple[tuple[int, int], tuple[int, int]]:
    """The benchmark's start/goal rule, reimplemented step for step from
    ``adapters/_common.auto_select_start_goal``: BFS over the largest
    8-connected free component (scan rows then columns, neighbour order
    :data:`_NEIGHBOURS_XY`), start = lexicographically smallest (y, x),
    goal = the component cell farthest from the start (first in BFS order on
    ties). Returns ``((row, col), (row, col))``."""
    occ = np.asarray(occ, dtype=bool)
    if occ.ndim != 2:
        raise ValueError("occupancy map must be 2-D")
    free = ~occ
    if not free.any():
        raise ValueError("occupancy map has no free cells")
    height, width = free.shape
    free_rows = free.tolist()
    visited = [[False] * width for _ in range(height)]
    largest: list[tuple[int, int]] = []
    for y in range(height):
        row = free_rows[y]
        for x in range(width):
            if not row[x] or visited[y][x]:
                continue
            component: list[tuple[int, int]] = []
            queue = deque([(x, y)])
            visited[y][x] = True
            while queue:
                xc, yc = queue.popleft()
                component.append((xc, yc))
                for dx, dy in _NEIGHBOURS_XY:
                    nx, ny = xc + dx, yc + dy
                    if 0 <= nx < width and 0 <= ny < height and not visited[ny][nx] and free_rows[ny][nx]:
                        visited[ny][nx] = True
                        queue.append((nx, ny))
            if len(component) > len(largest):
                largest = component
    start = min(largest, key=lambda p: (p[1], p[0]))
    x0, y0 = start
    goal = max(largest, key=lambda p: (p[0] - x0) ** 2 + (p[1] - y0) ** 2)
    return (int(start[1]), int(start[0])), (int(goal[1]), int(goal[0]))


# ── Pure-distance Dijkstra (the nav2 / SmacPlanner2D objective) ────────────


def shortest_traversable_path(
    traversable: np.ndarray,
    start: tuple[int, int],
    goal: tuple[int, int],
    resolution_m: float,
    allow_corner_cutting: bool = False,
) -> tuple[list[tuple[int, int]], float]:
    """8-connected Dijkstra on pure distance.

    With ``allow_corner_cutting=False`` (the default, and LunaPath's rule) a
    diagonal step is refused unless both cardinal neighbours it passes
    between are traversable -- without it the baseline may squeeze between
    two blocked cells where LunaPath refuses to (round 2 review, M-1).
    ``allow_corner_cutting=True`` is the motion model of MoonPlanBench's
    reference planners (PythonRobotics ``verify_node`` checks the
    destination cell only). Returns ``(path, distance)``; ``([], inf)`` when
    the goal is unreachable.
    """
    import heapq

    trav = np.asarray(traversable, dtype=bool)
    height, width = trav.shape
    start = (int(start[0]), int(start[1]))
    goal = (int(goal[0]), int(goal[1]))
    if not (0 <= start[0] < height and 0 <= start[1] < width and trav[start]):
        return [], math.inf
    if not (0 <= goal[0] < height and 0 <= goal[1] < width and trav[goal]):
        return [], math.inf
    trav_rows = trav.tolist()
    diagonal = float(resolution_m) * math.sqrt(2.0)
    cardinal = float(resolution_m)
    dist: dict[tuple[int, int], float] = {start: 0.0}
    came: dict[tuple[int, int], tuple[int, int]] = {}
    heap = [(0.0, start)]
    seen: set[tuple[int, int]] = set()
    while heap:
        d, node = heapq.heappop(heap)
        if node in seen:
            continue
        seen.add(node)
        if node == goal:
            break
        r, c = node
        for dr, dc in _OFFSETS_RC:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < height and 0 <= nc < width) or not trav_rows[nr][nc]:
                continue
            if dr and dc:
                if not allow_corner_cutting and not (trav_rows[r][nc] and trav_rows[nr][c]):
                    continue
                nd = d + diagonal
            else:
                nd = d + cardinal
            if nd < dist.get((nr, nc), math.inf):
                dist[(nr, nc)] = nd
                came[(nr, nc)] = node
                heapq.heappush(heap, (nd, (nr, nc)))
    if goal not in dist:
        return [], math.inf
    path = [goal]
    while path[-1] in came:
        path.append(came[path[-1]])
    path.reverse()
    return path, dist[goal]


# ── PathBench metric definitions ───────────────────────────────────────────


def bresenham_line(a: tuple[int, int], b: tuple[int, int]) -> list[tuple[int, int]]:
    """Grid cells from *a* to *b* inclusive, stepped exactly like PathBench's
    replay (``pathbench_wrappers._grid_line_sequence``; x = column,
    y = row) so a rasterised any-angle path measures as the benchmark
    measures it."""
    y0, x0 = int(a[0]), int(a[1])
    y1, x1 = int(b[0]), int(b[1])
    points = [(y0, x0)]
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    x_step = 1 if x0 < x1 else -1
    y_step = 1 if y0 < y1 else -1
    err = dx - dy
    x, y = x0, y0
    while x != x1 or y != y1:
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += x_step
        if e2 < dx:
            err += dx
            y += y_step
        points.append((y, x))
    return points


def rasterize_path(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Consecutive waypoints joined by :func:`bresenham_line`, without
    repeated cells -- the trace PathBench replays for a Theta* path."""
    if not points:
        return []
    out = [(int(points[0][0]), int(points[0][1]))]
    for current, nxt in zip(points, points[1:]):
        if current == nxt:
            continue
        for cell in bresenham_line(current, nxt)[1:]:
            if cell != out[-1]:
                out.append(cell)
    return out


def path_length_cells(path: list[tuple[int, int]]) -> float:
    """Sum of Euclidean steps, in grid cells (PathBench ``total_distance``)."""
    return float(sum(math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in zip(path[:-1], path[1:])))


def path_steps(path: list[tuple[int, int]]) -> int:
    """Number of moves (PathBench ``total_steps``: trace entries before the
    goal is appended)."""
    return max(len(path) - 1, 0)


def trajectory_smoothness(path: list[tuple[int, int]]) -> float:
    """PathBench ``get_smoothness``: for each move the unit vector from the
    current point BACK to the previous one, ``theta = arccos(u_x)`` (x is
    the column axis; the y component is discarded, so the angle is
    unsigned), the sum of ``|theta_i - theta_{i-1}|`` divided by the number
    of trace points. Kept exactly, quirk included."""
    if len(path) < 2:
        return 0.0
    total = 0.0
    prev: float | None = None
    for a, b in zip(path[:-1], path[1:]):
        if a == b:
            continue
        vx = a[1] - b[1]
        vy = a[0] - b[0]
        norm = math.hypot(vx, vy)
        theta = math.acos(max(-1.0, min(1.0, vx / norm)))
        if prev is None:
            prev = theta
            continue
        total += abs(prev - theta)
        prev = theta
    return total / len(path)


def obstacle_clearance(path: list[tuple[int, int]], occ: np.ndarray) -> float:
    """PathBench ``get_average_clearance``: mean over trace points of the
    Euclidean distance to the nearest occupied cell; 0 when the map has no
    obstacles. The exact distance transform gives the same minimum as the
    brute-force scan PathBench performs."""
    occ = np.asarray(occ, dtype=bool)
    if not path or not occ.any():
        return 0.0
    edt = distance_transform_edt(~occ)
    rows = np.fromiter((p[0] for p in path), dtype=np.intp, count=len(path))
    cols = np.fromiter((p[1] for p in path), dtype=np.intp, count=len(path))
    return float(np.mean(edt[rows, cols]))


def distance_to_goal(path: list[tuple[int, int]], start: tuple[int, int], goal: tuple[int, int]) -> float:
    """PathBench ``distance_to_goal``: from the agent's final cell; with no
    path planned the agent never moved, so it is the start-to-goal distance."""
    last = path[-1] if path else start
    return float(math.hypot(last[0] - goal[0], last[1] - goal[1]))


# ── Occupancy -> LunaPath grids ────────────────────────────────────────────


def occupancy_to_grids(
    occ: np.ndarray,
    cell_size_m: float | None,
    *,
    variant: str | None = None,
    map_name: str | None = None,
) -> dict[str, Any]:
    """The grids dictionary :func:`app.pathfinder.astar` plans on, built from
    an occupancy map alone: ``traversable = ~occ`` (the benchmark's
    definition; the rover's slope limit is not applied), zero elevation,
    slope and shadow, a constant placeholder temperature. Provenance is
    stamped: ``traversable`` is DERIVED (the authors' thresholding of LOLA),
    everything else SYNTHETIC."""
    occ = np.asarray(occ, dtype=bool)
    if occ.ndim != 2:
        raise ValueError("occupancy map must be 2-D")
    shape = occ.shape
    zeros = np.zeros(shape, dtype=np.float64)
    resolution = 1.0 if cell_size_m is None else float(cell_size_m)
    stem = None if map_name is None else os.path.basename(str(map_name)).removesuffix(".npy")
    return {
        "elevation": zeros,
        "slope": zeros.copy(),
        "thermal": np.full(shape, BENCHMARK_THERMAL_C, dtype=np.float64),
        "shadow_ratio": zeros.copy(),
        "traversable": ~occ,
        "metadata": {
            "resolution_m": resolution,
            "shape": [int(shape[0]), int(shape[1])],
            "source": "moonplanbench",
            "layer_validity": {
                "elevation": "SYNTHETIC",
                "slope": "SYNTHETIC",
                "thermal": "SYNTHETIC",
                "shadow_ratio": "SYNTHETIC",
                "traversable": "DERIVED",
            },
            "benchmark": {
                "paper": PAPER_ARXIV,
                "variant": variant,
                "slope_threshold_deg": SLOPE_THRESHOLD_DEG.get(variant) if variant else None,
                "map": stem,
                "native_m_per_px": LDEM_NATIVE_M_PER_PX.get(stem) if stem else None,
                "downsample_factor": DOWNSAMPLE_FACTOR,
                "cell_size_m": cell_size_m,
                "claim": CLAIM,
            },
        },
    }


# ── One planner on one map ─────────────────────────────────────────────────


def _resolve_rover(rover: Mapping[str, Any] | str | None) -> Mapping[str, Any]:
    if rover is None or isinstance(rover, str):
        return get_rover(rover)
    return rover


class _Timed:
    """Wall-clock around a planner call and, only when asked, the
    ``tracemalloc`` peak. Tracing is opt-in because it slows allocation-heavy
    Python by several times (measured here: 0.9 s -> 4.7 s for the pure
    Dijkstra on a 450 x 450 map), so a traced run's time is not the
    planner's time. PathBench traces every simulation it times."""

    def __init__(self, trace_memory: bool) -> None:
        self.trace_memory = trace_memory
        self.time_s = 0.0
        self.memory_kb: float | None = None

    def __enter__(self) -> "_Timed":
        if self.trace_memory:
            tracemalloc.start()
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *exc) -> None:
        self.time_s = time.perf_counter() - self._t0
        if self.trace_memory:
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            self.memory_kb = peak / 1000.0


def _finish(
    *,
    mode: str,
    path: list[tuple[int, int]],
    occ: np.ndarray,
    start: tuple[int, int],
    goal: tuple[int, int],
    cell_size_m: float | None,
    time_s: float,
    memory_kb: float | None,
    nodes_expanded: int | None,
    error: str | None,
) -> dict[str, Any]:
    goal = (int(goal[0]), int(goal[1]))
    timed_out = time_s > TIMEOUT_S
    success = bool(path) and tuple(path[-1]) == goal and not timed_out
    if success:
        length = path_length_cells(path)
        metrics = {
            "length_cells": length,
            "length_m": None if cell_size_m is None else length * float(cell_size_m),
            "steps": path_steps(path),
            "smoothness": trajectory_smoothness(path),
            "clearance": obstacle_clearance(path, occ),
        }
    else:
        metrics = {"length_cells": None, "length_m": None, "steps": None, "smoothness": None, "clearance": None}
        if error is None:
            error = "timed out (> %g s)" % TIMEOUT_S if timed_out else "no path"
    return {
        "mode": mode,
        "success": success,
        "timed_out": timed_out,
        "path": path,
        **metrics,
        "time_s": time_s,
        "memory_kb": memory_kb,
        "dist_left": distance_to_goal(path if success else [], start, goal),
        "original_distance": float(math.hypot(start[0] - goal[0], start[1] - goal[1])),
        "nodes_expanded": nodes_expanded,
        "error": error,
    }


def run_mode(
    mode: str,
    occ: np.ndarray,
    start: tuple[int, int],
    goal: tuple[int, int],
    cell_size_m: float | None,
    rover: Mapping[str, Any] | str | None = None,
    trace_memory: bool = False,
) -> dict[str, Any]:
    """Plan ``start -> goal`` on one occupancy map in one of :data:`MODES`
    and measure it the PathBench way. The wall clock wraps the planner call
    only; the ``tracemalloc`` peak is measured only with *trace_memory*
    (see :class:`_Timed`), otherwise ``memory_kb`` is None. The 60 s limit
    is applied afterwards (a run over it counts as a failure,
    ``timed_out``); nothing is killed."""
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; one of {MODES}")
    occ = np.asarray(occ, dtype=bool)
    start = (int(start[0]), int(start[1]))
    goal = (int(goal[0]), int(goal[1]))
    nodes: int | None = None
    error: str | None = None
    if mode.startswith("lunapath"):
        from .pathfinder import astar

        grids = occupancy_to_grids(occ, cell_size_m)
        weights = SINGLE_CRITERION_WEIGHTS if mode == "lunapath_single" else None
        rover_cfg = _resolve_rover(rover)
        with _Timed(trace_memory) as timed:
            res = astar(grids, start, goal, weights=weights, rover=rover_cfg)
        path = [(int(r), int(c)) for r, c in res["path_pixels"]] if res.get("path_pixels") else []
        nodes = res.get("metrics", {}).get("nodes_expanded")
        error = res.get("error") or None
    else:
        with _Timed(trace_memory) as timed:
            path, _ = shortest_traversable_path(
                ~occ, start, goal, 1.0, allow_corner_cutting=(mode == "dijkstra_cut")
            )
    return _finish(
        mode=mode, path=path, occ=occ, start=start, goal=goal, cell_size_m=cell_size_m,
        time_s=timed.time_s, memory_kb=timed.memory_kb, nodes_expanded=nodes, error=error,
    )


def run_reference_planner(
    name: str,
    occ: np.ndarray,
    start: tuple[int, int],
    goal: tuple[int, int],
    reference_dir: str | os.PathLike,
    trace_memory: bool = False,
) -> dict[str, Any]:
    """The benchmark's own planner *name* (PythonRobotics Dijkstra / AStar /
    ThetaStar through the authors' ``adapters``), imported from a local
    clone of PlanetaryPathBench at *reference_dir* -- nothing is vendored.
    Theta* returns an any-angle polyline; ``length_cells_raw`` is its own
    length and ``length_cells`` the length of the Bresenham-rasterised
    trace PathBench actually measures. Memory only with *trace_memory*.
    Without a usable clone the result says ``error: not run: ...``."""
    if name not in REFERENCE_PLANNERS:
        raise ValueError(f"unknown reference planner {name!r}; one of {REFERENCE_PLANNERS}")
    occ = np.asarray(occ, dtype=bool)
    start = (int(start[0]), int(start[1]))
    goal = (int(goal[0]), int(goal[1]))
    ref_dir = str(Path(reference_dir).resolve())
    base = {"planner": name, "length_cells_raw": None, "points_raw": None}
    if not os.path.isdir(os.path.join(ref_dir, "adapters")):
        return {
            **base,
            **_finish(mode="reference", path=[], occ=occ, start=start, goal=goal, cell_size_m=None,
                      time_s=0.0, memory_kb=None, nodes_expanded=None,
                      error=f"not run: no adapters/ under {ref_dir}"),
        }
    os.environ.setdefault("MPLBACKEND", "Agg")
    inserted = ref_dir not in sys.path
    if inserted:
        sys.path.insert(0, ref_dir)
    try:
        module = importlib.import_module(f"adapters.{_REFERENCE_ADAPTERS[name]}")
    except Exception as exc:  # noqa: BLE001 - reported, not raised
        if inserted:
            sys.path.remove(ref_dir)
        return {
            **base,
            **_finish(mode="reference", path=[], occ=occ, start=start, goal=goal, cell_size_m=None,
                      time_s=0.0, memory_kb=None, nodes_expanded=None,
                      error=f"not run: import failed: {exc!r}"),
        }
    occ_int = occ.astype(int)
    sink = io.StringIO()
    try:
        with _Timed(trace_memory) as timed, contextlib.redirect_stdout(sink):
            try:
                rx, ry = module.run(occ_int, [start[1], start[0]], [goal[1], goal[0]])
                error = None
            except Exception as exc:  # noqa: BLE001 - reported, not raised
                rx, ry, error = [], [], f"planner raised {exc!r}"
    finally:
        if inserted:
            sys.path.remove(ref_dir)
    time_s, peak_kb = timed.time_s, timed.memory_kb
    raw = [(int(round(float(y))), int(round(float(x)))) for x, y in zip(rx, ry)]
    # PythonRobotics returns the path goal -> start; orient it like the
    # benchmark's _orient_path (whichever end is nearer the start leads).
    if raw and math.hypot(raw[0][0] - start[0], raw[0][1] - start[1]) > math.hypot(raw[-1][0] - start[0], raw[-1][1] - start[1]):
        raw.reverse()
    reached = len(raw) >= 2 and raw[0] == start and raw[-1] == goal
    path = rasterize_path(raw) if reached else []
    result = _finish(
        mode="reference", path=path, occ=occ, start=start, goal=goal, cell_size_m=None,
        time_s=time_s, memory_kb=peak_kb, nodes_expanded=None,
        error=error if error else (None if reached else "no path"),
    )
    return {**base, **result, "length_cells_raw": path_length_cells(raw) if reached else None,
            "points_raw": len(raw) if reached else None}


# ── Aggregation (PathBench analyzer) and the whole benchmark ───────────────


def _mean(values: list[float | None]) -> float | None:
    present = [float(v) for v in values if v is not None]
    return sum(present) / len(present) if present else None


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """PathBench's ``Analyzer.__get_results``: success rate over all runs;
    length, steps, time, smoothness and clearance averaged over SUCCESSFUL
    runs only; distance left, original distance and memory over all runs.
    ``max_time_s`` and ``mean_nodes_expanded`` are ours, over all runs."""
    ok = [r for r in rows if r.get("success")]
    n = len(rows)
    return {
        "n_maps": n,
        "n_success": len(ok),
        "n_timed_out": sum(1 for r in rows if r.get("timed_out")),
        "success_rate_pct": (100.0 * len(ok) / n) if n else None,
        "mean_length_cells": _mean([r["length_cells"] for r in ok]),
        "mean_length_m": _mean([r.get("length_m") for r in ok]),
        "mean_steps": _mean([r["steps"] for r in ok]),
        "mean_time_s": _mean([r["time_s"] for r in ok]),
        "max_time_s": max((float(r["time_s"]) for r in rows), default=None),
        "mean_time_s_traced": _mean([r.get("time_s_traced") for r in ok]),
        "mean_smoothness": _mean([r["smoothness"] for r in ok]),
        "mean_clearance": _mean([r["clearance"] for r in ok]),
        "mean_dist_left": _mean([r["dist_left"] for r in rows]),
        "mean_original_distance": _mean([r["original_distance"] for r in rows]),
        "mean_memory_kb": _mean([r["memory_kb"] for r in rows]),
        "mean_nodes_expanded": _mean([r.get("nodes_expanded") for r in rows]),
    }


def load_inventory(data_dir: str | os.PathLike) -> dict[str, list[Path]]:
    """``{variant: sorted .npy paths}`` for the variants present under
    *data_dir*, in :data:`VARIANTS` order. Empty when nothing is there."""
    root = Path(data_dir)
    inventory: dict[str, list[Path]] = {}
    for variant in VARIANTS:
        folder = root / variant
        if folder.is_dir():
            paths = sorted(folder.glob("*.npy"))
            if paths:
                inventory[variant] = paths
    return inventory


def load_meta(data_dir: str | os.PathLike) -> dict[str, Any] | None:
    path = Path(data_dir) / META_FILENAME
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _strip_path(result: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in result.items() if k != "path"}


def _cost_grid_unique_values(occ: np.ndarray, cell: float | None, rover: Mapping[str, Any]) -> int:
    from .cost_engine import compute_cost_grid

    grids = occupancy_to_grids(occ, cell)
    cost = compute_cost_grid(
        grids["slope"], grids["thermal"], grids["shadow_ratio"],
        grids["metadata"]["resolution_m"], traversable=grids["traversable"], rover=rover,
    )
    finite = cost[np.isfinite(cost)]
    return int(np.unique(np.round(finite, 9)).size)


def run_benchmark(
    data_dir: str | os.PathLike,
    modes: tuple[str, ...] | list[str] = MODES,
    max_maps: int | None = None,
    reference_dir: str | os.PathLike | None = None,
    rover_id: str = "lpr_1",
    progress: Callable[[str], None] | None = None,
    memory: bool = False,
) -> dict[str, Any]:
    """Every map of every variant found under *data_dir* through every mode
    (and, with *reference_dir*, the benchmark's own planners), with
    PathBench aggregates per variant. Paths are not kept in the result.
    With *memory* each mode runs a second time under ``tracemalloc``; that
    pass supplies ``memory_kb`` and ``time_s_traced`` while ``time_s`` stays
    the untraced planner time. The reference planners are never traced."""
    inventory = load_inventory(data_dir)
    if not inventory:
        raise FileNotFoundError(f"no MoonPlanBench variant folder with .npy maps under {data_dir}")
    modes = list(modes)
    for mode in modes:
        if mode not in MODES:
            raise ValueError(f"unknown mode {mode!r}; one of {MODES}")
    rover = get_rover(rover_id)

    if reference_dir is None:
        reference = {"status": "not run: no --reference-dir given", "planners": [], "dir": None}
    elif not os.path.isdir(os.path.join(str(reference_dir), "adapters")):
        reference = {"status": f"not run: {reference_dir} has no adapters/ directory", "planners": [], "dir": str(reference_dir)}
    else:
        reference = {"status": "run", "planners": list(REFERENCE_PLANNERS), "dir": str(Path(reference_dir).resolve())}

    variants: dict[str, Any] = {}
    for variant, paths in inventory.items():
        maps: list[dict[str, Any]] = []
        for path in paths[:max_maps] if max_maps else paths:
            if progress:
                progress(f"{variant}/{path.stem}")
            occ = load_occupancy(path)
            entry: dict[str, Any] = {
                "map": path.stem,
                "file": path.name,
                "shape": [int(occ.shape[0]), int(occ.shape[1])],
                "free_fraction": float(1.0 - occ.mean()),
            }
            try:
                cell = cell_size_m(path.stem)
            except ValueError:
                cell = None
            entry["cell_size_m"] = cell
            try:
                start, goal = auto_select_start_goal(occ)
            except ValueError as exc:
                entry.update({"skipped": str(exc), "results": {}, "reference": {}})
                maps.append(entry)
                continue
            entry["start_rc"] = [start[0], start[1]]
            entry["goal_rc"] = [goal[0], goal[1]]
            entry["original_distance_cells"] = float(math.hypot(start[0] - goal[0], start[1] - goal[1]))
            entry["cost_grid_unique_values"] = _cost_grid_unique_values(occ, cell, rover)
            results: dict[str, Any] = {}
            for mode in modes:
                result = _strip_path(run_mode(mode, occ, start, goal, cell, rover))
                if memory:
                    traced = run_mode(mode, occ, start, goal, cell, rover, trace_memory=True)
                    result["memory_kb"] = traced["memory_kb"]
                    result["time_s_traced"] = traced["time_s"]
                results[mode] = result
            entry["results"] = results
            entry["reference"] = (
                {name: _strip_path(run_reference_planner(name, occ, start, goal, reference["dir"])) for name in reference["planners"]}
                if reference["status"] == "run" else {}
            )
            maps.append(entry)
        ran = [m for m in maps if "skipped" not in m]
        variants[variant] = {
            "slope_threshold_deg": SLOPE_THRESHOLD_DEG[variant],
            "maps": maps,
            "aggregates": {mode: aggregate([m["results"][mode] for m in ran]) for mode in modes},
            "reference_aggregates": {
                name: aggregate([m["reference"][name] for m in ran]) for name in reference["planners"]
            } if reference["status"] == "run" else {},
        }
    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_dir": str(Path(data_dir).resolve()),
        "meta": load_meta(data_dir),
        "rover_id": rover_id,
        "modes": modes,
        "timeout_s": TIMEOUT_S,
        "memory_pass": bool(memory),
        "reference": reference,
        "variants": variants,
        "paper_table_1": PAPER_TABLE_1,
        "claim": CLAIM,
    }
