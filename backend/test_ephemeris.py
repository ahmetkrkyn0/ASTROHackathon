"""Sun azimuth/elevation geometry tests (no SPICE kernels required)."""

from __future__ import annotations

import numpy as np
import pytest

from app.ephemeris import (
    grid_azimuth_to_true_azimuth,
    sun_azel_from_vector,
    true_azimuth_to_grid_azimuth,
    true_north_grid_azimuth,
)

# The real south-polar-stereographic WKT the pipeline is running against,
# copied verbatim from lunapath/data/processed/metadata.json's "crs" field.
LUNAR_SOUTH_POLAR_WKT = (
    'PROJCS["unnamed",GEOGCS["unnamed ellipse",DATUM["unknown",'
    'SPHEROID["unnamed",1737400,0]],PRIMEM["Greenwich",0],'
    'UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]]],'
    'PROJECTION["Polar_Stereographic"],PARAMETER["latitude_of_origin",-90],'
    'PARAMETER["central_meridian",0],PARAMETER["false_easting",0],'
    'PARAMETER["false_northing",0],UNIT["metre",1],'
    'AXIS["Easting",NORTH],AXIS["Northing",NORTH]]'
)


def test_sun_overhead_at_equator_prime_meridian():
    az, el = sun_azel_from_vector(np.array([1.0, 0.0, 0.0]), lat_deg=0.0, lon_deg=0.0)
    assert el == pytest.approx(90.0, abs=1e-6)


def test_sun_due_east_at_equator_prime_meridian():
    az, el = sun_azel_from_vector(np.array([0.0, 1.0, 0.0]), lat_deg=0.0, lon_deg=0.0)
    assert el == pytest.approx(0.0, abs=1e-6)
    assert az == pytest.approx(90.0, abs=1e-6)


def test_sun_due_north_at_equator_prime_meridian():
    az, el = sun_azel_from_vector(np.array([0.0, 0.0, 1.0]), lat_deg=0.0, lon_deg=0.0)
    assert el == pytest.approx(0.0, abs=1e-6)
    assert az == pytest.approx(0.0, abs=1e-6)


def test_at_south_pole_body_x_axis_is_local_north():
    """At lat=-90 the +X body direction lies on the local horizon, due North."""
    az, el = sun_azel_from_vector(np.array([1.0, 0.0, 0.0]), lat_deg=-90.0, lon_deg=0.0)
    assert el == pytest.approx(0.0, abs=1e-6)
    assert az == pytest.approx(0.0, abs=1e-6)


def test_south_pole_sun_is_low_not_overhead():
    """A Sun vector 1.5 deg above the local horizon at the south pole."""
    elev_rad = np.radians(1.5)
    vec = np.array([np.cos(elev_rad), 0.0, -np.sin(elev_rad)])
    az, el = sun_azel_from_vector(vec, lat_deg=-90.0, lon_deg=0.0)
    assert el == pytest.approx(1.5, abs=1e-6)


def test_azimuth_is_normalised_to_zero_360():
    az, _ = sun_azel_from_vector(np.array([0.0, -1.0, 0.0]), lat_deg=0.0, lon_deg=0.0)
    assert 0.0 <= az < 360.0
    assert az == pytest.approx(270.0, abs=1e-6)


def test_zero_vector_is_rejected():
    with pytest.raises(ValueError):
        sun_azel_from_vector(np.zeros(3), lat_deg=-88.0, lon_deg=0.0)


# --- true-north -> grid-north azimuth conversion (final review, C1) ---------


def _circular_delta(a_deg: float, b_deg: float) -> float:
    """Smallest absolute angular separation between two bearings."""
    return abs((float(a_deg) - float(b_deg) + 180.0) % 360.0 - 180.0)


def test_grid_north_matches_true_north_on_central_meridian():
    """The two frames coincide exactly on the projection's central meridian."""
    az = true_north_grid_azimuth(-89.0, 0.0, LUNAR_SOUTH_POLAR_WKT)
    assert _circular_delta(az, 0.0) < 1e-3


def test_grid_north_diverges_off_the_central_meridian():
    """90 deg off the central meridian, grid north is 90 deg from true north.

    This is the whole point of the conversion: away from the central meridian
    the horizon bins and the Sun azimuth are in different frames.
    """
    az = true_north_grid_azimuth(-89.0, 90.0, LUNAR_SOUTH_POLAR_WKT)
    assert _circular_delta(az, 90.0) < 1e-3


def test_grid_north_at_a_verified_south_polar_point():
    """A fixed ground-truth point, not whichever window currently ships.

    (-89.4991897, -110.2248594) was the centre of the Site01 window this
    project shipped when the Faz 1 final reviewer independently reproduced
    this bearing as ~249.8 deg -- a ~110 deg offset from true north, i.e.
    ~22 of 72 horizon bins. The shipped window has since moved to Site11,
    but the point is kept: what this test pins is the projection maths at a
    known latitude/longitude, and that answer does not change with the
    window. Re-anchoring it to whatever ships today would discard an
    independently verified value and prove nothing extra.
    """
    az = true_north_grid_azimuth(
        -89.4991897, -110.2248594, LUNAR_SOUTH_POLAR_WKT
    )
    assert az == pytest.approx(249.775, abs=0.05)


def test_grid_north_is_insensitive_to_the_step_size():
    """A numeric derivative must not depend on the probe step length."""
    values = [
        true_north_grid_azimuth(
            -89.4991897, -110.2248594, LUNAR_SOUTH_POLAR_WKT, step_deg=step
        )
        for step in (1e-6, 1e-5, 1e-4, 1e-3)
    ]
    for value in values[1:]:
        assert _circular_delta(value, values[0]) < 1e-3


def test_grid_north_azimuth_is_normalised_to_zero_360():
    for lon in (-179.0, -110.2248594, 0.0, 45.0, 179.0):
        az = true_north_grid_azimuth(-89.0, lon, LUNAR_SOUTH_POLAR_WKT)
        assert 0.0 <= az < 360.0


def test_true_azimuth_zero_maps_to_the_grid_north_bearing():
    """A Sun due TRUE north sits at whatever bearing grid-frame north is."""
    assert true_azimuth_to_grid_azimuth(0.0, 249.775141) == pytest.approx(
        249.775141
    )


def test_true_azimuth_rotates_by_the_grid_north_offset():
    assert true_azimuth_to_grid_azimuth(90.0, 249.775141) == pytest.approx(
        339.775141
    )


def test_true_azimuth_to_grid_azimuth_wraps_past_360():
    assert true_azimuth_to_grid_azimuth(180.0, 249.775141) == pytest.approx(
        69.775141
    )
    assert true_azimuth_to_grid_azimuth(350.0, 20.0) == pytest.approx(10.0)


def test_true_azimuth_to_grid_azimuth_is_identity_on_central_meridian():
    """With no convergence, the conversion must be a no-op."""
    for true_az in (0.0, 45.0, 123.4, 359.9):
        assert true_azimuth_to_grid_azimuth(true_az, 0.0) == pytest.approx(true_az)


# ── grid_azimuth_to_true_azimuth: the inverse rotation, for aspect grids ──────


def test_grid_azimuth_to_true_azimuth_is_the_exact_inverse_roundtrip():
    grid_north_az = 249.775141
    for true_az in (0.0, 45.0, 123.4, 210.0, 359.9):
        grid_az = true_azimuth_to_grid_azimuth(true_az, grid_north_az)
        assert grid_azimuth_to_true_azimuth(grid_az, grid_north_az) == pytest.approx(
            true_az
        )


def test_grid_azimuth_to_true_azimuth_wraps_past_zero():
    # A grid azimuth smaller than the offset must wrap around 360, not go
    # negative.
    assert grid_azimuth_to_true_azimuth(10.0, 20.0) == pytest.approx(350.0)


def test_grid_azimuth_to_true_azimuth_is_identity_on_central_meridian():
    for grid_az in (0.0, 45.0, 123.4, 359.9):
        assert grid_azimuth_to_true_azimuth(grid_az, 0.0) == pytest.approx(grid_az)


def test_grid_azimuth_to_true_azimuth_returns_a_python_float_for_scalar_input():
    out = grid_azimuth_to_true_azimuth(90.0, 249.775141)
    assert isinstance(out, float)


def test_grid_azimuth_to_true_azimuth_vectorises_over_an_aspect_grid():
    """The thermal path needs to rotate a whole (H, W) aspect grid in one
    call, unlike true_azimuth_to_grid_azimuth which only ever rotates
    individual sun samples."""
    grid_north_az = 249.775141
    aspect_grid = np.array([[0.0, 90.0], [180.0, 270.0]])
    out = grid_azimuth_to_true_azimuth(aspect_grid, grid_north_az)
    assert out.shape == aspect_grid.shape
    expected = np.mod(aspect_grid - grid_north_az, 360.0)
    assert np.allclose(out, expected)


# ── utc_to_et must furnish the kernel pool before converting ────────────────
#
# illumination_series.py's _spice_shadow_series once called spice.str2et
# BEFORE the first sun_vector_body -- the call that would otherwise have
# loaded the kernel pool. In a cold process the very first str2et raised
# SPICE(NOLEAPSECONDS); a broad `except Exception` turned that into "real
# illumination unavailable", a message that blamed missing kernels for what
# was actually an ordering mistake -- /api/plan-4d could never produce a
# time-varying series, not just on a cold start. The fix (app.ephemeris's
# utc_to_et, which every str2et call site now routes through) makes
# "furnish before you convert" a property of the API. This test proves that
# property holds without needing real NAIF kernels -- unlike
# test_l3_repeated_ephemeris_calls_do_not_refurnish_the_kernel above, it
# fakes spiceypy entirely, so it runs in the default suite on a fresh clone
# instead of skipping.


def test_utc_to_et_furnishes_the_kernel_pool_before_converting(monkeypatch):
    import spiceypy

    from app import ephemeris

    state = {"furnished": False}

    def _fake_furnsh(_path):
        state["furnished"] = True

    def _fake_ktotal(_category):
        return 1 if state["furnished"] else 0

    def _fake_str2et(_utc):
        if not state["furnished"]:
            # What a cold process actually raised before the fix.
            raise RuntimeError("SPICE(NOLEAPSECONDS): kernel pool not loaded")
        return 12345.0

    monkeypatch.setattr(spiceypy, "furnsh", _fake_furnsh)
    monkeypatch.setattr(spiceypy, "ktotal", _fake_ktotal)
    monkeypatch.setattr(spiceypy, "str2et", _fake_str2et)
    ephemeris._FURNISHED.clear()
    try:
        assert ephemeris.utc_to_et("2026-08-30T00:00:00") == 12345.0
        assert state["furnished"] is True
    finally:
        ephemeris._FURNISHED.clear()


def test_utc_to_et_without_the_fix_would_have_failed_cold(monkeypatch):
    """Documents the failure the fix prevents: calling the fake str2et
    directly, the way the pre-fix code did, raises on a cold pool."""
    import spiceypy

    def _fake_str2et(_utc):
        raise RuntimeError("SPICE(NOLEAPSECONDS): kernel pool not loaded")

    monkeypatch.setattr(spiceypy, "str2et", _fake_str2et)
    with pytest.raises(RuntimeError, match="NOLEAPSECONDS"):
        spiceypy.str2et("2026-08-30T00:00:00")


# ── body-parameterised ephemeris (A4: the Earth is the same call as the Sun) ─
#
# Direct-to-Earth visibility needs exactly the geometry the Sun already gets:
# spkpos in MOON_ME from the Moon, light-time corrected. The only thing that
# changes is the target name, so the target is a parameter and the two
# public helpers are one-line wrappers. Faked spiceypy, so this runs on a
# fresh clone with no kernels.


def _fake_spice(monkeypatch):
    import spiceypy

    from app import ephemeris

    calls: list[tuple] = []

    def _fake_spkpos(target, et, frame, abcorr, observer):
        calls.append((target, et, frame, abcorr, observer))
        return ([1.0, 2.0, 3.0], 0.0)

    monkeypatch.setattr(spiceypy, "furnsh", lambda _path: None)
    monkeypatch.setattr(spiceypy, "ktotal", lambda _category: 1)
    monkeypatch.setattr(spiceypy, "spkpos", _fake_spkpos)
    ephemeris._FURNISHED.clear()
    return ephemeris, calls


def test_earth_vector_body_queries_spice_for_the_earth(monkeypatch):
    ephemeris, calls = _fake_spice(monkeypatch)
    try:
        vec = ephemeris.earth_vector_body(123.0)
    finally:
        ephemeris._FURNISHED.clear()
    assert calls == [("EARTH", 123.0, "MOON_ME", "LT+S", "MOON")]
    np.testing.assert_allclose(vec, [1.0, 2.0, 3.0])


def test_sun_vector_body_still_queries_the_sun(monkeypatch):
    ephemeris, calls = _fake_spice(monkeypatch)
    try:
        ephemeris.sun_vector_body(456.0)
    finally:
        ephemeris._FURNISHED.clear()
    assert calls == [("SUN", 456.0, "MOON_ME", "LT+S", "MOON")]


def test_body_vector_body_takes_any_naif_target(monkeypatch):
    ephemeris, calls = _fake_spice(monkeypatch)
    try:
        ephemeris.body_vector_body("EARTH BARYCENTER", 7.0)
    finally:
        ephemeris._FURNISHED.clear()
    assert calls[0][0] == "EARTH BARYCENTER"


# ── CSPICE is not thread-safe, and this process shares one copy of it ───────
# FastAPI runs sync endpoints in a threadpool, so two requests reach
# app.ephemeris concurrently as a matter of course. CSPICE keeps its kernel
# database and its chkin_/chkout_ traceback stack in process globals, and two
# threads inside spkpos pop that stack against each other:
#
#     SPICE(BADSUBSCRIPT): Subscript out of range on file line 1189,
#     procedure "trcpkg". Attempt to access element 0 of variable "stack".
#     spkpos_c->SPKPOS->SPKEZP->FRINFO
#
# That is not catchable -- CSPICE's default error action ends the process, so
# a server does not degrade, it vanishes mid-request. Reproduced before the
# lock with 12 threads x 40 iterations; 3 600 calls across 20 threads pass
# with it.
#
# These tests assert the property that actually matters: the lock is HELD
# while CSPICE runs, not merely that some lock object exists. A second thread
# tries to take it from inside the fake spice call -- succeeding there would
# mean a real second thread could have been inside CSPICE at the same moment.


def _lock_is_held_by_another_thread(ephemeris) -> bool:
    """True when this thread cannot be joined inside the lock by another."""
    import threading

    taken: list[bool] = []

    def _try_acquire() -> None:
        got = ephemeris.spice_lock().acquire(timeout=0.25)
        taken.append(got)
        if got:
            ephemeris.spice_lock().release()

    probe = threading.Thread(target=_try_acquire)
    probe.start()
    probe.join(timeout=5.0)
    return taken == [False]


def test_body_vector_body_holds_the_spice_lock_while_cspice_runs(monkeypatch):
    import spiceypy

    from app import ephemeris

    held: list[bool] = []

    def _fake_spkpos(_target, _et, _frame, _abcorr, _observer):
        held.append(_lock_is_held_by_another_thread(ephemeris))
        return ([1.0, 2.0, 3.0], 0.0)

    monkeypatch.setattr(spiceypy, "furnsh", lambda _path: None)
    monkeypatch.setattr(spiceypy, "ktotal", lambda _category: 1)
    monkeypatch.setattr(spiceypy, "spkpos", _fake_spkpos)
    ephemeris._FURNISHED.clear()
    try:
        ephemeris.body_vector_body("SUN", 1.0)
    finally:
        ephemeris._FURNISHED.clear()
    assert held == [True]


def test_utc_to_et_holds_the_spice_lock_while_cspice_runs(monkeypatch):
    import spiceypy

    from app import ephemeris

    held: list[bool] = []

    def _fake_str2et(_utc):
        held.append(_lock_is_held_by_another_thread(ephemeris))
        return 12345.0

    monkeypatch.setattr(spiceypy, "furnsh", lambda _path: None)
    monkeypatch.setattr(spiceypy, "ktotal", lambda _category: 1)
    monkeypatch.setattr(spiceypy, "str2et", _fake_str2et)
    ephemeris._FURNISHED.clear()
    try:
        ephemeris.utc_to_et("2027-05-30T00:00:00")
    finally:
        ephemeris._FURNISHED.clear()
    assert held == [True]


def test_the_spice_lock_is_reentrant(monkeypatch):
    """sun_track holds the lock and then calls sun_vector_body, which takes
    it again. A plain Lock would deadlock on the first Sun track ever asked
    for, so the type is part of the contract, not an implementation detail."""
    from app import ephemeris

    lock = ephemeris.spice_lock()
    with lock:
        assert lock.acquire(blocking=False) is True
        lock.release()
