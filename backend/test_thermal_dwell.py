"""The thermal dwell model (C6), kernel-free.

What is pinned here: the inner-temperature target is the catalogue's own
piecewise offset model (vectorised, equal to the scalar to 1e-12); the
envelope is the tightest declared battery/electronics intersection; the
time to leave it under a first-order lag has three cases (already outside
-> 0, target inside -> unlimited, target outside -> the closed form); the
dwell cube reproduces the closed form on constant and two-piece targets;
the thermostat assumption only removes the cold side; a rover without
``thermal_tau_s`` gets no dwell; the planner is bit-equal without the
constraint and refuses over-long waits with it; LP-R12 and the
entrenchment trigger.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from app import thermal_dwell as TD
from app.constants import get_rover
from app.cost_engine import surface_to_inner

# ── Task 0: constants and layer labels ───────────────────────────────────────


def test_heater_thermostat_is_a_labelled_assumption_and_no_profile_field():
    from app import constants as C

    assert C.HEATER_THERMOSTAT_ASSUMPTION_SOURCE.startswith("assumption:")
    for rover in C.ROVERS.values():
        assert "heater_k_per_w" not in rover and "thermostat" not in rover


def test_dwell_layers_are_described_but_not_in_the_manifest():
    from app.terrain import LAYER_DESCRIPTIONS, LAYER_UNITS, TERRAIN_LAYERS

    assert LAYER_UNITS["max_dwell_h"] == "h" and LAYER_UNITS["dwell_side"] == "code"
    assert "max_dwell_h" in LAYER_DESCRIPTIONS and "max_dwell_h" not in TERRAIN_LAYERS


# ── Task 1: envelope, target, heater, closed form ─────────────────────────────


def test_inner_target_matches_the_scalar_offset_model_for_every_rover():
    surfaces = np.linspace(-200.0, 100.0, 10_001)
    for rid in ("lpr_1", "nasa_viper", "luvmi_m", "cnsa_yutu_2"):
        rover = get_rover(rid)
        expected = np.array([surface_to_inner(float(s), rover) for s in surfaces])
        np.testing.assert_allclose(TD.inner_target_c(surfaces, rover), expected, rtol=0, atol=1e-12)


def test_rover_envelope_is_the_tightest_declared_intersection():
    env = TD.rover_envelope(get_rover("lpr_1"))  # bat [0,35], elec [-10,40]
    assert (env.lo, env.hi) == (0.0, 35.0)
    assert env.lo_component == "battery" and env.hi_component == "battery"
    env = TD.rover_envelope(get_rover("cnsa_yutu_2"))  # bat [-10,30], elec [-40,55]
    assert (env.lo, env.hi) == (-10.0, 30.0)
    env = TD.rover_envelope(get_rover("luvmi_m"))  # bat [-100,0], no electronics
    assert (env.lo, env.hi) == (-100.0, 0.0) and env.hi_component == "battery"
    assert TD.nominal_inner_c(get_rover("lpr_1")) == 17.5
    assert TD.nominal_inner_c(get_rover("cnsa_yutu_2")) == 10.0


def test_exit_time_closed_form_three_cases_and_sides():
    env = TD.Envelope(0.0, 35.0, "battery", "battery")
    tau = 7200.0
    hours, side, comp = TD.exit_time_h(
        np.array([17.5, 17.5, 17.5, 50.0]), np.array([-123.15, 10.0, 60.0, 10.0]), env, tau
    )
    assert hours[0] == pytest.approx(7200 * math.log((17.5 + 123.15) / 123.15) / 3600)
    assert math.isinf(hours[1]) and side[1] == TD.SIDE_NONE and comp[1] == TD.COMPONENT_NONE
    assert hours[2] == pytest.approx(7200 * math.log((60 - 17.5) / (60 - 35)) / 3600)
    assert side[2] == TD.SIDE_HOT and comp[2] == TD.COMPONENT_BATTERY
    assert hours[3] == 0.0 and side[3] == TD.SIDE_HOT
    assert side[0] == TD.SIDE_COLD and comp[0] == TD.COMPONENT_BATTERY


def test_exit_time_names_the_electronics_when_their_bound_is_the_tight_one():
    env = TD.rover_envelope(get_rover("nasa_viper"))  # bat [0,35], elec [-20,50] -> battery both ends
    assert env.lo_component == "battery" and env.hi_component == "battery"
    env2 = TD.Envelope(-10.0, 40.0, "electronics", "electronics")
    hours, side, comp = TD.exit_time_h(np.array([10.0]), np.array([-80.0]), env2, 3600.0)
    assert side[0] == TD.SIDE_COLD and comp[0] == TD.COMPONENT_ELECTRONICS
    assert hours[0] == pytest.approx(math.log(90.0 / 70.0))


def test_warmer_cold_target_means_longer_cold_dwell():
    env = TD.rover_envelope(get_rover("lpr_1"))
    targets = np.array([-120.0, -80.0, -40.0, -10.0])
    hours, _side, _comp = TD.exit_time_h(np.full(4, 17.5), targets, env, 7200.0)
    assert np.all(np.diff(hours) > 0)


def test_thermostat_heater_holds_the_cold_bound_and_leaves_the_hot_side():
    env = TD.rover_envelope(get_rover("lpr_1"))
    held = TD.apply_heater(np.array([-120.0, 10.0, 60.0]), env, "thermostat_assumed")
    np.testing.assert_allclose(held, [0.0, 10.0, 60.0])
    np.testing.assert_allclose(TD.apply_heater(np.array([-120.0]), env, "none"), [-120.0])
    with pytest.raises(ValueError):
        TD.apply_heater(np.array([0.0]), env, "magic")


def test_rover_without_tau_is_unavailable_with_a_reason():
    assert "thermal_tau_s" in TD.dwell_unavailable_reason(get_rover("luvmi_m"))
    assert TD.dwell_unavailable_reason(get_rover("lpr_1")) is None


# ── Task 2: the surface series the cube integrates ────────────────────────────


def _toy_grids():
    rng = np.random.default_rng(7)
    shape = (16, 16)
    return {
        "elevation": rng.random(shape) * 30.0,
        "slope": rng.random(shape) * 12.0,
        "thermal": rng.random(shape) * 80.0 - 90.0,
        "shadow_ratio": rng.random(shape),
        "traversable": np.ones(shape, dtype=bool),
        "metadata": {
            "resolution_m": 80.0,
            "shape": list(shape),
            "thermal_shadow_coupled": True,
            "cost_weights": {"w_slope": 0.409, "w_energy": 0.259, "w_shadow": 0.142, "w_thermal": 0.19},
        },
    }


def test_surface_series_is_what_the_cube_integrates_bit_for_bit():
    from app.cost_cube import build_cost_cube, coarsen_grid, surface_temperature_series
    from app.thermal_model import (
        REGOLITH_THERMAL_TAU_S,
        relax_surface_c,
        shadowed_equilibrium_c,
        sunlit_peak_from_annual_peak_c,
    )

    grids = _toy_grids()
    rover = get_rover("lpr_1")
    rng = np.random.default_rng(1)
    series = [rng.random((16, 16)) for _ in range(6)]
    surface = surface_temperature_series(grids, series, coarsen=4, slice_hours=0.5)
    assert surface.shape == (6, 4, 4)
    cube_a = build_cost_cube(grids, series, rover, coarsen=4, slice_hours=0.5)
    cube_b = build_cost_cube(grids, series, rover, coarsen=4, slice_hours=0.5, surface_series=surface)
    np.testing.assert_array_equal(cube_a, cube_b)
    # The stored field is flagged shadow-coupled, so the series takes it
    # back to the sunlit peak first (round 4, H-1) and starts every cell at
    # its long-run equilibrium.
    base = coarsen_grid(grids["shadow_ratio"], 4)
    sunlit = np.asarray(sunlit_peak_from_annual_peak_c(coarsen_grid(grids["thermal"], 4), base), dtype=np.float64)
    state = np.asarray(shadowed_equilibrium_c(sunlit, base), dtype=np.float64)
    target0 = np.asarray(shadowed_equilibrium_c(sunlit, coarsen_grid(series[0], 4)), dtype=np.float64)
    expected0 = relax_surface_c(state, target0, 1800.0, REGOLITH_THERMAL_TAU_S)
    np.testing.assert_array_equal(surface[0], expected0)


def test_surface_series_rejects_a_mismatched_shape_and_holds_still_uncoupled():
    from app.cost_cube import build_cost_cube, surface_temperature_series

    grids = _toy_grids()
    series = [np.zeros((16, 16))] * 3
    held = surface_temperature_series(grids, series, coarsen=4, slice_hours=0.5, couple_thermal=False)
    assert held.shape == (3, 4, 4) and np.array_equal(held[0], held[2])
    with pytest.raises(ValueError):
        build_cost_cube(grids, series, get_rover("lpr_1"), coarsen=4, surface_series=np.zeros((2, 4, 4)))


# ── Task 3: the dwell cube, the route report, the route inner trace ───────────


def _constant_series(value, n=8, shape=(3, 3)):
    return np.full((n,) + shape, float(value))


def test_dwell_cube_with_a_constant_target_equals_the_closed_form():
    rover = get_rover("lpr_1")
    env = TD.rover_envelope(rover)
    cube = TD.build_dwell_cube(_constant_series(-100.0, n=400), 0.05, rover, np.ones((3, 3), bool))
    expected, _s, _c = TD.exit_time_h(np.array([17.5]), np.array([-40.0]), env, 7200.0)
    assert cube.max_dwell_h[0, 1, 1] == pytest.approx(expected[0], rel=1e-5)
    assert cube.side[0, 1, 1] == TD.SIDE_COLD and cube.component[0, 1, 1] == TD.COMPONENT_BATTERY
    assert cube.max_dwell_h.dtype == np.float32 and cube.n_states == 400 * 9
    late = float(cube.max_dwell_h[399, 1, 1])
    assert math.isinf(late) or late <= cube.lookahead_h[399] + 1e-9


def test_dwell_cube_lit_then_dark_is_the_hand_solved_two_piece_answer():
    rover = get_rover("lpr_1")
    tau = 7200.0
    series = np.concatenate([_constant_series(-40.0, n=4), _constant_series(-140.0, n=200)])
    cube = TD.build_dwell_cube(series, 0.25, rover, np.ones((3, 3), bool))
    t_after_lit = 20.0 + (17.5 - 20.0) * math.exp(-4 * 0.25 * 3600 / tau)
    t_cold = tau * math.log((t_after_lit + 80.0) / 80.0) / 3600
    assert cube.max_dwell_h[0, 0, 0] == pytest.approx(1.0 + t_cold, rel=1e-6)
    assert cube.max_dwell_h[4, 0, 0] == pytest.approx(tau * math.log((17.5 + 80.0) / 80.0) / 3600, rel=1e-6)


def test_dwell_cube_open_ended_where_the_target_stays_inside_and_nan_where_impassable():
    rover = get_rover("lpr_1")
    cube = TD.build_dwell_cube(_constant_series(-40.0, n=10), 0.5, rover, np.ones((3, 3), bool))
    assert np.all(np.isinf(cube.max_dwell_h[:, 1, 1])) and cube.lookahead_h[0] == pytest.approx(5.0)
    assert np.all(cube.side[:, 1, 1] == TD.SIDE_NONE)
    blocked = TD.build_dwell_cube(_constant_series(-40.0), 0.5, rover, np.zeros((3, 3), bool))
    assert np.isnan(blocked.max_dwell_h).all()


def test_thermostat_makes_the_cold_side_open_ended_only():
    rover = get_rover("lpr_1")
    cold = TD.build_dwell_cube(
        _constant_series(-140.0, n=10), 0.5, rover, np.ones((3, 3), bool), heater_model="thermostat_assumed"
    )
    assert np.all(np.isinf(cold.max_dwell_h))
    hot = TD.build_dwell_cube(
        _constant_series(-10.0, n=10), 0.5, rover, np.ones((3, 3), bool), heater_model="thermostat_assumed"
    )
    assert np.all(np.isfinite(hot.max_dwell_h[0])) and hot.side[0, 0, 0] == TD.SIDE_HOT


def test_dwell_cube_is_none_without_tau_and_bins_start_slices_over_budget():
    assert TD.build_dwell_cube(_constant_series(-100.0), 0.5, get_rover("luvmi_m"), np.ones((3, 3), bool)) is None
    cube = TD.build_dwell_cube(
        _constant_series(-100.0, n=40), 0.1, get_rover("lpr_1"), np.ones((3, 3), bool), max_states=100
    )
    assert cube.slices_per_bin == 4 and cube.max_dwell_h.shape[0] == 10
    assert cube.at(7, 0, 0)[0] == float(cube.max_dwell_h[1, 0, 0])
    assert cube.lookahead_h[1] == pytest.approx((40 - 4) * 0.1)


def test_dwell_cube_initial_outside_the_envelope_is_zero_everywhere():
    cube = TD.build_dwell_cube(
        _constant_series(-40.0, n=4), 0.5, get_rover("lpr_1"), np.ones((3, 3), bool), initial_inner_c=60.0
    )
    assert np.all(cube.max_dwell_h == 0.0) and np.all(cube.side == TD.SIDE_HOT) and cube.initial_outside_envelope


def test_route_dwell_report_counts_consecutive_stays_against_the_arrival_budget():
    rover = get_rover("lpr_1")
    cube = TD.build_dwell_cube(_constant_series(-100.0, n=12), 0.25, rover, np.ones((3, 3), bool))
    states = [(0, 0, 0), (0, 0, 1), (0, 0, 2), (0, 1, 3), (0, 1, 4)]
    rep = TD.route_dwell_report(states, 0.25, cube)
    assert rep["path_stay_hours"] == [0.0, 0.25, 0.5, 0.0, 0.25]
    budget = float(cube.max_dwell_h[0, 0, 0])
    assert rep["path_max_dwell_h"][2] == pytest.approx(budget)
    assert rep["path_dwell_margin_h"][2] == pytest.approx(budget - 0.5)
    assert rep["path_max_dwell_h"][3] == pytest.approx(float(cube.max_dwell_h[3, 0, 1]))
    assert rep["max_stay_h"] == 0.5 and rep["wait_steps"] == 3
    assert rep["min_dwell_margin_h"] == pytest.approx(min(v for v in rep["path_dwell_margin_h"] if v is not None))
    assert rep["states_past_thermal_dwell"] == sum(1 for v in rep["path_dwell_margin_h"] if v is not None and v < 0)


def test_route_dwell_report_open_ended_budgets_are_none():
    rover = get_rover("lpr_1")
    cube = TD.build_dwell_cube(_constant_series(-40.0, n=6), 0.5, rover, np.ones((3, 3), bool))
    rep = TD.route_dwell_report([(0, 0, 0), (0, 0, 1), (1, 1, 2)], 0.5, cube)
    assert rep["path_max_dwell_h"] == [None, None, None] and rep["min_dwell_margin_h"] is None
    assert rep["states_past_thermal_dwell"] == 0


def test_route_inner_trace_follows_the_arrival_cell_and_reports_the_first_exit():
    rover = get_rover("lpr_1")
    tau = 7200.0
    series = _constant_series(-140.0, n=10)  # inner target -80 everywhere
    states = [(0, 0, 0), (0, 1, 2), (0, 2, 4)]
    trace = TD.route_inner_trace(states, series, 0.5, rover)
    t1 = -80.0 + (17.5 + 80.0) * math.exp(-2 * 0.5 * 3600 / tau)
    assert trace["path_inner_c"][0] == 17.5 and trace["path_inner_c"][1] == pytest.approx(t1)
    assert trace["states_outside"] == 2 and trace["side"] == "cold" and trace["component"] == "battery"
    assert trace["first_exit_h"] == pytest.approx(tau * math.log(97.5 / 80.0) / 3600)
    assert trace["min_c"] == pytest.approx(min(trace["path_inner_c"]))
    assert trace["envelope"]["lo_c"] == 0.0


def test_route_inner_trace_stays_inside_when_the_target_does():
    rover = get_rover("lpr_1")
    trace = TD.route_inner_trace([(0, 0, 0), (0, 1, 3)], _constant_series(-40.0, n=6), 0.5, rover)
    assert trace["states_outside"] == 0 and trace["first_exit_h"] is None and trace["side"] is None


def test_route_inner_trace_is_none_without_tau():
    assert TD.route_inner_trace([(0, 0, 0), (0, 1, 1)], _constant_series(-40.0), 0.5, get_rover("luvmi_m")) is None


# ── Task 4: the planner's dwell constraint ────────────────────────────────────


def _open_field(n=8, slices=40):
    cost = np.full((slices, n, n), 0.3)
    wait = np.full((slices, n, n), 0.01)
    return cost, wait, np.ones((n, n), bool)


def test_planner_without_a_cube_and_with_an_unenforced_cube_expand_the_same_nodes():
    from app.pathfinder_4d import astar_4d

    rover = get_rover("lpr_1")
    cost, wait, trav = _open_field()
    shadow = np.zeros_like(cost)
    shadow[:, 4:, :] = 1.0
    base = astar_4d(cost, wait, trav, (0, 0), (7, 7), 80.0, 0.25, rover, shadow_cube=shadow)
    cube = TD.build_dwell_cube(np.full(cost.shape, -140.0), 0.25, rover, trav)
    reported = astar_4d(
        cost, wait, trav, (0, 0), (7, 7), 80.0, 0.25, rover, shadow_cube=shadow, max_dwell_cube=cube
    )
    assert reported["path_states"] == base["path_states"]
    assert reported["metrics"]["nodes_expanded"] == base["metrics"]["nodes_expanded"]
    assert reported["metrics"]["total_cost"] == base["metrics"]["total_cost"]
    assert base["path_dwell_margin_h"] is None and base["path_stay_hours"] is None
    assert base["path_max_dwell_h"] is None and base["metrics"]["min_dwell_margin_h"] is None
    assert len(reported["path_dwell_margin_h"]) == len(reported["path_states"])
    assert base["metrics"]["thermal_dwell_enforced"] is False
    assert reported["metrics"]["thermal_dwell_enforced"] is False
    assert reported["metrics"]["edges_rejected"]["thermal_dwell"] == 0
    assert base["metrics"]["edges_rejected"]["thermal_dwell"] == 0


def test_enforced_dwell_refuses_waits_longer_than_the_cell_budget():
    from app.pathfinder_4d import astar_4d, no_path_reason_4d

    rover = get_rover("lpr_1")
    n, slices = 4, 30
    cost = np.full((slices, n, n), 0.3)
    cost[:20, :, 2:] = np.inf  # the right half opens at slice 20: waiting pays
    wait = np.full((slices, n, n), 0.001)
    trav = np.ones((n, n), bool)
    free = astar_4d(cost, wait, trav, (0, 0), (0, 3), 80.0, 0.25, rover)
    assert free["error"] is None and free["metrics"]["wait_steps"] >= 10
    cube = TD.build_dwell_cube(np.full(cost.shape, -140.0), 0.25, rover, trav)  # ~0.27 h: one wait at most
    bound = astar_4d(
        cost, wait, trav, (0, 0), (0, 3), 80.0, 0.25, rover, max_dwell_cube=cube, require_thermal_dwell=True
    )
    assert bound["error"] is not None
    assert bound["metrics"]["edges_rejected"]["thermal_dwell"] > 0
    assert bound["metrics"]["thermal_dwell_enforced"] is True
    reason = no_path_reason_4d(bound["metrics"]["edges_rejected"], rover, slices, 0.25)
    assert "thermal dwell" in reason and "require_thermal_dwell" in reason


def test_enforced_dwell_lets_short_waits_through_and_reports_zero_past():
    from app.pathfinder_4d import astar_4d

    rover = get_rover("lpr_1")
    n, slices = 4, 30
    cost = np.full((slices, n, n), 0.3)
    cost[:2, :, 2:] = np.inf
    wait = np.full((slices, n, n), 0.001)
    trav = np.ones((n, n), bool)
    cube = TD.build_dwell_cube(np.full(cost.shape, -60.0), 0.25, rover, trav)  # -60 -> inner 0: boundary, unlimited
    out = astar_4d(
        cost, wait, trav, (0, 0), (0, 3), 80.0, 0.25, rover, max_dwell_cube=cube, require_thermal_dwell=True
    )
    assert out["error"] is None
    assert out["metrics"]["states_past_thermal_dwell"] == 0 and out["metrics"]["thermal_dwell_enforced"] is True
    assert out["path_max_dwell_h"] == [None] * len(out["path_states"])


def test_enforced_dwell_allows_exactly_the_waits_the_budget_covers():
    from app.pathfinder_4d import astar_4d

    rover = get_rover("lpr_1")
    n, slices = 4, 30
    cost = np.full((slices, n, n), 0.3)
    cost[:3, :, 2:] = np.inf  # three waits needed at 0.25 h = 0.75 h
    wait = np.full((slices, n, n), 0.001)
    trav = np.ones((n, n), bool)
    # The route spends four slices (1.0 h) in the cold whatever it does: one
    # move, two waits, one move into the opening column, one more move.
    # -100 surface -> -40 inner: the envelope is left after 0.725 h -> refused
    cube_short = TD.build_dwell_cube(np.full(cost.shape, -100.0), 0.25, rover, trav)
    out = astar_4d(cost, wait, trav, (0, 0), (0, 3), 80.0, 0.25, rover, max_dwell_cube=cube_short, require_thermal_dwell=True)
    assert out["error"] is not None and "inner temperature" in out["error"]
    # -90 surface -> -30 inner: left after 0.919 h < 1.0 h of exposure -> still refused
    cube_mid = TD.build_dwell_cube(np.full(cost.shape, -90.0), 0.25, rover, trav)
    out = astar_4d(cost, wait, trav, (0, 0), (0, 3), 80.0, 0.25, rover, max_dwell_cube=cube_mid, require_thermal_dwell=True)
    assert out["error"] is not None
    # -80 surface -> -20 inner: left after 1.257 h > 1.0 h -> allowed, arriving at slice 4
    cube_long = TD.build_dwell_cube(np.full(cost.shape, -80.0), 0.25, rover, trav)
    out = astar_4d(cost, wait, trav, (0, 0), (0, 3), 80.0, 0.25, rover, max_dwell_cube=cube_long, require_thermal_dwell=True)
    assert out["error"] is None and out["metrics"]["arrival_slice"] == 4
    assert out["metrics"]["thermal_dwell_enforced"] is True and out["metrics"]["states_past_thermal_dwell"] == 0
    assert out["path_inner_c"][-1] == pytest.approx(-20.0 + 37.5 * math.exp(-1.0 * 3600 / 7200), abs=1e-3)
    assert out["metrics"]["min_dwell_margin_h"] is not None and out["metrics"]["max_stay_h"] <= 0.75


def test_require_without_a_cube_is_refused_with_a_reason():
    from app.pathfinder_4d import astar_4d

    cost, wait, trav = _open_field()
    out = astar_4d(cost, wait, trav, (0, 0), (7, 7), 80.0, 0.25, get_rover("lpr_1"), require_thermal_dwell=True)
    assert out["error"] and "require_thermal_dwell" in out["error"]
    assert out["metrics"]["thermal_dwell_enforced"] is True


def test_enforced_dwell_cannot_be_evaded_by_shuffling_between_dark_blocks():
    """The first version of the constraint bounded consecutive stationary
    hours; the planner evaded it by moving back and forth between two dark
    blocks, resetting its clock while freezing all the same. The enforced
    quantity is therefore the inner temperature itself."""
    from app.pathfinder_4d import astar_4d

    rover = get_rover("lpr_1")
    n, slices = 4, 30
    cost = np.full((slices, n, n), 0.3)
    cost[:20, :, 2:] = np.inf
    wait = np.full((slices, n, n), 0.001)
    trav = np.ones((n, n), bool)
    cube = TD.build_dwell_cube(np.full(cost.shape, -140.0), 0.25, rover, trav)
    out = astar_4d(
        cost, wait, trav, (0, 0), (0, 3), 80.0, 0.25, rover, max_dwell_cube=cube, require_thermal_dwell=True
    )
    assert out["error"] is not None and out["metrics"]["edges_rejected"]["thermal_dwell"] > 0


def test_enforced_route_stays_inside_and_matches_the_post_hoc_trace():
    from app.pathfinder_4d import astar_4d

    rover = get_rover("lpr_1")
    n, slices = 6, 40
    surface = np.full((slices, n, n), -40.0)  # inner 20: inside
    surface[:, :, 3] = -100.0  # a cold column (inner -40) the route must cross quickly
    cost = np.full((slices, n, n), 0.3)
    wait = np.full((slices, n, n), 0.01)
    trav = np.ones((n, n), bool)
    cube = TD.build_dwell_cube(surface, 0.25, rover, trav)
    out = astar_4d(
        cost, wait, trav, (0, 0), (0, 5), 80.0, 0.25, rover, max_dwell_cube=cube, require_thermal_dwell=True
    )
    assert out["error"] is None
    env = TD.rover_envelope(rover)
    assert all(env.lo - 1e-6 <= v <= env.hi + 1e-6 for v in out["path_inner_c"])
    trace = TD.route_inner_trace(out["path_states"], surface, 0.25, rover)
    np.testing.assert_allclose(out["path_inner_c"], trace["path_inner_c"], atol=1e-3)
    assert trace["states_outside"] == 0


# ── Task 5: LP-R12 and the dwell_margin_h signal ──────────────────────────────


def test_lp_r12_is_in_the_catalogue_and_its_export():
    from app import safety_monitor as sm

    req = next(r for r in sm.REQUIREMENTS if r.id == "LP-R12")
    assert req.name == "thermal_dwell" and req.signal == "dwell_margin_h" and req.kind == "lower"
    assert req.fretish == "The rover shall always satisfy stay_h <= max_dwell_h"
    assert "dwell_margin_h" in sm.SIGNAL_NAMES and "dwell_margin_h" in sm.SAMPLE_KEYS
    doc = sm.fret_export()
    r12 = next(r for r in doc["requirements"] if r["reqid"] == "LP-R12")
    assert r12["monitor"]["formula_by_rover"]["lpr_1"] == "always (dwell_margin_h >= 0)"
    assert r12["monitor"]["threshold_source"] == "fixed" and r12["monitor"]["trace_kinds"] == ["4d", "telemetry"]


def test_plan4d_trace_carries_dwell_margin_only_when_given():
    from app import safety_monitor as sm

    rover = get_rover("lpr_1")
    kwargs = dict(
        path_states=[(0, 0, 0), (0, 0, 1), (0, 1, 2)],
        path_battery_pct=[100, 99, 98],
        path_dark_hours=[0, 0, 0],
        path_earth_visible=None,
        path_hours_until_earthset=None,
        path_haven_margin_h=None,
        slice_hours=0.5,
        coarse_slope=np.zeros((2, 2)),
        coarse_elevation=np.zeros((2, 2)),
        coarse_thermal=np.full((2, 2), -60.0),
        resolution_m=80.0,
        rover=rover,
    )
    plain = sm.trace_from_plan4d(**kwargs)
    assert "dwell_margin_h" not in plain.signals
    block = sm.evaluate_catalogue(plain, rover)
    assert next(e for e in block["requirements"] if e["id"] == "LP-R12")["applicable"] is False
    with_dwell = sm.trace_from_plan4d(**kwargs, path_dwell_margin_h=[None, 0.1, -0.2])
    np.testing.assert_allclose(with_dwell.signals["dwell_margin_h"], [np.inf, 0.1, -0.2])
    entry = next(e for e in sm.evaluate_catalogue(with_dwell, rover)["requirements"] if e["id"] == "LP-R12")
    assert entry["applicable"] is True and entry["satisfied"] is False and entry["rho"] == pytest.approx(-0.2)
    assert entry["worst_at"]["index"] == 2
    with pytest.raises(ValueError):
        sm.trace_from_plan4d(**kwargs, path_dwell_margin_h=[0.1])


def test_telemetry_samples_accept_dwell_margin():
    from app import safety_monitor as sm

    trace = sm.trace_from_samples([{"t_h": 0, "dwell_margin_h": 1.0}, {"t_h": 1, "dwell_margin_h": 0.5}])
    assert list(trace.signals["dwell_margin_h"]) == [1.0, 0.5]
    block = sm.evaluate_catalogue(trace, get_rover("lpr_1"))
    entry = next(e for e in block["requirements"] if e["id"] == "LP-R12")
    assert entry["applicable"] is True and entry["satisfied"] is True and entry["rho"] == pytest.approx(0.5)


# ── Task 6: the entrenchment trigger and block ───────────────────────────────


def test_entrenchment_levels_and_trigger():
    from app import replan_triggers as RT

    assert [RT.entrenchment_level(u) for u in (0.0, 0.49, 0.5, 0.79, 0.8, 0.99, 1.0, 3.0)] == [
        "ok", "ok", "warning", "warning", "critical", "critical", "fail", "fail",
    ]
    ok = RT.check_entrenchment(1.0, 4.0)
    assert not ok.triggered and "ok" in ok.detail and ok.trigger_id == "entrenchment"
    warn = RT.check_entrenchment(2.5, 4.0)
    assert not warn.triggered and "warning" in warn.detail
    crit = RT.check_entrenchment(3.5, 4.0)
    assert crit.triggered and "critical" in crit.detail
    fail = RT.check_entrenchment(5.0, 4.0)
    assert fail.triggered and "fail" in fail.detail and "-1.00 h" in fail.detail
    detailed = RT.evaluate_triggers_detailed({"entrenched_hours": 3.5, "tolerable_entrenched_hours": 4.0})
    assert [r.trigger_id for r in detailed["fired"]] == ["entrenchment"]
    skipped = RT.evaluate_triggers_detailed({"entrenched_hours": 1.0})["skipped"]
    assert any(s["trigger_id"] == "entrenchment" for s in skipped)
    assert RT.check_entrenchment(0.0, 0.0).triggered  # a zero budget is already failed


def test_entrenchment_block_takes_the_tighter_countdown():
    block = TD.entrenchment_block(
        1.0, {"max_dwell_h": 1.5, "side": "cold", "component": "battery"}, {"tolerable_h": 6.0}
    )
    assert block["entrenched_hours"] == 1.0
    assert block["thermal"]["remaining_h"] == pytest.approx(0.5) and block["thermal"]["level"] == "warning"
    assert block["haven"]["remaining_h"] == pytest.approx(5.0) and block["haven"]["level"] == "ok"
    assert block["overall"]["limiting"] == "thermal" and block["overall"]["level"] == "warning"
    assert block["overall"]["tolerable_h"] == 1.5 and block["overall"]["remaining_h"] == pytest.approx(0.5)
    assert block["levels"] == ["ok", "warning", "critical", "fail"]
    open_block = TD.entrenchment_block(1.0, {"max_dwell_h": None, "side": None, "component": None}, None)
    assert open_block["overall"]["tolerable_h"] is None and open_block["overall"]["level"] == "ok"
    assert open_block["overall"]["limiting"] is None and open_block["haven"] is None
    haven_only = TD.entrenchment_block(5.0, None, {"tolerable_h": 4.0})
    assert haven_only["overall"]["limiting"] == "haven" and haven_only["overall"]["level"] == "fail"


# ── Task 7: the cell's series and card, the response block ────────────────────


def test_cell_shadow_series_is_static_without_an_epoch_or_cube():
    from app.illumination_series import cell_shadow_series

    series, prov = cell_shadow_series({"shape": [4, 4]}, 1, 1, 5, 0.5, None, base_value=0.3)
    assert series == [0.3] * 5 and prov["model"] == "static" and "epoch" in prov["reason"]
    series, prov = cell_shadow_series({"shape": [4, 4]}, 1, 1, 3, 0.5, "2026-09-28T00:00:00", base_value=0.7)
    assert series == [0.7] * 3 and prov["model"] == "static" and "horizon" in prov["reason"]


def test_cell_dwell_matches_the_cube_on_the_same_series():
    rover = get_rover("lpr_1")
    card = TD.cell_dwell(-146.0, 0.9, [1.0] * 48, 0.5, rover)  # a polar flat cell, dark for 24 h
    surface = TD.surface_series_for_cell(-146.0, 0.9, [1.0] * 48, 0.5)
    cube = TD.build_dwell_cube(surface[:, None, None], 0.5, rover, np.ones((1, 1), bool))
    assert card["max_dwell_h"] == pytest.approx(float(cube.max_dwell_h[0, 0, 0]), rel=1e-9)
    assert card["open_ended"] is False and card["side"] == "cold" and card["component"] == "battery"
    assert card["envelope_verdict"]["cold_end"] == "cold" and card["envelope_verdict"]["peak"] == "cold"
    assert card["lookahead_h"] == pytest.approx(24.0) and card["initial_inner_c"] == 17.5
    assert card["inner_equilibrium_c"]["peak"] == pytest.approx(-86.0)


def test_cell_dwell_is_open_ended_inside_the_envelope_and_unavailable_without_tau():
    rover = get_rover("lpr_1")
    lit = TD.cell_dwell(-40.0, 0.0, [0.0] * 8, 0.5, rover)  # -40 surface -> +20 inner: inside
    assert lit["max_dwell_h"] is None and lit["open_ended"] is True and lit["side"] is None
    assert lit["envelope_verdict"]["peak"] == "inside"
    none = TD.cell_dwell(-40.0, 0.0, [0.0] * 8, 0.5, get_rover("luvmi_m"))
    assert none["max_dwell_h"] is None and none["dwell_model"]["model"] == "unavailable"
    assert none["envelope_verdict"]["peak"] == "inside"  # -40 within [-100, 0] for LUVMI-M


def test_thermal_dwell_block_has_both_shapes():
    rover = get_rover("lpr_1")
    off = TD.thermal_dwell_block(
        None, None, requested=False, applied=False, reason="not requested", inner_trace=None, rover=rover
    )
    assert off["validity"] == "MODEL" and off["thermal_lag_validity"] == "UNCALIBRATED"
    assert off["dwell_model"]["model"] == "unavailable" and off["dwell_model"]["reason"] == "not requested"
    assert off["requested"] is False and off["applied"] is False and off["quoted"]["case_matrix"] == 96
    assert off["envelope"]["lo_c"] == 0.0 and off["claim"].startswith("MODEL")
    cube = TD.build_dwell_cube(_constant_series(-100.0, n=4), 0.5, rover, np.ones((3, 3), bool))
    route = TD.route_dwell_report([(0, 0, 0), (0, 0, 1)], 0.5, cube)
    on = TD.thermal_dwell_block(cube, route, requested=True, applied=True, reason=None, inner_trace=None, rover=rover)
    assert on["applied"] is True and on["cube"]["fraction_cold_limited"] == 1.0
    assert on["dwell_model"]["model"] == TD.THERMAL_DWELL_MODEL_ID and on["route"]["wait_steps"] == 1
    assert on["quoted"]["max_polar_sun_elevation_deg"] == 1.5 and on["heater_model"] == "none"


# ── Task 9: the envelope matrix (JSC's chart, our model) ─────────────────────


def test_bin_envelope_and_matrix_verdicts_on_synthetic_samples():
    samples = {
        "el_deg": np.array([0.2, 0.3, 2.0, -1.0]),
        "s_par_deg": np.array([1.0, 1.0, 20.0, -20.0]),
        "surface_c": np.array([-100.0, -90.0, -20.0, -200.0]),
        "slope_deg": np.array([1.0, 1.0, 20.0, 20.0]),
    }
    el_edges = np.array([-3.0, 0.0, 1.0, 3.0])
    sp_edges = np.array([-30.0, 0.0, 10.0, 30.0])
    binned = TD.bin_envelope(samples, el_edges, sp_edges)
    assert binned["tmax"][1, 1] == -90.0 and binned["count"][1, 1] == 2 and binned["tmean"][1, 1] == -95.0
    assert np.isnan(binned["tmax"][0, 2]) and binned["count"][0, 2] == 0
    assert binned["tmax"][0, 0] == -200.0 and binned["tmax"][2, 2] == -20.0
    matrix = TD.envelope_matrix(binned, get_rover("lpr_1"))
    cells = {(c["el_bin"], c["s_par_bin"]): c for c in matrix["cells"]}
    assert cells[(1, 1)]["verdict"] == "cold_limited" and cells[(1, 1)]["inner_c"] == -30.0
    assert cells[(2, 2)]["verdict"] == "hot_limited" and cells[(2, 2)]["inner_c"] == 40.0
    assert cells[(2, 2)]["dwell_h"] == pytest.approx(7200 * math.log((40 - 17.5) / (40 - 35)) / 3600)
    assert cells[(0, 2)]["verdict"] == "unsampled" and cells[(0, 2)]["dwell_h"] is None
    assert matrix["counts"] == {"unlimited": 0, "cold_limited": 2, "hot_limited": 1, "unsampled": 6}
    assert matrix["axes"]["el_deg"]["edges"] == [-3.0, 0.0, 1.0, 3.0]
    assert matrix["envelope"]["lo_c"] == 0.0 and matrix["initial_inner_c"] == 17.5
    thermostat = TD.envelope_matrix(binned, get_rover("lpr_1"), heater_model="thermostat_assumed")
    assert thermostat["counts"]["cold_limited"] == 0 and thermostat["counts"]["unlimited"] == 2
    no_tau = TD.envelope_matrix(binned, get_rover("luvmi_m"))
    assert no_tau["dwell_model"]["model"] == "unavailable"
    assert all(c["dwell_h"] is None for c in no_tau["cells"])


def test_envelope_cache_round_trip(tmp_path):
    binned = TD.bin_envelope(
        {"el_deg": np.array([0.5]), "s_par_deg": np.array([5.0]), "surface_c": np.array([-50.0]), "slope_deg": np.array([5.0])},
        TD.ENVELOPE_EL_EDGES,
        TD.ENVELOPE_SPAR_EDGES,
    )
    path = tmp_path / TD.ENVELOPE_CACHE_FILENAME
    TD.save_envelope_cache(str(path), binned, {"lat_deg": -88.92, "slopes_deg": [5.0], "ndays": 13})
    assert path.exists() and (tmp_path / TD.ENVELOPE_META_FILENAME).exists()
    loaded = TD.load_envelope_cache(str(path))
    np.testing.assert_array_equal(loaded["tmax"], binned["tmax"])
    assert loaded["meta"]["lat_deg"] == -88.92 and loaded["el_edges"].shape == TD.ENVELOPE_EL_EDGES.shape
    assert TD.envelope_cache_path({"processed_dir": str(tmp_path)}) == str(path)
    assert TD.envelope_cache_path({}) is None and TD.envelope_cache_path({"processed_dir": str(tmp_path / "nope")}) is None


def test_heat1d_envelope_samples_needs_heat1d():
    from app.thermal_model import Heat1DModel

    if Heat1DModel.available():
        pytest.skip("heat1d present: the real run is exercised by the cache script and the real-grid test")
    with pytest.raises(RuntimeError):
        TD.heat1d_envelope_samples(-88.92, slopes=(0.0,), ndays=1)
