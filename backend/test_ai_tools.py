"""The tool registry is the authorization boundary, not the prompt.

The model proposes a function name and arguments; nothing here trusts either.
These tests pin the two properties that make that safe: the registry contains
exactly the two approved read-only tools, and the budget is counted on the
server where the model cannot see or raise it.

Contract: docs/ai/LunaPath_AI_Chatbot_Scope_v0.3.md sections 5, 6 and 7.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

os.environ["LUNAPATH_SKIP_STARTUP"] = "YES"

import numpy as np
import pytest

from app.ai_tools import (
    MAX_COMPARE_CALLS,
    MAX_READ_CALLS,
    AiToolError,
    ToolBudget,
    ToolRegistry,
    tool_specifications,
)
from app.cost_engine import COST_MODEL_ID

SHAPE = (20, 20)

_WEIGHTS = {
    "w_slope": 0.409,
    "w_energy": 0.259,
    "w_shadow": 0.142,
    "w_thermal": 0.190,
}


def _make_grids() -> dict:
    """A synthetic flat 20x20 grid set, matching test_plan_endpoint's shape."""
    return {
        "elevation": np.zeros(SHAPE, dtype=np.float64),
        "slope": np.full(SHAPE, 5.0, dtype=np.float64),
        "aspect": np.zeros(SHAPE, dtype=np.float64),
        "thermal": np.full(SHAPE, -50.0, dtype=np.float64),
        "shadow_ratio": np.full(SHAPE, 0.1, dtype=np.float64),
        "cost": np.full(SHAPE, 0.5, dtype=np.float64),
        "traversable": np.full(SHAPE, True, dtype=bool),
        "metadata": {
            "resolution_m": 80.0,
            "shape": list(SHAPE),
            "crs": "moon_sp",
            "source": "synthetic_test",
            "cost_weights": dict(_WEIGHTS),
            "cost_model": COST_MODEL_ID,
            "default_rover_id": "lpr_1",
            "layer_validity": {
                "elevation": "MEASURED",
                "slope": "DERIVED",
                "thermal": "DERIVED",
            },
        },
    }


def _snapshot(**overrides):
    from app.ai_contract import AiMissionSnapshot

    base = {
        "start": [2, 2],
        "goal": [8, 8],
        "roverId": "lpr_1",
        "weights": dict(_WEIGHTS),
        "focusedCell": None,
        "currentPlan": None,
    }
    base.update(overrides)
    return AiMissionSnapshot.model_validate(base)


def _registry(**overrides) -> ToolRegistry:
    return ToolRegistry(
        grids=_make_grids(),
        snapshot=_snapshot(**overrides),
        budget=ToolBudget(),
    )


# ── the registry exposes exactly two tools ───────────────────────────────────

def test_only_the_two_approved_tools_are_callable():
    assert set(_registry().tool_names()) == {"inspect_cell", "compare_mission_profiles"}


def test_tool_specifications_match_the_registry():
    names = {spec["name"] for spec in tool_specifications()}
    assert names == {"inspect_cell", "compare_mission_profiles"}


@pytest.mark.parametrize(
    "forbidden",
    [
        "plan",
        "plan_route",
        "replan",
        "load_dem",
        "load_preprocessed",
        "pose",
        "score_path",
        "plan_4d",
        "illumination_series",
        "http_get",
        "shell",
        "read_file",
    ],
)
def test_a_forbidden_tool_name_is_refused_not_executed(forbidden):
    registry = _registry()
    with pytest.raises(AiToolError) as excinfo:
        registry.call(forbidden, {})
    assert excinfo.value.code == "UNKNOWN_TOOL"


def test_route_planning_is_not_reachable_under_any_registered_name():
    # The absence of a plan tool is the mechanism, so assert on the registry
    # itself rather than on one spelling of the name.
    for name in _registry().tool_names():
        assert "plan" not in name or name == "compare_mission_profiles"


# ── budget is enforced server-side ───────────────────────────────────────────

def test_one_comparison_per_question_is_the_hard_ceiling():
    budget = ToolBudget()
    budget.spend_compare()
    with pytest.raises(AiToolError) as excinfo:
        budget.spend_compare()
    assert excinfo.value.code == "BUDGET_EXCEEDED"


def test_the_compare_ceiling_is_one():
    assert MAX_COMPARE_CALLS == 1


def test_safe_reads_are_capped():
    budget = ToolBudget()
    for _ in range(MAX_READ_CALLS):
        budget.spend_read()
    with pytest.raises(AiToolError) as excinfo:
        budget.spend_read()
    assert excinfo.value.code == "BUDGET_EXCEEDED"


def test_the_read_ceiling_is_twenty():
    assert MAX_READ_CALLS == 20


def test_budget_reports_what_was_spent():
    budget = ToolBudget()
    budget.spend_read()
    budget.spend_read()
    budget.spend_compare()
    assert budget.read_calls == 2
    assert budget.compare_calls == 1


def test_a_second_compare_is_refused_through_the_registry_too():
    registry = _registry()
    registry.call("compare_mission_profiles", {})
    with pytest.raises(AiToolError) as excinfo:
        registry.call("compare_mission_profiles", {})
    assert excinfo.value.code == "BUDGET_EXCEEDED"


# ── inspect_cell ─────────────────────────────────────────────────────────────

def test_inspect_cell_returns_safe_telemetry_for_a_valid_cell():
    result = _registry().call("inspect_cell", {"row": 5, "col": 5})
    assert result["row"] == 5
    assert result["altitude"]["unit"] == "m"
    assert result["thermal"]["unit"] == "degC"


def test_inspect_cell_preserves_layer_validity_and_derives_provenance():
    result = _registry().call("inspect_cell", {"row": 5, "col": 5})
    assert result["layer_validity"]["slope"] == "DERIVED"
    assert result["provenance"]["rawValidity"] == "DERIVED"
    assert result["provenance"]["displayPedigree"] == "model"


def test_inspect_cell_includes_the_decomposition_when_weights_agree():
    result = _registry().call("inspect_cell", {"row": 5, "col": 5})
    assert "cost_breakdown" in result
    assert result["limitations"] == []


def test_inspect_cell_withholds_the_decomposition_under_custom_plan_weights():
    registry = _registry(weights=dict(_WEIGHTS, w_energy=0.45))
    result = registry.call("inspect_cell", {"row": 5, "col": 5})
    assert "cost_breakdown" not in result
    assert result["limitations"][0]["code"] == "CELL_COST_BREAKDOWN_WEIGHT_MISMATCH"


@pytest.mark.parametrize("row,col", [(-1, 5), (5, -1), (20, 5), (5, 20), (999, 999)])
def test_inspect_cell_refuses_a_cell_outside_the_loaded_grid(row, col):
    with pytest.raises(AiToolError) as excinfo:
        _registry().call("inspect_cell", {"row": row, "col": col})
    assert excinfo.value.code == "INVALID_ARGUMENT"


@pytest.mark.parametrize("bad", ["five", None, 2.5, float("nan"), [1]])
def test_inspect_cell_refuses_a_non_integer_index(bad):
    with pytest.raises(AiToolError) as excinfo:
        _registry().call("inspect_cell", {"row": bad, "col": 5})
    assert excinfo.value.code == "INVALID_ARGUMENT"


def test_inspect_cell_spends_read_budget():
    registry = _registry()
    registry.call("inspect_cell", {"row": 5, "col": 5})
    assert registry.budget.read_calls == 1


# ── compare_mission_profiles ─────────────────────────────────────────────────

def test_compare_takes_its_endpoints_from_the_snapshot_not_the_model():
    # The model cannot move the route behind the user's back: coordinates in
    # the arguments are ignored entirely.
    registry = _registry()
    result = registry.call(
        "compare_mission_profiles", {"start": [0, 0], "goal": [19, 19]}
    )
    assert result["start"] == [2, 2]
    assert result["goal"] == [8, 8]


def test_compare_returns_every_mission_profile():
    result = _registry().call("compare_mission_profiles", {})
    ids = {profile["profile_id"] for profile in result["profiles"]}
    assert ids == {"balanced", "energy_saver", "fast_recon", "shadow_traverse"}


def test_compare_reports_real_energy_from_the_simulation():
    result = _registry().call("compare_mission_profiles", {})
    energy = result["profiles"][0]["simulation_summary"]["total_energy_consumed_wh"]
    assert isinstance(energy, float)
    assert energy > 0.0


def test_compare_evidence_carries_no_stale_recommendation():
    import json

    blob = json.dumps(_registry().call("compare_mission_profiles", {}), default=str)
    assert "recommendation" not in blob
    assert "not tracked in fast mode" not in blob


def test_compare_evidence_carries_no_route_geometry():
    import json

    blob = json.dumps(_registry().call("compare_mission_profiles", {}), default=str)
    assert "path_pixels" not in blob


def test_compare_evidence_carries_no_forbidden_metrics():
    import json

    blob = json.dumps(_registry().call("compare_mission_profiles", {}), default=str)
    assert "total_energy_wh" not in blob
    assert "total_shadow_hours" not in blob
    assert "total_shadow_exposure" not in blob
    assert "computation_time_ms" not in blob


def test_compare_preserves_constraint_check():
    result = _registry().call("compare_mission_profiles", {})
    assert "max_energy_wh" in result["profiles"][0]["constraint_check"]


def test_compare_publishes_each_profile_weight_set():
    result = _registry().call("compare_mission_profiles", {})
    weights = result["profiles"][0]["weights"]
    assert set(weights) == {"w_slope", "w_energy", "w_shadow", "w_thermal"}


def test_compare_refuses_when_the_user_has_not_chosen_a_route():
    registry = _registry(start=None, goal=None)
    with pytest.raises(AiToolError) as excinfo:
        registry.call("compare_mission_profiles", {})
    assert excinfo.value.code == "MISSION_INCOMPLETE"


def test_compare_leaves_the_grid_store_untouched():
    grids = _make_grids()
    registry = ToolRegistry(grids=grids, snapshot=_snapshot(), budget=ToolBudget())
    before = grids["metadata"]["cost_weights"].copy()
    registry.call("compare_mission_profiles", {})
    assert grids["metadata"]["cost_weights"] == before
    assert grids["traversable"].all()
