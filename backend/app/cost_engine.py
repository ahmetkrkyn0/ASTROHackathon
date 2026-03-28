"""Cost engine — all penalty functions and combined edge cost.

Every penalty returns MRU [0, 1].  Formulas match LunaPath_Final_Report_v3.2.
"""

import math

from . import constants as C


# ── 2.3.1  f_slope — Sigmoid slope penalty ──────────────────────────────────

def f_slope(theta_deg: float) -> float:
    if theta_deg > C.SLOPE_MAX_DEG:
        return float("inf")
    return 1.0 / (1.0 + math.exp(-0.4 * (theta_deg - 15.0)))


# ── 2.3.2  f_energy — Physics-based energy penalty ──────────────────────────

def f_energy(theta_deg: float, d_m: float) -> float:
    theta_rad = math.radians(theta_deg)
    cos_t = math.cos(theta_rad)
    if cos_t <= 0:
        return float("inf")

    mu = 1.0 + C.MU_COEFF * math.sin(theta_rad)
    v = C.V_MAX_MS * cos_t
    L = d_m / cos_t
    t_s = L / v
    E_wh = C.P_BASE_W * mu * t_s / 3600.0
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

    w = weights or {
        "w_slope": C.W_SLOPE,
        "w_energy": C.W_ENERGY,
        "w_shadow": C.W_SHADOW,
        "w_thermal": C.W_THERMAL,
    }

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
