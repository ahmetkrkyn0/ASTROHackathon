"""Dedicated tests for app.scenarios. (Round 3 review, L-19.)"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from app.constants import get_rover
from app.scenarios import (
    MISSION_PROFILES,
    compare_results,
    get_profile,
    list_profiles,
)


def _result(profile_id, distance, thermal, slope, cost):
    return {
        "profile_id": profile_id,
        "metrics": {
            "total_distance_m": distance,
            "max_thermal_risk": thermal,
            "max_slope_deg": slope,
            "total_weighted_cost": cost,
        },
    }


def test_every_profile_declares_the_full_weight_and_constraint_set():
    for profile_id, profile in MISSION_PROFILES.items():
        assert set(profile["weights"]) == {
            "w_slope",
            "w_energy",
            "w_shadow",
            "w_thermal",
        }, profile_id
        assert set(profile["constraints"]) == {
            "max_shadow_h",
            "max_slope_deg",
            "max_energy_wh",
            "min_soc",
        }, profile_id
        assert profile["color"].startswith("#")


def test_profile_slope_ceilings_are_within_the_default_rovers_limit():
    """A profile may only TIGHTEN the rover's limit, never loosen it."""
    limit = float(get_rover("lpr_1")["slope_max_deg"])
    for profile_id, profile in MISSION_PROFILES.items():
        assert profile["constraints"]["max_slope_deg"] <= limit, profile_id


def test_get_profile_returns_none_for_an_unknown_id():
    assert get_profile("no_such_profile") is None
    assert get_profile("balanced") is MISSION_PROFILES["balanced"]

    # list_profiles no longer returns the registry itself: it annotates each
    # constraint with HOW it is applied. A profile published four numbers
    # that read as equally binding while the planner enforced one of them.
    # (Round 4 review, M-4.)
    listed = list_profiles()
    assert set(listed) == set(MISSION_PROFILES)
    for profile_id, profile in listed.items():
        assert profile["constraints"] == MISSION_PROFILES[profile_id]["constraints"]
        handling = profile["constraint_handling"]
        assert set(handling) == set(profile["constraints"])
        assert handling["max_slope_deg"] == "enforced_in_search"
        for key in ("max_shadow_h", "max_energy_wh", "min_soc"):
            assert handling[key] == "verified_after_simulation"


def test_compare_results_handles_an_all_failed_set():
    summary = compare_results([{"profile_id": "a", "error": "boom"}])
    assert summary["shortest_profile"] is None
    assert summary["safest_profile"] is None
    assert summary["most_efficient_profile"] is None


def test_compare_results_ranks_on_the_stated_metrics():
    results = [
        _result("short", 100.0, 0.5, 10.0, 50.0),
        _result("cheap", 300.0, 0.5, 10.0, 20.0),
        _result("safe", 200.0, 0.1, 5.0, 40.0),
    ]
    summary = compare_results(results, get_rover("lpr_1"))
    assert summary["shortest_profile"] == "short"
    assert summary["most_efficient_profile"] == "cheap"
    assert summary["safest_profile"] == "safe"


def test_the_recommendation_disclaims_the_untracked_totals():
    summary = compare_results(
        [_result("a", 1.0, 0.1, 1.0, 1.0)], get_rover("lpr_1")
    )
    assert "not tracked in fast mode" in summary["recommendation"]
