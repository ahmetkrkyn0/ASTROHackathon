"""Risk-aware cost inputs: the CVaR tail of the slip and slope distributions (B2).

A cell's cost was one number: the slip ``mu(slope)`` of C3's curve and the
DEM's best-estimate slope, fed through four criteria. Both inputs come with
a spread now -- C3 put a ``sigma`` on every slip anchor
(``slip_model.slip_stats``), B3 put a per-cell slope ``sigma`` on the grid
from NASA's 100 DEM clones (``uncertainty.slope_sigma``) -- and this module
turns those spreads into the number the planner ranks by: the mean of the
worst ``1 - alpha`` of the distribution, the Conditional Value-at-Risk.

    CVaR_alpha(N(mu, sigma^2)) = mu + sigma * phi(z_alpha) / (1 - alpha),
    z_alpha = Phi^-1(alpha)

(Rockafellar & Uryasev 2000, closed form for the normal). The idea is
STEP's (Fan, Otsu, Kitahara, Zhang, Agha-mohammadi; RSS 2021) -- risk
terms as CVaR of a traversability distribution inside the planner's cost --
and Endo, Taniai, Ishigami's (ICRA 2023): slip ~ p(slip | slope, terrain),
CVaR of the slip into travel time and energy cost, the search unchanged.

Where alpha enters -- and where it does not
-------------------------------------------
``alpha`` is the operator's risk appetite, optional on a request
(``risk_alpha`` in [0.5, 0.999]). It changes the RANKING cost only:

* the energy criterion prices the cell at ``slip_cvar`` instead of ``mu``
  (``cost_engine.f_energy_cell``), where the tail's sigma is C3's anchor
  spread combined, by the delta method, with the slip the slope's own
  sigma would add: ``ds/dslope = k * s`` on a log-linear segment, so
  ``sigma_total^2 = sigma_slip^2 + (k * s * sigma_slope)^2``;
* the slope criterion reads ``min(slope_max, slope + sigma_slope * m_alpha)``
  (``cost_engine.f_slope``), the impassable gate staying on the NOMINAL
  slope so traversability never depends on alpha.

Travel time, battery, the formal margins, the corridor budgets and the
Monte Carlo keep the mean. Putting alpha into the physics would make the
nominal clock depend on a preference and double-count B5's own speed and
power distributions. What a response reports instead is the
"risk-adjusted" time and energy of the chosen route,
``t_alpha = t * (1 - mu) / (1 - s_alpha)`` (since ``t = t0 / (1 - s)``), so
the operator sees what the tail would cost without the planner's hours
changing.

``risk_alpha = None`` is the nominal build, bit for bit: every function
here is bypassed and the cost grid is the v4 grid. Note that alpha = 0.5
is NOT the mean -- ``CVaR_0.5 = mu + 0.798 sigma``.

Read this before quoting any risk number
----------------------------------------
CVaR here is a transform of MODEL-labelled distributions, never a measured
risk: the slip sigma is Yutu-2's measured range read as +-2 sigma and, for
every other anchor, a transferred relative spread of 0.5 (both assumptions,
written in the anchors' ``source``); the slope sigma is DERIVED from NASA's
clones (B3); the thermal field has NO published sigma. The thermal tail is
therefore a hook that refuses (:func:`thermal_cvar_cold_c`): measured on
Site11, ``f_thermal`` already saturates (>= 0.99) in 73 percent of LPR-1's
passable cells and 54 percent of VIPER's, and a range/4 cold tail at
alpha = 0.9 pushes that to 94 / 81 percent -- more saturation, no more
discrimination (D3's thermal-envelope finding; C6). Every response carries
``validity: "MODEL"`` and :data:`RISK_CLAIM`.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any

import numpy as np
from scipy.special import ndtri

from .slip_model import (
    MAX_SLIP_RATIO,
    _evaluate,
    _resolve,
    _segment_index,
    curve_for,
    slip_stats,
)

RISK_MEASURE_ID: str = "cvar_normal_closed_form_v1"
RISK_VALIDITY: str = "MODEL"
RISK_ALPHA_MIN: float = 0.5
RISK_ALPHA_MAX: float = 0.999

RISK_SCOPE: str = (
    "ranking cost only: the slope criterion reads min(slope_max, slope + "
    "sigma_slope * m_alpha) and the energy criterion prices the cell at "
    "CVaR_alpha(slip); travel time, battery, safety margins, corridor budgets "
    "and the Monte Carlo use the mean. risk_alpha=None is the nominal grid, "
    "bit for bit; alpha=0.5 is mu + 0.798 sigma, not the mean."
)

RISK_CLAIM: str = (
    "CVaR of MODEL-labelled distributions, not a measured risk: the slip sigma "
    "is Yutu-2's measured range read as +-2 sigma and a transferred relative "
    "spread of 0.5 elsewhere (assumptions, see each anchor's source); the "
    "slope sigma is derived from NASA's DEM clones (B3) where cached; the "
    "thermal field has no published sigma and is not tail-adjusted. Alpha "
    "changes the ranking cost only -- every hour, Wh and margin in this "
    "response is the mean-slip physics. Endo et al.'s success-rate figures "
    "are from their synthetic experiments, not from this site."
)

RISK_REFERENCES: tuple[dict[str, str], ...] = (
    {
        "id": "step_rss_2021",
        "title": "Fan, Otsu, Kitahara, Zhang, Agha-mohammadi -- STEP: Stochastic Traversability Evaluation and Planning for Risk-Aware Off-road Navigation (RSS 2021; extended arXiv 2303.01614)",
        "url": "https://arxiv.org/abs/2103.02828",
        "used_for": "CVaR of traversability risk terms inside the planner's cost (fielded in DARPA SubT)",
    },
    {
        "id": "endo_icra_2023",
        "title": "Endo, Taniai, Ishigami -- Risk-aware Path Planning via Probabilistic Fusion of Traversability Prediction for Planetary Rovers on Heterogeneous Terrains (ICRA 2023)",
        "url": "https://arxiv.org/abs/2303.01169",
        "used_for": "CVaR_alpha(slip) -> travel time / energy cost with the search unchanged; their success-rate numbers are synthetic and are quoted, not reproduced",
    },
    {
        "id": "rockafellar_uryasev_2000",
        "title": "Rockafellar, Uryasev -- Optimization of Conditional Value-at-Risk (Journal of Risk, 2000)",
        "url": "https://doi.org/10.21314/JOR.2000.038",
        "used_for": "CVaR definition; closed form for the normal: mu + sigma * phi(z_alpha) / (1 - alpha)",
    },
)

_SQRT_2PI: float = math.sqrt(2.0 * math.pi)


# ── closed form ─────────────────────────────────────────────────────────────


def _check_alpha(alpha: float) -> float:
    a = float(alpha)
    if not (RISK_ALPHA_MIN <= a <= RISK_ALPHA_MAX):
        raise ValueError(
            f"risk alpha must lie in [{RISK_ALPHA_MIN}, {RISK_ALPHA_MAX}], got {alpha!r}"
        )
    return a


def cvar_multiplier(alpha: float) -> float:
    """``phi(z_alpha) / (1 - alpha)``: how many sigmas above the mean the
    worst ``1 - alpha`` of a normal averages. 0.798 at 0.5, 1.755 at 0.9,
    2.665 at 0.99, 3.367 at 0.999. ``ValueError`` outside the allowed range."""
    a = _check_alpha(alpha)
    z = float(ndtri(a))
    return math.exp(-0.5 * z * z) / _SQRT_2PI / (1.0 - a)


def cvar_normal(mu: float, sigma: float, alpha: float) -> float:
    """``CVaR_alpha`` of ``N(mu, sigma^2)`` in closed form."""
    s = float(sigma)
    if not (s >= 0.0):
        raise ValueError(f"sigma must be non-negative, got {sigma!r}")
    return float(mu) + s * cvar_multiplier(alpha)


# ── slip: sensitivity, spread, tail ─────────────────────────────────────────


def slip_sensitivity(slope_deg: float, rover: Mapping[str, Any] | None = None) -> float:
    """``ds/dslope`` of the rover's slip curve, per degree.

    On a log-linear segment ``s = exp(a + k * slope)`` so the derivative is
    ``k * s``; it is 0 where the curve is capped at ``MAX_SLIP_RATIO`` and
    for a profile without a curve. This is what carries a slope sigma into
    a slip sigma by the delta method. Symmetric in the slope's sign.
    """
    curve = curve_for(_resolve(rover))
    if curve is None:
        return 0.0
    x = abs(float(slope_deg))
    if x != x:
        return float("nan")
    s = _evaluate(curve, x)
    if s >= MAX_SLIP_RATIO:
        return 0.0
    return curve.ks[_segment_index(curve, x)] * s


def slip_sensitivity_array(
    slope_deg: np.ndarray, rover: Mapping[str, Any] | None = None
) -> np.ndarray:
    """:func:`slip_sensitivity` over an array, same operation order (bit-equal)."""
    x = np.abs(np.asarray(slope_deg, dtype=np.float64))
    curve = curve_for(_resolve(rover))
    if curve is None:
        return np.zeros_like(x)
    last = len(curve.xs) - 2
    i = np.clip(np.searchsorted(curve.xs_array, x, side="right") - 1, 0, last)
    s = np.minimum(
        MAX_SLIP_RATIO, np.exp(curve.log_ys_array[i] + curve.ks_array[i] * (x - curve.xs_array[i]))
    )
    return np.where(s >= MAX_SLIP_RATIO, 0.0, curve.ks_array[i] * s)


def slip_stats_array(
    slope_deg: np.ndarray, rover: Mapping[str, Any] | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """``slip_model.slip_stats`` over an array: ``(mu, sigma)``, same operation
    order as the scalar (bit-equal)."""
    x = np.abs(np.asarray(slope_deg, dtype=np.float64))
    curve = curve_for(_resolve(rover))
    if curve is None:
        return np.zeros_like(x), np.zeros_like(x)
    last = len(curve.xs) - 2
    i = np.clip(np.searchsorted(curve.xs_array, x, side="right") - 1, 0, last)
    mu = np.minimum(
        MAX_SLIP_RATIO, np.exp(curve.log_ys_array[i] + curve.ks_array[i] * (x - curve.xs_array[i]))
    )
    rel = np.asarray(curve.rel_sigmas, dtype=np.float64)
    span = curve.xs_array[i + 1] - curve.xs_array[i]
    t = (x - curve.xs_array[i]) / span
    t = np.where(t < 0.0, 0.0, np.where(t > 1.0, 1.0, t))
    rel_here = rel[i] + t * (rel[i + 1] - rel[i])
    return mu, mu * rel_here


def _sigma_or_zero(slope_sigma: float | None) -> float:
    if slope_sigma is None:
        return 0.0
    s = float(slope_sigma)
    return s if math.isfinite(s) else 0.0


def slip_cvar(
    slope_deg: float,
    alpha: float,
    rover: Mapping[str, Any] | None = None,
    slope_sigma: float | None = None,
) -> float:
    """``min(MAX_SLIP_RATIO, CVaR_alpha(slip))`` at *slope_deg*.

    The tail's sigma is C3's anchor spread (``slip_stats``) combined in
    quadrature with the slip a slope error of *slope_sigma* degrees would
    add (``slip_sensitivity * slope_sigma``, the delta method). A missing or
    non-finite *slope_sigma* widens nothing. NaN slope -> NaN; a profile
    without a curve -> 0.
    """
    m = cvar_multiplier(alpha)
    rover_cfg = _resolve(rover)
    x = float(slope_deg)
    if x != x:
        return float("nan")
    mu, sigma = slip_stats(x, rover_cfg)
    term = slip_sensitivity(x, rover_cfg) * _sigma_or_zero(slope_sigma)
    total = math.sqrt(sigma * sigma + term * term)
    return min(MAX_SLIP_RATIO, mu + total * m)


def slip_cvar_array(
    slope_deg: np.ndarray,
    alpha: float,
    rover: Mapping[str, Any] | None = None,
    slope_sigma: np.ndarray | None = None,
) -> np.ndarray:
    """:func:`slip_cvar` over arrays, same operation order (bit-equal)."""
    m = cvar_multiplier(alpha)
    rover_cfg = _resolve(rover)
    x = np.asarray(slope_deg, dtype=np.float64)
    mu, sigma = slip_stats_array(x, rover_cfg)
    if slope_sigma is None:
        sig = np.zeros_like(x)
    else:
        raw = np.asarray(slope_sigma, dtype=np.float64)
        sig = np.where(np.isfinite(raw), raw, 0.0)
    term = slip_sensitivity_array(x, rover_cfg) * sig
    total = np.sqrt(sigma * sigma + term * term)
    return np.minimum(MAX_SLIP_RATIO, mu + total * m)


# ── slope tail ──────────────────────────────────────────────────────────────


def slope_cvar(
    slope_deg: float,
    alpha: float,
    slope_sigma: float | None,
    rover: Mapping[str, Any] | None = None,
) -> float:
    """``min(slope_max_deg, |slope| + slope_sigma * m_alpha)``: the slope the
    slope criterion reads under *alpha*. Without a (finite) sigma it is the
    nominal slope. The cap keeps the tail inside the rover's own limit, so
    the impassable gate -- evaluated on the nominal slope -- never moves.
    """
    m = cvar_multiplier(alpha)
    rover_cfg = _resolve(rover)
    x = abs(float(slope_deg))
    if x != x:
        return float("nan")
    sig = _sigma_or_zero(slope_sigma)
    if sig == 0.0:
        return x
    return min(float(rover_cfg["slope_max_deg"]), x + sig * m)


def slope_cvar_array(
    slope_deg: np.ndarray,
    alpha: float,
    slope_sigma: np.ndarray | None,
    rover: Mapping[str, Any] | None = None,
) -> np.ndarray:
    """:func:`slope_cvar` over arrays, same operation order (bit-equal)."""
    m = cvar_multiplier(alpha)
    rover_cfg = _resolve(rover)
    x = np.abs(np.asarray(slope_deg, dtype=np.float64))
    if slope_sigma is None:
        return x
    raw = np.asarray(slope_sigma, dtype=np.float64)
    sig = np.where(np.isfinite(raw), raw, 0.0)
    tail = np.minimum(float(rover_cfg["slope_max_deg"]), x + sig * m)
    return np.where(sig == 0.0, x, tail)


# ── route summary and response block ────────────────────────────────────────


def route_risk_summary(
    legs: Iterable[tuple[float, float, float, float | None, float | None]],
    rover: Mapping[str, Any],
    alpha: float | None,
) -> dict[str, Any] | None:
    """The ``risk.route`` block for ONE route at *alpha*, or ``None`` when
    no alpha was requested.

    *legs* are the driven edges as ``(slope_deg, distance_m, hours,
    drawn_wh | None, slope_sigma | None)`` -- the grade the edge was priced
    at, its length, its mean-slip travel time and drawn energy, and the
    slope sigma at that edge. Each leg is re-priced at its slip tail:
    ``t_alpha = t * (1 - mu) / (1 - s_alpha)`` (since ``t = t0 / (1 - s)``)
    and the same factor on the energy. Edges with a non-finite time are
    skipped and counted.
    """
    if alpha is None:
        return None
    a = _check_alpha(alpha)
    moves = 0
    skipped = 0
    distance_sum = 0.0
    weighted_mu = 0.0
    weighted_cvar = 0.0
    max_cvar = 0.0
    max_cvar_slope: float | None = None
    max_slope_tail = 0.0
    hours_sum = 0.0
    hours_adjusted = 0.0
    wh_sum = 0.0
    wh_adjusted = 0.0
    wh_known = True
    sigma_known = 0
    for slope_deg, distance_m, hours, drawn_wh, slope_sigma in legs:
        h = float(hours)
        if not math.isfinite(h):
            skipped += 1
            continue
        d = float(distance_m)
        mu, _sigma = slip_stats(slope_deg, rover)
        s_alpha = slip_cvar(slope_deg, a, rover, slope_sigma)
        factor = (1.0 - mu) / (1.0 - s_alpha)
        moves += 1
        distance_sum += d
        weighted_mu += d * mu
        weighted_cvar += d * s_alpha
        if s_alpha >= max_cvar:
            max_cvar = s_alpha
            max_cvar_slope = float(slope_deg)
        max_slope_tail = max(max_slope_tail, slope_cvar(slope_deg, a, slope_sigma, rover))
        hours_sum += h
        hours_adjusted += h * factor
        if slope_sigma is not None and math.isfinite(float(slope_sigma)):
            sigma_known += 1
        if drawn_wh is None or not math.isfinite(float(drawn_wh)):
            wh_known = False
        else:
            wh_sum += float(drawn_wh)
            wh_adjusted += float(drawn_wh) * factor
    return {
        "moves": moves,
        "skipped_edges": skipped,
        "mean_slip_mu": (weighted_mu / distance_sum) if distance_sum > 0.0 else 0.0,
        "mean_slip_cvar": (weighted_cvar / distance_sum) if distance_sum > 0.0 else 0.0,
        "max_slip_cvar": max_cvar,
        "max_slip_cvar_slope_deg": max_cvar_slope,
        "max_slope_cvar_deg": max_slope_tail,
        "slope_sigma_known_fraction": (sigma_known / moves) if moves else 0.0,
        "hours": hours_sum,
        "risk_adjusted_hours": hours_adjusted,
        "hours_factor": (hours_adjusted / hours_sum) if hours_sum > 0.0 else 1.0,
        "drawn_wh": wh_sum if (wh_known and moves > 0) else None,
        "risk_adjusted_drawn_wh": wh_adjusted if (wh_known and moves > 0) else None,
    }


def sigma_sources(
    rover: Mapping[str, Any], slope_sigma_info: Mapping[str, Any] | None
) -> dict[str, Any]:
    """Where each tail's sigma came from, for the response block.

    *slope_sigma_info* is ``uncertainty_layers_for_grids``'s ``info`` when
    the clone cache was there, else ``None``.
    """
    curve = curve_for(rover)
    if curve is None:
        slip = {
            "source": "none: this profile declares no slip_curve, so its slip and its spread are 0",
            "validity": None,
        }
    else:
        slip = {
            "source": (
                "C3 anchors: sigma per anchor (Yutu-2's measured 0..0.075 range read as "
                "+-2 sigma; a relative spread of 0.5 transferred to the other anchors as an "
                "assumption), interpolated in slope; plus the slope sigma carried into slip "
                "by the delta method (ds/dslope = k * s)"
            ),
            "validity": RISK_VALIDITY,
            "relative_spread_at_anchors": [
                {"slope_deg": float(a.slope_deg), "sigma_over_mu": float(a.sigma) / float(a.slip)}
                for a in curve.anchors
            ],
        }
    if slope_sigma_info is None:
        slope = {
            "source": "none",
            "validity": None,
            "reason": (
                "no DEM clone cache beside the processed grids; the slope criterion "
                "reads the nominal slope and the slip tail carries no slope sigma "
                "(scripts/build_dem_clone_cache.py)"
            ),
        }
    else:
        slope = {
            "source": "dem_clones",
            "model": slope_sigma_info.get("model"),
            "n_clones": slope_sigma_info.get("n_clones"),
            "validity": "SYNTHETIC" if slope_sigma_info.get("model") == "synthetic" else "DERIVED",
            "product_url": slope_sigma_info.get("product_url"),
        }
    return {"slip": slip, "slope": slope}


def risk_block(
    alpha: float | None,
    sources: Mapping[str, Any],
    route: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """The ``risk`` block a plan response carries."""
    applied = alpha is not None
    slope_available = sources.get("slope", {}).get("source") == "dem_clones"
    return {
        "alpha": None if alpha is None else float(alpha),
        "applied": applied,
        "validity": RISK_VALIDITY,
        "measure": RISK_MEASURE_ID,
        "multiplier": cvar_multiplier(alpha) if applied else None,
        "scope": RISK_SCOPE,
        "criteria": {
            "slope": "cvar" if (applied and slope_available) else "nominal",
            "energy": "cvar" if applied else "nominal",
        },
        "sigma_sources": dict(sources),
        "route": None if not applied else (dict(route) if route is not None else None),
        "claim": RISK_CLAIM,
    }


# ── thermal: a hook that refuses ────────────────────────────────────────────


def thermal_cvar_cold_c(t_peak_c: np.ndarray, t_min_c: np.ndarray, alpha: float) -> np.ndarray:
    """The cold-end thermal tail a CVaR thermal criterion would read. NOT
    implemented: the thermal field has no source for a sigma.

    The only candidate, reading ``thermal - thermal_min`` as +-2 sigma, is
    an assumption no product states -- and it would not discriminate.
    Measured on Site11 (5 Sept 2026): ``f_thermal`` is already >= 0.99 in
    72.7 percent of LPR-1's passable cells (median 0.9994) and 54.2 percent
    of VIPER's; a range/4 cold tail at alpha = 0.9 raises that to 94.0 and
    81.2 percent (mean change +0.025 / +0.070). More saturation, no more
    ranking. A thermal tail needs a measured sigma (Diviner PRP, C5) or the
    operational envelope (C6) first.
    """
    raise NotImplementedError(
        "thermal CVaR is not applied: the thermal field has no source for a "
        "sigma (thermal..thermal_min is a range, not a spread), and on Site11 "
        "f_thermal already saturates in 73 percent (LPR-1) / 54 percent (VIPER) "
        "of passable cells; a range/4 cold tail at alpha=0.9 would push that to "
        "94 / 81 percent. Needs Diviner PRP (C5) or the thermal operational "
        "envelope (C6)."
    )
