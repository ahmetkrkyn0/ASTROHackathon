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

from . import battery as battery_model_module
from .cost_engine import edge_travel_time_s, lateral_slope_tan
from .cost_cube import hibernate_cost, wait_cost
from .thermal_dwell import route_dwell_report

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
    # Direct-to-Earth: a MOVE whose arrival cell has no line of sight to
    # Earth at the arrival slice, refused only when the caller asked for the
    # VIPER teleoperation rule (require_earth_visibility). (A4.)
    "earth_visibility",
    # Safe haven (A1): a transition after which the rover could no longer
    # reach a safe haven before the Earth sets on it, refused only under
    # VIPER's leg rule (require_safe_haven).
    "safe_haven_deadline",
    # Continuous illumination (A2): a transition that would take the rover
    # out of the lit corridor -- a wait into a dark voxel, or a move whose
    # arrival voxel is outside the corridor or whose two blocks are not lit
    # for every slice of the move -- refused only under
    # require_continuous_illumination.
    "continuous_illumination",
    # The chance constraint (B1): a MOVE whose fault branches would push the
    # execution failure probability over max_failure_probability, refused
    # only when a survival field and a beta are given.
    "failure_probability",
    # The thermal dwell (C6): a WAIT that would keep the rover stationary in
    # a block longer than its inner temperature allows there (the cell's
    # max_dwell_h at the slice the stay began), refused only under
    # require_thermal_dwell with a dwell cube.
    "thermal_dwell",
    # Hibernation (C2): a HIBERNATE edge whose dawn pre-heat could not bring
    # the rover back inside its operating envelope in that cell -- the heater
    # saturates against the surface, or the array cannot supply it. Counted
    # rather than dropped: a non-finite pre-heat time would otherwise die
    # silently in the heap comparison and the route would report itself as
    # horizon-limited, which is exactly the H-2 failure no_path_reason_4d
    # exists to prevent.
    "hibernate_unwakeable",
    # Hibernation (C2): a dormancy whose inner temperature would leave the
    # SURVIVAL envelope -- the operating envelope widened at the cold end to
    # the cited 200 K freeze point. Distinct from "thermal_dwell", which is
    # C6's OPERATING envelope and only binds under require_thermal_dwell.
    "hibernate_too_cold",
)


def _empty_rejections() -> dict[str, int]:
    return {key: 0 for key in REJECTION_KEYS}


def no_path_reason_4d(
    rejections: dict[str, int],
    rover: Mapping[str, Any],
    n_slices: int,
    slice_hours: float,
    battery_model: str = "constant",
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
    dte = rejections.get("earth_visibility", 0)
    haven = rejections.get("safe_haven_deadline", 0)
    corridor = rejections.get("continuous_illumination", 0)
    risk = rejections.get("failure_probability", 0)
    dwell = rejections.get("thermal_dwell", 0)
    unwakeable = rejections.get("hibernate_unwakeable", 0)
    too_cold = rejections.get("hibernate_too_cold", 0)

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
        # C2: under the derated model the threshold is not the published
        # constant, it is what that state's deliverable charge still buys, so
        # the sentence must not quote the catalogue number as if it bound.
        if battery_model == "temperature_derated":
            parts.append(
                f"{endurance} edges would have kept the rover in continuous shadow beyond "
                f"what its charge and battery temperature could still sustain (the published "
                f"{float(rover['h_max_shadow_h']):g} h endurance scaled by the deliverable "
                "charge above the reserve; battery_model='temperature_derated')"
            )
        else:
            parts.append(
                f"{endurance} edges would have kept the rover in continuous shadow "
                f"beyond its {float(rover['h_max_shadow_h']):g} h endurance"
            )
    if dte:
        parts.append(
            f"{dte} edges would have driven the rover into a cell with no "
            "Earth visibility (require_earth_visibility: drive only with a "
            "direct-to-Earth link)"
        )
    if haven:
        parts.append(
            f"{haven} transitions would have left the rover unable to reach a "
            "safe haven before the Earth sets (require_safe_haven: "
            f"{float(rover['h_max_shadow_h']):g} h shadow endurance)"
        )
    if corridor:
        parts.append(
            f"{corridor} transitions would have taken the rover out of the "
            "continuous-illumination corridor (require_continuous_illumination: "
            "every block the rover occupies, for every slice of a move, must be "
            "lit in the shadow series)"
        )
    if risk:
        parts.append(
            f"{risk} moves would have pushed the execution failure probability "
            "over max_failure_probability (the chance constraint: every fault "
            "branch is closed with the recovery policy's P_safe)"
        )
    if dwell:
        parts.append(
            f"{dwell} transitions (waits or moves) would have left the rover's inner "
            "temperature outside its battery/electronics envelope (require_thermal_dwell: "
            "the thermal dwell -- the inner temperature relaxes toward each occupied "
            "block's surface-derived target with the rover's thermal_tau_s, and a stay "
            "in a block may not outlast max_dwell_h there; MODEL, uncalibrated)"
        )
    if too_cold:
        parts.append(
            f"{too_cold} hibernations would have taken the battery outside its "
            "survival range -- below the 200 K electrolyte freeze point the cited "
            "measurement reports, or above the declared maximum (allow_hibernate; the "
            "operating envelope is widened for a dormant rover, not removed)"
        )
    if unwakeable:
        parts.append(
            f"{unwakeable} hibernations could not be woken: the dawn pre-heat needs "
            "solar array power and a heater that is not already saturated against the "
            "surface, and in those cells it could not bring the inner temperature back "
            "inside the operating envelope (allow_hibernate; NASA Glenn's dawn mode runs "
            "the pre-heaters on array power alone with the battery isolated)"
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
    if horizon and not (
        lateral or along or blocked or unknown or soc or endurance or dte or haven
        or corridor or risk or dwell or unwakeable or too_cold
    ):
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
    safe_haven_enforced: bool = False,
    continuous_illumination_enforced: bool = False,
    survival_enforced: bool = False,
    start_recovery_prob: float | None = None,
    thermal_dwell_enforced: bool = False,
    hibernation_allowed: bool = False,
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
        "path_earth_visible": None,
        "path_time_to_haven_h": None,
        "path_hours_until_earthset": None,
        "path_haven_margin_h": None,
        "path_survival_prob": None,
        "path_recovery_prob": None,
        # The thermal dwell (C6): None without a dwell cube.
        "path_stay_hours": None,
        "path_max_dwell_h": None,
        "path_dwell_margin_h": None,
        "path_inner_c": None,
        # Hibernation (C2): None without the edge family.
        "path_actions": None,
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
            "moves_out_of_earth_view": None,
            "earth_visibility_enforced": False,
            "min_haven_margin_h": None,
            "states_past_haven_deadline": None,
            "ends_at_safe_haven": None,
            # Whether the rule was in force when the search failed: a caller
            # reading a refusal needs to know which rules produced it.
            "safe_haven_enforced": bool(safe_haven_enforced),
            # The lit corridor (A2): None without a corridor cube.
            "states_outside_corridor": None,
            "moves_outside_corridor": None,
            "continuous_illumination_enforced": bool(continuous_illumination_enforced),
            # The chance constraint (B1): None without a survival field.
            "execution_failure_probability": None,
            "min_recovery_prob": None,
            "start_recovery_prob": start_recovery_prob,
            "survival_enforced": bool(survival_enforced),
            # The thermal dwell (C6): None without a dwell cube.
            "min_dwell_margin_h": None,
            "states_past_thermal_dwell": None,
            "max_stay_h": None,
            "thermal_dwell_enforced": bool(thermal_dwell_enforced),
            # Hibernation (C2): 0/None until an edge family exists.
            "hibernate_steps": 0,
            "hibernate_hours": None,
            "hibernate_dark_hours": None,
            "coldest_inner_c": None,
            "hibernation_beyond_cited_evidence": None,
            "hibernation_allowed": bool(hibernation_allowed),
            "battery_model": "constant",
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
# The execution-survival axis (B1). Under a beta a label whose survival
# product is within one percent of a cheaper label's is pruned (the same
# order as the battery's tolerance; beta is a number like 0.02 or 0.05),
# and the label key bins it in thousandths. Without a beta the axis is
# switched off (infinite tolerance): the plan is the cost-optimal one and
# its risk is REPORTED, so the search expands exactly the nodes it expands
# without a field -- measured on the lunar-night pair, keeping the axis
# live in report-only mode expanded 1.2 M nodes against 171 k and took
# 281 s against 21 s. Without a field every label carries exactly 1.0
# here, so the pre-B1 search is reproduced bit for bit either way.
_SURVIVAL_DOMINANCE_TOL: float = 0.01
_SURVIVAL_BINS: int = 1000
# The thermal axis (C6). Under require_thermal_dwell a label whose inner
# temperature sits within a tenth of the envelope width of a cheaper
# label's margin is pruned, and the key bins the margin in tenths of the
# width. Finer settings (one percent, 400 bins, the battery axis's) let the
# label count explode on Site11's day route -- the inner temperature of two
# paths meeting at one node differs by tens of kelvin when one came through
# sunlight and the other through shadow, so almost nothing was pruned: the
# first real-grid run passed 2.3 GB and ten minutes without finishing; at
# five percent and 20 bins the infeasible day route took 156 s to refuse.
# The CONSTRAINT is still checked on the exact value; only the pruning is
# coarse, so a warmer route within 3.5 K of a cheaper colder one may be
# dropped. Without the constraint the tolerance is infinite and the key
# constant: the pre-C6 search bit for bit.
_THERMAL_MARGIN_TOL_FRAC: float = 0.10
_THERMAL_MARGIN_BINS: int = 10


def _dominated(
    front: list[tuple[float, float, float, float, float]],
    g: float,
    battery: float,
    dark: float,
    battery_tol: float,
    dark_tol: float,
    strict: bool = False,
    surv: float = 1.0,
    surv_tol: float = _SURVIVAL_DOMINANCE_TOL,
    margin: float = 0.0,
    margin_tol: float = math.inf,
) -> bool:
    """True if some label in *front* is at least as good on every axis.

    A label is (cost so far, battery Wh, continuous shadow hours, execution
    survival, thermal margin -- the inner temperature's distance to the
    nearer envelope bound). Lower cost, more battery, less shadow, more
    survival and more thermal margin all dominate, each within its
    tolerance. With *strict* the label must be beaten on at least one axis
    beyond the tolerance, which is how a label already in the front is told
    apart from a genuine dominator at pop time. The thermal axis (C6) is
    live only under require_thermal_dwell: its default tolerance is
    infinite, so without the constraint every comparison here is the pre-C6
    one.
    """
    for other_g, other_battery, other_dark, other_surv, other_margin in front:
        if (
            other_g <= g + 1e-12
            and other_battery >= battery - battery_tol
            and other_dark <= dark + dark_tol
            and other_surv >= surv - surv_tol
            and other_margin >= margin - margin_tol
        ):
            if not strict:
                return True
            if (
                other_g < g - 1e-12
                or other_battery > battery + battery_tol
                or other_dark < dark - dark_tol
                or other_surv > surv + surv_tol
                or other_margin > margin + margin_tol
            ):
                return True
    return False


def _insert_label(
    front: list[tuple[float, float, float, float, float]],
    g: float,
    battery: float,
    dark: float,
    battery_tol: float,
    dark_tol: float,
    surv: float = 1.0,
    surv_tol: float = _SURVIVAL_DOMINANCE_TOL,
    margin: float = 0.0,
    margin_tol: float = math.inf,
) -> None:
    """Add a non-dominated label and drop the ones it dominates."""
    front[:] = [
        (other_g, other_battery, other_dark, other_surv, other_margin)
        for other_g, other_battery, other_dark, other_surv, other_margin in front
        if not (
            g <= other_g + 1e-12
            and battery >= other_battery - battery_tol
            and dark <= other_dark + dark_tol
            and surv >= other_surv - surv_tol
            and margin >= other_margin - margin_tol
        )
    ]
    front.append((g, battery, dark, surv, margin))


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
    earth_visible_cube: np.ndarray | None = None,
    require_earth_visibility: bool = False,
    time_to_haven_hours: np.ndarray | None = None,
    hours_until_earthset_cube: np.ndarray | None = None,
    require_safe_haven: bool = False,
    corridor_cube: np.ndarray | None = None,
    corridor_lit_run_cube: np.ndarray | None = None,
    require_continuous_illumination: bool = False,
    survival_field: Any | None = None,
    max_failure_probability: float | None = None,
    max_dwell_cube: Any | None = None,
    require_thermal_dwell: bool = False,
    solar_gain_series: Any | None = None,
    heater_w_cube: np.ndarray | None = None,
    surface_cube: np.ndarray | None = None,
    battery_model: str = "constant",
    allow_hibernate: bool = False,
    shape_exponent: float = 1.0,
    weights: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Plan through space and time. Returns path_states, path_pixels, metrics.

    The panel gain (C1)
    -------------------
    *solar_gain_series* is the per-slice cos i gain (:mod:`app.panel`), one
    scalar per slice, which scales the solar income in the battery
    integration below exactly as it scales it in the cost cube the caller
    built with the same array. ``None`` -- the default -- is the pre-C1
    model, an array permanently face-on to the Sun, and the search is then
    bit-identical: same path, same ``nodes_expanded``, same ``total_cost``.

    A move can span several slices. Its solar income is the trapezoid of the
    two endpoint SLICE INCOMES -- ``0.5 * [(1 - e_dep) g_dep + (1 - e_arr)
    g_arr]`` -- which is what the cost cube charged for the same edge, since
    the cube prices each slice with that slice's own gain. It is NOT the mean
    exposure times the mean gain: the solar term is bilinear in (exposure,
    gain) once the gain varies, and those two differ by up to a factor of two
    on an edge that crosses the terminator. Housekeeping still follows the
    mean exposure, as before. A wait uses its own slice's gain.

    The battery in the cold, and hibernation (C2)
    ---------------------------------------------
    Three switches, each of which is the pre-C2 model when it is off, and all
    three of which are off by default. With all three off this function is
    bit-identical to before: same path, same ``nodes_expanded``, same
    ``total_cost``.

    *battery_model* ``"temperature_derated"`` reads the battery's charge as
    DELIVERABLE charge (:func:`app.battery.usable_fraction`) rather than
    nameplate charge, in exactly two places: the reserve floor and the
    continuous-darkness endurance, which becomes
    :func:`app.battery.shadow_endurance_h` -- the published
    ``h_max_shadow_h`` scaled by the fraction of the deliverable charge above
    the reserve this state still has. At full charge and at the rating
    temperature that ratio is exactly 1.0 for every profile in the catalogue,
    so the published constant is reproduced exactly rather than approximately.

    It also turns INNER-TEMPERATURE TRACKING on without turning the C6
    envelope CONSTRAINT on. That separation matters more than it looks:
    before C2 the inner temperature was integrated only under
    ``require_thermal_dwell``, and the sentinel it carried otherwise was
    ``0.0`` -- numerically identical to LPR-1's and VIPER's rating
    temperature, so a derating read at the sentinel would have returned 1.0
    everywhere, produced no error, and looked exactly like a model that had
    run. The derating therefore requires a dwell cube and refuses without one.
    Note the honest consequence: WITH ``require_thermal_dwell`` on, LPR-1 and
    VIPER are held inside [0, 35] C, so their deliverable fraction is
    identically 1.0 and the derating changes nothing. It bites precisely
    where the envelope is not enforced -- and in hibernation.

    *heater_w_cube* is a ``(T, H, W)`` survival-heater power derived from the
    same per-slice surface the cost cube was built from
    (:func:`app.battery.heater_power_w_grid`). It replaces the exposure-scaled
    heater term in the battery integration below, in the same place the cube
    replaced it in the objective -- both or neither, or the planner would
    prefer waits whose drain it does not actually pay.

    *allow_hibernate* adds a third edge family. It is ATOMIC: one edge from
    ``(r, c, t)`` to ``(r, c, t + d)`` covering entry, dormancy and the dawn
    pre-heat at one price, so no sixth label axis is needed and the label
    algebra is untouched. Four rules, three of them straight out of NASA
    Glenn's description of the mode:

    * it may only be ENTERED from a dark slice. Priced on the objective alone,
      dormancy is cheaper than waiting for two of the four profiles, and
      without this gate the planner fills its plans with naps in the sunshine
      and throws away the solar income it is no longer charged for.
    * it may only be LEFT into an illuminated slice. "Solar Array output
      triggers a 'Dawn Mode' within the Main Bus Controller"; the pre-heaters
      run "on Solar Array power alone (Battery still Isolated)". A rover
      cannot wake in the dark -- which is also what closes the loophole a
      hibernation would otherwise open, since a rover that could sleep and
      wake in darkness could reset its shadow clock indefinitely.
    * the dark clock does NOT stop; it runs at
      ``p_hibernate_w / p_shadow_w``. Freezing it would make
      ``metrics.max_continuous_shadow_h`` stop meaning continuous darkness and
      let D3's LP-R01 pass on a number nobody measured -- on this catalogue a
      frozen clock turns Yutu-2's 2 h endurance into 210 h.
    * the thermal envelope is not SUSPENDED, it is REPLACED by the survival
      envelope (:func:`app.battery.survival_envelope`), whose cold bound is
      the cited 200 K freeze point rather than the operating minimum, and it
      is checked over the whole dormancy rather than only at its end.
      Suspending it would reopen, in a new costume, the loophole C6 closed by
      constraining the temperature instead of the stay.

    A hibernation whose pre-heat cannot be completed is refused and TALLIED as
    ``hibernate_unwakeable``, never dropped as a silent ``inf`` or ``NaN``.

    The thermal dwell (C6)
    ----------------------
    *max_dwell_cube* is a ``thermal_dwell.DwellCube``: for every (start
    slice, block) the hours a rover arriving there with its nominal inner
    temperature may stand still before that temperature leaves the tightest
    declared battery/electronics envelope, plus the per-slice inner
    temperature TARGET the cube was built from. Given, the route is always
    REPORTED -- ``path_stay_hours`` (consecutive stationary hours in the
    current block), ``path_max_dwell_h`` (the block's budget at the slice
    the stay began; None where open-ended), ``path_dwell_margin_h``,
    ``path_inner_c`` (the inner temperature integrated along the route),
    and ``metrics.min_dwell_margin_h`` / ``states_past_thermal_dwell`` /
    ``max_stay_h`` -- computed from the finished route, so the search itself
    is untouched. With *require_thermal_dwell* it is ENFORCED: every label
    carries its inner temperature, relaxed toward the occupied block's
    target slice by slice (a wait: the block waited in; a move: the arrival
    block, the planner's shadow-clock rule), and any transition -- wait or
    move -- after which it would sit outside the envelope is refused
    (tallied as ``thermal_dwell``). A stay longer than the block's dwell is
    exactly such a wait; enforcing the temperature rather than the stay
    also closes the loophole a stay rule leaves open, where a rover
    shuffles between two dark blocks to reset its clock while freezing all
    the same (found by the first version of this constraint's test). The
    fifth label axis is the thermal margin (distance to the nearer bound,
    more is better); without the constraint it has an infinite dominance
    tolerance and a constant key, so the search is the pre-C6 one bit for
    bit.

    The chance constraint (B1)
    --------------------------
    *survival_field* is a ``survival.SurvivalField``: ``P_safe`` and the
    recovery policy over (time bin, block, SOC bin) under a Poisson fault
    model. Given, every label carries an EXECUTION SURVIVAL product: at
    each MOVE the no-fault branch continues on the plan and each fault
    branch is closed with ``P_safe`` of the state the fault leaves the
    rover in (Lamarre et al., AERO 2024), so ``1 - product`` at the goal is
    the probability that this plan, executed with the recovery policy as
    its fallback, ends in failure. Always REPORTED -- ``path_survival_prob``
    and ``path_recovery_prob`` per state, ``metrics.execution_failure_probability``,
    ``min_recovery_prob``, ``start_recovery_prob`` -- and with
    *max_failure_probability* ENFORCED: a move that would push the
    execution failure probability over it is refused (tallied as
    ``failure_probability``), and a start whose optimal recovery policy
    already fails more often than that is refused at once, since no plan
    from it can do better. Without a field the fourth label axis is a
    constant and the search is the pre-B1 one bit for bit.

    The continuous-illumination corridor (A2)
    -----------------------------------------
    *corridor_cube* is the (T, H, W) boolean corridor
    ``illumination_corridor.build_corridor`` prunes from the shadow series
    (CMU's sun-synchronous volume: every voxel on some lit path from the
    first slice to the last); *corridor_lit_run_cube* the (T, H, W) count of
    consecutive lit slices ending at each voxel, on the lit volume the
    corridor was cut from. Given together they are always REPORTED --
    ``metrics.states_outside_corridor``, ``metrics.moves_outside_corridor``
    -- and with *require_continuous_illumination* ENFORCED: the start must
    be inside at slice 0, a WAIT may only step into a corridor voxel, and a
    MOVE of ``d`` slices may only arrive in a corridor voxel with both its
    blocks lit for the ``d + 1`` slices from departure to arrival. Inside
    the corridor the shadow clock never starts, so ``path_dark_hours`` is
    zero throughout. Refusals are tallied as ``continuous_illumination``.

    The safe-haven deadline (A1)
    ----------------------------
    *time_to_haven_hours* is the (H, W) driving time from every cell to its
    nearest safe haven (``safe_haven.time_to_safe_haven_hours``);
    *hours_until_earthset_cube* the (T, H, W) hours each cell has left
    before it loses its Earth link (``safe_haven.hours_until_earthset_cube``,
    zero where there is no link now). Given together they are always
    REPORTED per state -- ``path_time_to_haven_h``,
    ``path_hours_until_earthset``, ``path_haven_margin_h`` -- and with
    *require_safe_haven* ENFORCED as VIPER's leg rule: every state the plan
    passes through, including the start and every wait, must satisfy
    ``time_to_haven <= hours_until_earthset``. Where the Earth is already
    down the deadline is zero, so only a haven itself is allowed: a rover
    without a link is a parked rover. Refusals are tallied as
    ``safe_haven_deadline``.

    Direct-to-Earth visibility (A4)
    -------------------------------
    *earth_visible_cube*, when supplied, is the (T, H, W) boolean field of
    which cells have a line of sight to Earth at which slice. It is always
    REPORTED: ``path_earth_visible`` per state and
    ``metrics.moves_out_of_earth_view``. With *require_earth_visibility* it
    is also ENFORCED, as VIPER's teleoperation rule: a MOVE may only arrive
    in a cell that sees the Earth at the arrival slice. Waiting is never
    restricted -- the rule is about driving blind, not about parking -- so
    a rover that starts out of view may sit until the link opens. Refusals
    are tallied as ``earth_visibility``.

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
    earth = (
        None if earth_visible_cube is None else np.asarray(earth_visible_cube, dtype=bool)
    )
    if earth is not None and earth.shape != cost.shape:
        return _empty("earth_visible_cube shape must match cost_cube")
    enforce_dte = bool(require_earth_visibility)
    if enforce_dte and earth is None:
        return _empty(
            "earth_visible_cube is required to enforce Earth visibility "
            "(require_earth_visibility=True without a field to check against)"
        )
    tts = (
        None
        if time_to_haven_hours is None
        else np.asarray(time_to_haven_hours, dtype=np.float64)
    )
    deadline = (
        None
        if hours_until_earthset_cube is None
        else np.asarray(hours_until_earthset_cube, dtype=np.float64)
    )
    if (tts is None) != (deadline is None):
        return _empty(
            "time_to_haven_hours and hours_until_earthset_cube go together: "
            "give both or neither"
        )
    if tts is not None and tts.shape != (height, width):
        return _empty("time_to_haven_hours shape must match cost_cube slices")
    if deadline is not None and deadline.shape != cost.shape:
        return _empty("hours_until_earthset_cube shape must match cost_cube")
    corridor = None if corridor_cube is None else np.asarray(corridor_cube, dtype=bool)
    lit_run = (
        None if corridor_lit_run_cube is None else np.asarray(corridor_lit_run_cube)
    )
    if (corridor is None) != (lit_run is None):
        return _empty(
            "corridor_cube and corridor_lit_run_cube go together: give both or "
            "neither"
        )
    if corridor is not None and corridor.shape != cost.shape:
        return _empty("corridor_cube shape must match cost_cube")
    if lit_run is not None and lit_run.shape != cost.shape:
        return _empty("corridor_lit_run_cube shape must match cost_cube")
    enforce_corridor = bool(require_continuous_illumination)
    if enforce_corridor and corridor is None:
        return _empty(
            "corridor_cube and corridor_lit_run_cube are required to enforce "
            "continuous illumination (require_continuous_illumination=True "
            "without a corridor to check against)"
        )
    field = survival_field
    beta = None if max_failure_probability is None else float(max_failure_probability)
    enforce_surv = beta is not None
    if enforce_surv and field is None:
        return _empty(
            "survival_field is required to enforce max_failure_probability "
            f"({beta}): the chance constraint closes every fault branch with "
            "the recovery policy's P_safe and has nothing to read without one",
            survival_enforced=True,
        )
    if enforce_surv and not (0.0 < beta < 1.0):
        return _empty(
            f"max_failure_probability must lie strictly between 0 and 1, not {beta}",
            survival_enforced=True,
        )
    dwell_cube = max_dwell_cube
    enforce_dwell = bool(require_thermal_dwell)
    if enforce_dwell and dwell_cube is None:
        return _empty(
            "max_dwell_cube is required to enforce the thermal dwell "
            "(require_thermal_dwell=True without a cube to check against: the rover "
            "declares no thermal_tau_s, or no dwell cube was built)",
            thermal_dwell_enforced=True,
        )
    # ── C2: the battery in the cold, and hibernation ─────────────────────
    if battery_model not in battery_model_module.BATTERY_MODELS:
        return _empty(
            f"unknown battery_model {battery_model!r}; expected one of "
            f"{battery_model_module.BATTERY_MODELS}"
        )
    derate = battery_model == "temperature_derated"
    if derate and dwell_cube is None:
        return _empty(
            "battery_model='temperature_derated' needs a thermal dwell cube: the "
            "deliverable fraction is a function of the INNER TEMPERATURE, and without "
            "a cube to integrate it the planner has no temperature to read. It would "
            "otherwise read the no-thermal-state sentinel 0.0, which is numerically "
            "identical to LPR-1's and VIPER's rating temperature and would return a "
            "fraction of exactly 1.0 everywhere -- a derating that looks like it ran "
            "and measured nothing"
        )
    if derate:
        fraction_reason = battery_model_module.usable_fraction_unavailable_reason(rover)
        if fraction_reason is not None:
            return _empty(
                "battery_model='temperature_derated' is unavailable for "
                f"{rover.get('name', rover.get('id', 'this rover'))}: {fraction_reason}"
            )
    hibernate_enabled = bool(allow_hibernate)
    # Inner-temperature TRACKING is not the same switch as the envelope
    # CONSTRAINT: the derating needs a temperature without needing the rover
    # held inside its envelope, and hibernation deliberately leaves it. All
    # three switches need a temperature; only require_thermal_dwell refuses on
    # it. Without tracking, a label carries the sentinel 0.0 -- so a rover that
    # waited in the dark and then hibernated would begin its dormancy from a
    # temperature it never had.
    track_inner = enforce_dwell or derate or hibernate_enabled

    hibernate_rate = 1.0
    survival_env = None
    if hibernate_enabled:
        available, hibernate_reason = battery_model_module.hibernation_available(rover)
        if not available:
            return _empty(
                "allow_hibernate=True is unavailable for "
                f"{rover.get('name', rover.get('id', 'this rover'))}: {hibernate_reason}",
                hibernation_allowed=True,
            )
        if dwell_cube is None or surface_cube is None or shadow is None:
            return _empty(
                "allow_hibernate=True needs a thermal dwell cube, a surface-temperature "
                "cube and a shadow cube: a dormant rover's inner temperature has to be "
                "integrated against the block it sleeps in, its dawn pre-heat timed "
                "against the surface it warms from, and its waking slice found in the "
                "illumination series",
                hibernation_allowed=True,
            )
        if weights is None:
            return _empty(
                "allow_hibernate=True needs the same weights the cost cubes were built "
                "with: a HIBERNATE edge is priced on the same objective as a WAIT edge "
                "(cost_cube.hibernate_cost), and pricing it on a different weight vector "
                "than the cubes would put two objectives in one search",
                hibernation_allowed=True,
            )
        hibernate_rate = battery_model_module.hibernate_dark_rate(rover)
        survival_env = battery_model_module.survival_envelope(rover)
        if survival_env is None:
            return _empty(
                "allow_hibernate=True needs a declared thermal envelope to widen into a "
                "survival envelope",
                hibernation_allowed=True,
            )
        # The first slice AFTER t at which this block is mostly lit -- where a
        # dormant rover could wake, because NASA Glenn's dawn mode is triggered
        # by array output and runs the pre-heaters on array power alone. One
        # reverse scan, so the edge below is O(1) in finding its dawn.
        next_lit = np.full(cost.shape, -1, dtype=np.int32)
        _running = np.full((height, width), -1, dtype=np.int32)
        for _t in range(n_slices - 1, -1, -1):
            next_lit[_t] = _running
            _running = np.where(shadow[_t] < _DARK_RATIO_THRESHOLD, _t, _running)

    heaters = None
    if heater_w_cube is not None:
        heaters = np.asarray(heater_w_cube, dtype=np.float64)
        if heaters.shape != cost.shape:
            return _empty(
                f"heater_w_cube {heaters.shape} must match the cost cube {cost.shape}"
            )
    surfaces = None
    if surface_cube is not None:
        surfaces = np.asarray(surface_cube, dtype=np.float64)
        if surfaces.shape != cost.shape:
            return _empty(
                f"surface_cube {surfaces.shape} must match the cost cube {cost.shape}"
            )

    haven_fields = tts is not None
    enforce_haven = bool(require_safe_haven)
    if enforce_haven and not haven_fields:
        return _empty(
            "time_to_haven_hours and hours_until_earthset_cube are required to "
            "enforce the safe-haven rule (require_safe_haven=True without the "
            "fields to check against)"
        )

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

    def haven_ok(r: int, c: int, t: int) -> bool:
        return bool(tts[r, c] <= deadline[t, r, c] + 1e-9)

    if enforce_haven and not haven_ok(start[0], start[1], 0):
        start_tts = float(tts[start])
        start_deadline = float(deadline[0][start])
        if start_deadline <= 0.0:
            return _empty(
                f"Start {start} has no Earth link at the first slice and is not "
                "a safe haven: under the safe-haven rule the rover must already "
                "be parked at a haven while the Earth is down"
            )
        return _empty(
            f"Start {start} cannot reach a safe haven before the Earth sets: "
            f"{start_tts:.2f} h to the nearest haven against "
            f"{start_deadline:.2f} h of link left"
        )

    if enforce_corridor and not corridor[0][start]:
        return _empty(
            f"Start {start} is not inside the continuous-illumination corridor "
            "at the first slice: under require_continuous_illumination the "
            "rover must begin in a block that is lit and can stay lit",
            continuous_illumination_enforced=True,
        )

    e_cap_wh = float(rover["e_cap_wh"])
    battery0 = min(1.0, max(0.0, float(initial_soc_frac))) * e_cap_wh
    start_recovery = (
        None if field is None else float(field.p_safe_at(0, start[0], start[1], battery0))
    )
    if enforce_surv and 1.0 - start_recovery > beta + 1e-12:
        return _empty(
            f"Start {start} cannot satisfy max_failure_probability={beta}: even the "
            "optimal recovery policy from there fails with probability "
            f"{1.0 - start_recovery:.4f} (P_safe {start_recovery:.4f} at "
            f"{100.0 * battery0 / e_cap_wh if e_cap_wh > 0 else 0.0:.0f} percent charge), "
            "and no plan can do better than the optimal policy",
            survival_enforced=True,
            start_recovery_prob=start_recovery,
        )

    # The goal's own deadline bounds the whole search. Arrival time only
    # ever grows, so once the goal can no longer satisfy the rule nothing
    # later can end there, and without this bound a goal that never
    # qualifies (its link already down, and it is not a haven) sent the
    # label-setting search through every reachable state at every slice --
    # measured on the production grid at 256 slices: not finished in ten
    # minutes, against 8.6 s for the same pair unconstrained.
    goal_last_ok = -1
    if enforce_haven:
        goal_ok = tts[goal] <= deadline[:, goal[0], goal[1]] + 1e-9
        if not bool(goal_ok.any()):
            goal_tts = float(tts[goal])
            goal_link = float(np.max(deadline[:, goal[0], goal[1]]))
            return _empty(
                f"Goal {goal} can never satisfy the safe haven rule within the "
                "horizon: "
                + ("no haven is reachable from it" if not math.isfinite(goal_tts)
                   else f"{goal_tts:.2f} h to the nearest haven")
                + " against at most "
                + ("no Earth link at all" if goal_link <= 0.0
                   else f"{goal_link:.2f} h of Earth link")
                + " at the goal (require_safe_haven)",
                safe_haven_enforced=True,
            )
        goal_last_ok = int(np.flatnonzero(goal_ok)[-1])

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
    reserve_wh = e_cap_wh * float(rover.get("soc_min_pct") or 0.0)
    h_max_shadow = float(rover["h_max_shadow_h"])
    track = shadow is not None
    surv_tol = _SURVIVAL_DOMINANCE_TOL if enforce_surv else math.inf
    # The thermal axis (C6): live only under the dwell constraint, where two
    # labels at one node with different inner temperatures genuinely differ
    # in what they may still do. Tolerance one percent of the envelope width
    # (the battery axis's order), key in 400 bins of it.
    if track_inner:
        # C2: the fifth axis is live whenever a temperature is tracked, not only
        # when the envelope is enforced. Two labels at one node whose batteries
        # deliver different amounts genuinely differ in what they may still do,
        # so the derating needs the same separation the dwell constraint needs.
        env_width = max(1e-9, float(dwell_cube.envelope.hi) - float(dwell_cube.envelope.lo))
        margin_tol = _THERMAL_MARGIN_TOL_FRAC * env_width
        inner0 = float(dwell_cube.initial_inner_c)
        if enforce_dwell and not dwell_cube.inside(inner0):
            return _empty(
                f"Start inner temperature {inner0:.2f} C is already outside the "
                f"[{dwell_cube.envelope.lo:g}, {dwell_cube.envelope.hi:g}] C envelope: under "
                "require_thermal_dwell no transition can begin from outside it",
                thermal_dwell_enforced=True,
            )
    else:
        env_width = 1.0
        margin_tol = math.inf
        inner0 = 0.0
    # The move factor depends on the label only through its battery, and
    # labels at one node differ by less than the key's resolution; memoised
    # at that resolution (a quarter percent of capacity) so the fault
    # branches are priced once per (slice, cell, direction, charge bin).
    factor_cache: dict[tuple[int, int, int, int, int], float] = {}

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
    # C2: the dormant draw, and the objective the hibernate edge is priced on
    # -- the same weight vector the cubes were built with, so the third edge
    # family competes with the other two on one objective.
    p_hibernate_w = float(rover["p_hibernate_w"]) if hibernate_enabled else 0.0
    hibernate_weights = dict(weights) if hibernate_enabled and weights is not None else None

    # C1: the panel gain per slice. Absent, every slice gains 1.0 and the
    # arithmetic below is the pre-C1 one, term for term.
    if solar_gain_series is None:
        gain_of = None
    else:
        _gains = np.asarray(solar_gain_series, dtype=np.float64).reshape(-1)
        if _gains.size < n_slices:
            return _empty(
                f"solar_gain_series has {_gains.size} entries for {n_slices} slices"
            )

        def gain_of(index: int) -> float:
            return float(_gains[index])

    def solar_w_at(index: int, exposure: float) -> float:
        """Solar power the array collects at *index* under *exposure* shadow."""
        lit = p_solar_w * (1.0 - exposure)
        return lit if gain_of is None else lit * gain_of(index)

    def housekeeping_w(ratio: float, index: int = -1, r: int = -1, c: int = -1) -> float:
        # C2: with a heater cube the heater's power comes from the cell's own
        # TEMPERATURE at this slice, exactly as it does in the cost cube the
        # caller built from the same array. Both or neither: if the objective
        # priced one heater and the battery integration paid another, the
        # planner would prefer waits whose drain it does not actually pay, and
        # no test would go red because the two agree with the cube absent.
        # == cost_engine.housekeeping_power_w(ratio, rover, heater_w)
        if heaters is None or index < 0:
            return p_idle_w + ratio * shadow_extra_w
        return p_idle_w + max(0.0, float(heaters[index, r, c]))

    def battery_key(battery_wh: float) -> int:
        if e_cap_wh <= 0.0:
            return 0
        return int(battery_wh / e_cap_wh * _BATTERY_BINS_PER_CAPACITY)

    def dark_key(dark_h: float) -> int:
        return int(dark_h / dark_quantum_h)

    def surv_key(surv: float) -> int:
        # Part of the label key only under a beta; in report-only mode the
        # key is the pre-B1 one and the cheapest label's product is reported.
        return int(surv * _SURVIVAL_BINS) if enforce_surv else 0

    def thermal_margin(inner_c: float) -> float:
        # Distance to the nearer envelope bound; a constant when no temperature
        # is tracked, so the fifth axis never separates labels then. (C6, C2.)
        return dwell_cube.margin_c(inner_c) if track_inner else 0.0

    def inner_key(inner_c: float) -> int:
        # Part of the label key only while a temperature is tracked (C6, C2).
        return int(thermal_margin(inner_c) / env_width * _THERMAL_MARGIN_BINS) if track_inner else 0

    def label_of(
        r: int, c: int, t: int, battery_wh: float, dark_h: float, surv: float = 1.0, inner_c: float = 0.0
    ):
        return (r, c, t, battery_key(battery_wh), dark_key(dark_h), surv_key(surv), inner_key(inner_c))

    def deliverable_of(battery_wh: float, inner_c: float) -> float:
        # C2: stored charge read as DELIVERABLE charge. The reserve is a
        # deliverable-energy floor -- 'the energy kept for survival heating' --
        # so in the cold the STORED charge needed to meet it goes up. One hedge
        # against cold, applied once: the charge ceiling and the dominance bin
        # stay nominal, and app.battery.deliverable_wh says so.
        if not derate:
            return battery_wh
        return battery_model_module.deliverable_wh(
            battery_wh, inner_c, rover, shape_exponent
        )

    def endurance_of(battery_wh: float, inner_c: float) -> float:
        # C2: the published endurance scaled by what this state can still
        # deliver above the reserve. Only the THRESHOLD is state-dependent --
        # dark_quantum_h, dark_tol and endurance_finite above stay derived from
        # the published constant, because they are the dominance axis's
        # resolution rather than a constraint, and this file's own rule is that
        # the constraints are checked on the exact values.
        if not derate:
            return h_max_shadow
        return battery_model_module.shadow_endurance_h(
            battery_wh, inner_c, rover, shape_exponent
        )

    def envelope_after(
        exposure: float,
        hours: float,
        battery_wh: float,
        dark_h: float,
        drain_wh: float,
        inner_c: float = 0.0,
        dark_rate: float = 1.0,
    ) -> tuple[float, float, str | None]:
        """Battery and shadow hours after a transition, or the refusal key.

        *exposure* is the shadow ratio the rover is exposed to across the
        transition (the slice waited through, or the arrival cell for a
        move); *drain_wh* the signed battery change it costs.

        *inner_c* (C2) is the inner temperature the transition ends at, read
        only under ``battery_model='temperature_derated'``; *dark_rate* the
        rate at which this transition spends the continuous-darkness budget,
        which is 1.0 for every edge except a hibernation.
        """
        new_battery = min(e_cap_wh, battery_wh - drain_wh)
        # Below the reserve is refused -- unless the transition CHARGES, so
        # a rover parked under its reserve in sunlight is allowed to recover.
        if derate:
            if deliverable_of(new_battery, inner_c) < reserve_wh and new_battery < battery_wh:
                return battery_wh, dark_h, "soc_floor"
        elif new_battery < reserve_wh and new_battery < battery_wh:
            return battery_wh, dark_h, "soc_floor"
        if exposure >= _DARK_RATIO_THRESHOLD:
            if dark_rate == 1.0:
                new_dark = dark_h + hours * exposure
            else:
                new_dark = dark_h + hours * exposure * dark_rate
        else:
            new_dark = 0.0
        if new_dark > endurance_of(new_battery, inner_c) + 1e-9:
            return battery_wh, dark_h, "shadow_endurance"
        return new_battery, new_dark, None

    # -- Label-setting A* ---------------------------------------------------
    start_label = label_of(start[0], start[1], 0, battery0, 0.0, 1.0, inner0)
    g_score: dict[tuple, float] = {start_label: 0.0}
    battery_of: dict[tuple, float] = {start_label: battery0}
    dark_of: dict[tuple, float] = {start_label: 0.0}
    surv_of: dict[tuple, float] = {start_label: 1.0}
    inner_of: dict[tuple, float] = {start_label: inner0}
    came_from: dict[tuple, tuple] = {}
    # C2: which edge family reached each label, so a hibernation is never
    # mistaken for a wait by the geometric test (both hold position), and
    # (hours, dark hours charged, the darkness clock's PEAK during the
    # dormancy, coldest inner) for the hibernations.
    action_of: dict[tuple, str] = {}
    hibernation_of: dict[tuple, tuple[float, float, float, float]] = {}
    fronts: dict[tuple[int, int, int], list[tuple[float, float, float, float, float]]] = {
        (start[0], start[1], 0): [(0.0, battery0, 0.0, 1.0, thermal_margin(inner0))]
    }
    closed: set[tuple] = set()
    counter = 0
    heap: list[tuple[float, float, int, tuple]] = [
        (heuristic(*start), 0.0, counter, start_label)
    ]
    nodes_expanded = 0
    goal_label: tuple | None = None

    def push(
        r: int, c: int, t: int, g_new: float, battery_wh: float, dark_h: float, parent: tuple,
        surv: float = 1.0, inner_c: float = 0.0, action: str = "move",
        hibernation: tuple[float, float, float, float] | None = None,
    ) -> None:
        nonlocal counter
        node = (r, c, t)
        front = fronts.setdefault(node, [])
        margin = thermal_margin(inner_c)
        if _dominated(
            front, g_new, battery_wh, dark_h, battery_tol, dark_tol,
            surv=surv, surv_tol=surv_tol, margin=margin, margin_tol=margin_tol,
        ):
            return
        _insert_label(
            front, g_new, battery_wh, dark_h, battery_tol, dark_tol,
            surv=surv, surv_tol=surv_tol, margin=margin, margin_tol=margin_tol,
        )
        label = label_of(r, c, t, battery_wh, dark_h, surv, inner_c)
        if g_new < g_score.get(label, math.inf):
            g_score[label] = g_new
            battery_of[label] = battery_wh
            dark_of[label] = dark_h
            surv_of[label] = surv
            inner_of[label] = inner_c
            came_from[label] = parent
            action_of[label] = action
            if hibernation is not None:
                hibernation_of[label] = hibernation
            counter += 1
            h = heuristic(r, c)
            heapq.heappush(heap, (g_new + h, h, counter, label))

    while heap:
        _f, _h, _n, label = heapq.heappop(heap)
        if label in closed:
            continue
        row, col, slice_index, _bkey, _dkey, _skey, _ykey = label
        current_g = g_score[label]
        battery_wh = battery_of[label]
        dark_h = dark_of[label]
        surv = surv_of[label]
        inner_c = inner_of[label]
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
            surv=surv,
            surv_tol=surv_tol,
            margin=thermal_margin(inner_c),
            margin_tol=margin_tol,
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
                # The inner temperature after one more slice in this block. It is
                # needed BEFORE the envelope test now, because C2's reserve floor
                # and endurance are read at the temperature the transition ends
                # at; without tracking it is the label's own value and no lag is
                # integrated, exactly as before. (C6, C2.)
                new_inner = (
                    dwell_cube.inner_after(inner_c, slice_index, slice_index + 1, row, col)
                    if track_inner else inner_c
                )
                if track:
                    exposure = float(shadow[slice_index, row, col])
                    # == wait_battery_drain_wh(exposure, slice_hours, rover,
                    #                           solar_gain=gain[slice_index],
                    #                           heater_w=heaters[slice_index, row, col])
                    drain_wh = (
                        housekeeping_w(exposure, slice_index, row, col)
                        - solar_w_at(slice_index, exposure)
                    ) * slice_hours
                    new_battery, new_dark, refused = envelope_after(
                        exposure, slice_hours, battery_wh, dark_h, drain_wh, new_inner
                    )
                else:
                    new_battery, new_dark, refused = battery_wh, dark_h, None
                if refused is not None:
                    rejections[refused] += 1
                elif enforce_haven and (
                    slice_index + 1 > goal_last_ok
                    or not haven_ok(row, col, slice_index + 1)
                ):
                    # Waiting past the deadline is how a rover ends up parked
                    # somewhere it cannot survive; the rule binds waits too.
                    # And past the goal's last admissible slice no wait can
                    # lead to a plan that ends there.
                    rejections["safe_haven_deadline"] += 1
                elif enforce_corridor and not corridor[slice_index + 1, row, col]:
                    # Waiting into a dark voxel is leaving the corridor. (A2.)
                    rejections["continuous_illumination"] += 1
                else:
                    # A wait that leaves the envelope is refused -- which is
                    # exactly a stay past the block's dwell. (C6.)
                    if enforce_dwell and not dwell_cube.inside(new_inner):
                        rejections["thermal_dwell"] += 1
                    else:
                        # No fault on a wait: the survival product is unchanged.
                        push(
                            row, col, slice_index + 1,
                            current_g + wait_step, new_battery, new_dark, label, surv, new_inner,
                            action="wait",
                        )

        # HIBERNATE edge (C2): shut down here, sleep through the dark, and wake
        # at first light after a dawn pre-heat. ONE atomic edge covering entry,
        # dormancy and pre-heat, so no sixth label axis is needed and the label
        # algebra the other two families share is untouched.
        if hibernate_enabled and track and slice_index + 1 < n_slices:
            exposure_now = float(shadow[slice_index, row, col])
            dawn = int(next_lit[slice_index, row, col])
            # Entered only from darkness. Priced on the objective alone,
            # dormancy is cheaper than waiting for two of this catalogue's four
            # profiles (VIPER 100 W against 130 W, Yutu-2 5 W against 60 W), so
            # an ungated edge fills plans with naps in the sunshine and throws
            # away solar income the objective no longer charges for. Left only
            # into light, because NASA Glenn's dawn mode is triggered by array
            # output -- which is also what stops a rover resetting its shadow
            # clock by sleeping and waking in the dark.
            if exposure_now >= _DARK_RATIO_THRESHOLD and dawn > slice_index:
                dormancy_h = (dawn - slice_index) * slice_hours
                dormant_drain_wh = p_hibernate_w * dormancy_h
                dormant_inner = dwell_cube.inner_after(
                    inner_c, slice_index, dawn, row, col
                )
                # A first-order lag toward a sequence of targets never leaves the
                # interval spanned by its start and those targets, so the two
                # extremes bound EVERY intermediate slice. That is what lets the
                # survival envelope be checked across the whole dormancy without
                # walking it -- and checking the whole dormancy, rather than only
                # its end, is what keeps this from reopening the loophole C6
                # closed by constraining the temperature instead of the stay.
                last_target = dwell_cube.target_c.shape[0] - 1
                window = dwell_cube.target_c[
                    min(slice_index + 1, last_target): min(dawn, last_target) + 1, row, col
                ]
                if window.size:
                    coldest_c = min(inner_c, float(np.min(window)))
                    hottest_c = max(inner_c, float(np.max(window)))
                else:
                    coldest_c = hottest_c = inner_c
                if (
                    coldest_c < survival_env.lo - 1e-9
                    or hottest_c > survival_env.hi + 1e-9
                ):
                    # Wider than the operating envelope -- its cold bound is the
                    # cited 200 K freeze point -- but not unbounded.
                    rejections["hibernate_too_cold"] += 1
                elif enforce_corridor:
                    # Every slice of a dormancy is dark by construction, so
                    # hibernating is leaving the lit corridor. (A2.)
                    rejections["continuous_illumination"] += 1
                else:
                    exposure_dawn = float(shadow[dawn, row, col])
                    preheat_h, exit_inner_c, preheat_reason = (
                        battery_model_module.dawn_preheat(
                            dormant_inner,
                            float(surfaces[dawn, row, col]),
                            solar_w_at(dawn, exposure_dawn),
                            rover,
                        )
                    )
                    if (
                        preheat_reason is not None
                        or preheat_h is None
                        or not math.isfinite(preheat_h)
                    ):
                        # Tallied, never dropped: a non-finite pre-heat time would
                        # die silently in the heap comparison and the route would
                        # report itself as horizon-limited.
                        rejections["hibernate_unwakeable"] += 1
                    else:
                        preheat_slices = (
                            int(math.ceil(preheat_h / slice_hours)) if preheat_h > 0.0 else 0
                        )
                        arrival_h = dawn + preheat_slices
                        if arrival_h >= n_slices:
                            rejections["horizon"] += 1
                        elif not bool(
                            np.all(
                                shadow[dawn: arrival_h + 1, row, col]
                                < _DARK_RATIO_THRESHOLD
                            )
                        ):
                            # The pre-heat has to run to completion on array
                            # power, and NASA Glenn's polar note is that the
                            # poles see "multiple short (Dusk-Dawn) cycles" --
                            # so first light is not a promise that the light
                            # lasts. A dawn that goes dark again mid-warm-up
                            # leaves the rover neither asleep nor awake, and
                            # (the optimistic half) the darkness clock would be
                            # reset on a slice that is not actually lit.
                            rejections["hibernate_unwakeable"] += 1
                        else:
                            # The dormancy spends the continuous-darkness budget at
                            # p_hibernate_w / p_shadow_w rather than stopping it.
                            new_battery, dark_peak, refused = envelope_after(
                                exposure_now, dormancy_h, battery_wh, dark_h,
                                dormant_drain_wh, dormant_inner, hibernate_rate,
                            )
                            if refused is not None:
                                rejections[refused] += 1
                            elif enforce_haven and (
                                arrival_h > goal_last_ok
                                or not haven_ok(row, col, arrival_h)
                            ):
                                rejections["safe_haven_deadline"] += 1
                            else:
                                # The pre-heat runs on array power with the battery
                                # isolated -- "MBC in Dawn Mode operates on Solar
                                # Array power alone (Battery still Isolated)" -- so
                                # the pack neither drains nor charges across it. The
                                # waking slice is lit, so the darkness clock resets
                                # there under the same rule every lit transition uses.
                                mean_illum = float(
                                    np.mean(1.0 - shadow[slice_index:dawn, row, col])
                                )
                                gain_now = 1.0 if gain_of is None else gain_of(slice_index)
                                gain_dawn = 1.0 if gain_of is None else gain_of(dawn)
                                step_cost = hibernate_cost(
                                    mean_illum, dormancy_h, rover, hibernate_weights,
                                    solar_gain=gain_now,
                                ) + wait_cost(
                                    1.0 - exposure_dawn, preheat_h, rover, hibernate_weights,
                                    solar_gain=gain_dawn,
                                )
                                push(
                                    row, col, arrival_h, current_g + step_cost,
                                    new_battery, 0.0, label, surv,
                                    float(exit_inner_c), action="hibernate",
                                    hibernation=(
                                        dormancy_h + float(preheat_h),
                                        dark_peak - dark_h,
                                        dark_peak,
                                        coldest_c,
                                    ),
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

            # VIPER's rule: drive only into a cell that sees the Earth when
            # you get there. (A4.)
            if enforce_dte and not earth[arrival, nr, nc]:
                rejections["earth_visibility"] += 1
                continue

            # VIPER's leg rule: from wherever you arrive, a haven must still
            # be reachable before the Earth sets there. (A1.)
            if enforce_haven and (
                arrival > goal_last_ok or not haven_ok(nr, nc, arrival)
            ):
                rejections["safe_haven_deadline"] += 1
                continue

            # CMU's corridor (A2): arrive in a corridor voxel, with both
            # blocks lit for every slice of the move.
            if enforce_corridor and not (
                corridor[arrival, nr, nc]
                and lit_run[arrival, row, col] >= d_slices + 1
                and lit_run[arrival, nr, nc] >= d_slices + 1
            ):
                rejections["continuous_illumination"] += 1
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
                #                          mean_exposure, rover,
                #                          solar_gain=mean gain over the edge)
                traction_w = p_base_w * (
                    1.0 + mu_coeff * math.sin(math.radians(max(0.0, edge_slope)))
                )
                if gain_of is None:
                    # The pre-C1 expression, character for character: the
                    # rewrite below is algebraically the same at gain 1 but
                    # not the same in IEEE-754, and this path is the
                    # bit-equality lock.
                    solar_move_w = p_solar_w * (1.0 - mean_exposure)
                else:
                    # The trapezoid of the two SLICE INCOMES, not the product
                    # of two separate means. The cost cube prices slice k with
                    # slice k's own gain, so the edge's cost carries
                    # 0.5 * [(1 - e_dep) g_dep + (1 - e_arr) g_arr]; under the
                    # pre-C1 affine term the product of the means happened to
                    # equal that, but with the gain the term is BILINEAR and
                    # the two diverge by 0.25 * p_solar * (e_arr - e_dep) *
                    # (g_dep - g_arr) * h -- a factor two on an edge that
                    # crosses the terminator. B5's Monte Carlo integrates the
                    # product too (stress_test.cumulative_lit_gain), so this
                    # is also what keeps the plan and its stress test on the
                    # same number.
                    solar_move_w = p_solar_w * 0.5 * (
                        (1.0 - float(shadow[slice_index, row, col])) * gain_of(slice_index)
                        + (1.0 - float(shadow[arrival, nr, nc])) * gain_of(arrival)
                    )
                # C2: the heater the arrival block actually needs at the arrival
                # slice, when a heater cube was supplied; the exposure-scaled term
                # otherwise, character for character.
                drain_wh = (
                    traction_w
                    + housekeeping_w(mean_exposure, arrival, nr, nc)
                    - solar_move_w
                ) * travel_h
                arrival_inner = (
                    dwell_cube.inner_after(inner_c, slice_index, arrival, nr, nc)
                    if track_inner else inner_c
                )
                new_battery, new_dark, refused = envelope_after(
                    float(shadow[arrival, nr, nc]), travel_h, battery_wh, dark_h, drain_wh,
                    arrival_inner,
                )
                if refused is not None:
                    rejections[refused] += 1
                    continue
                move_drain_wh = drain_wh
            else:
                new_battery, new_dark = battery_wh, dark_h
                move_drain_wh = 0.0
                arrival_inner = (
                    dwell_cube.inner_after(inner_c, slice_index, arrival, nr, nc)
                    if track_inner else inner_c
                )

            # The chance constraint (B1): close the fault branches of this
            # move with the recovery policy and refuse it when the execution
            # failure probability would exceed beta.
            new_surv = surv
            if field is not None:
                cache_key = (slice_index, row, col, nr * width + nc, battery_key(battery_wh))
                factor = factor_cache.get(cache_key)
                if factor is None:
                    factor = field.move_survival_factor(
                        slice_index, row, col, nr, nc, battery_wh, travel_h, distance_m, move_drain_wh
                    )[0]
                    factor_cache[cache_key] = factor
                new_surv = surv * factor
                if enforce_surv and 1.0 - new_surv > beta + 1e-12:
                    rejections["failure_probability"] += 1
                    continue

            # The thermal envelope (C6): the inner temperature relaxes toward
            # the arrival block's target for the slices the move takes, and a
            # move after which it sits outside the envelope is refused. A
            # move through shadow cools the rover as surely as a wait does.
            new_inner = arrival_inner
            if enforce_dwell and not dwell_cube.inside(new_inner):
                rejections["thermal_dwell"] += 1
                continue

            step = travel_h * (1.0 + 0.5 * (from_cost + to_cost))
            push(
                nr, nc, arrival, current_g + step, new_battery, new_dark, label,
                new_surv, new_inner, action="move",
            )

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    if goal_label is None:
        return _empty(
            no_path_reason_4d(rejections, rover, n_slices, slice_hours, battery_model),
            elapsed_ms,
            rejections,
            nodes_expanded,
            safe_haven_enforced=enforce_haven,
            continuous_illumination_enforced=enforce_corridor,
            survival_enforced=enforce_surv,
            start_recovery_prob=start_recovery,
            thermal_dwell_enforced=enforce_dwell,
        )

    labels: list[tuple] = [goal_label]
    while labels[-1] in came_from:
        labels.append(came_from[labels[-1]])
    labels.reverse()

    states: list[tuple[int, int, int]] = [(r, c, t) for r, c, t, _b, _d, _s, _y in labels]
    # The dwell and the inner temperature along the route (C6), from the
    # finished route -- so the report is the same whether or not the
    # constraint was enforced (enforced, every inner value is inside).
    # C2: which family produced each transition. A hibernation holds position
    # exactly as a wait does, so the geometric test cannot tell them apart and
    # would count one as the other; with no hibernation in the route the two
    # forms agree and wait_steps is the pre-C2 number.
    path_actions = [action_of.get(label, "move") for label in labels[1:]]
    hibernate_steps = sum(1 for kind in path_actions if kind == "hibernate")
    hibernations = [
        hibernation_of[label] for label in labels[1:] if label in hibernation_of
    ]
    if hibernations:
        hibernate_hours = float(sum(item[0] for item in hibernations))
        hibernate_dark_hours = float(sum(item[1] for item in hibernations))
        coldest_inner_c = float(min(item[3] for item in hibernations))
        # The darkness clock resets at the lit waking slice, so its peak during a
        # dormancy is never in `darks` -- and a hibernation that did not reach the
        # peak would otherwise publish 0 h of continuous darkness after sleeping
        # through a night. LP-R01 reads this series.
        hibernate_dark_peak = float(max(item[2] for item in hibernations))
        beyond_evidence, beyond_reason = battery_model_module.hibernation_beyond_evidence(
            coldest_inner_c, hibernate_hours
        )
    else:
        hibernate_hours = None
        hibernate_dark_hours = None
        coldest_inner_c = None
        hibernate_dark_peak = None
        beyond_evidence, beyond_reason = None, None

    dwell_report = None if dwell_cube is None else route_dwell_report(states, slice_hours, dwell_cube)
    if dwell_cube is None:
        path_inner_c = None
    elif any(kind == "hibernate" for kind in path_actions):
        # inner_along replays the MOVE rule slice by slice and knows nothing
        # about a dormancy or its dawn pre-heat, so on a route that hibernated it
        # would trace a rover that never slept. The labels carry what the search
        # actually integrated.
        path_inner_c = [round(float(inner_of[label]), 4) for label in labels]
    else:
        path_inner_c = [round(v, 4) for v in dwell_cube.inner_along(states)]
    batteries = [battery_of[label] for label in labels]
    darks = [dark_of[label] for label in labels]
    survivals = [surv_of[label] for label in labels]

    if field is None:
        path_survival_prob = None
        path_recovery_prob = None
        execution_failure = None
        min_recovery = None
    else:
        path_survival_prob = [round(float(v), 6) for v in survivals]
        path_recovery_prob = [
            round(float(field.p_safe_at(t, r, c, wh)), 6)
            for (r, c, t), wh in zip(states, batteries)
        ]
        execution_failure = round(1.0 - float(survivals[-1]), 6)
        min_recovery = round(min(path_recovery_prob), 6)


    wait_steps = sum(
        1
        for previous, current in zip(states[:-1], states[1:])
        if previous[:2] == current[:2]
    ) - hibernate_steps

    if e_cap_wh > 0.0:
        battery_pct = [round(100.0 * wh / e_cap_wh, 3) for wh in batteries]
    else:
        battery_pct = [100.0 for _ in batteries]
    energy_drawn = sum(max(0.0, a - b) for a, b in zip(batteries[:-1], batteries[1:]))
    energy_charged = sum(max(0.0, b - a) for a, b in zip(batteries[:-1], batteries[1:]))

    if earth is None:
        path_earth_visible = None
        moves_out_of_view = None
    else:
        path_earth_visible = [bool(earth[t, r, c]) for r, c, t in states]
        moves_out_of_view = sum(
            1
            for previous, current in zip(states[:-1], states[1:])
            if previous[:2] != current[:2]
            and not earth[current[2], current[0], current[1]]
        )

    if haven_fields:
        def _finite_or_none(value: float) -> float | None:
            return round(float(value), 4) if math.isfinite(value) else None

        path_tts = [float(tts[r, c]) for r, c, _t in states]
        path_deadline = [float(deadline[t, r, c]) for r, c, t in states]
        margins = [d - x for x, d in zip(path_tts, path_deadline)]
        finite_margins = [m for m in margins if math.isfinite(m)]
        path_time_to_haven_h = [_finite_or_none(v) for v in path_tts]
        path_hours_until_earthset = [_finite_or_none(v) for v in path_deadline]
        path_haven_margin_h = [_finite_or_none(m) for m in margins]
        min_haven_margin_h = (
            round(min(finite_margins), 4) if finite_margins else None
        )
        states_past_haven_deadline = sum(
            1 for x, d in zip(path_tts, path_deadline) if x > d + 1e-9
        )
        ends_at_safe_haven = bool(tts[goal] <= 1e-9)
    else:
        path_time_to_haven_h = None
        path_hours_until_earthset = None
        path_haven_margin_h = None
        min_haven_margin_h = None
        states_past_haven_deadline = None
        ends_at_safe_haven = None

    if corridor is None:
        states_outside_corridor = None
        moves_outside_corridor = None
    else:
        outside = [not corridor[t, r, c] for r, c, t in states]
        states_outside_corridor = int(sum(outside))
        moves_outside_corridor = sum(
            1
            for previous, current, is_out in zip(states[:-1], states[1:], outside[1:])
            if is_out and previous[:2] != current[:2]
        )

    return {
        "path_states": states,
        "path_pixels": [(r, c) for r, c, _ in states],
        "path_battery_pct": battery_pct,
        "path_dark_hours": [round(d, 4) for d in darks],
        # One entry per state: whether that cell saw the Earth at that
        # slice. None when no field was supplied -- never a list of True.
        "path_earth_visible": path_earth_visible,
        # One entry per state: driving hours to the nearest safe haven, the
        # hours of Earth link left there, and their difference. None where
        # a value is infinite (no haven reachable / no Earthset in sight),
        # and None throughout when the fields were not supplied.
        "path_time_to_haven_h": path_time_to_haven_h,
        "path_hours_until_earthset": path_hours_until_earthset,
        "path_haven_margin_h": path_haven_margin_h,
        # One entry per state (B1): the execution survival so far (the
        # product of the move factors) and the recovery policy's P_safe of
        # the state itself. None without a survival field.
        "path_survival_prob": path_survival_prob,
        "path_recovery_prob": path_recovery_prob,
        # One entry per state (C6): consecutive stationary hours in the
        # current block, the block's dwell budget at the slice the stay began
        # (None where open-ended) and their difference. None without a cube.
        "path_stay_hours": None if dwell_report is None else dwell_report["path_stay_hours"],
        "path_max_dwell_h": None if dwell_report is None else dwell_report["path_max_dwell_h"],
        "path_dwell_margin_h": None if dwell_report is None else dwell_report["path_dwell_margin_h"],
        # One entry per state (C6): the inner temperature, integrated along
        # the route toward each occupied block's target. None without a cube.
        "path_inner_c": path_inner_c,
        # One entry per TRANSITION (C2): "move", "wait" or "hibernate". A
        # hibernation holds position exactly as a wait does, so any consumer
        # that re-derives legs from consecutive states needs this to tell
        # them apart.
        "path_actions": path_actions,
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
            "max_continuous_shadow_h": round(
                max(darks) if hibernate_dark_peak is None
                else max(max(darks), hibernate_dark_peak),
                4,
            ),
            "energy_drawn_wh": round(energy_drawn, 3),
            "energy_charged_wh": round(energy_charged, 3),
            "envelope_tracked": track,
            # MOVE edges that arrived in a cell with no Earth line of sight
            # (None without a field); whether such moves were refused.
            "moves_out_of_earth_view": moves_out_of_view,
            "earth_visibility_enforced": enforce_dte,
            # The safe-haven margin along the route: the tightest finite
            # margin, how many states sat past their deadline (0 whenever
            # the rule was enforced), whether the route ends parked at a
            # haven, and whether the rule was enforced.
            "min_haven_margin_h": min_haven_margin_h,
            "states_past_haven_deadline": states_past_haven_deadline,
            "ends_at_safe_haven": ends_at_safe_haven,
            "safe_haven_enforced": enforce_haven,
            # The lit corridor along the route (A2): states and moves that
            # fall outside it (0 whenever enforced), None without a cube.
            "states_outside_corridor": states_outside_corridor,
            "moves_outside_corridor": moves_outside_corridor,
            "continuous_illumination_enforced": enforce_corridor,
            # The chance constraint (B1): 1 - survival at the goal, the
            # lowest recovery probability along the route, the start's own,
            # and whether beta was enforced. None without a field.
            "execution_failure_probability": execution_failure,
            "min_recovery_prob": min_recovery,
            "start_recovery_prob": (
                None if start_recovery is None else round(float(start_recovery), 6)
            ),
            "survival_enforced": enforce_surv,
            # The thermal dwell (C6): the tightest margin between a stay and
            # its block's budget, how many states overran it (0 whenever
            # enforced), the longest stay, and whether the rule was in force.
            # None without a cube.
            "min_dwell_margin_h": None if dwell_report is None else dwell_report["min_dwell_margin_h"],
            "states_past_thermal_dwell": (
                None if dwell_report is None else dwell_report["states_past_thermal_dwell"]
            ),
            "max_stay_h": None if dwell_report is None else dwell_report["max_stay_h"],
            "thermal_dwell_enforced": enforce_dwell,
            # Hibernation and the cold battery (C2). hibernate_dark_hours is
            # what the dormancy charged to the continuous-darkness budget at
            # p_hibernate_w / p_shadow_w -- reported separately so the
            # relaxation is visible rather than hidden inside an old field,
            # while max_continuous_shadow_h keeps meaning continuous darkness
            # and D3's LP-R01 keeps measuring what it says it measures.
            "hibernate_steps": hibernate_steps,
            "hibernate_hours": hibernate_hours,
            "hibernate_dark_hours": hibernate_dark_hours,
            "coldest_inner_c": coldest_inner_c,
            "hibernation_beyond_cited_evidence": beyond_evidence,
            "hibernation_beyond_evidence_reason": beyond_reason,
            "hibernation_allowed": hibernate_enabled,
            "battery_model": battery_model,
        },
        "error": None,
    }
