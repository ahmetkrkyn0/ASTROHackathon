"""Monte Carlo traverse stress test (B5): SHERPA's distributions, the
execution policy and the metric set, on synthetic routes and skies."""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.constants import get_rover
from app.stress_test import (
    SHERPA_DEFAULTS,
    Perturbations,
    sample_perturbations,
    wilson_interval,
)


# ── Task 1: SHERPA's truncated Gaussians and the Wilson interval ───────────


def _samples(perturbations=SHERPA_DEFAULTS, n=2000, seed=1, soc=1.0, end_h=10.0):
    return sample_perturbations(
        np.random.default_rng(seed), n, perturbations, soc, end_h
    )


def test_defaults_are_sherpas_numbers():
    assert SHERPA_DEFAULTS.start_delay_sigma_h == 2.0
    assert SHERPA_DEFAULTS.initial_soc_sigma == 0.20
    assert SHERPA_DEFAULTS.power_draw_sigma == 0.20
    assert SHERPA_DEFAULTS.speed_sigma == 0.20
    assert SHERPA_DEFAULTS.dsn_outage_probability == 0.0
    assert SHERPA_DEFAULTS.sep_event_probability == 0.0


def test_samples_point_in_sherpas_directions_and_stay_inside_the_truncation():
    s = _samples()
    # Start time: delay only, at most z_max sigma.
    assert np.all(s["start_delay_h"] >= 0.0)
    assert np.max(s["start_delay_h"]) <= 3.0 * 2.0 + 1e-9
    assert np.std(s["start_delay_h"]) > 0.5
    # Speed: never faster than planned, never below 1 - z_max sigma.
    assert np.all(s["speed_multiplier"] <= 1.0)
    assert np.all(s["speed_multiplier"] >= 1.0 - 3.0 * 0.2 - 1e-9)
    # Power draw: never below CBE.
    assert np.all(s["power_multiplier"] >= 1.0)
    assert np.max(s["power_multiplier"]) <= 1.0 + 3.0 * 0.2 + 1e-9
    # Battery: never above the nominal state of charge.
    assert np.all(s["initial_soc_frac"] <= 1.0)
    assert np.all(s["initial_soc_frac"] >= 1.0 - 3.0 * 0.2 - 1e-9)
    # A half-normal with sigma 2 has mean 2*sqrt(2/pi) ~ 1.6 before truncation.
    assert 1.3 < float(np.mean(s["start_delay_h"])) < 1.9


def test_z_max_truncates_every_distribution():
    s = _samples(Perturbations(z_max=1.0))
    assert np.max(s["start_delay_h"]) <= 2.0 + 1e-9
    assert np.min(s["speed_multiplier"]) >= 0.8 - 1e-9
    assert np.max(s["power_multiplier"]) <= 1.2 + 1e-9
    assert np.min(s["initial_soc_frac"]) >= 0.8 - 1e-9


def test_the_speed_multiplier_floor_binds_at_sherpas_50_percent_sigma():
    s = _samples(Perturbations(speed_sigma=0.5))
    assert np.min(s["speed_multiplier"]) >= 0.25 - 1e-9
    # ...and the floor is actually reached, not just respected.
    assert np.min(s["speed_multiplier"]) < 0.3


def test_the_initial_soc_scales_with_the_requested_state_of_charge():
    s = _samples(soc=0.5)
    assert np.all(s["initial_soc_frac"] <= 0.5 + 1e-12)
    assert np.all(s["initial_soc_frac"] > 0.0)


def test_the_same_seed_reproduces_the_samples_and_another_does_not():
    a = _samples(seed=7)
    b = _samples(seed=7)
    c = _samples(seed=8)
    for key in a:
        np.testing.assert_array_equal(a[key], b[key])
    assert not np.array_equal(a["start_delay_h"], c["start_delay_h"])


def test_zero_sigmas_give_the_nominal_run_exactly():
    s = _samples(
        Perturbations(
            start_delay_sigma_h=0.0,
            initial_soc_sigma=0.0,
            power_draw_sigma=0.0,
            speed_sigma=0.0,
        ),
        n=5,
    )
    assert np.all(s["start_delay_h"] == 0.0)
    assert np.all(s["speed_multiplier"] == 1.0)
    assert np.all(s["power_multiplier"] == 1.0)
    assert np.all(s["initial_soc_frac"] == 1.0)


def test_outages_are_absent_at_probability_zero_and_present_at_one():
    none = _samples(n=50)
    assert not np.any(none["dsn_event"])
    assert not np.any(none["sep_event"])
    assert np.all(np.isnan(none["dsn_start_h"]))
    assert np.all(np.isnan(none["sep_end_h"]))

    always = _samples(
        Perturbations(
            dsn_outage_probability=1.0,
            dsn_outage_mean_h=4.0,
            sep_event_probability=1.0,
            sep_event_mean_h=24.0,
        ),
        n=2000,
        end_h=10.0,
    )
    assert np.all(always["dsn_event"])
    assert np.all(always["sep_event"])
    # Starts inside the planned window, ends after they start.
    assert np.all(always["dsn_start_h"] >= 0.0)
    assert np.all(always["dsn_start_h"] <= 10.0)
    assert np.all(always["dsn_end_h"] >= always["dsn_start_h"])
    dsn_hours = always["dsn_end_h"] - always["dsn_start_h"]
    sep_hours = always["sep_end_h"] - always["sep_start_h"]
    # Truncated at zero with sigma = mean / 2, the mean sits a little above
    # the nominal value.
    assert 3.5 < float(np.mean(dsn_hours)) < 5.0
    assert 21.0 < float(np.mean(sep_hours)) < 30.0


def test_a_fractional_probability_hits_about_that_share_of_runs():
    s = _samples(Perturbations(dsn_outage_probability=0.3), n=4000)
    share = float(np.mean(s["dsn_event"]))
    assert 0.25 < share < 0.35


def test_wilson_interval_matches_the_textbook_values():
    lo, hi = wilson_interval(0, 10)
    assert lo == 0.0
    assert hi == pytest.approx(0.2775, abs=1e-3)
    lo, hi = wilson_interval(10, 10)
    assert lo == pytest.approx(0.7225, abs=1e-3)
    assert hi == 1.0
    lo, hi = wilson_interval(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-3)
    assert hi == pytest.approx(0.7634, abs=1e-3)
    assert wilson_interval(0, 0) == (0.0, 1.0)
    # Narrows with n.
    lo_big, hi_big = wilson_interval(970, 1000)
    assert hi_big - lo_big < 0.03


# ── Task 2: the route's legs and its sky columns ───────────────────────────

from app.cost_engine import edge_travel_time_s  # noqa: E402
from app.stress_test import RouteLegs, RouteSky, route_legs, route_sky_columns  # noqa: E402
from test_earth_visibility import _metadata, _script_ephemeris  # noqa: E402

RES_M = 80.0
H = 2.0  # slice hours in the toy cases


def _slope_grid():
    slope = np.zeros((3, 3))
    slope[0, 1] = 10.0
    slope[1, 1] = 20.0
    return slope


def _legs(states, slope=None, traversable=None, rover=None):
    return route_legs(
        states,
        _slope_grid() if slope is None else slope,
        RES_M,
        get_rover("lpr_1") if rover is None else rover,
        H,
        traversable=traversable,
    )


@pytest.mark.parametrize(
    "states, fragment",
    [
        ([(0, 0, 0)], "at least two"),
        ([(0, 0, 1), (0, 1, 2)], "slice 0"),
        ([(0, 0, 0), (0, 1, 0)], "increase"),
        ([(0, 0, 0), (0, 1, 2), (0, 2, 1)], "increase"),
        ([(0, 0, 0), (0, 3, 1)], "outside"),
        ([(0, 0, 0), (2, 2, 1)], "adjacent"),
    ],
)
def test_route_legs_rejects_a_malformed_route(states, fragment):
    with pytest.raises(ValueError, match=fragment):
        _legs(states)


def test_route_legs_rejects_an_impassable_cell():
    passable = np.ones((3, 3), dtype=bool)
    passable[0, 1] = False
    with pytest.raises(ValueError, match="traversable"):
        _legs([(0, 0, 0), (0, 1, 1)], traversable=passable)


def test_route_legs_prices_moves_like_the_planner_and_waits_as_nothing():
    rover = get_rover("lpr_1")
    legs = _legs([(0, 0, 0), (0, 1, 1), (0, 1, 2), (1, 2, 4)])
    assert isinstance(legs, RouteLegs)
    assert legs.n_states == 4
    assert legs.is_wait.tolist() == [False, True, False]
    assert legs.n_moves == 2 and legs.n_waits == 1
    # Cardinal then diagonal distances.
    assert legs.distance_m.tolist() == pytest.approx([RES_M, 0.0, RES_M * math.sqrt(2)])
    # Trapezoidal edge slope: (0 + 10) / 2 and (10 + 0) / 2, same as astar_4d.
    expected = [
        edge_travel_time_s(5.0, RES_M, rover) / 3600.0,
        0.0,
        edge_travel_time_s(5.0, RES_M * math.sqrt(2), rover) / 3600.0,
    ]
    assert legs.travel_h.tolist() == pytest.approx(expected)
    traction = float(rover["p_base_w"]) * (1.0 + float(rover["mu_coeff"]) * math.sin(math.radians(5.0)))
    assert legs.traction_w.tolist() == pytest.approx([traction, 0.0, traction])
    assert legs.planned_h.tolist() == pytest.approx([0.0, 2.0, 4.0, 8.0])
    assert legs.planned_duration_h == pytest.approx(8.0)
    assert legs.odometry_m == pytest.approx(RES_M * (1.0 + math.sqrt(2)))


def test_route_legs_refuses_an_edge_the_travel_model_cannot_cross():
    # cos(90 deg) is 6e-17 in floating point, so 90 is "finite but enormous"
    # for edge_travel_time_s (as it is for the planner); past 90 it is inf.
    slope = np.full((3, 3), 100.0)
    with pytest.raises(ValueError, match="cannot cross"):
        _legs([(0, 0, 0), (0, 1, 1)], slope=slope)


def test_route_sky_from_cubes_extracts_the_route_columns_and_the_time_tables():
    # Two cells; cell A dark, dark, lit, lit, dark; cell B lit throughout.
    shadow = np.zeros((5, 2, 2))
    shadow[:, 0, 0] = [1.0, 1.0, 0.0, 0.0, 1.0]
    earth = np.ones((5, 2, 2), dtype=bool)
    earth[3:, 1, 1] = False
    deadline = np.full((5, 2, 2), np.inf)
    tts = np.array([[0.0, 1.0], [2.0, np.inf]])
    sky = RouteSky.from_cubes(
        shadow, earth, deadline, tts, [(0, 0), (1, 1)], H, time_varying=True
    )
    assert sky.n_slices == 5 and sky.slice_hours == H
    assert sky.shadow[:, 0].tolist() == [1.0, 1.0, 0.0, 0.0, 1.0]
    assert sky.shadow[:, 1].tolist() == [0.0] * 5
    assert sky.earth[:, 1].tolist() == [True, True, True, False, False]
    assert sky.tts_h.tolist() == [0.0, math.inf]
    # Cumulative exposure integral, hours: 0, 2, 4, 4, 4, 6 for cell A.
    assert sky.cumulative[:, 0].tolist() == pytest.approx([0.0, 2.0, 4.0, 4.0, 4.0, 6.0])
    # Absolute hour of the next dark slice at or after each slice.
    assert sky.next_dark_h[:, 0].tolist() == [0.0, 2.0, 8.0, 8.0, 8.0]
    assert sky.next_dark_h[:, 1].tolist() == [math.inf] * 5


def test_route_sky_from_cubes_without_earth_or_havens():
    sky = RouteSky.from_cubes(
        np.zeros((3, 1, 1)), None, None, None, [(0, 0), (0, 0)], H, time_varying=False
    )
    assert sky.earth is None and sky.deadline_h is None and sky.tts_h is None
    assert sky.shadow.shape == (3, 2)


def _fine_horizon():
    """(8 az, 4, 4) fine horizon: block (0,0) has two cells at 0 deg and two
    at 4 deg; everything else 0 deg."""
    horizon = np.zeros((8, 4, 4))
    horizon[:, 0, 1] = 4.0
    horizon[:, 1, 0] = 4.0
    return horizon


def test_route_sky_columns_reproduce_the_planners_block_mean_and_block_and(monkeypatch):
    """Sun at +3 deg for 20 h then -10 deg; Earth at +5 deg throughout. The
    coarse block (0,0) is half lit (two of four fine cells clear 3 deg) and
    fully linked (all four clear 5 deg); block (1,1) is lit and linked."""
    metadata = _metadata()
    metadata["shape"] = [4, 4]
    _script_ephemeris(
        monkeypatch,
        metadata,
        lambda h: (90.0, 5.0),
        lambda h: (90.0, 3.0 if h < 20.0 else -10.0),
    )
    shadow, earth = route_sky_columns(
        _fine_horizon(), metadata, [(0, 0), (1, 1)], 2, "2026-09-01T00:00:00", 3, 10.0
    )
    assert shadow.shape == (3, 2) and earth.shape == (3, 2)
    np.testing.assert_allclose(shadow, [[0.5, 0.0], [0.5, 0.0], [1.0, 1.0]])
    assert earth.dtype == bool
    assert earth.tolist() == [[True, True]] * 3
