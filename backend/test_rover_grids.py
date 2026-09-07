"""Dedicated tests for app.rover_grids.

Referenced by exactly one other test file before this one, so the module
that decides WHICH traversability mask and cost grid a plan runs against --
a safety decision -- had no test of its own. (Round 3 review, L-19.)
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))

from app.cost_engine import COST_MODEL_ID
from app.rover_grids import grids_for_rover


def _base(shape=(6, 6)):
    slope = np.full(shape, 10.0, dtype=np.float64)
    slope[0, 0] = 22.0          # passable for lpr_1 (25), not for viper (20)
    return {
        "elevation": np.zeros(shape, dtype=np.float64),
        "slope": slope,
        "thermal": np.full(shape, -40.0, dtype=np.float64),
        "shadow_ratio": np.zeros(shape, dtype=np.float64),
        "traversable": np.ones(shape, dtype=bool),
        "cost": np.zeros(shape, dtype=np.float64),
        "metadata": {
            "resolution_m": 10.0,
            "shape": list(shape),
            "default_rover_id": "lpr_1",
            "cost_weights": {},
            "cost_model": COST_MODEL_ID,
        },
    }


def test_the_mask_follows_the_rovers_own_slope_limit():
    base = _base()
    assert bool(grids_for_rover(base, "lpr_1")["traversable"][0, 0]) is True
    assert bool(grids_for_rover(base, "nasa_viper")["traversable"][0, 0]) is False


def test_the_mask_is_recomputed_even_when_the_label_agrees():
    """default_rover_id is only a LABEL; a mask that disagrees with it must
    not be trusted."""
    base = _base()
    base["traversable"][:] = True
    base["traversable"][3, 3] = False  # a lie: nothing about (3,3) is blocked
    adapted = grids_for_rover(base, "lpr_1")
    assert bool(adapted["traversable"][3, 3]) is True


def test_metadata_records_the_rover_and_the_resolved_weights():
    adapted = grids_for_rover(base := _base(), "cnsa_yutu_2")
    assert adapted["metadata"]["rover_id"] == "cnsa_yutu_2"
    assert adapted["metadata"]["rover_name"] == "CNSA Yutu-2"
    assert adapted["metadata"]["default_rover_id"] == "lpr_1"
    assert set(adapted["metadata"]["cost_weights"]) == {
        "w_slope",
        "w_energy",
        "w_shadow",
        "w_thermal",
        "w_roughness",  # C4
    }
    assert base["metadata"].get("rover_id") is None  # the input is not mutated


def test_a_stale_cost_model_forces_a_recompute():
    base = _base()
    base["metadata"]["cost_model"] = "older_formula"
    adapted = grids_for_rover(base, "lpr_1")
    assert adapted["metadata"]["cost_model"] == COST_MODEL_ID
    assert not np.array_equal(adapted["cost"], base["cost"])


def test_blocked_cells_cost_infinity():
    base = _base()
    base["slope"][2, 2] = 80.0
    adapted = grids_for_rover(base, "lpr_1")
    assert not bool(adapted["traversable"][2, 2])
    assert np.isinf(adapted["cost"][2, 2])


def test_weight_overrides_change_the_cost_grid():
    base = _base()
    flat = grids_for_rover(base, "lpr_1", {"w_slope": 0.0})
    steep = grids_for_rover(base, "lpr_1", {"w_slope": 2.0})
    assert not np.allclose(flat["cost"], steep["cost"])
