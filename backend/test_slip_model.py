"""Slip model tests.

These check SHAPE and DIRECTION, not calibrated magnitude. The
coefficients are uncalibrated (see the module docstring), so asserting a
precise physical value would be asserting something the model does not
know. What must hold is that slip is positive, grows with slope, stays
bounded, and raises energy rather than lowering it.
"""

from __future__ import annotations

import math

import pytest

from app.cost_engine import edge_energy_wh
from app.slip_model import (
    I0,
    MAX_SLIP_RATIO,
    SLIP_MODEL_VALIDITY,
    check_slip_accumulation,
    effective_distance_m,
    slip_energy_multiplier,
    slip_ratio,
)


def test_flat_ground_slip_is_the_baseline_coefficient():
    assert slip_ratio(0.0) == pytest.approx(I0)


def test_slip_grows_monotonically_with_slope():
    ratios = [slip_ratio(deg) for deg in range(0, 31)]
    assert ratios == sorted(ratios)


def test_slip_is_capped_below_total_loss():
    """Slip reaching 1.0 would divide by zero in effective_distance_m."""
    assert slip_ratio(90.0) == pytest.approx(MAX_SLIP_RATIO)
    assert slip_ratio(1000.0) <= MAX_SLIP_RATIO


def test_slip_is_symmetric_in_slope_sign():
    """A descent is still a slope; the model does not distinguish
    direction, so a negative slope must not produce a smaller penalty."""
    assert slip_ratio(-15.0) == pytest.approx(slip_ratio(15.0))


def test_effective_distance_exceeds_commanded_distance():
    assert effective_distance_m(100.0, 10.0) > 100.0


def test_effective_distance_on_flat_ground_is_nearly_the_input():
    assert effective_distance_m(100.0, 0.0) == pytest.approx(100.0, rel=0.05)


def test_effective_distance_never_divides_by_zero():
    assert math.isfinite(effective_distance_m(100.0, 90.0))


def test_the_energy_multiplier_is_always_at_least_one():
    """Slip can only cost energy, never save it."""
    for deg in (0, 5, 10, 20, 30, 45):
        assert slip_energy_multiplier(deg) >= 1.0


def test_the_multiplier_matches_the_effective_distance_ratio():
    """Energy is linear in time and time is linear in distance, so the
    two must agree -- if they drift apart, one of them is wrong."""
    for deg in (0, 10, 20):
        assert slip_energy_multiplier(deg) == pytest.approx(
            effective_distance_m(100.0, deg) / 100.0
        )


def test_slip_makes_a_real_edge_more_expensive_not_less():
    """The whole point of the model: edge_energy_wh is systematically
    optimistic without it."""
    slope, distance = 20.0, 100.0
    plain = edge_energy_wh(slope, distance)
    corrected = edge_energy_wh(slope, effective_distance_m(distance, slope))
    assert corrected > plain


def test_the_correction_grows_with_slope():
    """A steeper edge must be penalised more than a shallow one."""
    gentle = slip_energy_multiplier(5.0)
    steep = slip_energy_multiplier(25.0)
    assert steep > gentle


def test_the_module_declares_itself_uncalibrated():
    """The label is load-bearing: consumers carry it into their output so
    no number from this model is presented as measured."""
    assert SLIP_MODEL_VALIDITY == "UNCALIBRATED"


# --- slip as a replan trigger ---------------------------------------------


def test_the_trigger_fires_when_progress_falls_short():
    result = check_slip_accumulation(travelled_m=50.0, commanded_m=100.0)
    assert result.triggered
    assert result.trigger_id == "slip_accumulation"


def test_the_trigger_stays_quiet_when_progress_is_nominal():
    assert not check_slip_accumulation(travelled_m=98.0, commanded_m=100.0).triggered


def test_the_trigger_boundary_matches_the_declared_threshold():
    assert not check_slip_accumulation(75.0, 100.0).triggered
    assert check_slip_accumulation(74.0, 100.0).triggered


def test_a_zero_commanded_distance_does_not_divide_by_zero():
    result = check_slip_accumulation(travelled_m=0.0, commanded_m=0.0)
    assert not result.triggered
    assert "no commanded distance" in result.detail


def test_overshooting_the_commanded_distance_does_not_fire():
    """Travelling further than commanded is not slip; it should not be
    reported as though the rover were bogging down."""
    assert not check_slip_accumulation(travelled_m=120.0, commanded_m=100.0).triggered


def test_the_trigger_detail_carries_the_calibration_label():
    detail = check_slip_accumulation(50.0, 100.0).detail
    assert SLIP_MODEL_VALIDITY in detail
