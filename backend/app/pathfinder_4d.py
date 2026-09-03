"""Time-expanded A*: states are (row, col, time_slice).

Two edge families:

* MOVE  (r, c, t) -> (r', c', t + dt)   dt = ceil(travel_time / slice_hours)
* WAIT  (r, c, t) -> (r,  c,  t + 1)

The WAIT edge is the point of the whole thing. On the lunar pole the right
answer is often "stop, let the Sun come, then cross" -- a decision a static
planner cannot express.

The 2-D ``app.pathfinder.astar`` is untouched; this is an additional
planner, not a replacement.
"""

from __future__ import annotations

import heapq
import math
import time
from collections import deque
from collections.abc import Mapping
from typing import Any

import numpy as np

from .cost_engine import edge_travel_time_s, lateral_slope_tan

# Every reason this planner can refuse an edge. Declared once so the metrics
# always carry the full set of keys and a caller can tell "checked, none"
# from "not counted". (Round 4 review, H-2.)
REJECTION_KEYS: tuple[str, ...] = (
    "step_slope",
    "lateral_slope",
    "nan_elevation",
    "untraversable",
    "corner_cut",
    "cost_infinite",
    "horizon",
    # The rover's envelope, carried in the search state: a transition that
    # would drain the battery below the reserve, or keep the rover in
    # continuous shadow longer than it survives.
    "soc_floor",
    "shadow_endurance",
)


def _empty_rejections() -> dict[str, int]:
    return {key: 0 for key in REJECTION_KEYS}


def no_path_reason_4d(
    rejections: dict[str, int],
    rover: Mapping[str, Any],
    n_slices: int,
    slice_hours: float,
) -> str:
    """Explain which constraint closed a 4-D route.

    Round 3 gave the 2-D planner ``_no_path_reason`` and left this planner
    with one string: "No path found within the time horizon". That message is
    not merely unhelpful, it is usually WRONG. At the default ``coarsen=4``,
    618 of 8 768 passable coarse cells -- 7.0 percent -- have no surviving
    edge at all once the cross-slope gate is applied, and a plan starting
    from one of them returned the horizon message however many slices the
    caller granted: reproduced at 800 slices against a 103-move route.
    (Round 4 review, H-2.)
    """
    lateral = rejections.get("lateral_slope", 0)
    along = rejections.get("step_slope", 0)
    horizon = rejections.get("horizon", 0)
    blocked = rejections.get("cost_infinite", 0)
    unknown = rejections.get("nan_elevation", 0)
    soc = rejections.get("soc_floor", 0)
    endurance = rejections.get("shadow_endurance", 0)

    parts: list[str] = []
    # The envelope first: when the battery or the darkness closed the route,
    # that is the answer, and slope counts beside it are noise.
    if soc:
        reserve_pct = 100.0 * float(rover.get("soc_min_pct") or 0.0)
        parts.append(
            f"{soc} edges would have drained the battery below the "
            f"{reserve_pct:.0f} percent reserve"
        )
    if endurance:
        parts.append(
            f"{endurance} edges would have kept the rover in continuous shadow "
            f"beyond its {float(rover['h_max_shadow_h']):g} h endurance"
        )
    if lateral:
        parts.append(
            f"{lateral} edges exceeded the {rover['slope_lateral_max_deg']} deg "
            "roll-over (cross-slope) limit"
        )
    if along:
        parts.append(
            f"{along} edges exceeded the {rover['slope_max_deg']} deg "
            "step-slope limit"
        )
    if blocked:
        parts.append(f"{blocked} edges led into cells with no finite cost")
    if unknown:
        parts.append(f"{unknown} edges crossed cells with no elevation")
    if horizon:
        parts.append(
            f"{horizon} edges would have arrived past the last of "
            f"{n_slices} slices ({n_slices * slice_hours:.1f} h)"
        )

    if not parts:
        return (
            "No path found: the goal is not reachable from the start through "
            "passable cells at this coarsen factor."
        )
    lead = "No path found"
    if horizon and not (lateral or along or blocked or unknown or soc or endurance):
        lead = "No path found within the time horizon"
    return (
        f"{lead} for {rover.get('name', rover.get('id', 'this rover'))}: "
        + "; ".join(parts)
        + "."
    )

_OFFSETS: tuple[tuple[int, int, bool], ...] = (
    (-1, 0, False), (1, 0, False), (0, -1, False), (0, 1, False),
    (-1, -1, True), (-1, 1, True), (1, -1, True), (1, 1, True),
)


def bfs_move_count(
    traversable: np.ndarray,
    start: tuple[int, int],
    goal: tuple[int, int],
) -> int | None:
    """Minimum number of 8-connected MOVE steps from *start* to *goal*.

    Unweighted and time-free -- it answers the same reachability question
    ``astar_4d`` does, but cheaply enough to check before spending time
    building a cost cube, and exactly enough to size a time horizon instead
    of guessing a slice count. Returns ``None`` when *start* or *goal* is
    out of bounds, either is blocked, or no route exists between them.

    A fixed default slice count (the pre-fix behaviour) starved routes
    whose start and goal were genuinely far apart on the production grid;
    an unbounded default risked masking a start/goal that coarsening had
    disconnected. This distinguishes the two cases up front instead of
    letting ``astar_4d`` exhaust its search and report a single generic
    "not found". (Faz 1-2-3 review, H1/H3.)
    """
    mask = np.asarray(traversable, dtype=bool)
    height, width = mask.shape
    if not (0 <= start[0] < height and 0 <= start[1] < width):
        return None
    if not (0 <= goal[0] < height and 0 <= goal[1] < width):
        return None
    if not mask[start] or not mask[goal]:
        return None
    if start == goal:
        return 0

    dist = np.full(mask.shape, -1, dtype=np.int64)
    dist[start] = 0
    queue: deque[tuple[int, int]] = deque([start])
    offsets = [(d_row, d_col) for d_row, d_col, _ in _OFFSETS]

    while queue:
        row, col = queue.popleft()
        # No goal test on pop: start == goal returned above, and every other
        # cell has its distance fixed when it is PUSHED, so the goal is
        # detected there. (Backend review, #20.)
        for d_row, d_col in offsets:
            nr, nc = row + d_row, col + d_col
            if (
                0 <= nr < height
                and 0 <= nc < width
                and mask[nr, nc]
                and dist[nr, nc] < 0
            ):
                # Same corner-cutting rule as astar_4d's MOVE edges: this
                # count sizes the planner's horizon, so counting a route
                # the planner cannot take would size it for a plan that
                # never happens. (Round 2 review, M-1.)
                if d_row and d_col and not (mask[row, nc] and mask[nr, col]):
                    continue
                dist[nr, nc] = dist[row, col] + 1
                if (nr, nc) == goal:
                    return int(dist[nr, nc])
                queue.append((nr, nc))
    return None


def gated_move_count(
    traversable: np.ndarray,
    start: tuple[int, int],
    goal: tuple[int, int],
    elevation: np.ndarray | None,
    resolution_m: float,
    rover: Mapping[str, Any],
) -> int | None:
    """:func:`bfs_move_count`, but honouring the hard EDGE gates as well.

    ``bfs_move_count`` answers reachability through passable CELLS.
    ``astar_4d`` additionally refuses edges on step slope and cross-slope, so
    the two graphs are not the same one -- and on the production grid at
    ``coarsen=4`` the difference is large: 83.5 percent of the passable area
    is reachable through cells, and the gated graph's largest component is
    76.4 percent, with 7.0 percent of cells isolated outright.

    Sizing the time horizon from the ungated count is therefore sizing it for
    a route the planner cannot take, and checking reachability with the
    ungated count reports a plan as merely horizon-limited when it is
    geometrically impossible. (Round 4 review, H-2.)
    """
    mask = np.asarray(traversable, dtype=bool)
    height, width = mask.shape
    if not (0 <= start[0] < height and 0 <= start[1] < width):
        return None
    if not (0 <= goal[0] < height and 0 <= goal[1] < width):
        return None
    if not mask[start] or not mask[goal]:
        return None
    if start == goal:
        return 0

    if elevation is None:
        return bfs_move_count(mask, start, goal)

    elev = np.asarray(elevation, dtype=np.float64)
    grad_row, grad_col = np.gradient(elev, float(resolution_m))
    grad_row = np.nan_to_num(grad_row, nan=0.0)
    grad_col = np.nan_to_num(grad_col, nan=0.0)
    tan_slope_max = math.tan(math.radians(float(rover["slope_max_deg"])))
    tan_lat_max_sq = math.tan(math.radians(float(rover["slope_lateral_max_deg"]))) ** 2
    diag_m = float(resolution_m) * math.sqrt(2.0)

    dist = np.full(mask.shape, -1, dtype=np.int64)
    dist[start] = 0
    queue: deque[tuple[int, int]] = deque([start])
    while queue:
        row, col = queue.popleft()
        for d_row, d_col, diagonal in _OFFSETS:
            nr, nc = row + d_row, col + d_col
            if not (0 <= nr < height and 0 <= nc < width):
                continue
            if not mask[nr, nc] or dist[nr, nc] >= 0:
                continue
            if diagonal and not (mask[row, nc] and mask[nr, col]):
                continue
            distance_m = diag_m if diagonal else float(resolution_m)
            dz = elev[nr, nc] - elev[row, col]
            if not math.isfinite(dz) or abs(dz) / distance_m > tan_slope_max:
                continue
            norm = math.hypot(d_row, d_col)
            unit_r, unit_c = d_row / norm, d_col / norm
            lat_tan = lateral_slope_tan(
                0.5 * (grad_row[row, col] + grad_row[nr, nc]),
                0.5 * (grad_col[row, col] + grad_col[nr, nc]),
                unit_r,
                unit_c,
            )
            if lat_tan * lat_tan > tan_lat_max_sq:
                continue
            dist[nr, nc] = dist[row, col] + 1
            if (nr, nc) == goal:
                return int(dist[nr, nc])
            queue.append((nr, nc))
    return None


def _empty(
    error: str,
    elapsed_ms: float = 0.0,
    rejections: dict[str, int] | None = None,
    nodes_expanded: int = 0,
) -> dict[str, Any]:
    """A failed plan.

    ``total_cost`` is ``None``, not ``inf``: this dict is a candidate for
    direct JSON serialisation and Starlette renders with ``allow_nan=False``,
    so a bare ``inf`` turns the response into a 500. ``None`` is the
    convention the rest of this API already uses for unrepresentable values
    (``main._read_grid_value``, ``main.get_layer``, ``CostMap.explain``).
    """
    tally = _empty_rejections() if rejections is None else dict(rejections)
    return {
        "path_states": [],
        "path_pixels": [],
        "metrics": {
            "wait_steps": 0,
            "move_steps": 0,
            "arrival_slice": None,
            "total_cost": None,
            "cost_units": "weighted_hours",
            # Threaded through rather than reported as a flat 0 beside a
            # non-empty rejection tally. (Round 4 review, M-2.)
            "nodes_expanded": nodes_expanded,
            "computation_time_ms": round(elapsed_ms, 3),
            "edges_rejected": tally,
            "edges_dropped_at_horizon": tally.get("horizon", 0),
            "horizon_truncated": tally.get("horizon", 0) > 0,
        },
        "error": error,
    }


# The envelope's resolution for DOMINANCE. At one (row, col, slice), a
# label whose battery is within one percent of capacity of a cheaper
# label's, and whose continuous shadow is within five percent of the
# endurance of it, is pruned: the difference is below anything the model
# can claim to resolve. Without a tolerance the search kept one label per
# floating-point drain value -- at a lunar-night epoch, where every edge
# drains by a slope-dependent amount, that is one label per path, and the
# production grid did not finish in ten minutes. A tolerance rather than
# fixed bins, because a bin boundary at exactly full charge split every
# lit-terrain label in two. Measured on the production grid (216 slices,
# coarsen 4): at these tolerances the tracked search expands exactly as
# many nodes as the untracked one (122 753 vs 122 604, static series) and
# finds the same cost; at half these tolerances the static series took
# 2.5x the nodes (the fractional long-run shadow resets the shadow clock
# differently on every path). The CONSTRAINTS are still checked on the
# exact values.
_BATTERY_DOMINANCE_TOL_FRAC: float = 0.01
_DARK_DOMINANCE_TOL_FRAC: float = 0.05
# Label keys (for the closed set and the cost table) are binned finely.
_BATTERY_BINS_PER_CAPACITY: int = 400
_DARK_BINS_PER_ENDURANCE: int = 100
# A slice counts toward continuous shadow when at least this much of it is
# dark. The SPICE series is binary, so this only matters for the static
# (long-run fraction) fallback, where it reads "mostly dark".
_DARK_RATIO_THRESHOLD: float = 0.5


def _dominated(
    front: list[tuple[float, float, float]],
    g: float,
    battery: float,
    dark: float,
    battery_tol: float,
    dark_tol: float,
    strict: bool = False,
) -> bool:
    """True if some label in *front* is at least as good on every axis.

    A label is (cost so far, battery Wh, continuous shadow hours). Lower
    cost, more battery and less shadow all dominate, each within its
    tolerance. With *strict* the label must be beaten on at least one axis
    beyond the tolerance, which is how a label already in the front is told
    apart from a genuine dominator at pop time.
    """
    for other_g, other_battery, other_dark in front:
        if (
            other_g <= g + 1e-12
            and other_battery >= battery - battery_tol
            and other_dark <= dark + dark_tol
        ):
            if not strict:
                return True
            if (
                other_g < g - 1e-12
                or other_battery > battery + battery_tol
                or other_dark < dark - dark_tol
            ):
                return True
    return False


def _insert_label(
    front: list[tuple[float, float, float]],
    g: float,
    battery: float,
    dark: float,
    battery_tol: float,
    dark_tol: float,
) -> None:
    """Add a non-dominated label and drop the ones it dominates."""
    front[:] = [
        (other_g, other_battery, other_dark)
        for other_g, other_battery, other_dark in front
        if not (
            g <= other_g + 1e-12
            and battery >= other_battery - battery_tol
            and dark <= other_dark + dark_tol
        )
    ]
    front.append((g, battery, dark))


def astar_4d(
    cost_cube: np.ndarray,
    wait_cost_cube: np.ndarray,
    traversable: np.ndarray,
    start: tuple[int, int],
    goal: tuple[int, int],
    resolution_m: float,
    slice_hours: float,
    rover: Mapping[str, Any],
    slope_grid: np.ndarray | None = None,
    elevation_grid: np.ndarray | None = None,
    shadow_cube: np.ndarray | None = None,
    initial_soc_frac: float = 1.0,
) -> dict[str, Any]:
    """Plan through space and time. Returns path_states, path_pixels, metrics.

    *elevation_grid*, when supplied, enables the same two hard edge
    constraints the 2-D planner enforces: the along-track step slope against
    ``slope_max_deg`` and the cross-slope against ``slope_lateral_max_deg``.
    Without it neither can be evaluated, and the two planners in this product
    would disagree about which edges are safe -- the same class of divergence
    round 2 fixed for corner-cutting. (Round 3 review, H-1 and H-2.)

    The rover's envelope in the state
    ---------------------------------
    *shadow_cube*, when supplied, is the (T, H, W) shadow ratio each label is
    exposed to. Every search label then carries the battery (Wh) and the
    continuous shadow hours accrued so far, integrated with the same physics
    ``wait_cost`` and the simulator use (``cost_engine.move_battery_drain_wh``
    and ``wait_battery_drain_wh``). A transition is refused when it would
    drain the battery below ``soc_min_pct`` of ``e_cap_wh`` -- unless it is a
    wait that CHARGES, so a rover parked under its reserve in sunlight may
    recover -- or keep the rover in continuous shadow beyond
    ``h_max_shadow_h``. Refusals are tallied as ``soc_floor`` and
    ``shadow_endurance``.

    This replaces the round-4 rule that closed a cell whenever its regolith
    skin fell below -150 C at that slice. Measured on the production grid at
    a lunar-night epoch that rule closed every cell within 2.5 h and refused
    every route for the whole night, while the catalogue gives LPR-1 50 h of
    darkness. The ground's skin temperature is priced by the cube; whether
    the rover may be there is decided here, by the rover.

    Labels at one (row, col, slice) are kept as a Pareto front over (cost,
    battery, shadow hours) so the search stays a label-setting A* rather
    than one state per drain value. The cost and the heuristic are
    unchanged, so admissibility is untouched: the envelope only removes
    edges.

    Without *shadow_cube* the envelope is not tracked: the battery is
    reported at ``initial_soc_frac`` throughout and shadow hours at zero,
    which is the pre-envelope behaviour the toy-cube tests exercise.
    """
    t0 = time.perf_counter()

    cost = np.asarray(cost_cube, dtype=np.float64)
    wait = np.asarray(wait_cost_cube, dtype=np.float64)
    passable = np.asarray(traversable, dtype=bool)

    if cost.ndim != 3:
        return _empty("cost_cube must be (T, H, W)")
    if wait.shape != cost.shape:
        return _empty("wait_cost_cube shape must match cost_cube")
    n_slices, height, width = cost.shape
    if passable.shape != (height, width):
        return _empty("traversable shape must match cost_cube slices")
    shadow = None if shadow_cube is None else np.asarray(shadow_cube, dtype=np.float64)
    if shadow is not None and shadow.shape != cost.shape:
        return _empty("shadow_cube shape must match cost_cube")

    def in_bounds(r: int, c: int) -> bool:
        return 0 <= r < height and 0 <= c < width

    if not in_bounds(*start):
        return _empty("Start out of bounds")
    if not in_bounds(*goal):
        return _empty("Goal out of bounds")
    if not passable[start]:
        return _empty("Start is not traversable")
    if not passable[goal]:
        return _empty("Goal is not traversable")

    slopes = (
        np.zeros((height, width), dtype=np.float64)
        if slope_grid is None
        else np.asarray(slope_grid, dtype=np.float64)
    )

    slope_max_deg = float(rover["slope_max_deg"])
    lateral_max_deg = float(rover["slope_lateral_max_deg"])
    tan_slope_max = math.tan(math.radians(slope_max_deg))
    tan_lat_max_sq = math.tan(math.radians(lateral_max_deg)) ** 2
    if elevation_grid is None:
        elevation = None
        grad_row = grad_col = None
    else:
        elevation = np.asarray(elevation_grid, dtype=np.float64)
        if elevation.shape != (height, width):
            return _empty("elevation_grid shape must match cost_cube slices")
        grad_row, grad_col = np.gradient(elevation, float(resolution_m))
        grad_row = np.nan_to_num(grad_row, nan=0.0)
        grad_col = np.nan_to_num(grad_col, nan=0.0)

    # Every refusal is counted, not just the horizon one. A move rejected
    # because it would land past the last slice is not the same as a move
    # that is unsafe, and until round 4 only the former was tallied -- so
    # when the geometry gates closed a route the planner said the horizon
    # was too short. (Round 3 M-3; round 4 H-2.)
    rejections = _empty_rejections()

    finite = cost[np.isfinite(cost)]
    min_cost = float(np.min(finite)) if finite.size else 0.01
    diag_m = resolution_m * math.sqrt(2.0)
    # MOVE and WAIT edges must live in the same units to trade off against
    # each other at all: MOVE used to cost distance_m * (1 + MRU) while WAIT
    # costs dt_hours * MRU-ish, off by orders of magnitude on the real grid
    # (measured: an average MOVE edge ~29, a dark WAIT step at the auto slice
    # length ~0.0045 -- ~6500x apart, so the planner could never meaningfully
    # choose to wait once the illumination cube stops being held constant
    # across slices). Both now cost hours: MOVE via the same edge_travel_time_s
    # the slice-count budget already uses, WAIT unchanged. The heuristic
    # follows suit, using v_max_ms (the fastest the rover ever moves) as a
    # divisor so distance/v_max stays a true lower bound on travel time for
    # any slope -- admissibility is preserved, not just the ordering.
    # (Faz 1-2-3 review, M2.)
    v_max_ms = float(rover["v_max_ms"])

    def heuristic(r: int, c: int) -> float:
        dr, dc = abs(r - goal[0]), abs(c - goal[1])
        straight, diagonal = abs(dr - dc), min(dr, dc)
        distance_m = straight * resolution_m + diagonal * diag_m
        hours_lower_bound = distance_m / v_max_ms / 3600.0
        return hours_lower_bound * (1.0 + min_cost)

    # -- The envelope -------------------------------------------------------
    e_cap_wh = float(rover["e_cap_wh"])
    reserve_wh = e_cap_wh * float(rover.get("soc_min_pct") or 0.0)
    h_max_shadow = float(rover["h_max_shadow_h"])
    battery0 = min(1.0, max(0.0, float(initial_soc_frac))) * e_cap_wh
    track = shadow is not None

    endurance_finite = math.isfinite(h_max_shadow) and h_max_shadow > 0.0
    dark_quantum_h = (
        h_max_shadow / _DARK_BINS_PER_ENDURANCE
        if endurance_finite
        else max(slice_hours, 1e-6)
    )
    battery_tol = e_cap_wh * _BATTERY_DOMINANCE_TOL_FRAC
    dark_tol = (
        h_max_shadow * _DARK_DOMINANCE_TOL_FRAC if endurance_finite else slice_hours
    )

    # The drain arithmetic, inlined: cost_engine.move_battery_drain_wh and
    # wait_battery_drain_wh are the reference (and the simulator's), and
    # test_pathfinder_4d checks this integration against them exactly, but
    # calling them per edge re-derived the travel time three times over and
    # doubled the planner's time per node.
    p_base_w = float(rover["p_base_w"])
    mu_coeff = float(rover["mu_coeff"])
    p_idle_w = float(rover["p_idle_w"])
    p_shadow_w = rover.get("p_shadow_w")
    shadow_extra_w = (
        max(0.0, float(p_shadow_w) - p_idle_w)
        if p_shadow_w is not None
        else float(rover.get("p_heater_w") or 0.0)
    )
    p_solar_w = float(rover.get("p_solar_w") or 0.0)

    def housekeeping_w(ratio: float) -> float:
        return p_idle_w + ratio * shadow_extra_w

    def battery_key(battery_wh: float) -> int:
        if e_cap_wh <= 0.0:
            return 0
        return int(battery_wh / e_cap_wh * _BATTERY_BINS_PER_CAPACITY)

    def dark_key(dark_h: float) -> int:
        return int(dark_h / dark_quantum_h)

    def label_of(r: int, c: int, t: int, battery_wh: float, dark_h: float):
        return (r, c, t, battery_key(battery_wh), dark_key(dark_h))

    def envelope_after(
        exposure: float,
        hours: float,
        battery_wh: float,
        dark_h: float,
        drain_wh: float,
    ) -> tuple[float, float, str | None]:
        """Battery and shadow hours after a transition, or the refusal key.

        *exposure* is the shadow ratio the rover is exposed to across the
        transition (the slice waited through, or the arrival cell for a
        move); *drain_wh* the signed battery change it costs.
        """
        new_battery = min(e_cap_wh, battery_wh - drain_wh)
        # Below the reserve is refused -- unless the transition CHARGES, so
        # a rover parked under its reserve in sunlight is allowed to recover.
        if new_battery < reserve_wh and new_battery < battery_wh:
            return battery_wh, dark_h, "soc_floor"
        if exposure >= _DARK_RATIO_THRESHOLD:
            new_dark = dark_h + hours * exposure
        else:
            new_dark = 0.0
        if new_dark > h_max_shadow + 1e-9:
            return battery_wh, dark_h, "shadow_endurance"
        return new_battery, new_dark, None

    # -- Label-setting A* ---------------------------------------------------
    start_label = label_of(start[0], start[1], 0, battery0, 0.0)
    g_score: dict[tuple, float] = {start_label: 0.0}
    battery_of: dict[tuple, float] = {start_label: battery0}
    dark_of: dict[tuple, float] = {start_label: 0.0}
    came_from: dict[tuple, tuple] = {}
    fronts: dict[tuple[int, int, int], list[tuple[float, float, float]]] = {
        (start[0], start[1], 0): [(0.0, battery0, 0.0)]
    }
    closed: set[tuple] = set()
    counter = 0
    heap: list[tuple[float, float, int, tuple]] = [
        (heuristic(*start), 0.0, counter, start_label)
    ]
    nodes_expanded = 0
    goal_label: tuple | None = None

    def push(
        r: int, c: int, t: int, g_new: float, battery_wh: float, dark_h: float, parent: tuple
    ) -> None:
        nonlocal counter
        node = (r, c, t)
        front = fronts.setdefault(node, [])
        if _dominated(front, g_new, battery_wh, dark_h, battery_tol, dark_tol):
            return
        _insert_label(front, g_new, battery_wh, dark_h, battery_tol, dark_tol)
        label = label_of(r, c, t, battery_wh, dark_h)
        if g_new < g_score.get(label, math.inf):
            g_score[label] = g_new
            battery_of[label] = battery_wh
            dark_of[label] = dark_h
            came_from[label] = parent
            counter += 1
            h = heuristic(r, c)
            heapq.heappush(heap, (g_new + h, h, counter, label))

    while heap:
        _f, _h, _n, label = heapq.heappop(heap)
        if label in closed:
            continue
        row, col, slice_index, _bkey, _dkey = label
        current_g = g_score[label]
        battery_wh = battery_of[label]
        dark_h = dark_of[label]
        # A label pushed earlier may have been dominated since by a better
        # one at the same node; expanding it would only re-derive worse
        # successors.
        if _dominated(
            fronts.get((row, col, slice_index), []),
            current_g,
            battery_wh,
            dark_h,
            battery_tol,
            dark_tol,
            strict=True,
        ):
            continue
        closed.add(label)
        nodes_expanded += 1

        if (row, col) == goal:
            goal_label = label
            break

        # WAIT edge
        if slice_index + 1 < n_slices:
            wait_step = float(wait[slice_index, row, col])
            if math.isfinite(wait_step):
                if track:
                    exposure = float(shadow[slice_index, row, col])
                    # == wait_battery_drain_wh(exposure, slice_hours, rover)
                    drain_wh = (
                        housekeeping_w(exposure) - p_solar_w * (1.0 - exposure)
                    ) * slice_hours
                    new_battery, new_dark, refused = envelope_after(
                        exposure, slice_hours, battery_wh, dark_h, drain_wh
                    )
                else:
                    new_battery, new_dark, refused = battery_wh, dark_h, None
                if refused is not None:
                    rejections[refused] += 1
                else:
                    push(
                        row, col, slice_index + 1,
                        current_g + wait_step, new_battery, new_dark, label,
                    )

        # MOVE edges
        for d_row, d_col, diagonal in _OFFSETS:
            nr, nc = row + d_row, col + d_col
            if not in_bounds(nr, nc):
                continue
            if not passable[nr, nc]:
                rejections["untraversable"] += 1
                continue

            # Diagonal corner-cutting safety, matching pathfinder._astar_core:
            # both adjacent cardinal cells must be passable, or the move
            # squeezes the rover diagonally between two blocked cells. The
            # 2-D planner has always refused this; without the same rule
            # here, /api/plan-4d returned routes through squeezes that
            # /api/plan calls untraversable -- two planners in one product
            # disagreeing about a safety predicate. bfs_move_count carries
            # the same rule so the horizon it sizes stays consistent with
            # the routes this loop can actually take. (Round 2 review, M-1.)
            if diagonal and not (passable[row, nc] and passable[nr, col]):
                rejections["corner_cut"] += 1
                continue

            distance_m = diag_m if diagonal else resolution_m

            # Same hard edge constraints as pathfinder._astar_core.
            if elevation is not None:
                dz = elevation[nr, nc] - elevation[row, col]
                if not math.isfinite(dz):
                    rejections["nan_elevation"] += 1
                    continue
                along_tan = abs(dz) / distance_m
                if along_tan > tan_slope_max:
                    rejections["step_slope"] += 1
                    continue
                norm = math.hypot(d_row, d_col)
                unit_r, unit_c = d_row / norm, d_col / norm
                g_row = 0.5 * (grad_row[row, col] + grad_row[nr, nc])
                g_col = 0.5 * (grad_col[row, col] + grad_col[nr, nc])
                # One shared implementation, in cost_engine. (Round 4, M-5.)
                lat_tan = lateral_slope_tan(g_row, g_col, unit_r, unit_c)
                if lat_tan * lat_tan > tan_lat_max_sq:
                    rejections["lateral_slope"] += 1
                    continue

            # Trapezoidal, matching pathfinder._astar_core's edge cost: an
            # edge is half in each cell, so its travel time follows the mean
            # of the two slopes rather than the destination's alone.
            # (Round 4 review, L-5.)
            edge_slope = 0.5 * (float(slopes[row, col]) + float(slopes[nr, nc]))
            travel_s = edge_travel_time_s(edge_slope, distance_m, rover)
            if not math.isfinite(travel_s):
                rejections["step_slope"] += 1
                continue
            d_slices = max(1, int(math.ceil(travel_s / 3600.0 / slice_hours)))
            arrival = slice_index + d_slices
            if arrival >= n_slices:
                rejections["horizon"] += 1
                continue

            from_cost = cost[slice_index, row, col]
            to_cost = cost[arrival, nr, nc]
            if not (math.isfinite(from_cost) and math.isfinite(to_cost)):
                rejections["cost_infinite"] += 1
                continue

            travel_h = travel_s / 3600.0
            if track:
                # The edge is half in each cell: the drain follows the mean
                # exposure, the same trapezoid the cost uses; the shadow
                # clock follows where the rover ends up.
                mean_exposure = 0.5 * (
                    float(shadow[slice_index, row, col])
                    + float(shadow[arrival, nr, nc])
                )
                # == move_battery_drain_wh(edge_slope, distance_m,
                #                          mean_exposure, rover)
                traction_w = p_base_w * (
                    1.0 + mu_coeff * math.sin(math.radians(max(0.0, edge_slope)))
                )
                drain_wh = (
                    traction_w
                    + housekeeping_w(mean_exposure)
                    - p_solar_w * (1.0 - mean_exposure)
                ) * travel_h
                new_battery, new_dark, refused = envelope_after(
                    float(shadow[arrival, nr, nc]), travel_h, battery_wh, dark_h, drain_wh
                )
                if refused is not None:
                    rejections[refused] += 1
                    continue
            else:
                new_battery, new_dark = battery_wh, dark_h

            step = travel_h * (1.0 + 0.5 * (from_cost + to_cost))
            push(nr, nc, arrival, current_g + step, new_battery, new_dark, label)

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    if goal_label is None:
        return _empty(
            no_path_reason_4d(rejections, rover, n_slices, slice_hours),
            elapsed_ms,
            rejections,
            nodes_expanded,
        )

    labels: list[tuple] = [goal_label]
    while labels[-1] in came_from:
        labels.append(came_from[labels[-1]])
    labels.reverse()

    states: list[tuple[int, int, int]] = [(r, c, t) for r, c, t, _b, _d in labels]
    batteries = [battery_of[label] for label in labels]
    darks = [dark_of[label] for label in labels]

    wait_steps = sum(
        1
        for previous, current in zip(states[:-1], states[1:])
        if previous[:2] == current[:2]
    )

    if e_cap_wh > 0.0:
        battery_pct = [round(100.0 * wh / e_cap_wh, 3) for wh in batteries]
    else:
        battery_pct = [100.0 for _ in batteries]
    energy_drawn = sum(max(0.0, a - b) for a, b in zip(batteries[:-1], batteries[1:]))
    energy_charged = sum(max(0.0, b - a) for a, b in zip(batteries[:-1], batteries[1:]))

    return {
        "path_states": states,
        "path_pixels": [(r, c) for r, c, _ in states],
        "path_battery_pct": battery_pct,
        "path_dark_hours": [round(d, 4) for d in darks],
        "metrics": {
            "wait_steps": wait_steps,
            "move_steps": len(states) - 1 - wait_steps,
            "arrival_slice": goal_label[2],
            "total_cost": round(float(g_score[goal_label]), 6),
            # MOVE edges cost travel HOURS scaled by the weighted cell cost,
            # and WAIT edges cost slice hours the same way -- so this total
            # is in weighted hours. app.pathfinder's total_weighted_cost is
            # in weighted METRES. Two endpoints answering different
            # questions under similar field names is a trap; the unit is
            # now stated. (Round 3 review, M-6.)
            "cost_units": "weighted_hours",
            "nodes_expanded": nodes_expanded,
            "computation_time_ms": round(elapsed_ms, 3),
            "edges_rejected": dict(rejections),
            "edges_dropped_at_horizon": rejections["horizon"],
            "horizon_truncated": rejections["horizon"] > 0,
            # The envelope along the route, as the planner accounted for it.
            "min_battery_pct": round(min(battery_pct), 3),
            "final_battery_pct": battery_pct[-1],
            "max_continuous_shadow_h": round(max(darks), 4),
            "energy_drawn_wh": round(energy_drawn, 3),
            "energy_charged_wh": round(energy_charged, 3),
            "envelope_tracked": track,
        },
        "error": None,
    }
