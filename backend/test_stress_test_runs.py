"""Monte Carlo traverse stress test (B5): the vectorised execution of a
route -- the planner's arithmetic, SHERPA's policy, the failure causes and
the margins -- and the summary the endpoint publishes."""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.constants import get_rover
from app.cost_engine import (
    edge_travel_time_s,
    housekeeping_power_w,
    move_battery_drain_wh,
    wait_battery_drain_wh,
)
from app.stress_test import (
    FAILURE_NAMES,
    RouteSky,
    RunResults,
    route_legs,
    simulate_runs,
)

RES_M = 80.0


def _rover(**overrides):
    rover = dict(get_rover("lpr_1"))
    rover.update(overrides)
    return rover


def _legs(states, rover, slice_hours, slope=3.0, shape=(1, 4)):
    return route_legs(states, np.full(shape, slope), RES_M, rover, slice_hours)


def _static_sky(shadow_per_state, n_slices, slice_hours, earth=None, deadline=None, tts=None):
    shadow = np.tile(np.asarray(shadow_per_state, dtype=float), (n_slices, 1))
    return RouteSky(shadow, earth, deadline, tts, slice_hours, time_varying=False)


def _samples(n=1, delay=0.0, speed=1.0, power=1.0, soc=1.0, dsn=None, sep=None):
    """Hand-built perturbation draws for *n* identical runs."""
    def _arr(value):
        return np.full(n, float(value))

    def _window(window):
        if window is None:
            return np.zeros(n, dtype=bool), _arr(np.nan), _arr(np.nan)
        return np.ones(n, dtype=bool), _arr(window[0]), _arr(window[1])

    dsn_event, dsn_start, dsn_end = _window(dsn)
    sep_event, sep_start, sep_end = _window(sep)
    return {
        "start_delay_h": _arr(delay),
        "speed_multiplier": _arr(speed),
        "power_multiplier": _arr(power),
        "initial_soc_frac": _arr(soc),
        "dsn_event": dsn_event,
        "dsn_start_h": dsn_start,
        "dsn_end_h": dsn_end,
        "sep_event": sep_event,
        "sep_start_h": sep_start,
        "sep_end_h": sep_end,
    }


def _travel_h(rover, slope=3.0, distance=RES_M):
    return edge_travel_time_s(slope, distance, rover) / 3600.0


# ── The nominal run is the planner's own accounting ───────────────────────


def test_the_nominal_run_reproduces_the_planners_battery_and_schedule():
    """MOVE, WAIT, MOVE on a static sky: the battery after each state is
    what cost_engine's signed drains (the planner's reference) give, and
    the departures sit on the planned slices."""
    rover = _rover()
    h = 1.0
    legs = _legs([(0, 0, 0), (0, 1, 1), (0, 1, 2), (0, 2, 3)], rover, h)
    sky = _static_sky([0.2, 0.7, 0.9, 0.0], 6, h)
    out = simulate_runs(legs, sky, rover, _samples())
    assert isinstance(out, RunResults)
    assert out.reached.tolist() == [True]
    assert FAILURE_NAMES[out.first_failure[0]] == "none"

    cap = float(rover["e_cap_wh"])
    travel = _travel_h(rover)
    expected = [cap]
    # Leg 0: MOVE (0,0)->(0,1), departs at 0, exposure 0.45 (trapezoid).
    b = min(cap, cap - move_battery_drain_wh(3.0, RES_M, 0.45, rover))
    expected.append(b)
    # Arrived at travel < 1 h: ahead, holds at (0,1) until the planned
    # departure of leg 1 (= planned end of the WAIT, 2 h). One hold of
    # 2 - travel hours in shadow 0.7.
    b = min(cap, b - wait_battery_drain_wh(0.7, 2.0 - travel, rover))
    expected.append(b)
    # Leg 2: MOVE from state 2 (exposure 0.9) to state 3 (0.0), departs at
    # 2 h: the trapezoid over the two STATE columns, (0.9 + 0.0) / 2.
    b = min(cap, b - move_battery_drain_wh(3.0, RES_M, 0.45, rover))
    expected.append(b)
    np.testing.assert_allclose(out.battery_wh[:, 0], expected, atol=1e-6)
    np.testing.assert_allclose(out.arrival_h[:, 0], [0.0, travel, 2.0, 2.0 + travel], atol=1e-9)
    assert out.duration_h[0] == pytest.approx(2.0 + travel)
    assert out.odometry_m[0] == pytest.approx(2 * RES_M)
    assert out.final_battery_wh[0] == pytest.approx(expected[-1])
    assert out.min_battery_wh[0] == pytest.approx(min(expected))


def test_the_nominal_run_matches_astar_4d_on_its_own_static_cube():
    from test_pathfinder_4d import _corridor
    from app.pathfinder_4d import astar_4d

    rover = _rover(e_cap_wh=400.0)
    # Three dark cells for 40 slices -- longer than the route takes, so the
    # cube is static over the plan and the planner drives through rather
    # than waiting three hours.
    c = _corridor(shadow_len=3, n_shadow_slices=40, corridor_len=8, rover=rover)
    result = astar_4d(c["cost_cube"], c["wait_cube"], **c["kwargs"])
    assert result["error"] is None
    cube = c["kwargs"]["shadow_cube"]
    legs = route_legs(
        result["path_states"], c["kwargs"]["slope_grid"], 80.0, rover, c["kwargs"]["slice_hours"]
    )
    sky = RouteSky.from_cubes(
        cube, None, None, None, legs.cells, c["kwargs"]["slice_hours"], time_varying=False
    )
    out = simulate_runs(legs, sky, rover, _samples())
    planner_pct = np.asarray(result["path_battery_pct"])
    np.testing.assert_allclose(100.0 * out.battery_wh[:, 0] / 400.0, planner_pct, atol=2e-3)
    assert out.reached[0]


# ── The multipliers scale exactly their own terms ─────────────────────────


def test_power_scales_the_draw_and_speed_scales_the_time():
    rover = _rover()
    h = 1.0
    legs = _legs([(0, 0, 0), (0, 1, 1)], rover, h)
    # 0.6 shadow: the drive drains (in lighter shade LPR-1's array would
    # outproduce it and the cap at capacity would hide the arithmetic).
    sky = _static_sky([0.6, 0.6], 8, h)
    samples = _samples(n=3)
    samples["power_multiplier"] = np.array([1.0, 1.5, 1.0])
    samples["speed_multiplier"] = np.array([1.0, 1.0, 0.5])
    out = simulate_runs(legs, sky, rover, samples)

    cap = float(rover["e_cap_wh"])
    travel = _travel_h(rover)
    traction = float(legs.traction_w[0])
    hk = housekeeping_power_w(0.6, rover)
    solar = float(rover["p_solar_w"]) * 0.4
    nominal = (traction + hk - solar) * travel
    power = (1.5 * traction + 1.5 * hk - solar) * travel
    slow = (traction + hk - solar) * 2.0 * travel
    np.testing.assert_allclose(cap - out.battery_wh[1], [nominal, power, slow], atol=1e-6)
    np.testing.assert_allclose(out.arrival_h[1], [travel, travel, 2.0 * travel], atol=1e-9)


def test_the_initial_soc_sample_sets_the_starting_battery():
    rover = _rover()
    legs = _legs([(0, 0, 0), (0, 1, 1)], rover, 1.0)
    sky = _static_sky([1.0, 1.0], 4, 1.0)
    out = simulate_runs(legs, sky, rover, _samples(soc=0.6))
    assert out.battery_wh[0, 0] == pytest.approx(0.6 * float(rover["e_cap_wh"]))


# ── SHERPA's policy ────────────────────────────────────────────────────────


def test_behind_schedule_the_rover_skips_its_wait_and_drives_on():
    rover = _rover()
    h = 2.0
    legs = _legs([(0, 0, 0), (0, 0, 1), (0, 1, 2)], rover, h)
    sky = _static_sky([0.0, 0.0, 0.0], 8, h)
    out = simulate_runs(legs, sky, rover, _samples(delay=3.0))
    travel = _travel_h(rover)
    # The wait was planned to end at 2 h; the rover reached the start at
    # 3 h, so the wait is skipped and the move (planned at 2 h) leaves at 3 h.
    np.testing.assert_allclose(out.arrival_h[:, 0], [3.0, 3.0, 3.0 + travel], atol=1e-9)
    assert out.reached[0]


def test_ahead_of_schedule_the_rover_holds_until_its_planned_departure():
    rover = _rover()
    h = 1.0
    legs = _legs([(0, 0, 0), (0, 1, 3), (0, 2, 6)], rover, h)
    sky = _static_sky([0.0, 1.0, 0.0], 10, h)
    out = simulate_runs(legs, sky, rover, _samples())
    travel = _travel_h(rover)
    np.testing.assert_allclose(out.arrival_h[:, 0], [0.0, travel, 3.0 + travel], atol=1e-9)
    # The hold at (0,1) from `travel` to 3 h is spent in full shadow and
    # drains the battery by the planner's wait drain.
    cap = float(rover["e_cap_wh"])
    after_move = min(cap, cap - move_battery_drain_wh(3.0, RES_M, 0.5, rover))
    held = after_move - wait_battery_drain_wh(1.0, 3.0 - travel, rover)
    after_second = min(cap, held - move_battery_drain_wh(3.0, RES_M, 0.5, rover))
    assert out.battery_wh[2, 0] == pytest.approx(after_second, abs=1e-6)
    # The continuous-shadow clock counted the arrival in the dark cell and
    # the hold there (travel + (3 - travel) = 3 h), then reset on arriving
    # in the lit cell.
    assert out.max_dark_h[0] == pytest.approx(3.0, abs=1e-9)


def test_an_outage_window_delays_the_departure_it_covers():
    rover = _rover()
    h = 1.0
    legs = _legs([(0, 0, 0), (0, 1, 1)], rover, h)
    sky = _static_sky([0.0, 0.0], 8, h)
    out = simulate_runs(legs, sky, rover, _samples(dsn=(0.0, 1.5)))
    travel = _travel_h(rover)
    np.testing.assert_allclose(out.arrival_h[:, 0], [0.0, 1.5 + travel], atol=1e-9)
    assert out.dsn_hold_h[0] == pytest.approx(1.5)
    assert out.sep_hold_h[0] == 0.0
    # A window that does not cover the departure changes nothing.
    out = simulate_runs(legs, sky, rover, _samples(sep=(0.5, 2.0)))
    np.testing.assert_allclose(out.arrival_h[:, 0], [0.0, travel], atol=1e-9)
    assert out.sep_hold_h[0] == 0.0


# ── Failure causes ─────────────────────────────────────────────────────────


def test_a_dark_drive_with_a_tiny_battery_ends_in_battery_depleted():
    rover = _rover(e_cap_wh=5.0)
    legs = _legs([(0, 0, 0), (0, 1, 1), (0, 2, 2)], rover, 1.0)
    sky = _static_sky([1.0, 1.0, 1.0], 6, 1.0)
    out = simulate_runs(legs, sky, rover, _samples())
    assert not out.reached[0]
    assert FAILURE_NAMES[out.first_failure[0]] == "battery_depleted"
    # Died on the first move: no state after the start is reached.
    assert out.alive[:, 0].tolist() == [True, False, False]
    assert np.isnan(out.arrival_h[1, 0]) and np.isnan(out.battery_wh[2, 0])
    assert out.odometry_m[0] == 0.0
    assert out.duration_h[0] == pytest.approx(_travel_h(rover))


def test_a_dark_drive_past_the_shadow_endurance_ends_in_shadow_endurance():
    rover = _rover(h_max_shadow_h=0.05)
    legs = _legs([(0, 0, 0), (0, 1, 1)], rover, 1.0)
    sky = _static_sky([1.0, 1.0], 6, 1.0)
    out = simulate_runs(legs, sky, rover, _samples())
    assert not out.reached[0]
    assert FAILURE_NAMES[out.first_failure[0]] == "shadow_endurance"


def test_battery_is_the_first_cause_when_both_fail_on_one_leg():
    rover = _rover(e_cap_wh=5.0, h_max_shadow_h=0.05)
    legs = _legs([(0, 0, 0), (0, 1, 1)], rover, 1.0)
    sky = _static_sky([1.0, 1.0], 6, 1.0)
    out = simulate_runs(legs, sky, rover, _samples())
    assert FAILURE_NAMES[out.first_failure[0]] == "battery_depleted"


def test_a_run_that_outlasts_the_sky_ends_in_horizon_exceeded():
    rover = _rover()
    legs = _legs([(0, 0, 0), (0, 1, 1)], rover, 1.0)
    sky = _static_sky([0.0, 0.0], 1, 1.0)  # a one-hour sky
    out = simulate_runs(legs, sky, rover, _samples(speed=0.05))
    assert not out.reached[0]
    assert FAILURE_NAMES[out.first_failure[0]] == "horizon_exceeded"


def test_the_reserve_breach_is_a_flag_not_a_failure():
    rover = _rover(e_cap_wh=60.0, soc_min_pct=0.5)
    legs = _legs([(0, 0, 0), (0, 1, 1)], rover, 1.0)
    sky = _static_sky([1.0, 1.0], 6, 1.0)
    out = simulate_runs(legs, sky, rover, _samples())
    assert out.reached[0]
    assert out.reserve_breached[0]
    assert not simulate_runs(legs, sky, _rover(e_cap_wh=6000.0), _samples()).reserve_breached[0]


# ── SHERPA's margins ───────────────────────────────────────────────────────


def _margin_case():
    """Cells A (state 0) and B (states 1-3). B goes dark at 2 h and loses
    its Earth link at 2 h; A is lit and linked throughout. Route: A -> B at
    slice 1, then two planned waits at B."""
    rover = _rover()
    h = 1.0
    legs = _legs([(0, 0, 0), (0, 1, 1), (0, 1, 2), (0, 1, 3)], rover, h)
    shadow = np.zeros((6, 4))
    shadow[2:, 1:] = 1.0
    earth = np.ones((6, 4), dtype=bool)
    earth[2:, 1:] = False
    deadline = np.zeros((6, 4))
    deadline[:, 0] = np.inf
    deadline[0, 1:] = 2.0
    deadline[1, 1:] = 1.0
    tts = np.array([0.0, 5.0, 5.0, 5.0])
    sky = RouteSky(shadow, earth, deadline, tts, h, time_varying=True)
    return rover, legs, sky


def test_margins_are_read_along_the_actual_timeline():
    rover, legs, sky = _margin_case()
    out = simulate_runs(legs, sky, rover, _samples())
    travel = _travel_h(rover)
    # Arrivals: 0, travel, 2, 3.
    np.testing.assert_allclose(out.arrival_h[:, 0], [0.0, travel, 2.0, 3.0], atol=1e-9)
    # time-to-sun-shadow: A never goes dark (open-ended, not counted); B at
    # `travel` has 2 - travel hours left; at 2 and 3 h it is dark (0).
    assert out.tts_sun_min_h[0] == pytest.approx(0.0)
    assert out.tts_sun_mean_h[0] == pytest.approx((2.0 - travel + 0.0 + 0.0) / 3.0)
    # time-to-DSN-shadow: the link at B has 2 - travel hours left on arrival.
    assert out.tts_dsn_min_h[0] == pytest.approx(0.0)
    # time-to-0-SOC: battery over the dark housekeeping draw, at its lowest.
    dark_w = housekeeping_power_w(1.0, rover)
    assert out.tts_zero_soc_min_h[0] == pytest.approx(float(out.min_battery_wh[0]) / dark_w)
    # One DSN shadow event (linked at `travel`, unlinked at 2 h), one hour
    # spent unlinked between the states at 2 h and 3 h.
    assert out.dsn_events[0] == 1
    assert out.dsn_shadow_h[0] == pytest.approx(1.0)
    # Haven rule: 5 h to the nearest haven against 2 - travel, 0 and 0 hours
    # of link -- three states past the deadline.
    assert out.states_past_deadline[0] == 3


def test_margins_are_open_ended_without_the_earth_and_haven_fields():
    rover = _rover()
    legs = _legs([(0, 0, 0), (0, 1, 1)], rover, 1.0)
    sky = _static_sky([0.0, 0.0], 4, 1.0)
    out = simulate_runs(legs, sky, rover, _samples())
    assert np.isnan(out.tts_sun_min_h[0]) and np.isnan(out.tts_sun_mean_h[0])
    assert np.isnan(out.tts_dsn_min_h[0])
    assert np.isnan(out.states_past_deadline[0])
    assert out.dsn_events[0] == 0 and out.dsn_shadow_h[0] == 0.0


def test_many_runs_are_vectorised_and_reproducible():
    from app.stress_test import sample_perturbations

    rover = _rover(e_cap_wh=300.0)
    legs = _legs([(0, i, i) for i in range(8)], rover, 0.2, shape=(1, 8))
    sky = _static_sky([0.6] * 8, 40, 0.2)
    a = simulate_runs(
        legs, sky, rover, sample_perturbations(np.random.default_rng(3), 500, planned_end_h=1.4)
    )
    b = simulate_runs(
        legs, sky, rover, sample_perturbations(np.random.default_rng(3), 500, planned_end_h=1.4)
    )
    assert a.reached.shape == (500,)
    assert a.battery_wh.shape == (8, 500)
    np.testing.assert_array_equal(a.duration_h, b.duration_h)
    # Slower and hungrier runs take longer and end lower than the nominal.
    nominal = simulate_runs(legs, sky, rover, _samples())
    assert float(np.median(a.duration_h)) > float(nominal.duration_h[0])
    assert float(np.median(a.final_battery_wh)) < float(nominal.final_battery_wh[0])



# ── Task 4: the summary and the top-level entry point ─────────────────────

from app.stress_test import (  # noqa: E402
    Perturbations,
    sample_perturbations,
    stress_test_route,
    summarize_runs,
    wilson_interval,
)


def _row_case(n_states=8, e_cap=300.0, shadow=0.6, earth=False):
    rover = _rover(e_cap_wh=e_cap)
    legs = _legs([(0, i, i) for i in range(n_states)], rover, 0.2, shape=(1, n_states))
    n_slices = 60
    earth_cols = None
    deadline = None
    tts = None
    if earth:
        earth_cols = np.ones((n_slices, n_states), dtype=bool)
        earth_cols[30:, :] = False
        deadline = np.where(
            earth_cols, (30 - np.arange(n_slices))[:, None] * 0.2, 0.0
        ).astype(float)
        tts = np.zeros(n_states)
        tts[-1] = 0.0
    sky = RouteSky(
        np.full((n_slices, n_states), shadow), earth_cols, deadline, tts, 0.2, time_varying=earth
    )
    return rover, legs, sky


def _summary(n=200, seed=5, earth=False, perturbations=None):
    rover, legs, sky = _row_case(earth=earth)
    samples = sample_perturbations(
        np.random.default_rng(seed),
        n,
        perturbations or Perturbations(),
        1.0,
        legs.planned_duration_h,
    )
    results = simulate_runs(legs, sky, rover, samples)
    return summarize_runs(results, legs, sky, rover, samples, n_bins=10), results


def test_summary_rates_count_the_runs_and_carry_wilson_intervals():
    summary, results = _summary()
    n = results.n_runs
    completion = summary["rates"]["completion"]
    assert completion["count"] == int(results.reached.sum())
    assert completion["rate"] == pytest.approx(completion["count"] / n)
    lo, hi = completion["ci95"]
    assert 0.0 <= lo <= completion["rate"] <= hi <= 1.0
    # The summary rounds to four decimals.
    assert (lo, hi) == pytest.approx(wilson_interval(completion["count"], n), abs=1e-4)
    assert set(summary["rates"]) == {
        "completion", "reached_within_reserve", "full_success", "reserve_breached"
    }
    # Three nested levels: reached; reached without touching the reserve;
    # and, on top, the haven rule where it is known.
    within = summary["rates"]["reached_within_reserve"]
    assert within["count"] == int((results.reached & ~results.reserve_breached).sum())
    assert summary["rates"]["full_success"]["count"] <= within["count"] <= completion["count"]
    # Every run either reached the goal or has exactly one first cause.
    failures = summary["failures"]
    assert set(failures) == {"battery_depleted", "shadow_endurance", "horizon_exceeded"}
    assert sum(failures.values()) + completion["count"] == n


def test_summary_metrics_are_percentiles_over_finite_values_and_null_when_none():
    summary, results = _summary()
    duration = summary["metrics"]["duration_h"]
    assert set(duration) == {"mean", "std", "p5", "p50", "p95", "min", "max", "n"}
    assert duration["n"] == results.n_runs
    assert duration["min"] <= duration["p5"] <= duration["p50"] <= duration["p95"] <= duration["max"]
    assert duration["p50"] == pytest.approx(float(np.median(results.duration_h)), abs=1e-4)
    assert summary["metrics"]["duration_normalized"]["p50"] == pytest.approx(
        duration["p50"] / summary["route"]["planned_duration_h"], abs=1e-3
    )
    # No Earth series: the DSN margin is unknown, not zero.
    assert summary["metrics"]["time_to_dsn_shadow_min_h"] is None
    assert summary["metrics"]["states_past_haven_deadline"] is None
    assert summary["verdict"]["haven_rule_known"] is False
    # A static 0.6 shadow counts as dark now: time-to-sun-shadow is zero,
    # not unknown.
    assert summary["metrics"]["time_to_sun_shadow_min_h"]["max"] == 0.0
    # Battery percentages are clipped at zero for the depleted runs.
    assert summary["metrics"]["min_battery_pct"]["min"] >= 0.0
    # The sampled inputs are reported too, so a reader can see the draws.
    for key in ("start_delay_h", "speed_multiplier", "power_multiplier", "initial_soc_pct"):
        assert summary["metrics"][key]["n"] == results.n_runs
    assert summary["metrics"]["initial_soc_pct"]["max"] <= 100.0


def test_summary_histograms_and_per_state_envelope_have_the_right_shapes():
    summary, results = _summary()
    hist = summary["histograms"]["duration_h"]
    assert len(hist["edges"]) == 11 and len(hist["counts"]) == 10
    assert sum(hist["counts"]) == results.n_runs
    assert "time_to_dsn_shadow_min_h" not in summary["histograms"]
    per_state = summary["per_state"]
    n_states = summary["route"]["n_states"]
    for key in ("p5", "p50", "p95"):
        assert len(per_state["arrival_h"][key]) == n_states
        assert len(per_state["battery_pct"][key]) == n_states
    assert per_state["alive_fraction"][0] == 1.0
    assert per_state["alive_fraction"][-1] == pytest.approx(summary["rates"]["completion"]["rate"])
    assert per_state["arrival_h"]["p50"][0] == pytest.approx(
        float(np.median(results.arrival_h[0])), abs=1e-4
    )


def test_summary_reports_the_earth_margins_and_the_haven_verdict_when_known():
    summary, results = _summary(earth=True)
    assert summary["metrics"]["time_to_dsn_shadow_min_h"]["n"] > 0
    assert summary["metrics"]["dsn_shadow_events"]["n"] == results.n_runs
    assert summary["metrics"]["states_past_haven_deadline"]["n"] == results.n_runs
    assert summary["route"]["ends_at_safe_haven"] is True
    assert summary["verdict"]["haven_rule_known"] is True
    full = summary["rates"]["full_success"]
    assert full["count"] == int(
        (results.reached & ~results.reserve_breached & (results.states_past_deadline == 0)).sum()
    )


def test_summary_counts_the_injected_outages():
    summary, results = _summary(
        perturbations=Perturbations(dsn_outage_probability=0.5, dsn_outage_mean_h=0.5)
    )
    dsn = summary["outages"]["dsn"]
    assert 60 < dsn["runs"] < 140
    assert dsn["mean_window_h"] > 0.0
    assert dsn["mean_hold_h"] >= 0.0
    assert summary["outages"]["sep"] == {"runs": 0, "mean_window_h": None, "mean_hold_h": None}


def test_the_verdict_needs_the_wilson_lower_bound_above_95_percent():
    rover, legs, sky = _row_case(e_cap=6000.0)
    calm = Perturbations(
        start_delay_sigma_h=0.0, initial_soc_sigma=0.0, power_draw_sigma=0.0, speed_sigma=0.0
    )
    small = stress_test_route(legs, sky, rover, 1.0, n_runs=20, seed=0, perturbations=calm)
    large = stress_test_route(legs, sky, rover, 1.0, n_runs=100, seed=0, perturbations=calm)
    assert small["rates"]["completion"]["rate"] == 1.0
    assert small["verdict"]["reaches_goal_at_95pct"] is False  # 20/20: lower bound 0.84
    assert large["verdict"]["reaches_goal_at_95pct"] is True  # 100/100: lower bound 0.96
    assert "100/100" in large["verdict"]["text"]


def test_stress_test_route_is_reproducible_and_carries_the_nominal_run():
    rover, legs, sky = _row_case()
    a = stress_test_route(legs, sky, rover, 1.0, n_runs=50, seed=11)
    b = stress_test_route(legs, sky, rover, 1.0, n_runs=50, seed=11)
    c = stress_test_route(legs, sky, rover, 1.0, n_runs=50, seed=12)
    a.pop("timing_ms"); b.pop("timing_ms"); c.pop("timing_ms")
    assert a == b
    assert a != c
    assert a["n_runs"] == 50 and a["seed"] == 11
    assert a["perturbations"]["speed_sigma"] == 0.2
    assert "Shirley" in a["perturbations"]["source"]
    nominal = a["nominal"]
    assert nominal["reached"] is True
    assert nominal["duration_h"] == pytest.approx(legs.planned_duration_h, abs=0.2)
    assert nominal["final_battery_pct"] <= 100.0
    assert a["route"]["move_steps"] == 7 and a["route"]["wait_steps"] == 0
    # JSON-safe: no NaN or inf anywhere.
    import json
    json.dumps(a, allow_nan=False)


def test_a_single_run_is_a_valid_stress_test():
    rover, legs, sky = _row_case()
    one = stress_test_route(legs, sky, rover, 1.0, n_runs=1, seed=3)
    assert one["rates"]["completion"]["count"] in (0, 1)
    assert one["metrics"]["duration_h"]["n"] == 1
    assert one["metrics"]["duration_h"]["std"] == 0.0


# ── B1: Poisson mobility faults as an event window ────────────────────────────

from dataclasses import replace as dataclass_replace  # noqa: E402

from app.stress_test import SHERPA_DEFAULTS  # noqa: E402


def test_no_fault_rate_keeps_sherpa_bit_identical():
    rover, legs, sky = _row_case()
    a = stress_test_route(legs, sky, rover, 1.0, n_runs=200, seed=3)
    b = stress_test_route(
        legs, sky, rover, 1.0, n_runs=200, seed=3,
        perturbations=dataclass_replace(SHERPA_DEFAULTS, fault_rate_per_km=0.0),
    )
    a.pop("timing_ms")
    b.pop("timing_ms")
    assert a == b
    assert a["faults"]["runs_with_fault"] == 0 and a["faults"]["rate_per_km"] == 0.0
    assert a["faults"]["recovery_h"] == 10.0 and a["faults"]["source"].startswith("assumption:")
    assert SHERPA_DEFAULTS.fault_rate_per_km == 0.0 and SHERPA_DEFAULTS.fault_recovery_h == 10.0


def test_fault_count_is_poisson_in_route_distance():
    rover, legs, sky = _row_case()
    p = dataclass_replace(SHERPA_DEFAULTS, fault_rate_per_km=2.0, fault_recovery_h=0.5)
    distance = float(legs.distance_m.sum())
    samples = sample_perturbations(
        np.random.default_rng(0), 5000, p, 1.0, legs.planned_duration_h, route_distance_m=distance
    )
    expected = 2.0 * distance / 1000.0
    assert samples["fault_count"].mean() == pytest.approx(expected, rel=0.1)
    assert samples["fault_positions_m"].shape[0] == 5000
    assert np.nanmax(samples["fault_positions_m"]) <= distance
    assert (np.isnan(samples["fault_positions_m"]).sum(axis=1) == samples["fault_positions_m"].shape[1] - samples["fault_count"]).all()
    none = sample_perturbations(np.random.default_rng(0), 10, SHERPA_DEFAULTS, 1.0, 1.0, route_distance_m=distance)
    assert none["fault_count"].sum() == 0 and none["fault_positions_m"].shape == (10, 1)


def test_a_first_half_fault_holds_at_the_origin_and_a_second_half_fault_at_the_destination():
    """Three 80 m moves with the slice equal to one move, so the plan has no
    slack; cell 1 is lit and cell 2 dark. A fault at 100 m (first half of
    the second leg) holds 2 h in lit cell 1 at idle power; one at 150 m
    (second half) holds 2 h in dark cell 2 with the heater on."""
    rover = _rover(p_solar_w=0.0)
    h = _travel_h(rover)
    states = [(0, 0, 0), (0, 1, 1), (0, 2, 2), (0, 3, 3)]
    legs = _legs(states, rover, h)
    sky = _static_sky([0.0, 0.0, 1.0, 0.0], 400, h)
    base = simulate_runs(legs, sky, rover, _samples())

    first = _samples()
    first["fault_positions_m"] = np.array([[100.0]])
    first["fault_count"] = np.array([1])
    a = simulate_runs(legs, sky, rover, first, fault_recovery_h=2.0)
    assert a.fault_count[0] == 1 and a.fault_hold_h[0] == pytest.approx(2.0)
    assert a.duration_h[0] == pytest.approx(base.duration_h[0] + 2.0)
    assert base.final_battery_wh[0] - a.final_battery_wh[0] == pytest.approx(rover["p_idle_w"] * 2.0)

    second = _samples()
    second["fault_positions_m"] = np.array([[150.0]])
    second["fault_count"] = np.array([1])
    b = simulate_runs(legs, sky, rover, second, fault_recovery_h=2.0)
    assert b.duration_h[0] == pytest.approx(base.duration_h[0] + 2.0)
    assert base.final_battery_wh[0] - b.final_battery_wh[0] == pytest.approx(rover["p_shadow_w"] * 2.0)
    assert b.max_dark_h[0] > base.max_dark_h[0]
    assert a.reached[0] and b.reached[0]


def test_stress_test_route_reports_the_faults_it_injected():
    rover, legs, sky = _row_case()
    p = Perturbations(
        start_delay_sigma_h=0.0, initial_soc_sigma=0.0, power_draw_sigma=0.0, speed_sigma=0.0,
        fault_rate_per_km=5.0, fault_recovery_h=0.25,
    )
    out = stress_test_route(legs, sky, rover, 1.0, n_runs=400, seed=1, perturbations=p)
    faults = out["faults"]
    assert faults["rate_per_km"] == 5.0 and faults["recovery_h"] == 0.25
    assert 0 < faults["runs_with_fault"] < 400
    assert faults["mean_faults"] == pytest.approx(5.0 * legs.odometry_m / 1000.0, rel=0.25)
    assert faults["mean_hold_h"] == pytest.approx(0.25 * faults["mean_faults"], rel=1e-6)
    assert out["metrics"]["fault_hold_h"]["max"] >= 0.25
    assert out["nominal"]["duration_h"] == pytest.approx(legs.planned_duration_h, abs=0.2)  # the nominal run has no fault
    assert out["perturbations"]["fault_rate_per_km"] == 5.0
