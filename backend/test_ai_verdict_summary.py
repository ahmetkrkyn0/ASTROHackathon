"""The mission report's verdict, once it reaches the assistant.

`test_report_verdict` proves the decision matches the report screen. This file
proves the decision survives the AI pipeline: that the reasons pass K5, that
the numbers they cite are registered rather than invented, that no explanation
level can drop a blocking finding, and that a blocked draft still tells the
operator the disposition.

Its own fixture, deliberately. `test_ai_summary_hardening.PLAN` is the shape a
verified summary is pinned against and adding the verdict's inputs to it would
change what that file's ordering assertion sees. A NO-GO plan is a different
fixture, and it belongs with the tests that need one.
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))

os.environ["LUNAPATH_SKIP_STARTUP"] = "YES"

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.ai_analysis import (
    DIMENSIONLESS,
    AnalysisEnvelope,
    Provenance,
    _PLAN_COUNTS,
    _SUMMARY_SECTIONS,
    plan_registry,
    verdict_registry,
    verdict_warnings,
)
from app.ai_chat import _build_envelope, _evidence_for, _verbalizer_input
from app.ai_contract import AiMissionSnapshot
from app.ai_grounding import (
    _COUNTED_NOUNS,
    deterministic_fallback,
    diagnostic,
    validate_draft,
    whitelist_tokens,
)
from app.ai_prompt import VERBALIZER_PROMPT
from app.ai_provider import ProviderReply, StubProvider
from app.ai_tools import AnalysisProvider, ToolBudget
from app.cost_engine import COST_MODEL_ID
from app.main import app
from app.report import decide_verdict_from_snapshot, reason, reason_codes, verdict_sentence

client = TestClient(app, raise_server_exceptions=True)

SHAPE = (20, 20)

_WEIGHTS = {
    "w_slope": 0.409,
    "w_energy": 0.259,
    "w_shadow": 0.142,
    "w_thermal": 0.190,
}

PROV = Provenance(source="DERIVED", layer="thermal")

# A plan that fires every blocking condition and every warning, in the flat
# shape sanitizePlanForAi puts on the wire.
PLAN_NOGO = {
    "distance": {"value": 3.0996, "unit": "km"},
    "elapsed": {"value": 2.4512, "unit": "h"},
    "energy": {"value": 1490.23, "unit": "Wh"},
    "min_battery": {"value": 8.4, "unit": "%"},
    "final_battery": {"value": 0.0, "unit": "%"},
    "max_slope": {"value": 12.336, "unit": "deg"},
    "max_continuous_shadow": {"value": 61.5, "unit": "h"},
    "shadow_limit": {"value": 6.0, "unit": "h"},
    "shadow_limit_exceeded": True,
    "waypoint_count": 495,
    "total_recharges": 2,
    "critical_steps_count": 2,
    "high_or_above_steps_count": 5,
    "peak_power_exceeded_steps": 3,
    "stranded": True,
    "stranded_at_step": 12,
    "execution": {
        "stranded": True,
        "truncated": True,
        "reason": "battery",
        "planned_nodes": 90,
        "executable_nodes": 40,
    },
}

# The same route with nothing wrong: every count zero, no execution block.
PLAN_GO = {
    "distance": {"value": 3.0996, "unit": "km"},
    "elapsed": {"value": 2.4512, "unit": "h"},
    "energy": {"value": 1490.23, "unit": "Wh"},
    "min_battery": {"value": 64.2, "unit": "%"},
    "final_battery": {"value": 71.8, "unit": "%"},
    "max_slope": {"value": 12.336, "unit": "deg"},
    "max_continuous_shadow": {"value": 3.4147, "unit": "h"},
    "shadow_limit": {"value": 6.0, "unit": "h"},
    "shadow_limit_exceeded": False,
    "waypoint_count": 495,
    "total_recharges": 0,
    "critical_steps_count": 0,
    "high_or_above_steps_count": 0,
    "peak_power_exceeded_steps": 0,
    "stranded": False,
}

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "frontend", "src"))


def _read(*parts: str) -> str:
    with open(os.path.join(*parts), encoding="utf-8") as handle:
        return handle.read()


AI_CONTEXT = _read(_SRC, "features", "assistant", "aiContext.ts")
CHAT_PANEL = _read(_SRC, "features", "assistant", "ChatPanel.tsx")


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


def _snapshot(plan: dict) -> AiMissionSnapshot:
    return AiMissionSnapshot.model_validate(
        {
            "start": [2, 2],
            "goal": [8, 8],
            "roverId": "lpr_1",
            "weights": dict(_WEIGHTS),
            "focusedCell": None,
            "currentPlan": dict(plan),
        }
    )


def _envelope(plan: dict = PLAN_NOGO) -> AnalysisEnvelope:
    provider = AnalysisProvider(
        grids=_make_grids(), snapshot=_snapshot(plan), budget=ToolBudget()
    )
    return _build_envelope("C-SUMMARY", {}, provider, provider.grids)


def _tokens(envelope: AnalysisEnvelope) -> frozenset[str]:
    return whitelist_tokens(envelope, rover_names=[], profile_names=[])


def _check(draft: str, envelope: AnalysisEnvelope):
    return validate_draft(draft, envelope, _tokens(envelope))


def _briefing(envelope: AnalysisEnvelope, level: str = "L2") -> dict:
    content = _verbalizer_input(envelope, "Bu rotayı özetle.", level)[0]["content"]
    return json.loads(content[content.index("{") :])


def _display(envelope: AnalysisEnvelope, key: str) -> str:
    return next(
        metric.display for metric in envelope.numeric_registry if metric.key == key
    )


def _install(provider) -> None:
    app.state.grids = _make_grids()
    app.state.ai_provider = provider


def _teardown() -> None:
    app.state.ai_provider = None


def _payload(plan: dict = PLAN_NOGO, question: str = "Bu rota sürülebilir mi?") -> dict:
    return {
        "messages": [{"role": "user", "content": question}],
        "mission": {
            "start": [2, 2],
            "goal": [8, 8],
            "roverId": "lpr_1",
            "weights": dict(_WEIGHTS),
            "focusedCell": None,
            "currentPlan": dict(plan),
        },
        "explanationLevel": "L2",
    }


# ── the verdict reaches the briefing ─────────────────────────────────────────


def test_a_summary_briefing_carries_the_verdict():
    briefing = _briefing(_envelope())
    assert briefing["verdict"]["code"] == "NO-GO"
    assert briefing["verdict"]["sentence"] == verdict_sentence("NO-GO")


def test_a_clean_route_reports_GO_rather_than_omitting_the_verdict():
    briefing = _briefing(_envelope(PLAN_GO))
    assert briefing["verdict"]["code"] == "GO"


def test_the_verdict_stays_out_of_every_other_briefing():
    """The field is additive: a cell briefing is what it was."""
    provider = AnalysisProvider(
        grids=_make_grids(), snapshot=_snapshot(PLAN_NOGO), budget=ToolBudget()
    )
    envelope = _build_envelope("C-POINT", {"row": 4, "col": 4}, provider, provider.grids)
    assert envelope.verdict is None
    assert "verdict" not in _briefing(envelope)


def test_an_analysis_briefing_still_carries_no_facts_key():
    """The verdict travels as its own field, not by reopening the facts channel
    -- which test_ai_guide pins shut for analysis capabilities."""
    envelope = _envelope()
    assert envelope.facts == []
    assert envelope.lexicon == []
    assert "facts" not in _briefing(envelope)


def test_every_reason_arrives_as_a_mandatory_warning():
    briefing = _briefing(_envelope())
    codes = [w["code"] for w in briefing["warnings"]]
    assert codes[:8] == [
        "VERDICT_STRANDED",
        "VERDICT_EXECUTION_TRUNCATED",
        "VERDICT_SHADOW_LIMIT_EXCEEDED",
        "VERDICT_CRITICAL_STEPS",
        "VERDICT_HIGH_RISK_STEPS",
        "VERDICT_BATTERY_WATCH",
        "VERDICT_PEAK_POWER_EXCEEDED",
        "VERDICT_RECHARGES_REQUIRED",
    ]


def test_a_GO_emits_no_warning_at_all():
    """An all-clear is not a mandatory warning; emitting one would make the
    channel mean 'here is a note' instead of 'you must state this'."""
    assert verdict_warnings(decide_verdict_from_snapshot(PLAN_GO)) == []


def test_blocking_reasons_are_critical_and_soft_ones_are_cautions():
    warnings = verdict_warnings(decide_verdict_from_snapshot(PLAN_NOGO))
    severities = {w.code: w.severity for w in warnings}
    assert severities["VERDICT_STRANDED"] == "critical"
    assert severities["VERDICT_RECHARGES_REQUIRED"] == "caution"


@pytest.mark.parametrize("level", ["L1", "L2", "L3"])
def test_every_level_receives_the_same_verdict_and_the_same_warnings(level):
    """N-13 and N-14: the level changes narration, never the record, and no
    level may drop a critical finding."""
    envelope = _envelope()
    briefing = _briefing(envelope, level)
    assert briefing["verdict"] == _briefing(envelope, "L2")["verdict"]
    assert briefing["warnings"] == _briefing(envelope, "L2")["warnings"]
    assert any(w["severity"] == "critical" for w in briefing["warnings"])


# ── the numbers a reason cites are registered ────────────────────────────────


def test_the_verdict_registers_the_stranded_step():
    envelope = _envelope()
    assert _display(envelope, "stranded_at_step") == "12"


def test_the_verdict_registers_both_node_counts():
    envelope = _envelope()
    assert _display(envelope, "execution_planned_nodes") == "90"
    assert _display(envelope, "execution_executable_nodes") == "40"


def test_the_battery_threshold_is_registered_as_a_report_policy_number():
    envelope = _envelope()
    metric = next(
        one for one in envelope.numeric_registry if one.key == "battery_watch_threshold"
    )
    assert metric.display == "30 %"
    # Turkish writes the percent first; the alias is what lets the natural
    # phrasing survive the mask.
    assert "%30" in metric.display_alt
    # MODEL, not MEASURED: the report chose this line, no instrument did.
    assert metric.provenance.source == "MODEL"


def test_a_clean_route_registers_none_of_the_verdict_extras():
    """Registering the stranded step for a route that finished would hand K4 a
    number with no sentence to put it in."""
    keys = {metric.key for metric in verdict_registry(
        PLAN_GO, decide_verdict_from_snapshot(PLAN_GO), PROV
    )}
    assert keys == set()


def test_a_stranded_route_with_no_step_recorded_registers_no_step():
    plan = dict(PLAN_GO)
    plan["stranded"] = True
    plan["stranded_at_step"] = None
    keys = {metric.key for metric in verdict_registry(
        plan, decide_verdict_from_snapshot(plan), PROV
    )}
    assert "stranded_at_step" not in keys


def test_the_shadow_limit_is_registered_so_both_sides_can_be_stated():
    envelope = _envelope()
    assert _display(envelope, "max_continuous_shadow") == "61,50 h"
    assert _display(envelope, "shadow_limit") == "6,00 h"


def test_the_peak_power_count_is_registered():
    assert _display(_envelope(), "peak_power_exceeded_steps") == "3"


# ── K5 lets the sanctioned wording through ───────────────────────────────────


@pytest.mark.parametrize("code", reason_codes())
def test_every_reason_text_passes_the_grounding_check(code):
    envelope = _envelope()
    verdict = _check(reason(code).text, envelope)
    assert verdict.ok, diagnostic(verdict)


@pytest.mark.parametrize("verdict_code", ["GO", "GO-WITH-RISK", "NO-GO"])
def test_every_verdict_sentence_passes_the_grounding_check(verdict_code):
    envelope = _envelope()
    verdict = _check(verdict_sentence(verdict_code), envelope)
    assert verdict.ok, diagnostic(verdict)


def test_a_faithful_verdict_answer_is_verified_rather_than_blocked():
    envelope = _envelope()
    draft = (
        f"{verdict_sentence('NO-GO')} "
        f"Rover {_display(envelope, 'stranded_at_step')}. adımda enerjisiz kaldı. "
        f"Planlanan {_display(envelope, 'execution_planned_nodes')} düğümün "
        f"{_display(envelope, 'execution_executable_nodes')} tanesi sürülebilir. "
        f"Kesintisiz gölge {_display(envelope, 'max_continuous_shadow')}, "
        f"rover limiti {_display(envelope, 'shadow_limit')}."
    )
    verdict = _check(draft, envelope)
    assert verdict.ok, diagnostic(verdict)


def test_the_fallback_leads_with_the_verdict_and_still_passes_the_check():
    envelope = _envelope()
    answer = deterministic_fallback(envelope)
    assert answer.splitlines()[0] == verdict_sentence("NO-GO")
    for code in (
        "STRANDED",
        "EXECUTION_TRUNCATED",
        "SHADOW_LIMIT_EXCEEDED",
        "CRITICAL_STEPS",
    ):
        assert reason(code).text in answer
    verdict = _check(answer, envelope)
    assert verdict.ok, diagnostic(verdict)


def test_a_spelled_out_step_index_is_blocked():
    """Why the verbalizer prompt has to name step indices explicitly: without
    that instruction a model writes "on ikinci adımda" and loses the answer."""
    envelope = _envelope()
    verdict = _check("Rover on ikinci adımda enerjisiz kaldı.", envelope)
    assert not verdict.ok
    assert {"code": "UNREGISTERED_NUMBER_WORD"} in diagnostic(verdict)


def test_a_safety_claim_is_blocked_even_next_to_a_real_verdict():
    envelope = _envelope()
    verdict = _check(
        f"{verdict_sentence('GO')} Bu rota güvenlidir ve risksizdir.", envelope
    )
    assert not verdict.ok
    assert {"code": "FORBIDDEN_CLAIM", "rule": "N-8"} in diagnostic(verdict)


# ── end to end, through the endpoint ─────────────────────────────────────────


def test_the_endpoint_states_the_verdict_on_a_verified_answer():
    envelope = _envelope()
    draft = (
        f"{verdict_sentence('NO-GO')} "
        f"Rover {_display(envelope, 'stranded_at_step')}. adımda enerjisiz kaldı."
    )
    _install(
        StubProvider(
            script=[ProviderReply(text=draft, tool_calls=[])],
            structured_script=[json.dumps({"action": "answer_from_context"})],
        )
    )
    try:
        body = client.post("/api/ai/chat", json=_payload()).json()
        assert body["groundingStatus"] == "verified"
        assert body["errorCode"] is None
        assert "NO-GO" in body["answer"]
        codes = [w["code"] for w in body["warnings"]]
        assert "VERDICT_STRANDED" in codes
    finally:
        _teardown()


def test_a_blocked_answer_still_tells_the_operator_the_verdict():
    _install(
        StubProvider(
            script=[
                ProviderReply(text="Bu rota güvenlidir ve risksizdir.", tool_calls=[])
            ],
            structured_script=[json.dumps({"action": "answer_from_context"})],
        )
    )
    try:
        body = client.post("/api/ai/chat", json=_payload()).json()
        assert body["errorCode"] == "E-GROUNDING"
        assert body["groundingStatus"] == "blocked"
        # The disposition is exactly what the operator must not lose here.
        assert "NO-GO" in body["answer"]
    finally:
        _teardown()


def test_the_verdict_limitation_says_it_is_not_a_safety_certificate():
    _install(
        StubProvider(
            script=[ProviderReply(text=verdict_sentence("NO-GO"), tool_calls=[])],
            structured_script=[json.dumps({"action": "answer_from_context"})],
        )
    )
    try:
        body = client.post("/api/ai/chat", json=_payload()).json()
        codes = [item["code"] for item in body["limitations"]]
        assert "VERDICT_IS_A_CONSTRAINT_CHECK" in codes
    finally:
        _teardown()


# ── the places two files must agree ──────────────────────────────────────────


def test_every_field_the_snapshot_adapter_reads_reaches_the_wire():
    """A verdict input missing from sanitizePlanForAi degrades the decision to
    GO without saying so, which is the worst possible failure here."""
    for field in (
        "stranded",
        "stranded_at_step",
        "shadow_limit",
        "shadow_limit_exceeded",
        "critical_steps_count",
        "high_or_above_steps_count",
        "min_battery",
        "peak_power_exceeded_steps",
        "total_recharges",
        "planned_nodes",
        "executable_nodes",
    ):
        assert field in AI_CONTEXT, field


def test_every_registered_count_has_a_noun_the_scan_knows():
    """ai_grounding's own rule: adding a count metric and adding its noun is
    one change. A count with no noun lets a spelled-out numeral through."""
    nouns = {
        "waypoint_count": "waypoint",
        "total_recharges": "şarj",
        "critical_steps_count": "adım",
        "high_or_above_steps_count": "adım",
        "peak_power_exceeded_steps": "adım",
    }
    for field, _label in _PLAN_COUNTS:
        assert nouns[field] in _COUNTED_NOUNS, field
    assert "düğüm" in _COUNTED_NOUNS


def test_the_verbalizer_prompt_names_every_section_the_registry_uses():
    for section in set(_SUMMARY_SECTIONS.values()):
        assert f"`{section}`" in VERBALIZER_PROMPT, section


def test_the_verbalizer_prompt_forbids_upgrading_the_verdict():
    for phrase in ("GO-WITH-RISK", "NO-GO", "yumuşatmazsın"):
        assert phrase in VERBALIZER_PROMPT


def test_the_summary_evidence_source_is_the_one_the_panel_labels():
    """A new source for the verdict would break the panel's label lookup
    silently, so C-SUMMARY keeps the source it had."""
    envelope = _envelope()
    source = _evidence_for(envelope)[0].source
    assert source == "current-plan"
    assert re.search(rf"'{re.escape(source)}':", CHAT_PANEL)


def test_a_verdict_metric_carries_the_verdict_section():
    briefing = _briefing(_envelope())
    sections = {item["key"]: item.get("section") for item in briefing["metrics"]}
    assert sections["stranded_at_step"] == "verdict"
    assert sections["battery_watch_threshold"] == "verdict"
    assert sections["shadow_limit"] == "terrain"
    assert sections["peak_power_exceeded_steps"] == "energy"


def test_the_plan_registry_still_leads_with_distance():
    """Adding two fields to the tables must not move what a summary opens on."""
    assert plan_registry(PLAN_NOGO, PROV)[0].key == "distance"


def test_a_dimensionless_verdict_metric_is_registered_without_a_unit():
    envelope = _envelope()
    metric = next(
        one for one in envelope.numeric_registry if one.key == "stranded_at_step"
    )
    assert metric.quantity.unit == DIMENSIONLESS
