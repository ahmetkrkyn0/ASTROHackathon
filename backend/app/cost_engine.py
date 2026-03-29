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


def edge_shadow_hours(
    shadow_ratio: float,
    theta_deg: float,
    d_m: float,
    rover: Mapping[str, Any] | None = None,
) -> float:
    """Approximate shadow exposure accrued on a single edge."""
    if shadow_ratio <= 0:
        return 0.0
    t_s = edge_travel_time_s(theta_deg, d_m, rover)
    if math.isinf(t_s):
        return float("inf")
    return max(0.0, shadow_ratio) * (t_s / 3600.0)


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

def log_barrier_penalty(
    theta_along: float,
    theta_lateral: float,
    soc: float,
    T_inner: float,
    mu: float = C.LOG_BARRIER_MU,
    rover: Mapping[str, Any] | None = None,
) -> float:
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
    rover: Mapping[str, Any] | None = None,
) -> float:
    """Compute full edge cost  C(a→b).

    weights dict keys: w_slope, w_energy, w_shadow, w_thermal
    """
    rover_cfg = _resolve_rover(rover)
    if slope_deg > float(rover_cfg["slope_max_deg"]):
        return float("inf")

    w = resolve_weights(weights, rover_cfg)

    cost = (
        w["w_slope"] * f_slope(slope_deg, rover_cfg)
        + w["w_energy"] * f_energy(slope_deg, distance_m, rover_cfg)
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

    rover_cfg = _resolve_rover(rover)
    resolved = resolve_weights(weights, rover_cfg)
    cost_grid = np.full(slope_grid.shape, np.inf, dtype=np.float64)

    for idx, slope_deg in np.ndenumerate(slope_grid):
        thermal_c = float(thermal_grid[idx])
        shadow_ratio = float(shadow_ratio_grid[idx])

        if not traversable_mask[idx]:
            continue
        if math.isnan(float(slope_deg)) or math.isnan(thermal_c) or math.isnan(shadow_ratio):
            continue

        local_shadow_h = edge_shadow_hours(shadow_ratio, float(slope_deg), resolution_m, rover_cfg)
        if math.isinf(local_shadow_h):
            continue

        local_cost = (
            resolved["w_slope"] * f_slope(float(slope_deg), rover_cfg)
            + resolved["w_energy"] * f_energy(float(slope_deg), resolution_m, rover_cfg)
            + resolved["w_shadow"] * f_shadow(local_shadow_h, rover_cfg)
            + resolved["w_thermal"] * f_thermal(thermal_c, rover_cfg)
        )
        cost_grid[idx] = max(0.01, local_cost)

    return cost_grid
