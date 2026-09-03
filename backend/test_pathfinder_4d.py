"""4-D (row, col, time) A* tests."""

from __future__ import annotations

import numpy as np
import pytest

from app.constants import get_rover
from app.pathfinder_4d import astar_4d

RES_M = 80.0
SLICE_H = 1.0


def _uniform_case(n_slices=6, shape=(1, 4), cost=0.01, wait=0.01):
    cost_cube = np.full((n_slices, *shape), cost, dtype=np.float64)
    wait_cube = np.full((n_slices, *shape), wait, dtype=np.float64)
    traversable = np.ones(shape, dtype=bool)
    return cost_cube, wait_cube, traversable


def _run(cost_cube, wait_cube, traversable, start=(0, 0), goal=(0, 3)):
    return astar_4d(
        cost_cube,
        wait_cube,
        traversable,
        start=start,
        goal=goal,
        resolution_m=RES_M,
        slice_hours=SLICE_H,
        rover=get_rover(),
    )


def test_finds_a_direct_path_on_a_uniform_cube():
    result = _run(*_uniform_case())
    assert result["error"] is None
    assert result["path_pixels"][0] == (0, 0)
    assert result["path_pixels"][-1] == (0, 3)
    assert result["metrics"]["wait_steps"] == 0


def test_path_states_carry_monotonically_increasing_time():
    result = _run(*_uniform_case())
    times = [t for _, _, t in result["path_states"]]
    assert times == sorted(times)
    assert times[0] == 0


def test_blocked_goal_returns_an_error():
    cost_cube, wait_cube, traversable = _uniform_case()
    traversable[0, 3] = False
    result = _run(cost_cube, wait_cube, traversable)
    assert result["error"] is not None
    assert result["path_pixels"] == []


def test_out_of_bounds_start_returns_an_error():
    result = _run(*_uniform_case(), start=(0, 9))
    assert result["error"] is not None


def test_exhausted_time_horizon_returns_an_error():
    """Two slices cannot cover a three-move path."""
    result = _run(*_uniform_case(n_slices=2))
    assert result["error"] is not None


def test_metrics_report_expansion_and_timing():
    result = _run(*_uniform_case())
    assert result["metrics"]["nodes_expanded"] > 0
    assert result["metrics"]["computation_time_ms"] >= 0.0
    assert result["metrics"]["move_steps"] == 3
    assert result["metrics"]["arrival_slice"] >= 3


def _shadow_then_sun_case():
    """A 1x4 corridor whose middle is expensive until slice 3.

    Sitting still at the start is nearly free (lit, charging), so the
    cheapest plan is: wait for the Sun, then cross.
    """
    n_slices, shape = 8, (1, 4)
    cost_cube = np.full((n_slices, *shape), 0.01, dtype=np.float64)
    cost_cube[:3, 0, 1] = 40.0
    cost_cube[:3, 0, 2] = 40.0
    wait_cube = np.full((n_slices, *shape), 0.001, dtype=np.float64)
    traversable = np.ones(shape, dtype=bool)
    return cost_cube, wait_cube, traversable


def test_planner_chooses_to_wait_for_the_sun():
    result = _run(*_shadow_then_sun_case())
    assert result["error"] is None
    assert result["metrics"]["wait_steps"] > 0, "planner should hold for the Sun"
    assert result["path_pixels"][-1] == (0, 3)


def test_waiting_plan_is_cheaper_than_crossing_immediately():
    """Sanity: the wait is an optimisation, not an artefact."""
    cost_cube, wait_cube, traversable = _shadow_then_sun_case()
    waited = _run(cost_cube, wait_cube, traversable)

    # Same cube, but waiting is made prohibitively expensive.
    expensive_wait = np.full_like(wait_cube, 1e6)
    rushed = _run(cost_cube, expensive_wait, traversable)

    assert waited["metrics"]["wait_steps"] > 0
    assert rushed["metrics"]["wait_steps"] == 0
    assert waited["metrics"]["total_cost"] < rushed["metrics"]["total_cost"]


def test_planner_does_not_wait_when_there_is_nothing_to_gain():
    """A uniformly cheap cube must produce a straight, wait-free plan."""
    result = _run(*_uniform_case(n_slices=8))
    assert result["metrics"]["wait_steps"] == 0


# ── Review findings: JSON safety and degenerate start/goal ────────────────────


def test_error_result_is_strict_json_serialisable():
    """``inf`` is not valid JSON; a caller that serialises an error result
    directly must not get a 500. Same root cause as the Faz 2 C1 finding."""
    import json

    cost_cube, wait_cube, traversable = _uniform_case()
    traversable[0, 3] = False
    result = _run(cost_cube, wait_cube, traversable)

    assert result["error"] is not None
    json.dumps(result, allow_nan=False)


def test_error_result_reports_total_cost_as_none():
    cost_cube, wait_cube, traversable = _uniform_case()
    traversable[0, 3] = False
    result = _run(cost_cube, wait_cube, traversable)
    assert result["metrics"]["total_cost"] is None


def test_successful_result_is_strict_json_serialisable():
    import json

    result = _run(*_uniform_case())
    assert result["error"] is None
    json.dumps(result, allow_nan=False)


# ── bfs_move_count: exact reachability for horizon sizing and diagnosis ───────


def test_bfs_move_count_on_open_grid_is_chebyshev_distance():
    from app.pathfinder_4d import bfs_move_count

    mask = np.ones((10, 10), dtype=bool)
    assert bfs_move_count(mask, (0, 0), (3, 5)) == 5  # diagonal covers 3, 2 more east


def test_bfs_move_count_is_zero_for_identical_start_and_goal():
    from app.pathfinder_4d import bfs_move_count

    mask = np.ones((4, 4), dtype=bool)
    assert bfs_move_count(mask, (2, 2), (2, 2)) == 0


def test_bfs_move_count_is_none_when_start_is_blocked():
    from app.pathfinder_4d import bfs_move_count

    mask = np.ones((4, 4), dtype=bool)
    mask[0, 0] = False
    assert bfs_move_count(mask, (0, 0), (3, 3)) is None


def test_bfs_move_count_is_none_when_goal_is_blocked():
    from app.pathfinder_4d import bfs_move_count

    mask = np.ones((4, 4), dtype=bool)
    mask[3, 3] = False
    assert bfs_move_count(mask, (0, 0), (3, 3)) is None


def test_bfs_move_count_is_none_when_out_of_bounds():
    from app.pathfinder_4d import bfs_move_count

    mask = np.ones((4, 4), dtype=bool)
    assert bfs_move_count(mask, (0, 0), (9, 9)) is None


def test_bfs_move_count_is_none_across_a_disconnecting_wall():
    from app.pathfinder_4d import bfs_move_count

    mask = np.ones((5, 5), dtype=bool)
    mask[2, :] = False  # a full-width wall with no gap
    assert bfs_move_count(mask, (0, 0), (4, 4)) is None


def test_bfs_move_count_routes_around_a_wall_with_a_gap():
    from app.pathfinder_4d import bfs_move_count

    mask = np.ones((5, 5), dtype=bool)
    mask[2, :] = False
    mask[2, 4] = True  # single gap at the east edge
    distance = bfs_move_count(mask, (0, 0), (4, 0))
    assert distance is not None
    assert distance > 4  # longer than the straight Chebyshev distance of 4


# ── MOVE/WAIT unit parity with the real cube builders (Faz 1-2-3 review, M2) ──
#
# The scenarios above hand-pick cost_cube/wait_cube values (40.0 vs 0.001)
# that prove the WAIT *mechanism* works, but not that it is *calibrated*: on
# the real grid, build_cost_cube's MOVE edges and build_wait_cost_cube's WAIT
# edges came out ~6500x apart in magnitude (MOVE in distance_m * MRU, WAIT in
# dt_hours * MRU), so a real illumination cube could never make waiting
# competitive. These tests build both cubes through the actual production
# functions -- not hand-set numbers -- so a regression that reintroduces the
# unit mismatch fails here even though the mechanism-only tests above
# wouldn't catch it.


def _real_cubes_shadowed_corridor(
    shadow_len: int, n_shadow_slices: int, corridor_len: int
):
    """A corridor whose first *shadow_len* cells are shadowed for the first
    *n_shadow_slices* slices, then lit for the rest of the horizon. Built
    entirely through app.cost_cube's real functions and the default rover,
    not through hand-picked cost values."""
    from app.cost_cube import auto_slice_hours, build_cost_cube, build_wait_cost_cube

    shape = (1, corridor_len)
    rover = get_rover()
    slope = np.full(shape, 3.0)
    thermal = np.full(shape, -60.0)
    traversable = np.ones(shape, dtype=bool)
    base_grids = {
        "slope": slope,
        "thermal": thermal,
        "traversable": traversable,
        "metadata": {"resolution_m": 80.0, "shape": list(shape)},
    }
    n_slices = n_shadow_slices + corridor_len + 2
    shadow_series, illum_series = [], []
    for t in range(n_slices):
        shadow = np.zeros(shape)
        if t < n_shadow_slices:
            shadow[0, 1 : 1 + shadow_len] = 1.0
        shadow_series.append(shadow)
        illum_series.append(1.0 - shadow)

    slice_hours = auto_slice_hours(slope, traversable, 80.0, rover)
    cost_cube = build_cost_cube(base_grids, shadow_series, rover, coarsen=1)
    wait_cube = build_wait_cost_cube(illum_series, rover, slice_hours, coarsen=1)
    return cost_cube, wait_cube, traversable, slope, slice_hours, corridor_len


def test_move_and_wait_edges_are_priced_in_the_same_units_on_real_cubes():
    """A slice of waiting and a slice of driving, both built by the
    production cube builders with the real rover, must be the same order of
    magnitude -- or the planner can never trade one for the other. They
    were ~6500x apart before the unit fix (Faz 1-2-3 review, M2)."""
    cost_cube, wait_cube, _traversable, _slope, slice_hours, _len = (
        _real_cubes_shadowed_corridor(shadow_len=10, n_shadow_slices=3, corridor_len=12)
    )
    finite = cost_cube[np.isfinite(cost_cube)]
    move_per_slice = slice_hours * (1.0 + float(np.mean(finite)))
    wait_per_slice = float(np.mean(wait_cube))
    assert 0.2 < wait_per_slice / move_per_slice < 5.0


def test_real_cubes_let_a_50h_rover_drive_through_a_short_dark_stretch():
    """Round 4 made a cell impassable at any slice its regolith skin was
    under -150 C, so waiting was the ONLY way through ten dark cells -- and
    the same rule closed the whole production grid for the whole lunar
    night. The envelope now lives in the planner's state: LPR-1 has 50 h of
    shadow endurance and 5.4 kWh, so ten dark cells (~1.1 h) are a priced
    crossing, not a wall. Waiting for the Sun is still available; it is no
    longer compulsory. The compulsory case is
    test_a_dark_stretch_longer_than_the_shadow_endurance_forces_a_wait."""
    rover = get_rover()
    c = _corridor(shadow_len=10, n_shadow_slices=3, corridor_len=12, rover=rover)
    forbidden = astar_4d(c["cost_cube"], np.full_like(c["wait_cube"], np.inf), **c["kwargs"])
    assert forbidden["error"] is None
    assert forbidden["metrics"]["wait_steps"] == 0
    assert forbidden["metrics"]["max_continuous_shadow_h"] < rover["h_max_shadow_h"]
    assert forbidden["metrics"]["min_battery_pct"] > rover["soc_min_pct"] * 100.0


# ── The rover's envelope lives in the state: battery and shadow endurance ────
#
# The cube used to close any cell whose regolith skin fell below -150 C, so
# at a lunar-night epoch the entire production grid went impassable within
# 2.5 h and /api/plan-4d answered "no finite cost" for every pair, although
# the catalogue says LPR-1 survives 50 h of darkness. Darkness is now the
# ROVER'S problem: each search label carries battery and continuous shadow
# hours, the same physics wait_cost and the simulator use, and a transition
# that drains below the reserve or outlasts h_max_shadow_h is refused.


def _corridor(shadow_len, n_shadow_slices, corridor_len, rover):
    """_real_cubes_shadowed_corridor, plus the shadow cube the planner now
    reads and a caller-supplied rover so a test can shrink its envelope."""
    from app.cost_cube import (
        auto_slice_hours,
        build_cost_cube,
        build_wait_cost_cube,
    )

    shape = (1, corridor_len)
    slope = np.full(shape, 3.0)
    traversable = np.ones(shape, dtype=bool)
    base_grids = {
        "slope": slope,
        "thermal": np.full(shape, -60.0),
        "traversable": traversable,
        "metadata": {
            "resolution_m": 80.0,
            "shape": list(shape),
            "thermal_field": "sunlit_peak",
        },
    }
    n_slices = n_shadow_slices + corridor_len + 2
    shadow_series = []
    for t in range(n_slices):
        shadow = np.zeros(shape)
        if t < n_shadow_slices:
            shadow[0, 1 : 1 + shadow_len] = 1.0
        shadow_series.append(shadow)
    slice_hours = auto_slice_hours(slope, traversable, 80.0, rover)
    cost_cube = build_cost_cube(
        base_grids, shadow_series, rover, coarsen=1, slice_hours=slice_hours
    )
    wait_cube = build_wait_cost_cube(
        [1.0 - s for s in shadow_series], rover, slice_hours, coarsen=1
    )
    return dict(
        cost_cube=cost_cube,
        wait_cube=wait_cube,
        kwargs=dict(
            traversable=traversable,
            start=(0, 0),
            goal=(0, corridor_len - 1),
            resolution_m=80.0,
            slice_hours=slice_hours,
            rover=rover,
            slope_grid=slope,
            shadow_cube=np.stack(shadow_series, axis=0),
        ),
    )


def test_planner_without_a_shadow_cube_reports_a_full_battery():
    """Callers that predate the envelope (the toy cubes above) get the old
    answer plus an honest profile: nothing drains, nothing is dark."""
    result = _run(*_uniform_case(n_slices=8))
    assert result["error"] is None
    assert result["path_battery_pct"] == [100.0] * len(result["path_states"])
    assert result["path_dark_hours"] == [0.0] * len(result["path_states"])
    assert result["metrics"]["min_battery_pct"] == 100.0
    assert result["metrics"]["max_continuous_shadow_h"] == 0.0


def test_planner_reports_the_battery_and_shadow_profile_along_the_route():
    rover = get_rover()
    c = _corridor(shadow_len=10, n_shadow_slices=0, corridor_len=12, rover=rover)
    result = astar_4d(c["cost_cube"], c["wait_cube"], **c["kwargs"])
    assert result["error"] is None
    states = result["path_states"]
    assert len(result["path_battery_pct"]) == len(states)
    assert len(result["path_dark_hours"]) == len(states)
    assert result["path_battery_pct"][0] == pytest.approx(100.0)
    # A lit corridor: the array outproduces the drive, so nothing is lost.
    assert min(result["path_battery_pct"]) == pytest.approx(100.0)
    assert result["metrics"]["max_continuous_shadow_h"] == 0.0
    assert result["metrics"]["energy_charged_wh"] >= 0.0


def _no_time_to_wait(c, n_slices):
    """The same corridor with the horizon cut to *n_slices*: just enough to
    drive straight through, none to wait (or to shuffle back and forth,
    which an infinite wait cube would not prevent)."""
    kwargs = dict(c["kwargs"])
    kwargs["shadow_cube"] = kwargs["shadow_cube"][:n_slices]
    return c["cost_cube"][:n_slices], c["wait_cube"][:n_slices], kwargs


def test_a_dark_stretch_longer_than_the_shadow_endurance_forces_a_wait():
    """Ten shadowed cells take ~1.1 h to cross and stay dark for 12 slices
    (~1.3 h). A rover that survives only 0.5 h of continuous darkness cannot
    rush them; it has to wait for the Sun -- and when there is no time to
    wait, the refusal is named for what it is."""
    rover = dict(get_rover())
    rover["h_max_shadow_h"] = 0.5
    c = _corridor(shadow_len=10, n_shadow_slices=12, corridor_len=12, rover=rover)

    waited = astar_4d(c["cost_cube"], c["wait_cube"], **c["kwargs"])
    assert waited["error"] is None
    assert waited["metrics"]["wait_steps"] > 0
    assert waited["metrics"]["max_continuous_shadow_h"] <= 0.5

    cost_cut, wait_cut, kwargs_cut = _no_time_to_wait(c, n_slices=13)
    forbidden = astar_4d(cost_cut, wait_cut, **kwargs_cut)
    assert forbidden["error"] is not None
    assert forbidden["metrics"]["edges_rejected"]["shadow_endurance"] > 0
    assert "shadow" in forbidden["error"].lower()


def test_planner_waits_for_sunlight_to_recharge_before_a_dark_crossing():
    """Crossing ten dark cells draws ~330 Wh. With a 150 Wh battery and a
    20 percent reserve that is impossible in the dark, while in sunlight the
    array outproduces the drive -- so the plan is: wait for the Sun."""
    rover = dict(get_rover())
    rover["e_cap_wh"] = 150.0
    c = _corridor(shadow_len=10, n_shadow_slices=12, corridor_len=12, rover=rover)

    waited = astar_4d(c["cost_cube"], c["wait_cube"], **c["kwargs"])
    assert waited["error"] is None
    assert waited["metrics"]["wait_steps"] > 0
    assert waited["metrics"]["min_battery_pct"] >= rover["soc_min_pct"] * 100.0 - 1e-6

    cost_cut, wait_cut, kwargs_cut = _no_time_to_wait(c, n_slices=13)
    forbidden = astar_4d(cost_cut, wait_cut, **kwargs_cut)
    assert forbidden["error"] is not None
    assert forbidden["metrics"]["edges_rejected"]["soc_floor"] > 0
    assert "battery" in forbidden["error"].lower()


def test_a_start_below_the_reserve_may_wait_in_sunlight_to_charge():
    """Starting at 10 percent, under a 20 percent reserve, is not a dead
    end when the start cell is lit: waiting charges, then the route runs."""
    rover = get_rover()
    c = _corridor(shadow_len=0, n_shadow_slices=0, corridor_len=6, rover=rover)
    result = astar_4d(c["cost_cube"], c["wait_cube"], **c["kwargs"], initial_soc_frac=0.10)
    assert result["error"] is None
    assert result["path_battery_pct"][0] == pytest.approx(10.0)
    assert result["path_battery_pct"][-1] > 10.0
    assert result["metrics"]["wait_steps"] >= 0


def test_battery_profile_matches_the_public_drain_functions():
    """The planner integrates the battery with its own inlined arithmetic
    for speed; it must agree exactly with cost_engine's reference functions
    (the ones wait_cost and the simulator use), or the three would drift."""
    from app.cost_engine import (
        edge_travel_time_s,
        move_battery_drain_wh,
        wait_battery_drain_wh,
    )

    rover = dict(get_rover())
    rover["e_cap_wh"] = 400.0  # small enough that the trace actually moves
    c = _corridor(shadow_len=10, n_shadow_slices=12, corridor_len=12, rover=rover)
    result = astar_4d(c["cost_cube"], c["wait_cube"], **c["kwargs"])
    assert result["error"] is None
    assert result["metrics"]["wait_steps"] > 0 or result["metrics"]["move_steps"] > 0

    shadow = c["kwargs"]["shadow_cube"]
    slope = c["kwargs"]["slope_grid"]
    slice_h = c["kwargs"]["slice_hours"]
    states = result["path_states"]
    battery = rover["e_cap_wh"]
    expected = [battery]
    for (r0, c0, t0), (r1, c1, t1) in zip(states[:-1], states[1:]):
        if (r0, c0) == (r1, c1):
            drain = wait_battery_drain_wh(float(shadow[t0, r0, c0]), slice_h, rover)
        else:
            distance = 80.0 * (2 ** 0.5 if (r0 != r1 and c0 != c1) else 1.0)
            edge_slope = 0.5 * (float(slope[r0, c0]) + float(slope[r1, c1]))
            exposure = 0.5 * (float(shadow[t0, r0, c0]) + float(shadow[t1, r1, c1]))
            drain = move_battery_drain_wh(edge_slope, distance, exposure, rover)
            assert edge_travel_time_s(edge_slope, distance, rover) > 0
        battery = min(rover["e_cap_wh"], battery - drain)
        expected.append(battery)
    expected_pct = [100.0 * b / rover["e_cap_wh"] for b in expected]
    assert result["path_battery_pct"] == pytest.approx(expected_pct, abs=1e-3)


def test_rejection_tally_always_carries_the_envelope_keys():
    result = _run(*_uniform_case(n_slices=8))
    tally = result["metrics"]["edges_rejected"]
    assert "soc_floor" in tally and "shadow_endurance" in tally


# ── A4: Direct-to-Earth visibility in the planner ──────────────────────────
#
# VIPER drives only with a link to Earth; it may sit anywhere. So the rule
# is on MOVE arrivals, never on WAIT. The toy strip is 1x4 with cell (0, 2)
# the only way through, which makes "is the rule enforced" unambiguous.


def _earth_cube(n_slices=6, shape=(1, 4)) -> np.ndarray:
    return np.ones((n_slices, *shape), dtype=bool)


def _run_with_earth(earth_cube, require, n_slices=6):
    cost_cube, wait_cube, traversable = _uniform_case(n_slices=n_slices)
    return astar_4d(
        cost_cube,
        wait_cube,
        traversable,
        start=(0, 0),
        goal=(0, 3),
        resolution_m=RES_M,
        slice_hours=SLICE_H,
        rover=get_rover(),
        earth_visible_cube=earth_cube,
        require_earth_visibility=require,
    )


def test_enforced_earth_visibility_refuses_a_move_into_a_cell_with_no_link():
    earth = _earth_cube()
    earth[:, 0, 2] = False  # never a link at the only cell on the way
    result = _run_with_earth(earth, require=True)
    assert result["error"] is not None
    assert "Earth visibility" in result["error"]
    assert result["metrics"]["edges_rejected"]["earth_visibility"] > 0


def test_enforced_earth_visibility_waits_for_the_link_to_open():
    earth = _earth_cube(n_slices=8)
    earth[:3, 0, 2] = False  # link at (0, 2) opens at slice 3
    result = _run_with_earth(earth, require=True, n_slices=8)
    assert result["error"] is None
    assert result["metrics"]["wait_steps"] >= 1
    assert all(result["path_earth_visible"])
    assert result["metrics"]["moves_out_of_earth_view"] == 0
    assert result["metrics"]["earth_visibility_enforced"] is True
    # The state that reaches (0, 2) must sit at slice 3 or later.
    arrival_at_2 = next(t for r, c, t in result["path_states"] if (r, c) == (0, 2))
    assert arrival_at_2 >= 3


def test_unenforced_earth_visibility_is_reported_not_imposed():
    earth = _earth_cube()
    earth[:, 0, 2] = False
    result = _run_with_earth(earth, require=False)
    assert result["error"] is None
    assert result["metrics"]["earth_visibility_enforced"] is False
    assert result["metrics"]["edges_rejected"]["earth_visibility"] == 0
    assert len(result["path_earth_visible"]) == len(result["path_states"])
    visible_at = {
        (r, c): v for (r, c, _t), v in zip(result["path_states"], result["path_earth_visible"])
    }
    assert visible_at[(0, 2)] is False and visible_at[(0, 3)] is True
    assert result["metrics"]["moves_out_of_earth_view"] == 1


def test_waiting_in_a_cell_without_a_link_is_allowed():
    """The rule is on driving, not on sitting: a rover that starts out of
    view may wait there until the link and then move."""
    earth = _earth_cube(n_slices=8)
    earth[:2, :, :] = False  # nothing has a link for the first two slices
    result = _run_with_earth(earth, require=True, n_slices=8)
    assert result["error"] is None
    # A move launched at slice 0 would arrive at slice 1, still without a
    # link; the only legal opening is to wait once and arrive at slice 2.
    assert result["metrics"]["wait_steps"] >= 1
    assert result["path_states"][0] == (0, 0, 0)
    assert all(c == 0 for _r, c, t in result["path_states"] if t < 2)


def test_without_an_earth_cube_nothing_is_reported():
    result = _run(*_uniform_case())
    assert result["path_earth_visible"] is None
    assert result["metrics"]["moves_out_of_earth_view"] is None
    assert result["metrics"]["earth_visibility_enforced"] is False
    assert "earth_visibility" in result["metrics"]["edges_rejected"]


def test_enforcing_without_a_cube_is_an_error_not_a_silent_pass():
    result = _run_with_earth(None, require=True)
    assert result["error"] is not None
    assert "earth_visible_cube" in result["error"]


def test_earth_cube_of_the_wrong_shape_is_refused():
    result = _run_with_earth(np.ones((6, 2, 2), dtype=bool), require=False)
    assert result["error"] is not None
    assert "earth_visible_cube" in result["error"]
