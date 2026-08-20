"""Sun geometry for the lunar surface.

Split deliberately in two:

* pure geometry (``sun_azel_from_vector``) -- no external data, unit tested
* SPICE-backed ephemeris (``sun_vector_body``, ``sun_track``) -- needs NAIF
  kernels fetched by ``lunapath/src/fetch_kernels.py``; not unit tested

Azimuth convention matches :mod:`app.horizon`: 0 = North, 90 = East,
range [0, 360).
"""

from __future__ import annotations

import numpy as np

DEFAULT_META_KERNEL = "kernels/lunapath.tm"
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


def sun_vector_body(et: float, meta_kernel: str = DEFAULT_META_KERNEL) -> np.ndarray:
    """Sun position in MOON_ME at ephemeris time *et*. Requires NAIF kernels."""
    try:
        import spiceypy as spice
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "spiceypy is required for ephemeris queries. "
            "Install it and run lunapath/src/fetch_kernels.py first."
        ) from exc

    spice.furnsh(meta_kernel)
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

    spice.furnsh(meta_kernel)
    et0 = spice.str2et(utc_start)
    et1 = spice.str2et(utc_end)
    ets = np.linspace(et0, et1, int(n_samples))
    return [
        sun_azel_from_vector(sun_vector_body(float(et), meta_kernel), lat_deg, lon_deg)
        for et in ets
    ]
