"""Slip model tests (C3).

The curve is a literature-anchored MODEL, not a measurement: it passes
through sourced anchors (VIPER's 15 deg / 40 percent design requirement,
Yutu-2's measured 0..0.075 on slopes up to 8.86 deg) and is log-linear
between them. What must hold: the curve reproduces every anchor, grows
with slope, is symmetric in the slope's sign, stays under the cap, the
scalar and vectorised evaluations agree to the bit, (mu, sigma) is
available for B2, a profile without a curve gets no correction, and the
label never says MEASURED.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.constants import ROVERS, get_rover
from app.slip_model import (
    MAX_SLIP_RATIO,
    SLIP_CLAIM,
    SLIP_MODEL_ID,
    SLIP_MODEL_VALIDITY,
    SlipAnchor,
    check_slip_accumulation,
    compile_curve,
    curve_for,
    effective_distance_m,
    slip_energy_multiplier,
    slip_ratio,
    slip_ratio_array,
    slip_stats,
    thermal_inertia_slip_scale,
)

FLAT = SlipAnchor(0.0, 0.0375, 0.01875, "measured", "Yutu-2 (test copy)")
STEEPEST = SlipAnchor(8.86, 0.075, 0.01875, "measured_bound", "Yutu-2 (test copy)")
VIPER15 = SlipAnchor(15.0, 0.40, 0.20, "design_constraint", "VIPER PSJ 2025 (test copy)")


def _rover(anchors=(FLAT, VIPER15)) -> dict:
    rover = dict(get_rover("nasa_viper"))
    rover["slip_curve"] = tuple(anchors)
    return rover


# ── the curve passes through its anchors ────────────────────────────────────


def test_the_curve_reproduces_every_anchor():
    rover = _rover()
    assert slip_ratio(0.0, rover) == pytest.approx(0.0375, rel=1e-9)
    assert slip_ratio(15.0, rover) == pytest.approx(0.40, rel=1e-9)


def test_a_three_anchor_curve_passes_through_the_middle_anchor_too():
    rover = _rover((FLAT, STEEPEST, VIPER15))
    assert slip_ratio(8.86, rover) == pytest.approx(0.075, rel=1e-9)
    assert slip_ratio(15.0, rover) == pytest.approx(0.40, rel=1e-9)


def test_between_anchors_the_curve_is_log_linear():
    """Halfway between two anchors in slope, slip is the geometric mean of
    the two anchor values -- that is what 'exponential between anchors'
    means, and it is the shape assumption the spec declares."""
    rover = _rover((FLAT, STEEPEST, VIPER15))
    midpoint = 0.5 * (8.86 + 15.0)
    assert slip_ratio(midpoint, rover) == pytest.approx(math.sqrt(0.075 * 0.40), rel=1e-9)


def test_beyond_the_last_anchor_the_last_segment_continues_until_the_cap():
    rover = _rover()
    k = math.log(0.40 / 0.0375) / 15.0
    assert slip_ratio(18.0, rover) == pytest.approx(0.40 * math.exp(k * 3.0), rel=1e-9)
    assert slip_ratio(60.0, rover) == pytest.approx(MAX_SLIP_RATIO)
    assert slip_ratio(1000.0, rover) <= MAX_SLIP_RATIO


def test_slip_grows_monotonically_with_slope():
    rover = _rover((FLAT, STEEPEST, VIPER15))
    ratios = [slip_ratio(float(deg), rover) for deg in range(0, 31)]
    assert ratios == sorted(ratios)


def test_slip_is_symmetric_in_slope_sign():
    """A descent is still a slope; the model does not distinguish
    direction, so a negative slope must not produce a smaller penalty."""
    rover = _rover()
    assert slip_ratio(-15.0, rover) == pytest.approx(slip_ratio(15.0, rover))
    assert slip_ratio(-7.0, rover) == slip_ratio(7.0, rover)


# ── validation: no anchor without a source, no silent defaults ──────────────


@pytest.mark.parametrize(
    "anchors, fragment",
    [
        ((SlipAnchor(5.0, 0.05, 0.0, "measured", "x"), VIPER15), "0 deg"),
        ((FLAT,), "two"),
        ((FLAT, SlipAnchor(0.0, 0.1, 0.0, "measured", "x")), "increasing"),
        ((VIPER15, FLAT), "increasing"),
        ((FLAT, SlipAnchor(15.0, 0.95, 0.0, "measured", "x")), "MAX_SLIP_RATIO"),
        ((FLAT, SlipAnchor(15.0, 0.01, 0.0, "measured", "x")), "decrease"),
        ((FLAT, SlipAnchor(15.0, 0.40, 0.2, "design_constraint", "")), "source"),
        ((FLAT, SlipAnchor(15.0, 0.40, -0.1, "design_constraint", "x")), "sigma"),
        ((FLAT, SlipAnchor(15.0, 0.40, 0.2, "guess", "x")), "kind"),
    ],
)
def test_compile_curve_refuses_a_malformed_anchor_set(anchors, fragment):
    with pytest.raises(ValueError, match=fragment):
        compile_curve(tuple(anchors))


def test_a_profile_without_a_curve_gets_no_correction():
    rover = dict(get_rover("nasa_viper"))
    rover["slip_curve"] = None
    assert curve_for(rover) is None
    assert slip_ratio(10.0, rover) == 0.0
    assert effective_distance_m(100.0, 10.0, rover) == 100.0
    assert slip_energy_multiplier(10.0, rover) == 1.0
    rover.pop("slip_curve")
    assert curve_for(rover) is None


def test_the_default_rover_is_used_when_none_is_given():
    default = get_rover()
    assert slip_ratio(10.0) == slip_ratio(10.0, default)


# ── scalar and vectorised evaluation agree to the bit ───────────────────────


def _dense_slopes(rng, n=200_000):
    slopes = rng.uniform(0.0, 90.0, n)
    extras = np.array([0.0, 8.86, 15.0, 20.0, 25.0, 20.1, 18.0, 89.999])
    return np.concatenate([slopes, extras])


@pytest.mark.parametrize("anchors", [(FLAT, VIPER15), (FLAT, STEEPEST, VIPER15)])
def test_slip_ratio_array_matches_the_scalar_bit_for_bit(anchors):
    rover = _rover(anchors)
    slopes = _dense_slopes(np.random.default_rng(3))
    vector = slip_ratio_array(slopes, rover)
    scalar = np.array([slip_ratio(float(s), rover) for s in slopes])
    assert vector.dtype == np.float64
    assert np.array_equal(vector, scalar)


@pytest.mark.parametrize("rover_id", list(ROVERS))
def test_catalogue_curves_agree_scalar_vs_array_bit_for_bit(rover_id):
    rover = get_rover(rover_id)
    slopes = _dense_slopes(np.random.default_rng(5), n=50_000)
    vector = slip_ratio_array(slopes, rover)
    scalar = np.array([slip_ratio(float(s), rover) for s in slopes])
    assert np.array_equal(vector, scalar)


def test_the_platform_exp_and_cos_agree_between_numpy_and_math():
    """The bit-equality above rests on numpy's and math's exp/cos being the
    same function on this platform (measured: 0 ulp over a million
    samples). If a platform breaks this, the corridor's slice counts and
    the planner's could round differently at the median slope."""
    rng = np.random.default_rng(11)
    x = rng.uniform(-6.0, 6.0, 100_000)
    assert np.array_equal(np.exp(x), np.array([math.exp(v) for v in x]))
    deg = rng.uniform(0.0, 90.0, 100_000)
    assert np.array_equal(
        np.cos(np.radians(deg)), np.array([math.cos(math.radians(v)) for v in deg])
    )


# ── (mu, sigma): the B2 hook ────────────────────────────────────────────────


def test_slip_stats_returns_the_anchor_mean_and_spread_at_an_anchor():
    rover = _rover()
    assert slip_stats(0.0, rover) == pytest.approx((0.0375, 0.01875))
    assert slip_stats(15.0, rover) == pytest.approx((0.40, 0.20))


def test_slip_stats_interpolates_the_relative_spread_linearly():
    """Both test anchors carry sigma/mu = 0.5, so halfway the relative
    spread is 0.5 as well; with a different second anchor it moves."""
    rover = _rover()
    mu, sigma = slip_stats(7.5, rover)
    assert sigma == pytest.approx(0.5 * mu)
    rover = _rover((FLAT, SlipAnchor(15.0, 0.40, 0.04, "design_constraint", "x")))
    mu, sigma = slip_stats(7.5, rover)
    assert sigma == pytest.approx(mu * 0.5 * (0.5 + 0.1))
    _, beyond = slip_stats(30.0, rover)
    assert beyond == pytest.approx(slip_ratio(30.0, rover) * 0.1)


def test_slip_stats_without_a_curve_is_zero_zero():
    rover = dict(get_rover("nasa_viper"))
    rover["slip_curve"] = None
    assert slip_stats(10.0, rover) == (0.0, 0.0)


# ── the correction is one number, used consistently ─────────────────────────


def test_effective_distance_exceeds_commanded_distance():
    assert effective_distance_m(100.0, 10.0, _rover()) > 100.0


def test_effective_distance_never_divides_by_zero():
    assert math.isfinite(effective_distance_m(100.0, 90.0, _rover()))


def test_the_multiplier_matches_the_effective_distance_ratio():
    rover = _rover()
    for deg in (0.0, 10.0, 20.0):
        assert slip_energy_multiplier(deg, rover) == pytest.approx(
            effective_distance_m(100.0, deg, rover) / 100.0
        )
        assert slip_energy_multiplier(deg, rover) >= 1.0


# ── the label ───────────────────────────────────────────────────────────────


def test_the_module_declares_itself_a_literature_anchored_model():
    assert SLIP_MODEL_VALIDITY == "MODEL"
    assert SLIP_MODEL_VALIDITY != "MEASURED"
    assert "not a measurement" in SLIP_CLAIM.lower()
    assert "measured" not in SLIP_MODEL_VALIDITY.lower()
    assert SLIP_MODEL_ID


def test_the_thermal_inertia_hook_is_a_signature_not_a_model():
    """Cunningham et al. (RSS 2017) modulate slip with thermal inertia. We
    have no Diviner product locally, so the hook must refuse loudly rather
    than return a factor that looks applied."""
    with pytest.raises(NotImplementedError, match="Diviner"):
        thermal_inertia_slip_scale(np.zeros((2, 2)))


# --- slip as a replan trigger ---------------------------------------------


def test_the_trigger_fires_when_progress_falls_short():
    result = check_slip_accumulation(map_progress_m=50.0, odometer_claim_m=100.0)
    assert result.triggered
    assert result.trigger_id == "slip_accumulation"


def test_the_trigger_stays_quiet_when_progress_is_nominal():
    assert not check_slip_accumulation(
        map_progress_m=98.0, odometer_claim_m=100.0
    ).triggered


def test_the_trigger_boundary_matches_the_declared_threshold():
    assert not check_slip_accumulation(75.0, 100.0).triggered
    assert check_slip_accumulation(74.0, 100.0).triggered


def test_the_detail_names_the_quantities_it_actually_compared():
    """Neither input is a COMMANDED distance -- saying so sent an auditor
    looking for a number nothing records. (Round 2 review, M-5.)"""
    detail = check_slip_accumulation(map_progress_m=50.0, odometer_claim_m=100.0).detail
    assert "commanded" not in detail
    assert "odometry claims" in detail


def test_a_zero_odometry_claim_does_not_divide_by_zero():
    result = check_slip_accumulation(map_progress_m=0.0, odometer_claim_m=0.0)
    assert not result.triggered
    assert "no odometry distance claim" in result.detail


def test_advancing_further_than_the_odometer_claims_does_not_fire():
    assert not check_slip_accumulation(
        map_progress_m=120.0, odometer_claim_m=100.0
    ).triggered


def test_the_trigger_detail_carries_the_calibration_label():
    detail = check_slip_accumulation(50.0, 100.0).detail
    assert SLIP_MODEL_VALIDITY in detail


# ── route_slip_summary: the block a plan response carries ───────────────────


def test_route_slip_summary_reports_distance_weighted_slip_and_the_extras():
    from app.slip_model import route_slip_summary

    rover = _rover()
    s0, s15 = slip_ratio(0.0, rover), slip_ratio(15.0, rover)
    block = route_slip_summary(
        [(0.0, 320.0, 1.0, 100.0), (15.0, 452.5, 2.0, 300.0)], rover
    )
    assert block["applied"] is True and block["validity"] == "MODEL"
    route = block["route"]
    assert route["moves"] == 2 and route["skipped_edges"] == 0
    assert route["mean_slip"] == pytest.approx((320.0 * s0 + 452.5 * s15) / 772.5)
    assert route["max_slip"] == pytest.approx(s15)
    assert route["max_slip_slope_deg"] == 15.0
    assert route["distance_factor"] == pytest.approx(
        (320.0 / (1.0 - s0) + 452.5 / (1.0 - s15)) / 772.5
    )
    assert route["extra_hours"] == pytest.approx(1.0 * s0 + 2.0 * s15)
    assert route["extra_drawn_wh"] == pytest.approx(100.0 * s0 + 300.0 * s15)
    assert "not a measurement" in block["claim"].lower()


def test_route_slip_summary_handles_missing_energy_and_infinite_edges():
    from app.slip_model import route_slip_summary

    rover = _rover()
    block = route_slip_summary(
        [(0.0, 320.0, 1.0, None), (15.0, 320.0, float("inf"), 5.0)], rover
    )
    assert block["route"]["moves"] == 1
    assert block["route"]["skipped_edges"] == 1
    assert block["route"]["extra_drawn_wh"] is None
    empty = route_slip_summary([], rover)
    assert empty["route"]["moves"] == 0 and empty["route"]["extra_hours"] == 0.0
    assert empty["route"]["distance_factor"] == 1.0 and empty["route"]["max_slip_slope_deg"] is None


def test_route_slip_summary_without_a_curve_says_so():
    from app.slip_model import route_slip_summary

    rover = dict(get_rover("nasa_viper"))
    rover["slip_curve"] = None
    block = route_slip_summary([(10.0, 320.0, 1.0, 50.0)], rover)
    assert block["applied"] is False and block["validity"] is None
    assert block["route"]["mean_slip"] == 0.0 and block["route"]["extra_hours"] == 0.0
