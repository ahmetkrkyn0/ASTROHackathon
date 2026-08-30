"""Dedicated tests for app.cost_vec.

The array forms are the ones the planner and the cost map actually run;
app.cost_engine holds the scalar reference. Before this module the array
forms were asserted only inside a review regression file, so a rewrite that
dropped that file would have left the hot path untested.
(Round 3 review, L-19.)
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))

from app import constants as C
from app.constants import get_rover
from app.cost_engine import f_shadow_cell, f_slope, f_thermal, surface_to_inner
from app.cost_vec import (
    f_energy_cell_grid,
    f_shadow_cell_grid,
    f_slope_grid,
    f_thermal_grid,
    surface_to_inner_grid,
)

ROVER_IDS = list(C.ROVERS)


@pytest.mark.parametrize("rover_id", ROVER_IDS)
def test_slope_matches_the_scalar_reference(rover_id):
    rover = get_rover(rover_id)
    slopes = np.linspace(-5.0, float(rover["slope_max_deg"]) + 5.0, 61)
    vector = f_slope_grid(slopes, rover)
    for value, angle in zip(vector, slopes):
        assert value == pytest.approx(f_slope(float(angle), rover))


@pytest.mark.parametrize("rover_id", ROVER_IDS)
def test_thermal_matches_the_scalar_reference(rover_id):
    rover = get_rover(rover_id)
    temperatures = np.linspace(-200.0, 120.0, 65)
    vector = f_thermal_grid(temperatures, rover)
    for value, temperature in zip(vector, temperatures):
        assert value == pytest.approx(f_thermal(float(temperature), rover))


def test_shadow_matches_the_scalar_reference():
    ratios = np.linspace(-0.5, 1.5, 41)
    vector = f_shadow_cell_grid(ratios)
    for value, ratio in zip(vector, ratios):
        assert value == pytest.approx(f_shadow_cell(float(ratio)))


@pytest.mark.parametrize("rover_id", ROVER_IDS)
def test_surface_to_inner_matches_the_scalar_reference(rover_id):
    rover = get_rover(rover_id)
    temperatures = np.linspace(-200.0, 120.0, 33)
    vector = surface_to_inner_grid(temperatures, rover)
    for value, temperature in zip(vector, temperatures):
        assert value == pytest.approx(surface_to_inner(float(temperature), rover))


def test_shapes_and_dtypes_are_preserved():
    rover = get_rover("lpr_1")
    slopes = np.zeros((4, 7))
    shadows = np.zeros((4, 7))
    for grid in (
        f_slope_grid(slopes, rover),
        f_energy_cell_grid(slopes, rover, shadows),
        f_shadow_cell_grid(shadows),
        f_thermal_grid(slopes, rover),
    ):
        assert grid.shape == (4, 7)
        assert grid.dtype == np.float64


def test_above_the_slope_limit_is_infinite_in_both_terms():
    rover = get_rover("lpr_1")
    over = np.array([float(rover["slope_max_deg"]) + 0.1])
    assert np.isinf(f_slope_grid(over, rover)).all()
    assert np.isinf(f_energy_cell_grid(over, rover)).all()


def test_energy_is_bounded_to_the_mru_range():
    rover = get_rover("lpr_1")
    rng = np.random.default_rng(3)
    slopes = rng.uniform(0.0, float(rover["slope_max_deg"]), 500)
    shadows = rng.uniform(0.0, 1.0, 500)
    values = f_energy_cell_grid(slopes, rover, shadows)
    assert values.min() >= 0.0
    assert values.max() <= 1.0


def test_energy_is_monotone_in_both_inputs():
    rover = get_rover("lpr_1")
    slopes = np.linspace(0.0, 25.0, 20)
    for shadow in (0.0, 0.5, 1.0):
        values = f_energy_cell_grid(slopes, rover, np.full_like(slopes, shadow))
        assert np.all(np.diff(values) >= -1e-12)

    shadows = np.linspace(0.0, 1.0, 20)
    for slope in (0.0, 10.0, 20.0):
        values = f_energy_cell_grid(np.full_like(shadows, slope), rover, shadows)
        assert np.all(np.diff(values) >= -1e-12)


def test_a_rover_without_a_thermal_envelope_gets_a_zero_penalty():
    rover = dict(get_rover("lpr_1"))
    for key in ("bat_op_min_c", "bat_op_max_c", "elec_op_min_c", "elec_op_max_c"):
        rover[key] = None
    assert f_thermal_grid(np.array([-200.0, 0.0, 200.0]), rover).tolist() == [
        0.0,
        0.0,
        0.0,
    ]
