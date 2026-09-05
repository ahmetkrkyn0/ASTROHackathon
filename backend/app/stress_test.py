"""Monte Carlo traverse stress test -- SHERPA's "Traverse Evaluation" (B5).

VIPER's planning team does not trust a plan because it is feasible once. Every
strategic plan is executed thousands of times against the uncertainties the
operations team actually faces, sampled from truncated Gaussians (Shirley &
Balaban, "An Overview of Mission Planning for the VIPER Rover", 2022;
Balaban et al., SHERPA, SpaceOps 2025):

* start time -- delayed, sigma 2 h;
* initial battery -- lower, sigma 20 percent;
* power draw -- higher, sigma 20 percent;
* effective speed ("speed made good") -- lower, sigma 20 / 30 / 40 / 50 percent;
* DSN outages and solar energetic particle (SEP) events -- injected with a
  modelled probability.

A human operator is imitated by a policy: behind schedule, the rover skips
charge breaks and drives through shadow on its battery; ahead of schedule
and facing shadow, it waits. The output is not one number but the
DISTRIBUTION of SHERPA's metrics -- completion rate, time-to-sun-shadow,
time-to-DSN-shadow, time-to-0-SOC and the rest.

This module runs that protocol on a ``/api/plan-4d`` route with the same
physics the planner used to choose it -- ``cost_engine``'s traction,
housekeeping and solar arithmetic, vectorised over N runs -- so the
distributions are about the plan, not about a second model of the rover.
Nothing here is fabricated: without an epoch and a horizon cube the sky is
static and the caller is told so; without an Earth series there is no DSN
margin; a rate is always reported with its Wilson interval.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from .constants import FAILURE_MODEL_SOURCE

#: 95 percent two-sided normal quantile, for the Wilson interval.
_Z_95: float = 1.959963984540054


# ── SHERPA's distributions ─────────────────────────────────────────────────


@dataclass(frozen=True)
class Perturbations:
    """The uncertainties injected per run. Sigmas are SHERPA's; the
    truncation is ours (a speed multiplier cannot go negative)."""

    #: Start delay, hours; delay only (a truncated Gaussian on the late side).
    start_delay_sigma_h: float = 2.0
    #: Initial state of charge, fraction of the requested one; lower only.
    initial_soc_sigma: float = 0.20
    #: Power draw multiplier on traction and housekeeping; higher only.
    power_draw_sigma: float = 0.20
    #: Effective speed multiplier; lower only. VIPER swept 0.2 / 0.3 / 0.4 / 0.5.
    speed_sigma: float = 0.20
    #: No run drives slower than this fraction of the plan's speed.
    speed_multiplier_floor: float = 0.25
    #: Every distribution is cut at this many sigmas.
    z_max: float = 3.0
    #: DSN outage: probability per run and mean duration (sd = mean / 2,
    #: truncated at zero). No published rate exists; the default injects none.
    dsn_outage_probability: float = 0.0
    dsn_outage_mean_h: float = 4.0
    #: Solar energetic particle event: the rover goes to safe mode and holds.
    sep_event_probability: float = 0.0
    sep_event_mean_h: float = 24.0
    #: Mobility faults (B1): a Poisson process in distance driven, rate per
    #: km, each holding the rover in place for the recovery time -- in the
    #: origin cell when it strikes in the first half of a move, in the
    #: destination cell in the second half (Lamarre et al.). The rover then
    #: continues the PLANNED route; it does not re-plan. No rover publishes
    #: a rate; the default injects none (constants.FAILURE_MODEL_SOURCE).
    fault_rate_per_km: float = 0.0
    fault_recovery_h: float = 10.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


#: Shirley & Balaban 2022, table of injected uncertainties.
SHERPA_DEFAULTS = Perturbations()


def _truncated_half_normal(
    rng: np.random.Generator, sigma: float, n: int, z_max: float
) -> np.ndarray:
    """``n`` draws of ``|N(0, sigma)|`` cut at ``z_max`` sigmas (>= 0)."""
    from scipy.stats import truncnorm

    if sigma <= 0.0 or z_max <= 0.0 or n <= 0:
        return np.zeros(int(n), dtype=np.float64)
    z = truncnorm(a=0.0, b=float(z_max), loc=0.0, scale=1.0).rvs(
        size=int(n), random_state=rng
    )
    return np.asarray(z, dtype=np.float64) * float(sigma)


def _event_windows(
    rng: np.random.Generator,
    n: int,
    probability: float,
    mean_h: float,
    planned_end_h: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``(event, start_h, end_h)``: a forced hold per run with the given
    probability, starting uniformly inside the planned window, lasting a
    Gaussian ``mean_h`` (sd ``mean_h / 2``) truncated at zero. NaN where
    there is no event."""
    from scipy.stats import truncnorm

    count = int(n)
    p = min(1.0, max(0.0, float(probability)))
    event = rng.random(count) < p
    start = rng.uniform(0.0, max(0.0, float(planned_end_h)), count)
    mean = max(0.0, float(mean_h))
    if mean > 0.0:
        sd = 0.5 * mean
        duration = np.asarray(
            truncnorm(a=-mean / sd, b=np.inf, loc=mean, scale=sd).rvs(
                size=count, random_state=rng
            ),
            dtype=np.float64,
        )
    else:
        duration = np.zeros(count, dtype=np.float64)
    start = np.where(event, start, np.nan)
    end = np.where(event, start + duration, np.nan)
    return event, start, end


def sample_perturbations(
    rng: np.random.Generator,
    n_runs: int,
    perturbations: Perturbations = SHERPA_DEFAULTS,
    initial_soc_frac: float = 1.0,
    planned_end_h: float = 0.0,
    route_distance_m: float = 0.0,
) -> dict[str, np.ndarray]:
    """One draw of every uncertainty per run, as ``(n_runs,)`` arrays.

    * ``fault_count`` ~ Poisson(rate * route km) and ``fault_positions_m``
      ``(n_runs, F)``, the odometer readings at which faults strike, sorted,
      NaN past each run's count (B1; *route_distance_m* is the route's
      odometry, zero faults without it or without a rate).

    * ``start_delay_h`` >= 0;
    * ``speed_multiplier`` in ``[speed_multiplier_floor, 1]``;
    * ``power_multiplier`` >= 1 (traction and housekeeping; the array is not
      scaled);
    * ``initial_soc_frac`` <= *initial_soc_frac* (never below a tenth of it);
    * ``dsn_event`` / ``sep_event`` with ``*_start_h`` / ``*_end_h`` (NaN when
      absent) -- forced holds.

    The same ``rng`` state gives the same draws.
    """
    p = perturbations
    n = int(n_runs)
    z_max = float(p.z_max)

    delay = _truncated_half_normal(rng, p.start_delay_sigma_h, n, z_max)

    floor = min(1.0, max(0.0, float(p.speed_multiplier_floor)))
    speed_z = (
        min(z_max, (1.0 - floor) / p.speed_sigma) if p.speed_sigma > 0.0 else z_max
    )
    speed = 1.0 - _truncated_half_normal(rng, p.speed_sigma, n, speed_z)
    speed = np.maximum(speed, floor)

    power = 1.0 + _truncated_half_normal(rng, p.power_draw_sigma, n, z_max)

    soc_z = (
        min(z_max, 0.9 / p.initial_soc_sigma) if p.initial_soc_sigma > 0.0 else z_max
    )
    soc0 = min(1.0, max(0.0, float(initial_soc_frac)))
    soc = soc0 * (1.0 - _truncated_half_normal(rng, p.initial_soc_sigma, n, soc_z))

    dsn_event, dsn_start, dsn_end = _event_windows(
        rng, n, p.dsn_outage_probability, p.dsn_outage_mean_h, planned_end_h
    )
    sep_event, sep_start, sep_end = _event_windows(
        rng, n, p.sep_event_probability, p.sep_event_mean_h, planned_end_h
    )

    distance = max(0.0, float(route_distance_m))
    expected_faults = max(0.0, float(p.fault_rate_per_km)) / 1000.0 * distance
    if expected_faults > 0.0:
        fault_count = rng.poisson(expected_faults, n).astype(np.int64)
    else:
        fault_count = np.zeros(n, dtype=np.int64)
    n_columns = max(1, int(fault_count.max()) if n else 1)
    positions = np.sort(rng.uniform(0.0, distance, (n, n_columns)), axis=1)
    beyond = np.arange(n_columns)[None, :] >= fault_count[:, None]
    fault_positions = np.where(beyond, np.nan, positions)

    return {
        "start_delay_h": delay,
        "speed_multiplier": speed,
        "power_multiplier": power,
        "initial_soc_frac": soc,
        "dsn_event": dsn_event,
        "dsn_start_h": dsn_start,
        "dsn_end_h": dsn_end,
        "sep_event": sep_event,
        "sep_start_h": sep_start,
        "sep_end_h": sep_end,
        "fault_count": fault_count,
        "fault_positions_m": fault_positions,
    }


def wilson_interval(successes: int, trials: int, z: float = _Z_95) -> tuple[float, float]:
    """Wilson score interval for a rate: ``(low, high)``; ``(0, 1)`` with no trials."""
    n = int(trials)
    if n <= 0:
        return 0.0, 1.0
    k = min(n, max(0, int(successes)))
    p = k / n
    z2 = z * z
    denominator = 1.0 + z2 / n
    centre = (p + z2 / (2.0 * n)) / denominator
    half = z * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n)) / denominator
    low = 0.0 if k == 0 else max(0.0, centre - half)
    high = 1.0 if k == n else min(1.0, centre + half)
    return low, high


# ── The route: legs priced like the planner ────────────────────────────────


@dataclass(frozen=True)
class RouteLegs:
    """A ``/api/plan-4d`` route as the simulator sees it: S states on the
    planner's grid, S-1 legs between them, each a MOVE (nominal drive hours
    and traction power from the planner's own trapezoidal edge slope) or a
    WAIT (nothing to drive, a planned hold)."""

    cells: np.ndarray        # (S, 2) int
    slices: np.ndarray       # (S,) int
    planned_h: np.ndarray    # (S,) hours: slices * slice_hours
    is_wait: np.ndarray      # (S-1,) bool
    distance_m: np.ndarray   # (S-1,) 0 for waits
    travel_h: np.ndarray     # (S-1,) nominal drive hours, 0 for waits
    traction_w: np.ndarray   # (S-1,) p_base * (1 + mu sin theta), 0 for waits
    slice_hours: float

    @property
    def n_states(self) -> int:
        return int(self.cells.shape[0])

    @property
    def n_waits(self) -> int:
        return int(np.count_nonzero(self.is_wait))

    @property
    def n_moves(self) -> int:
        return int(self.is_wait.shape[0]) - self.n_waits

    @property
    def planned_duration_h(self) -> float:
        return float(self.planned_h[-1])

    @property
    def odometry_m(self) -> float:
        return float(np.sum(self.distance_m))


def route_legs(
    states: Any,
    slope: np.ndarray,
    resolution_m: float,
    rover: Any,
    slice_hours: float,
    traversable: np.ndarray | None = None,
) -> RouteLegs:
    """Validate a route and price its legs the way ``astar_4d`` did.

    *states* are ``(row, col, slice)`` triples on the planner's grid. Raises
    ``ValueError`` -- naming the state -- when the route does not start at
    slice 0, its slices do not increase, a cell is outside the grid or not
    traversable, two consecutive cells are neither equal nor 8-adjacent, or
    an edge's slope is one the travel-time model cannot cross.
    """
    from .cost_engine import edge_travel_time_s

    raw = [tuple(int(v) for v in state) for state in states]
    if len(raw) < 2:
        raise ValueError("a route needs at least two states")
    if any(len(state) != 3 for state in raw):
        raise ValueError("every state must be a (row, col, slice) triple")
    if raw[0][2] != 0:
        raise ValueError(f"the route must start at slice 0, not {raw[0][2]}")

    slopes = np.asarray(slope, dtype=np.float64)
    rows, cols = slopes.shape
    step = float(slice_hours)
    if not (step > 0.0):
        raise ValueError("slice_hours must be positive")
    res = float(resolution_m)
    p_base_w = float(rover["p_base_w"])
    mu_coeff = float(rover["mu_coeff"])

    cells = np.zeros((len(raw), 2), dtype=np.int64)
    slices = np.zeros(len(raw), dtype=np.int64)
    for index, (r, c, t) in enumerate(raw):
        if not (0 <= r < rows and 0 <= c < cols):
            raise ValueError(
                f"state {index} ({r}, {c}, {t}) is outside the {rows}x{cols} grid"
            )
        if traversable is not None and not bool(traversable[r, c]):
            raise ValueError(f"state {index} ({r}, {c}, {t}) is not traversable")
        if index > 0 and t <= raw[index - 1][2]:
            raise ValueError(
                f"slices must increase along the route; state {index} is at "
                f"slice {t} after slice {raw[index - 1][2]}"
            )
        cells[index] = (r, c)
        slices[index] = t

    n_legs = len(raw) - 1
    is_wait = np.zeros(n_legs, dtype=bool)
    distance = np.zeros(n_legs, dtype=np.float64)
    travel = np.zeros(n_legs, dtype=np.float64)
    traction = np.zeros(n_legs, dtype=np.float64)
    diag_m = res * math.sqrt(2.0)
    for index in range(n_legs):
        (r0, c0), (r1, c1) = cells[index], cells[index + 1]
        d_row, d_col = int(r1 - r0), int(c1 - c0)
        if d_row == 0 and d_col == 0:
            is_wait[index] = True
            continue
        if max(abs(d_row), abs(d_col)) != 1:
            raise ValueError(
                f"states {index} and {index + 1} are not adjacent: "
                f"({r0}, {c0}) -> ({r1}, {c1})"
            )
        diagonal = d_row != 0 and d_col != 0
        distance[index] = diag_m if diagonal else res
        # Trapezoidal, as astar_4d and pathfinder._astar_core price it.
        edge_slope = 0.5 * (float(slopes[r0, c0]) + float(slopes[r1, c1]))
        seconds = edge_travel_time_s(edge_slope, distance[index], rover)
        if not math.isfinite(seconds):
            raise ValueError(
                f"the edge from state {index} ({r0}, {c0}) to ({r1}, {c1}) has "
                f"slope {edge_slope:.1f} deg, which the travel-time model cannot cross"
            )
        travel[index] = seconds / 3600.0
        traction[index] = p_base_w * (
            1.0 + mu_coeff * math.sin(math.radians(max(0.0, edge_slope)))
        )

    return RouteLegs(
        cells=cells,
        slices=slices,
        planned_h=slices.astype(np.float64) * step,
        is_wait=is_wait,
        distance_m=distance,
        travel_h=travel,
        traction_w=traction,
        slice_hours=step,
    )


# ── The sky along the route ────────────────────────────────────────────────

#: Exposure at or above this counts as shadow for the continuous-shadow
#: clock and for "wait until it is lit" -- the planner's threshold
#: (pathfinder_4d._DARK_RATIO_THRESHOLD, safe_haven._DARK_RATIO_THRESHOLD).
DARK_RATIO_THRESHOLD: float = 0.5


def _next_time_table(mask: np.ndarray, slice_hours: float) -> np.ndarray:
    """``(T, S)``: the absolute hour at which the first True slice at or
    after slice ``t`` begins; ``inf`` where there is none."""
    flags = np.asarray(mask, dtype=bool)
    n_slices = flags.shape[0]
    out = np.full(flags.shape, np.inf, dtype=np.float64)
    following = np.full(flags.shape[1:], np.inf, dtype=np.float64)
    for index in range(n_slices - 1, -1, -1):
        here = np.where(flags[index], index * float(slice_hours), following)
        out[index] = here
        following = here
    return out


@dataclass
class RouteSky:
    """The environment along the route, one column per route state:
    shadow ratio per slice, Earth link per slice, hours of link left per
    slice (VIPER's deadline) and hours to the nearest safe haven -- the
    last three optional, ``None`` when the input was not available."""

    shadow: np.ndarray                 # (T, S) in [0, 1]
    earth: np.ndarray | None           # (T, S) bool
    deadline_h: np.ndarray | None      # (T, S) hours until Earthset, inf open-ended
    tts_h: np.ndarray | None           # (S,) hours to the nearest haven, inf unreachable
    slice_hours: float
    time_varying: bool = True
    # Derived tables, filled in __post_init__.
    cumulative: np.ndarray = None  # type: ignore[assignment]
    next_dark_h: np.ndarray = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.shadow = np.clip(np.asarray(self.shadow, dtype=np.float64), 0.0, 1.0)
        if self.shadow.ndim != 2:
            raise ValueError(f"shadow columns must be (T, S), got {self.shadow.shape}")
        if self.earth is not None:
            self.earth = np.asarray(self.earth, dtype=bool)
            if self.earth.shape != self.shadow.shape:
                raise ValueError("earth columns must match the shadow columns")
        if self.deadline_h is not None:
            self.deadline_h = np.asarray(self.deadline_h, dtype=np.float64)
            if self.deadline_h.shape != self.shadow.shape:
                raise ValueError("deadline columns must match the shadow columns")
        if self.tts_h is not None:
            self.tts_h = np.asarray(self.tts_h, dtype=np.float64)
            if self.tts_h.shape != (self.shadow.shape[1],):
                raise ValueError("tts_h must have one entry per route state")
        self.slice_hours = float(self.slice_hours)
        if not (self.slice_hours > 0.0):
            raise ValueError("slice_hours must be positive")
        # Exposure integral: cumulative[t] = sum_{u < t} shadow[u] * slice_hours,
        # so the mean exposure over any [a, b] is exact for the piecewise-
        # constant columns.
        self.cumulative = np.vstack(
            [np.zeros((1, self.shadow.shape[1])), np.cumsum(self.shadow, axis=0)]
        ) * self.slice_hours
        # Absolute hour at which each cell next goes dark, per slice: SHERPA's
        # time-to-sun-shadow read at any instant.
        self.next_dark_h = _next_time_table(
            self.shadow >= DARK_RATIO_THRESHOLD, self.slice_hours
        )

    @property
    def n_slices(self) -> int:
        return int(self.shadow.shape[0])

    @property
    def horizon_h(self) -> float:
        return self.n_slices * self.slice_hours

    @classmethod
    def from_cubes(
        cls,
        shadow_cube: np.ndarray,
        earth_cube: np.ndarray | None,
        deadline_cube: np.ndarray | None,
        tts: np.ndarray | None,
        cells: Any,
        slice_hours: float,
        time_varying: bool = True,
    ) -> "RouteSky":
        """Pull the route's columns out of the planner's ``(T, H, W)`` cubes."""
        rows = np.asarray([int(cell[0]) for cell in cells])
        cols = np.asarray([int(cell[1]) for cell in cells])
        shadow = np.asarray(shadow_cube, dtype=np.float64)[:, rows, cols]
        earth = None if earth_cube is None else np.asarray(earth_cube, dtype=bool)[:, rows, cols]
        deadline = (
            None
            if deadline_cube is None
            else np.asarray(deadline_cube, dtype=np.float64)[:, rows, cols]
        )
        tts_h = None if tts is None else np.asarray(tts, dtype=np.float64)[rows, cols]
        return cls(shadow, earth, deadline, tts_h, slice_hours, time_varying)


def route_sky_columns(
    horizon: np.ndarray,
    metadata: dict[str, Any],
    cells: Any,
    coarsen: int,
    start_utc: str,
    n_slices: int,
    slice_hours: float,
) -> tuple[np.ndarray, np.ndarray]:
    """``(shadow (T, S), earth (T, S))`` for the route's coarse cells, from
    the fine horizon cube and the Sun's and the Earth's tracks.

    Exactly what ``/api/plan-4d`` puts in its cubes for those cells -- the
    block MEAN of the fine cells' instantaneous shadow (``coarsen_grid``)
    and the block AND of their Earth visibility (``coarsen_traversable``) --
    computed for the route's cells only, so a horizon many times longer
    than the plan's costs milliseconds rather than a full-grid series.
    Raises whatever spiceypy raises without kernels; the caller decides.
    """
    from .illumination import illuminated_mask
    from .illumination_series import body_track_for_series

    cube = np.asarray(horizon)
    if cube.ndim != 3:
        raise ValueError(f"horizon must be (n_azimuth, H, W), got {cube.shape}")
    factor = max(1, int(coarsen))
    rows = np.asarray([int(cell[0]) for cell in cells])
    cols = np.asarray([int(cell[1]) for cell in cells])
    offsets = np.arange(factor)
    # (S, f, f) fine indices of each coarse block.
    fine_rows = np.broadcast_to(
        rows[:, None, None] * factor + offsets[None, :, None], (rows.size, factor, factor)
    )
    fine_cols = np.broadcast_to(
        cols[:, None, None] * factor + offsets[None, None, :], (rows.size, factor, factor)
    )
    if fine_rows.max() >= cube.shape[1] or fine_cols.max() >= cube.shape[2]:
        raise ValueError("a route cell's fine block lies outside the horizon cube")
    # (n_az, S, f*f): the horizon profiles of every fine cell on the route.
    profiles = cube[:, fine_rows.reshape(-1), fine_cols.reshape(-1)].reshape(
        cube.shape[0], rows.size, factor * factor
    )

    count = int(n_slices)
    sun = body_track_for_series(metadata, count, slice_hours, start_utc, body="SUN")
    earth_track = body_track_for_series(metadata, count, slice_hours, start_utc, body="EARTH")
    shadow = np.empty((count, rows.size), dtype=np.float64)
    earth = np.empty((count, rows.size), dtype=bool)
    for index in range(count):
        lit = illuminated_mask(
            profiles, sun[index]["azimuth_grid_deg"], sun[index]["elevation_deg"]
        )
        shadow[index] = 1.0 - lit.mean(axis=1)
        seen = illuminated_mask(
            profiles,
            earth_track[index]["azimuth_grid_deg"],
            earth_track[index]["elevation_deg"],
        )
        earth[index] = seen.all(axis=1)
    return shadow, earth


# ── Executing the route N times ────────────────────────────────────────────

#: First cause of a run's failure, indexed by ``RunResults.first_failure``.
FAILURE_NAMES: tuple[str, ...] = (
    "none",
    "battery_depleted",
    "shadow_endurance",
    "horizon_exceeded",
)
_FAIL_BATTERY, _FAIL_SHADOW, _FAIL_HORIZON = 1, 2, 3


@dataclass
class RunResults:
    """Per-run outcomes of :func:`simulate_runs` -- ``(N,)`` arrays, plus the
    per-state envelope ``(S, N)``. Margins are NaN where open-ended or
    unknown (never a fabricated number)."""

    reached: np.ndarray
    first_failure: np.ndarray
    duration_h: np.ndarray
    odometry_m: np.ndarray
    min_battery_wh: np.ndarray
    final_battery_wh: np.ndarray
    max_dark_h: np.ndarray
    reserve_breached: np.ndarray
    tts_sun_min_h: np.ndarray
    tts_sun_mean_h: np.ndarray
    tts_dsn_min_h: np.ndarray
    tts_zero_soc_min_h: np.ndarray
    dsn_events: np.ndarray
    dsn_shadow_h: np.ndarray
    states_past_deadline: np.ndarray
    dsn_hold_h: np.ndarray
    sep_hold_h: np.ndarray
    arrival_h: np.ndarray
    battery_wh: np.ndarray
    alive: np.ndarray
    # Mobility faults (B1): how many struck each run and the hours they
    # cost. Zeros when the samples carried none.
    fault_count: np.ndarray | None = None
    fault_hold_h: np.ndarray | None = None

    @property
    def n_runs(self) -> int:
        return int(self.reached.shape[0])


def simulate_runs(
    legs: RouteLegs,
    sky: RouteSky,
    rover: Any,
    samples: dict[str, np.ndarray],
    dark_threshold: float = DARK_RATIO_THRESHOLD,
    fault_recovery_h: float = 0.0,
) -> RunResults:
    """Execute the route once per sampled run, all runs at once.

    Mobility faults (B1): ``samples["fault_positions_m"]`` are odometer
    readings; a fault in the first half of a move holds the rover
    *fault_recovery_h* hours in the origin cell before it departs, one in
    the second half holds it in the destination cell after it arrives, at
    housekeeping power minus solar income. The route itself is unchanged
    (SHERPA replays a fixed plan), so this is the risk of the PLAN executed
    as planned, not of the recovery policy.

    The clock is continuous; the sky is read per slice. Policy (SHERPA's
    operator): a MOVE departs at ``max(clock, planned departure)`` -- ahead
    of schedule the rover holds where it is, behind it drives on, through
    shadow on the battery; a planned WAIT ends at its planned end, or is
    skipped when the rover is already past it. A DSN outage or SEP window
    that covers a departure delays it to the window's end.

    Energy is the planner's: a drive drains ``(traction + housekeeping) *
    power_multiplier - solar income`` over its (speed-scaled) duration with
    the exact time-mean exposure of the two cells (``cost_engine.
    move_battery_drain_wh``); a hold drains ``housekeeping * power_multiplier
    - solar`` (``wait_battery_drain_wh``); the battery is capped at
    capacity. The continuous-shadow clock follows the planner's rule on the
    exposure at the end of each transition. A run fails -- first cause kept
    -- when it outlasts the sky, drains the battery below zero, or exceeds
    ``h_max_shadow_h``; dipping under the ``soc_min_pct`` reserve is flagged,
    not fatal.
    """
    n_states = legs.n_states
    if sky.shadow.shape[1] != n_states:
        raise ValueError(
            f"the sky has {sky.shadow.shape[1]} columns for a route of {n_states} states"
        )
    delay = np.asarray(samples["start_delay_h"], dtype=np.float64)
    n_runs = int(delay.shape[0])
    m_speed = np.asarray(samples["speed_multiplier"], dtype=np.float64)
    m_power = np.asarray(samples["power_multiplier"], dtype=np.float64)
    soc0 = np.asarray(samples["initial_soc_frac"], dtype=np.float64)
    windows = (
        (
            np.asarray(samples["dsn_event"], dtype=bool),
            np.asarray(samples["dsn_start_h"], dtype=np.float64),
            np.asarray(samples["dsn_end_h"], dtype=np.float64),
        ),
        (
            np.asarray(samples["sep_event"], dtype=bool),
            np.asarray(samples["sep_start_h"], dtype=np.float64),
            np.asarray(samples["sep_end_h"], dtype=np.float64),
        ),
    )

    step = sky.slice_hours
    n_slices = sky.n_slices
    horizon_h = sky.horizon_h
    times = np.arange(n_slices + 1, dtype=np.float64) * step
    shadow = sky.shadow
    cumulative = sky.cumulative
    thr = float(dark_threshold)

    e_cap_wh = float(rover["e_cap_wh"])
    reserve_wh = e_cap_wh * float(rover.get("soc_min_pct") or 0.0)
    h_max = float(rover.get("h_max_shadow_h") or np.inf)
    if not (h_max > 0.0):
        h_max = np.inf
    p_idle_w = float(rover["p_idle_w"])
    p_shadow_w = rover.get("p_shadow_w")
    shadow_extra_w = (
        max(0.0, float(p_shadow_w) - p_idle_w)
        if p_shadow_w is not None
        else float(rover.get("p_heater_w") or 0.0)
    )
    p_solar_w = float(rover.get("p_solar_w") or 0.0)
    dark_w = p_idle_w + shadow_extra_w

    def housekeeping(exposure: np.ndarray) -> np.ndarray:
        return p_idle_w + exposure * shadow_extra_w

    def slice_of(x: np.ndarray) -> np.ndarray:
        return np.clip(np.floor(x / step), 0, n_slices - 1).astype(np.int64)

    def exposure_mean(column: int, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """Time-mean shadow of *column* over [a, b]; the instant value at a
        when the interval is empty."""
        span = b - a
        integral = np.interp(b, times, cumulative[:, column]) - np.interp(
            a, times, cumulative[:, column]
        )
        with np.errstate(divide="ignore", invalid="ignore"):
            mean = np.where(span > 0.0, integral / np.where(span > 0.0, span, 1.0), 0.0)
        return np.where(span > 0.0, mean, shadow[slice_of(a), column])

    clock = delay.copy()
    battery = soc0 * e_cap_wh
    dark = np.zeros(n_runs)
    alive = np.ones(n_runs, dtype=bool)
    failure = np.zeros(n_runs, dtype=np.int8)
    distance = np.zeros(n_runs)
    end_clock = clock.copy()
    min_battery = battery.copy()
    max_dark = np.zeros(n_runs)
    reserve_breached = battery < reserve_wh

    arrival = np.full((n_states, n_runs), np.nan)
    battery_at = np.full((n_states, n_runs), np.nan)
    alive_at = np.zeros((n_states, n_runs), dtype=bool)
    arrival[0] = clock
    battery_at[0] = battery
    alive_at[0] = True

    sun_min = np.full(n_runs, np.inf)
    sun_sum = np.zeros(n_runs)
    sun_count = np.zeros(n_runs, dtype=np.int64)
    dsn_min = np.full(n_runs, np.inf)
    dsn_events = np.zeros(n_runs, dtype=np.int64)
    dsn_hours = np.zeros(n_runs)
    link = np.ones(n_runs, dtype=bool)
    past_deadline = np.zeros(n_runs, dtype=np.int64)
    holds = [np.zeros(n_runs), np.zeros(n_runs)]
    haven_fields = sky.deadline_h is not None and sky.tts_h is not None
    positions = samples.get("fault_positions_m")
    fault_positions = (
        np.full((n_runs, 1), np.nan)
        if positions is None
        else np.asarray(positions, dtype=np.float64).reshape(n_runs, -1)
    )
    recovery_h = max(0.0, float(fault_recovery_h))
    fault_count = np.zeros(n_runs, dtype=np.int64)
    fault_hold = np.zeros(n_runs)
    odometer = 0.0

    def faults_between(lo: float, hi: float) -> np.ndarray:
        with np.errstate(invalid="ignore"):
            return np.count_nonzero((fault_positions >= lo) & (fault_positions < hi), axis=1)

    def record_margins(state: int, mask: np.ndarray) -> None:
        nonlocal link
        index = slice_of(clock)
        offset = clock - index * step
        to_dark = sky.next_dark_h[index, state] - clock
        to_dark = np.where(to_dark < 0.0, 0.0, to_dark)
        counted = mask & np.isfinite(to_dark)
        sun_min[counted] = np.minimum(sun_min[counted], to_dark[counted])
        sun_sum[counted] += to_dark[counted]
        sun_count[counted] += 1
        if sky.earth is not None:
            now = sky.earth[index, state]
            dsn_events[mask & link & ~now] += 1
            link = np.where(mask, now, link)
        if sky.deadline_h is not None:
            left = sky.deadline_h[index, state]
            left = np.where(np.isfinite(left), np.maximum(0.0, left - offset), left)
            finite = mask & np.isfinite(left)
            dsn_min[finite] = np.minimum(dsn_min[finite], left[finite])
            if haven_fields:
                past_deadline[mask & (sky.tts_h[state] > left + 1e-9)] += 1

    record_margins(0, alive)

    for leg in range(n_states - 1):
        mask = alive.copy()
        if not mask.any():
            break
        s_from, s_to = leg, leg + 1
        if legs.is_wait[leg]:
            depart = np.maximum(clock, legs.planned_h[s_to])
        else:
            depart = np.maximum(clock, legs.planned_h[s_from])
        # A departure inside an outage window waits for the window to end;
        # twice, so a DSN end that lands inside a SEP window is caught.
        for _ in range(2):
            for which, (event, start, end) in enumerate(windows):
                covered = mask & event & (depart >= start) & (depart < end)
                holds[which] += np.where(covered, end - depart, 0.0)
                depart = np.where(covered, end, depart)
        # A fault in the first half of this move pins the rover in the
        # origin cell for the recovery time before it can depart. (B1.)
        if not legs.is_wait[leg]:
            leg_m = float(legs.distance_m[leg])
            first = np.where(mask, faults_between(odometer, odometer + 0.5 * leg_m), 0)
            second = np.where(mask, faults_between(odometer + 0.5 * leg_m, odometer + leg_m), 0)
            odometer += leg_m
            first_hold = first * recovery_h
            depart = depart + first_hold
            fault_count += first + second
            fault_hold += first_hold
        else:
            second = np.zeros(n_runs, dtype=np.int64)

        # The hold at s_from, if any.
        hold = depart - clock
        held = mask & (hold > 0.0)
        exposure = exposure_mean(s_from, clock, depart)
        drain = (housekeeping(exposure) * m_power - p_solar_w * (1.0 - exposure)) * hold
        battery = np.where(held, np.minimum(e_cap_wh, battery - drain), battery)
        end_exposure = shadow[slice_of(depart), s_from]
        dark = np.where(
            held, np.where(end_exposure >= thr, dark + hold * end_exposure, 0.0), dark
        )
        if sky.earth is not None:
            dsn_hours += np.where(held & ~link, hold, 0.0)
        min_battery = np.where(held, np.minimum(min_battery, battery), min_battery)
        max_dark = np.where(held, np.maximum(max_dark, dark), max_dark)
        reserve_breached |= held & (battery < reserve_wh)

        if legs.is_wait[leg]:
            arrive = depart
        else:
            travel = np.where(mask, legs.travel_h[leg] / m_speed, 0.0)
            arrive = depart + travel
            exposure = 0.5 * (
                exposure_mean(s_from, depart, arrive) + exposure_mean(s_to, depart, arrive)
            )
            drain = (
                legs.traction_w[leg] * m_power
                + housekeeping(exposure) * m_power
                - p_solar_w * (1.0 - exposure)
            ) * travel
            battery = np.where(mask, np.minimum(e_cap_wh, battery - drain), battery)
            end_exposure = shadow[slice_of(arrive), s_to]
            dark = np.where(
                mask, np.where(end_exposure >= thr, dark + travel * end_exposure, 0.0), dark
            )
            if sky.earth is not None:
                dsn_hours += np.where(mask & ~link, travel, 0.0)
            min_battery = np.where(mask, np.minimum(min_battery, battery), min_battery)
            max_dark = np.where(mask, np.maximum(max_dark, dark), max_dark)
            reserve_breached |= mask & (battery < reserve_wh)

            # A fault in the second half pins the rover in the destination
            # cell for the recovery time after it arrives. (B1.)
            second_hold = second * recovery_h
            pinned = mask & (second_hold > 0.0)
            if pinned.any():
                hold_end = arrive + second_hold
                exposure = exposure_mean(s_to, arrive, hold_end)
                drain = (housekeeping(exposure) * m_power - p_solar_w * (1.0 - exposure)) * second_hold
                battery = np.where(pinned, np.minimum(e_cap_wh, battery - drain), battery)
                end_exposure = shadow[slice_of(hold_end), s_to]
                dark = np.where(
                    pinned,
                    np.where(end_exposure >= thr, dark + second_hold * end_exposure, 0.0),
                    dark,
                )
                if sky.earth is not None:
                    dsn_hours += np.where(pinned & ~link, second_hold, 0.0)
                min_battery = np.where(pinned, np.minimum(min_battery, battery), min_battery)
                max_dark = np.where(pinned, np.maximum(max_dark, dark), max_dark)
                reserve_breached |= pinned & (battery < reserve_wh)
                fault_hold += second_hold
                arrive = np.where(pinned, hold_end, arrive)

        cause = np.where(
            arrive > horizon_h + 1e-9,
            _FAIL_HORIZON,
            np.where(battery < 0.0, _FAIL_BATTERY, np.where(dark > h_max + 1e-9, _FAIL_SHADOW, 0)),
        ).astype(np.int8)
        died = mask & (cause > 0)
        failure = np.where(died, cause, failure)
        end_clock = np.where(mask, arrive, end_clock)
        clock = np.where(mask, arrive, clock)
        alive = mask & ~died
        distance = np.where(alive, distance + legs.distance_m[leg], distance)
        arrival[s_to] = np.where(alive, arrive, np.nan)
        battery_at[s_to] = np.where(alive, battery, np.nan)
        alive_at[s_to] = alive
        record_margins(s_to, alive)

    with np.errstate(invalid="ignore", divide="ignore"):
        sun_mean = np.where(sun_count > 0, sun_sum / np.maximum(sun_count, 1), np.nan)
    sun_min = np.where(np.isfinite(sun_min), sun_min, np.nan)
    dsn_min = np.where(np.isfinite(dsn_min), dsn_min, np.nan)
    if dark_w > 0.0:
        zero_soc = np.maximum(0.0, min_battery) / (dark_w * m_power)
    else:
        zero_soc = np.full(n_runs, np.nan)

    return RunResults(
        reached=alive,
        first_failure=failure,
        duration_h=end_clock,
        odometry_m=distance,
        min_battery_wh=min_battery,
        final_battery_wh=battery,
        max_dark_h=max_dark,
        reserve_breached=reserve_breached,
        tts_sun_min_h=sun_min,
        tts_sun_mean_h=sun_mean,
        tts_dsn_min_h=dsn_min,
        tts_zero_soc_min_h=zero_soc,
        dsn_events=dsn_events,
        dsn_shadow_h=dsn_hours,
        states_past_deadline=(
            past_deadline.astype(np.float64) if haven_fields else np.full(n_runs, np.nan)
        ),
        dsn_hold_h=holds[0],
        sep_hold_h=holds[1],
        arrival_h=arrival,
        battery_wh=battery_at,
        alive=alive_at,
        fault_count=fault_count,
        fault_hold_h=fault_hold,
    )


# ── The summary the endpoint publishes ─────────────────────────────────────

#: Where SHERPA's distributions come from.
PERTURBATION_SOURCE: str = (
    "Shirley & Balaban 2022, 'An Overview of Mission Planning for the VIPER "
    "Rover' (Traverse Evaluation use case); Balaban et al., SHERPA, SpaceOps 2025"
)


def _finite(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64).ravel()
    return arr[np.isfinite(arr)]


def _distribution(values: np.ndarray, digits: int = 4) -> dict[str, Any] | None:
    """mean / std / p5 / p50 / p95 / min / max / n over the finite values;
    ``None`` when there are none."""
    finite = _finite(values)
    if finite.size == 0:
        return None
    p5, p50, p95 = np.percentile(finite, [5.0, 50.0, 95.0])
    return {
        "mean": round(float(np.mean(finite)), digits),
        "std": round(float(np.std(finite)), digits),
        "p5": round(float(p5), digits),
        "p50": round(float(p50), digits),
        "p95": round(float(p95), digits),
        "min": round(float(np.min(finite)), digits),
        "max": round(float(np.max(finite)), digits),
        "n": int(finite.size),
    }


def _histogram(values: np.ndarray, n_bins: int) -> dict[str, list[float]] | None:
    finite = _finite(values)
    if finite.size == 0:
        return None
    low, high = float(np.min(finite)), float(np.max(finite))
    if high <= low:
        high = low + 1.0
    counts, edges = np.histogram(finite, bins=int(n_bins), range=(low, high))
    return {
        "edges": [round(float(e), 4) for e in edges],
        "counts": [int(c) for c in counts],
    }


def _rate(mask: np.ndarray) -> dict[str, Any]:
    flags = np.asarray(mask, dtype=bool)
    n = int(flags.size)
    count = int(flags.sum())
    low, high = wilson_interval(count, n)
    return {
        "count": count,
        "rate": round(count / n, 4) if n else None,
        "ci95": [round(low, 4), round(high, 4)],
    }


def _percentile_rows(matrix: np.ndarray, digits: int = 4) -> dict[str, list[float | None]]:
    """p5 / p50 / p95 per row of an ``(S, N)`` matrix, ignoring NaN; ``None``
    where a row has no finite value."""
    out: dict[str, list[float | None]] = {"p5": [], "p50": [], "p95": []}
    for row in np.asarray(matrix, dtype=np.float64):
        finite = row[np.isfinite(row)]
        if finite.size == 0:
            for key in out:
                out[key].append(None)
            continue
        p5, p50, p95 = np.percentile(finite, [5.0, 50.0, 95.0])
        out["p5"].append(round(float(p5), digits))
        out["p50"].append(round(float(p50), digits))
        out["p95"].append(round(float(p95), digits))
    return out


def _nullable(value: float, digits: int = 4) -> float | None:
    v = float(value)
    return round(v, digits) if math.isfinite(v) else None


def full_success_mask(results: RunResults) -> np.ndarray:
    """Reached the goal, never dipped under the reserve and -- when the
    haven fields are known -- never sat past its Earthset deadline."""
    mask = results.reached & ~results.reserve_breached
    past = results.states_past_deadline
    known = np.isfinite(past)
    return mask & (~known | (past <= 0))


def summarize_runs(
    results: RunResults,
    legs: RouteLegs,
    sky: RouteSky,
    rover: Any,
    samples: dict[str, np.ndarray],
    n_bins: int = 20,
) -> dict[str, Any]:
    """SHERPA's metric set over the runs, JSON-ready: rates with Wilson
    intervals, the first-cause failure counts, per-metric distributions,
    histograms, the per-state envelope, the injected outages and a verdict."""
    e_cap_wh = float(rover["e_cap_wh"])
    n = results.n_runs
    pct = 100.0 / e_cap_wh if e_cap_wh > 0.0 else 0.0
    min_battery_pct = np.maximum(0.0, results.min_battery_wh) * pct
    final_battery_pct = np.maximum(0.0, results.final_battery_wh) * pct
    planned = legs.planned_duration_h
    normalized = (
        results.duration_h / planned if planned > 0.0 else np.full(n, np.nan)
    )

    metric_values: dict[str, np.ndarray] = {
        "duration_h": results.duration_h,
        "duration_normalized": normalized,
        "odometry_m": results.odometry_m,
        "min_battery_pct": min_battery_pct,
        "final_battery_pct": final_battery_pct,
        "max_continuous_shadow_h": results.max_dark_h,
        "time_to_sun_shadow_min_h": results.tts_sun_min_h,
        "time_to_sun_shadow_mean_h": results.tts_sun_mean_h,
        "time_to_dsn_shadow_min_h": results.tts_dsn_min_h,
        "time_to_zero_soc_min_h": results.tts_zero_soc_min_h,
        "dsn_shadow_events": (
            results.dsn_events.astype(np.float64)
            if sky.earth is not None
            else np.full(n, np.nan)
        ),
        "dsn_shadow_hours": (
            results.dsn_shadow_h if sky.earth is not None else np.full(n, np.nan)
        ),
        "states_past_haven_deadline": results.states_past_deadline,
        "fault_hold_h": (
            np.zeros(n) if results.fault_hold_h is None else np.asarray(results.fault_hold_h, dtype=np.float64)
        ),
        "start_delay_h": np.asarray(samples["start_delay_h"], dtype=np.float64),
        "speed_multiplier": np.asarray(samples["speed_multiplier"], dtype=np.float64),
        "power_multiplier": np.asarray(samples["power_multiplier"], dtype=np.float64),
        "initial_soc_pct": 100.0 * np.asarray(samples["initial_soc_frac"], dtype=np.float64),
    }
    metrics = {key: _distribution(values) for key, values in metric_values.items()}

    histograms: dict[str, Any] = {}
    for key in (
        "duration_h",
        "min_battery_pct",
        "final_battery_pct",
        "max_continuous_shadow_h",
        "time_to_sun_shadow_min_h",
        "time_to_dsn_shadow_min_h",
        "time_to_zero_soc_min_h",
    ):
        hist = _histogram(metric_values[key], n_bins)
        if hist is not None:
            histograms[key] = hist

    completion = _rate(results.reached)
    within_reserve = _rate(results.reached & ~results.reserve_breached)
    full_success = _rate(full_success_mask(results))
    haven_rule_known = sky.deadline_h is not None and sky.tts_h is not None
    failures = {
        name: int(np.count_nonzero(results.first_failure == index))
        for index, name in enumerate(FAILURE_NAMES)
        if index > 0
    }

    def _outage(event_key: str, start_key: str, end_key: str, hold: np.ndarray) -> dict[str, Any]:
        event = np.asarray(samples[event_key], dtype=bool)
        runs = int(event.sum())
        if runs == 0:
            return {"runs": 0, "mean_window_h": None, "mean_hold_h": None}
        window = np.asarray(samples[end_key], dtype=np.float64) - np.asarray(
            samples[start_key], dtype=np.float64
        )
        return {
            "runs": runs,
            "mean_window_h": round(float(np.mean(window[event])), 4),
            "mean_hold_h": round(float(np.mean(hold[event])), 4),
        }

    reaches = completion["ci95"][0] >= 0.95
    full_at_95 = full_success["ci95"][0] >= 0.95
    text = (
        f"{completion['count']}/{n} runs reached the goal (95% CI "
        f"{100.0 * completion['ci95'][0]:.1f}-{100.0 * completion['ci95'][1]:.1f}%), "
        f"{within_reserve['count']}/{n} without touching the reserve; "
        f"{full_success['count']}/{n} with every margin intact (95% CI "
        f"{100.0 * full_success['ci95'][0]:.1f}-{100.0 * full_success['ci95'][1]:.1f}%)."
    )
    ends_at_haven = None if sky.tts_h is None else bool(sky.tts_h[-1] <= 1e-9)
    if haven_rule_known and full_success["count"] < within_reserve["count"]:
        # Say what the haven rule cost, so a zero is not read as a rover
        # that died: on a lunar day with no haven in reach, every state
        # is past its deadline by definition (A1).
        if not np.isfinite(sky.tts_h).any():
            text += (
                " No safe haven is reachable from any state of this route on "
                "this lunar day, so the haven rule fails every run."
            )
        else:
            text += (
                f" The haven rule (reach a safe haven before the Earth sets) "
                f"failed {within_reserve['count'] - full_success['count']} of the "
                "runs that finished within the reserve."
            )
    elif not haven_rule_known:
        text += " The safe haven rule could not be checked (no Earthset deadline)."

    return {
        "n_runs": n,
        "route": {
            "n_states": legs.n_states,
            "move_steps": legs.n_moves,
            "wait_steps": legs.n_waits,
            "planned_duration_h": round(planned, 4),
            "odometry_m": round(legs.odometry_m, 3),
            "ends_at_safe_haven": ends_at_haven,
        },
        "rates": {
            "completion": completion,
            "reached_within_reserve": within_reserve,
            "full_success": full_success,
            "reserve_breached": _rate(results.reserve_breached),
        },
        "failures": failures,
        "metrics": metrics,
        "histograms": histograms,
        "per_state": {
            "arrival_h": _percentile_rows(results.arrival_h),
            "battery_pct": _percentile_rows(np.maximum(0.0, results.battery_wh) * pct),
            "alive_fraction": [
                round(float(np.mean(row)), 4) for row in results.alive
            ],
        },
        "outages": {
            "dsn": _outage("dsn_event", "dsn_start_h", "dsn_end_h", results.dsn_hold_h),
            "sep": _outage("sep_event", "sep_start_h", "sep_end_h", results.sep_hold_h),
        },
        # Mobility faults injected along the fixed route (B1): the rate and
        # recovery time are filled in by stress_test_route, which knows the
        # perturbations; here the counts.
        "faults": {
            "runs_with_fault": (
                0 if results.fault_count is None else int(np.count_nonzero(results.fault_count > 0))
            ),
            "total_faults": 0 if results.fault_count is None else int(results.fault_count.sum()),
            "mean_faults": (
                0.0 if results.fault_count is None else round(float(np.mean(results.fault_count)), 4)
            ),
            "mean_hold_h": (
                0.0 if results.fault_hold_h is None else round(float(np.mean(results.fault_hold_h)), 4)
            ),
        },
        "verdict": {
            "reaches_goal_at_95pct": bool(reaches),
            "full_success_at_95pct": bool(full_at_95),
            "haven_rule_known": bool(haven_rule_known),
            "text": text,
        },
    }


def _nominal_samples(initial_soc_frac: float) -> dict[str, np.ndarray]:
    """One run with every uncertainty at its nominal value."""
    return sample_perturbations(
        np.random.default_rng(0),
        1,
        Perturbations(
            start_delay_sigma_h=0.0,
            initial_soc_sigma=0.0,
            power_draw_sigma=0.0,
            speed_sigma=0.0,
            dsn_outage_probability=0.0,
            sep_event_probability=0.0,
        ),
        initial_soc_frac,
        0.0,
    )


def stress_test_route(
    legs: RouteLegs,
    sky: RouteSky,
    rover: Any,
    initial_soc_frac: float = 1.0,
    n_runs: int = 1000,
    seed: int = 0,
    perturbations: Perturbations = SHERPA_DEFAULTS,
    n_bins: int = 20,
) -> dict[str, Any]:
    """Sample, execute and summarise; plus the unperturbed run for reference."""
    import time

    t0 = time.perf_counter()
    rng = np.random.default_rng(int(seed))
    samples = sample_perturbations(
        rng, int(n_runs), perturbations, initial_soc_frac, legs.planned_duration_h,
        route_distance_m=legs.odometry_m,
    )
    results = simulate_runs(legs, sky, rover, samples, fault_recovery_h=perturbations.fault_recovery_h)
    summary = summarize_runs(results, legs, sky, rover, samples, n_bins=n_bins)
    summary["faults"].update(
        {
            "rate_per_km": float(perturbations.fault_rate_per_km),
            "recovery_h": float(perturbations.fault_recovery_h),
            "source": FAILURE_MODEL_SOURCE,
            "policy": (
                "the fixed plan is resumed after every hold (SHERPA replays the route); "
                "the recovery policy's own risk is app.survival.rollout"
            ),
        }
    )

    nominal = simulate_runs(legs, sky, rover, _nominal_samples(initial_soc_frac))
    e_cap_wh = float(rover["e_cap_wh"])
    pct = 100.0 / e_cap_wh if e_cap_wh > 0.0 else 0.0
    summary["nominal"] = {
        "reached": bool(nominal.reached[0]),
        "first_failure": FAILURE_NAMES[int(nominal.first_failure[0])],
        "duration_h": _nullable(nominal.duration_h[0]),
        "min_battery_pct": _nullable(max(0.0, float(nominal.min_battery_wh[0])) * pct),
        "final_battery_pct": _nullable(max(0.0, float(nominal.final_battery_wh[0])) * pct),
        "max_continuous_shadow_h": _nullable(nominal.max_dark_h[0]),
        "time_to_sun_shadow_min_h": _nullable(nominal.tts_sun_min_h[0]),
        "time_to_dsn_shadow_min_h": _nullable(nominal.tts_dsn_min_h[0]),
        "time_to_zero_soc_min_h": _nullable(nominal.tts_zero_soc_min_h[0]),
    }
    summary["seed"] = int(seed)
    summary["perturbations"] = {**perturbations.to_dict(), "source": PERTURBATION_SOURCE}
    summary["timing_ms"] = {"runs": round((time.perf_counter() - t0) * 1000.0, 3)}
    return summary
