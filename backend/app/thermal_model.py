"""Surface thermal model adapters.

LunaPath consumes surface temperature as a (H, W) float32 grid in degrees
Celsius. Where that grid comes from is a swappable decision:

- ``SyntheticModel``  -- the original elevation/aspect heuristic (validity SYNTHETIC)
- ``Heat1DModel``     -- Hayne's 1-D regolith diffusion model  (validity MODEL)

Keeping both behind one protocol means an unavailable or API-drifted heat1d
release degrades to the synthetic baseline instead of blocking the pipeline.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

from .thermal_grid import generate_thermal_grid


@runtime_checkable
class SurfaceThermalModel(Protocol):
    """Produces surface temperature in degrees Celsius."""

    name: str
    validity: str  # "MEASURED" | "DERIVED" | "MODEL" | "SYNTHETIC"

    def surface_temperature_c(
        self,
        slope_deg: np.ndarray,
        aspect_deg: np.ndarray,
        lat_deg: float,
    ) -> np.ndarray: ...


class SyntheticModel:
    """Legacy elevation + aspect heuristic. Kept as an explicit baseline."""

    name = "synthetic-elevation-aspect"
    validity = "SYNTHETIC"

    def __init__(
        self,
        elevation: np.ndarray,
        resolution_m: float,
        sun_azimuth_grid_deg: float = 0.0,
    ) -> None:
        self._elevation = np.asarray(elevation, dtype=np.float64)
        self._resolution_m = float(resolution_m)
        # Which grid azimuth the Sun sits in. Defaults to grid north, which
        # is what this heuristic always silently assumed; a caller that
        # knows the CRS passes the real sunward bearing instead.
        # (Round 3 review, L-4.)
        self._sun_azimuth_grid_deg = float(sun_azimuth_grid_deg)

    def surface_temperature_c(
        self,
        slope_deg: np.ndarray,
        aspect_deg: np.ndarray,
        lat_deg: float,
    ) -> np.ndarray:
        # lat_deg is unused: the synthetic heuristic has no latitude term.
        return generate_thermal_grid(
            self._elevation,
            np.asarray(slope_deg, dtype=np.float64),
            np.asarray(aspect_deg, dtype=np.float64),
            self._resolution_m,
            sun_azimuth_grid_deg=self._sun_azimuth_grid_deg,
        )


def build_thermal_grid(
    model: SurfaceThermalModel,
    slope_grid: np.ndarray,
    aspect_grid: np.ndarray,
    lat_deg: float,
) -> np.ndarray:
    """Run *model* and normalise its output to (H, W) float32 Celsius."""
    out = model.surface_temperature_c(slope_grid, aspect_grid, lat_deg)
    out = np.asarray(out, dtype=np.float32)
    if out.shape != np.asarray(slope_grid).shape:
        raise ValueError(
            f"{model.name} returned shape {out.shape}, "
            f"expected {np.asarray(slope_grid).shape}"
        )
    return out


# ── Shadow coupling ─────────────────────────────────────────────────────────

# Annual MAXIMUM temperature of a large south-polar permanently shadowed
# region. Diviner's cold-trap survey defines a cold trap by an annual
# maximum below 110 K and reports 80-110 K across the large south-polar
# PSRs (Paige et al. 2010, "Diviner Lunar Radiometer Observations of Cold
# Traps in the Moon's South Polar Region"). 90 K sits in the middle of that
# published band. It is an annual maximum on purpose: the grids this
# corrects hold annual peak temperature, so the floor has to be the same
# statistic, not a PSR's minimum.
PSR_ANNUAL_MAX_K: float = 90.0

_ABSOLUTE_ZERO_C: float = -273.15


# How fast the top skin of lunar regolith follows a change in illumination.
# ORDER OF MAGNITUDE ONLY, and labelled as such: Diviner observations of
# lunar eclipses show surface temperatures falling by of order 100 K within
# the ~1 h of totality, so the skin responds on a timescale of roughly an
# hour rather than instantly or over a lunar day. It is deliberately NOT
# the rover's ``thermal_tau_s`` -- that is the vehicle's internal envelope
# constant, a different body with a different mass.
#
# What this constant buys: before it, a cell that entered shadow was scored
# at the permanently-shadowed floor in the SAME time slice, so any cell dark
# at instant t was impassable at instant t however briefly the shadow
# lasted. On the production grid that is three quarters of the map.
# (Round 4 review, H-3.)
REGOLITH_THERMAL_TAU_S: float = 3600.0
REGOLITH_LAG_VALIDITY: str = "UNCALIBRATED"

# Smallest illumination fraction that still counts as a real lit episode.
# The production sun track carries 168 samples, so one sample is 1/168 and
# nothing below that is resolvable: a fraction under this is
# indistinguishable from never being lit at all.
DEFAULT_LIT_EPSILON: float = 1.0 / 168.0


def _as_pair(surface_c, shadow_ratio):
    surface = np.asarray(surface_c, dtype=np.float64)
    ratio = np.clip(np.asarray(shadow_ratio, dtype=np.float64), 0.0, 1.0)
    if surface.shape != ratio.shape:
        raise ValueError(
            f"shape mismatch: surface {surface.shape} vs shadow {ratio.shape}"
        )
    return surface, ratio


def _blend_k4(hot_k, cold_k, weight):
    """Fourth-power (Stefan-Boltzmann) blend of two temperatures in kelvin."""
    with np.errstate(invalid="ignore"):
        return (weight * hot_k**4 + (1.0 - weight) * cold_k**4) ** 0.25


def shadowed_equilibrium_c(
    surface_c: np.ndarray,
    shadow_ratio: np.ndarray,
    psr_annual_max_k: float = PSR_ANNUAL_MAX_K,
) -> np.ndarray:
    """The COLD end: radiative equilibrium under time-averaged insolation.

    A surface in radiative balance emits as T^4, so a patch lit a fraction
    ``f`` of the time and radiating to the cold-trap floor otherwise settles
    at the fourth-power mean

        T_eq = ( f * T_sunlit^4  +  (1 - f) * T_psr^4 ) ^ (1/4)

    This is a genuine and useful quantity -- it is the temperature the rover
    has to survive, and it is what the traversability gate should test. What
    it is NOT is a peak: see :func:`annual_peak_c`. Round 3 computed this
    blend and stored it under the peak field's name, which is the statistic
    error round 4 (H-3) separates out.
    """
    surface, ratio = _as_pair(surface_c, shadow_ratio)
    floor_k = max(0.0, float(psr_annual_max_k))
    sunlit_k = np.maximum(surface - _ABSOLUTE_ZERO_C, 0.0)
    result = _blend_k4(sunlit_k, floor_k, 1.0 - ratio) + _ABSOLUTE_ZERO_C
    # A NaN on either input stays NaN: traversability treats it as blocked,
    # which is the honest answer for a cell with no thermal or no shadow data.
    return np.where(np.isnan(surface) | np.isnan(ratio), np.nan, result).astype(
        np.float32
    )


def annual_peak_c(
    surface_c: np.ndarray,
    shadow_ratio: np.ndarray,
    psr_annual_max_k: float = PSR_ANNUAL_MAX_K,
    lit_epsilon: float = DEFAULT_LIT_EPSILON,
) -> np.ndarray:
    """The HOT end: the highest temperature the cell actually reaches.

    ``Heat1DModel`` stores ``np.nanmax`` over roughly a lunar year, so its
    output is an annual PEAK. ``shadow_ratio`` is a TIME FRACTION. Round 3
    combined them with the fourth-power time-mean above, which reports a
    cell lit a quarter of the time at -78.3 C when its peak is 0 C -- but
    such a cell still REACHES ~0 C every time the Sun clears its horizon,
    and with a skin response of order an hour
    (:data:`REGOLITH_THERMAL_TAU_S`) a lit episode of several hours gets
    there comfortably. Applying a time-average to a maximum is a statistic
    error, and it was worth up to 115 K. (Round 4 review, H-3.)

    A maximum is therefore essentially the sunlit peak wherever the cell is
    lit at all, and the PSR floor only where it never is. The transition is
    taken across ``[0, lit_epsilon]`` rather than as a hard step at exactly
    zero, because below one sun-track sample the illumination fraction
    cannot distinguish "never lit" from "lit briefly" -- and a step on a
    quantised input is a cliff in the wrong place. Interpolating in T^4
    keeps both ends exact: 0 gives the floor, ``lit_epsilon`` and above give
    the model's own peak.

    Round 3's real finding survives intact: a permanently shadowed cell
    still reads the PSR floor instead of +42.6 C, which is what makes the
    ``THERMAL_MIN_TRAVERSABLE_C`` gate bite on cold traps.
    """
    surface, ratio = _as_pair(surface_c, shadow_ratio)
    floor_k = max(0.0, float(psr_annual_max_k))
    sunlit_k = np.maximum(surface - _ABSOLUTE_ZERO_C, 0.0)

    eps = max(1e-12, float(lit_epsilon))
    weight = np.clip((1.0 - ratio) / eps, 0.0, 1.0)
    result = _blend_k4(sunlit_k, floor_k, weight) + _ABSOLUTE_ZERO_C
    return np.where(np.isnan(surface) | np.isnan(ratio), np.nan, result).astype(
        np.float32
    )


def couple_shadow_to_thermal(
    surface_c: np.ndarray,
    shadow_ratio: np.ndarray,
    psr_annual_max_k: float = PSR_ANNUAL_MAX_K,
    statistic: str = "peak",
    lit_epsilon: float = DEFAULT_LIT_EPSILON,
) -> np.ndarray:
    """Correct a sunlit-peak temperature field for illumination.

    *statistic* names which end of the cell's temperature range is wanted:

    ``"peak"``
        the annual maximum -- :func:`annual_peak_c`. This is the statistic
        ``Heat1DModel`` produces, so it is the default and the only one that
        may be stored back under the same field name.
    ``"equilibrium"``
        the time-averaged radiative equilibrium, i.e. the cold end --
        :func:`shadowed_equilibrium_c`.

    Why this exists at all
    ----------------------
    ``Heat1DModel`` evaluates a (slope x aspect) lookup table at a fixed
    latitude, so its output is a function of local geometry ALONE. It never
    sees ``shadow_ratio``, the one layer computed from real ray-cast horizon
    geometry and SPICE ephemeris. Measured before any coupling: 165 distinct
    temperatures across 250 000 cells, ``corr(thermal, shadow_ratio) =
    +0.027``, and 1 076 permanently shadowed cells carrying temperatures up
    to +42.6 C -- cells that never see the Sun, reported as comfortably
    warm, with the -150 C traversability gate blocking 150 cells in 250 000.

    Provenance
    ----------
    The result mixes a MODEL grid with a DERIVED one, so callers must label
    it with ``traversability.weakest_validity(thermal, shadow_ratio)``
    rather than keeping the thermal layer's own validity.
    """
    if statistic == "peak":
        return annual_peak_c(surface_c, shadow_ratio, psr_annual_max_k, lit_epsilon)
    if statistic == "equilibrium":
        return shadowed_equilibrium_c(surface_c, shadow_ratio, psr_annual_max_k)
    raise ValueError(
        f"unknown statistic {statistic!r}; expected 'peak' or 'equilibrium'"
    )


def sunlit_peak_from_annual_peak_c(
    annual_peak: np.ndarray,
    shadow_ratio: np.ndarray,
    psr_annual_max_k: float = PSR_ANNUAL_MAX_K,
    lit_epsilon: float = DEFAULT_LIT_EPSILON,
) -> np.ndarray:
    """Left inverse of :func:`annual_peak_c`: recover the uncorrected field.

    A grid on disk is stored ALREADY corrected (``thermal_shadow_coupled``),
    so anything that wants to re-apply the correction under a different
    illumination -- the 4-D cost cube, one slice at a time -- has to undo
    the static correction first. Applying it twice is not a smaller error
    than applying it once: it compounds, and measured on the production grid
    it left the 4-D planner's map 37 C colder than the 2-D planner's for the
    same terrain at the same instant, with 3 494 cells impassable to one
    planner and passable to the other. (Round 4 review, H-1.)

    Exact wherever the cell is lit at all. Where the cell is never lit the
    forward map has erased the sunlit value entirely and no inverse exists;
    the floor is returned, which is correct in the only sense that matters
    -- such a cell is dark in every slice, so its sunlit peak is never used.
    """
    peak, ratio = _as_pair(annual_peak, shadow_ratio)
    floor_k = max(0.0, float(psr_annual_max_k))
    eps = max(1e-12, float(lit_epsilon))
    weight = np.clip((1.0 - ratio) / eps, 0.0, 1.0)

    peak_k = np.maximum(peak - _ABSOLUTE_ZERO_C, 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        sunlit_k4 = (peak_k**4 - (1.0 - weight) * floor_k**4) / np.where(
            weight > 0.0, weight, 1.0
        )
        sunlit_k = np.maximum(sunlit_k4, 0.0) ** 0.25
    recovered = np.where(
        weight > 0.0, sunlit_k + _ABSOLUTE_ZERO_C, floor_k + _ABSOLUTE_ZERO_C
    )
    return np.where(np.isnan(peak) | np.isnan(ratio), np.nan, recovered).astype(
        np.float32
    )


def sunlit_peak_from_equilibrium_c(
    equilibrium_c: np.ndarray,
    shadow_ratio: np.ndarray,
    psr_annual_max_k: float = PSR_ANNUAL_MAX_K,
) -> np.ndarray:
    """Left inverse of :func:`shadowed_equilibrium_c`.

    Needed only to read artefacts written before round 4, which stored the
    equilibrium blend under the peak field's name. Anything written since
    stores the UNCORRECTED sunlit peak and is marked
    ``metadata["thermal_field"] == "sunlit_peak"``, so no inversion is
    involved and the correction cannot be applied twice by construction.
    (Round 4 review, H-1.)
    """
    equilibrium, ratio = _as_pair(equilibrium_c, shadow_ratio)
    floor_k = max(0.0, float(psr_annual_max_k))
    illum = 1.0 - ratio
    eq_k = np.maximum(equilibrium - _ABSOLUTE_ZERO_C, 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        sunlit_k4 = (eq_k**4 - ratio * floor_k**4) / np.where(illum > 0.0, illum, 1.0)
        sunlit_k = np.maximum(sunlit_k4, 0.0) ** 0.25
    recovered = np.where(
        illum > 0.0, sunlit_k + _ABSOLUTE_ZERO_C, floor_k + _ABSOLUTE_ZERO_C
    )
    return np.where(np.isnan(equilibrium) | np.isnan(ratio), np.nan, recovered).astype(
        np.float32
    )


def relax_surface_c(
    current_c: np.ndarray,
    target_c: np.ndarray,
    dt_s: float,
    tau_s: float = REGOLITH_THERMAL_TAU_S,
) -> np.ndarray:
    """Advance a surface temperature one step toward *target_c*.

    First-order lag, ``T <- T_target + (T - T_target) * exp(-dt / tau)``.
    Standard, cheap, and the smallest honest correction to the previous
    behaviour, which had no dynamics at all: a cell crossing into shadow was
    scored at the permanently-shadowed floor within the same time slice,
    regardless of how long the shadow lasted, so a passing shadow made a
    cell impassable exactly as thoroughly as a cold trap does.

    ``tau_s`` is UNCALIBRATED (see :data:`REGOLITH_LAG_VALIDITY`). What the
    model claims is the DIRECTION and the ORDER of the timescale -- shadowed
    ground cools over tens of minutes to hours, not instantly and not over a
    lunar day. It does not claim the constant is the right size.
    """
    current = np.asarray(current_c, dtype=np.float64)
    target = np.asarray(target_c, dtype=np.float64)
    tau = float(tau_s)
    if tau <= 0.0:
        return np.asarray(target, dtype=np.float64)
    decay = float(np.exp(-max(0.0, float(dt_s)) / tau))
    return target + (current - target) * decay


_SLOPE_MAX_DEG_FOR_TABLE = 30.0


class Heat1DModel:
    """Hayne (2017) 1-D regolith diffusion model, evaluated on a
    (slope x aspect) lookup table and sampled per cell.

    Running heat1d once per grid cell is wasteful: at the lunar south pole
    latitude is effectively constant across our 40 km window, so surface
    temperature depends almost entirely on local slope and azimuth. A
    coarse table plus nearest-bin lookup captures that at a fraction of the
    cost and is deterministic.

    Real-API note (Faz 1 / Task 4)
    -------------------------------
    This class was planned against an assumed
    ``heat1d.Model(planet=..., lat=..., ndays=..., slope=..., slope_az=...)``
    signature. Two real-API surprises had to be resolved by inspecting the
    installed package directly (see task-4-report.md for the full trail):

    1. PyPI's ``heat1d`` (0.3.2 as of writing) has **no** slope/aspect
       support at all -- ``Model.__init__`` only takes
       ``(planet, lat, ndays, config)``. ``available()`` correctly reports
       ``False`` against that release.
    2. The GitHub ``main`` branch *does* add ``slope``/``slope_az`` (v0.4.1),
       but its installable package root moved to a ``python/`` subdirectory
       (``pip install`` needs ``...#subdirectory=python``), and:
       - its default ``planet=planets.Moon`` refers to heat1d's own bundled
         ``heat1d.planets`` submodule, not the separate top-level ``planets``
         PyPI package the brief's ``import planets`` line assumed (0.4.1 no
         longer depends on that package; the two ``Planet`` classes are only
         coincidentally similar, not a documented-compatible substitute), so
         we import ``heat1d.planets`` instead;
       - its much faster ``solver="fourier-matrix"`` is documented by heat1d
         itself to produce Gibbs-ringing artifacts *at the diurnal peak* for
         sloped surfaces -- exactly the value this table reports -- so it is
         unsafe for our purposes. We use ``solver="crank-nicolson"`` instead:
         unconditionally stable, second-order accurate, explicitly
         recommended by heat1d's own docs for sloped output, and it matched
         the package's default ``explicit`` solver's result to ~1 C in
         testing (measured per-cell timing for either solver was in the
         low single-digit seconds and did not show a consistent, reproducible
         advantage for one over the other -- see task-4-report.md).

    ``ndays`` (annual peak, not single-day) -- Task 4 review finding
    ------------------------------------------------------------------
    The table stores the *annual* peak surface temperature, not a single
    diurnal cycle's peak: ``ndays=13`` (~1 lunar year) is passed to
    ``heat1d.Model``, not ``ndays=1``. A single lunar day (~29.5 Earth days)
    starting from Model's internal phase reference does not sample the part
    of the year with the highest solar elevation at a given latitude --
    measured at this class's default latitude a single-day flat-cell peak
    landed ~81 C below the true annual peak (and the gap is itself
    slope-dependent: ~81 C at 0 deg slope vs ~22 C at 10 deg sun-facing
    slope, so a single day doesn't just offset the table, it distorts the
    slope contrast the cost engine reads). ``ndays=13`` costs roughly 2x a
    single day per cell (equilibration dominates the run, not the extra
    simulated days), so a full default-sized table (13x16 = 208 cells) is a
    one-time ~12-15 minute build per distinct latitude -- acceptable given
    it is cached per ``Heat1DModel`` instance (``self._cache``, keyed by
    latitude) and this table is a slow one-off construction, not something
    on any request's hot path.
    """

    validity = "MODEL"

    def __init__(self, n_slope_bins: int = 13, n_aspect_bins: int = 16) -> None:
        self.n_slope_bins = int(n_slope_bins)
        self.n_aspect_bins = int(n_aspect_bins)
        self.name = f"heat1d-lut-{self.n_slope_bins}x{self.n_aspect_bins}"
        self._cache: dict[float, np.ndarray] = {}

    @staticmethod
    def available() -> bool:
        """True when heat1d is importable with a slope-capable Model.

        Checks both APIs ``_lookup_table`` actually calls: ``Model`` (for
        ``slope``/``slope_az``) and ``Configurator`` (for ``solver``, used
        to select crank-nicolson). A build with slope support but a
        differently-shaped ``Configurator`` would otherwise report
        available() == True and then raise TypeError at grid-build time,
        defeating the synthetic fallback this check exists to guarantee.
        """
        try:
            import inspect

            import heat1d
        except Exception:
            return False
        try:
            model_params = inspect.signature(heat1d.Model.__init__).parameters
            config_params = inspect.signature(heat1d.Configurator).parameters
        except (TypeError, ValueError):
            return False
        return "slope" in model_params and "solver" in config_params

    def _lookup_table(self, lat_deg: float) -> np.ndarray:
        """(n_slope_bins, n_aspect_bins) peak surface temperature in Celsius."""
        key = round(float(lat_deg), 4)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        import heat1d
        from heat1d import planets as heat1d_planets

        slopes = np.linspace(0.0, _SLOPE_MAX_DEG_FOR_TABLE, self.n_slope_bins)
        aspects = np.linspace(0.0, 360.0, self.n_aspect_bins, endpoint=False)
        table = np.empty((self.n_slope_bins, self.n_aspect_bins), dtype=np.float64)

        for i, slope_deg in enumerate(slopes):
            for j, aspect_deg in enumerate(aspects):
                # crank-nicolson: unconditionally stable, 2nd-order accurate,
                # and free of the fourier-matrix solver's terminator-ringing
                # artifact on sloped surfaces (see class docstring).
                config = heat1d.Configurator(solver="crank-nicolson")
                model = heat1d.Model(
                    planet=heat1d_planets.Moon,
                    lat=np.deg2rad(lat_deg),
                    ndays=13,  # ~1 lunar year: see class docstring "ndays" note
                    slope=np.deg2rad(slope_deg),
                    slope_az=np.deg2rad(aspect_deg),
                    config=config,
                )
                model.run()
                surface_k = np.asarray(model.T)[:, 0]
                # Peak *annual* surface temperature is the planning-relevant
                # value: it bounds the warmest state the rover must survive.
                # A single lunar day does not sample the highest-elevation
                # part of the year at a given latitude (see docstring).
                table[i, j] = float(np.nanmax(surface_k)) - 273.15

        table = np.clip(table, -250.0, 130.0)
        self._cache[key] = table
        return table

    def surface_temperature_c(
        self,
        slope_deg: np.ndarray,
        aspect_deg: np.ndarray,
        lat_deg: float,
    ) -> np.ndarray:
        table = self._lookup_table(lat_deg)
        slope_arr = np.asarray(slope_deg, dtype=np.float64)
        aspect_arr = np.asarray(aspect_deg, dtype=np.float64)

        slope_clipped = np.clip(
            np.nan_to_num(slope_arr, nan=0.0), 0.0, _SLOPE_MAX_DEG_FOR_TABLE
        )
        si = np.rint(
            slope_clipped / _SLOPE_MAX_DEG_FOR_TABLE * (self.n_slope_bins - 1)
        ).astype(np.int64)

        aspect_wrapped = np.mod(np.nan_to_num(aspect_arr, nan=0.0), 360.0)
        ai = np.mod(
            np.rint(aspect_wrapped / 360.0 * self.n_aspect_bins).astype(np.int64),
            self.n_aspect_bins,
        )

        return table[si, ai]
