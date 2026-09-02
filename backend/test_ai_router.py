"""K2 routing and K3 gating -- semantic outcomes, no network.

K2 turns free text into a structured decision and nothing else: it may not
write prose, may not emit numbers, and may not see a backend endpoint name.
K3 is the deterministic gate in front of every invocation.

The router is exercised through the stub provider, which returns scripted
JSON strings. That proves the contract and the retry path; it does not prove
real-model classification accuracy, which needs a key (AI-02 A-6).

Contract: docs/ai/LunaPath_AI_Chatbot_Scope_v0.3.md sections 12 and 15.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

os.environ["LUNAPATH_SKIP_STARTUP"] = "YES"

import numpy as np
import pytest

from app.ai_contract import AiMissionSnapshot, RouterFailure, parse_router_output
from app.ai_provider import StubProvider
from app.ai_router import gate, route
from app.ai_tools import AnalysisProvider, ToolBudget
from app.cost_engine import COST_MODEL_ID

SHAPE = (20, 20)
_WEIGHTS = {"w_slope": 0.409, "w_energy": 0.259, "w_shadow": 0.142, "w_thermal": 0.190}


def _make_grids() -> dict:
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
            "layer_validity": {"elevation": "MEASURED", "slope": "DERIVED"},
        },
    }


def _snapshot(**overrides) -> AiMissionSnapshot:
    base = {
        "start": [2, 2],
        "goal": [8, 8],
        "roverId": "lpr_1",
        "weights": dict(_WEIGHTS),
        "focusedCell": None,
        "currentPlan": {"energy": {"value": 1490.23, "unit": "Wh"}},
    }
    base.update(overrides)
    return AiMissionSnapshot.model_validate(base)


def _provider(**overrides) -> AnalysisProvider:
    return AnalysisProvider(
        grids=_make_grids(), snapshot=_snapshot(**overrides), budget=ToolBudget()
    )


def _stub(*payloads) -> StubProvider:
    return StubProvider(structured_script=[json.dumps(p) for p in payloads])


# ── RouterOutput parsing ─────────────────────────────────────────────────────

def test_an_invoke_decision_parses():
    decision = parse_router_output(
        {"action": "invoke", "capability": "C-POINT",
         "params": {"row": 5, "col": 5}, "rationale_key": "cell_question"}
    )
    assert decision.action == "invoke"
    assert decision.capability == "C-POINT"


def test_answer_from_context_parses():
    assert parse_router_output({"action": "answer_from_context"}).action == "answer_from_context"


def test_clarify_carries_what_is_missing():
    decision = parse_router_output({"action": "clarify", "missing": ["cell"]})
    assert decision.missing == ["cell"]


def test_refuse_carries_a_code():
    decision = parse_router_output({"action": "refuse", "code": "OUT_OF_SCOPE"})
    assert decision.code == "OUT_OF_SCOPE"


def test_the_router_cannot_smuggle_prose_through_an_extra_field():
    # extra="forbid": an `answer` key is how a router quietly becomes a
    # verbalizer, which would bypass K5 entirely.
    with pytest.raises(Exception):
        parse_router_output(
            {"action": "answer_from_context", "answer": "Rota 12 km."}
        )


def test_the_rationale_key_is_a_closed_vocabulary():
    # A free-text rationale is a place numbers could hide.
    with pytest.raises(Exception):
        parse_router_output(
            {"action": "invoke", "capability": "C-POINT", "params": {},
             "rationale_key": "the route is 12 km long"}
        )


def test_an_unavailable_capability_cannot_be_named():
    with pytest.raises(Exception):
        parse_router_output(
            {"action": "invoke", "capability": "C-CONTRAST", "params": {},
             "rationale_key": "cell_question"}
        )


# ── route() ──────────────────────────────────────────────────────────────────

def test_route_returns_the_scripted_decision():
    provider = _provider()
    decision = route(
        _stub({"action": "answer_from_context"}),
        question="Bu rotayı özetle.",
        history=[],
        capabilities=provider.get_capabilities(),
        context=provider.get_context(),
    )
    assert decision.action == "answer_from_context"


def test_route_retries_once_after_malformed_json():
    provider = _provider()
    stub = StubProvider(structured_script=["not json at all",
                                           json.dumps({"action": "answer_from_context"})])
    decision = route(stub, question="q", history=[],
                     capabilities=provider.get_capabilities(),
                     context=provider.get_context())
    assert decision.action == "answer_from_context"
    assert len(stub.structured_calls) == 2


def test_route_gives_up_with_e_schema_after_two_attempts():
    provider = _provider()
    stub = StubProvider(structured_script=["nope", "still nope"])
    decision = route(stub, question="q", history=[],
                     capabilities=provider.get_capabilities(),
                     context=provider.get_context())
    assert isinstance(decision, RouterFailure)
    assert decision.code == "E-SCHEMA"


def test_the_router_never_sees_a_backend_endpoint_name():
    provider = _provider()
    stub = _stub({"action": "answer_from_context"})
    route(stub, question="q", history=[],
          capabilities=provider.get_capabilities(),
          context=provider.get_context())
    blob = json.dumps(stub.structured_calls[0], default=str)
    for leak in ("/api/", "inspect_cell", "compare_mission_profiles",
                 "cell-telemetry", "total_energy_consumed_wh"):
        assert leak not in blob, leak


def test_the_router_never_sees_a_metric_value():
    # K2 must not be handed a number it could echo into its rationale.
    provider = _provider()
    stub = _stub({"action": "answer_from_context"})
    route(stub, question="q", history=[],
          capabilities=provider.get_capabilities(),
          context=provider.get_context())
    assert "1490.23" not in json.dumps(stub.structured_calls[0], default=str)


# ── capability descriptors ───────────────────────────────────────────────────

def test_capabilities_report_the_audited_availability():
    available = {c["code"]: c["available"] for c in _provider().get_capabilities()}
    assert available["C-SUMMARY"] is True
    assert available["C-POINT"] is True
    assert available["C-COMPARE"] is True
    assert available["C-CONTRAST"] is False
    assert available["C-RECOURSE"] is False


def test_capability_descriptors_carry_no_endpoint_names():
    blob = json.dumps(_provider().get_capabilities(), default=str)
    assert "/api/" not in blob
    assert "inspect_cell" not in blob


def test_context_reports_grid_facts_from_runtime_not_from_a_document():
    context = _provider().get_context()
    assert context["grid"]["rows"] == 20
    assert context["grid"]["resolution_m"] == 80.0


# ── K3 gate ──────────────────────────────────────────────────────────────────

def _invoke(capability, params=None, key="cell_question"):
    return parse_router_output(
        {"action": "invoke", "capability": capability,
         "params": params or {}, "rationale_key": key}
    )


def test_gate_admits_a_well_formed_point_request():
    provider = _provider()
    result = gate(_invoke("C-POINT", {"row": 5, "col": 5}), provider=provider,
                  budget=provider.budget)
    assert result.ok


def test_gate_rejects_a_malformed_point_request_with_e_schema():
    provider = _provider()
    result = gate(_invoke("C-POINT", {"row": "five"}), provider=provider,
                  budget=provider.budget)
    assert not result.ok
    assert result.code == "E-SCHEMA"


def test_gate_rejects_an_unavailable_capability_with_e_unsupported():
    provider = _provider()
    # Bypass the parser to simulate a router that named an absent capability.
    from app.ai_contract import RouterInvoke

    decision = RouterInvoke.model_construct(
        action="invoke", capability="C-CONTRAST", params={},
        rationale_key="cell_question",
    )
    result = gate(decision, provider=provider, budget=provider.budget)
    assert not result.ok
    assert result.code == "E-UNSUPPORTED"


def test_gate_refuses_a_second_comparison_with_e_budget():
    provider = _provider()
    provider.budget.spend_compare()
    result = gate(_invoke("C-COMPARE", key="profile_tradeoff"), provider=provider,
                  budget=provider.budget)
    assert not result.ok
    assert result.code == "E-BUDGET"


def test_gate_refuses_a_comparison_without_endpoints_with_e_context():
    provider = _provider(start=None, goal=None)
    result = gate(_invoke("C-COMPARE", key="profile_tradeoff"), provider=provider,
                  budget=provider.budget)
    assert not result.ok
    assert result.code == "E-CONTEXT"


def test_gate_refuses_a_summary_without_a_plan_with_e_context():
    provider = _provider(currentPlan=None)
    decision = parse_router_output({"action": "answer_from_context"})
    result = gate(decision, provider=provider, budget=provider.budget)
    assert not result.ok
    assert result.code == "E-CONTEXT"


def test_every_gate_refusal_carries_a_turkish_reason():
    provider = _provider()
    result = gate(_invoke("C-POINT", {"row": 999, "col": 999}), provider=provider,
                  budget=provider.budget)
    assert not result.ok
    assert result.message_tr
    assert len(result.message_tr) > 20


# ── AnalysisProvider dispatch ────────────────────────────────────────────────

def test_invoke_reaches_the_existing_cell_implementation():
    payload = _provider().invoke("C-POINT", {"row": 5, "col": 5})
    assert payload["row"] == 5
    assert payload["thermal"]["unit"] == "degC"


def test_invoke_reaches_the_existing_comparison_implementation():
    payload = _provider().invoke("C-COMPARE", {})
    assert len(payload["profiles"]) == 4


def test_invoke_of_an_unknown_capability_raises():
    from app.ai_tools import AiToolError

    with pytest.raises(AiToolError):
        _provider().invoke("C-CONTRAST", {})


def test_there_is_no_capability_that_writes():
    assert all(c["writes"] is False for c in _provider().get_capabilities())


# ── partial capability status and scope ──────────────────────────────────────

def _spec(code: str) -> dict:
    return {c["code"]: c for c in _provider().get_capabilities()}[code]


def test_full_capabilities_report_status_full():
    for code in ("C-SUMMARY", "C-POINT", "C-COMPARE"):
        assert _spec(code)["status"] == "full", code


def test_partial_capabilities_are_partial_not_unavailable():
    # They were previously collapsed into the same bucket as the two genuinely
    # absent ones, which lost the semantic intent entirely.
    for code in ("C-DECOMPOSE", "C-BINDING", "C-INFEASIBLE", "C-SENSITIVITY"):
        spec = _spec(code)
        assert spec["status"] == "partial", code
        assert spec["available"] is True, code


def test_each_partial_capability_declares_its_scope():
    assert _spec("C-BINDING")["scope"] == "compare_profile_constraints"
    assert _spec("C-INFEASIBLE")["scope"] == "compare_profile_failures_only"
    assert _spec("C-SENSITIVITY")["scope"] == "discrete_predefined_profiles"
    assert _spec("C-DECOMPOSE")["scope"] == "cell_only"


def test_genuinely_absent_capabilities_stay_unavailable():
    for code in ("C-CONTRAST", "C-RECOURSE"):
        spec = _spec(code)
        assert spec["status"] == "unavailable", code
        assert spec["available"] is False, code


def test_the_router_can_name_every_partial_capability():
    for code in ("C-DECOMPOSE", "C-BINDING", "C-INFEASIBLE", "C-SENSITIVITY"):
        decision = parse_router_output(
            {"action": "invoke", "capability": code,
             "params": {"row": 5, "col": 5} if code == "C-DECOMPOSE" else {},
             "rationale_key": "constraint_margin"}
        )
        assert decision.capability == code


def test_the_router_still_cannot_name_an_absent_capability():
    for code in ("C-CONTRAST", "C-RECOURSE"):
        with pytest.raises(Exception):
            parse_router_output(
                {"action": "invoke", "capability": code, "params": {},
                 "rationale_key": "profile_tradeoff"}
            )


# ── one physical comparison, shared by every compare-backed alias ────────────

def test_compare_backed_aliases_share_one_budget():
    provider = _provider()
    first = gate(_invoke("C-BINDING", key="constraint_margin"),
                 provider=provider, budget=provider.budget)
    assert first.ok
    provider.invoke("C-BINDING", {})

    second = gate(_invoke("C-SENSITIVITY", key="profile_tradeoff"),
                  provider=provider, budget=provider.budget)
    assert not second.ok
    assert second.code == "E-BUDGET"


def test_every_compare_backed_alias_needs_endpoints():
    provider = _provider(start=None, goal=None)
    for code in ("C-COMPARE", "C-BINDING", "C-INFEASIBLE", "C-SENSITIVITY"):
        result = gate(_invoke(code, key="profile_tradeoff"),
                      provider=provider, budget=provider.budget)
        assert not result.ok, code
        assert result.code == "E-CONTEXT", code


def test_a_compare_backed_alias_reaches_the_existing_implementation():
    for code in ("C-BINDING", "C-INFEASIBLE", "C-SENSITIVITY"):
        payload = _provider().invoke(code, {})
        assert len(payload["profiles"]) == 4, code


def test_decompose_reaches_the_existing_cell_implementation():
    payload = _provider().invoke("C-DECOMPOSE", {"row": 5, "col": 5})
    assert payload["row"] == 5


def test_decompose_without_a_cell_is_refused_rather_than_answered():
    # Route-wide decomposition does not exist; answering anyway would be a
    # fabricated result.
    provider = _provider()
    result = gate(_invoke("C-DECOMPOSE", {}, key="cell_question"),
                  provider=provider, budget=provider.budget)
    assert not result.ok
    assert result.code == "E-SCHEMA"
