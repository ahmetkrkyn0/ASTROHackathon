"""Cost engine — all penalty functions and combined edge cost.

Every penalty returns MRU [0, 1]. Formulas match
``docs/lunapath_referans_belgesi_2.md``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

import numpy as np

from . import constants as C

_WEIGHT_KEYS: tuple[str, ...] = (
    "w_slope",
    "w_energy",
    "w_shadow",
    "w_thermal",
)


def default_weights() -> dict[str, float]:
    """Return the default AHP weights as a fresh dict."""
    return {
        "w_slope": C.W_SLOPE,
        "w_energy": C.W_ENERGY,
        "w_shadow": C.W_SHADOW,
        "w_thermal": C.W_THERMAL,
    }


def resolve_weights(weights: Mapping[str, float] | None = None) -> dict[str, float]:
    """Merge optional overrides onto the default weight profile."""
    resolved = default_weights()
    if weights is None:
        return resolved

    for key in _WEIGHT_KEYS:
        if key in weights:
            resolved[key] = float(weights[key])
    return resolved


# ── 2.3.1  f_slope — Sigmoid slope penalty ──────────────────────────────────

def f_slope(theta_deg: float) -> float:
    if theta_deg > C.SLOPE_MAX_DEG:
        return float("inf")
    return 1.0 / (1.0 + math.exp(-0.4 * (theta_deg - 15.0)))


# ── 2.3.2  f_energy — Physics-based energy penalty ──────────────────────────

def f_energy(theta_deg: float, d_m: float) -> float:
    E_wh = edge_energy_wh(theta_deg, d_m)
    if math.isinf(E_wh):
        return float("inf")
    return E_wh / C.E_CAP_WH


# ── 2.3.3  f_shadow — Cumulative exponential shadow penalty ─────────────────

_SHADOW_LAMBDA = 3.0

def f_shadow(H_hours: float) -> float:
    if H_hours >= C.H_MAX_SHADOW_H:
        return 1.0
    if H_hours <= 0:
        return 0.0
    return (math.exp(_SHADOW_LAMBDA * H_hours / C.H_MAX_SHADOW_H) - 1.0) / (
        math.exp(_SHADOW_LAMBDA) - 1.0
    )


# ── 2.3.4  f_thermal — Dual-sigmoid thermal penalty ─────────────────────────

def _sigmoid(x: float) -> float:
    if x > 500:
        return 1.0
    if x < -500:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))


def surface_to_inner(T_surface_C: float) -> float:
    if T_surface_C < 0:
        return T_surface_C + C.THERMAL_OFFSET_COLD
    return T_surface_C + C.THERMAL_OFFSET_HOT


def edge_path_length_m(theta_deg: float, d_m: float) -> float:
    """Return rover travel length along a sloped edge."""
    cos_t = math.cos(math.radians(theta_deg))
    if cos_t <= 0:
        return float("inf")
    return d_m / cos_t


def edge_travel_time_s(theta_deg: float, d_m: float) -> float:
    """Return traversal time for one edge in seconds."""
    cos_t = math.cos(math.radians(theta_deg))
    if cos_t <= 0:
        return float("inf")
    v = C.V_MAX_MS * cos_t
    if v <= 0:
        return float("inf")
    L = d_m / cos_t
    return L / v


def edge_energy_wh(theta_deg: float, d_m: float) -> float:
    """Return physical edge energy in Wh."""
    theta_rad = math.radians(theta_deg)
    cos_t = math.cos(theta_rad)
    if cos_t <= 0:
        return float("inf")

    mu = 1.0 + C.MU_COEFF * math.sin(theta_rad)
    t_s = edge_travel_time_s(theta_deg, d_m)
    if math.isinf(t_s):
        return float("inf")
    return C.P_BASE_W * mu * t_s / 3600.0


def edge_shadow_hours(shadow_ratio: float, theta_deg: float, d_m: float) -> float:
    """Approximate shadow exposure accrued on a single edge."""
    if shadow_ratio <= 0:
        return 0.0
    t_s = edge_travel_time_s(theta_deg, d_m)
    if math.isinf(t_s):
        return float("inf")
    return max(0.0, shadow_ratio) * (t_s / 3600.0)


def f_thermal(T_surface_C: float) -> float:
    T_inner = surface_to_inner(T_surface_C)

    S_bat = _sigmoid(0.3 * (C.BAT_OP_MIN_C - T_inner)) + _sigmoid(
        0.3 * (T_inner - C.BAT_OP_MAX_C)
    )
    S_elk = _sigmoid(0.25 * (C.ELEC_OP_MIN_C - T_inner)) + _sigmoid(
        0.25 * (T_inner - C.ELEC_OP_MAX_C)
    )
    return 0.6 * S_bat + 0.4 * S_elk


# ── 2.3.5  Log-barrier penalty ──────────────────────────────────────────────

def log_barrier_penalty(
    theta_along: float,
    theta_lateral: float,
    soc: float,
    T_inner: float,
    mu: float = C.LOG_BARRIER_MU,
) -> float:
    terms: list[float] = []

    slack_slope = 1.0 - theta_along / 25.0
    if slack_slope <= 0:
        return float("inf")
    terms.append(math.log(slack_slope))

    slack_lat = 1.0 - theta_lateral / 18.0
    if slack_lat <= 0:
        return float("inf")
    terms.append(math.log(slack_lat))

    if soc <= 0:
        return float("inf")
    slack_soc = 1.0 - 0.20 / soc
    if slack_soc <= 0:
        return float("inf")
    terms.append(math.log(slack_soc))

    slack_t_low = (T_inner + 20) / 115.0
    if slack_t_low <= 0:
        return float("inf")
    terms.append(math.log(slack_t_low))

    slack_t_high = (95 - T_inner) / 115.0
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
    barrier_mu: float = C.LOG_BARRIER_MU,
) -> float:
    """Compute full edge cost  C(a→b).

    weights dict keys: w_slope, w_energy, w_shadow, w_thermal
    """
    if slope_deg > C.SLOPE_MAX_DEG:
        return float("inf")

    w = resolve_weights(weights)

    cost = (
        w["w_slope"] * f_slope(slope_deg)
        + w["w_energy"] * f_energy(slope_deg, distance_m)
        + w["w_shadow"] * f_shadow(H_cumulative_hours)
        + w["w_thermal"] * f_thermal(T_surface_C)
    )

    T_inner = surface_to_inner(T_surface_C)
    J = log_barrier_penalty(slope_deg, theta_lateral, soc, T_inner, barrier_mu)
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
    if slope_grid.shape != thermal_grid.shape or slope_grid.shape != shadow_ratio_grid.shape:
        raise ValueError("slope, thermal, and shadow grids must have identical shapes")

    if traversable is None:
        traversable_mask = np.ones_like(slope_grid, dtype=bool)
    else:
        if traversable.shape != slope_grid.shape:
            raise ValueError("traversable mask must match grid shape")
        traversable_mask = traversable.astype(bool)

    resolved = resolve_weights(weights)
    cost_grid = np.full(slope_grid.shape, np.inf, dtype=np.float64)

    for idx, slope_deg in np.ndenumerate(slope_grid):
        thermal_c = float(thermal_grid[idx])
        shadow_ratio = float(shadow_ratio_grid[idx])

        if not traversable_mask[idx]:
            continue
        if math.isnan(float(slope_deg)) or math.isnan(thermal_c) or math.isnan(shadow_ratio):
            continue

        local_shadow_h = edge_shadow_hours(shadow_ratio, float(slope_deg), resolution_m)
        if math.isinf(local_shadow_h):
            continue

        local_cost = (
            resolved["w_slope"] * f_slope(float(slope_deg))
            + resolved["w_energy"] * f_energy(float(slope_deg), resolution_m)
            + resolved["w_shadow"] * f_shadow(local_shadow_h)
            + resolved["w_thermal"] * f_thermal(thermal_c)
        )
        cost_grid[idx] = max(0.01, local_cost)

    return cost_grid
