"""Regression tests for the round 4 independent backend review.

One test group per finding, each pinning the BEHAVIOUR the fix establishes
rather than the shape of the patch. Where the review reports a measurement,
the test asserts the property that measurement demonstrates.

Review: docs/superpowers/reviews/2026-08-30-backend-review-4.md
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.constants import (
    LOG_BARRIER_MU,
    THERMAL_MIN_TRAVERSABLE_C,
    get_rover,
)
from app.cost_cube import build_cost_cube, coarsen_grid, coarsen_traversable
from app.cost_engine import (
    edge_barrier_penalty,
    geometric_barrier_terms,
    lateral_slope_tan,
    thermal_barrier_terms,
    _surface_ceiling_c,
)
from app.costmap import CostMap, PlanContext, default_cost_map
from app.data_loader import THERMAL_FIELD_SUNLIT_PEAK, derive_thermal_fields
from app.horizon import horizon_map, march_distances_cells
from app.pathfinder import _barrier_table, _geometric_barrier, astar
from app.pathfinder_4d import astar_4d, gated_move_count, no_path_reason_4d
from app.scenarios import MISSION_PROFILES, check_profile_constraints, list_profiles
from app.thermal_model import (
    PSR_ANNUAL_MAX_K,
    REGOLITH_THERMAL_TAU_S,
    annual_peak_c,
    relax_surface_c,
    shadowed_equilibrium_c,
    sunlit_peak_from_annual_peak_c,
    sunlit_peak_from_equilibrium_c,
)
from app.traversability import compute_traversability, compute_traversability_bool

PSR_C = PSR_ANNUAL_MAX_K - 273.15


def _grids(shape=(12, 12), resolution=10.0, slope=4.0, thermal=-40.0, shadow=0.3):
    sunlit = np.full(shape, thermal, dtype=np.float64)
    shadow_grid = np.full(shape, shadow, dtype=np.float64)
    peak, cold = derive_thermal_fields(sunlit, shadow_grid)
    return {
        "elevation": np.zeros(shape, dtype=np.float64),
        "slope": np.full(shape, slope, dtype=np.float64),
        "thermal": peak,
        "thermal_min": cold,
        "thermal_sunlit_peak": sunlit,
        "shadow_ratio": shadow_grid,
        "traversable": compute_traversability_bool(
            np.full(shape, slope), peak, thermal_min=cold
        ),
        "metadata": {
            "resolution_m": resolution,
            "shape": list(shape),
            "thermal_field": THERMAL_FIELD_SUNLIT_PEAK,
        },
    }


# ── H-1: the illumination correction is applied exactly once ───────────────


def test_h1_the_cube_does_not_re_correct_an_already_corrected_field():
    """Round 3 coupled a coupled field. Compounding is not a smaller error.

    Measured on the production grid before the fix: the 4-D planner's map ran
    37 C colder than the 2-D planner's for the same terrain at the same
    instant, 3 494 cells were impassable to one and passable to the other,
    and mean cell cost was 20 percent high.
    """
    grids = _grids()
    rover = get_rover()
    shadow = grids["shadow_ratio"]

    cube = build_cost_cube(grids, [shadow], rover, slice_hours=1.0)

    # The cube's slice-0 temperature must be the cell's own cold-end
    # equilibrium under its own long-run illumination -- not that field put
    # through the blend a second time.
    expected = np.asarray(
        shadowed_equilibrium_c(grids["thermal_sunlit_peak"], shadow), dtype=np.float64
    )
    assert np.allclose(expected, grids["thermal_min"], equal_nan=True)

    # And the two planners must agree about which cells are passable.
    finite = np.isfinite(cube[0])
    assert np.array_equal(finite, np.asarray(grids["traversable"], dtype=bool))


def test_h1_the_stored_field_round_trips_through_both_corrections():
    sunlit = np.array([[24.0, 0.0, -50.0, 10.0]])
    shadow = np.array([[0.0, 0.53, 0.9, 0.99]])

    peak = annual_peak_c(sunlit, shadow)
    assert np.allclose(sunlit_peak_from_annual_peak_c(peak, shadow), sunlit, atol=1e-2)

    equilibrium = shadowed_equilibrium_c(sunlit, shadow)
    assert np.allclose(
        sunlit_peak_from_equilibrium_c(equilibrium, shadow), sunlit, atol=1e-2
    )


def test_h1_metadata_names_the_statistic_not_merely_that_one_was_applied():
    """`thermal_shadow_coupled` could not express WHICH field was stored."""
    grids = _grids()
    assert grids["metadata"]["thermal_field"] == THERMAL_FIELD_SUNLIT_PEAK


# ── H-2: the 4-D planner must name the constraint that closed the route ────


def _corner_locked_grid():
    """A 5x5 grid whose centre cell has no legal edge: a cross-slope bowl."""
    shape = (5, 5)
    elevation = np.zeros(shape, dtype=np.float64)
    # A steep ridge running north-south beside the centre column makes every
    # edge out of the centre a severe cross-slope.
    elevation[:, 1] = 60.0
    elevation[:, 3] = -60.0
    return elevation


def test_h2_a_geometric_failure_is_not_reported_as_a_horizon_failure():
    rover = get_rover()
    elevation = _corner_locked_grid()
    passable = np.ones(elevation.shape, dtype=bool)
    cost = np.zeros((40, *elevation.shape))
    wait = np.full((40, *elevation.shape), 0.05)

    result = astar_4d(
        cost, wait, passable,
        start=(2, 2), goal=(4, 4),
        resolution_m=20.0, slice_hours=1.0, rover=rover,
        slope_grid=np.zeros(elevation.shape),
        elevation_grid=elevation,
    )
    assert result["error"] is not None
    # 40 slices for a 2-move route: the horizon is not the problem, and the
    # message must not say it is.
    assert "roll-over" in result["error"] or "step-slope" in result["error"]
    assert result["metrics"]["edges_rejected"]["lateral_slope"] > 0
    assert result["metrics"]["nodes_expanded"] > 0


def test_h2_a_genuine_horizon_failure_still_says_so():
    rover = get_rover()
    shape = (2, 8)
    passable = np.ones(shape, dtype=bool)
    cost = np.zeros((3, *shape))
    wait = np.full((3, *shape), 0.05)
    result = astar_4d(
        cost, wait, passable,
        start=(0, 0), goal=(0, 7),
        resolution_m=400.0, slice_hours=0.05, rover=rover,
        slope_grid=np.zeros(shape),
        elevation_grid=np.zeros(shape),
    )
    assert result["error"] is not None
    assert "time horizon" in result["error"]
    assert result["metrics"]["horizon_truncated"]


def test_h2_gated_reachability_sees_edges_that_cell_reachability_misses():
    rover = get_rover()
    elevation = _corner_locked_grid()
    passable = np.ones(elevation.shape, dtype=bool)

    from app.pathfinder_4d import bfs_move_count

    assert bfs_move_count(passable, (2, 2), (4, 4)) is not None
    assert (
        gated_move_count(passable, (2, 2), (4, 4), elevation, 20.0, rover) is None
    ), "the gated graph must not claim a route the planner will refuse"


def test_h2_no_path_reason_reports_every_counted_constraint():
    rover = get_rover()
    reason = no_path_reason_4d(
        {"lateral_slope": 7, "step_slope": 3, "horizon": 2, "cost_infinite": 1},
        rover, n_slices=10, slice_hours=1.0,
    )
    for fragment in ("7 edges", "3 edges", "2 edges", "1 edges"):
        assert fragment in reason


# ── H-3: peak and cold end are different statistics ────────────────────────


def test_h3_a_partly_lit_cell_still_reaches_its_peak():
    """A time-average is not a maximum. Round 3 read 78 K low at f = 0.25."""
    sunlit = np.array([[0.0]])
    for ratio in (0.0, 0.25, 0.5, 0.75, 0.9):
        peak = float(annual_peak_c(sunlit, np.array([[ratio]]))[0, 0])
        assert peak == pytest.approx(0.0, abs=1e-3)
    assert float(annual_peak_c(sunlit, np.array([[1.0]]))[0, 0]) == pytest.approx(
        PSR_C, abs=1e-3
    )


def test_h3_the_cold_end_still_falls_with_illumination():
    sunlit = np.full(5, 10.0)
    cold = shadowed_equilibrium_c(sunlit, np.array([0.0, 0.25, 0.5, 0.75, 1.0]))
    assert all(b < a for a, b in zip(cold, cold[1:]))


def test_h3_regolith_lag_separates_a_passing_shadow_from_a_cold_trap():
    floor = np.array(PSR_C)
    after_hour = float(relax_surface_c(np.array(0.0), floor, 3600.0))
    assert THERMAL_MIN_TRAVERSABLE_C < after_hour < 0.0
    after_day = float(relax_surface_c(np.array(0.0), floor, 24 * 3600.0))
    assert after_day == pytest.approx(PSR_C, abs=1.0)


def test_h3_sustained_shadow_makes_a_cell_costlier_but_never_closes_it():
    """H-3 introduced the regolith lag so that one slice of shadow is not a
    cold trap. It also closed the cell once the skin fell below -150 C, and
    that rule shut the entire production grid for the whole lunar night
    (measured 2026-09-07: 0 percent passable after 2.5 h) while the
    catalogue gives LPR-1 50 h of darkness. The lag stays; the veto is gone.
    Whether the rover may sit in a dark cell is now decided by its own
    battery and shadow endurance in the planner's state (pathfinder_4d)."""
    grids = _grids(thermal=10.0, shadow=0.0)
    rover = get_rover()
    dark = np.ones(grids["slope"].shape)
    lit = np.zeros(grids["slope"].shape)
    cube = build_cost_cube(
        grids, [lit] + [dark] * 15, rover, slice_hours=1.0
    )
    assert np.isfinite(cube[0, 0, 0])
    assert np.isfinite(cube[1, 0, 0]), "one hour of shadow is not a cold trap"
    assert np.isfinite(cube[-1, 0, 0]), "sustained shadow is priced, not banned"
    assert cube[-1, 0, 0] > cube[1, 0, 0], "the surface keeps cooling, so cost keeps rising"


def test_h3_traversability_gates_on_the_cold_end():
    slope = np.array([[5.0]])
    peak = np.array([[20.0]])          # comfortable at its peak
    cold = np.array([[-160.0]])        # not survivable at its cold end
    assert not compute_traversability_bool(slope, peak, thermal_min=cold)[0, 0]
    assert compute_traversability(slope, peak, thermal_min=cold)[0, 0] == 0.0
    assert compute_traversability_bool(slope, peak)[0, 0], "peak alone still passes"


def test_h3_the_thermal_penalty_scores_the_worse_end():
    from app.cost_engine import f_thermal

    rover = get_rover()
    warm_only = f_thermal(0.0, rover)
    envelope = f_thermal(0.0, rover, -183.0)
    assert envelope >= warm_only


# ── H-4: the horizon reaches its stated range ──────────────────────────────


def test_h4_max_steps_bounds_samples_not_range():
    steps = march_distances_cells(
        resolution_m=5.0, max_range_m=10000.0, max_steps=200
    )
    assert steps.size <= 200
    assert steps.max() * 5.0 == pytest.approx(10000.0, rel=1e-3)
    # Dense near field: every cell out to the dense range is visited.
    assert np.array_equal(steps[:80], np.arange(1.0, 81.0))


def test_h4_a_roi_marches_over_the_surrounding_terrain():
    """The crop's horizon and the window-in-context horizon differ."""
    elevation = np.zeros((9, 60), dtype=np.float64)
    elevation[:, 55] = 400.0                       # a ridge outside the crop

    crop = horizon_map(
        elevation[:, :20], 5.0, n_azimuth=4, max_range_m=10000.0, curvature=False
    )
    in_context = horizon_map(
        elevation, 5.0, n_azimuth=4, max_range_m=10000.0, curvature=False,
        roi=(0, 9, 0, 20),
    )
    assert crop.shape == in_context.shape
    east = 1  # azimuth index 1 of 4 = grid east
    assert in_context[east, 4, 10] > crop[east, 4, 10] + 5.0, (
        "the ridge outside the crop must raise the horizon inside it"
    )


# ── M-1: the reported cost is the objective the planner minimised ──────────


def test_m1_total_weighted_cost_is_the_g_score_barrier_included():
    grids = _grids(thermal=-40.0, shadow=0.0)
    result = astar(grids, (0, 0), (5, 5), rover=get_rover())
    metrics = result["metrics"]
    assert metrics["total_weighted_cost"] > metrics["total_weighted_cost_cells_only"]
    # barrier_share is rounded for the wire; it must still agree with the
    # two totals it is derived from.
    assert metrics["barrier_share"] == pytest.approx(
        (metrics["total_weighted_cost"] - metrics["total_weighted_cost_cells_only"])
        / metrics["total_weighted_cost"],
        abs=1e-6,
    )
    assert 0.0 < metrics["barrier_share"] < 1.0


# ── M-2: nodes_expanded survives a failure ────────────────────────────────


def test_m2_a_failed_plan_reports_the_work_it_did():
    elevation = np.zeros((12, 12), dtype=np.float64)
    elevation[:, 6] = 500.0            # an impassable wall
    grids = _grids()
    grids["elevation"] = elevation
    result = astar(grids, (0, 0), (0, 11), rover=get_rover())
    assert result["error"] is not None
    rejected = sum(result["metrics"]["edges_rejected"].values())
    assert rejected > 0
    assert result["metrics"]["nodes_expanded"] > 0, (
        "a plan that refused edges must have expanded nodes to refuse them"
    )


# ── M-4: every declared constraint gets a verdict ─────────────────────────


def test_m4_profiles_say_how_each_constraint_is_applied():
    listed = list_profiles()
    for profile in listed.values():
        handling = profile["constraint_handling"]
        assert handling["max_slope_deg"] == "enforced_in_search"
        for key in ("max_shadow_h", "max_energy_wh", "min_soc"):
            assert handling[key] == "verified_after_simulation"


def test_m4_constraint_check_verdicts_track_a_simulated_summary():
    profile = MISSION_PROFILES["energy_saver"]

    unchecked = check_profile_constraints(profile, None)
    assert all(not v["checked"] for k, v in unchecked.items() if k != "max_slope_deg")

    summary = {
        "max_continuous_shadow_h": 12.0,
        "total_energy_consumed_wh": 3000.0,   # over the 2500 Wh limit
        "min_battery_pct": 40.0,              # over the 0.35 floor
    }
    checked = check_profile_constraints(profile, summary)
    assert checked["max_shadow_h"]["satisfied"] is True
    assert checked["max_energy_wh"]["satisfied"] is False
    assert checked["min_soc"]["satisfied"] is True
    assert all(v["checked"] for v in checked.values())


# ── M-5: one barrier formula, not four transcriptions ─────────────────────


def test_m5_the_barrier_table_samples_the_cost_engine_formula():
    limit = 25.0
    table, scale = _barrier_table(limit)
    for degrees in (0.0, 5.0, 12.5, 20.0, 24.0):
        tangent = math.tan(math.radians(degrees))
        index = min(int(tangent * scale), len(table) - 1)
        exact = -LOG_BARRIER_MU * sum(
            geometric_barrier_terms(
                degrees, 0.0,
                {"slope_max_deg": limit, "slope_lateral_max_deg": limit},
            )
        )
        assert table[index] == pytest.approx(exact, abs=0.02)


def test_m5_the_planner_and_the_cost_engine_share_one_cross_slope():
    root2 = 1.0 / math.sqrt(2.0)
    for grad_row, grad_col, unit_r, unit_c in (
        (0.3, 0.0, 0.0, 1.0),
        (0.0, 0.3, -1.0, 0.0),
        (0.2, -0.1, -root2, root2),
    ):
        direct = abs(grad_row * -unit_c + grad_col * unit_r)
        assert lateral_slope_tan(grad_row, grad_col, unit_r, unit_c) == pytest.approx(
            direct
        )


def test_m5_geometric_barrier_delegates_rather_than_restating():
    assert _geometric_barrier(10.0, 5.0, 25.0, 18.0) == pytest.approx(
        -LOG_BARRIER_MU
        * sum(
            geometric_barrier_terms(
                10.0, 5.0, {"slope_max_deg": 25.0, "slope_lateral_max_deg": 18.0}
            )
        )
    )
    assert math.isinf(_geometric_barrier(25.0, 5.0, 25.0, 18.0))


# ── M-6: no fabricated zeros ──────────────────────────────────────────────


def test_m6_untracked_metrics_are_none_not_zero():
    grids = _grids()
    result = astar(grids, (0, 0), (5, 5), rover=get_rover())
    assert result["metrics"]["total_energy_wh"] is None
    assert result["metrics"]["total_shadow_hours"] is None


# ── M-7: the hot wall stands at the tightest declared ceiling ─────────────


def test_m7_the_hot_wall_uses_the_binding_component_limit():
    lpr = get_rover("lpr_1")
    # bat_op_max_c 35 C is tighter than elec_op_max_c 40 C; with a -40 offset
    # that is a 75 C surface ceiling, not 80 C.
    assert _surface_ceiling_c(lpr) == pytest.approx(75.0)
    assert _surface_ceiling_c(lpr) < float(lpr["elec_op_max_c"]) - float(
        lpr["thermal_offset_hot"]
    )


# ── L-1: the zero-weight veto guard reaches explain() too ─────────────────


def test_l1_explain_does_not_multiply_zero_by_infinity():
    rover = get_rover()
    ctx = PlanContext(
        slope=np.array([[40.0]]),          # over every rover's limit
        thermal=np.array([[0.0]]),
        shadow_ratio=np.array([[0.0]]),
        traversable=np.array([[False]]),
        resolution_m=5.0,
        rover=rover,
    )
    cost_map = default_cost_map(
        rover, {"w_slope": 0.0, "w_energy": 0.3, "w_shadow": 0.3, "w_thermal": 0.4}
    )
    with np.errstate(all="raise"):
        breakdown = cost_map.explain(0, 0, ctx)
    assert breakdown["slope"] is None
    assert breakdown["total"] is None


# ── L-2: a lateral refusal is reported as a lateral refusal ───────────────


def test_l2_barrier_rejections_are_attributed_to_the_right_limit():
    from app.pathfinder import _astar_core

    keys = set()
    elevation = np.zeros((6, 6))
    grids = _grids(shape=(6, 6))
    grids["elevation"] = elevation
    result = astar(grids, (0, 0), (5, 5), rover=get_rover())
    keys = set(result["metrics"]["edges_rejected"])
    assert {"slope_barrier", "lateral_barrier", "step_slope", "lateral_slope"} <= keys


# ── L-3: the search reads float64 costs ───────────────────────────────────


def test_l3_the_cost_grid_the_search_reads_is_not_quantised():
    from app.pathfinder import _resolve_cost_grid

    grids = _grids()
    resolved = _resolve_cost_grid(
        grids, grids["slope"], grids["thermal"], grids["shadow_ratio"],
        10.0, grids["traversable"], None, get_rover(),
    )
    assert resolved.dtype == np.float64


# ── L-4: the simulator drives the geometry the planner gated on ───────────


def test_l4_simulation_uses_the_segment_slope():
    from app.simulation import simulate_path

    shape = (3, 6)
    elevation = np.zeros(shape, dtype=np.float64)
    for col in range(6):
        elevation[1, col] = col * 2.0     # a real climb the cell slope misses
    path = [[1, c] for c in range(6)]
    result = {"path_pixels": path, "metrics": {}, "error": None}

    flat = simulate_path(
        result, np.full(shape, 0.5), np.zeros(shape), np.full(shape, -20.0),
        np.zeros(shape), pixel_size_m=5.0,
    )
    climbed = simulate_path(
        result, np.full(shape, 0.5), np.zeros(shape), np.full(shape, -20.0),
        np.zeros(shape), pixel_size_m=5.0, elevation_grid=elevation,
    )
    assert climbed[-1].elapsed_hours > flat[-1].elapsed_hours
    assert climbed[-1].segment_slope_deg > 0.0
    assert flat[-1].segment_slope_deg == pytest.approx(0.0)


# ── L-6: an un-reset odometer is an epoch error, not slip ─────────────────


def test_l6_an_impossible_odometry_claim_does_not_fire_slip():
    from app.slip_model import check_slip_accumulation

    # 5 m along a 100 m corridor against a 900 m claim: on the face of it a
    # ratio of 0.006, well under threshold -- but no rover drove 900 m on a
    # 100 m route, so the claim is a counter that was never reset.
    result = check_slip_accumulation(5.0, 900.0, corridor_length_m=100.0)
    assert not result.triggered
    assert "reset" in result.detail

    # Genuine slip on a plausible claim still fires.
    fired = check_slip_accumulation(30.0, 100.0, corridor_length_m=200.0)
    assert fired.triggered


# ── L-7: the slice comes from the real slope distribution ─────────────────


def test_l7_auto_slice_hours_is_not_biased_by_the_coarsen_factor():
    from app.cost_cube import auto_slice_hours

    rover = get_rover()
    fine = np.tile(np.array([2.0, 2.0, 2.0, 20.0]), (8, 2))
    passable = np.ones(fine.shape, dtype=bool)

    from_fine = auto_slice_hours(fine, passable, 20.0, rover)
    from_block_max = auto_slice_hours(
        coarsen_grid(fine, 4, how="max"),
        coarsen_traversable(passable, 4),
        20.0,
        rover,
    )
    assert from_fine < from_block_max, (
        "a median of block maxima is biased high; that was the bug"
    )


# ── L-8: one traversability rule, two dtypes ──────────────────────────────


def test_l8_both_traversability_forms_apply_the_same_rule():
    slope = np.array([[5.0, 5.0]])
    thermal = np.array([[0.0, 0.0]])
    elevation = np.array([[0.0, np.nan]])
    boolean = compute_traversability_bool(slope, thermal, elevation)
    floating = compute_traversability(slope, thermal, elevation=elevation)
    assert np.array_equal(boolean, floating.astype(bool))
    assert not boolean[0, 1], "a NaN elevation must block in BOTH forms"


# ── L-11: the coarse gate measures the published hop ──────────────────────


def test_l11_center_reduction_reports_the_waypoint_cell():
    grid = np.arange(16, dtype=np.float64).reshape(4, 4)
    centred = coarsen_grid(grid, 2, how="center")
    assert centred.shape == (2, 2)
    # Block (0,0) spans rows 0-1, cols 0-1; its centre cell is (1, 1) = 5.
    assert centred[0, 0] == pytest.approx(grid[1, 1])
    assert centred[1, 1] == pytest.approx(grid[3, 3])


def test_l11_a_block_mean_hides_a_step_the_centres_actually_have():
    fine = np.zeros((4, 4), dtype=np.float64)
    fine[2:, 2:] = 40.0                    # one block genuinely higher
    mean = coarsen_grid(fine, 2, how="mean")
    centre = coarsen_grid(fine, 2, how="center")
    assert centre[1, 1] - centre[0, 0] >= mean[1, 1] - mean[0, 0]


# ── L-12: the cold wall agrees with the traversability gate ───────────────


def test_l12_a_cell_at_the_gate_is_a_legal_start_and_a_legal_destination():
    rover = get_rover()
    at_wall = THERMAL_MIN_TRAVERSABLE_C
    assert compute_traversability_bool(
        np.array([[5.0]]), np.array([[at_wall]])
    )[0, 0], "the gate is inclusive"

    terms = thermal_barrier_terms(at_wall, rover)
    assert all(math.isfinite(t) for t in terms), "so the barrier must be too"
    assert math.isfinite(edge_barrier_penalty(5.0, 5.0, at_wall, rover=rover))
    assert edge_barrier_penalty(5.0, 5.0, at_wall, rover=rover) > 1.0

    assert math.isinf(edge_barrier_penalty(5.0, 5.0, at_wall - 1.0, rover=rover))
