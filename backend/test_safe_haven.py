"""Safe Haven (A1): VIPER's rule on synthetic grids.

Everything here runs without NAIF kernels -- the Sun and the Earth are
scripted the way test_earth_visibility.py scripts them -- so the counting
rule, the mask, the time-to-safe-haven graph and the Earthset deadline are
pinned on arrays a reader can check by hand. The real-grid behaviour lives
in test_safe_haven_real_grid.py.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.constants import get_rover

STEP_H = 2.0


# ── Task 1: the counting rule ─────────────────────────────────────────────────


def test_dark_hours_are_counted_only_while_the_earth_is_below_the_horizon():
    """One cell, six 2 h steps.

    step:          0    1    2    3    4    5
    sun_visible:   F    F    F    T    F    F
    earth_visible: F    F    T    T    F    F

    Steps 0-1 are dark with no link (4 h). Step 2 is dark but the Earth is
    up -- the rover could be commanded away, so the run RESETS. Step 3 is
    lit. Steps 4-5 are dark with no link again (4 h). Longest run: 4 h.
    """
    from app.safe_haven import max_dark_hours_without_dte

    sun = np.array([[[False]], [[False]], [[False]], [[True]], [[False]], [[False]]])
    earth = np.array([[[False]], [[False]], [[True]], [[True]], [[False]], [[False]]])

    hours = max_dark_hours_without_dte(sun, earth, STEP_H)

    assert hours.shape == (1, 1)
    assert hours[0, 0] == pytest.approx(4.0)


def test_a_cell_dark_and_unlinked_throughout_accrues_the_whole_window():
    from app.safe_haven import max_dark_hours_without_dte

    sun = np.zeros((6, 1, 1), dtype=bool)
    earth = np.zeros((6, 1, 1), dtype=bool)
    assert max_dark_hours_without_dte(sun, earth, STEP_H)[0, 0] == pytest.approx(12.0)


def test_a_cell_that_is_lit_or_linked_at_every_step_accrues_nothing():
    from app.safe_haven import max_dark_hours_without_dte

    always_lit = np.ones((6, 1, 2), dtype=bool)
    never_linked = np.zeros((6, 1, 2), dtype=bool)
    assert max_dark_hours_without_dte(always_lit, never_linked, STEP_H).tolist() == [[0.0, 0.0]]

    always_dark = np.zeros((6, 1, 2), dtype=bool)
    always_linked = np.ones((6, 1, 2), dtype=bool)
    assert max_dark_hours_without_dte(always_dark, always_linked, STEP_H).tolist() == [[0.0, 0.0]]


def test_counting_rule_refuses_mismatched_series():
    from app.safe_haven import max_dark_hours_without_dte

    with pytest.raises(ValueError):
        max_dark_hours_without_dte(np.zeros((3, 2, 2), bool), np.zeros((3, 2, 3), bool), STEP_H)
    with pytest.raises(ValueError):
        max_dark_hours_without_dte(np.zeros((3, 2, 2), bool), np.zeros((3, 2, 2), bool), 0.0)


# ── Task 1: the mask ──────────────────────────────────────────────────────────


def test_safe_haven_mask_applies_the_endurance_the_lit_clause_and_traversability():
    """Four cells: 0 h dark, 40 h dark, 60 h dark, and a permanently dark
    cell whose no-link period happened to be short. At LPR-1's 50 h only
    the first two qualify -- the last one never generates power."""
    from app.safe_haven import safe_haven_mask

    max_dark = np.array([[0.0, 40.0, 60.0, 0.0]])
    ever_lit = np.array([[True, True, True, False]])
    traversable = np.array([[True, True, True, True]])

    mask = safe_haven_mask(max_dark, ever_lit, traversable, h_max_shadow_h=50.0)

    assert mask.dtype == bool
    assert mask.tolist() == [[True, True, False, False]]


def test_safe_haven_mask_excludes_cells_the_rover_cannot_park_on():
    from app.safe_haven import safe_haven_mask

    max_dark = np.zeros((1, 3))
    ever_lit = np.ones((1, 3), dtype=bool)
    traversable = np.array([[True, False, True]])
    assert safe_haven_mask(max_dark, ever_lit, traversable, 50.0).tolist() == [[True, False, True]]


def test_safe_haven_set_shrinks_with_a_shorter_endurance():
    """The same site under LUVMI-M's 4 h endurance keeps only the cells
    that never sit dark without a link -- the research doc's demo."""
    from app.safe_haven import safe_haven_mask

    max_dark = np.array([[0.0, 3.0, 40.0, 90.0]])
    ever_lit = np.ones((1, 4), dtype=bool)
    traversable = np.ones((1, 4), dtype=bool)

    lpr_1 = safe_haven_mask(max_dark, ever_lit, traversable, float(get_rover("lpr_1")["h_max_shadow_h"]))
    viper = safe_haven_mask(max_dark, ever_lit, traversable, float(get_rover("nasa_viper")["h_max_shadow_h"]))
    luvmi = safe_haven_mask(max_dark, ever_lit, traversable, float(get_rover("luvmi_m")["h_max_shadow_h"]))

    assert viper.sum() >= lpr_1.sum() >= luvmi.sum()
    assert lpr_1.tolist() == [[True, True, True, False]]
    assert luvmi.tolist() == [[True, True, False, False]]


# ── Task 2: time-to-safe-haven, in hours, over the planners' gated graph ─────

RES_M = 80.0


def _flat_hours(distance_m: float, slope_deg: float = 0.0) -> float:
    from app.cost_engine import edge_travel_time_s

    return edge_travel_time_s(slope_deg, distance_m, get_rover()) / 3600.0


def test_time_to_haven_along_a_flat_corridor_is_the_summed_edge_time():
    from app.safe_haven import time_to_safe_haven_hours

    safe = np.array([[True, False, False, False, False]])
    passable = np.ones((1, 5), dtype=bool)
    elevation = np.zeros((1, 5))
    slope = np.zeros((1, 5))

    tts = time_to_safe_haven_hours(safe, passable, elevation, slope, RES_M, get_rover())

    step = _flat_hours(RES_M)
    assert tts.shape == (1, 5)
    assert tts[0].tolist() == pytest.approx([0.0, step, 2 * step, 3 * step, 4 * step])


def test_time_to_haven_uses_the_trapezoidal_edge_slope_the_planner_uses():
    """astar_4d prices a MOVE at the mean of the two cell slopes; the
    distance to a haven must be measured with the same rule or the
    deadline check compares two different clocks."""
    from app.safe_haven import time_to_safe_haven_hours

    safe = np.array([[True, False, False]])
    passable = np.ones((1, 3), dtype=bool)
    elevation = np.zeros((1, 3))
    slope = np.array([[0.0, 10.0, 20.0]])

    tts = time_to_safe_haven_hours(safe, passable, elevation, slope, RES_M, get_rover())

    assert tts[0, 1] == pytest.approx(_flat_hours(RES_M, 5.0))
    assert tts[0, 2] == pytest.approx(_flat_hours(RES_M, 5.0) + _flat_hours(RES_M, 15.0))


def test_cells_behind_a_wall_cannot_reach_a_haven():
    from app.safe_haven import time_to_safe_haven_hours

    safe = np.array([[True, False, False, False, False]])
    passable = np.array([[True, True, False, True, True]])
    elevation = np.zeros((1, 5))
    slope = np.zeros((1, 5))

    tts = time_to_safe_haven_hours(safe, passable, elevation, slope, RES_M, get_rover())

    assert np.isfinite(tts[0, :2]).all()
    assert np.isinf(tts[0, 2])  # impassable itself
    assert np.isinf(tts[0, 3:]).all()


def test_a_step_too_steep_to_drive_closes_the_way_to_a_haven():
    """The along-track gate: an 80 m step with a 50 m rise is 32 deg,
    over LPR-1's 25 deg limit, so the haven behind it is unreachable
    however passable the cells are."""
    from app.safe_haven import time_to_safe_haven_hours

    safe = np.array([[True, False, False]])
    passable = np.ones((1, 3), dtype=bool)
    elevation = np.array([[0.0, 0.0, 50.0]])
    slope = np.zeros((1, 3))

    tts = time_to_safe_haven_hours(safe, passable, elevation, slope, RES_M, get_rover())

    assert np.isfinite(tts[0, 1])
    assert np.isinf(tts[0, 2])


def test_a_diagonal_step_costs_root_two_and_may_not_cut_a_corner():
    from app.safe_haven import time_to_safe_haven_hours

    safe = np.array([[True, False], [False, False]])
    passable = np.array([[True, False], [False, True]])
    elevation = np.zeros((2, 2))
    slope = np.zeros((2, 2))

    blocked = time_to_safe_haven_hours(safe, passable, elevation, slope, RES_M, get_rover())
    assert np.isinf(blocked[1, 1]), "diagonal between two blocked cells is a corner cut"

    passable = np.ones((2, 2), dtype=bool)
    open_ = time_to_safe_haven_hours(safe, passable, elevation, slope, RES_M, get_rover())
    assert open_[1, 1] == pytest.approx(_flat_hours(RES_M * math.sqrt(2.0)))


def test_no_haven_anywhere_means_every_cell_is_infinitely_far():
    from app.safe_haven import time_to_safe_haven_hours

    safe = np.zeros((2, 2), dtype=bool)
    tts = time_to_safe_haven_hours(
        safe, np.ones((2, 2), bool), np.zeros((2, 2)), np.zeros((2, 2)), RES_M, get_rover()
    )
    assert np.isinf(tts).all()


def test_finite_time_to_haven_agrees_with_the_planner_reachability_on_a_random_grid():
    """The set of cells with a finite time-to-haven must be exactly the set
    from which gated_move_count reaches some haven: same cells, same edge
    gates, same corner rule. Any difference means the deadline check and
    the planner disagree about the graph."""
    from app.pathfinder_4d import gated_move_count
    from app.safe_haven import time_to_safe_haven_hours

    rng = np.random.default_rng(7)
    shape = (9, 9)
    passable = rng.random(shape) > 0.25
    elevation = rng.normal(0.0, 12.0, size=shape)
    grad_r, grad_c = np.gradient(elevation, RES_M)
    slope = np.degrees(np.arctan(np.hypot(grad_r, grad_c)))
    safe = np.zeros(shape, dtype=bool)
    for cell in [(0, 0), (4, 4), (8, 8)]:
        safe[cell] = True
    safe &= passable
    rover = get_rover()

    tts = time_to_safe_haven_hours(safe, passable, elevation, slope, RES_M, rover)

    havens = [tuple(int(v) for v in cell) for cell in np.argwhere(safe)]
    assert havens, "fixture needs at least one passable haven"
    for row in range(shape[0]):
        for col in range(shape[1]):
            reachable = any(
                gated_move_count(passable, (row, col), haven, elevation, RES_M, rover) is not None
                for haven in havens
            )
            assert np.isfinite(tts[row, col]) == reachable, (row, col)


# ── Task 3: the Earthset deadline and the map builder ────────────────────────

from test_earth_visibility import _metadata, _script_ephemeris  # noqa: E402

N_AZ = 8
MAP_SHAPE = (2, 3)


def test_hours_until_earthset_counts_to_the_first_unlinked_slice():
    """Cell A: linked, linked, UNLINKED, linked, linked at 2 h slices.
    Cell B: linked throughout. Without a lookahead the run to the end of
    the horizon is open-ended (inf); with one, the hours after the last
    slice are added on."""
    from app.safe_haven import hours_until_earthset_cube

    earth = np.array(
        [[[True, True]], [[True, True]], [[False, True]], [[True, True]], [[True, True]]]
    )

    open_ended = hours_until_earthset_cube(earth, 2.0)
    assert open_ended.shape == (5, 1, 2)
    assert open_ended[:, 0, 0].tolist()[:3] == pytest.approx([4.0, 2.0, 0.0])
    assert np.isinf(open_ended[3:, 0, 0]).all()
    assert np.isinf(open_ended[:, 0, 1]).all()

    after_end = np.array([[6.0, 10.0]])
    closed = hours_until_earthset_cube(earth, 2.0, after_end_h=after_end)
    assert closed[:, 0, 0].tolist() == pytest.approx([4.0, 2.0, 0.0, 8.0, 6.0])
    assert closed[:, 0, 1].tolist() == pytest.approx([18.0, 16.0, 14.0, 12.0, 10.0])

    never = hours_until_earthset_cube(earth, 2.0, after_end_h=np.full((1, 2), np.inf))
    assert np.isinf(never[3:, 0, 0]).all()


def _map_horizon() -> np.ndarray:
    """Three columns toward grid East (bin 2 of 8): flat (0 deg), a 4 deg
    ridge, and a -30 deg drop-off that sees everything."""
    horizon = np.zeros((N_AZ, *MAP_SHAPE), dtype=np.float32)
    horizon[2, :, 1] = 4.0
    horizon[2, :, 2] = -30.0
    return horizon


def test_earthset_after_horizon_finds_the_next_loss_of_link_per_cell(monkeypatch):
    """Earth due East, sinking 1 deg/h from +5.25 deg at the horizon's end.
    The flat column loses it once the Earth is below 0 (first 1 h sample:
    6 h), the ridge once below 4 deg (2 h), and the drop-off not within a
    24 h lookahead."""
    from app.safe_haven import earthset_after_horizon_hours

    metadata = _metadata()
    metadata["shape"] = list(MAP_SHAPE)
    _script_ephemeris(monkeypatch, metadata, lambda h: (90.0, 5.25 - h))

    after = earthset_after_horizon_hours(
        _map_horizon(), metadata, "2026-09-01T00:00:00", lookahead_hours=24.0, step_hours=1.0
    )

    assert after.shape == MAP_SHAPE
    assert after[:, 0].tolist() == pytest.approx([6.0, 6.0])
    assert after[:, 1].tolist() == pytest.approx([2.0, 2.0])
    assert np.isinf(after[:, 2]).all()


def _scripted_month(monkeypatch, metadata):
    """400 h: the Earth is up (+5 deg) for the first 100 h, down (-5 deg)
    until 300 h, then up again. The Sun alternates 20 h lit (+3 deg) and
    20 h dark (-10 deg), due East."""

    def earth(h):
        return (90.0, 5.0 if (h < 100.0 or h >= 300.0) else -5.0)

    def sun(h):
        return (90.0, 3.0 if (int(h // 20) % 2 == 0) else -10.0)

    _script_ephemeris(monkeypatch, metadata, earth, sun)


def test_build_safe_haven_map_applies_the_rule_per_cell_and_per_rover(monkeypatch):
    """Flat column: dark 20 h at a time -> haven for LPR-1 (50 h), not for
    LUVMI-M (4 h). Ridge column: the Sun never clears 4 deg, so it is never
    lit and never a haven (200 h dark with no link). Drop-off column: always
    lit and always linked -> haven for everyone. Row 1 of the flat column
    is impassable."""
    from app.safe_haven import build_safe_haven_map

    metadata = _metadata()
    metadata["shape"] = list(MAP_SHAPE)
    _scripted_month(monkeypatch, metadata)
    traversable = np.ones(MAP_SHAPE, dtype=bool)
    traversable[1, 0] = False

    layers, info = build_safe_haven_map(
        _map_horizon(), metadata, traversable, get_rover("lpr_1"),
        "2026-09-01T00:00:00", span_hours=400.0, step_hours=2.0,
    )

    assert layers["safe_haven"].tolist() == [[True, False, True], [False, False, True]]
    assert layers["max_dark_hours_without_dte"][:, 0].tolist() == pytest.approx([20.0, 20.0])
    assert layers["max_dark_hours_without_dte"][:, 1].tolist() == pytest.approx([200.0, 200.0])
    assert layers["max_dark_hours_without_dte"][:, 2].tolist() == pytest.approx([0.0, 0.0])
    assert layers["earth_below_hours"][0].tolist() == pytest.approx([200.0, 200.0, 0.0])
    assert layers["ever_lit"].tolist() == [[True, False, True], [True, False, True]]

    assert info["model"] == "spice_horizon"
    assert info["n_steps"] == 200
    assert info["step_hours"] == 2.0
    assert info["span_hours"] == 400.0
    assert info["h_max_shadow_h"] == 50.0
    assert info["rover_id"] == "lpr_1"
    assert info["safe_haven_cells"] == 3
    assert info["traversable_cells"] == 5
    assert info["safe_haven_fraction"] == pytest.approx(3 / 5)
    assert info["earth_below_fraction"] == pytest.approx((4 * 0.5) / 6)

    luvmi, _ = build_safe_haven_map(
        _map_horizon(), metadata, traversable, get_rover("luvmi_m"),
        "2026-09-01T00:00:00", span_hours=400.0, step_hours=2.0,
    )
    assert luvmi["safe_haven"].tolist() == [[False, False, True], [False, False, True]]


def _grids(processed_dir=None) -> dict:
    metadata = _metadata(processed_dir)
    metadata["shape"] = list(MAP_SHAPE)
    return {
        "elevation": np.zeros(MAP_SHAPE),
        "slope": np.full(MAP_SHAPE, 3.0),
        "thermal": np.full(MAP_SHAPE, -60.0),
        "shadow_ratio": np.full(MAP_SHAPE, 0.3),
        "traversable": np.ones(MAP_SHAPE, dtype=bool),
        "metadata": metadata,
    }


def test_safe_haven_for_grids_is_unavailable_without_a_horizon_or_an_epoch(tmp_path):
    from app.safe_haven import clear_safe_haven_cache, safe_haven_for_grids

    clear_safe_haven_cache()
    layers, tts, info = safe_haven_for_grids(_grids(), "lpr_1", "2026-09-01T00:00:00")
    assert layers is None and tts is None
    assert info["model"] == "unavailable"
    assert "horizon_map.npy" in info["reason"]

    np.save(tmp_path / "horizon_map.npy", _map_horizon())
    layers, tts, info = safe_haven_for_grids(_grids(tmp_path), "lpr_1", None)
    assert layers is None
    assert info["model"] == "unavailable"
    assert "epoch" in info["reason"]


def test_safe_haven_for_grids_builds_the_map_and_the_distance_and_caches_them(
    monkeypatch, tmp_path
):
    from app.safe_haven import clear_safe_haven_cache, safe_haven_for_grids

    clear_safe_haven_cache()
    np.save(tmp_path / "horizon_map.npy", _map_horizon())
    grids = _grids(tmp_path)
    _scripted_month(monkeypatch, grids["metadata"])

    layers, tts, info = safe_haven_for_grids(
        grids, "lpr_1", "2026-09-01T00:00:00", span_hours=400.0, step_hours=2.0
    )

    assert info["model"] == "spice_horizon"
    assert layers["safe_haven"].tolist() == [[True, False, True], [True, False, True]]
    assert tts.shape == MAP_SHAPE
    assert tts[0, 0] == 0.0 and tts[0, 2] == 0.0
    assert 0.0 < tts[0, 1] < np.inf

    again = safe_haven_for_grids(
        grids, "lpr_1", "2026-09-01T00:00:00", span_hours=400.0, step_hours=2.0
    )
    assert again[0] is layers and again[1] is tts

    other, _, _ = safe_haven_for_grids(
        grids, "luvmi_m", "2026-09-01T00:00:00", span_hours=400.0, step_hours=2.0
    )
    assert other is not layers
    assert other["safe_haven"].sum() < layers["safe_haven"].sum()


# ── Task 5: SHERPA's margin metrics along a route ────────────────────────────


def test_route_margins_report_sherpa_time_to_shadow_dsn_and_zero_soc():
    """Three states along a 1x3 corridor at 1 h slices.

    shadow (t, cell):   t0 [0 0 1]  t1 [0 0 1]  t2 [1 0 1]  t3 [1 0 1]
    state (0,0,0): lit now, dark from t2 -> 2 h to shadow
    state (0,1,1): lit through the horizon -> open-ended, not counted
    state (0,2,2): dark now -> 0 h
    """
    from app.safe_haven import route_margins

    states = [(0, 0, 0), (0, 1, 1), (0, 2, 2)]
    shadow = np.array(
        [[[0.0, 0.0, 1.0]], [[0.0, 0.0, 1.0]], [[1.0, 0.0, 1.0]], [[1.0, 0.0, 1.0]]]
    )
    earthset = np.full((4, 1, 3), np.inf)
    earthset[0, 0, 0] = 10.0
    earthset[1, 0, 1] = 5.0
    batteries = [5420.0, 2000.0, 1000.0]
    rover = get_rover("lpr_1")

    margins = route_margins(states, batteries, shadow, earthset, 1.0, rover)

    assert margins["time_to_sun_shadow_min_h"] == pytest.approx(0.0)
    assert margins["time_to_sun_shadow_mean_h"] == pytest.approx(1.0)
    assert margins["time_to_dsn_shadow_min_h"] == pytest.approx(5.0)
    # Holding still in full shadow: housekeeping is p_shadow_w (65 W).
    assert margins["time_to_zero_soc_min_h"] == pytest.approx(1000.0 / 65.0, abs=1e-4)


def test_route_margins_say_none_when_a_margin_is_open_ended_or_unknown():
    from app.safe_haven import route_margins

    states = [(0, 0, 0), (0, 1, 1)]
    lit = np.zeros((3, 1, 2))
    margins = route_margins(states, None, lit, None, 1.0, get_rover("lpr_1"))
    assert margins["time_to_sun_shadow_min_h"] is None
    assert margins["time_to_sun_shadow_mean_h"] is None
    assert margins["time_to_dsn_shadow_min_h"] is None
    assert margins["time_to_zero_soc_min_h"] is None

    without_shadow = route_margins(states, [100.0, 50.0], None, None, 1.0, get_rover("lpr_1"))
    assert without_shadow["time_to_sun_shadow_min_h"] is None
    assert without_shadow["time_to_zero_soc_min_h"] == pytest.approx(50.0 / 65.0, abs=1e-4)


# ── Task 6 helper: block-min coarsening of the Earthset lookahead ────────────


def test_block_min_takes_the_earliest_earthset_in_each_block():
    """A coarse block loses its link when ANY fine cell in it does -- the
    same conservative direction as coarsen_traversable's AND."""
    from app.safe_haven import block_min

    fine = np.array(
        [[10.0, 2.0, np.inf, np.inf], [8.0, 9.0, np.inf, 5.0]]
    )
    coarse = block_min(fine, 2)
    assert coarse.tolist() == [[2.0, 5.0]]
    assert block_min(fine, 1) is not None and block_min(fine, 1).shape == fine.shape
    with pytest.raises(ValueError):
        block_min(fine, 3)
