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

    def __init__(self, elevation: np.ndarray, resolution_m: float) -> None:
        self._elevation = np.asarray(elevation, dtype=np.float64)
        self._resolution_m = float(resolution_m)

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
