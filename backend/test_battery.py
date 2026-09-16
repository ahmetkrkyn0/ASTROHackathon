"""C2: the battery in the cold, the heater's power, and hibernation.

Unit tests and the two locks that matter most.

The BIT-EQUALITY lock: with ``battery_model="constant"``,
``heater_power_model="constant"`` and ``allow_hibernate=False`` -- the
defaults -- every number the model produces is the pre-C2 one, operation for
operation. That is asserted here on the shared energy functions, their
vectorised twins and the planner.

The FLAG-ON lock is its mirror image, and it exists because the bit-equality
lock cannot see the feature at all: it asserts precisely that nothing changed.
A feature whose switched-on behaviour cannot be written down as an assertion
has nothing to measure, so each of the three models is pinned at a stated
state with a stated number.

Nothing here claims thermal or electrochemical accuracy. NASA Glenn's, ISRO's
and NASA JSC's figures are quoted and checked as quotations; everything else
is this model's own arithmetic on the catalogue.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from app import battery as B
from app.constants import ROVERS, THERMAL_MIN_TRAVERSABLE_C, get_rover
from app.cost_cube import hibernate_cost, wait_cost
from app.cost_engine import (
    housekeeping_power_w,
    net_energy_per_metre_wh,
    resolve_weights,
)
from app.cost_vec import _housekeeping_power_w_grid, f_energy_cell_grid
from app.thermal_dwell import build_dwell_cube, rover_envelope

ROVER_IDS = list(ROVERS)


# ── the quoted figures stay quotations ──────────────────────────────────────


def test_the_freeze_point_is_200_kelvin_and_nasas_own_rounding_is_kept_apart():
    assert B.BATTERY_FREEZE_K == 200.0
    assert B.BATTERY_FREEZE_C == pytest.approx(-73.15)
    # NASA writes "(-70 C)" beside 200 K; the quotation keeps their words and
    # the model keeps the exact conversion. The two must not be conflated.
    assert "-70" in B.NASA_GLENN_QUOTED["freeze_quote"]
    assert B.NASA_GLENN_QUOTED["freeze_k"] == 200.0
    assert B.NASA_GLENN_QUOTED["isro_temperature_c"] == -160.0
    assert B.NASA_GLENN_QUOTED["isro_days"] == 14
    assert B.NASA_GLENN_QUOTED["vacuum_trials"].startswith("4 of 4")


def test_every_assumption_string_says_it_is_one():
    for source in (
        B.BATTERY_FREEZE_SOURCE,
        B.USABLE_FRACTION_SHAPE_SOURCE,
        B.HEATER_SIZING_SOURCE,
        B.HIBERNATION_POWER_SOURCE,
        B.HIBERNATION_ENDURANCE_SOURCE,
    ):
        assert source.startswith("assumption:")
        assert "Not a rover specification" in source


def test_the_research_documents_unsourced_percentages_are_not_used_anywhere():
    """The note guesses "85 percent at 0 C". e_cap_wh is ALREADY quoted at 0 C
    for the two profiles that carry VIPER's 5 420 Wh, so applying 0.85 there
    would discount the same capacity twice. The curve says 1.0."""
    for rover_id in ("lpr_1", "nasa_viper"):
        rover = get_rover(rover_id)
        assert B.battery_rating_c(rover) == 0.0
        assert B.usable_fraction(0.0, rover) == 1.0
        assert B.usable_fraction(20.0, rover) == 1.0


def test_the_jsc_cross_check_reproduces_their_published_26_percent():
    """NASA JSC: "Decreasing a component's survival temperature from 270K to
    250K ... decreases heater power requirements by 26%". Their law, their
    number; this only checks that our reading of the law agrees."""
    check = B.jsc_survival_temperature_check()
    assert check["quoted_pct"] == 26.0
    assert check["predicted_pct"] == pytest.approx(26.50, abs=0.01)
    assert abs(check["difference_pct_points"]) < 1.0
    # The coefficient cancels, so the prediction is flat in the environment
    # temperature across the polar range.
    values = [row["predicted_reduction_pct"] for row in check["by_environment"]]
    assert max(values) - min(values) < 1.0


# ── the deliverable fraction ────────────────────────────────────────────────


def test_the_curve_is_anchored_at_both_ends_and_monotone_between():
    rover = get_rover("lpr_1")
    assert B.usable_fraction(B.BATTERY_FREEZE_C, rover) == 0.0
    assert B.usable_fraction(B.BATTERY_FREEZE_C - 10.0, rover) == 0.0
    assert B.usable_fraction(0.0, rover) == 1.0
    values = [
        B.usable_fraction(t, rover)
        for t in np.linspace(B.BATTERY_FREEZE_C, 0.0, 25)
    ]
    assert all(b >= a - 1e-12 for a, b in zip(values, values[1:]))


def test_the_shape_exponent_moves_the_middle_and_never_the_anchors():
    rover = get_rover("lpr_1")
    for exponent in (0.5, 1.0, 2.0, 4.0):
        assert B.usable_fraction(B.BATTERY_FREEZE_C, rover, exponent) == 0.0
        assert B.usable_fraction(0.0, rover, exponent) == 1.0
    middle = B.BATTERY_FREEZE_C / 2.0
    assert B.usable_fraction(middle, rover, 2.0) < B.usable_fraction(middle, rover, 1.0)
    assert B.usable_fraction(middle, rover, 0.5) > B.usable_fraction(middle, rover, 1.0)


def test_luvmi_m_is_refused_with_a_reason_rather_than_given_an_invented_rating():
    """Its declared battery minimum is -100 C, 27 K BELOW the freeze point the
    cited measurement reports. The two cannot both hold, and no rating point
    is invented to reconcile them."""
    rover = get_rover("luvmi_m")
    reason = B.usable_fraction_unavailable_reason(rover)
    assert reason is not None
    assert "-100" in reason and "freeze point" in reason
    assert B.usable_fraction(-50.0, rover) is None
    assert B.usable_fraction_grid(np.array([-50.0]), rover) is None
    # And the stored charge is then read at face value, not at a guess.
    assert B.deliverable_wh(1000.0, -50.0, rover) == 1000.0


def test_the_other_three_profiles_have_a_curve_anchored_on_their_own_envelope():
    for rover_id in ("lpr_1", "nasa_viper", "cnsa_yutu_2"):
        rover = get_rover(rover_id)
        assert B.usable_fraction_unavailable_reason(rover) is None
        assert B.battery_rating_c(rover) == float(rover["bat_op_min_c"])
        assert B.usable_fraction(float(rover["bat_op_min_c"]), rover) == 1.0


def test_the_grid_form_matches_the_scalar_form_cell_for_cell():
    rover = get_rover("lpr_1")
    temperatures = np.linspace(-120.0, 40.0, 97)
    grid = B.usable_fraction_grid(temperatures, rover)
    scalar = np.array([B.usable_fraction(float(t), rover) for t in temperatures])
    assert np.allclose(grid, scalar, rtol=0.0, atol=1e-12)


# ── the heater ──────────────────────────────────────────────────────────────


def test_the_calibration_returns_the_published_heater_power_at_the_sizing_surface():
    """Both laws agree at the one point the sizing assumption pins, by
    construction -- which is what makes comparing them anywhere else mean
    something."""
    for rover_id in ROVER_IDS:
        rover = get_rover(rover_id)
        coefficients = B.heater_coefficients(rover)
        assert coefficients is not None, rover_id
        for model in ("delta_t", "radiative"):
            power = B.heater_power_w(THERMAL_MIN_TRAVERSABLE_C, rover, model)
            assert power == pytest.approx(float(rover["p_heater_w"]), rel=1e-12), (rover_id, model)
            equilibrium = B.heated_equilibrium_c(THERMAL_MIN_TRAVERSABLE_C, rover, None, model)
            assert equilibrium == pytest.approx(coefficients.set_point_c, abs=1e-9)


def test_the_heater_is_clipped_at_both_ends_and_never_runs_above_the_set_point():
    rover = get_rover("lpr_1")
    for model in ("delta_t", "radiative"):
        assert B.heater_power_w(-250.0, rover, model) == float(rover["p_heater_w"])
        assert B.heater_power_w(0.0, rover, model) == 0.0
        assert B.heater_power_w(40.0, rover, model) == 0.0


def test_the_heater_reads_the_surface_and_is_therefore_monotone_in_it():
    """The first draft drove the heater off ``surface_to_inner``, which is
    piecewise on the SIGN of the surface and jumps by 100 K across zero -- so
    the heater turned ON as the ground got WARMER. Reading the surface, as
    NASA JSC's T_env does, makes the power monotone."""
    rover = get_rover("lpr_1")
    surfaces = np.linspace(-200.0, 40.0, 241)
    for model in ("delta_t", "radiative"):
        powers = [B.heater_power_w(float(s), rover, model) for s in surfaces]
        assert all(b <= a + 1e-12 for a, b in zip(powers, powers[1:])), model
        # and in particular no jump across zero
        assert B.heater_power_w(-0.001, rover, model) == pytest.approx(
            B.heater_power_w(0.001, rover, model), abs=1e-3
        )


def test_the_heater_grid_matches_the_scalar_form():
    rover = get_rover("nasa_viper")
    surfaces = np.linspace(-200.0, 40.0, 61)
    for model in ("delta_t", "radiative"):
        grid = B.heater_power_w_grid(surfaces, rover, model)
        scalar = np.array([B.heater_power_w(float(s), rover, model) for s in surfaces])
        assert np.array_equal(grid, scalar), model


def test_the_constant_model_is_not_a_temperature_law_and_says_so():
    rover = get_rover("lpr_1")
    with pytest.raises(ValueError, match="pre-C2 exposure term"):
        B.heater_power_w(-100.0, rover, "constant")


# ── bit-equality: the default path is the pre-C2 path ───────────────────────


@pytest.mark.parametrize("rover_id", ROVER_IDS)
@pytest.mark.parametrize("shadow", [0.0, 0.3, 0.7, 1.0])
def test_the_scalar_and_vector_housekeeping_twins_agree_with_and_without_a_heater(
    rover_id, shadow
):
    """The existing twin guard (test_review_fixes) sweeps SLOPE only and leaves
    shadow_ratio at 0.0 on both sides, where both forms return exactly
    p_idle_w -- so it cannot see the heater half of this term at all. This
    sweeps the half that matters, across every profile, with and without a
    temperature-derived heater."""
    rover = get_rover(rover_id)
    assert housekeeping_power_w(shadow, rover) == float(
        _housekeeping_power_w_grid(np.array(shadow), rover)
    )
    for heater_w in (0.0, 7.5, float(rover["p_heater_w"]), 1000.0):
        assert housekeeping_power_w(shadow, rover, heater_w) == float(
            _housekeeping_power_w_grid(np.array(shadow), rover, heater_w)
        )


@pytest.mark.parametrize("rover_id", ROVER_IDS)
def test_heater_w_none_is_the_pre_c2_arithmetic_exactly(rover_id):
    rover = get_rover(rover_id)
    slopes = np.linspace(0.0, float(rover["slope_max_deg"]), 13)
    shadows = np.linspace(0.0, 1.0, 11)
    for slope in slopes:
        for shadow in shadows:
            assert net_energy_per_metre_wh(
                float(slope), float(shadow), rover
            ) == net_energy_per_metre_wh(float(slope), float(shadow), rover, heater_w=None)
    grid_slope, grid_shadow = np.meshgrid(slopes, shadows)
    assert np.array_equal(
        f_energy_cell_grid(grid_slope, rover, grid_shadow),
        f_energy_cell_grid(grid_slope, rover, grid_shadow, heater_w=None),
    )


def test_wait_cost_with_no_heater_is_the_pre_c2_value():
    rover = get_rover("lpr_1")
    weights = resolve_weights(None, rover)
    for frac in (0.0, 0.25, 0.5, 1.0):
        assert wait_cost(frac, 0.5, rover, weights) == wait_cost(
            frac, 0.5, rover, weights, heater_w=None
        )


def test_the_wait_cube_dedup_is_exact_with_a_per_cell_heater():
    """With a heater the value depends on the PAIR (illuminated fraction,
    heater power), not on the fraction alone, so the de-duplication key has to
    widen. Two cells equally lit but at different temperatures must not share a
    value -- and the widened path must still agree with the scalar function
    cell for cell."""
    from app.cost_cube import build_wait_cost_cube

    rover = get_rover("lpr_1")
    weights = resolve_weights(None, rover)
    rng = np.random.default_rng(7)
    n_slices, height, width = 5, 6, 7
    illum = [rng.choice([0.0, 0.25, 0.5, 0.75, 1.0], size=(height, width)) for _ in range(n_slices)]
    heaters = rng.choice([0.0, 5.0, 12.5, 25.0], size=(n_slices, height, width))
    gains = rng.uniform(0.3, 1.0, size=n_slices)

    def direct(**kwargs):
        return np.array(
            [
                [
                    [
                        wait_cost(
                            float(illum[t][r, c]), 0.5, rover, weights,
                            solar_gain=float(kwargs.get("gains", [1.0] * n_slices)[t]),
                            heater_w=(
                                None if kwargs.get("heaters") is None
                                else float(kwargs["heaters"][t, r, c])
                            ),
                        )
                        for c in range(width)
                    ]
                    for r in range(height)
                ]
                for t in range(n_slices)
            ]
        )

    # the pre-C2 whole-cube table, untouched
    assert np.array_equal(
        build_wait_cost_cube(illum, rover, 0.5, weights, coarsen=1), direct()
    )
    # C1's per-slice gain, untouched
    assert np.array_equal(
        build_wait_cost_cube(illum, rover, 0.5, weights, coarsen=1, solar_gain_series=gains),
        direct(gains=gains),
    )
    # C2's per-cell heater, exact
    assert np.array_equal(
        build_wait_cost_cube(
            illum, rover, 0.5, weights, coarsen=1,
            solar_gain_series=gains, heater_w_series=heaters,
        ),
        direct(gains=gains, heaters=heaters),
    )


def test_the_wait_cube_refuses_a_heater_series_of_the_wrong_shape():
    from app.cost_cube import build_wait_cost_cube

    rover = get_rover("lpr_1")
    weights = resolve_weights(None, rover)
    illum = [np.full((3, 3), 0.5) for _ in range(4)]
    with pytest.raises(ValueError, match="heater_w_series"):
        build_wait_cost_cube(
            illum, rover, 0.5, weights, coarsen=1,
            heater_w_series=np.zeros((2, 3, 3)),
        )


# ── the flag-ON lock: what the models actually change ───────────────────────


def test_a_stated_state_gives_a_stated_derating():
    """The mirror image of the bit-equality lock. Measured: LPR-1 at -20 C
    inner delivers 72.6589 percent of its stored charge under the default
    linear shape, and its published 50 h endurance becomes 32.9118 h at full
    charge -- the reserve is a DELIVERABLE floor, so the cold eats into the
    margin above it twice as fast as it eats into the charge."""
    rover = get_rover("lpr_1")
    assert B.usable_fraction(-20.0, rover) == pytest.approx(0.7265892, abs=1e-7)
    assert B.shadow_endurance_h(5420.0, -20.0, rover) == pytest.approx(32.9118, abs=1e-4)
    assert B.shadow_endurance_h(5420.0, -20.0, rover) < 50.0


def test_a_stated_surface_gives_a_stated_heater_power():
    """Measured: LPR-1's 25 W heater against a -60 C surface draws 10.00 W
    under the linear law and 16.41 W under NASA JSC's T^4 law -- 64 percent
    more. The gap between the two IS the fourth power, and it is why the
    research note's linear form is offered beside the source's own rather
    than instead of it."""
    rover = get_rover("lpr_1")
    assert B.heater_power_w(-60.0, rover, "delta_t") == pytest.approx(10.0, abs=1e-9)
    assert B.heater_power_w(-60.0, rover, "radiative") == pytest.approx(16.4080, abs=1e-4)
    assert B.heater_power_w(-120.0, rover, "radiative") == pytest.approx(23.5004, abs=1e-4)


def test_the_two_heater_laws_are_not_a_bound_on_the_old_one():
    """The first draft claimed the temperature law is always at most the
    exposure-scaled one. It is not: the two read different layers. A LIT but
    COLD cell pays nothing under the old term and pays the heater under the
    new one."""
    rover = get_rover("lpr_1")
    old_in_sunlight = housekeeping_power_w(0.0, rover)
    new_in_a_cold_lit_cell = housekeeping_power_w(
        0.0, rover, B.heater_power_w(-120.0, rover, "radiative")
    )
    assert new_in_a_cold_lit_cell > old_in_sunlight


# ── the endurance ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("rover_id", ROVER_IDS)
def test_full_charge_at_the_rating_temperature_returns_the_published_endurance(rover_id):
    """Exactly, for every profile -- including NASA VIPER, whose catalogue is
    internally inconsistent (50 h at 130 W is 6 500 Wh against a 5 420 Wh
    pack). That inconsistency is reported in the research note, not smuggled
    into the endurance by a ``min()``."""
    rover = get_rover(rover_id)
    rating = B.battery_rating_c(rover)
    probe = float(rover["bat_op_max_c"]) if rating is None else rating
    assert B.shadow_endurance_h(float(rover["e_cap_wh"]), probe, rover) == float(
        rover["h_max_shadow_h"]
    )


def test_the_endurance_falls_with_charge_and_with_temperature_and_never_rises():
    rover = get_rover("lpr_1")
    published = float(rover["h_max_shadow_h"])
    full_warm = B.shadow_endurance_h(5420.0, 10.0, rover)
    half_warm = B.shadow_endurance_h(2710.0, 10.0, rover)
    full_cold = B.shadow_endurance_h(5420.0, -50.0, rover)
    assert full_warm == published
    assert half_warm < full_warm
    assert full_cold < full_warm
    assert B.shadow_endurance_h(5420.0, -80.0, rover) == 0.0   # below the freeze point


def test_the_reserve_is_a_deliverable_floor_so_the_cold_raises_the_stored_charge_it_needs():
    rover = get_rover("lpr_1")
    reserve = 5420.0 * 0.2
    assert B.deliverable_wh(reserve, 10.0, rover) == pytest.approx(reserve)
    assert B.deliverable_wh(reserve, -40.0, rover) < reserve


# ── hibernation ─────────────────────────────────────────────────────────────


def test_hibernation_is_undefined_for_luvmi_m_and_says_why():
    available, reason = B.hibernation_available(get_rover("luvmi_m"))
    assert available is False
    assert "p_hibernate_w" in reason


@pytest.mark.parametrize("rover_id", ["lpr_1", "nasa_viper", "cnsa_yutu_2"])
def test_hibernation_is_available_for_the_other_three(rover_id):
    available, reason = B.hibernation_available(get_rover(rover_id))
    assert available is True and reason is None


def test_the_dark_rate_says_lpr1_hibernation_costs_more_than_its_heaters():
    """The catalogue's p_hibernate_w for LPR-1 is 108 W against a 65 W shadow
    draw -- so its "hibernation" is a keep-alive mode, not NASA Glenn's
    passive one. Reported, not corrected."""
    assert B.hibernate_dark_rate(get_rover("lpr_1")) == pytest.approx(108.0 / 65.0)
    assert B.hibernate_dark_rate(get_rover("nasa_viper")) == pytest.approx(100.0 / 130.0)
    assert B.hibernate_dark_rate(get_rover("cnsa_yutu_2")) == pytest.approx(5.0 / 60.0)
    assert B.hibernate_dark_rate(get_rover("lpr_1")) > 1.0


def test_the_survival_envelope_widens_the_cold_end_only_and_stays_bounded():
    rover = get_rover("lpr_1")
    operating = rover_envelope(rover)
    survival = B.survival_envelope(rover)
    assert survival.lo == B.BATTERY_FREEZE_C
    assert survival.lo < operating.lo
    assert survival.hi == operating.hi        # nothing says a dormant rover may cook
    assert math.isfinite(survival.lo) and math.isfinite(survival.hi)


def test_hibernation_names_which_components_left_their_operating_range():
    """NASA Glenn's evidence is about CELLS; NASA JSC's caution is about
    AVIONICS. A response says which bound was crossed rather than reporting
    one and letting the reader assume the other."""
    rover = get_rover("lpr_1")            # battery 0 C, electronics -10 C
    assert B.components_past_operating_limit(5.0, rover) == []
    assert B.components_past_operating_limit(-5.0, rover) == ["battery"]
    assert B.components_past_operating_limit(-40.0, rover) == ["battery", "electronics"]


def test_the_dawn_preheat_needs_light_and_a_heater_that_is_not_saturated():
    rover = get_rover("lpr_1")
    # No array power: NASA's dawn mode runs the pre-heaters on the array alone.
    hours, exit_c, reason = B.dawn_preheat(-60.0, -80.0, 0.0, rover)
    assert hours is None and exit_c is None and "dark" in reason

    # At the sizing surface the heater's equilibrium IS the envelope floor, so
    # the approach is asymptotic and the rover must not sleep there.
    hours, _exit, reason = B.dawn_preheat(-60.0, THERMAL_MIN_TRAVERSABLE_C, 410.0, rover)
    assert hours is None and "saturates" in reason

    # Somewhere warmer it completes, in HOURS, and lands on the envelope floor.
    hours, exit_c, reason = B.dawn_preheat(-60.0, -100.0, 410.0, rover)
    assert reason is None
    assert 0.0 < hours < 48.0
    assert exit_c == rover_envelope(rover).lo


def test_the_dawn_preheat_is_in_hours_not_seconds():
    """tau_s is in seconds and the whole model is in hours; the closed form
    divides by 3600 exactly as thermal_dwell.exit_time_h does."""
    rover = get_rover("lpr_1")
    hours, _exit, reason = B.dawn_preheat(-60.0, -100.0, 410.0, rover)
    assert reason is None
    tau_h = float(rover["thermal_tau_s"]) / 3600.0
    assert hours < 20.0 * tau_h


def test_a_rover_already_inside_its_envelope_needs_no_preheat():
    rover = get_rover("lpr_1")
    hours, exit_c, reason = B.dawn_preheat(5.0, -100.0, 410.0, rover)
    assert reason is None and hours == 0.0 and exit_c == 5.0


def test_the_cited_evidence_has_a_range_and_the_model_says_when_it_is_left():
    beyond, reason = B.hibernation_beyond_evidence(-70.0, 100.0)
    assert beyond is False and reason is None
    beyond, reason = B.hibernation_beyond_evidence(-200.0, 100.0)
    assert beyond is True and "80 K" in reason
    beyond, reason = B.hibernation_beyond_evidence(-70.0, 400.0)
    assert beyond is True and "14 day" in reason


def test_hibernate_cost_is_never_a_reward_and_never_below_the_hours_it_spends():
    """A negative or zero-cost dormant hour would break the A* heuristic
    across a zero-distance edge, and a rover could lower its cost by sleeping
    in the sunshine."""
    for rover_id in ("lpr_1", "nasa_viper", "cnsa_yutu_2"):
        rover = get_rover(rover_id)
        weights = resolve_weights(None, rover)
        for frac in (0.0, 0.5, 1.0):
            value = hibernate_cost(frac, 2.0, rover, weights)
            assert value >= 2.0


def test_hibernate_cost_refuses_a_profile_with_no_declared_draw():
    rover = get_rover("luvmi_m")
    with pytest.raises(ValueError, match="p_hibernate_w"):
        hibernate_cost(0.0, 1.0, rover, resolve_weights(None, rover))


def test_the_dormant_draw_is_cheaper_for_two_profiles_and_dearer_for_one():
    for rover_id, cheaper in (("lpr_1", False), ("nasa_viper", True), ("cnsa_yutu_2", True)):
        rover = get_rover(rover_id)
        weights = resolve_weights(None, rover)
        dark_wait = wait_cost(0.0, 1.0, rover, weights)
        dormant = hibernate_cost(0.0, 1.0, rover, weights)
        assert (dormant < dark_wait) is cheaper, rover_id


# ── the planner ─────────────────────────────────────────────────────────────


def _synthetic_night(rover, dawn_slice=20, n_slices=40, slice_hours=1.0):
    """A 1x2 world in which holding position is the only option until dawn."""
    height, width = 1, 2
    shadow = np.ones((n_slices, height, width))
    shadow[dawn_slice:, :, :] = 0.0
    # The offsets are piecewise on the surface sign: -140 C surface maps to a
    # -70 C inner target (just above the freeze point), -60 C to +10 C.
    surface = np.where(shadow > 0.5, -140.0, -60.0).astype(np.float64)
    cost = np.zeros((n_slices, height, width))
    cost[:dawn_slice, 0, 1] = np.inf          # the goal is shut until dawn
    traversable = np.ones((height, width), dtype=bool)
    weights = resolve_weights(None, rover)
    wait_cube = np.array(
        [
            [
                [wait_cost(float(1.0 - shadow[t, r, c]), slice_hours, rover, weights)
                 for c in range(width)]
                for r in range(height)
            ]
            for t in range(n_slices)
        ]
    )
    dwell = build_dwell_cube(surface, slice_hours, rover, traversable)
    return dict(
        cost_cube=cost,
        wait_cost_cube=wait_cube,
        traversable=traversable,
        start=(0, 0),
        goal=(0, 1),
        resolution_m=10.0,
        slice_hours=slice_hours,
        rover=rover,
        slope_grid=np.zeros((height, width)),
        shadow_cube=shadow,
        initial_soc_frac=1.0,
        max_dwell_cube=dwell,
        surface_cube=surface,
        weights=weights,
    )


def test_waiting_out_a_night_is_refused_and_hibernating_through_it_is_not():
    from app.pathfinder_4d import astar_4d

    rover = get_rover("cnsa_yutu_2")          # 2 h endurance, 5 W dormant
    world = _synthetic_night(rover)

    refused = astar_4d(**world)
    assert refused["path_states"] == []
    assert "continuous shadow" in refused["error"]

    planned = astar_4d(**world, allow_hibernate=True)
    assert planned["path_states"], planned["error"]
    assert planned["path_actions"].count("hibernate") == 1
    metrics = planned["metrics"]
    assert metrics["hibernate_steps"] == 1
    assert metrics["wait_steps"] == 0          # a hibernation is not a wait
    assert metrics["hibernate_hours"] > 20.0


def test_the_darkness_clock_runs_during_a_dormancy_and_is_reported_at_its_peak():
    """Stopping the clock would make max_continuous_shadow_h stop meaning
    continuous darkness and let D3's LP-R01 pass on a number nobody measured.
    Yutu-2's 20 h dormancy spends 20 * 5/60 = 1.667 h of its 2 h budget."""
    from app.pathfinder_4d import astar_4d

    rover = get_rover("cnsa_yutu_2")
    planned = astar_4d(**_synthetic_night(rover), allow_hibernate=True)
    metrics = planned["metrics"]
    assert metrics["hibernate_dark_hours"] == pytest.approx(20.0 * 5.0 / 60.0, abs=1e-6)
    # Reported at the peak, not at the post-dawn reset.
    assert metrics["max_continuous_shadow_h"] == pytest.approx(
        metrics["hibernate_dark_hours"], abs=1e-3
    )
    assert metrics["max_continuous_shadow_h"] <= float(rover["h_max_shadow_h"])


def test_the_endurance_still_binds_a_dormancy_it_is_only_spent_more_slowly():
    """A dormancy is not unbounded: 30 h at Yutu-2's rate is 2.5 h against a
    2 h budget, and the planner refuses it."""
    from app.pathfinder_4d import astar_4d

    rover = get_rover("cnsa_yutu_2")
    world = _synthetic_night(rover, dawn_slice=30, n_slices=50)
    refused = astar_4d(**world, allow_hibernate=True)
    assert refused["path_states"] == []
    assert "continuous shadow" in refused["error"]


def test_hibernation_cannot_be_entered_from_a_lit_slice():
    """Dormancy is cheaper than waiting for two of four profiles, so an
    ungated edge fills plans with naps in the sunshine."""
    from app.pathfinder_4d import astar_4d

    rover = get_rover("cnsa_yutu_2")
    world = _synthetic_night(rover, dawn_slice=20)
    world["shadow_cube"] = np.zeros_like(world["shadow_cube"])   # lit throughout
    planned = astar_4d(**world, allow_hibernate=True)
    assert planned["path_states"], planned["error"]
    assert "hibernate" not in planned["path_actions"]


def test_the_route_trace_follows_the_rover_that_actually_slept():
    from app.pathfinder_4d import astar_4d

    rover = get_rover("cnsa_yutu_2")
    planned = astar_4d(**_synthetic_night(rover), allow_hibernate=True)
    inner = planned["path_inner_c"]
    assert inner[0] == pytest.approx(10.0)                    # envelope midpoint
    assert inner[1] == pytest.approx(rover_envelope(rover).lo)  # the pre-heat lands there
    assert planned["metrics"]["coldest_inner_c"] < inner[1]
    assert planned["metrics"]["coldest_inner_c"] >= B.BATTERY_FREEZE_C


def test_a_profile_without_a_declared_draw_is_refused_rather_than_given_one():
    from app.pathfinder_4d import astar_4d

    rover = get_rover("luvmi_m")
    world = _synthetic_night(rover)
    refused = astar_4d(**world, allow_hibernate=True)
    assert refused["path_states"] == []
    assert "p_hibernate_w" in refused["error"]


def test_the_derating_refuses_a_profile_whose_anchors_contradict_each_other():
    from app.pathfinder_4d import astar_4d

    rover = get_rover("luvmi_m")
    refused = astar_4d(**_synthetic_night(rover), battery_model="temperature_derated")
    assert refused["path_states"] == []
    assert "temperature_derated" in refused["error"]


def test_the_derating_refuses_to_read_the_no_thermal_state_sentinel():
    """0.0 is the sentinel a label carries when nothing is tracked, and it is
    numerically identical to LPR-1's rating temperature -- so reading the
    derating there would return 1.0 everywhere and look like it had run."""
    from app.pathfinder_4d import astar_4d

    rover = get_rover("lpr_1")
    world = _synthetic_night(rover)
    world["max_dwell_cube"] = None
    refused = astar_4d(**world, battery_model="temperature_derated")
    assert refused["path_states"] == []
    assert "sentinel" in refused["error"]


def test_every_new_refusal_is_tallied_and_named():
    from app.pathfinder_4d import REJECTION_KEYS, _empty_rejections, no_path_reason_4d

    assert "hibernate_unwakeable" in REJECTION_KEYS
    assert "hibernate_too_cold" in REJECTION_KEYS
    rover = get_rover("lpr_1")
    for key, phrase in (
        ("hibernate_unwakeable", "dawn pre-heat"),
        ("hibernate_too_cold", "200 K"),
    ):
        tally = _empty_rejections()
        tally[key] = 3
        message = no_path_reason_4d(tally, rover, 40, 1.0)
        assert phrase in message
        # and neither is allowed to read as a horizon problem
        tally["horizon"] = 5
        assert "within the time horizon" not in no_path_reason_4d(tally, rover, 40, 1.0)


def test_the_endurance_refusal_does_not_quote_the_catalogue_when_it_did_not_bind():
    from app.pathfinder_4d import _empty_rejections, no_path_reason_4d

    rover = get_rover("lpr_1")
    tally = _empty_rejections()
    tally["shadow_endurance"] = 2
    plain = no_path_reason_4d(tally, rover, 40, 1.0)
    derated = no_path_reason_4d(tally, rover, 40, 1.0, "temperature_derated")
    assert "its 50 h endurance" in plain
    assert "battery temperature" in derated


def test_with_every_switch_off_the_planner_is_the_pre_c2_planner():
    from app.pathfinder_4d import astar_4d

    rover = get_rover("cnsa_yutu_2")
    world = _synthetic_night(rover, dawn_slice=1)
    reference = astar_4d(**{k: v for k, v in world.items() if k != "weights"})
    with_defaults = astar_4d(
        **world,
        battery_model="constant",
        allow_hibernate=False,
        heater_w_cube=None,
    )
    assert with_defaults["path_states"] == reference["path_states"]
    assert with_defaults["metrics"]["total_cost"] == reference["metrics"]["total_cost"]
    assert with_defaults["metrics"]["nodes_expanded"] == reference["metrics"]["nodes_expanded"]


# ── the catalogue's two stale labels ────────────────────────────────────────


def test_p_hibernate_w_now_has_a_reader_and_thermal_tau_s_is_no_longer_declared_only():
    from app.constants import DECLARED_ONLY_FIELDS, MODELLED_FIELDS, rover_catalog

    assert "p_hibernate_w" in MODELLED_FIELDS
    assert "thermal_tau_s" in MODELLED_FIELDS
    assert "thermal_tau_s" not in DECLARED_ONLY_FIELDS
    # Correcting the label must not remove the number from the API.
    entry = rover_catalog()[0]
    assert entry["thermal_tau_s"] == 7200.0
    assert "battery_model" in entry


def test_the_c6_assumption_string_no_longer_claims_no_coefficient_exists():
    from app.constants import HEATER_THERMOSTAT_ASSUMPTION_SOURCE

    assert "C2 AMENDMENT" in HEATER_THERMOSTAT_ASSUMPTION_SOURCE
    assert "POWER-LIMITED" in HEATER_THERMOSTAT_ASSUMPTION_SOURCE


def test_the_catalogue_block_says_what_each_profile_cannot_do():
    from app.constants import rover_catalog

    blocks = {entry["id"]: entry["battery_model"] for entry in rover_catalog()}
    assert blocks["luvmi_m"]["cold_capacity"]["available"] is False
    assert blocks["luvmi_m"]["hibernation"]["available"] is False
    for rover_id in ("lpr_1", "nasa_viper", "cnsa_yutu_2"):
        assert blocks[rover_id]["cold_capacity"]["available"] is True
        assert blocks[rover_id]["hibernation"]["available"] is True
