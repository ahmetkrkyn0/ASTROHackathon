"""Cost engine — all penalty functions and combined edge cost.

Every penalty returns MRU [0, 1]. Formulas match
``docs/lunapath_referans_belgesi_2.md``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import numpy as np

from . import constants as C

# Identifies the formula compute_cost_grid implements. Bump this whenever a
# penalty term changes shape, so anything holding a cost grid computed by an
# older build (a P1 .npy on disk, a cache directory) can tell that it no
# longer matches this code instead of being silently reused. The v2 bump is
# review #1: f_energy -> f_energy_cell. (Review #5.) The v3 bump is round 3
# review H-4: f_energy_cell now reads shadow as well as slope, so the energy
# criterion is no longer a monotone restatement of the slope criterion.
COST_MODEL_ID: str = "weighted_cell_cost_shadow_aware_energy_v3"

_WEIGHT_KEYS: tuple[str, ...] = (
    "w_slope",
    "w_energy",
    "w_shadow",
    "w_thermal",
)


def _resolve_rover(rover: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    if rover is None:
        return C.get_rover()
    return rover


def default_weights(rover: Mapping[str, Any] | None = None) -> dict[str, float]:
    """Return the default AHP weights as a fresh dict."""
    rover_cfg = _resolve_rover(rover)
    return {
        "w_slope": float(rover_cfg["w_slope"]),
        "w_energy": float(rover_cfg["w_energy"]),
        "w_shadow": float(rover_cfg["w_shadow"]),
        "w_thermal": float(rover_cfg["w_thermal"]),
    }


def resolve_weights(
    weights: Mapping[str, float] | None = None,
    rover: Mapping[str, Any] | None = None,
) -> dict[str, float]:
    """Merge optional overrides onto the default weight profile."""
    resolved = default_weights(rover)
    if weights is None:
        return resolved

    for key in _WEIGHT_KEYS:
        if key in weights:
            resolved[key] = float(weights[key])
    return resolved


# ── 2.3.1  f_slope — Sigmoid slope penalty ──────────────────────────────────

def f_slope(theta_deg: float, rover: Mapping[str, Any] | None = None) -> float:
    rover_cfg = _resolve_rover(rover)
    slope_max = float(rover_cfg["slope_max_deg"])
    slope_comfortable = float(rover_cfg["slope_comfortable_deg"])
    if theta_deg > slope_max:
        return float("inf")
    return 1.0 / (1.0 + math.exp(-0.4 * (theta_deg - slope_comfortable)))


# ── 2.3.2  f_energy — Physics-based energy penalty ──────────────────────────

def f_energy(theta_deg: float, d_m: float, rover: Mapping[str, Any] | None = None) -> float:
    rover_cfg = _resolve_rover(rover)
    E_wh = edge_energy_wh(theta_deg, d_m, rover_cfg)
    if math.isinf(E_wh):
        return float("inf")
    return E_wh / float(rover_cfg["e_cap_wh"])


def housekeeping_power_w(
    shadow_ratio: float, rover: Mapping[str, Any] | None = None
) -> float:
    """Non-traction power the rover draws in a cell of the given shadow ratio.

    In sunlight this is the idle draw; in full shadow the survival heater is
    on top of it. ``p_shadow_w`` -- the rover's published total housekeeping
    draw in shadow -- sets the shadowed end when it is declared, which is
    what finally gives that catalogue field a reader (round 3 review, M-8);
    it equals ``p_idle_w + p_heater_w`` in every registered profile, so the
    two forms agree and the fallback is exact rather than approximate.
    """
    rover_cfg = _resolve_rover(rover)
    ratio = min(1.0, max(0.0, float(shadow_ratio)))
    idle_w = float(rover_cfg["p_idle_w"])
    shadow_w = rover_cfg.get("p_shadow_w")
    if shadow_w is not None:
        return idle_w + ratio * max(0.0, float(shadow_w) - idle_w)
    return idle_w + ratio * float(rover_cfg.get("p_heater_w") or 0.0)


def gross_energy_per_metre_wh(
    theta_deg: float,
    shadow_ratio: float = 0.0,
    rover: Mapping[str, Any] | None = None,
) -> float:
    """Energy DRAWN to advance one metre: traction plus housekeeping.

    ``edge_energy_wh`` counts traction only, which is the right number for a
    corridor's per-segment drive budget. This adds the housekeeping load the
    rover pays for the whole time it is crossing the cell.
    """
    rover_cfg = _resolve_rover(rover)
    theta = max(0.0, float(theta_deg))
    seconds = edge_travel_time_s(theta, 1.0, rover_cfg)
    if not math.isfinite(seconds):
        return float("inf")
    mu = 1.0 + float(rover_cfg["mu_coeff"]) * math.sin(math.radians(theta))
    traction_w = float(rover_cfg["p_base_w"]) * mu
    total_w = traction_w + housekeeping_power_w(shadow_ratio, rover_cfg)
    return total_w * seconds / 3600.0


def net_energy_per_metre_wh(
    theta_deg: float,
    shadow_ratio: float = 0.0,
    rover: Mapping[str, Any] | None = None,
) -> float:
    """Energy the BATTERY loses to advance one metre.

    Draw minus the solar input the cell actually offers, floored at zero: a
    cell where the array outproduces the drive is free, not negative, because
    this feeds a penalty in [0, 1] and banking charge is not a cost.

    Solar input is ``p_solar_w * (1 - shadow_ratio)`` -- the same convention
    ``simulation.simulate_path`` and ``cost_cube.wait_cost`` already use, so
    the three places that reason about solar power agree.

    This is the quantity the energy criterion should always have measured.
    Counting only the draw made the penalty a monotone function of slope --
    measured Spearman correlation with ``f_slope`` was exactly 1.000000 on
    the production slope distribution, so a quarter of the AHP weight vector
    could rescale the cost but never reorder two cells. Subtracting the solar
    term is what makes shadow a first-class input: a flat LIT cell costs the
    battery nothing at all, a flat DARK one costs 0.39 of the worst case, and
    that gap has nothing to do with slope. Measured after the change:
    Spearman 0.955, correlation with shadow +0.32. (Round 3 review, H-4.)
    """
    rover_cfg = _resolve_rover(rover)
    theta = max(0.0, float(theta_deg))
    seconds = edge_travel_time_s(theta, 1.0, rover_cfg)
    if not math.isfinite(seconds):
        return float("inf")
    mu = 1.0 + float(rover_cfg["mu_coeff"]) * math.sin(math.radians(theta))
    traction_w = float(rover_cfg["p_base_w"]) * mu
    ratio = min(1.0, max(0.0, float(shadow_ratio)))
    solar_w = float(rover_cfg.get("p_solar_w") or 0.0) * (1.0 - ratio)
    net_w = max(
        0.0, traction_w + housekeeping_power_w(ratio, rover_cfg) - solar_w
    )
    return net_w * seconds / 3600.0


def f_energy_cell(
    theta_deg: float,
    rover: Mapping[str, Any] | None = None,
    shadow_ratio: float = 0.0,
) -> float:
    """Cell-level energy penalty in MRU [0, 1].

    Unlike :func:`f_energy`, which reports one edge's energy as a FRACTION OF
    BATTERY CAPACITY, this reports how much MORE energy a cell costs than the
    cheapest possible cell (flat and fully lit), normalised so the worst
    admissible cell (at the rover's slope limit, fully shadowed) reads 1.0.

    f_energy was mathematically correct and practically inert: one 5 m edge
    draws ~1.4 Wh against a 5420 Wh battery, so the term stayed in
    [0.00026, 0.00074] while slope/shadow/thermal ranged over [0.02, 1.0].
    Weighted at 0.259 it contributed 0.04% of cell cost -- sweeping w_energy
    from 0.0 to 2.0 returned the byte-identical route, so a quarter of the
    AHP weight vector decided nothing. This is the same collapse
    :func:`f_shadow_cell` documents for the shadow term, which was fixed
    there and missed here. (Backend review, #1.)

    Round 3 review, H-4: fixing that left a subtler problem. The repaired
    term read SLOPE ONLY, and so did ``f_slope`` -- measured Spearman
    correlation between the two penalties on the production slope
    distribution was exactly 1.000000. Two of the four AHP criteria were
    therefore the same ordering under different curves, and
    ``w_slope + w_energy`` (0.668 of the default weight vector) expressed
    one preference rather than two. Energy now reads shadow as well,
    because the heater load in a dark cell is a real, first-order part of
    what a traverse costs -- and that is a genuinely different question
    from "is this slope comfortable to climb".

    The ratio is independent of edge length, so unlike f_energy this does
    not silently rescale with grid resolution.
    """
    rover_cfg = _resolve_rover(rover)
    slope_max = float(rover_cfg["slope_max_deg"])
    theta = float(theta_deg)
    # NaN must not read as flat ground. ``max(0.0, nan)`` is 0.0 in Python,
    # so a NaN slope used to return a 0.0 -- the CHEAPEST possible -- energy
    # penalty from the function documented as the reference implementation,
    # while the array form returned NaN. Production masks NaN cells to inf
    # before this matters, but the scalar's failure direction was fail-open.
    # (Round 3 review, L-1.)
    if not math.isfinite(theta):
        return float("nan")
    if theta > slope_max:
        return float("inf")

    best_wh = net_energy_per_metre_wh(0.0, 0.0, rover_cfg)
    here_wh = net_energy_per_metre_wh(max(0.0, theta), shadow_ratio, rover_cfg)
    worst_wh = net_energy_per_metre_wh(slope_max, 1.0, rover_cfg)
    if not math.isfinite(here_wh) or best_wh < 0.0:
        return float("inf")

    span = worst_wh - best_wh
    if not math.isfinite(span) or span <= 0.0:
        return 0.0
    return min(1.0, max(0.0, (here_wh - best_wh) / span))


# ── 2.3.3  f_shadow — Cumulative exponential shadow penalty ─────────────────

_SHADOW_LAMBDA = 3.0

def f_shadow(H_hours: float, rover: Mapping[str, Any] | None = None) -> float:
    rover_cfg = _resolve_rover(rover)
    h_max_shadow_h = float(rover_cfg["h_max_shadow_h"])
    if H_hours >= h_max_shadow_h:
        return 1.0
    if H_hours <= 0:
        return 0.0
    return (math.exp(_SHADOW_LAMBDA * H_hours / h_max_shadow_h) - 1.0) / (
        math.exp(_SHADOW_LAMBDA) - 1.0
    )


def f_shadow_cell(shadow_ratio: float) -> float:
    """Cell-level shadow penalty in MRU [0, 1].

    Unlike :func:`f_shadow`, which takes CUMULATIVE shadow hours and is
    therefore path-dependent, this is a per-cell proxy for the static cost
    grid. It applies the same exponential shape directly to the shadow
    ratio so a fully shadowed cell costs 1.0 and a fully lit cell 0.0.

    Feeding f_shadow a single-edge duration (~0.11 h) normalised against
    h_max_shadow_h (50 h) collapsed the term to ~3e-4, which made the
    0.142-weighted shadow criterion irrelevant to planning.
    """
    r = min(1.0, max(0.0, float(shadow_ratio)))
    return (math.exp(_SHADOW_LAMBDA * r) - 1.0) / (math.exp(_SHADOW_LAMBDA) - 1.0)


# ── 2.3.4  f_thermal — Dual-sigmoid thermal penalty ─────────────────────────

def _sigmoid(x: float) -> float:
    if x > 500:
        return 1.0
    if x < -500:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))


def surface_to_inner(T_surface_C: float, rover: Mapping[str, Any] | None = None) -> float:
    rover_cfg = _resolve_rover(rover)
    thermal_offset_cold = rover_cfg.get("thermal_offset_cold")
    thermal_offset_hot = rover_cfg.get("thermal_offset_hot")
    if thermal_offset_cold is None or thermal_offset_hot is None:
        return T_surface_C
    if T_surface_C < 0:
        return T_surface_C + float(thermal_offset_cold)
    return T_surface_C + float(thermal_offset_hot)


def inner_surface_preimages(
    T_inner_C: float, rover: Mapping[str, Any] | None = None
) -> list[float]:
    """Every surface temperature that maps to *T_inner_C*.

    ``surface_to_inner`` is piecewise on the SURFACE temperature's sign and
    jumps by ``offset_cold - offset_hot`` (100 K for lpr_1) across zero, so
    it is not injective: most inner readings have two valid pre-images, one
    on each branch, and some have only one. Returning all of them lets a
    caller be explicitly conservative -- ``log_barrier_penalty`` takes the
    WORST, so an ambiguous reading never buys the rover more headroom than
    the ambiguity allows.
    """
    rover_cfg = _resolve_rover(rover)
    cold = rover_cfg.get("thermal_offset_cold")
    hot = rover_cfg.get("thermal_offset_hot")
    if cold is None or hot is None:
        return [float(T_inner_C)]

    inner = float(T_inner_C)
    candidates: list[float] = []
    cold_branch = inner - float(cold)
    if cold_branch < 0.0:
        candidates.append(cold_branch)
    hot_branch = inner - float(hot)
    if hot_branch >= 0.0:
        candidates.append(hot_branch)
    # An inner value no surface can produce (the gap the jump leaves) is
    # reported as the nearer branch rather than as nothing at all.
    return candidates or [cold_branch]


def inner_to_surface(T_inner_C: float, rover: Mapping[str, Any] | None = None) -> float:
    """Left inverse of :func:`surface_to_inner`.

    The forward map is piecewise on the SURFACE temperature's sign and jumps
    by ``offset_cold - offset_hot`` (100 K for lpr_1) across zero, so it is
    NOT injective: every inner value in the overlap band has two valid
    surface pre-images, one on each branch. This returns the COLDER one when
    both exist. That is the conservative reading for a barrier -- it places
    the rover nearer the cold wall, so the penalty it computes is the larger
    of the two defensible values, and the barrier never reports more
    headroom than the ambiguity allows.

    ``inner_to_surface(surface_to_inner(t)) == t`` therefore does not hold
    for every t, but ``surface_to_inner(inner_to_surface(v)) == v`` does for
    every v: the value returned is always a genuine pre-image.
    """
    rover_cfg = _resolve_rover(rover)
    thermal_offset_cold = rover_cfg.get("thermal_offset_cold")
    thermal_offset_hot = rover_cfg.get("thermal_offset_hot")
    if thermal_offset_cold is None or thermal_offset_hot is None:
        return float(T_inner_C)
    cold_branch = float(T_inner_C) - float(thermal_offset_cold)
    if cold_branch < 0.0:
        return cold_branch
    return float(T_inner_C) - float(thermal_offset_hot)


def edge_travel_time_s(
    theta_deg: float,
    d_m: float,
    rover: Mapping[str, Any] | None = None,
) -> float:
    """Return traversal time for one edge in seconds."""
    rover_cfg = _resolve_rover(rover)
    cos_t = math.cos(math.radians(theta_deg))
    if cos_t <= 0:
        return float("inf")
    v = float(rover_cfg["v_max_ms"]) * cos_t
    if v <= 0:
        return float("inf")
    L = d_m / cos_t
    return L / v


def edge_energy_wh(
    theta_deg: float,
    d_m: float,
    rover: Mapping[str, Any] | None = None,
) -> float:
    """Return physical edge energy in Wh."""
    rover_cfg = _resolve_rover(rover)
    theta_rad = math.radians(theta_deg)
    cos_t = math.cos(theta_rad)
    if cos_t <= 0:
        return float("inf")

    mu = 1.0 + float(rover_cfg["mu_coeff"]) * math.sin(theta_rad)
    t_s = edge_travel_time_s(theta_deg, d_m, rover_cfg)
    if math.isinf(t_s):
        return float("inf")
    return float(rover_cfg["p_base_w"]) * mu * t_s / 3600.0


def _thermal_penalty(
    value: float,
    low: float | None,
    high: float | None,
    gain: float,
) -> float | None:
    if low is None or high is None:
        return None
    return _sigmoid(gain * (float(low) - value)) + _sigmoid(gain * (value - float(high)))


def f_thermal(T_surface_C: float, rover: Mapping[str, Any] | None = None) -> float:
    rover_cfg = _resolve_rover(rover)
    T_inner = surface_to_inner(T_surface_C, rover_cfg)

    weighted_terms: list[tuple[float, float]] = []
    bat_penalty = _thermal_penalty(
        T_inner,
        rover_cfg.get("bat_op_min_c"),
        rover_cfg.get("bat_op_max_c"),
        0.3,
    )
    if bat_penalty is not None:
        weighted_terms.append((0.6, bat_penalty))

    elec_penalty = _thermal_penalty(
        T_inner,
        rover_cfg.get("elec_op_min_c"),
        rover_cfg.get("elec_op_max_c"),
        0.25,
    )
    if elec_penalty is not None:
        weighted_terms.append((0.4, elec_penalty))

    if not weighted_terms:
        return 0.0

    total_weight = sum(weight for weight, _ in weighted_terms)
    return sum(weight * value for weight, value in weighted_terms) / total_weight


# ── 2.3.5  Log-barrier penalty ──────────────────────────────────────────────

def lateral_slope_deg(cell_slope_deg: float, along_slope_deg: float) -> float:
    """Cross-slope of an edge, given the cell's total slope and the edge's own.

    The terrain gradient at a cell has a magnitude ``tan(cell_slope)``. An
    edge crossing that cell resolves it into an along-track component,
    ``tan(along_slope)``, and a perpendicular one -- the cross-slope the
    rover rolls on. Pythagoras on the gradient vector gives

        tan(lateral)^2 = tan(cell)^2 - tan(along)^2

    clamped at zero, because a discretised along-track slope measured over
    one cell step can slightly exceed the smoothed cell gradient.

    This is what makes ``slope_lateral_max_deg`` enforceable without any new
    grid: the roll-over limit is a property of the EDGE, not of the cell,
    which is why a cell-level traversability mask could never express it.
    (Round 3 review, H-1.)
    """
    total = math.tan(math.radians(abs(float(cell_slope_deg))))
    along = math.tan(math.radians(abs(float(along_slope_deg))))
    residual = total * total - along * along
    if not math.isfinite(residual) or residual <= 0.0:
        return 0.0
    return math.degrees(math.atan(math.sqrt(residual)))


def _surface_ceiling_c(rover_cfg: Mapping[str, Any]) -> float | None:
    """Surface temperature at which the rover's hottest component hits its limit.

    Inverts :func:`surface_to_inner` on the warm branch. Returns None when the
    rover declares no electronics limit or no hot offset, in which case the
    barrier simply has no hot term -- the same "skip what is not declared"
    convention ``_thermal_penalty`` already uses.
    """
    inner_max = rover_cfg.get("elec_op_max_c")
    offset_hot = rover_cfg.get("thermal_offset_hot")
    if inner_max is None or offset_hot is None:
        return None
    return float(inner_max) - float(offset_hot)


def thermal_barrier_terms(
    t_surface_c: float, rover: Mapping[str, Any] | None = None
) -> list[float]:
    """log(slack) terms keeping a route away from its thermal limits.

    Anchored to the limits the rest of the system already enforces rather
    than to free-standing numbers. The cold anchor is
    ``THERMAL_MIN_TRAVERSABLE_C`` -- the same -150 C that
    ``compute_traversability`` uses as a hard gate -- so the barrier is the
    smooth approach to a wall that already exists, which is precisely a
    barrier's job. The hot anchor is the rover's own ``elec_op_max_c``
    mapped back to a surface temperature.

    The spec's original form used fixed -20 C / +95 C inner-temperature
    limits. Measured against the production grid those bounds put 36.2
    percent of otherwise-passable cells outside the barrier's domain, i.e.
    at infinite cost -- so the published constants are not a survival band
    for the temperatures this thermal model produces, and adopting them
    literally would have blacked out a third of the map. Anchoring to the
    traversability threshold keeps the barrier meaningful without inventing
    a survival envelope no source states. (Round 3 review, H-1.)
    """
    rover_cfg = _resolve_rover(rover)
    surface = float(t_surface_c)
    terms: list[float] = []

    cold_floor = float(C.THERMAL_MIN_TRAVERSABLE_C)
    cold_span = abs(cold_floor)  # slack reaches 1.0 at 0 C
    # Every slack is capped at 1.0. Without the cap a cell comfortably inside
    # its limits produced a slack above 1, hence a POSITIVE log, hence a
    # NEGATIVE barrier -- a discount for being safe. That is not what a
    # barrier is, and a negative edge term would also break the A*
    # heuristic's admissibility, which relies on every edge costing at least
    # distance * (1 + min_cost).
    slack_cold = min(1.0, (surface - cold_floor) / cold_span)
    if slack_cold <= 0.0:
        return [float("-inf")]
    terms.append(math.log(slack_cold))

    ceiling = _surface_ceiling_c(rover_cfg)
    if ceiling is not None and ceiling > 0.0:
        # Anchored so slack reaches 1.0 at 0 C, mirroring the cold term:
        # both walls are "far away" at the same reference temperature, and a
        # comfortable cell therefore costs exactly zero barrier rather than a
        # standing penalty for existing.
        slack_hot = min(1.0, (ceiling - surface) / ceiling)
        if slack_hot <= 0.0:
            return [float("-inf")]
        terms.append(math.log(slack_hot))

    return terms


def edge_barrier_penalty(
    theta_along: float,
    theta_lateral: float,
    t_surface_c: float,
    mu: float = C.LOG_BARRIER_MU,
    rover: Mapping[str, Any] | None = None,
) -> float:
    """The barrier terms a static-grid planner can actually evaluate.

    ``log_barrier_penalty`` below is the full spec form and includes a
    state-of-charge term. SOC is path-dependent -- it is not a property of
    an edge -- so the planner cannot evaluate it, and pretending otherwise
    is how the whole barrier ended up unused. The split is explicit: the
    GEOMETRIC and THERMAL terms are enforced here, on every edge the
    planner considers, and the SOC floor is enforced by
    ``simulation.simulate_path``, which is the only component that knows
    the battery state. Between them every term of the documented formula
    now runs somewhere. (Round 3 review, H-1.)
    """
    rover_cfg = _resolve_rover(rover)
    terms: list[float] = []

    slack_slope = 1.0 - float(theta_along) / float(rover_cfg["slope_max_deg"])
    if slack_slope <= 0.0:
        return float("inf")
    terms.append(math.log(min(1.0, slack_slope)))

    slack_lat = 1.0 - float(theta_lateral) / float(rover_cfg["slope_lateral_max_deg"])
    if slack_lat <= 0.0:
        return float("inf")
    terms.append(math.log(min(1.0, slack_lat)))

    thermal_terms = thermal_barrier_terms(t_surface_c, rover_cfg)
    if any(not math.isfinite(term) for term in thermal_terms):
        return float("inf")
    terms.extend(thermal_terms)

    return -float(mu) * sum(terms)


def log_barrier_penalty(
    theta_along: float,
    theta_lateral: float,
    soc: float,
    T_inner: float,
    mu: float = C.LOG_BARRIER_MU,
    rover: Mapping[str, Any] | None = None,
) -> float:
    """Full spec-form barrier, including the path-dependent SOC term.

    Kept as the reference implementation of
    ``docs/lunapath_referans_belgesi_2.md`` 2.3.5 and used by
    :func:`total_edge_cost`. The planner calls
    :func:`edge_barrier_penalty` instead, which drops only the SOC term --
    see that function for why.

    *T_inner* is an INNER temperature; the thermal terms need a surface
    temperature to compare against the traversability anchor, so it is
    mapped back through the rover's own offset rather than compared against
    the hardcoded -20/+95 the earlier revision used. Those constants were
    neither rover-aware nor reachable by this thermal model's output range.
    """
    rover_cfg = _resolve_rover(rover)
    terms: list[float] = []

    slack_slope = 1.0 - theta_along / float(rover_cfg["slope_max_deg"])
    if slack_slope <= 0:
        return float("inf")
    terms.append(math.log(slack_slope))

    slack_lat = 1.0 - theta_lateral / float(rover_cfg["slope_lateral_max_deg"])
    if slack_lat <= 0:
        return float("inf")
    terms.append(math.log(slack_lat))

    if soc <= 0:
        return float("inf")
    slack_soc = 1.0 - float(rover_cfg["soc_min_pct"]) / soc
    if slack_soc <= 0:
        return float("inf")
    terms.append(math.log(slack_soc))

    # T_inner does not identify a surface temperature uniquely (see
    # inner_surface_preimages), so the barrier is evaluated on every valid
    # pre-image and the WORST one wins. Reporting the gentler reading would
    # let an ambiguous sensor value buy headroom the ambiguity does not
    # support -- and the earlier single-pre-image form made the hot wall
    # unreachable through this signature entirely, because every inner value
    # that could have come from a hot surface resolved to the cold branch.
    geometric = -mu * sum(terms)
    worst = None
    for surface in inner_surface_preimages(float(T_inner), rover_cfg):
        thermal_terms = thermal_barrier_terms(surface, rover_cfg)
        if any(not math.isfinite(term) for term in thermal_terms):
            return float("inf")
        candidate = geometric - mu * sum(thermal_terms)
        worst = candidate if worst is None else max(worst, candidate)
    return geometric if worst is None else worst


# ── Combined edge cost ──────────────────────────────────────────────────────

def total_edge_cost(
    slope_deg: float,
    distance_m: float,
    H_cumulative_hours: float,
    T_surface_C: float,
    weights: dict[str, float] | None = None,
    theta_lateral: float = 0.0,
    soc: float = 1.0,
    barrier_mu: float = C.LOG_BARRIER_MU,
    rover: Mapping[str, Any] | None = None,
    shadow_ratio: float = 0.0,
) -> float:
    """Compute full edge cost  C(a→b).

    weights dict keys: w_slope, w_energy, w_shadow, w_thermal

    *shadow_ratio* feeds the energy term's heater load; it defaults to 0.0
    (fully lit), which reproduces the pre-H-4 slope-only behaviour for
    callers that do not supply it.
    """
    rover_cfg = _resolve_rover(rover)
    if slope_deg > float(rover_cfg["slope_max_deg"]):
        return float("inf")

    w = resolve_weights(weights, rover_cfg)

    cost = (
        w["w_slope"] * f_slope(slope_deg, rover_cfg)
        + w["w_energy"] * f_energy_cell(slope_deg, rover_cfg, shadow_ratio)
        + w["w_shadow"] * f_shadow(H_cumulative_hours, rover_cfg)
        + w["w_thermal"] * f_thermal(T_surface_C, rover_cfg)
    )

    T_inner = surface_to_inner(T_surface_C, rover_cfg)
    J = log_barrier_penalty(
        slope_deg,
        theta_lateral,
        soc,
        T_inner,
        barrier_mu,
        rover_cfg,
    )
    if math.isinf(J):
        return float("inf")

    cost += J
    return max(0.01, cost)


def compute_cost_grid(
    slope_grid: np.ndarray,
    thermal_grid: np.ndarray,
    shadow_ratio_grid: np.ndarray,
    resolution_m: float,
    traversable: np.ndarray | None = None,
    weights: Mapping[str, float] | None = None,
    rover: Mapping[str, Any] | None = None,
) -> np.ndarray:
    """Compute a continuous weighted cost layer for each grid cell.

    This is a *cell-level proxy* for the planner's full edge cost:
    - the slope and energy terms (`f_slope`, `f_energy_cell`) read the local
      cell slope; both are MRU [0, 1] and independent of the step length.
    - the shadow term uses ``f_shadow_cell`` on the local shadow ratio; the
      cumulative ``f_shadow`` belongs to the path-dependent planner, not to
      this static grid.
    - the log-barrier term is intentionally omitted here because it depends on
      cumulative SOC / shadow history and therefore only makes sense during
      path planning.

    Blocked cells are kept separate via ``traversable`` and receive ``inf``.
    """
    if slope_grid.shape != thermal_grid.shape or slope_grid.shape != shadow_ratio_grid.shape:
        raise ValueError("slope, thermal, and shadow grids must have identical shapes")

    if traversable is None:
        traversable_mask = np.ones_like(slope_grid, dtype=bool)
    else:
        if traversable.shape != slope_grid.shape:
            raise ValueError("traversable mask must match grid shape")
        traversable_mask = traversable.astype(bool)

    rover_cfg = _resolve_rover(rover)
    resolved = resolve_weights(weights, rover_cfg)

    # Evaluated with the array forms in app.cost_vec rather than a per-cell
    # ndenumerate loop: same formulas, same results (asserted cell-for-cell in
    # test_review_fixes), ~7.3 s -> ~0.05 s on the 500x500 production grid.
    # This runs on the request path, so the loop was a latency cost paid by
    # every plan. (Backend review, #8.)
    from .cost_vec import (
        f_energy_cell_grid,
        f_shadow_cell_grid,
        f_slope_grid,
        f_thermal_grid,
    )

    slope = np.asarray(slope_grid, dtype=np.float64)
    thermal = np.asarray(thermal_grid, dtype=np.float64)
    shadow = np.asarray(shadow_ratio_grid, dtype=np.float64)

    with np.errstate(invalid="ignore"):
        combined = (
            resolved["w_slope"] * f_slope_grid(slope, rover_cfg)
            # Reads shadow as well as slope now: without it the energy layer
            # was a monotone restatement of the slope layer and two of the
            # four AHP criteria decided the same thing. (Round 3, H-4.)
            + resolved["w_energy"] * f_energy_cell_grid(slope, rover_cfg, shadow)
            + resolved["w_shadow"] * f_shadow_cell_grid(shadow)
            + resolved["w_thermal"] * f_thermal_grid(thermal, rover_cfg)
        )

    cost_grid = np.maximum(combined, 0.01)
    invalid = (
        ~traversable_mask
        | np.isnan(slope)
        | np.isnan(thermal)
        | np.isnan(shadow)
    )
    cost_grid[invalid] = np.inf
    return cost_grid
