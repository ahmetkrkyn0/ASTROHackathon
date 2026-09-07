"""app.risk (B2): the closed-form normal CVaR, the slip and slope tails built
from C3's anchors and B3's slope sigma, their bit-equal array twins, the
route summary and the thermal hook that refuses."""

from __future__ import annotations

import math

import numpy as np
import pytest

from app import constants as C
from app.constants import get_rover
from app.risk import (
    RISK_ALPHA_MAX,
    RISK_ALPHA_MIN,
    RISK_CLAIM,
    RISK_MEASURE_ID,
    RISK_VALIDITY,
    cvar_multiplier,
    cvar_normal,
    risk_block,
    route_risk_summary,
    sigma_sources,
    slip_cvar,
    slip_cvar_array,
    slip_sensitivity,
    slip_sensitivity_array,
    slip_stats_array,
    slope_cvar,
    slope_cvar_array,
    thermal_cvar_cold_c,
)
from app.slip_model import MAX_SLIP_RATIO, curve_for, slip_ratio, slip_stats

ROVER_IDS = list(C.ROVERS)
ALPHAS = (0.5, 0.9, 0.99)


def _viper() -> dict:
    return dict(get_rover("nasa_viper"))


def _curveless() -> dict:
    rover = dict(get_rover("nasa_viper"))
    rover["slip_curve"] = None
    return rover


# ── closed form ─────────────────────────────────────────────────────────────


def test_the_multiplier_matches_the_standard_normal_table():
    # phi(z_alpha) / (1 - alpha): 0.5 -> 0.79788, 0.9 -> 1.75498, 0.99 -> 2.66521
    assert cvar_multiplier(0.5) == pytest.approx(0.7978845608, rel=1e-6)
    assert cvar_multiplier(0.9) == pytest.approx(1.7549833193, rel=1e-6)
    assert cvar_multiplier(0.99) == pytest.approx(2.6652142203, rel=1e-6)


def test_alpha_one_half_is_not_the_mean():
    assert cvar_normal(0.3, 0.1, 0.5) == pytest.approx(0.3 + 0.1 * 0.7978845608, rel=1e-9)
    assert cvar_normal(0.3, 0.1, 0.5) > 0.3


def test_out_of_range_alpha_is_refused():
    for bad in (0.0, 0.49, 1.0, 1.5, -0.1, float("nan")):
        with pytest.raises(ValueError):
            cvar_multiplier(bad)
    assert RISK_ALPHA_MIN == 0.5 and RISK_ALPHA_MAX == 0.999
    assert math.isfinite(cvar_multiplier(RISK_ALPHA_MAX))
    assert cvar_multiplier(RISK_ALPHA_MAX) == pytest.approx(3.3671, rel=1e-3)


def test_cvar_grows_with_alpha_and_refuses_a_negative_sigma():
    values = [cvar_normal(0.2, 0.05, a) for a in (0.5, 0.7, 0.9, 0.99, 0.999)]
    assert all(b > a for a, b in zip(values[:-1], values[1:]))
    assert cvar_normal(0.2, 0.0, 0.99) == 0.2
    with pytest.raises(ValueError):
        cvar_normal(0.2, -0.01, 0.9)


def test_the_closed_form_matches_a_monte_carlo_tail_mean():
    rng = np.random.default_rng(0)
    samples = rng.standard_normal(2_000_000)
    for alpha in ALPHAS:
        var = np.quantile(samples, alpha)
        tail_mean = float(samples[samples >= var].mean())
        assert abs(tail_mean - cvar_normal(0.0, 1.0, alpha)) < 1e-2
    # Affine: mu + sigma * X.
    scaled = 0.3 + 0.1 * samples
    var = np.quantile(scaled, 0.9)
    assert abs(float(scaled[scaled >= var].mean()) - cvar_normal(0.3, 0.1, 0.9)) < 1e-3


# ── slip sensitivity (delta method) ─────────────────────────────────────────


def test_slip_sensitivity_is_the_derivative_of_the_curve():
    rover = _viper()
    h = 1e-4
    for theta in (2.0, 7.5, 12.0, 14.9, 16.0, 19.0):
        numeric = (slip_ratio(theta + h, rover) - slip_ratio(theta - h, rover)) / (2 * h)
        assert slip_sensitivity(theta, rover) == pytest.approx(numeric, rel=1e-6)
        assert slip_sensitivity(theta, rover) > 0.0


def test_slip_sensitivity_is_zero_at_the_cap_and_without_a_curve():
    rover = get_rover("lpr_1")
    assert slip_ratio(22.0, rover) == MAX_SLIP_RATIO
    assert slip_sensitivity(22.0, rover) == 0.0
    assert slip_sensitivity(10.0, _curveless()) == 0.0
    assert slip_sensitivity(-10.0, rover) == slip_sensitivity(10.0, rover)
    assert math.isnan(slip_sensitivity(float("nan"), rover))


# ── slip and slope tails ────────────────────────────────────────────────────


def test_slip_cvar_sits_above_the_mean_and_under_the_cap():
    rover = _viper()
    for theta in (0.0, 5.0, 10.0, 15.0):
        mu, sigma = slip_stats(theta, rover)
        for alpha in ALPHAS:
            value = slip_cvar(theta, alpha, rover)
            assert value == pytest.approx(min(MAX_SLIP_RATIO, mu + sigma * cvar_multiplier(alpha)), rel=1e-12)
            assert mu <= value <= MAX_SLIP_RATIO
    assert slip_cvar(19.0, 0.99, rover) == MAX_SLIP_RATIO
    assert slip_cvar(10.0, 0.99, _curveless()) == 0.0
    assert math.isnan(slip_cvar(float("nan"), 0.9, rover))


def test_slope_sigma_widens_the_slip_tail_by_the_delta_method():
    rover = _viper()
    theta, alpha, sigma_theta = 10.0, 0.9, 1.5
    mu, sigma = slip_stats(theta, rover)
    total = math.sqrt(sigma * sigma + (slip_sensitivity(theta, rover) * sigma_theta) ** 2)
    expected = min(MAX_SLIP_RATIO, mu + total * cvar_multiplier(alpha))
    assert slip_cvar(theta, alpha, rover, sigma_theta) == pytest.approx(expected, rel=1e-12)
    assert slip_cvar(theta, alpha, rover, sigma_theta) > slip_cvar(theta, alpha, rover)
    # An unknown sigma does not widen anything.
    assert slip_cvar(theta, alpha, rover, float("nan")) == slip_cvar(theta, alpha, rover)
    assert slip_cvar(theta, alpha, rover, 0.0) == slip_cvar(theta, alpha, rover)


def test_slope_cvar_is_capped_at_the_rovers_limit_and_needs_a_sigma():
    rover = _viper()  # slope_max 20
    assert slope_cvar(10.0, 0.9, 1.5, rover) == pytest.approx(10.0 + 1.5 * cvar_multiplier(0.9), rel=1e-12)
    assert slope_cvar(19.0, 0.99, 1.5, rover) == 20.0
    assert slope_cvar(10.0, 0.9, None, rover) == 10.0
    assert slope_cvar(10.0, 0.9, float("nan"), rover) == 10.0
    assert slope_cvar(10.0, 0.9, 0.0, rover) == 10.0
    assert math.isnan(slope_cvar(float("nan"), 0.9, 1.5, rover))
    # Negative slopes are read by magnitude, like the slip curve.
    assert slope_cvar(-10.0, 0.9, 1.5, rover) == slope_cvar(10.0, 0.9, 1.5, rover)


# ── bit-parity of the array twins ───────────────────────────────────────────


def _thetas(rover: dict, n: int = 100_000) -> np.ndarray:
    rng = np.random.default_rng(7)
    curve = curve_for(rover)
    anchors = np.asarray([] if curve is None else curve.xs, dtype=np.float64)
    return np.concatenate([rng.uniform(0.0, 90.0, n), anchors, [float(rover["slope_max_deg"]), 20.1, 0.0]])


@pytest.mark.parametrize("rover_id", ROVER_IDS)
def test_slip_stats_array_is_bit_equal_to_the_scalar(rover_id):
    rover = get_rover(rover_id)
    thetas = _thetas(rover)
    mu, sigma = slip_stats_array(thetas, rover)
    scalar = [slip_stats(float(t), rover) for t in thetas]
    assert np.array_equal(mu, np.array([m for m, _ in scalar]))
    assert np.array_equal(sigma, np.array([s for _, s in scalar]))


@pytest.mark.parametrize("rover_id", ROVER_IDS)
def test_slip_sensitivity_array_is_bit_equal_to_the_scalar(rover_id):
    rover = get_rover(rover_id)
    thetas = _thetas(rover)
    assert np.array_equal(
        slip_sensitivity_array(thetas, rover), np.array([slip_sensitivity(float(t), rover) for t in thetas])
    )


@pytest.mark.parametrize("rover_id", ROVER_IDS)
@pytest.mark.parametrize("alpha", ALPHAS)
def test_slip_cvar_array_is_bit_equal_to_the_scalar(rover_id, alpha):
    rover = get_rover(rover_id)
    thetas = _thetas(rover, 50_000)
    rng = np.random.default_rng(11)
    sigmas = rng.uniform(0.0, 3.0, thetas.shape)
    sigmas[::97] = np.nan
    without = slip_cvar_array(thetas, alpha, rover)
    assert np.array_equal(without, np.array([slip_cvar(float(t), alpha, rover) for t in thetas]))
    with_sigma = slip_cvar_array(thetas, alpha, rover, sigmas)
    assert np.array_equal(
        with_sigma, np.array([slip_cvar(float(t), alpha, rover, float(s)) for t, s in zip(thetas, sigmas)])
    )
    assert np.all(with_sigma >= without)


@pytest.mark.parametrize("rover_id", ROVER_IDS)
def test_slope_cvar_array_is_bit_equal_to_the_scalar(rover_id):
    rover = get_rover(rover_id)
    thetas = _thetas(rover, 50_000)
    rng = np.random.default_rng(13)
    sigmas = rng.uniform(0.0, 3.0, thetas.shape)
    sigmas[::89] = np.nan
    for alpha in ALPHAS:
        vector = slope_cvar_array(thetas, alpha, sigmas, rover)
        assert np.array_equal(
            vector, np.array([slope_cvar(float(t), alpha, float(s), rover) for t, s in zip(thetas, sigmas)])
        )
        assert np.array_equal(slope_cvar_array(thetas, alpha, None, rover), np.abs(thetas))


def test_curveless_arrays_are_zero():
    rover = _curveless()
    thetas = np.array([0.0, 5.0, 40.0])
    assert np.array_equal(slip_cvar_array(thetas, 0.9, rover, np.ones(3)), np.zeros(3))
    assert np.array_equal(slip_sensitivity_array(thetas, rover), np.zeros(3))


# ── route summary and block ─────────────────────────────────────────────────


def test_route_risk_summary_prices_each_leg_at_its_tail():
    rover = _viper()
    alpha = 0.9
    legs = [(0.0, 320.0, 1.0, 100.0, 1.5), (15.0, 452.5, 2.0, 300.0, None)]
    out = route_risk_summary(legs, rover, alpha)
    s0 = slip_cvar(0.0, alpha, rover, 1.5)
    s15 = slip_cvar(15.0, alpha, rover, None)
    mu0, mu15 = slip_ratio(0.0, rover), slip_ratio(15.0, rover)
    assert out["moves"] == 2 and out["skipped_edges"] == 0
    assert out["mean_slip_mu"] == pytest.approx((320.0 * mu0 + 452.5 * mu15) / 772.5)
    assert out["mean_slip_cvar"] == pytest.approx((320.0 * s0 + 452.5 * s15) / 772.5)
    assert out["max_slip_cvar"] == pytest.approx(s15) and out["max_slip_cvar_slope_deg"] == 15.0
    assert out["max_slope_cvar_deg"] == pytest.approx(max(slope_cvar(0.0, alpha, 1.5, rover), 15.0))
    assert out["hours"] == pytest.approx(3.0)
    expected_hours = 1.0 * (1 - mu0) / (1 - s0) + 2.0 * (1 - mu15) / (1 - s15)
    assert out["risk_adjusted_hours"] == pytest.approx(expected_hours)
    assert out["hours_factor"] == pytest.approx(expected_hours / 3.0)
    assert out["drawn_wh"] == pytest.approx(400.0)
    assert out["risk_adjusted_drawn_wh"] == pytest.approx(
        100.0 * (1 - mu0) / (1 - s0) + 300.0 * (1 - mu15) / (1 - s15)
    )
    assert out["slope_sigma_known_fraction"] == pytest.approx(0.5)
    assert out["risk_adjusted_hours"] >= out["hours"]


def test_route_risk_summary_handles_missing_energy_infinite_legs_and_no_alpha():
    rover = _viper()
    legs = [(5.0, 320.0, 1.0, None, 1.0), (95.0, 320.0, float("inf"), 10.0, 1.0)]
    out = route_risk_summary(legs, rover, 0.9)
    assert out["moves"] == 1 and out["skipped_edges"] == 1
    assert out["risk_adjusted_drawn_wh"] is None and out["drawn_wh"] is None
    assert route_risk_summary(legs, rover, None) is None
    empty = route_risk_summary([], rover, 0.9)
    assert empty["moves"] == 0 and empty["hours"] == 0.0 and empty["risk_adjusted_hours"] == 0.0


def test_risk_block_says_what_was_applied_and_from_where():
    rover = _viper()
    sources = sigma_sources(rover, {"model": "pgda_clones", "n_clones": 100})
    assert sources["slope"]["source"] == "dem_clones" and sources["slope"]["n_clones"] == 100
    assert sources["slope"]["validity"] == "DERIVED"
    assert sources["slip"]["validity"] == "MODEL" and "C3" in sources["slip"]["source"]
    block = risk_block(0.9, sources, route={"moves": 1})
    assert block["alpha"] == 0.9 and block["applied"] is True
    assert block["criteria"] == {"slope": "cvar", "energy": "cvar"}
    assert block["multiplier"] == pytest.approx(cvar_multiplier(0.9))
    assert block["validity"] == RISK_VALIDITY == "MODEL"
    assert block["measure"] == RISK_MEASURE_ID
    assert "not a measured risk" in block["claim"].lower()

    none_sources = sigma_sources(rover, None)
    assert none_sources["slope"]["source"] == "none"
    block = risk_block(0.9, none_sources, route={"moves": 1})
    assert block["criteria"] == {"slope": "nominal", "energy": "cvar"}

    nominal = risk_block(None, none_sources)
    assert nominal["alpha"] is None and nominal["applied"] is False and nominal["route"] is None
    assert nominal["criteria"] == {"slope": "nominal", "energy": "nominal"}
    assert nominal["multiplier"] is None

    curveless = sigma_sources(_curveless(), None)
    assert curveless["slip"]["source"].startswith("none")


def test_the_thermal_tail_is_a_hook_that_refuses():
    with pytest.raises(NotImplementedError) as info:
        thermal_cvar_cold_c(np.array([-40.0]), np.array([-90.0]), 0.9)
    message = str(info.value).lower()
    assert "thermal" in message and "no source" in message


def test_labels_and_claim():
    assert RISK_VALIDITY == "MODEL" and RISK_VALIDITY != "MEASURED"
    assert "not a measured risk" in RISK_CLAIM.lower()
    assert "ranking" in RISK_CLAIM.lower()
