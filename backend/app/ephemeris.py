"""Sun geometry for the lunar surface.

Split deliberately in two:

* pure geometry (``sun_azel_from_vector``) -- no external data, unit tested
* SPICE-backed ephemeris (``sun_vector_body``, ``sun_track``) -- needs NAIF
  kernels fetched by ``lunapath/src/fetch_kernels.py``; not unit tested

Azimuth convention matches :mod:`app.horizon`: 0 = North, 90 = East,
range [0, 360).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

# backend/app/ephemeris.py -> backend/app -> backend -> repo root.
# Resolved from __file__ rather than the CWD: the documented pipeline
# invocation is `cd lunapath/src && python process_lunar_data.py`, under
# which a CWD-relative "kernels/lunapath.tm" never resolves (fetch_kernels.py
# writes to the REPO ROOT's kernels/). Same pattern fetch_kernels.py uses.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_META_KERNEL = str(_REPO_ROOT / "kernels" / "lunapath.tm")
_MOON_BODY_FRAME = "MOON_ME"


def sun_azel_from_vector(
    sun_vec_body: np.ndarray,
    lat_deg: float,
    lon_deg: float,
) -> tuple[float, float]:
    """Convert a Moon-body-fixed Sun vector to local azimuth/elevation.

    Parameters
    ----------
    sun_vec_body:
        Sun position in the Moon body-fixed frame (MOON_ME). Magnitude is
        irrelevant; only direction is used.
    lat_deg, lon_deg:
        Sub-observer point on the lunar surface, degrees.

    Returns
    -------
    (azimuth_deg, elevation_deg)
    """
    vec = np.asarray(sun_vec_body, dtype=np.float64).reshape(3)
    norm = float(np.linalg.norm(vec))
    if norm == 0.0 or not np.isfinite(norm):
        raise ValueError("sun_vec_body must be a finite non-zero 3-vector")
    unit = vec / norm

    lat = np.radians(float(lat_deg))
    lon = np.radians(float(lon_deg))

    up = np.array(
        [np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)]
    )
    east = np.array([-np.sin(lon), np.cos(lon), 0.0])
    north = np.array(
        [-np.sin(lat) * np.cos(lon), -np.sin(lat) * np.sin(lon), np.cos(lat)]
    )

    u = float(np.dot(unit, up))
    e = float(np.dot(unit, east))
    n = float(np.dot(unit, north))

    elevation_deg = float(np.degrees(np.arcsin(np.clip(u, -1.0, 1.0))))
    azimuth_deg = float(np.degrees(np.arctan2(e, n)) % 360.0)
    return azimuth_deg, elevation_deg


def true_north_grid_azimuth(
    lat_deg: float, lon_deg: float, crs_wkt: str, step_deg: float = 1e-4
) -> float:
    """Grid-frame azimuth (app.horizon convention: 0 = decreasing row/North,
    90 = increasing column/East) that TRUE north points toward, at
    (lat_deg, lon_deg) in the given projected CRS.

    sun_azel_from_vector's azimuth is true-north-referenced (an ENU frame on
    the body-fixed sphere); app.horizon's bins are grid-north-referenced
    (raster row/column directions). These coincide only on the projection's
    central meridian. Computed numerically via a short true-north step
    projected through the real CRS, rather than an assumed closed-form
    convergence formula, so this is correct for any CRS the pipeline loads,
    not just the one active today.
    """
    import os

    os.environ.setdefault("PROJ_IGNORE_CELESTIAL_BODY", "YES")
    from pyproj import Transformer

    to_proj = Transformer.from_crs("EPSG:4326", crs_wkt, always_xy=True)
    x0, y0 = to_proj.transform(lon_deg, lat_deg)
    x1, y1 = to_proj.transform(lon_deg, lat_deg + step_deg)
    dx, dy = x1 - x0, y1 - y0
    # Grid convention (derived from app.horizon + the Task 8 y-sign fix):
    # +col <-> +x (East), +row <-> -y (row increases southward), so grid
    # azimuth 0 (grid North = decreasing row) points along +y, and grid
    # azimuth 90 (East = increasing column) points along +x. That is the
    # standard atan2(dx, dy) compass-bearing form.
    return float(np.degrees(np.arctan2(dx, dy)) % 360.0)


def true_azimuth_to_grid_azimuth(
    true_az_deg: float, true_north_grid_az_deg: float
) -> float:
    """Rotate a true-north-referenced azimuth (from sun_azel_from_vector /
    sun_track) into app.horizon's grid-frame convention."""
    return float((true_north_grid_az_deg + true_az_deg) % 360.0)


def grid_azimuth_to_true_azimuth(
    grid_az_deg: float | np.ndarray, true_north_grid_az_deg: float
) -> float | np.ndarray:
    """Inverse of :func:`true_azimuth_to_grid_azimuth`.

    Rotates a grid-frame azimuth (app.horizon / make_aspect_grid convention:
    0 = decreasing row, 90 = increasing column) into the true-north frame
    that heat1d's ``slope_az`` and ``orbits.solarAzimuth`` expect (0 = true
    North, clockwise) -- the same frame mismatch Faz 1's C1 finding fixed
    for the shadow path (``true_azimuth_to_grid_azimuth``); the thermal path
    still fed raw grid-frame aspect straight to heat1d (Faz 1-2-3 review,
    M1).

    Vectorised, unlike ``true_azimuth_to_grid_azimuth``: the shadow path
    only ever rotates individual (az, elev) sun samples, but the thermal
    path needs to rotate a whole (H, W) aspect grid in one call.
    """
    grid_az = np.asarray(grid_az_deg, dtype=np.float64)
    rotated = np.mod(grid_az - float(true_north_grid_az_deg), 360.0)
    return rotated if grid_az.ndim else float(rotated)


# Kernels already furnished in this process. spice.furnsh appends the
# meta-kernel's files to CSPICE's KEEPER database every time it is
# called, so sun_track(n_samples=N) -- which calls sun_vector_body per
# sample -- loaded the same kernels N+1 times. Duplicates count against
# the loaded-kernel limit and re-prioritise SPKs, so a long-running
# process making repeated ephemeris queries degrades and eventually
# fails with a kernel-database error. Load once per process per kernel.
# (Round 2 review, L-3.)
_FURNISHED: set[str] = set()


def _ensure_kernels(spice, meta_kernel: str) -> None:
    # The cache is only valid while the SPICE pool still holds what it
    # recorded. Anything calling spice.kclear() empties the pool without
    # telling us, after which every subsequent query would run with NO
    # kernels loaded and fail obscurely -- or worse, succeed against a
    # partially reloaded pool. Checking the pool is one cheap call.
    # (Round 3 review, L-17.)
    try:
        if int(spice.ktotal("ALL")) == 0:
            _FURNISHED.clear()
    except Exception:  # pragma: no cover - defensive, ktotal is not optional
        _FURNISHED.clear()
    if meta_kernel not in _FURNISHED:
        spice.furnsh(meta_kernel)
        _FURNISHED.add(meta_kernel)


def utc_to_et(utc: str, meta_kernel: str = DEFAULT_META_KERNEL) -> float:
    """UTC string -> ephemeris time, loading the kernel pool first.

    ``spice.str2et`` needs the leapsecond kernel in the pool. Every caller
    that furnished the pool itself before calling ``str2et`` directly has,
    at one point, gotten the order wrong: the first ``str2et`` in a cold
    process raises ``SPICE(NOLEAPSECONDS)``, and depending on how broadly
    the caller catches that, it can look like "no kernels available" when
    the kernels were simply never asked for yet. Routing every UTC-to-ET
    conversion through here makes "furnish before you convert" a property
    of the API instead of something each caller has to remember.
    """
    import spiceypy as spice

    _ensure_kernels(spice, meta_kernel)
    return float(spice.str2et(utc))


def sun_vector_body(et: float, meta_kernel: str = DEFAULT_META_KERNEL) -> np.ndarray:
    """Sun position in MOON_ME at ephemeris time *et*. Requires NAIF kernels."""
    try:
        import spiceypy as spice
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "spiceypy is required for ephemeris queries. "
            "Install it and run lunapath/src/fetch_kernels.py first."
        ) from exc

    _ensure_kernels(spice, meta_kernel)
    position, _light_time = spice.spkpos("SUN", et, _MOON_BODY_FRAME, "LT+S", "MOON")
    return np.asarray(position, dtype=np.float64)


def sun_track(
    utc_start: str,
    utc_end: str,
    n_samples: int,
    lat_deg: float,
    lon_deg: float,
    meta_kernel: str = DEFAULT_META_KERNEL,
) -> list[tuple[float, float]]:
    """Sample (azimuth_deg, elevation_deg) between two UTC instants.

    Requires NAIF kernels. Output feeds ``app.illumination`` and the
    Phase 3 time-expanded planner.
    """
    try:
        import spiceypy as spice
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "spiceypy is required for ephemeris queries. "
            "Install it and run lunapath/src/fetch_kernels.py first."
        ) from exc

    _ensure_kernels(spice, meta_kernel)
    et0 = spice.str2et(utc_start)
    et1 = spice.str2et(utc_end)
    ets = np.linspace(et0, et1, int(n_samples))
    return [
        sun_azel_from_vector(sun_vector_body(float(et), meta_kernel), lat_deg, lon_deg)
        for et in ets
    ]
