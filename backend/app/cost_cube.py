"""Time-sliced cost cube for the 4-D planner.

Illumination on the lunar pole changes on the scale of hours, so cost is
not one grid but a stack of them -- one per time slice. Cells whose only
time-varying input is shadow get re-costed per slice; slope, energy and
thermal terms are shared.

Coarsening is not an optimisation, it is a scale decision (spec 3.1):
a 500x500 grid across 168 hourly slices is 42 M states / ~1.3 GB. Solving
time on a coarse grid is correct because illumination does not vary at
80 m resolution.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from .costmap import PlanContext, default_cost_map
from .roughness import RoughnessScale  # noqa: F401  (type of the roughness_scale argument)
from .thermal_model import (
    REGOLITH_THERMAL_TAU_S,
    relax_surface_c,
    shadowed_equilibrium_c,
    sunlit_peak_from_annual_peak_c,
)


def coarsen_grid(grid: np.ndarray, factor: int, how: str = "mean") -> np.ndarray:
    """Block-reduce a 2-D grid by an integer factor.

    ``how="center"`` returns the value at each block's CENTRE cell rather
    than a statistic over the block. That is the right reduction for
    elevation in the 4-D planner: ``/api/plan-4d`` publishes block centres as
    its waypoints, so the geometry a rover meets driving between two of them
    is the geometry AT those centres -- not the average of two blocks, which
    smooths the terrain and made the coarse step-slope gate reject nothing at
    all where the fine gate rejected 1 894 edges. (Round 4 review, L-11.)
    """
    arr = np.asarray(grid, dtype=np.float64)
    factor = int(factor)
    if factor <= 1:
        return arr
    height, width = arr.shape
    if height % factor or width % factor:
        raise ValueError(
            f"shape {arr.shape} is not divisible by coarsen factor {factor}"
        )
    blocks = arr.reshape(height // factor, factor, width // factor, factor)
    if how == "mean":
        return np.nanmean(blocks, axis=(1, 3))
    if how == "max":
        return np.nanmax(blocks, axis=(1, 3))
    if how == "center":
        offset = factor // 2
        return arr[offset::factor, offset::factor][
            : height // factor, : width // factor
        ]
    raise ValueError(f"unknown reduction: {how!r}")


def coarsen_traversable(traversable: np.ndarray, factor: int) -> np.ndarray:
    """Conservative: a coarse cell is passable only if all fine cells are."""
    mask = np.asarray(traversable, dtype=bool)
    factor = int(factor)
    if factor <= 1:
        return mask
    height, width = mask.shape
    if height % factor or width % factor:
        raise ValueError(
            f"shape {mask.shape} is not divisible by coarsen factor {factor}"
        )
    blocks = mask.reshape(height // factor, factor, width // factor, factor)
    return blocks.all(axis=(1, 3))


def surface_temperature_series(
    base_grids: Mapping[str, Any],
    shadow_ratio_series: Sequence[np.ndarray],
    coarsen: int = 1,
    slice_hours: float = 1.0,
    tau_s: float = REGOLITH_THERMAL_TAU_S,
    couple_thermal: bool = True,
) -> np.ndarray:
    """(T, H', W') surface temperature per slice, in Celsius (float64).

    This is the thermal state :func:`build_cost_cube` prices every slice
    at, factored out so the thermal dwell model (C6) can integrate the
    rover's inner temperature against the SAME surface the cube saw.

    The sunlit-peak field: data_loader publishes it directly -- it is the
    single stored statistic everything else is derived from -- so normally
    there is nothing to invert; the inversion is the fallback for a caller
    that assembled ``base_grids`` by hand from a corrected field. The
    initial state is the equilibrium under the cell's LONG-RUN illumination:
    starting every cell at its annual peak would assume the traverse begins
    at the hottest moment of the year, and the long-run equilibrium is the
    honest "we do not know where in the cycle this is" prior. Each slice
    then has an equilibrium target set by its own illumination and the
    surface relaxes toward it with the regolith time constant ``tau_s``
    (UNCALIBRATED; see thermal_model.REGOLITH_LAG_VALIDITY). With
    ``couple_thermal=False`` every slice is the stored (coarsened) field.
    """
    if len(shadow_ratio_series) == 0:
        raise ValueError("shadow_ratio_series must contain at least one snapshot")
    slope = np.asarray(base_grids["slope"], dtype=np.float64)
    thermal = np.asarray(base_grids["thermal"], dtype=np.float64)
    metadata = base_grids["metadata"]
    base_shadow = np.asarray(
        base_grids.get("shadow_ratio", shadow_ratio_series[0]), dtype=np.float64
    )
    already_coupled = bool(metadata.get("thermal_shadow_coupled", False))
    for index, snapshot in enumerate(shadow_ratio_series):
        if np.asarray(snapshot).shape != slope.shape:
            raise ValueError(
                f"shadow snapshot {index} has shape {np.asarray(snapshot).shape}, "
                f"expected {slope.shape}"
            )

    thermal_c = coarsen_grid(thermal, coarsen, how="mean")
    base_shadow_c = coarsen_grid(base_shadow, coarsen, how="mean")
    if not couple_thermal:
        return np.stack([thermal_c.copy() for _ in shadow_ratio_series], axis=0)

    sunlit = base_grids.get("thermal_sunlit_peak")
    if sunlit is not None:
        sunlit_c = coarsen_grid(np.asarray(sunlit, dtype=np.float64), coarsen)
    elif already_coupled:
        sunlit_c = np.asarray(
            sunlit_peak_from_annual_peak_c(thermal_c, base_shadow_c), dtype=np.float64
        )
    else:
        sunlit_c = thermal_c
    surface_state = np.asarray(
        shadowed_equilibrium_c(sunlit_c, base_shadow_c), dtype=np.float64
    )
    dt_s = max(0.0, float(slice_hours)) * 3600.0

    out: list[np.ndarray] = []
    for snapshot in shadow_ratio_series:
        shadow_c = coarsen_grid(np.asarray(snapshot, dtype=np.float64), coarsen)
        # Where this slice's illumination would take the surface if it were
        # held there indefinitely, and how far the surface actually gets in
        # one slice.
        target = np.asarray(shadowed_equilibrium_c(sunlit_c, shadow_c), dtype=np.float64)
        surface_state = np.asarray(
            relax_surface_c(surface_state, target, dt_s, tau_s), dtype=np.float64
        )
        out.append(surface_state)
    return np.stack(out, axis=0)


def build_cost_cube(
    base_grids: Mapping[str, Any],
    shadow_ratio_series: Sequence[np.ndarray],
    rover: Mapping[str, Any],
    weights: Mapping[str, float] | None = None,
    coarsen: int = 1,
    couple_thermal: bool = True,
    slice_hours: float = 1.0,
    tau_s: float = REGOLITH_THERMAL_TAU_S,
    risk_alpha: float | None = None,
    slope_sigma: np.ndarray | None = None,
    roughness: np.ndarray | None = None,
    roughness_scale: "RoughnessScale | None" = None,
    surface_series: np.ndarray | None = None,
    solar_gain_series: Sequence[float] | np.ndarray | None = None,
    heater_w_series: np.ndarray | None = None,
) -> np.ndarray:
    """(T, H', W') cost cube, one slice per shadow-ratio snapshot.

    Surface series (C6)
    -------------------
    *surface_series* is the ``(T, H', W')`` per-slice surface temperature
    :func:`surface_temperature_series` produces for these very arguments.
    Given, it is used as is (the thermal dwell model reads the same array,
    so the cube and the dwell see one surface); omitted, it is computed
    here. Either way the slices are identical bit for bit.

    Panel gain (C1)
    ---------------
    *solar_gain_series* is the per-slice cos i gain (:mod:`app.panel`), one
    scalar per snapshot, which the energy criterion multiplies into the
    cell's solar income. ``None`` is the pre-C1 cube, bit for bit.

    Heater power (C2)
    -----------------
    *heater_w_series* is the ``(T, H', W')`` survival-heater power the caller
    derived from ``surface_series`` (:func:`app.battery.heater_power_w_grid`),
    already coarsened. Given, the energy criterion prices each cell's heater
    from its own TEMPERATURE instead of its exposure; ``None`` is the pre-C2
    cube, bit for bit. Only this 4-D path ever has one: the 2-D
    ``compute_cost_grid`` has no epoch and so no per-slice surface, which is
    why ``COST_MODEL_ID`` does not move for C2 and the checked-in cost-grid
    digests are untouched.

    Roughness (C4)
    --------------
    *roughness* is the FINE measured LDRM roughness grid (metres) and
    *roughness_scale* its [0, 1] mapping; given together, the fifth
    criterion enters every slice. Roughness does not vary with time, and it
    is coarsened with ``how="max"`` like the slope: a block is priced at its
    roughest 50 m pixel, the conservative pairing. One without the other is
    refused; neither is the four-criterion cube as before.

    Risk appetite (B2)
    ------------------
    *risk_alpha* makes the slope and energy layers read their CVaR tails;
    *slope_sigma* is the FINE per-cell slope spread (B3), coarsened with
    ``how="max"`` like the slope itself -- the block's worst slope paired
    with its widest spread, a conservative pairing. ``None`` is the nominal
    cube, bit for bit.

    Thermal dynamics
    ----------------
    With *couple_thermal* the surface temperature is INTEGRATED across the
    slices: each slice has an equilibrium target set by its own illumination,
    and the surface relaxes toward it with the regolith time constant
    ``tau_s`` over ``slice_hours``. Pass False to hold ``base_grids["thermal"]``
    fixed for every slice.

    Two round-4 findings meet here.

    * **H-1.** The previous form applied ``couple_shadow_to_thermal`` to
      ``base_grids["thermal"]`` -- a field the loader has ALREADY coupled
      (``metadata["thermal_shadow_coupled"]``). Applying the Stefan-Boltzmann
      blend twice does not halve its effect, it compounds it: measured on the
      production grid the 4-D planner's map ran 37 C colder than the 2-D
      planner's for the same terrain at the same instant, 3 494 cells were
      impassable to one planner and passable to the other, and mean cell cost
      was 20 percent high. The stored field is now taken back to the sunlit
      peak first (``sunlit_peak_from_annual_peak_c``) and the correction
      applied exactly once, per slice.

    * **H-3.** There were no dynamics at all, so a cell crossing into shadow
      was scored at the permanently-shadowed floor within the same slice --
      below the traversability gate, hence impassable, however briefly the
      shadow lasted. Three quarters of this grid sits above shadow_ratio 0.5.
      The first-order lag is what makes a passing shadow cost something
      finite and a genuine cold trap cost everything.
    """
    if len(shadow_ratio_series) == 0:
        raise ValueError("shadow_ratio_series must contain at least one snapshot")

    slope = np.asarray(base_grids["slope"], dtype=np.float64)
    traversable = np.asarray(base_grids["traversable"], dtype=bool)
    metadata = base_grids["metadata"]
    resolution_m = float(metadata["resolution_m"])

    for index, snapshot in enumerate(shadow_ratio_series):
        if np.asarray(snapshot).shape != slope.shape:
            raise ValueError(
                f"shadow snapshot {index} has shape {np.asarray(snapshot).shape}, "
                f"expected {slope.shape}"
            )

    slope_c = coarsen_grid(slope, coarsen, how="max")       # worst case per block
    traversable_c = coarsen_traversable(traversable, coarsen)
    resolution_c = resolution_m * max(1, int(coarsen))
    sigma_c = None
    if slope_sigma is not None:
        sigma_fine = np.asarray(slope_sigma, dtype=np.float64)
        if sigma_fine.shape != slope.shape:
            raise ValueError(
                f"slope_sigma {sigma_fine.shape} must match the slope grid {slope.shape}"
            )
        with np.errstate(all="ignore"):
            sigma_c = coarsen_grid(sigma_fine, coarsen, how="max")
    roughness_c = None
    if roughness is not None or roughness_scale is not None:
        if roughness is None or roughness_scale is None:
            raise ValueError(
                "roughness and roughness_scale must be given together (C4): a roughness "
                "grid cannot be priced without its scale, and a scale prices nothing without the grid"
            )
        roughness_fine = np.asarray(roughness, dtype=np.float64)
        if roughness_fine.shape != slope.shape:
            raise ValueError(
                f"roughness {roughness_fine.shape} must match the slope grid {slope.shape}"
            )
        with np.errstate(all="ignore"):
            roughness_c = coarsen_grid(roughness_fine, coarsen, how="max")

    # The per-slice surface temperature: the same array the thermal dwell
    # model (C6) integrates, computed once when the caller did not. (The
    # sunlit-peak selection and the long-run-equilibrium prior live in
    # surface_temperature_series.)
    if surface_series is None:
        surface = surface_temperature_series(
            base_grids,
            shadow_ratio_series,
            coarsen=coarsen,
            slice_hours=slice_hours,
            tau_s=tau_s,
            couple_thermal=couple_thermal,
        )
    else:
        surface = np.asarray(surface_series, dtype=np.float64)
        expected = (len(shadow_ratio_series),) + slope_c.shape
        if surface.shape != expected:
            raise ValueError(
                f"surface_series {surface.shape} must be {expected}: one coarse "
                "surface temperature grid per shadow snapshot"
            )
    cost_map = default_cost_map(
        rover, weights, risk_alpha=risk_alpha, roughness_scale=roughness_scale
    )

    # Every layer is evaluated per slice. The optimisation this replaces --
    # evaluating "invariant" layers once -- rested on the assumption that
    # only the shadow layer varies with time. That stopped being true when
    # thermal became a function of illumination (round 3, H-3): a cell that
    # is dark at slice t is genuinely COLDER at slice t, and freezing the
    # thermal layer at one value hid exactly the physics the 4-D planner
    # exists to reason about. The layers are true NumPy now (review #8
    # removed np.vectorize), so per-slice evaluation costs a handful of
    # array ops per slice rather than the ~22 s that made the optimisation
    # necessary in the first place.
    heaters = None
    if heater_w_series is not None:
        heaters = np.asarray(heater_w_series, dtype=np.float64)
        expected_heat = (len(shadow_ratio_series),) + slope_c.shape
        if heaters.shape != expected_heat:
            raise ValueError(
                f"heater_w_series {heaters.shape} must be {expected_heat}: one coarse "
                "heater-power grid per shadow snapshot"
            )

    gains = None
    if solar_gain_series is not None:
        gains = np.asarray(solar_gain_series, dtype=np.float64).reshape(-1)
        if gains.size != len(shadow_ratio_series):
            raise ValueError(
                f"solar_gain_series has {gains.size} entries for "
                f"{len(shadow_ratio_series)} shadow snapshots"
            )

    slices: list[np.ndarray] = []
    for index, snapshot in enumerate(shadow_ratio_series):
        shadow_c = coarsen_grid(np.asarray(snapshot, dtype=np.float64), coarsen)
        thermal_slice = surface[index]

        # The per-slice temperature is a COST, never a veto. Round 4 also
        # ANDed ``thermal_slice >= THERMAL_MIN_TRAVERSABLE_C`` into this
        # slice's traversable mask so that a WAIT edge had something to buy.
        # Measured on the production grid at a lunar-night epoch
        # (2026-09-07): every statically passable cell fell below the gate
        # within 2.5 h -- the fully shadowed equilibrium is the 90 K PSR
        # floor, 33 C under the gate, and the skin relaxes there with a 1 h
        # time constant -- so the whole map was impassable for the whole
        # night and /api/plan-4d refused every pair with "no finite cost",
        # while the catalogue gives LPR-1 50 h of darkness. The skin
        # temperature of the ground is not what limits the rover; its own
        # battery and shadow endurance are, and those now live in the
        # planner's state (pathfinder_4d). The static cold-trap gate stays
        # where it always was, in the base traversable mask.
        context = PlanContext(
            slope=slope_c,
            thermal=thermal_slice,
            shadow_ratio=shadow_c,
            traversable=traversable_c,
            resolution_m=resolution_c,
            rover=rover,
            slope_sigma=sigma_c,
            roughness=roughness_c,
            roughness_scale=roughness_scale,
            solar_gain=1.0 if gains is None else float(gains[index]),
            heater_w=None if heaters is None else heaters[index],
        )
        slices.append(cost_map.total(context))

    return np.stack(slices, axis=0)


from .cost_engine import (
    edge_travel_time_s,
    f_shadow_cell,
    housekeeping_power_w,
    resolve_weights,
)


def wait_cost(
    illum_frac: float,
    dt_hours: float,
    rover: Mapping[str, Any],
    weights: Mapping[str, float],
    solar_gain: float = 1.0,
    heater_w: float | None = None,
) -> float:
    """Cost of holding position for one time slice.

    Waiting in sunlight recharges the battery and costs nothing on the
    energy axis; waiting in shadow drains state of charge and accumulates
    shadow exposure. Modelling this is what turns "go faster" into
    "stop, let the Sun come, then cross".

    Time is in the total, not just the penalties. A MOVE edge costs
    ``travel_hours * (1 + weighted cell cost)``; a WAIT used to cost only
    the weighted penalties, so a slice spent in full sunlight came out at
    exactly 0.0 -- waiting was free, the planner had no reason to prefer
    arriving sooner, and ties between "go now" and "wait indefinitely, then
    go" were broken by heap insertion order rather than by the objective.
    Both edge families now cost hours scaled the same way. The heuristic
    stays admissible: a WAIT costs at least ``dt`` and closes no distance,
    so a distance-based lower bound is still a lower bound.
    (Round 3 review, M-2.)

    Housekeeping power comes from ``cost_engine.housekeeping_power_w``, so
    the heater load here matches the one the energy penalty and the
    simulator use. It previously charged full heater power even in full
    sunlight. (Round 3 review, M-9.)

    *solar_gain* is C1's panel gain for THIS slice. The illuminated fraction
    says whether the Sun is visible from the cell; the gain says how much of
    that light the array actually faces. 1.0 is the pre-C1 model and is
    bit-for-bit the identity. (C1.)

    *heater_w* is C2's temperature-derived heater power for THIS cell at THIS
    slice. The illuminated fraction says how much light the cell gets; the
    heater power says how cold it actually is, and on Site11 those two layers
    are independent (measured Spearman -0.0014). ``None`` is the pre-C2 model
    and is the identity. (C2.)
    """
    frac = min(1.0, max(0.0, float(illum_frac)))
    dt = max(0.0, float(dt_hours))

    solar_in_w = float(rover["p_solar_w"]) * frac * float(solar_gain)
    net_w = solar_in_w - housekeeping_power_w(1.0 - frac, rover, heater_w)

    # Rate form, so the dt factor is applied once, at the end.
    soc_drain_per_hour = max(0.0, -net_w / float(rover["e_cap_wh"]))
    shadow_penalty = f_shadow_cell(1.0 - frac)

    return float(
        dt
        * (
            1.0
            + weights["w_energy"] * soc_drain_per_hour
            + weights["w_shadow"] * shadow_penalty
        )
    )


def hibernate_cost(
    illum_frac: float,
    dt_hours: float,
    rover: Mapping[str, Any],
    weights: Mapping[str, float],
    solar_gain: float = 1.0,
) -> float:
    """Cost of lying dormant for *dt_hours* instead of holding station (C2).

    The same shape as :func:`wait_cost` -- hours scaled by the same two
    weighted penalties -- with the catalogue's ``p_hibernate_w`` in place of
    the shadow housekeeping draw. Sharing the shape is the point: a HIBERNATE
    edge and a WAIT edge have to be comparable on one objective, and the only
    difference between them is the power the vehicle draws while it stands
    still.

    That difference is not always a saving. Measured on this catalogue,
    ``p_hibernate_w / p_shadow_w`` is 1.662 for LPR-1 (its dormant draw is
    LARGER than running its heaters -- the reference document defines the mode
    as 'idle + heater + thermal management'), 0.769 for NASA VIPER and 0.083
    for Yutu-2. So hibernation is genuinely cheaper for two of the four
    profiles and genuinely dearer for one, and the planner is left to work out
    which on the objective rather than being told.

    Never negative and never below ``dt``, exactly as ``wait_cost`` is not:
    the SOC term is floored at zero and the shadow penalty is non-negative.
    That is what keeps the A* heuristic admissible AND consistent across a
    zero-distance edge -- a dormant hour must never be a reward, or a rover
    could lower its cost by sleeping in the sunshine.
    """
    frac = min(1.0, max(0.0, float(illum_frac)))
    dt = max(0.0, float(dt_hours))
    hibernate_w = rover.get("p_hibernate_w")
    if hibernate_w is None:
        raise ValueError(
            "rover declares no p_hibernate_w: hibernation is undefined for this "
            "profile and no draw is invented for it"
        )

    solar_in_w = float(rover["p_solar_w"]) * frac * float(solar_gain)
    net_w = solar_in_w - float(hibernate_w)

    soc_drain_per_hour = max(0.0, -net_w / float(rover["e_cap_wh"]))
    shadow_penalty = f_shadow_cell(1.0 - frac)

    return float(
        dt
        * (
            1.0
            + weights["w_energy"] * soc_drain_per_hour
            + weights["w_shadow"] * shadow_penalty
        )
    )


def build_wait_cost_cube(
    illum_frac_series: Sequence[np.ndarray],
    rover: Mapping[str, Any],
    dt_hours: float,
    weights: Mapping[str, float] | None = None,
    coarsen: int = 1,
    solar_gain_series: Sequence[float] | np.ndarray | None = None,
    heater_w_series: np.ndarray | None = None,
) -> np.ndarray:
    """(T, H', W') cost of waiting one slice in each cell at each time.

    *solar_gain_series* is C1's per-slice panel gain, one scalar per
    snapshot. Omitted, the pre-C1 whole-cube value table is used and the
    result is bit-identical to before. Given, the value table has to be
    built PER SLICE: with a slice-dependent gain the same illuminated
    fraction buys different amounts of charge at different times, and one
    table across the whole cube would collapse exactly that distinction.

    *heater_w_series* is C2's ``(T, H', W')`` heater power, already coarsened.
    It varies per CELL as well as per slice, so with it the de-duplication key
    becomes the PAIR (illuminated fraction, heater power) rather than the
    fraction alone -- two cells equally lit but at different temperatures must
    not share a value. Omitted, the pre-C2 path runs unchanged.
    """
    if len(illum_frac_series) == 0:
        raise ValueError("illum_frac_series must contain at least one snapshot")

    resolved = resolve_weights(weights, rover)

    # wait_cost is a pure scalar function of the illumination fraction, and
    # illumination grids are highly repetitive (whole regions share a value,
    # and the endpoint currently repeats one snapshot across every slice).
    # Evaluating it per cell per slice cost ~5 s for a 168-slice cube; solving
    # it once per DISTINCT value and gathering makes the cube size irrelevant.
    # (Faz 3 review, M3.)
    coarse = [
        coarsen_grid(np.asarray(frac, dtype=np.float64), coarsen)
        for frac in illum_frac_series
    ]
    stacked = np.stack(coarse, axis=0)

    heaters = None
    if heater_w_series is not None:
        heaters = np.asarray(heater_w_series, dtype=np.float64)
        if heaters.shape != stacked.shape:
            raise ValueError(
                f"heater_w_series {heaters.shape} must be {stacked.shape}: one coarse "
                "heater-power grid per illumination snapshot"
            )

    if solar_gain_series is None and heaters is None:
        unique, inverse = np.unique(stacked, return_inverse=True)
        table = np.array(
            [wait_cost(value, dt_hours, rover, resolved) for value in unique],
            dtype=np.float64,
        )
        return table[inverse].reshape(stacked.shape)

    if solar_gain_series is None:
        gains = np.ones(stacked.shape[0], dtype=np.float64)
    else:
        gains = np.asarray(solar_gain_series, dtype=np.float64).reshape(-1)
        if gains.size != stacked.shape[0]:
            raise ValueError(
                f"solar_gain_series has {gains.size} entries for "
                f"{stacked.shape[0]} illumination snapshots"
            )
    out = np.empty(stacked.shape, dtype=np.float64)
    for index in range(stacked.shape[0]):
        slice_frac = stacked[index]
        if heaters is None:
            unique, inverse = np.unique(slice_frac, return_inverse=True)
            table = np.array(
                [
                    wait_cost(value, dt_hours, rover, resolved, solar_gain=float(gains[index]))
                    for value in unique
                ],
                dtype=np.float64,
            )
        else:
            pairs = np.stack([slice_frac.ravel(), heaters[index].ravel()], axis=1)
            unique, inverse = np.unique(pairs, axis=0, return_inverse=True)
            inverse = np.asarray(inverse).reshape(-1)
            table = np.array(
                [
                    wait_cost(
                        float(value), dt_hours, rover, resolved,
                        solar_gain=float(gains[index]), heater_w=float(heat),
                    )
                    for value, heat in unique
                ],
                dtype=np.float64,
            )
        out[index] = table[inverse].reshape(slice_frac.shape)
    return out


def auto_slice_hours(
    slope: np.ndarray,
    traversable: np.ndarray,
    resolution_m: float,
    rover: Mapping[str, Any],
    percentile: float = 50.0,
) -> float:
    """Time-slice length matched to how long crossing one cell actually takes.

    The 4-D planner advances time in whole slices
    (``d_slices = ceil(travel_time / slice_hours)``), so a slice much longer
    than an edge traversal collapses every move to exactly one slice: the
    time axis then counts STEPS rather than hours and the slope-dependent
    travel time -- the whole reason ``edge_travel_time_s`` is consulted --
    becomes invisible. On the production grid a 1 h slice did exactly that
    at every resolution from 5 m to 320 m. (Faz 3 review, C1.)

    Sizing a slice at the typical edge traversal keeps ``arrival_slice`` a
    real clock and lets a steep edge cost more slices than a flat one.
    Impassable cells are excluded: they routinely carry near-vertical
    slopes that the rover will never drive and whose traversal time is
    infinite.

    Feed this the FINE slope grid with the COARSE cell length. Callers used
    to pass a ``how="max"`` coarsened grid, so the "median" was a median of
    block maxima -- biased high, and biased by the coarsen factor, which has
    nothing to do with how long a crossing takes. (Round 4 review, L-7.)
    """
    slope_arr = np.asarray(slope, dtype=np.float64)
    passable = np.asarray(traversable, dtype=bool)

    candidates = slope_arr[passable & np.isfinite(slope_arr)]
    if candidates.size == 0:
        # Nothing drivable: fall back to a flat edge so the caller still gets
        # a positive, finite slice length instead of a degenerate clock.
        reference_slope = 0.0
    else:
        reference_slope = float(np.percentile(candidates, percentile))

    travel_s = edge_travel_time_s(reference_slope, float(resolution_m), rover)
    if not math.isfinite(travel_s) or travel_s <= 0.0:
        travel_s = edge_travel_time_s(0.0, float(resolution_m), rover)

    return float(travel_s / 3600.0)
