"""Uncertainty budget model tests."""

from __future__ import annotations

import math

import pytest

from app.localization_budget import (
    DRIFT_RATES,
    budget_for_source,
    distance_until_uncertainty_exceeds,
)


def test_the_budget_is_headroom_over_rate():
    # 20 m half-width, 10% drift, clean start: 200 m.
    assert distance_until_uncertainty_exceeds(20.0, 0.10) == pytest.approx(200.0)


def test_initial_uncertainty_consumes_headroom():
    assert distance_until_uncertainty_exceeds(
        20.0, 0.10, sigma_0_m=10.0
    ) == pytest.approx(100.0)


def test_an_estimate_already_wider_than_the_corridor_gets_zero_budget():
    assert distance_until_uncertainty_exceeds(5.0, 0.10, sigma_0_m=8.0) == 0.0


def test_zero_drift_with_headroom_never_expires():
    assert math.isinf(distance_until_uncertainty_exceeds(20.0, 0.0))


def test_dead_reckoning_expires_far_sooner_than_visual_odometry():
    """The ordering the whole report rests on: a 20x drift-rate gap must
    show up as a 20x distance gap under a linear model."""
    dead = distance_until_uncertainty_exceeds(20.0, 0.10)
    visual = distance_until_uncertainty_exceeds(20.0, 0.005)
    assert visual / dead == pytest.approx(20.0)


@pytest.mark.parametrize("bad", [-1.0])
def test_negative_inputs_are_rejected(bad):
    with pytest.raises(ValueError):
        distance_until_uncertainty_exceeds(bad, 0.1)
    with pytest.raises(ValueError):
        distance_until_uncertainty_exceeds(10.0, bad)
    with pytest.raises(ValueError):
        distance_until_uncertainty_exceeds(10.0, 0.1, sigma_0_m=bad)


def test_the_carried_drift_rates_are_the_published_ones():
    rates = {source: rate for source, rate, _ in DRIFT_RATES}
    assert rates["dead_reckoning"] == pytest.approx(0.10)
    assert rates["visual_odometry"] == pytest.approx(0.005)


def test_every_carried_rate_cites_a_source():
    for _source, _rate, note in DRIFT_RATES:
        assert note.strip() != ""


def test_budget_for_source_carries_everything_through():
    budget = budget_for_source("visual_odometry", 0.005, 15.0, note="test")
    assert budget.distance_m == pytest.approx(3000.0)
    assert budget.half_width_m == 15.0
    assert budget.note == "test"
