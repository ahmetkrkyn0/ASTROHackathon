"""C3: slip enters the energy/time model at ONE point, edge_travel_time_s.

Every time and energy figure derives from that function, so the checks
here are about (a) the formula itself, (b) the vectorised twin agreeing
with it bit for bit -- the planner calls the scalar per edge while the
gated graph and the corridor tables are vectorised, and a move of
exactly one slice must round the same way in both -- and (c) the
derived quantities scaling by exactly 1 / (1 - slip).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.constants import ROVERS, get_rover
from app.cost_engine import (
    COST_MODEL_ID,
    edge_energy_wh,
    edge_travel_time_s,
    edge_travel_time_s_array,
    f_energy_cell,
    gross_energy_per_metre_wh,
    move_battery_drain_wh,
)
from app.slip_model import slip_ratio


def _slip_free(rover_id: str = "nasa_viper") -> dict:
    rover = dict(get_rover(rover_id))
    rover["slip_curve"] = None
    return rover


def test_travel_time_applies_the_effective_distance_of_the_profiles_curve():
    rover = get_rover("nasa_viper")
    theta, d = 10.0, 320.0
    cos_t = math.cos(math.radians(theta))
    expected = (d / cos_t) / (1.0 - slip_ratio(theta, rover)) / (float(rover["v_max_ms"]) * cos_t)
    assert edge_travel_time_s(theta, d, rover) == pytest.approx(expected, rel=1e-12)


def test_a_profile_without_a_curve_keeps_the_slip_free_formula():
    rover = _slip_free()
    theta, d = 10.0, 320.0
    cos_t = math.cos(math.radians(theta))
    assert edge_travel_time_s(theta, d, rover) == pytest.approx(
        (d / cos_t) / (float(rover["v_max_ms"]) * cos_t), rel=1e-15
    )


def test_slip_lengthens_travel_time_and_more_so_on_steeper_slopes():
    with_slip = get_rover("nasa_viper")
    without = _slip_free()
    ratios = [
        edge_travel_time_s(theta, 320.0, with_slip) / edge_travel_time_s(theta, 320.0, without)
        for theta in (0.0, 5.0, 10.0, 15.0)
    ]
    assert all(r > 1.0 for r in ratios)
    assert ratios == sorted(ratios)
    assert ratios[3] == pytest.approx(1.0 / (1.0 - 0.40), rel=1e-9)


@pytest.mark.parametrize("rover_id", list(ROVERS))
def test_the_vectorised_travel_time_matches_the_scalar_bit_for_bit(rover_id):
    rover = get_rover(rover_id)
    rng = np.random.default_rng(17)
    thetas = np.concatenate([rng.uniform(0.0, 89.0, 100_000), [0.0, 8.86, 15.0, 20.0, 25.0]])
    distances = np.concatenate([rng.uniform(1.0, 500.0, 100_000), np.full(5, 320.0)])
    vector = edge_travel_time_s_array(thetas, distances, rover)
    scalar = np.array(
        [edge_travel_time_s(float(t), float(d), rover) for t, d in zip(thetas, distances)]
    )
    assert vector.dtype == np.float64
    assert np.array_equal(vector, scalar)


def test_the_vectorised_travel_time_accepts_a_scalar_distance():
    rover = get_rover("lpr_1")
    thetas = np.array([0.0, 5.0, 10.0])
    assert np.array_equal(
        edge_travel_time_s_array(thetas, 320.0, rover),
        edge_travel_time_s_array(thetas, np.full(3, 320.0), rover),
    )


def test_a_vertical_or_overhanging_edge_is_infinite_in_both_paths():
    rover = get_rover("lpr_1")
    assert math.isinf(edge_travel_time_s(95.0, 10.0, rover))
    assert math.isinf(edge_travel_time_s(120.0, 10.0, rover))
    vector = edge_travel_time_s_array(np.array([95.0, 120.0, 10.0]), 10.0, rover)
    assert np.isinf(vector[0]) and np.isinf(vector[1]) and np.isfinite(vector[2])


def test_edge_energy_scales_by_exactly_one_over_one_minus_slip():
    rover = get_rover("nasa_viper")
    plain = edge_energy_wh(10.0, 100.0, _slip_free())
    corrected = edge_energy_wh(10.0, 100.0, rover)
    assert corrected == pytest.approx(plain / (1.0 - slip_ratio(10.0, rover)), rel=1e-12)


def test_the_battery_drain_of_a_move_scales_with_the_same_factor():
    """Traction, housekeeping and solar income are all per unit TIME, so a
    slip-lengthened move scales every term together."""
    rover = get_rover("nasa_viper")
    plain = move_battery_drain_wh(12.0, 320.0, 0.3, _slip_free())
    corrected = move_battery_drain_wh(12.0, 320.0, 0.3, rover)
    assert corrected == pytest.approx(plain / (1.0 - slip_ratio(12.0, rover)), rel=1e-12)
    assert gross_energy_per_metre_wh(12.0, 0.3, rover) == pytest.approx(
        gross_energy_per_metre_wh(12.0, 0.3, _slip_free()) / (1.0 - slip_ratio(12.0, rover)),
        rel=1e-12,
    )


def test_the_energy_criterion_keeps_its_normalisation_under_slip():
    rover = get_rover("nasa_viper")
    assert f_energy_cell(0.0, rover, 0.0) == 0.0
    assert f_energy_cell(float(rover["slope_max_deg"]), rover, 1.0) == pytest.approx(1.0)
    assert 0.0 < f_energy_cell(10.0, rover, 0.5) < 1.0


def test_the_cost_model_id_says_slip_is_in_the_grid():
    """A cost grid computed by the slip-free build must not be reused."""
    assert COST_MODEL_ID.endswith("slip_v4")


def test_the_energy_criterion_keeps_its_scale_when_slip_enters():
    """Normalising against the slip-inclusive worst cell (25 deg at slip
    0.9, ten times the slip-free time) squeezed every ordinary cell into
    [0, 0.15] and the criterion collapsed back towards a monotone function
    of slope -- the H-4 failure. The scale stays the slip-free worst
    admissible cell: slip raises a cell's penalty on that fixed scale, and
    cells that exceed it saturate at 1.0."""
    lpr = get_rover("lpr_1")
    dark_10 = f_energy_cell(10.0, lpr, 1.0)
    assert dark_10 > 0.3, dark_10
    assert dark_10 > f_energy_cell(10.0, _slip_free("lpr_1"), 1.0)
    assert f_energy_cell(22.0, lpr, 1.0) == 1.0
    assert f_energy_cell(float(lpr["slope_max_deg"]), _slip_free("lpr_1"), 1.0) == pytest.approx(1.0)


def test_the_vectorised_energy_criterion_includes_slip_like_the_scalar():
    from app.cost_vec import f_energy_cell_grid

    for rover_id in ROVERS:
        rover = get_rover(rover_id)
        slopes = np.linspace(0.0, float(rover["slope_max_deg"]), 23)
        shadows = np.linspace(0.0, 1.0, 23)
        vector = f_energy_cell_grid(slopes, rover, shadows)
        scalar = np.array([f_energy_cell(float(s), rover, float(h)) for s, h in zip(slopes, shadows)])
        np.testing.assert_allclose(vector, scalar, atol=1e-12)
