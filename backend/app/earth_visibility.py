"""Direct-to-Earth (DTE) visibility: the illumination pipeline run for the Earth.

VIPER's traverse planning is constrained less by the Sun than by the Earth:
the rover is teleoperated, so it drives only while it has a direct radio
line of sight to Earth, and every leg ends at a place that keeps that link
(Shirley & Balaban 2022). LunaPath modelled the Sun in detail and the Earth
not at all -- ``replan_triggers.check_comm_window`` existed, but its input
was expected from outside and never computed.

The geometry is the one :mod:`app.illumination` already applies to the Sun:
a cell sees a body when the body's local elevation exceeds the terrain
horizon angle in the body's azimuth (Mazarico et al. 2011, the method behind
NASA's LOLA Earth-visibility products). Only the ephemeris target changes.
At the pole the Earth's elevation librates between roughly -7 and +7 deg
with a ~27 day period, so this field changes on the scale of DAYS, not the
hours the Sun's field changes on.

Three consumers:

* a long-run fraction layer, ``earth_visibility_grid.npy``, built once by
  ``scripts/build_earth_visibility_cache.py`` (the LOLA "average Earth
  visibility" product, computed here for this window);
* a per-slice series for ``/api/earth-series`` and the 4-D planner;
* a per-cell forward search, :func:`comm_window`, that turns the trigger's
  ``comm_minutes_remaining`` from a hand-fed number into a computed one.

Like :func:`app.illumination_series.build_shadow_series`, nothing here
fabricates a field it cannot compute: a series that could not be built is
returned labelled ``static`` (from the long-run layer) or ``unavailable``,
with the reason spelled out.
"""

from __future__ import annotations

import math
import os
from datetime import timedelta
from typing import Any

import numpy as np

from .illumination import illuminated_mask
from .illumination_series import (
    HORIZON_CACHE_FILENAME,
    _grid_north_azimuth,
    _parse_start_utc,
    _window_centre_latlon,
    body_track_for_series,
    horizon_cache_path,
)

#: Long-run Earth-visibility fraction, beside the processed grids. Written by
#: ``scripts/build_earth_visibility_cache.py``; loaded by ``data_loader`` when
#: present, under the grid key ``earth_visibility``.
EARTH_VISIBILITY_CACHE_FILENAME: str = "earth_visibility_grid.npy"
#: Provenance of that layer -- sampling span, step, count, elevation range.
EARTH_VISIBILITY_META_FILENAME: str = "earth_visibility_meta.json"

#: Default forward search for :func:`comm_window`. The Earth's elevation at
#: the pole runs through one libration cycle in ~27 days, so half a cycle
#: is enough to find the next rise or set from any phase.
DEFAULT_COMM_SEARCH_HOURS: float = 336.0
DEFAULT_COMM_STEP_MINUTES: float = 30.0


def earth_track_for_series(
    metadata: dict[str, Any],
    n_slices: int,
    slice_hours: float,
    start_utc: str,
) -> list[dict[str, Any]]:
    """Earth azimuth and elevation at each slice; same shape as the Sun track."""
    return body_track_for_series(metadata, n_slices, slice_hours, start_utc, body="EARTH")


def earth_visible_mask(
    horizon_deg: np.ndarray, earth_az_grid_deg: float, earth_elev_deg: float
) -> np.ndarray:
    """(H, W) bool: True where the Earth clears the local terrain horizon.

    The same predicate as :func:`app.illumination.illuminated_mask`, sentinel
    handling included -- a cell whose ray left the DEM is credited with a
    link exactly when the Earth is above the horizontal.
    """
    return illuminated_mask(horizon_deg, earth_az_grid_deg, earth_elev_deg)


def _load_horizon(cache_path: str, expected_shape: tuple[int, int]) -> np.ndarray:
    horizon = np.load(cache_path)
    if horizon.ndim != 3 or tuple(horizon.shape[1:]) != tuple(expected_shape):
        raise ValueError(
            f"horizon cache {horizon.shape} does not match the grid "
            f"{tuple(expected_shape)}"
        )
    return horizon


def _grid_shape(metadata: dict[str, Any]) -> tuple[int, int]:
    shape = metadata.get("shape") or (0, 0)
    return int(shape[0]), int(shape[1])


def build_earth_visibility_series(
    base_fraction: np.ndarray | None,
    metadata: dict[str, Any],
    n_slices: int,
    slice_hours: float,
    start_utc: str | None = None,
) -> tuple[list[np.ndarray], dict[str, Any]]:
    """Return ``(series, provenance)``: one (H, W) 1.0/0.0 grid per slice.

    Three honest outcomes, in the order they are tried:

    * ``spice_horizon`` -- an epoch, the horizon cube and NAIF kernels are
      all present; each slice is the instantaneous visibility mask.
    * ``static`` -- something was missing but *base_fraction* (the long-run
      layer) was given; it is repeated per slice and ``reason`` says what
      was missing.
    * ``unavailable`` -- nothing to compute from and nothing to fall back
      on; the series is EMPTY. A caller that needs the field must say it
      could not have it, not paint zeros.
    """
    count = int(n_slices)

    def _fallback(reason: str) -> tuple[list[np.ndarray], dict[str, Any]]:
        if base_fraction is not None:
            base = np.asarray(base_fraction, dtype=np.float64)
            return [base] * count, {
                "model": "static",
                "time_varying": False,
                "reason": reason,
            }
        return [], {"model": "unavailable", "time_varying": False, "reason": reason}

    if start_utc is None:
        return _fallback(
            "no start epoch given; Earth visibility is a function of time and "
            "cannot vary without one"
        )

    cache_path = horizon_cache_path(metadata)
    if cache_path is None:
        return _fallback(
            f"no {HORIZON_CACHE_FILENAME} beside the processed grids; run "
            "scripts/build_horizon_cache.py to enable Earth visibility"
        )

    try:
        horizon = _load_horizon(cache_path, _grid_shape(metadata))
        track = earth_track_for_series(metadata, count, float(slice_hours), start_utc)
        series = [
            np.where(
                earth_visible_mask(
                    horizon, entry["azimuth_grid_deg"], entry["elevation_deg"]
                ),
                1.0,
                0.0,
            )
            for entry in track
        ]
    except Exception as exc:
        # Deliberately broad, deliberately non-fatal: spiceypy maps SPICE
        # failures on to assorted builtin exception types, and a missing
        # kernel must degrade to the honest fallback rather than take an
        # endpoint down. Same contract as build_shadow_series.
        return _fallback(f"Earth visibility unavailable ({exc})")

    return series, {
        "model": "spice_horizon",
        "time_varying": True,
        "horizon_cache": cache_path,
        "start_utc": start_utc,
    }


def long_run_earth_visibility(
    horizon: np.ndarray,
    metadata: dict[str, Any],
    start_utc: str,
    span_days: float,
    step_hours: float,
    progress: bool = False,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Fraction of sampled instants in which each cell sees the Earth.

    This is LunaPath's own version of the LOLA "average Earth visibility"
    product (Mazarico et al. 2011; PGDA product 69, 18.6 years at hourly
    steps). Samples run from *start_utc* for *span_days* at *step_hours*,
    end excluded, so a whole-year span does not count its first hour twice.

    Returns the (H, W) float32 fraction and a provenance dict meant to be
    written beside it as ``EARTH_VISIBILITY_META_FILENAME``.
    """
    horizon = np.asarray(horizon)
    if horizon.ndim != 3:
        raise ValueError(f"horizon must be (n_azimuth, H, W), got {horizon.shape}")
    step = float(step_hours)
    if step <= 0.0 or float(span_days) <= 0.0:
        raise ValueError("span_days and step_hours must be positive")
    n_samples = max(1, int(round(float(span_days) * 24.0 / step)))

    track = earth_track_for_series(metadata, n_samples, step, start_utc)
    accumulator = np.zeros(horizon.shape[1:], dtype=np.float64)
    elevations = np.empty(n_samples, dtype=np.float64)
    for index, entry in enumerate(track):
        accumulator += earth_visible_mask(
            horizon, entry["azimuth_grid_deg"], entry["elevation_deg"]
        )
        elevations[index] = entry["elevation_deg"]
        if progress and (index + 1) % 1000 == 0:
            print(f"  earth visibility: sample {index + 1}/{n_samples}", flush=True)

    fraction = (accumulator / float(n_samples)).astype(np.float32)
    start = _parse_start_utc(start_utc)
    end = start + timedelta(hours=step * n_samples)
    info = {
        "model": "spice_horizon",
        "start_utc": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end_utc": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "span_days": float(span_days),
        "step_hours": step,
        "n_samples": int(n_samples),
        "earth_elevation_min_deg": float(elevations.min()),
        "earth_elevation_max_deg": float(elevations.max()),
        "mean_fraction": float(fraction.mean()),
        "n_azimuth": int(horizon.shape[0]),
        "reference": (
            "Mazarico et al. 2011, Icarus 211; same horizon method as the "
            "LOLA average-Earth-visibility products (PGDA 69)"
        ),
    }
    return fraction, info


def comm_window(
    horizon: np.ndarray,
    metadata: dict[str, Any],
    row: int,
    col: int,
    utc: str,
    step_minutes: float = DEFAULT_COMM_STEP_MINUTES,
    max_hours: float = DEFAULT_COMM_SEARCH_HOURS,
) -> dict[str, Any]:
    """When does this cell's Direct-to-Earth link next change?

    Steps forward from *utc* in *step_minutes* increments for up to
    *max_hours* and reports the first change of state. The cell's own horizon
    profile is used; the Earth's direction is taken at the window centre,
    the same approximation the Sun path makes (across a 2.5 km window the
    difference is well under a horizon bin).

    ``trigger_minutes_remaining`` is always a number, for
    :func:`app.replan_triggers.check_comm_window`: the minutes until the
    link closes; the full search length when the link outlasts the search
    (a lower bound, flagged by ``search_limited``); and ``0.0`` when there
    is no link now -- VIPER does not drive without one.
    """
    from . import ephemeris

    horizon = np.asarray(horizon)
    if horizon.ndim != 3:
        raise ValueError(f"horizon must be (n_azimuth, H, W), got {horizon.shape}")
    n_az, height, width = horizon.shape
    if not (0 <= int(row) < height and 0 <= int(col) < width):
        raise ValueError(f"cell ({row}, {col}) is outside the {height}x{width} grid")
    profile = np.asarray(horizon[:, int(row), int(col)], dtype=np.float64).reshape(
        n_az, 1, 1
    )

    lat_deg, lon_deg = _window_centre_latlon(metadata)
    north_grid_az = _grid_north_azimuth(metadata)
    start = _parse_start_utc(utc)

    def _state(moment):
        et = ephemeris.utc_to_et(moment.strftime("%Y-%m-%dT%H:%M:%S"))
        true_az, elev = ephemeris.sun_azel_from_vector(
            ephemeris.body_vector_body("EARTH", et), lat_deg, lon_deg
        )
        grid_az = float(ephemeris.true_azimuth_to_grid_azimuth(true_az, north_grid_az))
        visible = bool(earth_visible_mask(profile, grid_az, elev)[0, 0])
        return visible, float(true_az) % 360.0, grid_az % 360.0, float(elev)

    visible_now, true_az, grid_az, elev = _state(start)
    from .illumination import _azimuth_bin

    horizon_deg = float(profile[_azimuth_bin(grid_az, n_az), 0, 0])

    step = float(step_minutes)
    if step <= 0.0:
        raise ValueError("step_minutes must be positive")
    n_steps = max(1, int(math.ceil(float(max_hours) * 60.0 / step)))
    change_minutes: float | None = None
    change_utc: str | None = None
    for index in range(1, n_steps + 1):
        moment = start + timedelta(minutes=step * index)
        visible, _, _, _ = _state(moment)
        if visible != visible_now:
            change_minutes = step * index
            change_utc = moment.strftime("%Y-%m-%dT%H:%M:%SZ")
            break

    searched_minutes = step * n_steps
    search_limited = change_minutes is None
    if visible_now:
        minutes_remaining = change_minutes
        minutes_until_visible = None
        trigger_minutes = searched_minutes if search_limited else float(change_minutes)
    else:
        minutes_remaining = None
        minutes_until_visible = change_minutes
        trigger_minutes = 0.0

    return {
        "utc": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "row": int(row),
        "col": int(col),
        "visible_now": visible_now,
        "minutes_remaining": minutes_remaining,
        "minutes_until_visible": minutes_until_visible,
        "next_change_utc": change_utc,
        "search_limited": search_limited,
        "searched_hours": searched_minutes / 60.0,
        "step_minutes": step,
        "trigger_minutes_remaining": float(trigger_minutes),
        "earth_elevation_deg": elev,
        "earth_azimuth_true_deg": true_az,
        "earth_azimuth_grid_deg": grid_az,
        "horizon_deg": horizon_deg,
    }


def comm_window_from_metadata(
    metadata: dict[str, Any],
    row: int,
    col: int,
    utc: str,
    **kwargs: Any,
) -> dict[str, Any] | None:
    """:func:`comm_window` against the cached horizon cube, or ``None`` when
    there is no cube to read. Memory-mapped: one cell's profile is 72
    values out of a 69 MB file, and a per-request full load would be the
    whole cost of the endpoint."""
    cache_path = horizon_cache_path(metadata)
    if cache_path is None:
        return None
    horizon = np.load(cache_path, mmap_mode="r")
    return comm_window(horizon, metadata, row, col, utc, **kwargs)


def earth_visibility_cache_path(metadata: dict[str, Any]) -> str | None:
    """Where the long-run layer for these grids would live, if it exists."""
    processed_dir = metadata.get("processed_dir")
    if not processed_dir:
        return None
    path = os.path.join(str(processed_dir), EARTH_VISIBILITY_CACHE_FILENAME)
    return path if os.path.exists(path) else None
