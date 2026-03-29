"""Cost engine — all penalty functions and combined edge cost.

Every penalty returns MRU [0, 1]. Formulas match
``docs/lunapath_referans_belgesi_2.md``.

All functions accept a ``rover_config`` dict so the engine is rover-agnostic.
When ``rover_config`` is None the default rover (LPR-1) is used.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

import numpy as np

from .constants import LOG_BARRIER_MU, get_rover

_WEIGHT_KEYS: tuple[str, ...] = (
    "w_slope",
    "w_energy",
    "w_shadow",
    "w_thermal",
)


def default_weights(rover_config: dict | None = None) -> dict[str, float]:
    """Return the default AHP weights from the rover config."""
    rc = rover_config or get_rover()
    return {k: rc[k] for k in _WEIGHT_KEYS}


def resolve_weights(
    weights: Mapping[str, float] | None = None,
    rover_config: dict | None = None,
) -> dict[str, float]:
    """Merge optional overrides onto the rover's default weight profile."""
    resolved = default_weights(rover_config)
    if weights is None:
        return resolved
    for key in _WEIGHT_KEYS:
        if key in weights:
            resolved[key] = float(weights[key])
    return resolved


# ── 2.3.1  f_slope — Sigmoid slope penalty ──────────────────────────────────

def f_slope(theta_deg: float, rover_config: dict | None = None) -> float:
    rc = rover_config or get_rover()
    if theta_deg > rc["slope_max_deg"]:
        return float("inf")
    return 1.0 / (1.0 + math.exp(-0.4 * (theta_deg - rc["slope_comfortable_deg"])))


# ── 2.3.2  f_energy — Physics-based energy penalty ──────────────────────────

def f_energy(theta_deg: float, d_m: float, rover_config: dict | None = None) -> float:
    rc = rover_config or get_rover()
    E_wh = edge_energy_wh(theta_deg, d_m, rc)
    if math.isinf(E_wh):
        return float("inf")
    return E_wh / rc["e_cap_wh"]


# ── 2.3.3  f_shadow — Cumulative exponential shadow penalty ─────────────────

_SHADOW_LAMBDA = 3.0

def f_shadow(H_hours: float, rover_config: dict | None = None) -> float:
    rc = rover_config or get_rover()
    h_max = rc["h_max_shadow_h"]
    if h_max is None or h_max <= 0:
        return 0.0
    if H_hours >= h_max:
        return 1.0
    if H_hours <= 0:
        return 0.0
    return (math.exp(_SHADOW_LAMBDA * H_hours / h_max) - 1.0) / (
        math.exp(_SHADOW_LAMBDA) - 1.0
    )


# ── 2.3.4  f_thermal — Dual-sigmoid thermal penalty ─────────────────────────

def _sigmoid(x: float) -> float:
    if x > 500:
        return 1.0
    if x < -500:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))


def surface_to_inner(T_surface_C: float, rover_config: dict | None = None) -> float:
    rc = rover_config or get_rover()
    offset_cold = rc.get("thermal_offset_cold")
    offset_hot = rc.get("thermal_offset_hot")
    if offset_cold is None or offset_hot is None:
        return T_surface_C
    if T_surface_C < 0:
        return T_surface_C + offset_cold
    return T_surface_C + offset_hot


def edge_travel_time_s(theta_deg: float, d_m: float, rover_config: dict | None = None) -> float:
    """Return traversal time for one edge in seconds."""
    rc = rover_config or get_rover()
    cos_t = math.cos(math.radians(theta_deg))
    if cos_t <= 0:
        return float("inf")
    v = rc["v_max_ms"] * cos_t
    if v <= 0:
        return float("inf")
    L = d_m / cos_t
    return L / v


def edge_energy_wh(theta_deg: float, d_m: float, rover_config: dict | None = None) -> float:
    """Return physical edge energy in Wh."""
    rc = rover_config or get_rover()
    theta_rad = math.radians(theta_deg)
    cos_t = math.cos(theta_rad)
    if cos_t <= 0:
        return float("inf")

    mu = 1.0 + rc["mu_coeff"] * math.sin(theta_rad)
    t_s = edge_travel_time_s(theta_deg, d_m, rc)
    if math.isinf(t_s):
        return float("inf")
    return rc["p_base_w"] * mu * t_s / 3600.0


def edge_shadow_hours(shadow_ratio: float, theta_deg: float, d_m: float, rover_config: dict | None = None) -> float:
    """Approximate shadow exposure accrued on a single edge."""
    if shadow_ratio <= 0:
        return 0.0
    rc = rover_config or get_rover()
    t_s = edge_travel_time_s(theta_deg, d_m, rc)
    if math.isinf(t_s):
        return float("inf")
    return max(0.0, shadow_ratio) * (t_s / 3600.0)


def f_thermal(T_surface_C: float, rover_config: dict | None = None) -> float:
    rc = rover_config or get_rover()

    # If thermal operating limits are not defined, disable thermal penalty
    bat_min = rc.get("bat_op_min_c")
    bat_max = rc.get("bat_op_max_c")
    elec_min = rc.get("elec_op_min_c")
    elec_max = rc.get("elec_op_max_c")

    T_inner = surface_to_inner(T_surface_C, rc)

    # Battery component
    if bat_min is not None and bat_max is not None:
        S_bat = _sigmoid(0.3 * (bat_min - T_inner)) + _sigmoid(
            0.3 * (T_inner - bat_max)
        )
    else:
        S_bat = 0.0

    # Electronics component
    if elec_min is not None and elec_max is not None:
        S_elk = _sigmoid(0.25 * (elec_min - T_inner)) + _sigmoid(
            0.25 * (T_inner - elec_max)
        )
    else:
        S_elk = 0.0

    return 0.6 * S_bat + 0.4 * S_elk


# ── 2.3.5  Log-barrier penalty ──────────────────────────────────────────────

def log_barrier_penalty(
    theta_along: float,
    theta_lateral: float,
    soc: float,
    T_inner: float,
    rover_config: dict | None = None,
    mu: float = LOG_BARRIER_MU,
) -> float:
    rc = rover_config or get_rover()
    terms: list[float] = []

    slope_max = rc["slope_max_deg"]
    slope_lat_max = rc["slope_lateral_max_deg"]
    soc_min = rc["soc_min_pct"]

    slack_slope = 1.0 - theta_along / slope_max
    if slack_slope <= 0:
        return float("inf")
    terms.append(math.log(slack_slope))

    slack_lat = 1.0 - theta_lateral / slope_lat_max
    if slack_lat <= 0:
        return float("inf")
    terms.append(math.log(slack_lat))

    if soc <= 0:
        return float("inf")
    slack_soc = 1.0 - soc_min / soc
    if slack_soc <= 0:
        return float("inf")
    terms.append(math.log(slack_soc))

    # Thermal barrier only if limits are available
    bat_min = rc.get("bat_op_min_c")
    elec_max = rc.get("elec_op_max_c")
    if bat_min is not None and elec_max is not None:
        t_low_bound = bat_min - 10
        t_high_bound = elec_max + 55
        range_span = t_high_bound - t_low_bound
        if range_span <= 0:
            range_span = 115.0

        slack_t_low = (T_inner - t_low_bound) / range_span
        if slack_t_low <= 0:
            return float("inf")
        terms.append(math.log(slack_t_low))

        slack_t_high = (t_high_bound - T_inner) / range_span
        if slack_t_high <= 0:
            return float("inf")
        terms.append(math.log(slack_t_high))

    return -mu * sum(terms)


# ── Combined edge cost ──────────────────────────────────────────────────────

def total_edge_cost(
    slope_deg: float,
    distance_m: float,
    H_cumulative_hours: float,
    T_surface_C: float,
    weights: dict[str, float] | None = None,
    theta_lateral: float = 0.0,
    soc: float = 1.0,
    barrier_mu: float = LOG_BARRIER_MU,
    rover_config: dict | None = None,
) -> float:
    """Compute full edge cost  C(a->b).

    weights dict keys: w_slope, w_energy, w_shadow, w_thermal
    """
    rc = rover_config or get_rover()
    if slope_deg > rc["slope_max_deg"]:
        return float("inf")

    w = resolve_weights(weights, rc)

    cost = (
        w["w_slope"] * f_slope(slope_deg, rc)
        + w["w_energy"] * f_energy(slope_deg, distance_m, rc)
        + w["w_shadow"] * f_shadow(H_cumulative_hours, rc)
        + w["w_thermal"] * f_thermal(T_surface_C, rc)
    )

    T_inner = surface_to_inner(T_surface_C, rc)
    J = log_barrier_penalty(slope_deg, theta_lateral, soc, T_inner, rc, barrier_mu)
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
    rover_config: dict | None = None,
) -> np.ndarray:
    """Compute a continuous weighted cost layer for each grid cell.

    This is a *cell-level proxy* for the planner's full edge cost:
    - edge-based terms (`f_slope`, `f_energy`) use the local cell slope and one
      nominal grid step of length ``resolution_m``.
    - the shadow term uses local shadow ratio multiplied by the traversal time
      of one nominal step.
    - the log-barrier term is intentionally omitted here because it depends on
      cumulative SOC / shadow history and therefore only makes sense during
      path planning.

    Blocked cells are kept separate via ``traversable`` and receive ``inf``.
    """
    rc = rover_config or get_rover()

    if slope_grid.shape != thermal_grid.shape or slope_grid.shape != shadow_ratio_grid.shape:
        raise ValueError("slope, thermal, and shadow grids must have identical shapes")

    if traversable is None:
        traversable_mask = np.ones_like(slope_grid, dtype=bool)
    else:
        if traversable.shape != slope_grid.shape:
            raise ValueError("traversable mask must match grid shape")
        traversable_mask = traversable.astype(bool)

    resolved = resolve_weights(weights, rc)
    cost_grid = np.full(slope_grid.shape, np.inf, dtype=np.float64)

    for idx, slope_deg in np.ndenumerate(slope_grid):
        thermal_c = float(thermal_grid[idx])
        shadow_ratio = float(shadow_ratio_grid[idx])

        if not traversable_mask[idx]:
            continue
        if math.isnan(float(slope_deg)) or math.isnan(thermal_c) or math.isnan(shadow_ratio):
            continue

        local_shadow_h = edge_shadow_hours(shadow_ratio, float(slope_deg), resolution_m, rc)
        if math.isinf(local_shadow_h):
            continue

        local_cost = (
            resolved["w_slope"] * f_slope(float(slope_deg), rc)
            + resolved["w_energy"] * f_energy(float(slope_deg), resolution_m, rc)
            + resolved["w_shadow"] * f_shadow(local_shadow_h, rc)
            + resolved["w_thermal"] * f_thermal(thermal_c, rc)
        )
        cost_grid[idx] = max(0.01, local_cost)

    return cost_grid
