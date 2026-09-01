"""The evidence contract: what may reach the language model, and in what form.

Every assertion here defends a specific trap from
docs/ai/LunaPath_AI_Chatbot_Scope_v0.3.md section 4. The sanitizers are the
only path from raw backend dicts to model context, so a field that survives
one of these tests is a field the model can hallucinate a story about.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import pytest

from app.ai_evidence import (
    Quantity,
    display_pedigree,
    sanitize_cell_telemetry,
    sanitize_compare,
    sanitize_current_plan,
    weakest_validity,
)


# ── provenance ladder ─────────────────────────────────────────────────────────

def test_weakest_validity_picks_the_lowest_rung_of_the_raw_ladder():
    assert weakest_validity(["MEASURED", "DERIVED", "MODEL"]) == "DERIVED"
    assert weakest_validity(["MEASURED", "MODEL"]) == "MODEL"
    assert weakest_validity(["MEASURED"]) == "MEASURED"


def test_synthetic_beats_every_other_rung_downwards():
    assert weakest_validity(["MEASURED", "MODEL", "DERIVED", "SYNTHETIC"]) == "SYNTHETIC"


def test_weakest_validity_of_nothing_is_unknown_not_a_guess():
    assert weakest_validity([]) is None


def test_unrecognised_validity_does_not_silently_become_the_strongest():
    # An unknown label is not evidence that the data is good.
    assert weakest_validity(["MEASURED", "GRADE_A_BEEF"]) is None


def test_display_pedigree_collapses_four_raw_rungs_onto_three_ui_levels():
    assert display_pedigree("MEASURED") == "measurement"
    assert display_pedigree("MODEL") == "model"
    assert display_pedigree("DERIVED") == "model"
    assert display_pedigree("SYNTHETIC") == "demo"


def test_display_pedigree_of_unknown_is_none():
    assert display_pedigree(None) is None


# ── Quantity: a number without a unit is not evidence ─────────────────────────

def test_quantity_keeps_value_and_unit_together():
    q = Quantity(value=1490.23, unit="Wh")
    assert q.value == 1490.23
    assert q.unit == "Wh"


def test_quantity_rejects_a_missing_unit():
    with pytest.raises(Exception):
        Quantity(value=1.0, unit="")


def test_quantity_rejects_a_non_finite_value():
    with pytest.raises(Exception):
        Quantity(value=float("nan"), unit="Wh")


# ── current plan sanitizer ────────────────────────────────────────────────────

def _plan_response() -> dict:
    """A /api/plan response shaped like the real one, traps included."""
    return {
        "status": "success",
        "summary": {
            "total_distance_km": 3.0996,
            "total_elapsed_hours": 4.3,
            "final_battery_pct": 74.0,
            "min_battery_pct": 72.5,
            "max_slope_deg": 12.0,
            "max_segment_slope_deg": 11.5,
            "total_energy_consumed_wh": 1490.23,
            "total_shadow_exposure": 0.9123,
            "critical_steps_count": 0,
            "high_or_above_steps_count": 2,
            "waypoint_count": 495,
            "total_recharges": 0,
            "stranded": False,
            "stranded_at_step": None,
            "max_continuous_shadow_h": 3.4147,
            "shadow_limit_h": 40.0,
            "shadow_limit_exceeded": False,
            "peak_power_exceeded_steps": 0,
        },
        "astar_metrics": {
            "total_distance_m": 3099.55,
            "total_energy_wh": None,
            "total_shadow_hours": None,
            "max_slope_deg": 12.0,
            "max_segment_slope_deg": 11.5,
            "max_cell_slope_deg": 11.9,
            "max_thermal_risk": 0.31,
            "min_surface_temp_c": -180.0,
            "max_surface_temp_c": -20.0,
            "total_weighted_cost": 4688.451,
            "total_weighted_cost_cells_only": 4068.1,
            "barrier_share": 0.13215,
            "cost_units": "weighted_metres",
            "path_length_nodes": 495,
            "computation_time_ms": 4291.0,
            "nodes_expanded": 113319,
            "edges_rejected": {"step_slope": 27, "lateral_slope": 5370},
        },
        "corridor": {"corridor_id": "abc123def456", "waypoints": []},
        "route_statistics": {"mean_slope_deg": 6.0},
        "execution": {"stranded": False, "truncated": False, "reason": None},
        "waypoints": [{"step": i} for i in range(495)],
        "geojson": {"type": "FeatureCollection", "features": []},
        "rover": {"id": "lpr_1", "name": "LPR-1"},
    }


def _flatten(obj) -> str:
    import json

    return json.dumps(obj, default=str)


def test_current_plan_energy_comes_from_the_summary_not_the_null_metric():
    plan = sanitize_current_plan(_plan_response())
    assert plan["energy"]["value"] == 1490.23
    assert plan["energy"]["unit"] == "Wh"


def test_current_plan_continuous_shadow_comes_from_the_summary():
    plan = sanitize_current_plan(_plan_response())
    assert plan["max_continuous_shadow"]["value"] == 3.4147
    assert plan["max_continuous_shadow"]["unit"] == "h"


def test_current_plan_never_carries_the_always_null_astar_energy_field():
    blob = _flatten(sanitize_current_plan(_plan_response()))
    assert "total_energy_wh" not in blob
    assert "total_shadow_hours" not in blob


def test_current_plan_never_carries_total_shadow_exposure():
    blob = _flatten(sanitize_current_plan(_plan_response()))
    assert "total_shadow_exposure" not in blob


def test_current_plan_strips_nondeterministic_comparison_noise():
    blob = _flatten(sanitize_current_plan(_plan_response()))
    assert "computation_time_ms" not in blob
    assert "corridor_id" not in blob
    assert "abc123def456" not in blob


def test_current_plan_does_not_ship_hundreds_of_waypoints_to_the_model():
    blob = _flatten(sanitize_current_plan(_plan_response()))
    assert "geojson" not in blob
    # The count is useful; the array is 495 objects of token burn.
    assert len(blob) < 4000


def test_current_plan_keeps_the_edges_rejected_counters():
    plan = sanitize_current_plan(_plan_response())
    assert plan["edges_rejected"]["lateral_slope"] == 5370


def test_current_plan_of_nothing_is_none():
    assert sanitize_current_plan(None) is None


# ── cell telemetry sanitizer ──────────────────────────────────────────────────

def _cell_response() -> dict:
    return {
        "row": 250,
        "col": 250,
        "lon": 12.5,
        "lat": -88.9,
        "altitude_m": 1820.4,
        "thermal_c": -45.0,
        "thermal_min_c": -180.0,
        "resolution_m": 5.0,
        "span_km": 2.5,
        "cost_breakdown": {
            "slope": 0.12,
            "energy": 0.08,
            "shadow": 0.05,
            "thermal": 0.06,
            "total": 0.3056,
        },
        "layer_validity": {
            "elevation": "MEASURED",
            "slope": "DERIVED",
            "thermal": "DERIVED",
        },
    }


_PLAN_WEIGHTS = {
    "w_slope": 0.409,
    "w_energy": 0.259,
    "w_shadow": 0.142,
    "w_thermal": 0.190,
}


def test_cell_keeps_physical_telemetry_with_units():
    cell = sanitize_cell_telemetry(
        _cell_response(), plan_weights=_PLAN_WEIGHTS, grid_weights=_PLAN_WEIGHTS
    )
    assert cell["altitude"]["unit"] == "m"
    assert cell["thermal"]["unit"] == "degC"
    assert cell["thermal"]["value"] == -45.0


def test_cell_carries_cost_breakdown_when_weights_agree():
    cell = sanitize_cell_telemetry(
        _cell_response(), plan_weights=_PLAN_WEIGHTS, grid_weights=_PLAN_WEIGHTS
    )
    assert cell["cost_breakdown"]["slope"] == 0.12
    assert cell["limitations"] == []


def test_cell_suppresses_cost_breakdown_when_the_plan_used_other_weights():
    # T-3: cell-telemetry always explains with the grid's stamped weights, so
    # a plan run on custom weights gets a decomposition of a different cost
    # landscape than the one it was routed through.
    plan_weights = dict(_PLAN_WEIGHTS, w_energy=0.45)
    cell = sanitize_cell_telemetry(
        _cell_response(), plan_weights=plan_weights, grid_weights=_PLAN_WEIGHTS
    )
    assert "cost_breakdown" not in cell
    assert "CELL_COST_BREAKDOWN_WEIGHT_MISMATCH" in [
        item["code"] for item in cell["limitations"]
    ]


def test_the_weight_mismatch_limitation_explains_itself_deterministically():
    plan_weights = dict(_PLAN_WEIGHTS, w_energy=0.45)
    cell = sanitize_cell_telemetry(
        _cell_response(), plan_weights=plan_weights, grid_weights=_PLAN_WEIGHTS
    )
    message = cell["limitations"][0]["message"]
    # The model must be told, not left to notice.
    assert len(message) > 40


def test_cell_suppression_keeps_the_safe_location_telemetry():
    plan_weights = dict(_PLAN_WEIGHTS, w_energy=0.45)
    cell = sanitize_cell_telemetry(
        _cell_response(), plan_weights=plan_weights, grid_weights=_PLAN_WEIGHTS
    )
    assert cell["altitude"]["value"] == 1820.4
    assert cell["row"] == 250


def test_cell_preserves_raw_layer_validity_and_adds_the_display_mapping():
    cell = sanitize_cell_telemetry(
        _cell_response(), plan_weights=_PLAN_WEIGHTS, grid_weights=_PLAN_WEIGHTS
    )
    assert cell["layer_validity"]["slope"] == "DERIVED"
    assert cell["provenance"]["rawValidity"] == "DERIVED"
    assert cell["provenance"]["displayPedigree"] == "model"


def test_cell_omits_a_value_the_backend_had_no_number_for():
    raw = _cell_response()
    raw["altitude_m"] = None
    cell = sanitize_cell_telemetry(
        raw, plan_weights=_PLAN_WEIGHTS, grid_weights=_PLAN_WEIGHTS
    )
    assert "altitude" not in cell


# ── compare sanitizer ─────────────────────────────────────────────────────────

def _compare_response() -> dict:
    def profile(pid: str, energy: float) -> dict:
        return {
            "profile_id": pid,
            "profile_name": pid.title(),
            "color": "#3B82F6",
            "error": None,
            "path_pixels": [[r, r] for r in range(495)],
            "metrics": {
                "total_distance_m": 3099.55,
                "total_energy_wh": None,
                "total_shadow_hours": None,
                "max_slope_deg": 12.0,
                "max_segment_slope_deg": 11.5,
                "max_cell_slope_deg": 11.9,
                "min_surface_temp_c": -180.0,
                "max_surface_temp_c": -20.0,
                "max_thermal_risk": 0.31,
                "total_weighted_cost": 4688.451,
                "total_weighted_cost_cells_only": 4068.1,
                "barrier_share": 0.13215,
                "cost_units": "weighted_metres",
                "path_length_nodes": 495,
                "computation_time_ms": 4291.0,
                "nodes_expanded": 113319,
                "edges_rejected": {"step_slope": 27, "lateral_slope": 5370},
            },
            "simulation_summary": {
                "total_distance_km": 3.0996,
                "total_elapsed_hours": 4.3,
                "final_battery_pct": 74.0,
                "min_battery_pct": 72.5,
                "max_slope_deg": 12.0,
                "max_segment_slope_deg": 11.5,
                "total_energy_consumed_wh": energy,
                "total_shadow_exposure": 0.9123,
                "critical_steps_count": 0,
                "high_or_above_steps_count": 2,
                "waypoint_count": 495,
                "total_recharges": 0,
                "stranded": False,
                "stranded_at_step": None,
                "max_continuous_shadow_h": 3.4147,
                "shadow_limit_h": 40.0,
                "shadow_limit_exceeded": False,
                "peak_power_exceeded_steps": 0,
            },
            "constraint_check": {
                "max_energy_wh": {
                    "limit": 4000.0,
                    "actual": energy,
                    "satisfied": True,
                    "enforced_in_search": False,
                    "checked": True,
                },
            },
        }

    return {
        "start": [50, 50],
        "goal": [440, 440],
        "results": [
            profile("balanced", 1490.23),
            profile("energy_saver", 1500.58),
        ],
        "comparison": {
            "shortest_profile": "balanced",
            "safest_profile": "balanced",
            "most_efficient_profile": "balanced",
            "recommendation": (
                "balanced minimizes the weighted safety envelope; Energy and "
                "shadow totals are not tracked in fast mode, so neither "
                "ranking is an energy claim."
            ),
        },
    }


def test_compare_never_passes_the_stale_recommendation_to_the_model():
    # T-13. The sentence contradicts the simulation_summary in the same body.
    blob = _flatten(sanitize_compare(_compare_response()))
    assert "recommendation" not in blob
    assert "not tracked in fast mode" not in blob


def test_compare_keeps_the_real_energy_from_simulation_summary():
    out = sanitize_compare(_compare_response())
    energies = {
        p["profile_id"]: p["simulation_summary"]["total_energy_consumed_wh"]
        for p in out["profiles"]
    }
    assert energies == {"balanced": 1490.23, "energy_saver": 1500.58}


def test_compare_keeps_continuous_shadow_from_simulation_summary():
    out = sanitize_compare(_compare_response())
    first = out["profiles"][0]["simulation_summary"]
    assert first["max_continuous_shadow_h"] == 3.4147


def test_compare_drops_total_shadow_exposure_from_every_profile():
    blob = _flatten(sanitize_compare(_compare_response()))
    assert "total_shadow_exposure" not in blob


def test_compare_drops_the_always_null_astar_energy_and_shadow_metrics():
    blob = _flatten(sanitize_compare(_compare_response()))
    assert "total_energy_wh" not in blob
    assert "total_shadow_hours" not in blob


def test_compare_strips_computation_time_from_every_profile():
    blob = _flatten(sanitize_compare(_compare_response()))
    assert "computation_time_ms" not in blob


def test_compare_does_not_ship_route_geometry_to_the_model():
    blob = _flatten(sanitize_compare(_compare_response()))
    assert "path_pixels" not in blob
    assert "color" not in blob


def test_compare_preserves_constraint_check():
    out = sanitize_compare(_compare_response())
    check = out["profiles"][0]["constraint_check"]["max_energy_wh"]
    assert check["limit"] == 4000.0
    assert check["satisfied"] is True


def test_compare_keeps_the_edges_rejected_counters_that_answer_why_winding():
    out = sanitize_compare(_compare_response())
    assert out["profiles"][0]["metrics"]["edges_rejected"]["lateral_slope"] == 5370


def test_compare_reports_the_profile_weights_so_the_model_can_see_all_four_moved():
    # R-12: energy_saver is not "the same run with more energy weight".
    out = sanitize_compare(_compare_response())
    weights = out["profiles"][0]["weights"]
    assert set(weights) == {"w_slope", "w_energy", "w_shadow", "w_thermal"}


def test_compare_surfaces_a_failed_profile_as_an_error_not_a_silent_gap():
    raw = _compare_response()
    raw["results"][1]["error"] = "No path found"
    raw["results"][1]["metrics"] = {}
    raw["results"][1]["simulation_summary"] = None
    out = sanitize_compare(raw)
    assert out["profiles"][1]["error"] == "No path found"
