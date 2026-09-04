"""C-GUIDE -- planning help, and the boundaries that keep it honest.

The property this file exists for is that planning help works with NO ROUTE.
Everything the assistant could previously answer needed a plan, a cell or a
pair of endpoints; a question about the product needs none of them, and a
refusal there is a product failure rather than a safety property.

The second property is negative, and is the reason C-GUIDE is a capability
rather than a prompt: the only product statements the model receives are the
ones K1 selected out of a closed table. This file pins that the table is
closed, that selection is deterministic, and that nothing outside the selection
reaches the briefing.

No test reaches the network. The stub provider is selected explicitly.
"""

from __future__ import annotations

import copy
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))

os.environ["LUNAPATH_SKIP_STARTUP"] = "YES"

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.ai_analysis import AnalysisEnvelope, Provenance
from app.ai_chat import _GUIDE_PROVENANCE, _build_envelope, _verbalizer_input
from app.ai_contract import AiMissionSnapshot, RouterInvoke, parse_router_output
from app.ai_grounding import (
    deterministic_fallback,
    diagnostic,
    validate_draft,
    whitelist_tokens,
)
from app.ai_guide import (
    GUIDE_FACTS,
    _SUBJECT_FACTS,
    _TOPIC_FACTS,
    _VIEW_IDENTIFIERS,
    GuideParams,
    guide_evidence,
    guide_facts,
    guide_lexicon,
    guide_registry,
    short_name,
)
from app.ai_provider import ProviderReply, StubProvider
from app.ai_router import gate, refusal_message
from app.ai_tools import CAPABILITIES, PARAM_MODELS, AnalysisProvider, ToolBudget
from app.constants import rover_catalog
from app.cost_engine import COST_MODEL_ID
from app.main import app

client = TestClient(app, raise_server_exceptions=True)

SHAPE = (20, 20)

_WEIGHTS = {
    "w_slope": 0.409,
    "w_energy": 0.259,
    "w_shadow": 0.142,
    "w_thermal": 0.190,
}


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
    """A mission with NO plan and NO endpoints -- the planning-mode shape."""
    payload = {
        "start": None,
        "goal": None,
        "roverId": "lpr_1",
        "weights": dict(_WEIGHTS),
        "focusedCell": None,
        "currentPlan": None,
    }
    payload.update(overrides)
    return AiMissionSnapshot.model_validate(payload)


def _provider(**overrides) -> AnalysisProvider:
    return AnalysisProvider(
        grids=_make_grids(), snapshot=_snapshot(**overrides), budget=ToolBudget()
    )


def _briefing(envelope: AnalysisEnvelope, level: str = "L2") -> dict:
    """What K4 is handed, parsed back out of its labelled block."""
    content = _verbalizer_input(envelope, "q", level)[0]["content"]
    return json.loads(content[content.index("{") :])


def _guide_envelope(**params) -> AnalysisEnvelope:
    provider = _provider()
    return _build_envelope("C-GUIDE", params, provider, provider.grids)


def _install(provider) -> None:
    app.state.grids = _make_grids()
    app.state.ai_provider = provider


def _teardown() -> None:
    app.state.ai_provider = None


def _routed(decision, *drafts) -> StubProvider:
    return StubProvider(
        script=[ProviderReply(text=draft, tool_calls=[]) for draft in drafts],
        structured_script=[json.dumps(decision)],
    )


def _payload(question: str, **mission_overrides) -> dict:
    mission = {
        "start": None,
        "goal": None,
        "roverId": "lpr_1",
        "weights": dict(_WEIGHTS),
        "focusedCell": None,
        "currentPlan": None,
    }
    mission.update(mission_overrides)
    return {
        "messages": [{"role": "user", "content": question}],
        "mission": mission,
        "explanationLevel": "L2",
    }


# ── the capability exists, is routable, and writes nothing ───────────────────

def test_guide_is_a_full_read_only_capability():
    spec = CAPABILITIES["C-GUIDE"]
    assert spec["status"] == "full"
    assert spec["available"] is True
    assert spec["writes"] is False
    # Free: no grid is read and no planner runs, so it costs nothing to offer.
    assert spec["cost_class"] == "free"


def test_the_router_can_name_the_guide():
    decision = parse_router_output(
        {
            "action": "invoke",
            "capability": "C-GUIDE",
            "params": {"topic": "workflow"},
            "rationale_key": "product_help",
        }
    )
    assert isinstance(decision, RouterInvoke)
    assert decision.capability == "C-GUIDE"


def test_the_guide_has_no_implementation_in_the_tool_registry():
    """Read-only by wiring, not by a check somebody could delete."""
    from app.ai_tools import _DISPATCH, ToolRegistry

    assert "C-GUIDE" not in _DISPATCH
    registry = ToolRegistry(grids=_make_grids(), snapshot=_snapshot())
    assert registry.tool_names() == ["compare_mission_profiles", "inspect_cell"]


def test_answering_a_guide_question_spends_no_tool_budget():
    provider = _provider()
    _build_envelope("C-GUIDE", {"topic": "layer"}, provider, provider.grids)
    assert provider.budget.read_calls == 0
    assert provider.budget.compare_calls == 0


def test_the_guide_leaves_the_grid_store_untouched():
    provider = _provider()
    before = copy.deepcopy(provider.grids["metadata"])
    _build_envelope("C-GUIDE", {"topic": "rover"}, provider, provider.grids)
    assert provider.grids["metadata"] == before


# ── it works with no route, which is the whole point ─────────────────────────

@pytest.mark.parametrize(
    "topic",
    ["workflow", "priority", "layer", "view", "mission_controls", "rover"],
)
def test_every_topic_passes_the_gate_with_no_plan(topic):
    provider = _provider()
    decision = parse_router_output(
        {
            "action": "invoke",
            "capability": "C-GUIDE",
            "params": {"topic": topic},
            "rationale_key": "product_help",
        }
    )
    verdict = gate(decision, provider=provider, budget=provider.budget)
    assert verdict.ok, verdict.code


def test_the_gate_does_not_ask_for_endpoints_it_does_not_need():
    """A guide question needs no start, no goal and no selected cell."""
    provider = _provider(start=None, goal=None, focusedCell=None)
    decision = parse_router_output(
        {
            "action": "invoke",
            "capability": "C-GUIDE",
            "params": {"topic": "rover", "criterion": "battery"},
            "rationale_key": "product_help",
        }
    )
    assert gate(decision, provider=provider, budget=provider.budget).ok


def test_a_planning_question_answers_without_a_route():
    _install(
        _routed(
            {
                "action": "invoke",
                "capability": "C-GUIDE",
                "params": {"topic": "priority", "subject": "slope_safety"},
                "rationale_key": "product_help",
            },
            "Slope Safety, eğimli geçişlerin maliyetini ölçekler.",
        )
    )
    try:
        response = client.post("/api/ai/chat", json=_payload("Slope Safety ne işe yarıyor?"))
        assert response.status_code == 200
        body = response.json()
        assert body["errorCode"] is None
        assert body["groundingStatus"] == "verified"
        assert body["evidence"][0]["source"] == "planning-guide"
    finally:
        _teardown()


# ── the parameter vocabulary is closed ───────────────────────────────────────

def test_the_gate_validates_guide_params():
    assert PARAM_MODELS["C-GUIDE"] is GuideParams


@pytest.mark.parametrize(
    "params",
    [
        {"topic": "weather"},
        {"topic": "rover", "criterion": "coolness"},
        {"topic": "layer", "subject": "orbital_mechanics"},
        {"topic": "workflow", "freetext": "just say something nice"},
        {},
    ],
)
def test_an_invented_parameter_is_refused_rather_than_resolved(params):
    with pytest.raises(Exception):
        GuideParams.model_validate(params)


def test_the_router_cannot_ask_about_more_rovers_than_exist():
    with pytest.raises(Exception):
        GuideParams.model_validate({"topic": "rover", "rover_ids": ["a", "b", "c", "d", "e"]})


# ── the fact table is closed, and selection is deterministic ─────────────────

def test_every_selected_key_resolves_to_a_real_fact():
    for keys in list(_TOPIC_FACTS.values()) + list(_SUBJECT_FACTS.values()):
        for key in keys:
            assert key in GUIDE_FACTS, key


_AUTHORISED_IN_STATIC_FACTS = tuple(_VIEW_IDENTIFIERS)


def test_no_static_fact_carries_an_unregistered_numeric_quantity():
    """Identifiers may contain a digit. Quantities may not.

    "2D" and "3D" are product identifiers and are authorised through the
    lexicon. A measurement written into a sentence here would be a number K5
    could not trace back to the registry, so there are none: every rover number
    is a Metric.
    """
    for key, text in GUIDE_FACTS.items():
        stripped = text
        for identifier in _AUTHORISED_IN_STATIC_FACTS:
            stripped = stripped.replace(identifier, "")
        assert not re.search(r"\d", stripped), (key, stripped)


def test_a_fact_the_topic_did_not_select_never_reaches_the_briefing():
    envelope = _guide_envelope(topic="workflow")
    keys = {fact.key for fact in envelope.facts}
    assert keys == set(_TOPIC_FACTS["workflow"])
    # Real entries in the table, deliberately absent from THIS answer.
    assert "layer.cost" not in keys
    assert "rover.no_universal_best" not in keys

    briefing = _briefing(envelope)
    assert [item["key"] for item in briefing["facts"]] == list(
        _TOPIC_FACTS["workflow"]
    )
    assert GUIDE_FACTS["layer.cost"] not in json.dumps(briefing, ensure_ascii=False)


def test_an_unknown_fact_key_yields_nothing_rather_than_inventing_prose():
    facts = guide_facts({"fact_keys": ["not.a.real.key"], "rovers": [], "criterion": None})
    assert facts == []


def test_an_analysis_briefing_still_carries_no_facts_key():
    """The guide channel is additive: analysis briefings are what they were."""
    provider = AnalysisProvider(
        grids=_make_grids(),
        snapshot=_snapshot(
            currentPlan={"distance": {"value": 3.0996, "unit": "km"}}
        ),
        budget=ToolBudget(),
    )
    envelope = _build_envelope("C-SUMMARY", {}, provider, provider.grids)
    assert envelope.facts == []
    assert envelope.lexicon == []
    briefing = _briefing(envelope)
    assert "facts" not in briefing


# ── §17: the planning question matrix ────────────────────────────────────────

@pytest.mark.parametrize(
    "topic,subject,expected_key",
    [
        ("workflow", None, "workflow.overview"),
        ("workflow", "first_steps", "workflow.first_steps"),
        ("priority", "slope_safety", "priority.slope_safety"),
        ("priority", "not_percentages", "priority.not_percentages"),
        ("layer", "cost", "layer.cost"),
        ("layer", "shadow", "layer.cost_vs_shadow"),
        ("layer", "slope", "layer.slope_vs_aspect"),
        ("view", "two_d", "view.two_d"),
        ("view", "three_d", "view.three_d"),
        ("mission_controls", "start", "mission_controls.start"),
        ("mission_controls", "goal", "mission_controls.goal"),
        ("mission_controls", "generate_route", "mission_controls.generate_route"),
        ("rover", "rover_select", "mission_controls.rover_select"),
    ],
)
def test_each_supported_question_selects_the_fact_that_answers_it(
    topic, subject, expected_key
):
    envelope = _guide_envelope(topic=topic, subject=subject)
    assert expected_key in {fact.key for fact in envelope.facts}


def test_the_weights_are_explained_as_coefficients_and_not_percentages():
    envelope = _guide_envelope(topic="priority", subject="not_percentages")
    text = " ".join(fact.text for fact in envelope.facts)
    assert "yüzde değildir" in text
    assert "katsayı" in text
    # The claim that matters: changing one does not renormalise the others.
    assert "yeniden ölçeklemez" in text


def test_cost_and_shadow_are_distinguished():
    envelope = _guide_envelope(topic="layer", subject="shadow")
    text = " ".join(fact.text for fact in envelope.facts)
    assert "aynı şey değildir" in text


def test_both_view_dimensions_are_described_and_neither_is_invented():
    envelope = _guide_envelope(topic="view")
    text = " ".join(fact.text for fact in envelope.facts)
    assert "2D" in text and "3D" in text
    # No animation, no time axis, no capability the product does not have.
    assert "animasyon" not in text


def test_generate_route_is_explained_and_not_invoked():
    provider = _provider()
    envelope = _build_envelope(
        "C-GUIDE",
        {"topic": "mission_controls", "subject": "generate_route"},
        provider,
        provider.grids,
    )
    text = " ".join(fact.text for fact in envelope.facts)
    assert "operatör başlatır" in text
    assert provider.snapshot.currentPlan is None


def test_the_guide_states_that_it_changes_nothing():
    envelope = _guide_envelope(topic="workflow")
    text = " ".join(fact.text for fact in envelope.facts)
    assert "yalnızca okur" in text


# ── rover evidence comes from the catalogue, through the registry ────────────

def test_rover_numbers_are_registered_metrics_not_prose():
    envelope = _guide_envelope(topic="rover", rover_ids=["lpr_1"])
    by_key = {metric.key: metric for metric in envelope.numeric_registry}
    assert by_key["lpr_1.e_cap_wh"].display == "5420 Wh"
    assert by_key["lpr_1.mass_kg"].display == "450 kg"
    assert by_key["lpr_1.v_max_ms"].display == "0,20 m/s"
    assert by_key["lpr_1.slope_max_deg"].display == "25 deg"
    assert by_key["lpr_1.h_max_shadow_h"].display == "50 h"
    # No fact repeats a number the registry holds.
    for fact in envelope.facts:
        assert "5420" not in fact.text


def test_the_reserve_fraction_is_scaled_once_and_marked_derived():
    """soc_min_pct is named _pct and holds 0.20. K1 does the scaling."""
    envelope = _guide_envelope(topic="rover", rover_ids=["lpr_1"])
    metric = next(
        m for m in envelope.numeric_registry if m.key == "lpr_1.soc_min_pct"
    )
    assert metric.display == "20 %"
    assert metric.provenance.source == "DERIVED"
    assert "%20" in metric.display_alt


def test_rover_evidence_reads_the_published_catalogue_and_no_further():
    """The power and thermal internals stay behind get_rover()."""
    envelope = _guide_envelope(topic="rover")
    keys = {metric.key.split(".", 1)[-1] for metric in envelope.numeric_registry}
    for internal in ("p_base_w", "p_peak_w", "thermal_tau_s", "mu_coeff", "f_net_n"):
        assert internal not in keys


def test_two_named_rovers_are_compared_from_registered_values():
    envelope = _guide_envelope(topic="rover", rover_ids=["lpr_1", "nasa_viper"])
    keys = {metric.key for metric in envelope.numeric_registry}
    assert "lpr_1.e_cap_wh" in keys
    assert "nasa_viper.e_cap_wh" in keys
    # The rovers nobody asked about stay out of it.
    assert not any(key.startswith("luvmi_m.") for key in keys)
    count = next(m for m in envelope.numeric_registry if m.key == "rover_count")
    assert count.display == "2"
    assert count.display_alt == ["iki rover"]


def test_a_named_criterion_is_resolved_by_k1():
    envelope = _guide_envelope(topic="rover", criterion="battery")
    resolved = next(
        fact for fact in envelope.facts if fact.key == "rover.criterion.battery"
    )
    # lpr_1 holds 5420 Wh, the largest in the catalogue.
    assert "LPR-1" in resolved.text
    # The winner is named; the comparison itself is never handed to the model.
    assert "5420" not in resolved.text


@pytest.mark.parametrize(
    "criterion,winner",
    [
        ("battery", "LPR-1"),
        ("speed", "LPR-1"),
        ("shadow_endurance", "NASA VIPER"),
        ("mass", "LUVMI-M"),
    ],
)
def test_each_criterion_picks_the_extremum_from_the_catalogue(criterion, winner):
    envelope = _guide_envelope(topic="rover", criterion=criterion)
    resolved = next(
        fact for fact in envelope.facts if fact.key.startswith("rover.criterion.")
    )
    assert winner in resolved.text


def test_a_tie_names_every_rover_that_holds_it():
    """lpr_1 and nasa_viper are both 450 kg; neither is the lighter one."""
    payload = guide_evidence(
        {"topic": "rover", "rover_ids": ["lpr_1", "nasa_viper"], "criterion": "mass"},
        rover_catalog(),
    )
    resolved = next(
        fact for fact in guide_facts(payload) if fact.key.startswith("rover.criterion.")
    )
    assert "LPR-1" in resolved.text and "NASA VIPER" in resolved.text
    assert "eşit" in resolved.text


def test_no_criterion_means_no_winner():
    envelope = _guide_envelope(topic="rover")
    text = " ".join(fact.text for fact in envelope.facts)
    assert "evrensel olarak üstün bir rover belirlenemez" in text
    assert not any(fact.key.startswith("rover.criterion.") for fact in envelope.facts)


def test_an_unknown_rover_id_answers_about_the_catalogue_rather_than_nothing():
    payload = guide_evidence(
        {"topic": "rover", "rover_ids": ["mars_rover_9000"]}, rover_catalog()
    )
    assert [entry["id"] for entry in payload["rovers"]] == [
        entry["id"] for entry in rover_catalog()
    ]


def test_the_short_rover_name_is_what_a_sentence_contains():
    assert short_name("LPR-1 (Varsayilan)") == "LPR-1"
    assert short_name("NASA VIPER") == "NASA VIPER"


# ── grounding: the lexicon widens masking without widening the numbers ───────

def _tokens(envelope: AnalysisEnvelope) -> frozenset[str]:
    from app.ai_chat import _profile_names, _rover_names

    return whitelist_tokens(
        envelope, rover_names=_rover_names(), profile_names=_profile_names()
    )


@pytest.mark.parametrize(
    "rover_id", [entry["id"] for entry in rover_catalog()]
)
def test_the_bare_rover_name_survives_the_digit_scan(rover_id):
    """The catalogue publishes "LPR-1 (Varsayilan)"; prose says "LPR-1".

    Parametrized over the whole catalogue rather than the default rover,
    because the digit is not in the same place for each of them. "LPR-1"
    carries it in the published name, "CNSA Yutu-2" carries it after a word
    the whitelist does not otherwise contain, and "NASA VIPER" and "LUVMI-M"
    carry none at all -- so a whitelist that happened to work for one of them
    proves very little about the others. This is the assertion that would have
    caught the bare-name gap for Yutu-2 rather than only for LPR-1.
    """
    entry = next(item for item in rover_catalog() if item["id"] == rover_id)
    name = short_name(str(entry["name"]))
    envelope = _guide_envelope(topic="rover", rover_ids=[rover_id])
    verdict = validate_draft(
        f"{name} katalogda tanımlı bir rover'dır.", envelope, _tokens(envelope)
    )
    assert verdict.ok, (name, diagnostic(verdict))


@pytest.mark.parametrize(
    "rover_id", [entry["id"] for entry in rover_catalog()]
)
def test_every_rover_publishes_its_specs_as_registered_metrics(rover_id):
    """A name that masks is not enough; the numbers beside it must too."""
    envelope = _guide_envelope(topic="rover", rover_ids=[rover_id])
    displays = [metric.display for metric in envelope.numeric_registry]
    assert len(displays) > 1, rover_id
    draft = " ".join(f"Değer {display}." for display in displays)
    verdict = validate_draft(draft, envelope, _tokens(envelope))
    assert verdict.ok, (rover_id, diagnostic(verdict))


def test_the_view_identifiers_survive_the_digit_scan():
    envelope = _guide_envelope(topic="view")
    verdict = validate_draft(
        "LunaPath araziyi 2D ve 3D olarak gösterebilir.", envelope, _tokens(envelope)
    )
    assert verdict.ok, diagnostic(verdict)


def test_the_authorised_percent_phrase_survives_the_percent_scan():
    envelope = _guide_envelope(topic="priority", subject="not_percentages")
    verdict = validate_draft(
        "Bu öncelikler ağırlık katsayısıdır; yüzde değildir.",
        envelope,
        _tokens(envelope),
    )
    assert verdict.ok, diagnostic(verdict)


def test_an_unauthorised_percentage_still_blocks_in_the_same_answer():
    envelope = _guide_envelope(topic="priority", subject="not_percentages")
    verdict = validate_draft(
        "Bu öncelikler yüzde değildir, ancak enerji ağırlığı yüzde 40'tır.",
        envelope,
        _tokens(envelope),
    )
    assert not verdict.ok
    assert {"code": "UNREGISTERED_PERCENT"} in diagnostic(verdict)


def test_authorising_a_view_identifier_does_not_authorise_a_stray_digit():
    envelope = _guide_envelope(topic="view")
    verdict = validate_draft(
        "LunaPath 2D ve 3D destekler ve 7 katman gösterir.",
        envelope,
        _tokens(envelope),
    )
    assert not verdict.ok
    assert {"code": "UNREGISTERED_NUMBER"} in diagnostic(verdict)


def test_an_invented_rover_number_is_blocked():
    envelope = _guide_envelope(topic="rover", rover_ids=["lpr_1"])
    verdict = validate_draft(
        "LPR-1 batarya kapasitesi 9999 Wh.", envelope, _tokens(envelope)
    )
    assert not verdict.ok
    assert {"code": "UNREGISTERED_NUMBER"} in diagnostic(verdict)


def test_a_registered_rover_number_is_verified():
    envelope = _guide_envelope(topic="rover", rover_ids=["lpr_1"])
    verdict = validate_draft(
        "LPR-1 batarya kapasitesi 5420 Wh, azami eğimi 25 deg.",
        envelope,
        _tokens(envelope),
    )
    assert verdict.ok, diagnostic(verdict)


def test_the_registered_rover_count_may_be_spelled_out():
    envelope = _guide_envelope(topic="rover", rover_ids=["lpr_1", "nasa_viper"])
    verdict = validate_draft(
        "Karşılaştırmada iki rover var.", envelope, _tokens(envelope)
    )
    assert verdict.ok, diagnostic(verdict)


def test_an_unregistered_rover_count_is_blocked():
    envelope = _guide_envelope(topic="rover", rover_ids=["lpr_1", "nasa_viper"])
    verdict = validate_draft(
        "Karşılaştırmada yedi rover var.", envelope, _tokens(envelope)
    )
    assert not verdict.ok
    assert {"code": "UNREGISTERED_NUMBER_WORD"} in diagnostic(verdict)


@pytest.mark.parametrize(
    "topic,params",
    [
        ("workflow", {}),
        ("priority", {}),
        ("layer", {}),
        ("view", {}),
        ("mission_controls", {}),
        ("rover", {}),
        ("rover", {"criterion": "battery"}),
    ],
)
def test_the_fallback_passes_the_check_it_is_the_fallback_for(topic, params):
    """A blocked guide answer must not produce a second blocked answer."""
    envelope = _guide_envelope(topic=topic, **params)
    fallback = deterministic_fallback(envelope)
    verdict = validate_draft(fallback, envelope, _tokens(envelope))
    assert verdict.ok, diagnostic(verdict)


def test_a_prose_only_fallback_does_not_claim_to_be_showing_values():
    envelope = _guide_envelope(topic="workflow")
    assert envelope.numeric_registry == []
    fallback = deterministic_fallback(envelope)
    assert "kayıtlı bilgileri" in fallback
    assert "kayıtlı değerleri" not in fallback
    for fact in envelope.facts:
        assert fact.text in fallback


# ── read-only: a mutation is refused, and never faked ────────────────────────

def test_a_mutation_request_is_refused_with_the_manual_instruction():
    _install(
        _routed({"action": "refuse", "code": "MUTATING_REQUEST"}, "unused")
    )
    try:
        response = client.post(
            "/api/ai/chat", json=_payload("Energy Use değerini 0.5 yap.")
        )
        body = response.json()
        assert body["errorCode"] == "E-SCOPE"
        # Told how to do it, never told that it was done.
        assert "salt okunur" in body["answer"]
        assert "Generate Route" in body["answer"]
        for claim in ("ayarladım", "değiştirdim", "yaptım", "güncelledim"):
            assert claim not in body["answer"].lower()
    finally:
        _teardown()


def test_the_two_refusals_do_not_share_one_message():
    assert refusal_message("MUTATING_REQUEST") != refusal_message("OUT_OF_SCOPE")
    assert "LunaPath" in refusal_message("OUT_OF_SCOPE")


def test_an_out_of_scope_question_is_still_out_of_scope():
    _install(_routed({"action": "refuse", "code": "OUT_OF_SCOPE"}, "unused"))
    try:
        response = client.post("/api/ai/chat", json=_payload("Python kodu yaz."))
        body = response.json()
        assert body["errorCode"] == "E-SCOPE"
        assert body["groundingStatus"] == "not_applicable"
    finally:
        _teardown()


# ── what the router is allowed to see ────────────────────────────────────────

def test_the_router_context_names_the_rovers_without_pricing_them():
    context = _provider().get_context()
    assert context["rover_ids"] == [entry["id"] for entry in rover_catalog()]
    blob = json.dumps(context, default=str)
    # Identifiers, not specifications: a number here is a number K2 could echo.
    for value in ("5420", "450", "0.2", "25"):
        assert value not in blob


def test_the_guide_limitations_say_what_it_is_not():
    _install(
        _routed(
            {
                "action": "invoke",
                "capability": "C-GUIDE",
                "params": {"topic": "workflow"},
                "rationale_key": "product_help",
            },
            "Önce bir rover seçin.",
        )
    )
    try:
        body = client.post("/api/ai/chat", json=_payload("Önce ne yapmalıyım?")).json()
        codes = {item["code"] for item in body["limitations"]}
        assert codes == {"PRODUCT_SCOPE_ONLY", "READ_ONLY_GUIDANCE"}
    finally:
        _teardown()
