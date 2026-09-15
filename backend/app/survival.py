"""Recovery policies and the chance constraint (B1).

The planner in ``app.pathfinder_4d`` is deterministic: a route is inside the
rover's envelope or it is not. This module adds the question "and if
something goes wrong on the way?" the way Lamarre, Malhotra and Kelly
(University of Toronto STARS Lab) answer it for a solar-powered rover in
the lunar south pole:

* the rover's state is ``(time bin, cell, state-of-charge bin)``;
* from every state the rover may drive to one of its eight neighbours or
  wait one bin; a drive can suffer a mobility fault (Poisson in distance
  driven, rate ``alpha`` per km) that pins it in place for ``R`` hours;
* a state is a FAILURE when its battery bin lies under the reserve or when
  the horizon runs out; a state is SAFE when the rover stands in the safe
  set with the charge that set requires;
* backward value iteration gives ``V(x)``, the probability that the best
  possible policy from ``x`` still ends in failure; ``P_safe = 1 - V`` is
  published, and the arg-min action is the RECOVERY POLICY.

The 4-D planner then carries an execution-survival factor in every label:
at each move the fault branches are closed with ``P_safe`` of the state the
fault leaves the rover in (the AERO 2024 rule), and with
``max_failure_probability = beta`` a move that would push the execution
failure probability over ``beta`` is refused.

What is Lamarre's and what is ours is stated in ``SURVIVAL_CLAIM`` and
``LAMARRE_QUOTED``; every response carries both. Two deliberate deviations
from the papers, both forced by the data and both reported:

* the SAFE SET. Lamarre's target set is "at a safe haven with the charge
  to hibernate through the lunar night". On Site11 LPR-1 has no safe haven
  at any epoch probed (A1; probe of 5 Sep 2026), so that set is empty and
  ``P_safe`` would be zero everywhere. The default set here is the LEG set
  -- the plan's goal block at the reserve charge, plus every haven block
  at its hibernation charge -- and ``safe_set="haven"`` is the strict one.
* the TIME AXIS. Every action advances at least one bin (the planner's own
  ``ceil`` rule), so a single backward sweep is exact and no fixed-point
  iteration is needed; the papers' min-max over the lower and upper time
  bin is applied wherever a move spans more than one bin and, always, when
  the planner reads the field between two bins.
"""

from __future__ import annotations

import math
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from . import constants as C
from .cost_engine import edge_travel_time_s_array, housekeeping_power_w

# ── identity, claim, references ──────────────────────────────────────────────

SURVIVAL_MODEL_ID: str = "reach_avoid_value_iteration_v1"
SURVIVAL_VALIDITY: str = "MODEL"

#: Which states count as "safe" (the reach target of the reach-avoid
#: problem). ``leg``: the goal block at the reserve charge and every safe
#: haven block at its hibernation charge; ``haven``: the havens only, which
#: is Lamarre's target set.
SAFE_SETS: tuple[str, ...] = ("leg", "haven")

#: The planner's move order (``pathfinder_4d._OFFSETS``), so an action code
#: means the same thing in the policy cube and in the planner.
OFFSETS: tuple[tuple[int, int, bool], ...] = (
    (-1, 0, False), (1, 0, False), (0, -1, False), (0, 1, False),
    (-1, -1, True), (-1, 1, True), (1, -1, True), (1, 1, True),
)
ACTION_NAMES: tuple[str, ...] = ("N", "S", "W", "E", "NW", "NE", "SW", "SE", "wait")
ACTION_WAIT: int = 8
#: The state is already in the safe set: no action needed.
ACTION_SAFE: int = 254
#: No action leads anywhere: the state is failed or the block impassable.
ACTION_NONE: int = 255

DEFAULT_SOC_BINS: int = 16
MIN_SOC_BINS: int = 8
MAX_SOC_BINS: int = 40
#: The field is float32 P_safe plus uint8 policy per state: 100 M states is
#: 500 MB. Measured on Site11 at coarsen 4 (probe of 5 Sep 2026): about
#: 0.23 s per backward bin at 20 SOC bins over 125 x 125 blocks.
MAX_SURVIVAL_STATES: int = 100_000_000
MAX_SURVIVAL_HORIZON_HOURS: float = 168.0

SURVIVAL_SCOPE: str = (
    "state (time bin, coarse block, SOC bin); actions: the planner's eight moves "
    "and a one-bin wait; failure: a SOC bin under the reserve, a fault hold longer "
    "than h_max_shadow_h in a dark block, or the horizon running out; the "
    "continuous-shadow clock and the thermal envelope are NOT state variables "
    "(the planner's own labels still enforce the shadow clock on the plan). "
    "Energy is cost_engine's: traction, housekeeping with the heater in shadow, "
    "solar income; the fault hold drains at housekeeping power (the catalogue has "
    "no fault-resolution power)."
)

SURVIVAL_CLAIM: str = (
    "MODEL: a reach-avoid value iteration under an ASSUMED Poisson fault model "
    "(rate and recovery time are Lamarre et al.'s experiment values, not a rover "
    "specification) on a coarsened grid with a coarsened time axis; P_safe is the "
    "success probability of the best policy the discretised model can express: "
    "the charge is read by linear interpolation between SOC bin centres (Lamarre's "
    "'interpolation map', unbiased in expectation -- his conservative lower-bin map "
    "charges a whole bin per 20 m move here and is unusable), the time by the worse "
    "of the two neighbouring bins, and every action takes at least one bin (the "
    "field's clock is slower than the rover's). Conservativeness is therefore "
    "EMPIRICAL, checked against a Monte Carlo of the policy in continuous time, "
    "never assumed; P_safe is never a measured rate. The default safe set (goal or haven) is NOT Lamarre's "
    "haven-only set: on Site11 LPR-1 has no haven at any probed epoch. Lamarre's "
    "numbers (41.5 M states, beta 2 percent -> 1.5 percent realised, +0.5 km and "
    "+2 h for the risk-bounded plan) are quoted from the papers, not reproduced."
)

SURVIVAL_REFERENCES: tuple[dict[str, str], ...] = (
    {
        "id": "lamarre_acta_2023",
        "title": "Lamarre, Malhotra, Kelly -- Recovery Policies for Safe Exploration of Lunar Permanently Shadowed Regions by a Solar-Powered Rover (Acta Astronautica 2023)",
        "url": "https://arxiv.org/abs/2307.16786",
        "used_for": "state (cell, time, battery); eight moves + wait; V_k = 1_{X\\O} + 1_{O\\S} min_a E[V_{k+1}]; Poisson faults split into two halves with three outcomes; min-max over the lower/upper time bin and the lower energy bin",
    },
    {
        "id": "lamarre_aero_2024",
        "title": "Lamarre, Malhotra, Kelly -- Safe Mission-Level Path Planning for Exploration of Lunar Shadowed Regions by a Solar-Powered Rover (IEEE Aerospace 2024)",
        "url": "https://arxiv.org/abs/2401.08558",
        "used_for": "the chance constraint Pr{mission failure} <= beta over the trajectory; fault branches closed with the recovery value function; alpha = 1 per 5 000 m, R = 36 000 s",
    },
    {
        "id": "gplanetary_nav",
        "title": "utiasSTARS/gplanetary-nav (MIT)",
        "url": "https://github.com/utiasSTARS/gplanetary-nav",
        "used_for": "terrain/insolation map and planning-graph conventions; the piecewise-constant power time integral pattern (numba_energy). The recovery policy itself is not in the repository",
    },
)

#: Lamarre et al.'s own figures, as read from the two papers' HTML on
#: 5 Sep 2026. Quotations: every one of them is theirs, none is ours.
LAMARRE_QUOTED: dict[str, Any] = {
    "states_experiment_1": 2_500_000,
    "states_experiment_3": 41_500_000,
    "time_bin_s": {"experiment_1": 3600, "experiment_3": 3600, "aero_roi_1": 1800},
    "energy_bin_wh": {"experiment_1": 100, "experiment_3": 250, "aero_roi_1": 150},
    "wait_action_s": 5000,
    "fault_rate_per_km": {"experiment_1": 1.0, "experiment_3": 0.2},
    "recovery_s": {"experiment_1": 18000, "experiment_3": 36000},
    "monte_carlo_trials": {"experiment_3": 100_000, "aero_roi_1": 10_000},
    "aero_beta": 0.02,
    "aero_realised_failure": 0.015,
    "aero_risk_bounded_extra": {"km": 0.5, "hours": 2.0},
    "aero_lunar_night_rule": "SOC >= 50 percent (15 000 Wh) by 26 Sep 2029, hibernating in place",
    "policy_time_s": "about 10 s (smallest discretisation) to 2 500+ s (41.5 M states)",
    "map": "240 m/px, hourly JPL visibility maps, Cabeus area, 1 Aug - 27 Oct 2029, 2 089 maps",
    "power_w": {"drive": "60-300", "idle": "40-80", "hibernate": "30-40", "fault_resolution": "50-80"},
    "battery_wh": "7 000-30 000",
}


# ── the fault model ──────────────────────────────────────────────────────────


def fault_outcome_probabilities(rate_per_km: float, distance_m: float) -> tuple[float, float, float]:
    """Lamarre's three outcomes of one drive of *distance_m* metres.

    ``(no fault, fault in the first half, fault in the second half)`` --
    ``exp(-a rho)``, ``1 - exp(-a rho / 2)`` and ``exp(-a rho / 2) - exp(-a rho)``
    with ``a rho`` the expected number of faults over the drive (Acta 2023
    eq. 2-4). They sum to one; with no fault rate they are ``(1, 0, 0)``.
    """
    expected = max(0.0, float(rate_per_km)) / 1000.0 * max(0.0, float(distance_m))
    if expected <= 0.0:
        return 1.0, 0.0, 0.0
    none = math.exp(-expected)
    half = math.exp(-expected / 2.0)
    return none, 1.0 - half, half - none


# ── the safe set ─────────────────────────────────────────────────────────────


def haven_hibernation_soc_wh(rover: Mapping[str, Any]) -> float:
    """The charge a safe haven requires before the rover may count as safe.

    Lamarre's target set asks for the charge that carries the rover through
    the lunar night at a haven. This catalogue has no per-haven SOC series,
    so the requirement is derived from the endurance the haven definition
    (A1) is built on: the reserve plus full-shadow housekeeping power for
    ``h_max_shadow_h`` hours, capped at capacity.
    """
    e_cap = float(rover["e_cap_wh"])
    reserve = e_cap * float(rover.get("soc_min_pct") or 0.0)
    endurance_h = float(rover.get("h_max_shadow_h") or 0.0)
    if not math.isfinite(endurance_h) or endurance_h < 0.0:
        return e_cap
    return min(e_cap, reserve + housekeeping_power_w(1.0, rover) * endurance_h)


def safe_soc_requirement(
    traversable: np.ndarray,
    haven_mask: np.ndarray | None,
    goal: tuple[int, int] | None,
    rover: Mapping[str, Any],
    safe_set: str,
) -> np.ndarray:
    """``(H, W)`` Wh a block needs on arrival to count as safe; ``inf`` never.

    ``leg``: the goal block at the reserve and every haven block at its
    hibernation charge. ``haven``: the haven blocks only. An impassable
    block is never safe -- the rover cannot be there.
    """
    if safe_set not in SAFE_SETS:
        raise ValueError(f"safe_set must be one of {SAFE_SETS}, not {safe_set!r}")
    passable = np.asarray(traversable, dtype=bool)
    requirement = np.full(passable.shape, np.inf, dtype=np.float64)
    if haven_mask is not None:
        havens = np.asarray(haven_mask, dtype=bool)
        if havens.shape != passable.shape:
            raise ValueError("haven_mask shape must match traversable")
        requirement[havens] = haven_hibernation_soc_wh(rover)
    if safe_set == "leg":
        if goal is None:
            raise ValueError("the leg safe set needs a goal block")
        r, c = int(goal[0]), int(goal[1])
        if not (0 <= r < passable.shape[0] and 0 <= c < passable.shape[1]):
            raise ValueError(f"goal {goal} is outside the {passable.shape} grid")
        reserve = float(rover["e_cap_wh"]) * float(rover.get("soc_min_pct") or 0.0)
        requirement[r, c] = min(requirement[r, c], reserve)
    requirement[~passable] = np.inf
    return requirement


# ── the planner's edges, per direction ───────────────────────────────────────


@dataclass(frozen=True)
class DirectionTables:
    """The eight moves as full-grid tables indexed by the SOURCE cell.

    ``allowed[d, r, c]`` says the move ``OFFSETS[d]`` from ``(r, c)`` passes
    the planner's gates; ``travel_h`` its hours; ``traction_w`` the traction
    power on it; ``distance_m[d]`` its length. Impassable or refused: False,
    inf, 0.
    """

    allowed: np.ndarray
    travel_h: np.ndarray
    distance_m: np.ndarray
    traction_w: np.ndarray


def direction_tables(
    traversable: np.ndarray,
    elevation: np.ndarray | None,
    slope: np.ndarray | None,
    resolution_m: float,
    rover: Mapping[str, Any],
) -> DirectionTables:
    """The same gates and the same travel time as ``astar_4d`` per edge.

    Both cells passable and no corner cut; along-track step slope within
    ``slope_max_deg``; cross-slope within ``slope_lateral_max_deg``; travel
    time from the mean of the two cell slopes through
    ``edge_travel_time_s_array`` (bit-equal to the scalar the planner
    calls). ``safe_haven._gated_edges`` builds the same graph as an edge
    list; ``test_survival`` checks the two agree edge for edge.
    """
    from .safe_haven import _terrain_gradient

    passable = np.asarray(traversable, dtype=bool)
    height, width = passable.shape
    elev = None if elevation is None else np.asarray(elevation, dtype=np.float64)
    slopes = (
        np.zeros(passable.shape, dtype=np.float64)
        if slope is None
        else np.asarray(slope, dtype=np.float64)
    )
    if elev is not None and elev.shape != passable.shape:
        raise ValueError("elevation shape must match traversable")
    if slopes.shape != passable.shape:
        raise ValueError("slope shape must match traversable")

    res = float(resolution_m)
    tan_slope_max = math.tan(math.radians(float(rover["slope_max_deg"])))
    tan_lat_max_sq = math.tan(math.radians(float(rover["slope_lateral_max_deg"]))) ** 2
    p_base_w = float(rover["p_base_w"])
    mu_coeff = float(rover["mu_coeff"])
    if elev is not None:
        grad_row, grad_col = _terrain_gradient(elev, res)

    allowed = np.zeros((8, height, width), dtype=bool)
    travel = np.full((8, height, width), np.inf, dtype=np.float64)
    traction = np.zeros((8, height, width), dtype=np.float64)
    distances = np.zeros(8, dtype=np.float64)
    for d, (d_row, d_col, diagonal) in enumerate(OFFSETS):
        distance_m = res * math.sqrt(2.0) if diagonal else res
        distances[d] = distance_m
        r0, r1 = max(0, -d_row), height - max(0, d_row)
        c0, c1 = max(0, -d_col), width - max(0, d_col)
        if r1 <= r0 or c1 <= c0:
            continue
        src = (slice(r0, r1), slice(c0, c1))
        dst = (slice(r0 + d_row, r1 + d_row), slice(c0 + d_col, c1 + d_col))
        ok = passable[src] & passable[dst]
        if diagonal:
            ok &= passable[(slice(r0, r1), slice(c0 + d_col, c1 + d_col))]
            ok &= passable[(slice(r0 + d_row, r1 + d_row), slice(c0, c1))]
        if elev is not None:
            dz = elev[dst] - elev[src]
            ok &= np.isfinite(dz) & (np.abs(dz) / distance_m <= tan_slope_max)
            norm = math.hypot(d_row, d_col)
            unit_r, unit_c = d_row / norm, d_col / norm
            g_row = 0.5 * (grad_row[src] + grad_row[dst])
            g_col = 0.5 * (grad_col[src] + grad_col[dst])
            lat_tan = np.abs(g_row * -unit_c + g_col * unit_r)
            ok &= lat_tan * lat_tan <= tan_lat_max_sq
        edge_slope = 0.5 * (slopes[src] + slopes[dst])
        hours = edge_travel_time_s_array(edge_slope, distance_m, rover) / 3600.0
        ok &= np.isfinite(hours)
        allowed[d][src] = ok
        travel[d][src] = np.where(ok, hours, np.inf)
        traction[d][src] = np.where(
            ok,
            p_base_w * (1.0 + mu_coeff * np.sin(np.radians(np.maximum(0.0, edge_slope)))),
            0.0,
        )
    return DirectionTables(allowed=allowed, travel_h=travel, distance_m=distances, traction_w=traction)


# ── the time axis ────────────────────────────────────────────────────────────


def bin_shadow_series(series: Sequence[np.ndarray], slices_per_bin: int) -> np.ndarray:
    """``(n_bins, H, W)`` block mean of the planner's per-slice shadow snapshots.

    A bin of ``m`` slices carries the mean exposure of its slices; a last
    bin shorter than ``m`` carries the mean of what it has. With ``m = 1``
    this is the stacked series.
    """
    m = max(1, int(slices_per_bin))
    stacked = np.stack([np.asarray(snapshot, dtype=np.float64) for snapshot in series], axis=0)
    n_slices = stacked.shape[0]
    n_bins = int(math.ceil(n_slices / m))
    out = np.empty((n_bins, *stacked.shape[1:]), dtype=np.float64)
    for index in range(n_bins):
        out[index] = stacked[index * m : min(n_slices, (index + 1) * m)].mean(axis=0)
    return out


def auto_slices_per_bin(
    n_slices_needed: int, n_cells: int, n_soc_bins: int, max_states: int = MAX_SURVIVAL_STATES
) -> int:
    """Smallest ``m`` (planner slices per DP bin) that keeps the field under
    *max_states* states: ``ceil(n_slices * cells * K / max_states)``, at
    least 1."""
    per_slice = max(1, int(n_cells)) * max(1, int(n_soc_bins))
    needed = max(0, int(n_slices_needed)) * per_slice
    return max(1, int(math.ceil(needed / max(1, int(max_states)))))


# ── constants re-exported for the API blocks ─────────────────────────────────

FAILURE_RATE_PER_KM_ASSUMED: float = C.FAILURE_RATE_PER_KM_ASSUMED
FAULT_RECOVERY_HOURS_ASSUMED: float = C.FAULT_RECOVERY_HOURS_ASSUMED
FAILURE_MODEL_SOURCE: str = C.FAILURE_MODEL_SOURCE


# ── the field ────────────────────────────────────────────────────────────────


@dataclass
class _PowerTerms:
    """``housekeeping(e) - solar(1 - e) = base + e * slope`` in watts, so a
    hold's drain is ``base * hours + slope * shadow_hours`` -- the
    piecewise-constant power integral gplanetary-nav's ``numba_energy``
    computes, here on the cumulative shadow-hours of each block."""

    base_w: float
    slope_w: float
    p_solar_w: float


def _power_terms(rover: Mapping[str, Any], solar_gain: float = 1.0) -> _PowerTerms:
    """The affine power law, optionally with C1's panel gain folded in.

    *solar_gain* is a SCALAR on purpose. ``p_solar_w`` enters ``base_w`` and
    ``slope_w`` with opposite signs, and that factorisation is what keeps the
    reach-avoid DP's drain a closed-form integral over cumulative shadow
    hours; a per-bin gain would have to be integrated jointly with the
    exposure and the closed form would be gone. The caller therefore passes
    the MINIMUM gain over the field's horizon, so the survival probability
    is never optimistic about how much charge the array will actually
    collect -- a safety bound may be conservative, not hopeful. The gap
    between the minimum and the mean is measured and reported.
    """
    p_idle_w = float(rover["p_idle_w"])
    p_shadow_w = rover.get("p_shadow_w")
    shadow_extra_w = (
        max(0.0, float(p_shadow_w) - p_idle_w)
        if p_shadow_w is not None
        else float(rover.get("p_heater_w") or 0.0)
    )
    p_solar_w = float(rover.get("p_solar_w") or 0.0) * float(solar_gain)
    return _PowerTerms(base_w=p_idle_w - p_solar_w, slope_w=shadow_extra_w + p_solar_w, p_solar_w=p_solar_w)


@dataclass
class SurvivalField:
    """``P_safe`` and the recovery policy over ``(time bin, block, SOC bin)``.

    ``p_safe[t, r, c, k]`` for ``t`` in ``0 .. n_bins`` -- the last entry
    is the terminal boundary (safe set 1, everything else 0). ``policy``
    has the same shape: ``0-7`` a move in ``OFFSETS`` order, ``ACTION_WAIT``,
    ``ACTION_SAFE`` or ``ACTION_NONE``. The planner reads the field in its
    own slices through ``slices_per_bin``.
    """

    p_safe: np.ndarray
    policy: np.ndarray
    step_hours: float
    slices_per_bin: int
    n_bins: int
    n_soc_bins: int
    soc_bin_wh: float
    e_cap_wh: float
    reserve_wh: float
    exposure: np.ndarray
    cumulative: np.ndarray
    rate_per_km: float
    recovery_h: float
    safe_set: str
    safe_soc_min_wh: np.ndarray
    tables: DirectionTables
    rover: Mapping[str, Any]
    provenance: dict[str, Any] = field(default_factory=dict)
    compute_s: float = 0.0
    h_max_shadow_h: float = math.inf
    #: C1's panel gain, as the single conservative scalar ``_power_terms``
    #: folds into the solar term. 1.0 is the pre-C1 field, bit for bit.
    solar_gain: float = 1.0

    # -- indexing -----------------------------------------------------------

    @property
    def slice_hours(self) -> float:
        return self.step_hours / max(1, int(self.slices_per_bin))

    @property
    def horizon_hours(self) -> float:
        return self.n_bins * self.step_hours

    @property
    def shape(self) -> tuple[int, int]:
        return int(self.p_safe.shape[1]), int(self.p_safe.shape[2])

    @property
    def n_states(self) -> int:
        height, width = self.shape
        return int(self.n_bins) * height * width * int(self.n_soc_bins)

    @property
    def nbytes(self) -> int:
        return int(self.p_safe.nbytes + self.policy.nbytes)

    def soc_bin(self, battery_wh: float) -> int:
        """The SOC bin whose CENTRE is nearest *battery_wh*, clipped to the axis."""
        if self.soc_bin_wh <= 0.0:
            return 0
        position = float(battery_wh) / self.soc_bin_wh - 0.5
        return int(min(self.n_soc_bins - 1, max(0, int(math.floor(position + 0.5)))))

    def _soc_weights(self, battery_wh: float) -> tuple[int, int, float]:
        """``(lower bin, upper bin, weight of the upper)`` bracketing
        *battery_wh* between bin centres, clamped at both ends."""
        if self.soc_bin_wh <= 0.0:
            return 0, 0, 0.0
        position = float(battery_wh) / self.soc_bin_wh - 0.5
        if position <= 0.0:
            return 0, 0, 0.0
        top = self.n_soc_bins - 1
        if position >= top:
            return top, top, 0.0
        lower = int(math.floor(position))
        return lower, min(top, lower + 1), position - lower

    def bins_of_hours(self, hours: float) -> tuple[int, int]:
        """The lower and upper time bins around *hours* (may exceed n_bins)."""
        x = float(hours) / self.step_hours
        lo = int(math.floor(x + 1e-9))
        hi = int(math.ceil(x - 1e-9))
        return lo, max(lo, hi)

    def p_safe_hours(self, hours: float, r: int, c: int, battery_wh: float) -> float:
        """``P_safe`` at a continuous time and charge: the WORSE of the two
        time bins around it (the papers' min-max on the read side), linearly
        interpolated between the two SOC bin centres around the charge; zero
        past the horizon."""
        lo, hi = self.bins_of_hours(hours)
        if lo < 0 or hi > self.n_bins:
            return 0.0
        k_lo, k_hi, weight = self._soc_weights(battery_wh)

        def at(t_bin: int) -> float:
            column = self.p_safe[t_bin, r, c]
            return (1.0 - weight) * float(column[k_lo]) + weight * float(column[k_hi])

        value = at(lo)
        if hi != lo:
            value = min(value, at(hi))
        return value

    def p_safe_at(self, slice_index: int, r: int, c: int, battery_wh: float) -> float:
        """``P_safe`` at a planner slice (see :meth:`p_safe_hours`)."""
        return self.p_safe_hours(float(slice_index) * self.slice_hours, r, c, battery_wh)

    # -- energy -------------------------------------------------------------

    def _cumulative_at(self, r: int, c: int, hours: float) -> float:
        """Shadow-hours of block (r, c) accumulated by *hours*, interpolated
        on the bin grid and held flat past the horizon."""
        x = float(hours) / self.step_hours
        if x <= 0.0:
            return 0.0
        if x >= self.n_bins:
            return float(self.cumulative[self.n_bins, r, c])
        lo = int(math.floor(x))
        frac = x - lo
        a = float(self.cumulative[lo, r, c])
        b = float(self.cumulative[lo + 1, r, c])
        return a + frac * (b - a)

    def recovery_drain_wh(self, r: int, c: int, from_h: float) -> float:
        """Battery drawn holding position at (r, c) for ``recovery_h`` hours
        from *from_h*: housekeeping minus solar, integrated over the block's
        shadow series."""
        terms = _power_terms(self.rover, self.solar_gain)
        shadow_hours = self._cumulative_at(r, c, from_h + self.recovery_h) - self._cumulative_at(r, c, from_h)
        return terms.base_w * self.recovery_h + terms.slope_w * shadow_hours

    def _dark_at(self, r: int, c: int, hours: float) -> bool:
        lo, _hi = self.bins_of_hours(hours)
        index = min(max(0, lo), self.n_bins - 1)
        return bool(self.exposure[index, r, c] >= 0.5)

    def _hold_is_fatal(self, r: int, c: int, from_h: float) -> bool:
        return self.recovery_h > self.h_max_shadow_h + 1e-9 and self._dark_at(r, c, from_h)

    # -- the planner's edge ---------------------------------------------------

    def move_survival_factor(
        self,
        slice_index: int,
        r: int,
        c: int,
        nr: int,
        nc: int,
        battery_wh: float,
        travel_h: float,
        distance_m: float,
        drain_wh: float,
    ) -> tuple[float, float, float, float, float]:
        """``(factor, p_fault_first, p_fault_second, p_safe_first, p_safe_second)``.

        The factor a move multiplies the execution-survival label by: the
        no-fault branch continues on the plan (probability ``p0``); each
        fault branch is closed with ``P_safe`` of the state the fault leaves
        the rover in after the hold (AERO 2024). A hold longer than the
        shadow endurance in a dark block is fatal.
        """
        p0, p1, p2 = fault_outcome_probabilities(self.rate_per_km, distance_m)
        if p1 <= 0.0 and p2 <= 0.0:
            return 1.0, 0.0, 0.0, 1.0, 1.0
        depart_h = float(slice_index) * self.slice_hours
        half_h = depart_h + 0.5 * float(travel_h)
        if self._hold_is_fatal(r, c, half_h):
            ps1 = 0.0
        else:
            battery_1 = min(self.e_cap_wh, float(battery_wh) - 0.5 * float(drain_wh) - self.recovery_drain_wh(r, c, half_h))
            ps1 = 0.0 if battery_1 < self.reserve_wh else self.p_safe_hours(half_h + self.recovery_h, r, c, battery_1)
        arrive_h = depart_h + float(travel_h)
        if self._hold_is_fatal(nr, nc, arrive_h):
            ps2 = 0.0
        else:
            battery_2 = min(self.e_cap_wh, float(battery_wh) - float(drain_wh) - self.recovery_drain_wh(nr, nc, arrive_h))
            ps2 = 0.0 if battery_2 < self.reserve_wh else self.p_safe_hours(arrive_h + self.recovery_h, nr, nc, battery_2)
        return p0 + p1 * ps1 + p2 * ps2, p1, p2, ps1, ps2

    # -- the policy ---------------------------------------------------------

    def best_action(self, slice_index: int, r: int, c: int, battery_wh: float) -> dict[str, Any]:
        """The recovery policy's action at a planner slice, block and charge."""
        hours = float(slice_index) * self.slice_hours
        lo, _hi = self.bins_of_hours(hours)
        k = self.soc_bin(battery_wh)
        p_now = self.p_safe_hours(hours, r, c, battery_wh)
        if lo < 0 or lo > self.n_bins:
            return {"action": ACTION_NONE, "name": "none", "target": None, "p_safe_now": 0.0, "p_safe_next": None}
        code = int(self.policy[lo, r, c, k])
        if code == ACTION_SAFE:
            return {"action": code, "name": "safe", "target": None, "p_safe_now": p_now, "p_safe_next": p_now}
        if code == ACTION_NONE:
            return {"action": code, "name": "none", "target": None, "p_safe_now": p_now, "p_safe_next": None}
        terms = _power_terms(self.rover, self.solar_gain)
        bin_index = min(lo, self.n_bins - 1)
        if code == ACTION_WAIT:
            exposure = float(self.exposure[bin_index, r, c])
            drain = (terms.base_w + exposure * terms.slope_w) * self.step_hours
            battery_next = min(self.e_cap_wh, float(battery_wh) - drain)
            p_next = self.p_safe_hours(hours + self.step_hours, r, c, battery_next)
            return {"action": code, "name": "wait", "target": (r, c), "p_safe_now": p_now, "p_safe_next": p_next}
        d_row, d_col, _diag = OFFSETS[code]
        target = (r + d_row, c + d_col)
        travel_h = float(self.tables.travel_h[code, r, c])
        d_bins = max(1, int(math.ceil(travel_h / self.step_hours - 1e-9)))
        arrival_bin = min(self.n_bins - 1, bin_index + d_bins)
        exposure = 0.5 * (float(self.exposure[bin_index, r, c]) + float(self.exposure[arrival_bin, target[0], target[1]]))
        drain = (float(self.tables.traction_w[code, r, c]) + terms.base_w + exposure * terms.slope_w) * travel_h
        battery_next = min(self.e_cap_wh, float(battery_wh) - drain)
        p_next = self.p_safe_hours(hours + d_bins * self.step_hours, target[0], target[1], battery_next)
        return {
            "action": code,
            "name": ACTION_NAMES[code],
            "target": target,
            "p_safe_now": p_now,
            "p_safe_next": p_next,
        }

    # -- the API block ------------------------------------------------------

    def info(self) -> dict[str, Any]:
        finite = np.isfinite(self.safe_soc_min_wh)
        return {
            "model": SURVIVAL_MODEL_ID,
            "validity": SURVIVAL_VALIDITY,
            "step_hours": round(self.step_hours, 6),
            "slices_per_bin": int(self.slices_per_bin),
            "n_bins": int(self.n_bins),
            "horizon_hours": round(self.horizon_hours, 4),
            "n_soc_bins": int(self.n_soc_bins),
            "soc_bin_wh": round(self.soc_bin_wh, 3),
            "grid": list(self.shape),
            "n_states": self.n_states,
            "nbytes": self.nbytes,
            "safe_set": self.safe_set,
            "safe_cells": int(finite.sum()),
            "failure_model": {
                "rate_per_km": float(self.rate_per_km),
                "recovery_h": float(self.recovery_h),
                "source": FAILURE_MODEL_SOURCE,
                "outcomes": "no fault / fault in the first half (hold at the origin) / fault in the second half (hold at the destination)",
            },
            "compute_s": round(self.compute_s, 3),
            "provenance": dict(self.provenance),
        }


def build_survival_field(
    traversable: np.ndarray,
    elevation: np.ndarray | None,
    slope: np.ndarray | None,
    resolution_m: float,
    rover: Mapping[str, Any],
    shadow_bins: np.ndarray,
    step_hours: float,
    slices_per_bin: int,
    safe_soc_min_wh: np.ndarray,
    n_soc_bins: int = DEFAULT_SOC_BINS,
    failure_rate_per_km: float = FAILURE_RATE_PER_KM_ASSUMED,
    recovery_hours: float = FAULT_RECOVERY_HOURS_ASSUMED,
    provenance: Mapping[str, Any] | None = None,
    safe_set: str = "leg",
    solar_gain: float = 1.0,
) -> SurvivalField:
    """Backward value iteration over ``(bin, block, SOC bin)``.

    ``V[T] = 1`` except on the safe set; for ``t = T-1 .. 0``::

        V[t] = min over actions of  max over time mappings of
               p0 V[no fault] + p1 V[fault, origin] + p2 V[fault, destination]

    with safe states pinned at 0 and failed states (SOC bin under the
    reserve, impassable block) at 1 before the minimum. Every action
    advances at least one bin, so one sweep is exact. A bin's exposure is
    the mean shadow of its planner slices (*shadow_bins*).

    *solar_gain* (C1) scales the array's income. It is one scalar for the
    whole field, and the caller passes the MINIMUM gain over the horizon:
    ``_power_terms`` explains why a per-bin gain would cost the DP its
    closed-form drain, and why a survival bound that is conservative about
    charging is the right kind of wrong.
    """
    t0 = time.perf_counter()
    passable = np.asarray(traversable, dtype=bool)
    height, width = passable.shape
    shadow = np.asarray(shadow_bins, dtype=np.float64)
    if shadow.ndim != 3 or shadow.shape[1:] != (height, width):
        raise ValueError(f"shadow_bins must be (n_bins, {height}, {width}), got {shadow.shape}")
    n_bins = int(shadow.shape[0])
    if n_bins < 1:
        raise ValueError("at least one time bin is needed")
    step = float(step_hours)
    if not (step > 0.0):
        raise ValueError("step_hours must be positive")
    n_soc = int(n_soc_bins)
    if n_soc < 1:
        raise ValueError("n_soc_bins must be positive")
    req = np.asarray(safe_soc_min_wh, dtype=np.float64)
    if req.shape != (height, width):
        raise ValueError("safe_soc_min_wh shape must match traversable")

    tables = direction_tables(passable, elevation, slope, resolution_m, rover)
    e_cap = float(rover["e_cap_wh"])
    reserve = e_cap * float(rover.get("soc_min_pct") or 0.0)
    delta = e_cap / n_soc
    # Every bin is represented by its CENTRE, and a transition's charge is
    # read between the two centres it lands between (linear interpolation).
    # Lamarre's map takes the lower bin, which is conservative when a move
    # drains about a bin (240 m at 0.1 m/s and 300 W: 200 Wh against 250 Wh
    # bins) and hopeless here, where a 20 m move drains 20 Wh against a
    # 271 Wh bin: every dark move cost a whole bin, and the probe of 5 Sep
    # 2026 found P_safe = 0 at the start of the standard day route.
    centre = (np.arange(n_soc, dtype=np.float64) + 0.5) * delta
    failed_bin = centre < reserve - 1e-9
    # A requirement at or above the top bin's centre means "a full battery":
    # VIPER's hibernation charge (reserve + 96 h of shadow power) exceeds its
    # capacity and is capped at e_cap, which no bin centre reaches.
    effective_req = np.where(np.isfinite(req), np.minimum(req, centre[-1]), np.inf)
    safe = (
        (centre[None, None, :] >= effective_req[:, :, None] - 1e-9)
        & passable[:, :, None]
        & ~failed_bin[None, None, :]
    )

    terms = _power_terms(rover, solar_gain)
    net_wait_w = terms.base_w + shadow * terms.slope_w  # (T, H, W), signed
    cumulative = np.concatenate(
        [np.zeros((1, height, width)), np.cumsum(shadow, axis=0) * step], axis=0
    )
    h_max = float(rover.get("h_max_shadow_h") or math.inf)
    if not (h_max > 0.0):
        h_max = math.inf
    recovery_h = float(recovery_hours)
    rate = float(failure_rate_per_km)
    dark_fatal = recovery_h > h_max + 1e-9
    dark = shadow >= 0.5

    V = np.ones((n_bins + 1, height, width, n_soc), dtype=np.float32)
    policy = np.full((n_bins + 1, height, width, n_soc), ACTION_NONE, dtype=np.uint8)
    V[n_bins][safe] = 0.0
    policy[n_bins][safe] = ACTION_SAFE

    k_index = np.arange(n_soc)[None, None, :]
    cell_rows = np.arange(height)[:, None]
    cell_cols = np.arange(width)[None, :]

    def shift_of(drain_wh: np.ndarray) -> np.ndarray:
        """SOC bins lost (negative: gained) by a signed drain, per cell -- a
        real number; the value is interpolated between the two bins around
        ``k - shift``."""
        return np.asarray(drain_wh, dtype=np.float64) / delta

    def value_at_bins(t_bins: np.ndarray, rows: np.ndarray, cols: np.ndarray, shift: np.ndarray, fatal: np.ndarray) -> np.ndarray:
        """V at per-cell arrival bins (H, W) for the cells (rows, cols), with
        a per-cell real SOC shift read between bin centres; bins past the
        boundary and *fatal* cells are failure, a charge under bin 0 is
        failure, a charge over the top bin is the top bin (the cap). Gathers
        only the cells of each distinct arrival bin, so the work is one full
        gather however many bins the cells spread over."""
        out = np.ones((height, width, n_soc), dtype=np.float32)
        valid = ~fatal & (t_bins <= n_bins) & (t_bins >= 0)
        if not valid.any():
            return out
        for t_bin in np.unique(t_bins[valid]):
            here = np.nonzero(valid & (t_bins == t_bin))
            block = V[int(t_bin)][rows[here], cols[here]]  # (n, K) at the target cells
            position = k_index[0] - shift[here][:, None]     # (n, K) real bin position
            lower = np.floor(position)
            weight = (position - lower).astype(np.float32)
            lower = lower.astype(np.int64)
            upper = lower + 1
            v_lo = np.take_along_axis(block, np.clip(lower, 0, n_soc - 1), axis=1)
            v_hi = np.take_along_axis(block, np.clip(upper, 0, n_soc - 1), axis=1)
            v_lo = np.where(lower < 0, np.float32(1.0), v_lo)
            v_hi = np.where(upper < 0, np.float32(1.0), v_hi)
            out[here] = (1.0 - weight) * v_lo + weight * v_hi
        return out

    def hold_drain(rows: np.ndarray, cols: np.ndarray, from_h: np.ndarray) -> np.ndarray:
        """Drain of a ``recovery_h`` hold at cells (rows, cols) starting at
        per-cell hours *from_h*: base power plus the shadow-hours integral."""
        def cum_at(hours: np.ndarray) -> np.ndarray:
            x = np.clip(hours / step, 0.0, float(n_bins))
            lo = np.minimum(np.floor(x).astype(np.int64), n_bins - 1)
            frac = x - lo
            a = cumulative[lo, rows, cols]
            b = cumulative[lo + 1, rows, cols]
            return a + frac * (b - a)

        shadow_hours = cum_at(from_h + recovery_h) - cum_at(from_h)
        return terms.base_w * recovery_h + terms.slope_w * shadow_hours

    def dark_at(rows: np.ndarray, cols: np.ndarray, hours: np.ndarray) -> np.ndarray:
        index = np.clip(np.floor(hours / step + 1e-9).astype(np.int64), 0, n_bins - 1)
        return dark[index, rows, cols]

    same_rows = np.broadcast_to(cell_rows, (height, width))
    same_cols = np.broadcast_to(cell_cols, (height, width))
    no_fatal = np.zeros((height, width), dtype=bool)

    for t in range(n_bins - 1, -1, -1):
        now_h = t * step
        best = np.ones((height, width, n_soc), dtype=np.float32)
        choice = np.full((height, width, n_soc), ACTION_NONE, dtype=np.uint8)

        # Moves first, the wait last, each replacing only a STRICTLY worse
        # value: on a tie the policy names a move (which way to go) rather
        # than a wait, and the first equally good move in OFFSETS order.
        for d, (d_row, d_col, _diag) in enumerate(OFFSETS):
            allowed = tables.allowed[d]
            if not allowed.any():
                continue
            tau = np.where(allowed, tables.travel_h[d], 0.0)
            rho = float(tables.distance_m[d])
            target_rows = np.clip(same_rows + d_row, 0, height - 1)
            target_cols = np.clip(same_cols + d_col, 0, width - 1)
            d_lo = np.maximum(1, np.floor(tau / step + 1e-9)).astype(np.int64)
            d_hi = np.maximum(1, np.ceil(tau / step - 1e-9)).astype(np.int64)
            # Exposure over the move: the origin now, the destination on arrival.
            arrival_index = np.clip(t + d_hi, 0, n_bins - 1)
            exposure = 0.5 * (shadow[t] + shadow[arrival_index, target_rows, target_cols])
            drain = (tables.traction_w[d] + terms.base_w + exposure * terms.slope_w) * tau
            move_shift = shift_of(drain)
            p0, p1, p2 = fault_outcome_probabilities(rate, rho)

            expect = p0 * np.maximum(
                value_at_bins(t + d_lo, target_rows, target_cols, move_shift, no_fatal),
                value_at_bins(t + d_hi, target_rows, target_cols, move_shift, no_fatal),
            )
            if p1 > 0.0 or p2 > 0.0:
                # Fault in the first half: hold at the origin from now + tau/2.
                half_h = now_h + 0.5 * tau
                fatal_1 = dark_at(same_rows, same_cols, half_h) if dark_fatal else no_fatal
                shift_1 = shift_of(0.5 * drain + hold_drain(same_rows, same_cols, half_h))
                x1 = (half_h + recovery_h) / step
                lo_1 = np.floor(x1 + 1e-9).astype(np.int64)
                hi_1 = np.ceil(x1 - 1e-9).astype(np.int64)
                v1 = np.maximum(
                    value_at_bins(lo_1, same_rows, same_cols, shift_1, fatal_1),
                    value_at_bins(hi_1, same_rows, same_cols, shift_1, fatal_1),
                )
                # Fault in the second half: hold at the destination from arrival.
                arrive_h = now_h + tau
                fatal_2 = dark_at(target_rows, target_cols, arrive_h) if dark_fatal else no_fatal
                shift_2 = shift_of(drain + hold_drain(target_rows, target_cols, arrive_h))
                x2 = (arrive_h + recovery_h) / step
                lo_2 = np.floor(x2 + 1e-9).astype(np.int64)
                hi_2 = np.ceil(x2 - 1e-9).astype(np.int64)
                v2 = np.maximum(
                    value_at_bins(lo_2, target_rows, target_cols, shift_2, fatal_2),
                    value_at_bins(hi_2, target_rows, target_cols, shift_2, fatal_2),
                )
                expect = expect + p1 * v1 + p2 * v2
            better = allowed[:, :, None] & (expect < best - 1e-9)
            best = np.where(better, expect, best)
            choice = np.where(better, np.uint8(d), choice)

        # WAIT: one bin in place, no fault.
        wait_shift = shift_of(net_wait_w[t] * step)
        wait_value = value_at_bins(np.full((height, width), t + 1), same_rows, same_cols, wait_shift, no_fatal)
        better = wait_value < best - 1e-9
        best = np.where(better, wait_value, best)
        choice = np.where(better, np.uint8(ACTION_WAIT), choice)

        best[safe] = 0.0
        choice[safe] = ACTION_SAFE
        best[:, :, failed_bin] = 1.0
        choice[:, :, failed_bin] = ACTION_NONE
        best[~passable] = 1.0
        choice[~passable] = ACTION_NONE
        # An action whose value is certain failure is no action.
        choice = np.where(best >= 1.0 - 1e-7, np.uint8(ACTION_NONE), choice)
        choice[safe] = ACTION_SAFE
        V[t] = best
        policy[t] = choice

    return SurvivalField(
        p_safe=(1.0 - V).astype(np.float32),
        policy=policy,
        step_hours=step,
        slices_per_bin=max(1, int(slices_per_bin)),
        n_bins=n_bins,
        n_soc_bins=n_soc,
        soc_bin_wh=delta,
        e_cap_wh=e_cap,
        reserve_wh=reserve,
        exposure=shadow,
        cumulative=cumulative,
        rate_per_km=rate,
        recovery_h=recovery_h,
        safe_set=safe_set,
        safe_soc_min_wh=req,
        tables=tables,
        rover=rover,
        provenance=dict(provenance or {}),
        compute_s=time.perf_counter() - t0,
        h_max_shadow_h=h_max,
        solar_gain=float(solar_gain),
    )


# ── Monte Carlo of the policy ────────────────────────────────────────────────


def _plan_legs_for_rollout(field: SurvivalField, plan_states: Sequence[Any]) -> list[tuple[int, int, int]]:
    """``(direction or ACTION_WAIT, row, col)`` per plan edge, validated
    against the field's tables; ``ValueError`` names a bad edge."""
    raw = [tuple(int(v) for v in state) for state in plan_states]
    if len(raw) < 2:
        raise ValueError("a plan needs at least two states")
    height, width = field.shape
    legs: list[tuple[int, int, int]] = []
    for index in range(len(raw) - 1):
        (r0, c0, _t0), (r1, c1, _t1) = raw[index][:3], raw[index + 1][:3]
        if not (0 <= r0 < height and 0 <= c0 < width):
            raise ValueError(f"plan state {index} ({r0}, {c0}) is outside the {height}x{width} grid")
        if (r0, c0) == (r1, c1):
            legs.append((ACTION_WAIT, r0, c0))
            continue
        direction = next(
            (d for d, (dr, dc, _diag) in enumerate(OFFSETS) if (r0 + dr, c0 + dc) == (r1, c1)),
            None,
        )
        if direction is None:
            raise ValueError(f"plan states {index} and {index + 1} are not adjacent: ({r0}, {c0}) -> ({r1}, {c1})")
        if not field.tables.allowed[direction, r0, c0]:
            raise ValueError(f"plan edge {index} ({r0}, {c0}) -> ({r1}, {c1}) is not drivable in the field")
        legs.append((direction, r0, c0))
    return legs


def rollout(
    field: SurvivalField,
    start: tuple[int, int],
    battery_wh: float,
    n_runs: int,
    seed: int,
    start_slice: int = 0,
    plan_states: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Execute the recovery policy ``n_runs`` times in CONTINUOUS time and
    charge -- Lamarre's own check of a policy.

    Every run keeps a real clock (hours) and a real battery (Wh); the policy
    is read at the floor bin of both, so the discretisation is exercised
    rather than replayed. Faults are drawn per move with the same three
    outcomes the field assumed; a fault holds the rover ``recovery_h`` hours
    at housekeeping power. With *plan_states* the runs first follow the plan
    (waits and moves as given) and switch to the policy only after a fault;
    without, they follow the policy from the start. A run ends SAFE on
    entering the safe set with the required charge, FAILED under the
    reserve, after a fatal dark hold, or past the horizon.
    """
    rng = np.random.default_rng(int(seed))
    n = int(n_runs)
    if n <= 0:
        raise ValueError("n_runs must be positive")
    r0, c0 = int(start[0]), int(start[1])
    legs = None if plan_states is None else _plan_legs_for_rollout(field, plan_states)
    if legs is not None and (legs[0][1], legs[0][2]) != (r0, c0):
        raise ValueError(f"the plan starts at {(legs[0][1], legs[0][2])}, not at {start}")
    terms = _power_terms(field.rover, field.solar_gain)
    step = field.step_hours
    horizon = field.horizon_hours
    req = field.safe_soc_min_wh
    tables = field.tables

    clock = float(start_slice) * field.slice_hours
    outcomes = np.zeros(n, dtype=np.int8)  # 0 running, 1 safe, 2 failed, 3 horizon
    faults = np.zeros(n, dtype=np.int64)
    predicted = 1.0 - field.p_safe_hours(clock, r0, c0, battery_wh)

    def exposure_at(r: int, c: int, hours: float) -> float:
        index = min(field.n_bins - 1, max(0, int(math.floor(hours / step + 1e-9))))
        return float(field.exposure[index, r, c])

    for run in range(n):
        t = clock
        battery = float(battery_wh)
        r, c = r0, c0
        on_plan = legs is not None
        leg_index = 0
        steps = 0
        max_steps = field.n_bins * 4 + (0 if legs is None else len(legs)) + 8
        while outcomes[run] == 0:
            steps += 1
            if steps > max_steps:
                outcomes[run] = 3
                break
            if t > horizon + 1e-9:
                outcomes[run] = 3
                break
            if battery < field.reserve_wh - 1e-9:
                outcomes[run] = 2
                break
            if battery >= float(req[r, c]) - 1e-9:
                outcomes[run] = 1
                break
            if on_plan:
                if leg_index >= len(legs):
                    # The plan is over and the rover is not safe: hand over
                    # to the policy from here.
                    on_plan = False
                    continue
                action = legs[leg_index][0]
                leg_index += 1
            else:
                best = field.best_action(int(round(t / field.slice_hours)), r, c, battery)
                action = int(best["action"])
                if action == ACTION_SAFE:
                    outcomes[run] = 1
                    break
                if action == ACTION_NONE:
                    outcomes[run] = 2
                    break
            if action == ACTION_WAIT:
                # A planned wait is one planner slice; the policy's wait is
                # one DP bin (the field's own action).
                hold = field.slice_hours if on_plan else step
                exposure = exposure_at(r, c, t)
                battery = min(field.e_cap_wh, battery - (terms.base_w + exposure * terms.slope_w) * hold)
                t += hold
                continue
            d_row, d_col, _diag = OFFSETS[action]
            if not tables.allowed[action, r, c]:
                outcomes[run] = 2
                break
            nr, nc = r + d_row, c + d_col
            tau = float(tables.travel_h[action, r, c])
            rho = float(tables.distance_m[action])
            exposure = 0.5 * (exposure_at(r, c, t) + exposure_at(nr, nc, t + tau))
            drain = (float(tables.traction_w[action, r, c]) + terms.base_w + exposure * terms.slope_w) * tau
            p0, p1, _p2 = fault_outcome_probabilities(field.rate_per_km, rho)
            u = rng.random()
            if u < p0:
                battery = min(field.e_cap_wh, battery - drain)
                t += tau
                r, c = nr, nc
                continue
            faults[run] += 1
            on_plan = False
            if u < p0 + p1:
                # First half: back in the origin block, half the drive paid.
                hold_from = t + 0.5 * tau
                battery = min(field.e_cap_wh, battery - 0.5 * drain)
                hold_r, hold_c = r, c
            else:
                hold_from = t + tau
                battery = min(field.e_cap_wh, battery - drain)
                hold_r, hold_c = nr, nc
            if field._hold_is_fatal(hold_r, hold_c, hold_from):
                outcomes[run] = 2
                break
            battery = min(field.e_cap_wh, battery - field.recovery_drain_wh(hold_r, hold_c, hold_from))
            t = hold_from + field.recovery_h
            r, c = hold_r, hold_c

    from .stress_test import wilson_interval

    n_safe = int(np.count_nonzero(outcomes == 1))
    n_failed = int(np.count_nonzero(outcomes == 2))
    n_horizon = int(np.count_nonzero(outcomes == 3))
    n_bad = n_failed + n_horizon
    low, high = wilson_interval(n_bad, n)
    return {
        "n_runs": n,
        "seed": int(seed),
        "safe": n_safe,
        "failed": n_failed,
        "horizon": n_horizon,
        "failure_rate": n_bad / n,
        "wilson_low": low,
        "wilson_high": high,
        "predicted_failure": float(predicted),
        "conservative": bool(predicted + 1e-9 >= n_bad / n),
        "mean_faults": float(faults.mean()),
        "followed_plan": legs is not None,
        "start_hours": clock,
        "battery_wh": float(battery_wh),
    }


# ── the API blocks ───────────────────────────────────────────────────────────


def survival_block(
    field: SurvivalField | None,
    result: Mapping[str, Any] | None,
    beta: float | None,
    requested: bool,
    reason: str | None = None,
    shadow_model: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """The ``survival`` block of a plan response.

    Not requested, or requested and unavailable: ``requested``, ``applied``
    and the ``reason``. With a field: the field's identity and size, the
    failure model with its source, the route's execution failure
    probability and recovery probabilities as the planner reported them,
    beta and whether it was enforced, the claim and the references.
    """
    if field is None:
        return {
            "requested": bool(requested),
            "applied": False,
            "reason": reason or "no survival field",
            "validity": SURVIVAL_VALIDITY,
            "model": SURVIVAL_MODEL_ID,
        }
    metrics = dict((result or {}).get("metrics") or {})
    recovery = (result or {}).get("path_recovery_prob") or []
    route = {
        "execution_failure_probability": metrics.get("execution_failure_probability"),
        "min_recovery_prob": metrics.get("min_recovery_prob"),
        "mean_recovery_prob": (
            round(float(np.mean([float(v) for v in recovery])), 6) if recovery else None
        ),
        "start_recovery_prob": metrics.get("start_recovery_prob"),
        "moves_refused": int((metrics.get("edges_rejected") or {}).get("failure_probability", 0) or 0),
    }
    info = field.info()
    return {
        "requested": bool(requested),
        "applied": beta is not None,
        "beta": None if beta is None else float(beta),
        "validity": SURVIVAL_VALIDITY,
        "model": SURVIVAL_MODEL_ID,
        "safe_set": field.safe_set,
        "safe_set_definition": (
            "goal block at the reserve charge, plus every safe haven block at its hibernation charge"
            if field.safe_set == "leg"
            else "safe haven blocks at their hibernation charge only (Lamarre's target set)"
        ),
        "failure_model": info["failure_model"],
        "field": {key: info[key] for key in (
            "step_hours", "slices_per_bin", "n_bins", "horizon_hours", "n_soc_bins", "soc_bin_wh",
            "grid", "n_states", "nbytes", "safe_cells", "compute_s",
        )},
        "route": route,
        "shadow_model": None if shadow_model is None else dict(shadow_model),
        "scope": SURVIVAL_SCOPE,
        "claim": SURVIVAL_CLAIM,
        "quoted": LAMARRE_QUOTED,
        "references": list(SURVIVAL_REFERENCES),
    }


def recovery_suggestion(
    field: SurvivalField,
    r: int,
    c: int,
    battery_wh: float,
    coarsen: int,
    slice_index: int = 0,
) -> dict[str, Any]:
    """The recovery policy's advice at one state, for ``/api/replan`` and
    ``/api/cell-telemetry``: the action, where it leads (coarse block and
    the block's centre pixel on the fine grid), ``P_safe`` now and after."""
    best = field.best_action(int(slice_index), int(r), int(c), float(battery_wh))
    factor = max(1, int(coarsen))
    offset = factor // 2
    target = best["target"]
    e_cap = field.e_cap_wh
    return {
        "action": int(best["action"]),
        "action_name": best["name"],
        "target_block": None if target is None else [int(target[0]), int(target[1])],
        "target_pixel": (
            None if target is None else [int(target[0]) * factor + offset, int(target[1]) * factor + offset]
        ),
        "p_safe_now": round(float(best["p_safe_now"]), 6),
        "p_safe_next": None if best["p_safe_next"] is None else round(float(best["p_safe_next"]), 6),
        "soc_frac": round(float(battery_wh) / e_cap, 6) if e_cap > 0.0 else None,
        "hours": round(float(slice_index) * field.slice_hours, 4),
        "block": [int(r), int(c)],
        "safe_set": field.safe_set,
        "validity": SURVIVAL_VALIDITY,
        "model": SURVIVAL_MODEL_ID,
        "failure_model": field.info()["failure_model"],
        "claim": SURVIVAL_CLAIM,
    }


# ── a small cache: two fields of up to 200 MB each ──────────────────────────

_CACHE_LIMIT: int = 2
_cache: dict[tuple, Any] = {}


def clear_survival_cache() -> None:
    _cache.clear()


def cached_survival_field(key: tuple, builder):
    """The field for *key*, built by *builder* on a miss; the oldest of
    ``_CACHE_LIMIT`` entries is evicted."""
    hit = _cache.get(key)
    if hit is not None:
        return hit
    value = builder()
    if len(_cache) >= _CACHE_LIMIT:
        _cache.pop(next(iter(_cache)))
    _cache[key] = value
    return value
