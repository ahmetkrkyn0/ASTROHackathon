"""Array forms of the cost_engine penalties.

``app.cost_engine`` holds the scalar, reference implementations -- the frozen
formulas the docs and tests describe. This module holds their true NumPy
equivalents, cell for cell identical but evaluated on whole grids at once.

Why it exists: the layered cost map used ``np.vectorize``, which is a Python
loop behind an array-shaped API, not vectorisation. Both cost paths therefore
cost ~1.3-1.5 s per 500x500 call, on the request path, twice per plan. These
functions are the same maths written for arrays.

The scalar forms stay the source of truth: ``test_review_fixes`` asserts each
function here matches its ``cost_engine`` counterpart across the input domain,
so a future edit to one that is not mirrored in the other fails a test rather
than silently splitting the planner from ``CostMap.explain()``. (Review #8.)
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from .cost_engine import _SHADOW_LAMBDA, _resolve_rover


def f_slope_grid(
    slope_deg: np.ndarray, rover: Mapping[str, Any] | None = None
) -> np.ndarray:
    """Array form of :func:`app.cost_engine.f_slope`."""
    rover_cfg = _resolve_rover(rover)
    slope_max = float(rover_cfg["slope_max_deg"])
    comfortable = float(rover_cfg["slope_comfortable_deg"])

    theta = np.asarray(slope_deg, dtype=np.float64)
    with np.errstate(over="ignore", invalid="ignore"):
        penalty = 1.0 / (1.0 + np.exp(-0.4 * (theta - comfortable)))
    return np.where(theta > slope_max, np.inf, penalty)


def f_energy_cell_grid(
    slope_deg: np.ndarray,
    rover: Mapping[str, Any] | None = None,
    shadow_ratio: np.ndarray | float = 0.0,
) -> np.ndarray:
    """Array form of :func:`app.cost_engine.f_energy_cell`.

    Reads slope AND shadow: the heater load in a dark cell is part of what a
    traverse costs, and without it this penalty was rank-identical to
    ``f_slope_grid`` (measured Spearman 1.000000 on the production slope
    distribution). (Round 3 review, H-4.)
    """
    rover_cfg = _resolve_rover(rover)
    slope_max = float(rover_cfg["slope_max_deg"])

    theta = np.asarray(slope_deg, dtype=np.float64)
    shadow = np.clip(np.asarray(shadow_ratio, dtype=np.float64), 0.0, 1.0)

    best_wh = _energy_per_metre_wh_scalar(0.0, 0.0, rover_cfg)
    worst_wh = _energy_per_metre_wh_scalar(slope_max, 1.0, rover_cfg)
    if not np.isfinite(best_wh) or best_wh < 0.0:
        return np.full(np.broadcast(theta, shadow).shape, np.inf, dtype=np.float64)

    span = worst_wh - best_wh
    if not np.isfinite(span) or span <= 0.0:
        return np.where(theta > slope_max, np.inf, 0.0)

    here_wh = _energy_per_metre_wh_grid(theta, shadow, rover_cfg)
    value = np.clip((here_wh - best_wh) / span, 0.0, 1.0)
    return np.where(theta > slope_max, np.inf, value)


def _housekeeping_power_w_grid(
    shadow_ratio: np.ndarray, rover_cfg: Mapping[str, Any]
) -> np.ndarray:
    """Array form of :func:`app.cost_engine.housekeeping_power_w`."""
    ratio = np.clip(np.asarray(shadow_ratio, dtype=np.float64), 0.0, 1.0)
    idle_w = float(rover_cfg["p_idle_w"])
    shadow_w = rover_cfg.get("p_shadow_w")
    if shadow_w is not None:
        return idle_w + ratio * max(0.0, float(shadow_w) - idle_w)
    return idle_w + ratio * float(rover_cfg.get("p_heater_w") or 0.0)


def _energy_per_metre_wh_grid(
    theta_deg: np.ndarray, shadow_ratio: np.ndarray, rover_cfg: Mapping[str, Any]
) -> np.ndarray:
    """Array form of :func:`app.cost_engine.net_energy_per_metre_wh`.

    ``edge_travel_time_s(theta, 1.0) = (1 / cos) / (v_max * cos)``, so cos
    enters SQUARED -- the same identity the scalar form relies on.
    """
    mu_coeff = float(rover_cfg["mu_coeff"])
    p_base = float(rover_cfg["p_base_w"])
    v_max = float(rover_cfg["v_max_ms"])

    theta_rad = np.radians(np.clip(np.asarray(theta_deg, dtype=np.float64), 0.0, None))
    cos_t = np.cos(theta_rad)
    with np.errstate(divide="ignore", invalid="ignore"):
        seconds = 1.0 / (v_max * cos_t * cos_t)
    traction_w = p_base * (1.0 + mu_coeff * np.sin(theta_rad))
    ratio = np.clip(np.asarray(shadow_ratio, dtype=np.float64), 0.0, 1.0)
    solar_w = float(rover_cfg.get("p_solar_w") or 0.0) * (1.0 - ratio)
    net_w = np.maximum(
        0.0, traction_w + _housekeeping_power_w_grid(ratio, rover_cfg) - solar_w
    )
    with np.errstate(invalid="ignore"):
        return net_w * seconds / 3600.0


def _energy_per_metre_wh_scalar(
    theta_deg: float, shadow_ratio: float, rover_cfg: Mapping[str, Any]
) -> float:
    from .cost_engine import net_energy_per_metre_wh

    return net_energy_per_metre_wh(theta_deg, shadow_ratio, rover_cfg)


def f_shadow_cell_grid(shadow_ratio: np.ndarray) -> np.ndarray:
    """Array form of :func:`app.cost_engine.f_shadow_cell`."""
    ratio = np.clip(np.asarray(shadow_ratio, dtype=np.float64), 0.0, 1.0)
    return (np.exp(_SHADOW_LAMBDA * ratio) - 1.0) / (np.exp(_SHADOW_LAMBDA) - 1.0)


def _sigmoid_grid(x: np.ndarray) -> np.ndarray:
    """Array form of cost_engine._sigmoid, including its +/-500 saturation."""
    clipped = np.clip(np.asarray(x, dtype=np.float64), -500.0, 500.0)
    out = 1.0 / (1.0 + np.exp(-clipped))
    out = np.where(np.asarray(x) > 500.0, 1.0, out)
    return np.where(np.asarray(x) < -500.0, 0.0, out)


def surface_to_inner_grid(
    surface_c: np.ndarray, rover: Mapping[str, Any] | None = None
) -> np.ndarray:
    """Array form of :func:`app.cost_engine.surface_to_inner`."""
    rover_cfg = _resolve_rover(rover)
    cold = rover_cfg.get("thermal_offset_cold")
    hot = rover_cfg.get("thermal_offset_hot")
    surface = np.asarray(surface_c, dtype=np.float64)
    if cold is None or hot is None:
        return surface
    return np.where(surface < 0.0, surface + float(cold), surface + float(hot))


def f_thermal_grid(
    surface_c: np.ndarray, rover: Mapping[str, Any] | None = None
) -> np.ndarray:
    """Array form of :func:`app.cost_engine.f_thermal`."""
    rover_cfg = _resolve_rover(rover)
    inner = surface_to_inner_grid(surface_c, rover_cfg)

    total_weight = 0.0
    accumulator = np.zeros(np.shape(inner), dtype=np.float64)

    for weight, low_key, high_key, gain in (
        (0.6, "bat_op_min_c", "bat_op_max_c", 0.3),
        (0.4, "elec_op_min_c", "elec_op_max_c", 0.25),
    ):
        low = rover_cfg.get(low_key)
        high = rover_cfg.get(high_key)
        if low is None or high is None:
            continue
        penalty = _sigmoid_grid(gain * (float(low) - inner)) + _sigmoid_grid(
            gain * (inner - float(high))
        )
        accumulator = accumulator + weight * penalty
        total_weight += weight

    if total_weight == 0.0:
        return np.zeros(np.shape(inner), dtype=np.float64)
    return accumulator / total_weight
