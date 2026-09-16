"""D6, the sweep itself: exactness, fidelity to the planner, and the bands.

These run on hand-built grids so every number is checkable by hand. The two
properties the feature's whole claim rests on are tested against BRUTE FORCE
rather than against themselves:

* exactness -- the forward sweep's maximum charge and minimum darkness at
  every ``(slice, block)`` equal what an exhaustive enumeration of every
  label sequence finds;
* containment -- every block ``astar_4d`` can actually route to is in the
  sweep's live set.

``test_reachability_real_grid.py`` repeats the containment check on Site11.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.constants import get_rover
from app.cost_cube import build_cost_cube, build_wait_cost_cube
from app.cost_engine import (
    edge_travel_time_s,
    housekeeping_power_w,
    move_battery_drain_wh,
    wait_battery_drain_wh,
)
from app.pathfinder_4d import _DARK_RATIO_THRESHOLD, _OFFSETS as PLANNER_OFFSETS, astar_4d
from app.reachability import (
    DARK_RATIO_THRESHOLD,
    DEFAULT_BAND_COUNT,
    ENDURANCE_SLACK_H,
    HOLD_LIMIT_CODES,
    MAX_REACHABLE_GROUP_STEPS,
    PLANNER_CONFIGURATION,
    REACHABILITY_CORRECTIONS,
    REACHABILITY_QUOTED,
    REACHABILITY_REFERENCES,
    band_boundary_cells,
    coarse_shadow_cube,
    compare_fields,
    default_band_edges,
    default_hold_horizon_hours,
    edge_group_count,
    hold_limit,
    hold_times,
    isochrone_bands,
    shift_epoch,
    sweep,
)
from app.survival import OFFSETS as SURVIVAL_OFFSETS, direction_tables

ROVER = get_rover("lpr_1")
RES_M = 20.0


def flat_grid(height: int = 6, width: int = 6, slope_deg: float = 3.0):
    traversable = np.ones((height, width), dtype=bool)
    elevation = np.zeros((height, width), dtype=np.float64)
    slope = np.full((height, width), slope_deg, dtype=np.float64)
    return traversable, elevation, slope


def dark_cube(n_slices: int, shape: tuple[int, int], value: float = 1.0) -> np.ndarray:
    return np.full((n_slices, *shape), float(value), dtype=np.float64)


# ── the constants this module borrows ────────────────────────────────────────


def test_dark_threshold_matches_the_planner():
    # Repeated by value rather than imported so the module has no import-time
    # dependency on the planner; this is the assertion that keeps them equal.
    assert DARK_RATIO_THRESHOLD == _DARK_RATIO_THRESHOLD


def test_offsets_match_the_planner_move_order():
    assert SURVIVAL_OFFSETS == PLANNER_OFFSETS


def test_endurance_slack_matches_the_planner_literal():
    # pathfinder_4d.envelope_after refuses only above endurance + 1e-9. A
    # sweep without the same slack would kill a hairline state the planner
    # keeps, and the published negative claim would be false there.
    assert ENDURANCE_SLACK_H == 1e-9


def test_planner_configuration_names_every_capability_switch():
    # The containment claim is stated against this configuration, so a new
    # capability added to Plan4DRequest without being named here would
    # silently widen what the claim is supposed to cover.
    for key in ("allow_hibernate", "battery_model", "heater_power_model", "panel_model"):
        assert key in PLANNER_CONFIGURATION


# ── the drain arithmetic ─────────────────────────────────────────────────────


def _planner_move_drain(edge_slope: float, distance_m: float, e_dep: float, e_arr: float) -> float:
    """astar_4d's inlined move drain, replayed scalar for scalar.

    NOT ``cost_engine.move_battery_drain_wh``: the two are algebraically the
    same and not equal in IEEE-754 (that one routes the draw through
    ``gross_energy_per_metre_wh``, i.e. per-metre time times distance, and
    subtracts the solar term after multiplying rather than before). The
    planner's expression is the reference here because the planner is what
    D6 claims to contain.
    """
    p_base_w = float(ROVER["p_base_w"])
    mu_coeff = float(ROVER["mu_coeff"])
    p_idle_w = float(ROVER["p_idle_w"])
    shadow_extra_w = max(0.0, float(ROVER["p_shadow_w"]) - p_idle_w)
    p_solar_w = float(ROVER["p_solar_w"])
    travel_h = edge_travel_time_s(edge_slope, distance_m, ROVER) / 3600.0
    traction_w = p_base_w * (1.0 + mu_coeff * math.sin(math.radians(max(0.0, edge_slope))))
    mean_exposure = 0.5 * (e_dep + e_arr)
    return (
        traction_w
        + (p_idle_w + mean_exposure * shadow_extra_w)
        - p_solar_w * (1.0 - mean_exposure)
    ) * travel_h


def test_sweep_move_drain_is_bit_equal_to_the_planner_expression():
    """One dark step, one lit step: the charge the sweep lands on is exactly
    the charge the planner's own arithmetic produces."""
    traversable, elevation, slope = flat_grid(3, 3, slope_deg=0.0)
    e_cap = float(ROVER["e_cap_wh"])
    for exposure in (0.0, 0.25, 0.5, 1.0):
        shadow = dark_cube(4, (3, 3), exposure)
        field = sweep(
            traversable, elevation, slope, RES_M, ROVER, shadow, 1.0, (1, 1), 1.0
        )
        expected = min(
            e_cap, e_cap - _planner_move_drain(0.0, RES_M, exposure, exposure)
        )
        # A cardinal neighbour of the start, reached in exactly one slice.
        assert field.first_slice[1, 2] == 1
        assert field.soc_at_first_wh[1, 2] == expected


def test_wait_drain_matches_cost_engine_exactly():
    """The wait edge is ``wait_battery_drain_wh`` term for term."""
    p_idle_w = float(ROVER["p_idle_w"])
    extra = max(0.0, float(ROVER["p_shadow_w"]) - p_idle_w)
    p_solar_w = float(ROVER["p_solar_w"])
    for exposure in (0.0, 0.3, 0.5, 1.0):
        mine = (p_idle_w + exposure * extra - p_solar_w * (1.0 - exposure)) * 1.0
        assert mine == wait_battery_drain_wh(exposure, 1.0, ROVER)
        assert housekeeping_power_w(exposure, ROVER) == p_idle_w + exposure * extra


def test_move_battery_drain_wh_is_the_same_model_but_not_the_same_float():
    """Why the sweep inlines rather than calling cost_engine.

    The two agree to well inside a milliwatt-hour and disagree in the last
    bits; D6 claims to contain the PLANNER, so it copies the planner.
    """
    mine = _planner_move_drain(8.0, RES_M, 1.0, 1.0)
    theirs = move_battery_drain_wh(8.0, RES_M, 1.0, ROVER)
    assert mine == pytest.approx(theirs, rel=1e-9)


# ── exactness, against brute force ───────────────────────────────────────────


def _brute_force(traversable, elevation, slope, shadow, slice_hours, start, soc_frac):
    """Every label sequence, enumerated. ``(best_soc, min_dark)`` per state."""
    tables = direction_tables(traversable, elevation, slope, RES_M, ROVER)
    n_slices, height, width = shadow.shape
    e_cap = float(ROVER["e_cap_wh"])
    reserve = e_cap * float(ROVER["soc_min_pct"])
    endurance = float(ROVER["h_max_shadow_h"])
    p_idle_w = float(ROVER["p_idle_w"])
    extra = max(0.0, float(ROVER["p_shadow_w"]) - p_idle_w)
    p_solar_w = float(ROVER["p_solar_w"])

    best = {}
    seen: set = set()
    stack = [(0, start[0], start[1], soc_frac * e_cap, 0.0)]
    while stack:
        t, r, c, soc, dark = stack.pop()
        key = (t, r, c, round(soc, 9), round(dark, 9))
        if key in seen:
            continue
        seen.add(key)
        prev = best.get((t, r, c))
        best[(t, r, c)] = (
            (soc, dark) if prev is None else (max(prev[0], soc), min(prev[1], dark))
        )
        if t + 1 >= n_slices:
            continue
        exposure = float(shadow[t, r, c])
        drain = (p_idle_w + exposure * extra - p_solar_w * (1.0 - exposure)) * slice_hours
        new_soc = min(e_cap, soc - drain)
        new_dark = dark + slice_hours * exposure if exposure >= 0.5 else 0.0
        if new_soc >= reserve and new_dark <= endurance + 1e-9:
            stack.append((t + 1, r, c, new_soc, new_dark))
        for d, (d_row, d_col, _diag) in enumerate(SURVIVAL_OFFSETS):
            nr, nc = r + d_row, c + d_col
            if not (0 <= nr < height and 0 <= nc < width):
                continue
            if not tables.allowed[d, r, c]:
                continue
            travel_h = float(tables.travel_h[d, r, c])
            span = max(1, int(math.ceil(travel_h / slice_hours)))
            arrival = t + span
            if arrival >= n_slices:
                continue
            e_dep = float(shadow[t, r, c])
            e_arr = float(shadow[arrival, nr, nc])
            mean_exposure = 0.5 * (e_dep + e_arr)
            drain = (
                float(tables.traction_w[d, r, c])
                + (p_idle_w + mean_exposure * extra)
                - p_solar_w * (1.0 - mean_exposure)
            ) * travel_h
            new_soc = min(e_cap, soc - drain)
            new_dark = dark + travel_h * e_arr if e_arr >= 0.5 else 0.0
            if new_soc >= reserve and new_dark <= endurance + 1e-9:
                stack.append((arrival, nr, nc, new_soc, new_dark))
    return best


def test_sweep_is_exact_against_brute_force():
    """The per-field optima really are optima.

    Small enough to enumerate, dark enough that the battery moves, and long
    enough that a wait competes with a drive.
    """
    traversable, elevation, slope = flat_grid(4, 4, slope_deg=2.0)
    shadow = np.zeros((6, 4, 4), dtype=np.float64)
    shadow[:, :, 2:] = 1.0
    shadow[3:, 0, :] = 1.0
    field = sweep(traversable, elevation, slope, RES_M, ROVER, shadow, 1.0, (0, 0), 1.0)
    truth = _brute_force(traversable, elevation, slope, shadow, 1.0, (0, 0), 1.0)

    reached = {(r, c) for (_t, r, c) in truth}
    for row in range(4):
        for col in range(4):
            assert field.reachable[row, col] == ((row, col) in reached)
            if (row, col) not in reached:
                continue
            first = min(t for (t, r, c) in truth if (r, c) == (row, col))
            assert field.first_slice[row, col] == first
            soc, dark = truth[(first, row, col)]
            assert field.soc_at_first_wh[row, col] == pytest.approx(soc, abs=1e-9)
            assert field.dark_at_first_h[row, col] == pytest.approx(dark, abs=1e-12)
            best = max(s for (t, r, c), (s, _d) in truth.items() if (r, c) == (row, col))
            assert field.best_soc_wh[row, col] == pytest.approx(best, abs=1e-9)


# ── containment, against the planner ─────────────────────────────────────────


def _plan_to(goal, traversable, elevation, slope, shadow, slice_hours, start, soc_frac):
    grids = {
        "metadata": {"shape": list(traversable.shape), "resolution_m": RES_M},
        "traversable": traversable,
        "slope": slope,
        "elevation": elevation,
        "shadow_ratio": shadow[0],
        "thermal": np.zeros_like(slope),
    }
    series = [shadow[index] for index in range(shadow.shape[0])]
    cost = build_cost_cube(grids, series, ROVER, None, coarsen=1)
    wait = build_wait_cost_cube([1.0 - snap for snap in series], ROVER, slice_hours, None, coarsen=1)
    return astar_4d(
        cost,
        wait,
        traversable,
        start,
        goal,
        RES_M,
        slice_hours,
        ROVER,
        slope_grid=slope,
        elevation_grid=elevation,
        shadow_cube=shadow,
        initial_soc_frac=soc_frac,
    )


def test_live_set_contains_every_block_the_planner_can_route_to():
    """The direction the published claim runs in.

    A block the planner reaches must be in the set; a block outside the set
    is one the planner cannot reach. The reverse is NOT asserted -- the set
    is a relaxation and may be strictly larger, which is the whole reason the
    claim is stated negatively.
    """
    traversable, elevation, slope = flat_grid(5, 5, slope_deg=2.0)
    shadow = np.zeros((8, 5, 5), dtype=np.float64)
    shadow[:, :, 3:] = 1.0
    field = sweep(traversable, elevation, slope, RES_M, ROVER, shadow, 1.0, (0, 0), 0.30)
    planned = 0
    for row in range(5):
        for col in range(5):
            if (row, col) == (0, 0):
                continue
            result = _plan_to(
                (row, col), traversable, elevation, slope, shadow, 1.0, (0, 0), 0.30
            )
            if result.get("path_states"):
                planned += 1
                assert field.reachable[row, col], (
                    f"planner routes to {(row, col)} but the sweep calls it unreachable"
                )
    assert planned > 0, "the fixture must let the planner reach something"


# ── the refusal counters ─────────────────────────────────────────────────────


def test_refusals_report_which_rule_bound_the_frontier():
    """A short horizon on a full battery is a distance transform, and the
    response has to be able to say so."""
    traversable, elevation, slope = flat_grid(8, 8, slope_deg=1.0)
    shadow = np.zeros((4, 8, 8), dtype=np.float64)
    field = sweep(traversable, elevation, slope, RES_M, ROVER, shadow, 1.0, (0, 0), 1.0)
    assert field.refusals["soc_floor"] == 0
    assert field.refusals["shadow_endurance"] == 0
    assert field.refusals["horizon"] > 0
    assert field.energy_binds is False


def test_soc_floor_binds_on_a_thin_battery():
    traversable, elevation, slope = flat_grid(8, 8, slope_deg=10.0)
    shadow = np.ones((12, 8, 8), dtype=np.float64)
    field = sweep(traversable, elevation, slope, RES_M, ROVER, shadow, 1.0, (0, 0), 0.21)
    assert field.refusals["soc_floor"] > 0
    assert field.energy_binds is True


def test_shadow_endurance_binds_before_the_battery_in_the_dark():
    """Yutu-2 survives 2 h of darkness and holds 1 500 Wh: the clock stops it
    long before the charge does, which is the case a bare time-to-0-SOC
    would report wrongly."""
    rover = get_rover("cnsa_yutu_2")
    traversable, elevation, slope = flat_grid(6, 6, slope_deg=1.0)
    shadow = np.ones((12, 6, 6), dtype=np.float64)
    field = sweep(traversable, elevation, slope, RES_M, rover, shadow, 1.0, (0, 0), 1.0)
    assert field.refusals["shadow_endurance"] > 0
    assert field.energy_binds is True


def test_negative_edges_are_counted_when_the_array_outproduces_the_load():
    traversable, elevation, slope = flat_grid(5, 5, slope_deg=0.0)
    lit = np.zeros((4, 5, 5), dtype=np.float64)
    field = sweep(traversable, elevation, slope, RES_M, ROVER, lit, 1.0, (0, 0), 1.0)
    assert field.negative_edges > 0
    dark = np.ones((4, 5, 5), dtype=np.float64)
    field = sweep(traversable, elevation, slope, RES_M, ROVER, dark, 1.0, (0, 0), 1.0)
    assert field.negative_edges == 0


def test_every_move_edge_advances_the_clock():
    """The DAG argument, asserted rather than assumed: a span of zero would
    write backwards into a finalised slice and nothing downstream would
    notice."""
    traversable, elevation, slope = flat_grid(5, 5, slope_deg=0.0)
    shadow = np.zeros((6, 5, 5), dtype=np.float64)
    field = sweep(traversable, elevation, slope, RES_M, ROVER, shadow, 1e-6, (0, 0), 1.0)
    # A 1 us slice makes every span enormous; nothing may land at or before
    # its own slice, and nothing may be reached at all inside the horizon.
    assert field.first_slice[0, 0] == 0
    assert int(field.reachable.sum()) == 1


def test_unusable_edges_never_reach_the_arithmetic():
    """An impassable neighbour carries travel_h = inf in direction_tables;
    casting that to an integer span yields INT64_MIN, which would wrap the
    shadow index. The mask must come first."""
    traversable, elevation, slope = flat_grid(4, 4, slope_deg=0.0)
    traversable[:, 2] = False
    shadow = np.zeros((6, 4, 4), dtype=np.float64)
    field = sweep(traversable, elevation, slope, RES_M, ROVER, shadow, 1.0, (0, 0), 1.0)
    assert not field.reachable[:, 2].any()
    assert not field.reachable[:, 3].any()


# ── the hold clocks ──────────────────────────────────────────────────────────


def test_hold_limit_names_the_clock_that_ends_the_stay():
    """In full darkness LPR-1 reaches its reserve at 66.7 h and zero at
    83.4 h, but its published endurance is 50 h -- so the endurance binds and
    a bare time-to-0-SOC would quote a state the rest of this API calls
    mission failure."""
    traversable, elevation, slope = flat_grid(3, 3, slope_deg=0.0)
    shadow = np.zeros((4, 3, 3), dtype=np.float64)
    field = sweep(traversable, elevation, slope, RES_M, ROVER, shadow, 1.0, (1, 1), 1.0)
    dark = np.ones((400, 3, 3), dtype=np.float64)
    holds = hold_times(field, dark, ROVER, 0.5)
    hours, code = hold_limit(holds, field.reachable)
    assert holds.to_reserve_h[1, 1] == pytest.approx(66.7, abs=0.6)
    assert holds.to_zero_h[1, 1] == pytest.approx(83.4, abs=0.6)
    assert holds.to_endurance_h[1, 1] == pytest.approx(50.0, abs=0.6)
    assert code[1, 1] == HOLD_LIMIT_CODES["shadow_endurance"]
    assert hours[1, 1] == pytest.approx(holds.to_endurance_h[1, 1])


def test_hold_censoring_is_a_flag_and_never_a_number():
    traversable, elevation, slope = flat_grid(3, 3, slope_deg=0.0)
    lit = np.zeros((4, 3, 3), dtype=np.float64)
    field = sweep(traversable, elevation, slope, RES_M, ROVER, lit, 1.0, (1, 1), 1.0)
    holds = hold_times(field, np.zeros((40, 3, 3)), ROVER, 0.5)
    _hours, code = hold_limit(holds, field.reachable)
    # Standing in sunlight the battery never falls: every clock is censored,
    # and that is reported as censored rather than as a very large number.
    assert bool(holds.reserve_censored[1, 1])
    assert math.isnan(holds.to_reserve_h[1, 1])
    assert code[1, 1] == HOLD_LIMIT_CODES["censored"]
    assert code[0, 0] != HOLD_LIMIT_CODES["unreachable"]


def test_default_hold_horizon_outlasts_the_drive_horizon():
    # A 3 h drive horizon censored all 2 086 reachable blocks on Site11; the
    # default has to outlast the rover, not the drive.
    assert default_hold_horizon_hours(ROVER, 3.0) == 100.0
    assert default_hold_horizon_hours(ROVER, 150.0) == 150.0


def test_hold_arrival_resolution_is_the_hold_slice():
    traversable, elevation, slope = flat_grid(3, 3, slope_deg=0.0)
    shadow = np.zeros((4, 3, 3), dtype=np.float64)
    field = sweep(traversable, elevation, slope, RES_M, ROVER, shadow, 1.0, (1, 1), 1.0)
    holds = hold_times(field, np.ones((10, 3, 3)), ROVER, 0.25)
    assert holds.arrival_resolution_h == 0.25
    assert holds.slice_hours == 0.25


# ── bands ────────────────────────────────────────────────────────────────────


def test_band_edges_default_to_equal_slices_of_the_horizon():
    assert default_band_edges(6.0, 3) == [2.0, 4.0, 6.0]
    assert len(default_band_edges(6.0)) == DEFAULT_BAND_COUNT


def test_bands_place_an_arrival_exactly_on_an_edge_inside_that_band():
    traversable, elevation, slope = flat_grid(4, 4, slope_deg=0.0)
    shadow = np.zeros((5, 4, 4), dtype=np.float64)
    field = sweep(traversable, elevation, slope, RES_M, ROVER, shadow, 1.0, (0, 0), 1.0)
    bands = isochrone_bands(field, [1.0, 2.0, 4.0], RES_M)
    index = bands.pop("band_index")
    # The start arrives at 0 h, inside the first band; a neighbour at
    # exactly 1.0 h is in the first band too, not the second.
    assert index[0, 0] == 0
    assert index[0, 1] == 0
    assert field.earliest_hours[0, 1] == 1.0
    assert sum(entry["blocks"] for entry in bands["bands"]) + bands[
        "beyond_last_edge_blocks"
    ] == int(field.reachable.sum())


def test_band_edges_must_be_positive_and_increasing():
    traversable, elevation, slope = flat_grid(3, 3)
    shadow = np.zeros((3, 3, 3), dtype=np.float64)
    field = sweep(traversable, elevation, slope, RES_M, ROVER, shadow, 1.0, (0, 0), 1.0)
    for edges in ([], [2.0, 1.0], [0.0, 1.0], [1.0, 1.0]):
        with pytest.raises(ValueError):
            isochrone_bands(field, edges, RES_M)


def test_boundary_cells_are_the_staircase_and_report_truncation():
    index = np.full((5, 5), -1, dtype=np.int16)
    index[1:4, 1:4] = 0
    cells, truncated = band_boundary_cells(index, 0)
    # The 3x3 block's interior cell is not on the boundary; the other eight
    # are, because each touches a -1.
    assert len(cells) == 8
    assert [2, 2] not in cells
    assert truncated is False
    cells, truncated = band_boundary_cells(index, 0, limit=3)
    assert len(cells) == 3
    assert truncated is True


# ── the epoch ────────────────────────────────────────────────────────────────


def test_shift_epoch_matches_the_fastapi_helper():
    from app.main import _shift_utc

    for hours in (0.0, 1.5, 24.0, -3.0):
        assert shift_epoch("2026-09-05T00:00:00", hours) == _shift_utc(
            "2026-09-05T00:00:00", hours
        )


def test_coarse_shadow_cube_without_an_epoch_is_static_and_says_so():
    base = np.linspace(0.0, 1.0, 16).reshape(4, 4)
    metadata = {"shape": [4, 4], "resolution_m": 5.0}
    cube, provenance = coarse_shadow_cube(base, metadata, 1, 5, 1.0, None)
    assert cube.shape == (5, 4, 4)
    assert provenance["time_varying"] is False
    assert "reason" in provenance
    assert np.array_equal(cube[0], cube[4])


def test_compare_fields_names_the_question_it_does_not_answer():
    traversable, elevation, slope = flat_grid(3, 3)
    shadow = np.zeros((4, 3, 3), dtype=np.float64)
    field = sweep(traversable, elevation, slope, RES_M, ROVER, shadow, 1.0, (0, 0), 1.0)
    block = compare_fields(field, field, RES_M)
    assert block["jaccard"] == 1.0
    assert block["gained_by_later_start_blocks"] == 0
    assert block["independent_restart"] is True
    assert "waits" in block["question_not_answered"].lower()


# ── the work bound ───────────────────────────────────────────────────────────


def test_edge_group_count_grows_as_the_slice_shrinks():
    """A short slice splits one span into many and multiplies the work.

    The grid has to carry a spread of slopes for this to show at all: on
    uniform terrain every edge of a direction has the same travel time and
    therefore one span, whatever the slice.
    """
    traversable, elevation, _slope = flat_grid(8, 8)
    slope = np.tile(np.linspace(0.0, 20.0, 8), (8, 1))
    tables = direction_tables(traversable, elevation, slope, RES_M, ROVER)
    coarse = edge_group_count(tables, 1.0, 2000)
    fine = edge_group_count(tables, 0.002, 2000)
    assert coarse == 8, "at a long slice every edge is one span per direction"
    assert fine > coarse
    assert coarse * 100 < MAX_REACHABLE_GROUP_STEPS


# ── the claim boundary ───────────────────────────────────────────────────────


def test_quoted_numbers_are_not_presented_as_ours():
    for key, entry in REACHABILITY_QUOTED.items():
        assert "not_ours" in entry, f"{key} must say whose numbers these are"


def test_corrections_record_what_was_read_and_when():
    assert len(REACHABILITY_CORRECTIONS) >= 3
    for entry in REACHABILITY_CORRECTIONS:
        assert entry["read"], "a correction has to say when the source was read"
        assert entry["claim"] and entry["correction"]


def test_references_say_what_each_source_is_used_for():
    ids = {entry["id"] for entry in REACHABILITY_REFERENCES}
    assert "tompkins_cmu_2005" in ids
    for entry in REACHABILITY_REFERENCES:
        assert entry["used_for"]
