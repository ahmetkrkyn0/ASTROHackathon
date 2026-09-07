"""The rover's thermal dwell: how long it may stand still (C6).

LunaPath's thermal check used to be STATIC: a cell's annual-peak or
cold-end surface temperature, mapped to an inner temperature with the
catalogue's offsets, read against the battery and electronics envelopes.
D3 measured what that says on Site11 -- every real route violates LP-R04
and LP-R05 -- because the equilibrium inner temperature sits outside the
envelope and the model has neither a time axis nor a heater.

NASA JSC/MSFC built two frameworks for VIPER around exactly this question
(Slusser, Turk, Stewart, Page, Barragan, Mittag, ICES-2025-376): the
UNLIMITED OPERATIONS ENVELOPE -- the geometries in which the parked rover
never exceeds an allowable flight temperature (AFT) -- and the TOLERABLE
ENTRENCHED TIME -- how long an immobilised rover may stay put before "the
clock runs out". This module builds both with LunaPath's own model:

* the inner temperature relaxes toward ``surface_to_inner(surface(t))``
  with the catalogue's ``thermal_tau_s`` (first-order lag; the same
  closed form :func:`app.thermal_model.relax_surface_c` applies to the
  regolith skin), where ``surface(t)`` is the per-slice surface the 4-D
  cost cube already integrates;
* ``max_dwell_h[t, y, x]`` is the time that lag takes to leave the
  tightest declared envelope when the rover arrives at slice ``t`` with a
  nominal inner temperature -- computed in closed form for every start
  slice at once;
* the planner may refuse any wait longer than the cell's dwell; the
  replan endpoint counts down from an entrenchment; heat1d's transient at
  the site's latitude is binned into (Sun elevation x Sun-parallel slope)
  to draw the counterpart of JSC's envelope chart.

What is JSC's and what is ours is stated in ``THERMAL_DWELL_CLAIM`` and
``JSC_QUOTED``; every response carries both. The thermal model itself is
MODEL / UNCALIBRATED (see :data:`app.thermal_model.REGOLITH_LAG_VALIDITY`)
and nothing here claims thermal accuracy; the heater enters the
temperature model only as an EXPLICIT, labelled assumption
(``heater_model="thermostat_assumed"``), never by default.
"""

from __future__ import annotations

import math
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from . import constants as C
from .thermal_model import (
    REGOLITH_LAG_VALIDITY,
    REGOLITH_THERMAL_TAU_S,
    relax_surface_c,
    shadowed_equilibrium_c,
)

# ── identity, claim, references, quotations ─────────────────────────────────

THERMAL_DWELL_MODEL_ID: str = "inner_temperature_first_order_lag_v1"
THERMAL_DWELL_VALIDITY: str = "MODEL"

#: How the heater enters the TEMPERATURE model. ``none``: it does not (the
#: catalogue has no W-to-K link; the heater is counted in the energy model
#: only, as before). ``thermostat_assumed``: the ASSUMPTION that the heater
#: holds the inner temperature at the envelope's lower bound -- see
#: :data:`app.constants.HEATER_THERMOSTAT_ASSUMPTION_SOURCE`.
HEATER_MODELS: tuple[str, ...] = ("none", "thermostat_assumed")

SIDE_NONE: int = 0
SIDE_COLD: int = 1
SIDE_HOT: int = 2
SIDE_NAMES: dict[int, str | None] = {SIDE_NONE: None, SIDE_COLD: "cold", SIDE_HOT: "hot"}

COMPONENT_NONE: int = 0
COMPONENT_BATTERY: int = 1
COMPONENT_ELECTRONICS: int = 2
COMPONENT_NAMES: dict[int, str | None] = {
    COMPONENT_NONE: None,
    COMPONENT_BATTERY: "battery",
    COMPONENT_ELECTRONICS: "electronics",
}
_COMPONENT_CODES: dict[str, int] = {"battery": COMPONENT_BATTERY, "electronics": COMPONENT_ELECTRONICS}

THERMAL_DWELL_SCOPE: str = (
    "inner temperature = first-order lag with the rover's thermal_tau_s toward "
    "surface_to_inner(surface(t)); surface(t) = the cost cube's per-slice regolith "
    "state (shadowed equilibrium relaxed with the regolith constant); envelope = the "
    "tightest declared battery/electronics operating range; max_dwell_h[t, y, x] = "
    "the time that lag takes to leave the envelope when the rover arrives at slice t "
    "with the nominal (or given) inner temperature; the heater enters the temperature "
    "model only under heater_model='thermostat_assumed'."
)

THERMAL_DWELL_CLAIM: str = (
    "MODEL, uncalibrated: the surface temperature is heat1d's (slope x aspect) annual "
    "peak coupled to the SPICE shadow series with an UNCALIBRATED regolith lag, and "
    "the inner temperature is the catalogue's piecewise offset model relaxed with the "
    "catalogue's thermal_tau_s; no Diviner comparison is made here (C5). The offsets "
    "are piecewise on the surface sign, so the surfaces that map into the LPR-1/VIPER "
    "battery envelope are -60..-25 C (cold branch) and 40..75 C (hot branch): a "
    "'hot-limited' verdict on a -25..0 C surface is that offset model, not overheating. "
    "The heater has no sourced W-to-K link; heater_model='thermostat_assumed' is an "
    "explicit assumption and the default is 'none'. The dwell cube assumes the rover "
    "arrives at its nominal inner temperature; the route trace integrates the actual "
    "one. JSC's envelope axes (slope x Sun azimuth relative to the rover heading, at "
    "the mission's maximum Sun elevation) need a rover body model LunaPath does not "
    "have; ours are Sun elevation x Sun-parallel slope from heat1d's transient -- the "
    "same method on our model, not a comparison. JSC's numbers are quoted, never mixed "
    "with a measurement."
)

THERMAL_DWELL_REFERENCES: tuple[dict[str, str], ...] = (
    {
        "id": "slusser_ices_2025",
        "title": (
            "Slusser, Turk, Stewart, Page, Barragan, Mittag -- Generalizing Lunar Vehicle "
            "Thermal Analysis: Lessons Learned from VIPER (ICES-2025-376, 54th International "
            "Conference on Environmental Systems, Prague, July 2025)"
        ),
        "url": "https://ntrs.nasa.gov/api/citations/20250004028/downloads/ICES-2025-376_Final.pdf",
        "used_for": (
            "the unlimited-operations-envelope idea (bounding hot cases, slope parallel to the "
            "Sun azimuth, maximum mission Sun elevation, AFT-exceedance normalisation) and the "
            "tolerable-entrenched-time framing (time an immobilised rover may stay put before it "
            "can no longer reach the safe haven; thermal transients bounded by that time)"
        ),
    },
    {
        "id": "hayne_2017_heat1d",
        "title": "Hayne et al. 2017 -- heat1d, 1-D lunar regolith thermal model (GitHub main, slope/slope_az)",
        "url": "https://github.com/phayne/heat1d",
        "used_for": "surface temperature LUT and the envelope transient at the site's latitude",
    },
)

#: JSC's own figures as read from the PDF on 5 Sep 2026. Quotations: every
#: one of them is theirs, none is ours.
JSC_QUOTED: dict[str, Any] = {
    "source": "ICES-2025-376 (Slusser et al. 2025), read 5 Sep 2026",
    "max_polar_sun_elevation_deg": 1.5,
    "sun_elevation_rule": (
        "the maximum solar elevation angle at the lunar poles is 1.5 deg, increasing by one "
        "degree for every degree in latitude from the pole (Sec. III.D)"
    ),
    "envelope_axes": (
        "downslope solar azimuth angle relative to the rover heading (angular, 16 evenly "
        "spaced) vs slope angle (radial, 0-15 deg in 3 deg steps); the slope direction is "
        "kept parallel to the solar azimuth and the solar elevation is the mission maximum; "
        "the rover is parked in its highest continuous power state (Sec. V.G)"
    ),
    "case_matrix": 96,
    "case_matrix_note": "16 azimuths x 6 slopes, steady-state; negative (Sun-averted) slopes left out as more benign",
    "components_screened": "more than 60 critical components",
    "aft_exceedance_example": {
        "component": "an avionics box",
        "aft_c": 65.0,
        "modelled_c": 77.0,
        "exceedance_c": 12.0,
        "note": "the normalisation example (Sec. V.G), not a specific slope/elevation case",
    },
    "parked_hotspot_onset": "typically a few hours (Sec. V.H, Fig. 12)",
    "tolerable_entrenched_time": (
        "the finite time a vehicle may remain static after a mobility fault before it can no "
        "longer complete the direct traverse and arrive at the destination safe haven before "
        "lunar night; off-nominal thermal transients are bounded by it (Sec. V.H)"
    ),
    "entrenched_time_caveats": (
        "does not take into account state-of-charge variances, transient shadow allowances, "
        "or a fault anywhere along a nominal traverse; VIPER's speed means it is always at risk "
        "of reaching thermal balance with its environment (Sec. V.H)"
    ),
    "safe_haven_night_hours": {"shortest": 50.0, "typical_range": [85.0, 150.0]},
    "tool": "Thermal Desktop",
}


# ── envelope and inner-temperature target ───────────────────────────────────


@dataclass(frozen=True)
class Envelope:
    """The tightest declared inner-temperature envelope and who owns each end."""

    lo: float
    hi: float
    lo_component: str
    hi_component: str

    @property
    def components(self) -> list[str]:
        names = [self.lo_component]
        if self.hi_component not in names:
            names.append(self.hi_component)
        return names

    def as_dict(self) -> dict[str, Any]:
        return {
            "lo_c": self.lo,
            "hi_c": self.hi,
            "lo_component": self.lo_component,
            "hi_component": self.hi_component,
        }


_ENVELOPE_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("battery", "bat_op_min_c", "bat_op_max_c"),
    ("electronics", "elec_op_min_c", "elec_op_max_c"),
)


def rover_envelope(rover: Mapping[str, Any]) -> Envelope | None:
    """The intersection of every declared operating range, or None when the
    rover declares none. The battery is listed first, so a tie names it."""
    lows: list[tuple[float, str]] = []
    highs: list[tuple[float, str]] = []
    for name, lo_key, hi_key in _ENVELOPE_FIELDS:
        lo, hi = rover.get(lo_key), rover.get(hi_key)
        if lo is not None:
            lows.append((float(lo), name))
        if hi is not None:
            highs.append((float(hi), name))
    if not lows or not highs:
        return None
    lo_value, lo_name = max(lows, key=lambda item: item[0])
    hi_value, hi_name = min(highs, key=lambda item: item[0])
    return Envelope(lo_value, hi_value, lo_name, hi_name)


def nominal_inner_c(rover: Mapping[str, Any]) -> float | None:
    """The midpoint of the tightest envelope: the inner temperature a rover is
    taken to arrive with when nothing better is known."""
    env = rover_envelope(rover)
    return None if env is None else 0.5 * (env.lo + env.hi)


def inner_target_c(surface_c: np.ndarray | float, rover: Mapping[str, Any]) -> np.ndarray:
    """``cost_engine.surface_to_inner`` over an array: the cold offset below
    0 C surface, the hot offset at or above it; the surface itself when the
    rover declares no offsets."""
    surface = np.asarray(surface_c, dtype=np.float64)
    cold = rover.get("thermal_offset_cold")
    hot = rover.get("thermal_offset_hot")
    if cold is None or hot is None:
        return surface.copy()
    return np.where(surface < 0.0, surface + float(cold), surface + float(hot))


def apply_heater(target_c: np.ndarray, envelope: Envelope, heater_model: str) -> np.ndarray:
    """The target the inner temperature relaxes toward under *heater_model*.

    ``none`` leaves it alone; ``thermostat_assumed`` clamps it at the lower
    bound (the heater holds the cold side, never the hot one)."""
    if heater_model not in HEATER_MODELS:
        raise ValueError(f"unknown heater_model {heater_model!r}; expected one of {HEATER_MODELS}")
    target = np.asarray(target_c, dtype=np.float64)
    if heater_model == "thermostat_assumed":
        return np.maximum(target, float(envelope.lo))
    return target.copy()


def exit_time_h(
    inner_c: np.ndarray | float,
    target_c: np.ndarray | float,
    envelope: Envelope,
    tau_s: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Hours until a first-order lag from *inner_c* toward a CONSTANT
    *target_c* leaves ``[lo, hi]``, with the side and the component whose
    bound is crossed.

    Already outside -> 0 on that side; target inside -> +inf (never);
    target below lo -> tau ln((T - g)/(lo - g)); above hi -> tau ln((g - T)/(g - hi)).
    """
    T = np.asarray(inner_c, dtype=np.float64)
    g = np.asarray(target_c, dtype=np.float64)
    T, g = np.broadcast_arrays(T, g)
    lo, hi = float(envelope.lo), float(envelope.hi)
    tau = float(tau_s)
    lo_code = _COMPONENT_CODES[envelope.lo_component]
    hi_code = _COMPONENT_CODES[envelope.hi_component]

    hours = np.full(T.shape, np.inf, dtype=np.float64)
    side = np.full(T.shape, SIDE_NONE, dtype=np.int8)
    comp = np.full(T.shape, COMPONENT_NONE, dtype=np.int8)

    below = T < lo
    above = T > hi
    inside = ~(below | above)
    hours[below] = 0.0
    side[below] = SIDE_COLD
    comp[below] = lo_code
    hours[above] = 0.0
    side[above] = SIDE_HOT
    comp[above] = hi_code

    cold = inside & (g < lo)
    with np.errstate(divide="ignore", invalid="ignore"):
        hours[cold] = tau * np.log((T[cold] - g[cold]) / (lo - g[cold])) / 3600.0
    side[cold] = SIDE_COLD
    comp[cold] = lo_code

    hot = inside & (g > hi)
    with np.errstate(divide="ignore", invalid="ignore"):
        hours[hot] = tau * np.log((g[hot] - T[hot]) / (g[hot] - hi)) / 3600.0
    side[hot] = SIDE_HOT
    comp[hot] = hi_code

    nan = np.isnan(T) | np.isnan(g)
    hours[nan] = np.nan
    return hours, side, comp


def dwell_unavailable_reason(rover: Mapping[str, Any]) -> str | None:
    """Why no dwell can be timed for *rover*, or None when it can."""
    tau = rover.get("thermal_tau_s")
    if tau is None or not float(tau) > 0.0:
        return (
            "rover declares no thermal_tau_s: the inner-temperature lag cannot be timed "
            "(no regolith constant is substituted for the vehicle's)"
        )
    if rover_envelope(rover) is None:
        return "rover declares no thermal envelope (bat_op_*/elec_op_*)"
    return None


def heater_source(heater_model: str) -> str | None:
    """The assumption string a response carries under ``thermostat_assumed``."""
    return C.HEATER_THERMOSTAT_ASSUMPTION_SOURCE if heater_model == "thermostat_assumed" else None


# ── the dwell cube ───────────────────────────────────────────────────────────

#: Start slices x blocks the cube is computed for before the start axis is
#: binned (every m-th planner slice becomes one start bin; the planner's
#: constraint reads the per-slice TARGET series, not the cube, so binning
#: only coarsens the report). Site11 at coarsen 4 is 15 625 blocks: the day
#: route's 120 slices bin at m = 2 (1.2 s instead of 2.6 s unbinned), the
#: lunar night's 270 at m = 5, VIPER's 43 stay unbinned -- measured on
#: 5 Sep 2026; the cube is built on every /api/plan-4d call.
DWELL_MAX_STATES: int = 1_000_000


@dataclass
class DwellCube:
    """``max_dwell_h[t, y, x]``: hours a rover arriving in block (y, x) at
    slice ``t`` with ``initial_inner_c`` may stand still before its inner
    temperature leaves the envelope. ``+inf`` where it never does before
    the series ends (open-ended; ``lookahead_h[t]`` says how far the model
    looked), NaN where the block is impassable. ``side``/``component`` name
    the bound that ends the dwell (0 where open-ended)."""

    max_dwell_h: np.ndarray
    side: np.ndarray
    component: np.ndarray
    lookahead_h: np.ndarray
    slice_hours: float
    slices_per_bin: int
    n_slices: int
    initial_inner_c: float
    heater_model: str
    tau_s: float
    envelope: Envelope
    compute_ms: float
    initial_outside_envelope: bool
    #: (T, H, W) inner-temperature target per slice (the heater already
    #: applied): what the planner integrates a label's inner temperature
    #: toward, slice by slice, so its check and this cube share one physics.
    target_c: np.ndarray

    @property
    def n_states(self) -> int:
        return int(np.prod(self.max_dwell_h.shape))

    @property
    def decay(self) -> float:
        """``exp(-slice / tau)``: the fraction of an offset left after one slice."""
        return math.exp(-self.slice_hours * 3600.0 / self.tau_s)

    def inside(self, inner_c: float) -> bool:
        return self.envelope.lo - 1e-9 <= inner_c <= self.envelope.hi + 1e-9

    def margin_c(self, inner_c: float) -> float:
        """Distance to the nearer envelope bound (negative outside)."""
        return min(inner_c - self.envelope.lo, self.envelope.hi - inner_c)

    def inner_after(self, inner_c: float, from_slice: int, to_slice: int, r: int, c: int) -> float:
        """The inner temperature after occupying block (r, c) from *from_slice*
        to *to_slice*, relaxing toward that block's target one slice at a
        time (the target of the last slice repeats past the series)."""
        last = self.target_c.shape[0] - 1
        d = self.decay
        value = float(inner_c)
        for s in range(int(from_slice), int(to_slice)):
            g = float(self.target_c[min(s, last), r, c])
            value = g + (value - g) * d
        return value

    def inner_along(self, path_states: Sequence[Sequence[int]]) -> list[float]:
        """The inner temperature at every state of a route, integrated with
        :meth:`inner_after` and the arrival block's target between states
        (the planner's own rule); starts at ``initial_inner_c``."""
        values = [float(self.initial_inner_c)]
        for previous, state in zip(path_states[:-1], path_states[1:]):
            values.append(
                self.inner_after(values[-1], int(previous[2]), int(state[2]), int(state[0]), int(state[1]))
            )
        return values

    def bin_of(self, t: int) -> int:
        return int(min(max(int(t), 0) // self.slices_per_bin, self.max_dwell_h.shape[0] - 1))

    def at(self, t: int, r: int, c: int) -> tuple[float, int, int]:
        """``(hours, side, component)`` for an arrival at slice *t* in (r, c)."""
        b = self.bin_of(t)
        return float(self.max_dwell_h[b, r, c]), int(self.side[b, r, c]), int(self.component[b, r, c])

    def summary(self, t: int = 0) -> dict[str, Any]:
        """The dwell distribution over the passable blocks at slice *t*."""
        b = self.bin_of(t)
        values = self.max_dwell_h[b].astype(np.float64).ravel()
        sides = self.side[b].ravel()
        passable = ~np.isnan(values)
        n = int(passable.sum())
        finite = values[passable & np.isfinite(values)]
        summary: dict[str, Any] = {
            "slice": int(b * self.slices_per_bin),
            "traversable_blocks": n,
            "lookahead_h": round(float(self.lookahead_h[b]), 4),
            "fraction_unlimited": None,
            "fraction_cold_limited": None,
            "fraction_hot_limited": None,
            "finite_median_h": None,
            "finite_p5_h": None,
            "finite_p95_h": None,
        }
        if n:
            summary["fraction_unlimited"] = round(float(np.isinf(values[passable]).mean()), 6)
            summary["fraction_cold_limited"] = round(float((sides[passable] == SIDE_COLD).mean()), 6)
            summary["fraction_hot_limited"] = round(float((sides[passable] == SIDE_HOT).mean()), 6)
        if finite.size:
            summary["finite_median_h"] = round(float(np.median(finite)), 4)
            summary["finite_p5_h"] = round(float(np.percentile(finite, 5)), 4)
            summary["finite_p95_h"] = round(float(np.percentile(finite, 95)), 4)
        return summary

    def info(self) -> dict[str, Any]:
        return {
            "model": THERMAL_DWELL_MODEL_ID,
            "validity": THERMAL_DWELL_VALIDITY,
            "thermal_lag_validity": REGOLITH_LAG_VALIDITY,
            "n_start_bins": int(self.max_dwell_h.shape[0]),
            "n_slices": int(self.n_slices),
            "slices_per_bin": int(self.slices_per_bin),
            "blocks": [int(self.max_dwell_h.shape[1]), int(self.max_dwell_h.shape[2])],
            "n_states": self.n_states,
            "slice_hours": round(float(self.slice_hours), 6),
            "tau_s": float(self.tau_s),
            "initial_inner_c": float(self.initial_inner_c),
            "initial_outside_envelope": bool(self.initial_outside_envelope),
            "heater_model": self.heater_model,
            "heater_source": heater_source(self.heater_model),
            "envelope": self.envelope.as_dict(),
            "compute_ms": round(float(self.compute_ms), 3),
        }


def build_dwell_cube(
    surface_series: np.ndarray,
    slice_hours: float,
    rover: Mapping[str, Any],
    traversable: np.ndarray,
    initial_inner_c: float | None = None,
    heater_model: str = "none",
    max_states: int = DWELL_MAX_STATES,
) -> DwellCube | None:
    """The dwell cube for a ``(T, H, W)`` surface series, or None when the
    rover declares no ``thermal_tau_s`` or no envelope.

    Every start slice is integrated at once: the state of each active
    (start, block) pair is advanced one slice per step with the exact
    exponential, the closed form :func:`exit_time_h` says whether the bound
    is crossed inside the coming slice, and pairs that crossed (or ran out
    of series) drop out of the active set -- so the work is proportional to
    the pairs still inside the envelope, not to ``T^2``.
    """
    if dwell_unavailable_reason(rover) is not None:
        return None
    t_start = time.perf_counter()
    env = rover_envelope(rover)
    assert env is not None
    tau = float(rover["thermal_tau_s"])
    if heater_model not in HEATER_MODELS:
        raise ValueError(f"unknown heater_model {heater_model!r}; expected one of {HEATER_MODELS}")

    surface = np.asarray(surface_series, dtype=np.float64)
    if surface.ndim != 3:
        raise ValueError(f"surface_series must be (T, H, W), got {surface.shape}")
    n_slices, height, width = surface.shape
    passable = np.asarray(traversable, dtype=bool)
    if passable.shape != (height, width):
        raise ValueError(f"traversable {passable.shape} must match the series blocks {(height, width)}")
    delta_h = float(slice_hours)
    if not delta_h > 0.0:
        raise ValueError("slice_hours must be positive")

    t0 = float(nominal_inner_c(rover) if initial_inner_c is None else initial_inner_c)
    n_cells = height * width
    target = apply_heater(inner_target_c(surface.reshape(n_slices, n_cells), rover), env, heater_model)
    bad_cell = np.isnan(target).any(axis=0) | ~passable.ravel()

    m = max(1, int(math.ceil(n_slices * n_cells / float(max_states))))
    starts = np.arange(0, n_slices, m, dtype=np.int64)
    n_starts = int(starts.size)

    dwell = np.full(n_starts * n_cells, np.inf, dtype=np.float64)
    side = np.zeros(n_starts * n_cells, dtype=np.int8)
    comp = np.zeros(n_starts * n_cells, dtype=np.int8)

    # A pair whose block's target never leaves the envelope again is
    # open-ended for certain (the state is inside and relaxes toward inside
    # targets), so it can retire the moment its clock passes the block's
    # last outside slice instead of being carried to the horizon. Under the
    # thermostat assumption that is almost every pair, and without it the
    # lit blocks: measured on Site11's day route the cube went from 9.5 s
    # to well under a second.
    outside = (target < env.lo) | (target > env.hi)
    any_outside = outside.any(axis=0)
    last_outside = np.where(
        any_outside, n_slices - 1 - np.argmax(outside[::-1, :], axis=0), -1
    ).astype(np.int64)

    # Active (start, block) pairs as flat indices into the (S, HW) arrays,
    # each with its current inner temperature.
    good = ~bad_cell
    active = np.flatnonzero(np.repeat(good[None, :], n_starts, axis=0).ravel())
    state = np.full(active.size, t0, dtype=np.float64)
    decay = math.exp(-delta_h * 3600.0 / tau)
    inside_start = env.lo <= t0 <= env.hi

    k = 0
    while active.size:
        rows = active // n_cells
        cols = active - rows * n_cells
        slices = starts[rows] + k
        keep = slices < n_slices
        if inside_start:
            # Retire pairs that can never leave: no outside target from here on.
            keep &= slices <= last_outside[cols]
        if not keep.all():
            active, state, rows, cols, slices = active[keep], state[keep], rows[keep], cols[keep], slices[keep]
            if not active.size:
                break
        g = target[slices, cols]
        hours, sd, cp = exit_time_h(state, g, env, tau)
        hit = hours < delta_h
        if hit.any():
            where = active[hit]
            dwell[where] = k * delta_h + hours[hit]
            side[where] = sd[hit]
            comp[where] = cp[hit]
        stay = ~hit
        active = active[stay]
        state = g[stay] + (state[stay] - g[stay]) * decay
        k += 1

    dwell = dwell.reshape(n_starts, n_cells)
    side = side.reshape(n_starts, n_cells)
    comp = comp.reshape(n_starts, n_cells)
    dwell[:, bad_cell] = np.nan
    side[:, bad_cell] = SIDE_NONE
    comp[:, bad_cell] = COMPONENT_NONE

    return DwellCube(
        max_dwell_h=dwell.reshape(n_starts, height, width).astype(np.float32),
        side=side.reshape(n_starts, height, width),
        component=comp.reshape(n_starts, height, width),
        lookahead_h=(n_slices - starts).astype(np.float64) * delta_h,
        slice_hours=delta_h,
        slices_per_bin=m,
        n_slices=int(n_slices),
        initial_inner_c=t0,
        heater_model=heater_model,
        tau_s=tau,
        envelope=env,
        compute_ms=(time.perf_counter() - t_start) * 1000.0,
        initial_outside_envelope=not (env.lo <= t0 <= env.hi),
        target_c=target.reshape(n_slices, height, width),
    )


def _finite_or_none(value: float) -> float | None:
    return float(value) if math.isfinite(value) else None


def route_dwell_report(
    path_states: Sequence[Sequence[int]], slice_hours: float, cube: DwellCube
) -> dict[str, Any]:
    """The dwell budget along a planned route: per state, the hours the rover
    has stood still in its current block (a wait chain), the budget of that
    block at the slice the chain began (None where open-ended) and the
    margin between them; plus the route's tightest margin and how many
    states overran it."""
    delta_h = float(slice_hours)
    stays: list[float] = []
    budgets: list[float | None] = []
    margins: list[float | None] = []
    sides: list[str | None] = []
    components: list[str | None] = []
    arrival_slice = int(path_states[0][2]) if path_states else 0
    previous: tuple[int, int] | None = None
    wait_steps = 0
    for state in path_states:
        r, c, t = int(state[0]), int(state[1]), int(state[2])
        if previous == (r, c):
            wait_steps += 1
        else:
            arrival_slice = t
        stay = (t - arrival_slice) * delta_h
        budget, sd, cp = cube.at(arrival_slice, r, c)
        budget_value = _finite_or_none(budget)
        stays.append(stay)
        budgets.append(budget_value)
        margins.append(None if budget_value is None else budget_value - stay)
        sides.append(SIDE_NAMES.get(sd))
        components.append(COMPONENT_NAMES.get(cp))
        previous = (r, c)

    finite = [(i, m) for i, m in enumerate(margins) if m is not None]
    if finite:
        min_index, min_margin = min(finite, key=lambda item: item[1])
    else:
        min_index, min_margin = None, None
    return {
        "path_stay_hours": stays,
        "path_max_dwell_h": budgets,
        "path_dwell_margin_h": margins,
        "path_dwell_side": sides,
        "path_dwell_component": components,
        "wait_steps": wait_steps,
        "max_stay_h": max(stays) if stays else 0.0,
        "min_dwell_margin_h": min_margin,
        "min_margin_state": min_index,
        "min_margin_side": None if min_index is None else sides[min_index],
        "min_margin_component": None if min_index is None else components[min_index],
        "states_past_thermal_dwell": sum(1 for m in margins if m is not None and m < -1e-9),
        "open_ended_states": sum(1 for b in budgets if b is None),
    }


def route_inner_trace(
    path_states: Sequence[Sequence[int]],
    surface_series: np.ndarray,
    slice_hours: float,
    rover: Mapping[str, Any],
    initial_inner_c: float | None = None,
    heater_model: str = "none",
) -> dict[str, Any] | None:
    """The rover's inner temperature along a planned route, integrated with
    the same lag the cube uses: between two states the target is the
    surface of the block the rover ARRIVES in (the planner's own rule for
    its shadow clock), slice by slice. None when the rover declares no lag.

    Reports the temperature at every state, how many states sit outside
    the envelope, and the first instant the envelope is left (closed form
    inside the slice it happens in) with the side and the component.
    """
    if dwell_unavailable_reason(rover) is not None:
        return None
    env = rover_envelope(rover)
    assert env is not None
    tau = float(rover["thermal_tau_s"])
    t0 = float(nominal_inner_c(rover) if initial_inner_c is None else initial_inner_c)
    surface = np.asarray(surface_series, dtype=np.float64)
    n_slices = surface.shape[0]
    delta_h = float(slice_hours)
    decay = math.exp(-delta_h * 3600.0 / tau)
    start_slice = int(path_states[0][2]) if path_states else 0

    inner: list[float] = [t0]
    current = t0
    first_exit: float | None = None
    exit_side = SIDE_NONE
    exit_comp = COMPONENT_NONE
    if not (env.lo <= t0 <= env.hi):
        first_exit = 0.0
        exit_side = SIDE_COLD if t0 < env.lo else SIDE_HOT
        exit_comp = _COMPONENT_CODES[env.lo_component if t0 < env.lo else env.hi_component]
    for previous, state in zip(path_states[:-1], path_states[1:]):
        r, c = int(state[0]), int(state[1])
        for s in range(int(previous[2]), int(state[2])):
            g_arr = apply_heater(inner_target_c(surface[min(s, n_slices - 1), r, c], rover), env, heater_model)
            g = float(g_arr)
            if first_exit is None:
                hours, sd, cp = exit_time_h(np.array([current]), np.array([g]), env, tau)
                if hours[0] < delta_h:
                    first_exit = (s - start_slice) * delta_h + float(hours[0])
                    exit_side, exit_comp = int(sd[0]), int(cp[0])
            current = g + (current - g) * decay
        inner.append(current)

    outside = sum(1 for v in inner if not (env.lo <= v <= env.hi))
    return {
        "path_inner_c": inner,
        "min_c": min(inner),
        "max_c": max(inner),
        "states_outside": int(outside),
        "first_exit_h": first_exit,
        "side": SIDE_NAMES.get(exit_side),
        "component": COMPONENT_NAMES.get(exit_comp),
        "envelope": env.as_dict(),
        "initial_inner_c": t0,
        "heater_model": heater_model,
        "heater_source": heater_source(heater_model),
        "tau_s": tau,
        "target_rule": "the arrival block's surface, slice by slice (the planner's shadow-clock rule)",
    }


# ── one cell: its surface series, its dwell card ─────────────────────────────

#: How far a cell card or an entrenchment countdown looks ahead by default,
#: and at what slice. 24 h of half-hour slices: the polar Sun moves 12 deg
#: of azimuth in that time, so a shadow edge crossing a cell is resolved.
DEFAULT_DWELL_LOOKAHEAD_H: float = 24.0
DEFAULT_DWELL_SLICE_H: float = 0.5


def surface_series_for_cell(
    sunlit_peak_c: float,
    base_shadow: float,
    shadow_series: Sequence[float],
    slice_hours: float,
    tau_s: float = REGOLITH_THERMAL_TAU_S,
) -> np.ndarray:
    """The per-slice surface temperature of ONE cell: the same integration
    :func:`app.cost_cube.surface_temperature_series` performs for a grid
    (long-run equilibrium prior, per-slice equilibrium target, regolith
    lag), for a hover or a telemetry tick."""
    sunlit = np.asarray([float(sunlit_peak_c)], dtype=np.float64)
    state = np.asarray(shadowed_equilibrium_c(sunlit, np.asarray([float(base_shadow)])), dtype=np.float64)
    dt_s = max(0.0, float(slice_hours)) * 3600.0
    out: list[float] = []
    for ratio in shadow_series:
        target = np.asarray(shadowed_equilibrium_c(sunlit, np.asarray([float(ratio)])), dtype=np.float64)
        state = np.asarray(relax_surface_c(state, target, dt_s, tau_s), dtype=np.float64)
        out.append(float(state[0]))
    return np.asarray(out, dtype=np.float64)


def _verdict(inner_c: float, env: Envelope) -> str:
    if inner_c < env.lo:
        return "cold"
    if inner_c > env.hi:
        return "hot"
    return "inside"


def cell_dwell(
    sunlit_peak_c: float,
    base_shadow: float,
    shadow_series: Sequence[float],
    slice_hours: float,
    rover: Mapping[str, Any],
    initial_inner_c: float | None = None,
    heater_model: str = "none",
) -> dict[str, Any]:
    """The dwell card of one cell: the equilibrium verdicts (the static
    reading D3 makes) and, when the rover declares a lag, the hours it may
    stand there from the requested inner temperature before leaving the
    envelope, with the side and the component. ``max_dwell_h`` is None where
    open-ended within the lookahead (``open_ended``) or where no dwell can be
    timed (``dwell_model.model == "unavailable"``)."""
    env = rover_envelope(rover)
    reason = dwell_unavailable_reason(rover)
    peak_inner = float(inner_target_c(np.asarray([float(sunlit_peak_c)]), rover)[0])
    cold_end_surface = float(
        shadowed_equilibrium_c(np.asarray([float(sunlit_peak_c)]), np.asarray([float(base_shadow)]))[0]
    )
    cold_end_inner = float(inner_target_c(np.asarray([cold_end_surface]), rover)[0])
    card: dict[str, Any] = {
        "max_dwell_h": None,
        "open_ended": False,
        "side": None,
        "component": None,
        "initial_inner_c": None if env is None else float(
            nominal_inner_c(rover) if initial_inner_c is None else initial_inner_c
        ),
        "heater_model": heater_model,
        "heater_source": heater_source(heater_model),
        "lookahead_h": round(float(len(shadow_series)) * float(slice_hours), 4),
        "slice_hours": float(slice_hours),
        "inner_equilibrium_c": {"peak": round(peak_inner, 3), "cold_end": round(cold_end_inner, 3)},
        "surface_c": {
            "sunlit_peak": float(sunlit_peak_c),
            "cold_end": round(cold_end_surface, 3),
            "base_shadow_ratio": float(base_shadow),
        },
        "envelope": None if env is None else env.as_dict(),
        "envelope_verdict": None
        if env is None
        else {"peak": _verdict(peak_inner, env), "cold_end": _verdict(cold_end_inner, env)},
        "thermal_lag_validity": REGOLITH_LAG_VALIDITY,
    }
    if reason is not None or env is None:
        card["dwell_model"] = {
            "model": "unavailable",
            "validity": THERMAL_DWELL_VALIDITY,
            "reason": reason or "rover declares no thermal envelope",
        }
        return card
    surface = surface_series_for_cell(sunlit_peak_c, base_shadow, shadow_series, slice_hours)
    cube = build_dwell_cube(
        surface[:, None, None],
        slice_hours,
        rover,
        np.ones((1, 1), dtype=bool),
        initial_inner_c=initial_inner_c,
        heater_model=heater_model,
    )
    assert cube is not None
    hours, side, comp = cube.at(0, 0, 0)
    card.update(
        {
            "max_dwell_h": None if not math.isfinite(hours) else float(hours),
            "open_ended": bool(math.isinf(hours)),
            "side": SIDE_NAMES.get(side),
            "component": COMPONENT_NAMES.get(comp),
            "initial_inner_c": float(cube.initial_inner_c),
            "initial_outside_envelope": bool(cube.initial_outside_envelope),
            "surface_c": {
                **card["surface_c"],
                "series_min": round(float(surface.min()), 3),
                "series_max": round(float(surface.max()), 3),
                "shadow_fraction": round(float(np.mean(np.asarray(shadow_series, dtype=np.float64) >= 0.5)), 4),
            },
            "dwell_model": {k: v for k, v in cube.info().items() if k not in ("blocks", "n_states", "n_start_bins")},
        }
    )
    return card


# ── the response blocks ─────────────────────────────────────────────────────


def thermal_dwell_block(
    cube: DwellCube | None,
    route: Mapping[str, Any] | None,
    requested: bool,
    applied: bool,
    reason: str | None,
    inner_trace: Mapping[str, Any] | None,
    rover: Mapping[str, Any],
    heater_model: str = "none",
    initial_inner_c: float | None = None,
    shadow_model: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """The ``thermal_dwell`` block of ``/api/plan-4d``: what the model is,
    what it was asked to do, the cube's summary at the first slice, the
    route's stays against their budgets and the inner temperature along
    it, JSC's quoted figures and the claim."""
    env = rover_envelope(rover)
    if cube is not None:
        dwell_model: dict[str, Any] = cube.info()
        initial = float(cube.initial_inner_c)
        heater = cube.heater_model
    else:
        dwell_model = {
            "model": "unavailable",
            "validity": THERMAL_DWELL_VALIDITY,
            "reason": reason or dwell_unavailable_reason(rover) or "no dwell cube",
        }
        initial = None if env is None else float(
            nominal_inner_c(rover) if initial_inner_c is None else initial_inner_c
        )
        heater = heater_model
    route_block: dict[str, Any] | None = None
    if route is not None:
        route_block = {
            "wait_steps": route.get("wait_steps"),
            "max_stay_h": route.get("max_stay_h"),
            "min_dwell_margin_h": route.get("min_dwell_margin_h"),
            "min_margin_state": route.get("min_margin_state"),
            "min_margin_side": route.get("min_margin_side"),
            "min_margin_component": route.get("min_margin_component"),
            "states_past_thermal_dwell": route.get("states_past_thermal_dwell"),
            "open_ended_states": route.get("open_ended_states"),
            "inner": None
            if inner_trace is None
            else {
                key: inner_trace.get(key)
                for key in ("min_c", "max_c", "states_outside", "first_exit_h", "side", "component", "target_rule")
            },
        }
    return {
        "model": THERMAL_DWELL_MODEL_ID,
        "validity": THERMAL_DWELL_VALIDITY,
        "thermal_lag_validity": REGOLITH_LAG_VALIDITY,
        "requested": bool(requested),
        "applied": bool(applied),
        "dwell_model": dwell_model,
        "envelope": None if env is None else env.as_dict(),
        "initial_inner_c": initial,
        "heater_model": heater,
        "heater_source": heater_source(heater),
        "tau_s": None if rover.get("thermal_tau_s") is None else float(rover["thermal_tau_s"]),
        "cube": None if cube is None else cube.summary(0),
        "route": route_block,
        "shadow_model": None if shadow_model is None else dict(shadow_model),
        "scope": THERMAL_DWELL_SCOPE,
        "quoted": JSC_QUOTED,
        "references": list(THERMAL_DWELL_REFERENCES),
        "claim": THERMAL_DWELL_CLAIM,
    }


def _countdown(entrenched_h: float, tolerable_h: float | None) -> dict[str, Any]:
    from .replan_triggers import entrenchment_level

    if tolerable_h is None or not math.isfinite(float(tolerable_h)):
        return {"tolerable_h": None, "remaining_h": None, "used_fraction": None, "level": "ok", "open_ended": True}
    tolerable = float(tolerable_h)
    used = math.inf if tolerable <= 0.0 else float(entrenched_h) / tolerable
    return {
        "tolerable_h": tolerable,
        "remaining_h": tolerable - float(entrenched_h),
        "used_fraction": None if math.isinf(used) else round(used, 6),
        "level": entrenchment_level(used),
        "open_ended": False,
    }


def entrenchment_block(
    entrenched_h: float,
    thermal: Mapping[str, Any] | None,
    haven: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """The ``entrenchment`` block of ``/api/replan`` (C6): two countdowns from
    the moment the rover stopped moving -- the block's thermal dwell and the
    safe-haven window (JSC's tolerable entrenched time proper) -- and the
    tighter of the two with its level.

    *thermal* carries ``max_dwell_h`` (None where open-ended) plus whatever
    else the cell card said; *haven* carries ``tolerable_h``; either may be
    None when it could not be computed.
    """
    from .replan_triggers import ENTRENCHMENT_CRITICAL_FRAC, ENTRENCHMENT_LEVELS, ENTRENCHMENT_WARNING_FRAC

    e = max(0.0, float(entrenched_h))
    thermal_block = None
    if thermal is not None:
        thermal_block = {**dict(thermal), **_countdown(e, thermal.get("max_dwell_h"))}
    haven_block = None
    if haven is not None:
        haven_block = {**dict(haven), **_countdown(e, haven.get("tolerable_h"))}
    candidates = [
        (name, block["tolerable_h"])
        for name, block in (("thermal", thermal_block), ("haven", haven_block))
        if block is not None and block["tolerable_h"] is not None
    ]
    if candidates:
        limiting, tolerable = min(candidates, key=lambda item: item[1])
        overall = {**_countdown(e, tolerable), "limiting": limiting}
    else:
        overall = {**_countdown(e, None), "limiting": None}
    return {
        "entrenched_hours": e,
        "thermal": thermal_block,
        "haven": haven_block,
        "overall": overall,
        "levels": list(ENTRENCHMENT_LEVELS),
        "thresholds": {
            "warning_fraction": ENTRENCHMENT_WARNING_FRAC,
            "critical_fraction": ENTRENCHMENT_CRITICAL_FRAC,
            "source": "LunaPath's own level fractions; the framing is JSC's tolerable entrenched time",
        },
        "quoted": {
            "tolerable_entrenched_time": JSC_QUOTED["tolerable_entrenched_time"],
            "caveats": JSC_QUOTED["entrenched_time_caveats"],
        },
    }


# ── the envelope matrix: JSC's chart on our model ────────────────────────────

#: Sun elevation bins (deg). The site's annual range is about -2.6..+2.6
#: deg (SPICE, probe of 5 Sep 2026; JSC: 1.5 deg at the pole plus one per
#: degree of latitude), so the axis covers it with half-degree bins.
ENVELOPE_EL_EDGES: np.ndarray = np.arange(-3.0, 3.01, 0.5)
#: Sun-parallel slope bins (deg): the terrain's tilt along the Sun's
#: azimuth, positive toward the Sun. JSC's radial axis stops at VIPER's
#: 15 deg requirement and drops Sun-averted slopes; ours runs to the
#: catalogue's steepest limit both ways.
ENVELOPE_SPAR_EDGES: np.ndarray = np.arange(-30.0, 30.01, 2.5)
#: Slopes heat1d is run at (one aspect: the Sun sweeps every azimuth each
#: lunar day at the pole, so one run covers s_par in [-s, +s]).
ENVELOPE_SLOPES_DEG: tuple[float, ...] = (0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0, 25.0, 30.0)
ENVELOPE_CACHE_FILENAME: str = "thermal_envelope_heat1d.npz"
ENVELOPE_META_FILENAME: str = "thermal_envelope_meta.json"
ENVELOPE_VERDICTS: tuple[str, ...] = ("unlimited", "cold_limited", "hot_limited", "unsampled")


def heat1d_envelope_samples(
    lat_deg: float,
    slopes: Sequence[float] = ENVELOPE_SLOPES_DEG,
    ndays: int = 13,
    slope_az_deg: float = 0.0,
) -> dict[str, np.ndarray]:
    """Run heat1d at *lat_deg* for every slope in *slopes* and return every
    output step as a sample ``(el_deg, s_par_deg, surface_c, slope_deg)``.

    A subclass of heat1d's ``Model`` records the Sun's elevation and
    azimuth at every ``advance`` with the same hour-angle formula
    ``surfFlux`` uses; the samples of the final (output) phase are aligned
    with the temperature rows. ``s_par = atan(tan s * cos(az_sun - az_slope))``
    is the slope's component along the Sun's azimuth (positive: tilted
    toward the Sun). Raises RuntimeError when heat1d is not importable with
    slope support or its internals have moved.
    """
    from .thermal_model import Heat1DModel

    if not Heat1DModel.available():
        raise RuntimeError("heat1d with slope support is not installed (GitHub main, python/ subdirectory)")
    try:
        import heat1d
        from heat1d import orbits as orb
        from heat1d import planets as heat1d_planets
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"heat1d import failed: {exc}") from exc

    class _RecordingModel(heat1d.Model):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._geom: list[tuple[int, float, float, float]] = []
            self._phase = 0
            self._last_t = -1.0

        def advance(self, dt_max=None):  # type: ignore[override]
            super().advance(dt_max=dt_max)
            if self.t < self._last_t:
                self._phase += 1
            self._last_t = self.t
            h = orb.TWOPI * self.t / self.P_sid + self._nu0 - self.nu
            cz = orb.cosSolarZenith(self.lat, self.dec, h, clip=False)
            az = orb.solarAzimuth(self.lat, self.dec, h)
            self._geom.append((self._phase, float(self.t), float(cz), float(az)))

    el_all: list[np.ndarray] = []
    sp_all: list[np.ndarray] = []
    t_all: list[np.ndarray] = []
    s_all: list[np.ndarray] = []
    for slope_deg in slopes:
        try:
            config = heat1d.Configurator(solver="crank-nicolson")
            model = _RecordingModel(
                planet=heat1d_planets.Moon,
                lat=np.deg2rad(float(lat_deg)),
                ndays=int(ndays),
                slope=np.deg2rad(float(slope_deg)),
                slope_az=np.deg2rad(float(slope_az_deg)),
                config=config,
            )
            model.run()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"heat1d run failed at slope {slope_deg} deg: {exc}") from exc
        geom = np.asarray(model._geom, dtype=np.float64)
        if geom.size == 0:
            raise RuntimeError("heat1d recorded no steps: its advance() hook has moved")
        geom = geom[geom[:, 0] == geom[-1, 0]]
        temps = np.asarray(model.T)[:, 0] - 273.15
        n = min(len(geom), len(temps))
        geom, temps = geom[-n:], temps[-n:]
        el = np.degrees(np.arcsin(np.clip(geom[:, 2], -1.0, 1.0)))
        delta = geom[:, 3] - np.deg2rad(float(slope_az_deg))
        s_par = np.degrees(np.arctan(np.tan(np.deg2rad(float(slope_deg))) * np.cos(delta)))
        el_all.append(el)
        sp_all.append(s_par)
        t_all.append(temps)
        s_all.append(np.full(n, float(slope_deg)))
    return {
        "el_deg": np.concatenate(el_all),
        "s_par_deg": np.concatenate(sp_all),
        "surface_c": np.concatenate(t_all),
        "slope_deg": np.concatenate(s_all),
    }


def bin_envelope(
    samples: Mapping[str, np.ndarray],
    el_edges: np.ndarray = ENVELOPE_EL_EDGES,
    sp_edges: np.ndarray = ENVELOPE_SPAR_EDGES,
) -> dict[str, np.ndarray]:
    """Bin the samples into (elevation x Sun-parallel slope): the maximum
    and mean surface temperature and the sample count per bin; NaN where a
    bin was never visited (the honest 'no sample', never a fill)."""
    el = np.asarray(samples["el_deg"], dtype=np.float64)
    sp = np.asarray(samples["s_par_deg"], dtype=np.float64)
    t = np.asarray(samples["surface_c"], dtype=np.float64)
    el_edges = np.asarray(el_edges, dtype=np.float64)
    sp_edges = np.asarray(sp_edges, dtype=np.float64)
    shape = (el_edges.size - 1, sp_edges.size - 1)
    ie = np.digitize(el, el_edges) - 1
    isp = np.digitize(sp, sp_edges) - 1
    ok = (ie >= 0) & (ie < shape[0]) & (isp >= 0) & (isp < shape[1]) & np.isfinite(t)
    flat = ie[ok] * shape[1] + isp[ok]
    count = np.bincount(flat, minlength=shape[0] * shape[1]).astype(np.int64)
    total = np.bincount(flat, weights=t[ok], minlength=shape[0] * shape[1])
    tmax = np.full(shape[0] * shape[1], -np.inf)
    np.maximum.at(tmax, flat, t[ok])
    tmax[count == 0] = np.nan
    tmean = np.where(count > 0, total / np.maximum(count, 1), np.nan)
    return {
        "tmax": tmax.reshape(shape),
        "tmean": tmean.reshape(shape),
        "count": count.reshape(shape),
        "el_edges": el_edges,
        "sp_edges": sp_edges,
    }


def envelope_cache_path(metadata: Mapping[str, Any]) -> str | None:
    """Where the heat1d envelope cache for these grids lives, if it exists."""
    import os

    processed_dir = metadata.get("processed_dir")
    if not processed_dir:
        return None
    path = os.path.join(str(processed_dir), ENVELOPE_CACHE_FILENAME)
    return path if os.path.exists(path) else None


def save_envelope_cache(path: str, binned: Mapping[str, np.ndarray], meta: Mapping[str, Any]) -> None:
    """Write the binned matrix (.npz) and its provenance (JSON beside it)."""
    import json
    import os

    np.savez(
        path,
        tmax=np.asarray(binned["tmax"], dtype=np.float64),
        tmean=np.asarray(binned["tmean"], dtype=np.float64),
        count=np.asarray(binned["count"], dtype=np.int64),
        el_edges=np.asarray(binned["el_edges"], dtype=np.float64),
        sp_edges=np.asarray(binned["sp_edges"], dtype=np.float64),
    )
    meta_path = os.path.join(os.path.dirname(os.path.abspath(path)), ENVELOPE_META_FILENAME)
    with open(meta_path, "w", encoding="utf-8") as handle:
        json.dump(dict(meta), handle, indent=2, ensure_ascii=False)


def load_envelope_cache(path: str) -> dict[str, Any]:
    """The binned matrix and its provenance (``meta`` is ``{}`` when the JSON is missing)."""
    import json
    import os

    with np.load(path) as data:
        out: dict[str, Any] = {key: np.asarray(data[key]) for key in ("tmax", "tmean", "count", "el_edges", "sp_edges")}
    meta_path = os.path.join(os.path.dirname(os.path.abspath(path)), ENVELOPE_META_FILENAME)
    meta: dict[str, Any] = {}
    if os.path.exists(meta_path):
        with open(meta_path, encoding="utf-8") as handle:
            meta = json.load(handle)
    out["meta"] = meta
    return out


def envelope_matrix(
    cache: Mapping[str, Any],
    rover: Mapping[str, Any],
    initial_inner_c: float | None = None,
    heater_model: str = "none",
) -> dict[str, Any]:
    """JSC's unlimited-operations envelope on our model: for every
    (elevation, Sun-parallel slope) bin the binned maximum surface
    temperature, the inner temperature it maps to, the verdict (unlimited /
    cold-limited / hot-limited / unsampled) and, where the rover declares a
    lag, the hours from *initial_inner_c* to the bound."""
    env = rover_envelope(rover)
    tmax = np.asarray(cache["tmax"], dtype=np.float64)
    tmean = np.asarray(cache["tmean"], dtype=np.float64)
    count = np.asarray(cache["count"])
    el_edges = np.asarray(cache["el_edges"], dtype=np.float64)
    sp_edges = np.asarray(cache["sp_edges"], dtype=np.float64)
    reason = dwell_unavailable_reason(rover)
    tau = None if reason is not None else float(rover["thermal_tau_s"])
    t0 = None if env is None else float(nominal_inner_c(rover) if initial_inner_c is None else initial_inner_c)

    if env is not None:
        inner = apply_heater(inner_target_c(tmax, rover), env, heater_model)
    else:
        inner = inner_target_c(tmax, rover)
    if tau is not None and env is not None and t0 is not None:
        hours, side, comp = exit_time_h(np.full(tmax.shape, t0), inner, env, tau)
    else:
        hours = np.full(tmax.shape, np.nan)
        side = np.full(tmax.shape, SIDE_NONE, dtype=np.int8)
        comp = np.full(tmax.shape, COMPONENT_NONE, dtype=np.int8)

    cells: list[dict[str, Any]] = []
    counts = {name: 0 for name in ENVELOPE_VERDICTS}
    for i in range(tmax.shape[0]):
        for j in range(tmax.shape[1]):
            if np.isnan(tmax[i, j]):
                verdict = "unsampled"
            elif env is None:
                verdict = "unsampled"
            elif inner[i, j] < env.lo:
                verdict = "cold_limited"
            elif inner[i, j] > env.hi:
                verdict = "hot_limited"
            else:
                verdict = "unlimited"
            counts[verdict] += 1
            dwell_value: float | None = None
            if verdict in ("cold_limited", "hot_limited") and tau is not None and math.isfinite(hours[i, j]):
                dwell_value = float(hours[i, j])
            cells.append(
                {
                    "el_bin": int(i),
                    "s_par_bin": int(j),
                    "el_mid_deg": round(float(0.5 * (el_edges[i] + el_edges[i + 1])), 4),
                    "s_par_mid_deg": round(float(0.5 * (sp_edges[j] + sp_edges[j + 1])), 4),
                    "samples": int(count[i, j]),
                    "surface_c_max": None if np.isnan(tmax[i, j]) else float(tmax[i, j]),
                    "surface_c_mean": None if np.isnan(tmean[i, j]) else round(float(tmean[i, j]), 3),
                    "inner_c": None if np.isnan(inner[i, j]) else float(inner[i, j]),
                    "verdict": verdict,
                    "dwell_h": dwell_value,
                    "side": SIDE_NAMES.get(int(side[i, j])) if verdict != "unsampled" else None,
                    "component": COMPONENT_NAMES.get(int(comp[i, j])) if verdict != "unsampled" else None,
                }
            )
    return {
        "model": THERMAL_DWELL_MODEL_ID,
        "validity": THERMAL_DWELL_VALIDITY,
        "thermal_lag_validity": REGOLITH_LAG_VALIDITY,
        "dwell_model": (
            {"model": "unavailable", "validity": THERMAL_DWELL_VALIDITY, "reason": reason}
            if reason is not None
            else {"model": THERMAL_DWELL_MODEL_ID, "validity": THERMAL_DWELL_VALIDITY, "tau_s": tau}
        ),
        "envelope": None if env is None else env.as_dict(),
        "initial_inner_c": t0,
        "heater_model": heater_model,
        "heater_source": heater_source(heater_model),
        "axes": {
            "el_deg": {"edges": [float(v) for v in el_edges], "label": "Sun elevation at the site (deg)"},
            "s_par_deg": {
                "edges": [float(v) for v in sp_edges],
                "label": "terrain slope along the Sun's azimuth (deg, positive toward the Sun)",
            },
        },
        "counts": counts,
        "cells": cells,
        "verdicts": list(ENVELOPE_VERDICTS),
        "method": (
            "heat1d (Hayne 2017) transient at the site's latitude for each slope in slopes_deg, every "
            "output step binned by (Sun elevation, Sun-parallel slope component); per bin the maximum "
            "surface temperature over the run, mapped to the inner temperature with the catalogue's "
            "offsets and read against the tightest declared envelope; the dwell is the closed-form time "
            "from initial_inner_c to the bound. JSC's chart (slope x Sun azimuth relative to the rover, "
            "at the mission's maximum elevation, Thermal Desktop, 60+ components) is quoted, not reproduced."
        ),
    }
