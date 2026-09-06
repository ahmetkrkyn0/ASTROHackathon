"""Direct-to-Earth (DTE) visibility: the Sun's pipeline run for the Earth.

Every test here fakes the ephemeris -- a scripted Earth vector built from a
chosen azimuth/elevation at the window centre -- so the geometry, the series
logic and the comm-window search are pinned without NAIF kernels on disk.
The real-kernel checks live in test_earth_visibility_real_grid.py.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pytest

from app import ephemeris
from app.illumination_series import _window_centre_latlon, sun_track_for_series

SHAPE = (6, 5)
N_AZ = 8


def _metadata(processed_dir=None) -> dict:
    meta = {
        "origin": {"x": 156000.0, "y": 28000.0},
        "resolution_m": 80.0,
        "shape": list(SHAPE),
        # No CRS on purpose: the synthetic grids carry none the projection
        # library can parse, and without one grid north IS true north.
    }
    if processed_dir is not None:
        meta["processed_dir"] = str(processed_dir)
    return meta


def _hours_since_epoch(utc: str) -> float:
    moment = datetime.fromisoformat(utc.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    epoch = datetime(2026, 9, 1, tzinfo=timezone.utc)
    return (moment - epoch).total_seconds() / 3600.0


def _vector_for(az_deg: float, el_deg: float, lat_deg: float, lon_deg: float) -> np.ndarray:
    """Inverse of sun_azel_from_vector: a body-fixed unit vector that reads
    back as (az, el) at the given surface point."""
    lat, lon = np.radians(lat_deg), np.radians(lon_deg)
    up = np.array([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)])
    east = np.array([-np.sin(lon), np.cos(lon), 0.0])
    north = np.array([-np.sin(lat) * np.cos(lon), -np.sin(lat) * np.sin(lon), np.cos(lat)])
    az, el = np.radians(az_deg), np.radians(el_deg)
    return np.cos(el) * (np.sin(az) * east + np.cos(az) * north) + np.sin(el) * up


def _script_ephemeris(monkeypatch, metadata, earth_azel, sun_azel=None):
    """Replace SPICE with two callables of ``hours`` -> (az_deg, el_deg)."""
    lat, lon = _window_centre_latlon(metadata)

    def _utc_to_et(utc, meta_kernel=None):
        # "et" is hours since 2026-09-01 in this fake; only differences matter.
        return _hours_since_epoch(utc)

    def _body_vector(body, et, meta_kernel=None):
        if body == "EARTH":
            az, el = earth_azel(float(et))
        elif body == "SUN" and sun_azel is not None:
            az, el = sun_azel(float(et))
        else:
            raise AssertionError(f"unexpected body {body!r}")
        return _vector_for(az, el, lat, lon)

    monkeypatch.setattr(ephemeris, "utc_to_et", _utc_to_et)
    monkeypatch.setattr(ephemeris, "body_vector_body", _body_vector)


# ── Task 1: the Earth track is the Sun track with a different target ───────


def test_earth_track_reports_the_scripted_azimuth_and_elevation(monkeypatch):
    from app.earth_visibility import earth_track_for_series

    metadata = _metadata()
    _script_ephemeris(monkeypatch, metadata, lambda h: (90.0, 5.0 - h))

    track = earth_track_for_series(metadata, 3, 2.0, "2026-09-01T00:00:00")

    assert [entry["index"] for entry in track] == [0, 1, 2]
    assert [entry["utc"] for entry in track] == [
        "2026-09-01T00:00:00Z",
        "2026-09-01T02:00:00Z",
        "2026-09-01T04:00:00Z",
    ]
    assert [entry["elevation_deg"] for entry in track] == pytest.approx([5.0, 3.0, 1.0], abs=1e-6)
    assert all(entry["azimuth_true_deg"] == pytest.approx(90.0, abs=1e-6) for entry in track)
    # No CRS means no meridian convergence, so the grid frame is the true frame.
    assert all(entry["azimuth_grid_deg"] == pytest.approx(90.0, abs=1e-6) for entry in track)


def test_sun_track_still_reports_the_sun(monkeypatch):
    """sun_track_for_series now routes through the body-parameterised
    helper; its contract must not have moved."""
    metadata = _metadata()
    _script_ephemeris(
        monkeypatch, metadata,
        earth_azel=lambda h: (0.0, 0.0),
        sun_azel=lambda h: (180.0, 10.0 + h),
    )

    track = sun_track_for_series(metadata, 2, 1.0, "2026-09-01T00:00:00")

    assert set(track[0]) == {"index", "utc", "azimuth_true_deg", "azimuth_grid_deg", "elevation_deg"}
    assert [entry["elevation_deg"] for entry in track] == pytest.approx([10.0, 11.0], abs=1e-6)
    assert track[1]["azimuth_true_deg"] == pytest.approx(180.0, abs=1e-6)


# ── Task 2: the per-slice series ───────────────────────────────────────────
#
# Horizon fixture: flat 0 deg everywhere, except column 1 which sees a 4 deg
# ridge toward grid East (bin 2 of 8 = 90 deg). The scripted Earth sits due
# East and sinks 1 deg per hour from +5 deg, so slice by slice the field goes
# "all visible" -> "column 1 hidden" -> "all hidden".

RIDGE_COL = 1
RIDGE_DEG = 4.0


def _horizon() -> np.ndarray:
    horizon = np.zeros((N_AZ, *SHAPE), dtype=np.float32)
    horizon[2, :, RIDGE_COL] = RIDGE_DEG
    return horizon


def _processed_dir(tmp_path):
    np.save(tmp_path / "horizon_map.npy", _horizon())
    return tmp_path


def _sinking_earth(h: float) -> tuple[float, float]:
    # Zero crossing at h = 5.25, deliberately BETWEEN samples: a scripted
    # elevation of exactly 0 comes back from arcsin as +/-1e-15 and lands on
    # either side of a strict threshold at random.
    return 90.0, 5.25 - h


def test_series_is_time_varying_with_an_epoch_and_a_horizon_cube(monkeypatch, tmp_path):
    from app.earth_visibility import build_earth_visibility_series

    metadata = _metadata(_processed_dir(tmp_path))
    _script_ephemeris(monkeypatch, metadata, _sinking_earth)

    series, provenance = build_earth_visibility_series(
        None, metadata, n_slices=4, slice_hours=2.0, start_utc="2026-09-01T00:00:00"
    )

    assert provenance["model"] == "spice_horizon"
    assert provenance["time_varying"] is True
    assert provenance["horizon_cache"].endswith("horizon_map.npy")
    assert len(series) == 4 and all(snapshot.shape == SHAPE for snapshot in series)
    # +5.25 deg: everything sees the Earth.
    assert series[0].min() == 1.0
    # +3.25 deg: the ridge column no longer does, the rest still does.
    assert series[1][:, RIDGE_COL].max() == 0.0
    assert np.delete(series[1], RIDGE_COL, axis=1).min() == 1.0
    # -0.75 deg: below the horizontal everywhere.
    assert series[3].max() == 0.0


def test_series_without_a_horizon_cube_is_static_from_the_long_run_layer(monkeypatch):
    from app.earth_visibility import build_earth_visibility_series

    metadata = _metadata()  # no processed_dir -> no horizon cache
    base = np.full(SHAPE, 0.42)

    series, provenance = build_earth_visibility_series(
        base, metadata, n_slices=3, slice_hours=1.0, start_utc="2026-09-01T00:00:00"
    )

    assert provenance["model"] == "static"
    assert provenance["time_varying"] is False
    assert "horizon_map.npy" in provenance["reason"]
    assert len(series) == 3 and all(np.array_equal(s, base) for s in series)


def test_series_without_an_epoch_says_so(monkeypatch):
    from app.earth_visibility import build_earth_visibility_series

    series, provenance = build_earth_visibility_series(
        np.full(SHAPE, 0.5), _metadata(), n_slices=2, slice_hours=1.0, start_utc=None
    )
    assert provenance["model"] == "static"
    assert "epoch" in provenance["reason"]
    assert len(series) == 2


def test_series_with_nothing_to_fall_back_on_is_unavailable_not_invented():
    from app.earth_visibility import build_earth_visibility_series

    series, provenance = build_earth_visibility_series(
        None, _metadata(), n_slices=2, slice_hours=1.0, start_utc=None
    )
    assert series == []
    assert provenance["model"] == "unavailable"
    assert provenance["time_varying"] is False
    assert provenance["reason"]


def test_series_degrades_when_the_ephemeris_fails(monkeypatch, tmp_path):
    """A missing kernel must not take the endpoint down -- the same contract
    build_shadow_series honours -- and the reason must name the failure."""
    from app.earth_visibility import build_earth_visibility_series

    metadata = _metadata(_processed_dir(tmp_path))

    def _broken(body, et, meta_kernel=None):
        raise RuntimeError("SPICE(NOSUCHFILE): de440s.bsp")

    monkeypatch.setattr(ephemeris, "utc_to_et", lambda utc, meta_kernel=None: 0.0)
    monkeypatch.setattr(ephemeris, "body_vector_body", _broken)

    series, provenance = build_earth_visibility_series(
        None, metadata, n_slices=2, slice_hours=1.0, start_utc="2026-09-01T00:00:00"
    )
    assert series == []
    assert provenance["model"] == "unavailable"
    assert "NOSUCHFILE" in provenance["reason"]


def test_series_rejects_a_horizon_cube_of_the_wrong_shape(monkeypatch, tmp_path):
    from app.earth_visibility import build_earth_visibility_series

    np.save(tmp_path / "horizon_map.npy", np.zeros((N_AZ, 3, 3), dtype=np.float32))
    metadata = _metadata(tmp_path)
    _script_ephemeris(monkeypatch, metadata, _sinking_earth)

    series, provenance = build_earth_visibility_series(
        None, metadata, n_slices=2, slice_hours=1.0, start_utc="2026-09-01T00:00:00"
    )
    assert series == []
    assert provenance["model"] == "unavailable"
    assert "does not match" in provenance["reason"]


# ── Task 2: the long-run fraction (the LOLA "average Earth visibility") ─────


def test_long_run_fraction_counts_the_samples_in_which_each_cell_sees_earth(monkeypatch):
    from app.earth_visibility import long_run_earth_visibility

    metadata = _metadata()
    _script_ephemeris(monkeypatch, metadata, _sinking_earth)

    # 10 hourly samples at h = 0..9: elevations +5.25 .. -3.75. A flat cell
    # sees the Earth while el > 0 (h = 0..5 -> 6 of 10); the ridge column
    # only while el > 4 (h = 0, 1 -> 2 of 10). The span END is not sampled
    # -- a full-year run must not count its first hour twice.
    fraction, info = long_run_earth_visibility(
        _horizon(), metadata, start_utc="2026-09-01T00:00:00",
        span_days=10.0 / 24.0, step_hours=1.0,
    )

    assert fraction.shape == SHAPE and fraction.dtype == np.float32
    assert fraction[:, RIDGE_COL] == pytest.approx(0.2)
    assert np.delete(fraction, RIDGE_COL, axis=1) == pytest.approx(0.6)
    assert info["n_samples"] == 10
    assert info["step_hours"] == 1.0
    assert info["earth_elevation_max_deg"] == pytest.approx(5.25, abs=1e-6)
    assert info["earth_elevation_min_deg"] == pytest.approx(-3.75, abs=1e-6)
    assert info["start_utc"] == "2026-09-01T00:00:00Z"
    assert info["model"] == "spice_horizon"


# ── Task 2: the per-cell forward search behind comm_minutes_remaining ──────


def _triangle_earth(h: float) -> tuple[float, float]:
    """Rises above the horizontal at h = 4.75, peaks +5.25 at h = 10, sets
    at h = 15.25, period 20 h. The crossings sit between the 30-minute
    samples on purpose (see _sinking_earth)."""
    return 90.0, 5.25 - abs((h % 20.0) - 10.0)


def test_comm_window_reports_minutes_until_the_earth_sets(monkeypatch):
    from app.earth_visibility import comm_window

    metadata = _metadata()
    _script_ephemeris(monkeypatch, metadata, _triangle_earth)

    window = comm_window(_horizon(), metadata, 0, 0, "2026-09-01T10:00:00", step_minutes=30.0)

    assert window["visible_now"] is True
    assert window["earth_elevation_deg"] == pytest.approx(5.25, abs=1e-6)
    assert window["earth_azimuth_grid_deg"] == pytest.approx(90.0, abs=1e-6)
    assert window["horizon_deg"] == 0.0
    # Sets at h = 15.25; the first 30-minute sample past that is h = 15.5.
    assert window["minutes_remaining"] == pytest.approx(330.0)
    assert window["minutes_until_visible"] is None
    assert window["next_change_utc"] == "2026-09-01T15:30:00Z"
    assert window["search_limited"] is False
    assert window["trigger_minutes_remaining"] == pytest.approx(330.0)


def test_comm_window_reports_minutes_until_the_earth_rises(monkeypatch):
    from app.earth_visibility import comm_window

    metadata = _metadata()
    _script_ephemeris(monkeypatch, metadata, _triangle_earth)

    window = comm_window(_horizon(), metadata, 0, 0, "2026-09-01T00:00:00", step_minutes=30.0)

    assert window["visible_now"] is False
    assert window["minutes_remaining"] is None
    # Crosses 0 deg at h = 4.75; the first 30-minute sample past that is h = 5.
    assert window["minutes_until_visible"] == pytest.approx(300.0)
    assert window["next_change_utc"] == "2026-09-01T05:00:00Z"
    # For the replan trigger "no link now" is zero minutes of link left.
    assert window["trigger_minutes_remaining"] == 0.0


def test_comm_window_respects_the_local_horizon(monkeypatch):
    """The ridge column needs the Earth above 4 deg: at h = 8 (el +3.25) the
    flat cell has a link and the ridge cell does not."""
    from app.earth_visibility import comm_window

    metadata = _metadata()
    _script_ephemeris(monkeypatch, metadata, _triangle_earth)

    flat = comm_window(_horizon(), metadata, 0, 0, "2026-09-01T08:00:00")
    ridge = comm_window(_horizon(), metadata, 0, RIDGE_COL, "2026-09-01T08:00:00")

    assert flat["visible_now"] is True
    assert ridge["visible_now"] is False
    assert ridge["horizon_deg"] == pytest.approx(RIDGE_DEG)
    # The ridge cell's link opens once el > 4 (h > 8.75): sample h = 9 -> 60 min.
    assert ridge["minutes_until_visible"] == pytest.approx(60.0)


def test_comm_window_says_when_the_search_ran_out(monkeypatch):
    from app.earth_visibility import comm_window

    metadata = _metadata()
    _script_ephemeris(monkeypatch, metadata, _triangle_earth)

    window = comm_window(
        _horizon(), metadata, 0, 0, "2026-09-01T00:00:00",
        step_minutes=30.0, max_hours=2.0,
    )
    assert window["visible_now"] is False
    assert window["minutes_until_visible"] is None
    assert window["next_change_utc"] is None
    assert window["search_limited"] is True

    # A link that outlasts the search is reported as "at least this long",
    # never as "unknown" -- the trigger needs a number.
    window = comm_window(
        _horizon(), metadata, 0, 0, "2026-09-01T10:00:00",
        step_minutes=30.0, max_hours=2.0,
    )
    assert window["visible_now"] is True
    assert window["minutes_remaining"] is None
    assert window["search_limited"] is True
    assert window["trigger_minutes_remaining"] == pytest.approx(120.0)


def test_comm_window_from_metadata_needs_the_horizon_cache(monkeypatch, tmp_path):
    from app.earth_visibility import comm_window_from_metadata

    assert comm_window_from_metadata(_metadata(), 0, 0, "2026-09-01T10:00:00") is None

    metadata = _metadata(_processed_dir(tmp_path))
    _script_ephemeris(monkeypatch, metadata, _triangle_earth)
    window = comm_window_from_metadata(metadata, 0, 0, "2026-09-01T10:00:00")
    assert window is not None and window["visible_now"] is True

    with pytest.raises(ValueError):
        comm_window_from_metadata(metadata, SHAPE[0], 0, "2026-09-01T10:00:00")
