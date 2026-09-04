"""Route summaries: what K4 is told to lead with, and what K5 lets through.

Two separate jobs, and the split matters.

The FIRST half is about the briefing. A summary was previously handed the
registry in registration order with nothing saying which facts were core, so
the model could open on a node count. Ordering and an explicit ``section`` fix
that without giving K4 anything new to say.

The SECOND half is about false positives in K5, and every test here exists
because a CORRECT answer was being blocked. None of it loosens the check: the
tolerance is still zero, every claim rule still fires, and each fix is either a
narrower lookahead or an alternative rendering of digits K1 already registered.
The blocked-draft diagnostics are pinned by name so a regression names itself.
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
    EnvelopeWarning,
    Provenance,
    make_metric,
    plan_registry,
    summary_section,
    unit_aliases,
)
from app.ai_chat import _verbalizer_input
from app.ai_grounding import (
    _NUMERAL_WORDS,
    deterministic_fallback,
    diagnostic,
    validate_draft,
    whitelist_tokens,
)
from app.ai_provider import ProviderReply, StubProvider
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

PROV = Provenance(source="DERIVED", layer="thermal")

# The shape a real plan reaches the assistant in, after ai_evidence.
PLAN = {
    "distance": {"value": 3.0996, "unit": "km"},
    "elapsed": {"value": 2.4512, "unit": "h"},
    "energy": {"value": 1490.23, "unit": "Wh"},
    "min_battery": {"value": 34.24, "unit": "%"},
    "final_battery": {"value": 51.8, "unit": "%"},
    "max_slope": {"value": 12.336, "unit": "deg"},
    "max_continuous_shadow": {"value": 3.4147, "unit": "h"},
    "waypoint_count": 495,
    "critical_steps_count": 2,
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


def _summary_env(warnings=()) -> AnalysisEnvelope:
    return AnalysisEnvelope(
        capability="C-SUMMARY",
        ok=True,
        numeric_registry=plan_registry(PLAN, PROV),
        warnings=list(warnings),
        provenance_summary=[PROV],
        backend_version="0.3.0",
    )


def _tokens(envelope: AnalysisEnvelope) -> frozenset[str]:
    return whitelist_tokens(envelope, rover_names=[], profile_names=[])


def _diagnose(draft: str, envelope: AnalysisEnvelope | None = None):
    envelope = envelope or _summary_env()
    return diagnostic(validate_draft(draft, envelope, _tokens(envelope)))


def _briefing(envelope: AnalysisEnvelope, level: str = "L2") -> dict:
    content = _verbalizer_input(envelope, "Bu rotayı özetle.", level)[0]["content"]
    return json.loads(content[content.index("{") :])


def _install(provider) -> None:
    app.state.grids = _make_grids()
    app.state.ai_provider = provider


def _teardown() -> None:
    app.state.ai_provider = None


def _payload(question: str = "Bu rotayı özetle.") -> dict:
    return {
        "messages": [{"role": "user", "content": question}],
        "mission": {
            "start": [2, 2],
            "goal": [8, 8],
            "roverId": "lpr_1",
            "weights": dict(_WEIGHTS),
            "focusedCell": None,
            "currentPlan": dict(PLAN),
        },
        "explanationLevel": "L2",
    }


# ── §12: the briefing says what a summary leads with ─────────────────────────

def test_the_registry_is_ordered_route_then_energy_then_terrain():
    quantities = [
        metric.key
        for metric in plan_registry(PLAN, PROV)
        if metric.quantity.unit != DIMENSIONLESS
    ]
    assert quantities == [
        "distance",
        "elapsed",
        "energy",
        "min_battery",
        "final_battery",
        "max_slope",
        "max_continuous_shadow",
    ]


def test_distance_is_still_the_first_registered_metric():
    """Pinned separately: another test asserts numeric_registry[0] by display."""
    assert plan_registry(PLAN, PROV)[0].key == "distance"


@pytest.mark.parametrize(
    "key,section",
    [
        ("distance", "route"),
        ("elapsed", "route"),
        ("energy", "energy"),
        ("min_battery", "energy"),
        ("final_battery", "energy"),
        ("max_slope", "terrain"),
        ("max_continuous_shadow", "terrain"),
    ],
)
def test_each_core_metric_carries_its_section(key, section):
    assert summary_section(key) == section


def test_the_briefing_labels_the_sections_it_knows():
    briefing = _briefing(_summary_env())
    sections = {
        item["key"]: item.get("section") for item in briefing["metrics"]
    }
    assert sections["distance"] == "route"
    assert sections["energy"] == "energy"
    assert sections["max_slope"] == "terrain"


def test_a_metric_with_no_section_is_secondary_by_omission():
    """Nothing invents a section for a metric K1 does not place."""
    envelope = AnalysisEnvelope(
        capability="C-SUMMARY",
        ok=True,
        numeric_registry=[
            make_metric(
                key="nodes_expanded",
                label="Genişletilen düğüm",
                value=1200,
                unit=DIMENSIONLESS,
                provenance=PROV,
                precision=0,
            )
        ],
    )
    assert "section" not in _briefing(envelope)["metrics"][0]
    assert summary_section("nodes_expanded") is None


# ── §13: the level changes the telling, never the facts ──────────────────────

@pytest.mark.parametrize("level", ["L1", "L2", "L3"])
def test_every_level_receives_the_same_facts(level):
    baseline = _briefing(_summary_env(), "L2")
    briefing = _briefing(_summary_env(), level)
    assert briefing["explanation_level"] == level
    del baseline["explanation_level"], briefing["explanation_level"]
    assert briefing == baseline


def test_a_mandatory_warning_reaches_the_briefing_at_every_level():
    warning = EnvelopeWarning(
        code="CONSTRAINT_VIOLATED",
        severity="critical",
        message="Enerji tasarrufu profilinde soc kısıtı sağlanmıyor.",
    )
    for level in ("L1", "L2", "L3"):
        briefing = _briefing(_summary_env(warnings=[warning]), level)
        assert briefing["warnings"][0]["code"] == "CONSTRAINT_VIOLATED"


# ── §11: the false positives, and why each one was a product defect ──────────

def test_a_registered_display_followed_by_a_comma_is_still_registered():
    """The blocker a normal Turkish summary sentence walks into.

    "... 3,100 km, ... 1490,23 Wh." is a faithful answer built entirely from
    canonical displays, and the comma alone used to make it unmaskable.
    """
    verdict = validate_draft(
        "Toplam mesafe 3,100 km, geçen süre 2,45 h, toplam enerji 1490,23 Wh.",
        _summary_env(),
        _tokens(_summary_env()),
    )
    assert verdict.ok, diagnostic(verdict)


def test_a_dimensionless_display_still_guards_its_comma():
    """495 really can be the head of 495,2, so that guard stays."""
    envelope = AnalysisEnvelope(
        capability="C-SUMMARY",
        ok=True,
        numeric_registry=[
            make_metric(
                key="waypoint_count",
                label="Rota düğüm sayısı",
                value=495,
                unit=DIMENSIONLESS,
                provenance=PROV,
                precision=0,
            )
        ],
    )
    verdict = validate_draft("Düğüm sayısı 495,2 kadar.", envelope, _tokens(envelope))
    assert not verdict.ok
    assert {"code": "UNREGISTERED_NUMBER"} in diagnostic(verdict)


def test_a_longer_number_still_cannot_hide_behind_a_registered_one():
    assert {"code": "UNREGISTERED_NUMBER"} in _diagnose("Enerji 1490,236 Wh.")
    assert {"code": "UNREGISTERED_NUMBER"} in _diagnose("Enerji 31490,23 Wh.")


def test_the_turkish_percent_order_is_a_registered_rendering():
    """Prose writes %34,2 where the canonical display is "34,2 %"."""
    verdict = validate_draft(
        "Minimum batarya %34,2 seviyesine iniyor.",
        _summary_env(),
        _tokens(_summary_env()),
    )
    assert verdict.ok, diagnostic(verdict)


@pytest.mark.parametrize(
    "draft",
    [
        "En dik eğim 12,34°.",
        "En dik eğim 12,34 derece.",
        "Geçen süre 2,45 saat.",
        "Toplam mesafe 3,100 kilometre.",
    ],
)
def test_the_natural_turkish_unit_is_a_registered_rendering(draft):
    verdict = validate_draft(draft, _summary_env(), _tokens(_summary_env()))
    assert verdict.ok, diagnostic(verdict)


def test_an_unregistered_percentage_still_blocks():
    codes = _diagnose("Batarya %41,7 seviyesine iniyor.")
    assert {"code": "UNREGISTERED_NUMBER"} in codes
    assert {"code": "UNREGISTERED_PERCENT"} in codes


def test_a_converted_unit_still_blocks():
    """1,49 kWh is the same magnitude and a different string. Zero tolerance."""
    assert {"code": "UNREGISTERED_NUMBER"} in _diagnose("Enerji 1,49 kWh.")


# ── the alias generator is bounded, and provably so ──────────────────────────

def test_every_generated_alias_preserves_the_registered_digits():
    for metric in plan_registry(PLAN, PROV):
        numeric = re.sub(r"[^\d,]", "", metric.display)
        for alias in metric.display_alt:
            assert numeric and numeric in alias.replace(" ", ""), (metric.key, alias)


def test_no_generated_alias_spells_a_number_as_a_word():
    """The thing Metric.display_alt exists to prevent, asserted directly.

    A numeral WORD in an auto-derived alias would let the verbalizer spell any
    registered value. Order and unit variants cannot: they carry the same
    digits.
    """
    patterns = [re.compile(r"\b" + word + r"\w*", re.IGNORECASE) for word in _NUMERAL_WORDS]
    for metric in plan_registry(PLAN, PROV):
        for alias in metric.display_alt:
            for pattern in patterns:
                assert not pattern.search(alias), (metric.key, alias)


def test_the_energy_unit_is_deliberately_not_aliased():
    """_mask_aliases is case-insensitive, and Wh is not wh."""
    assert unit_aliases("1490,23 Wh", "Wh") == []


def test_a_dimensionless_count_gets_no_automatic_alias():
    assert unit_aliases("495", DIMENSIONLESS) == []


# ── §15: the blocked-draft diagnostics, pinned by name ───────────────────────

def test_a_clean_draft_produces_no_diagnostic():
    assert _diagnose("Rota 3,100 km ve 1490,23 Wh olarak kaydedildi.") == ()


@pytest.mark.parametrize(
    "draft,code",
    [
        ("Rota 4200 Wh harcadı.", "UNREGISTERED_NUMBER"),
        ("Rota bin dört yüz doksan Wh harcadı.", "UNREGISTERED_NUMBER_WORD"),
        ("Batarya yüzde 40 seviyesinde.", "UNREGISTERED_PERCENT"),
        ("Enerji 1490,23 Wh ± 5 Wh.", "UNREGISTERED_UNCERTAINTY"),
    ],
)
def test_each_numeric_category_reports_itself(draft, code):
    assert {"code": code} in _diagnose(draft)


@pytest.mark.parametrize(
    "draft,rule",
    [
        ("Sistem otonom navigasyon yapar.", "N-6"),
        ("Bu katman gerçek NASA verisidir.", "N-7"),
        ("Bu rota güvenlidir.", "N-8"),
        ("LunaPath bu alandaki en iyi çözüm.", "N-9"),
        ("Yazılım sertifikalıdır.", "N-10"),
        ("Bu bir uçuş yazılımıdır.", "N-10"),
        ("Rota risksizdir.", "N-8"),
        ("LunaPath bu alandaki en iyi çözümdür.", "N-9"),
        ("Rota kesinlikle tamamlanır.", "N-11"),
    ],
)
def test_each_forbidden_claim_reports_its_contract_rule(draft, rule):
    assert {"code": "FORBIDDEN_CLAIM", "rule": rule} in _diagnose(draft)


@pytest.mark.parametrize(
    "draft",
    [
        "Bu rover güvenlidir.",
        "Güvenli bir roverdır.",
        "Seçili rover tamamen güvenlidir.",
    ],
)
def test_a_rover_safety_claim_is_refused_like_a_route_one(draft):
    """N-8 gained a subject when C-GUIDE gained rovers.

    The rule protected rota/güzergah/yol and admitted "rover" only with
    korur/koruyor/koruyacak, which was enough while the assistant never made a
    rover the subject of a sentence. C-GUIDE answers "which rover" and
    "LPR-1 vs NASA VIPER", so it does now.
    """
    assert {"code": "FORBIDDEN_CLAIM", "rule": "N-8"} in _diagnose(draft)


@pytest.mark.parametrize(
    "draft",
    [
        "Bu rover güvenli değildir.",
        "Bu roverın güvenli olduğu doğrulanmamıştır.",
        "Mevcut veriler roverın güvenli olduğunu kanıtlamaz.",
        "Bu analiz rover güvenliğini sertifikalandırmaz.",
        # The narrowing the copula requirement buys: a measurement about a
        # limit is not a claim about the rover.
        "Rover için güvenli sınır aşılmadı.",
        "Rover güvenliği bu analizin kapsamı dışındadır.",
    ],
)
def test_cautious_language_about_a_rover_is_not_a_claim(draft):
    """Denying, hedging and measuring all have to survive.

    A rule that blocked "bu rover güvenli değildir" would push the verbalizer
    towards saying nothing about safety at all, which is the opposite of what
    N-8 is for.
    """
    assert _diagnose(draft) == ()


def test_a_safety_margin_is_not_a_safety_claim():
    """N-8's exemption: "güvenlik marjı" is a different word."""
    assert _diagnose("Güvenlik marjı korunuyor; kısıtlar ihlal edilmiyor.") == ()


def test_a_diagnostic_never_carries_the_draft_it_rejected():
    codes = _diagnose("Bu rota kesinlikle güvenlidir ve 9999 Wh harcar.")
    serialised = json.dumps(codes, ensure_ascii=False)
    for leak in ("güvenli", "kesinlikle", "9999"):
        assert leak not in serialised
    for entry in codes:
        assert set(entry) <= {"code", "rule"}


def test_an_empty_draft_blocks_rather_than_answering_with_nothing():
    _install(
        StubProvider(
            script=[ProviderReply(text="", tool_calls=[])],
            structured_script=[json.dumps({"action": "answer_from_context"})],
        )
    )
    try:
        body = client.post("/api/ai/chat", json=_payload()).json()
        assert body["errorCode"] == "E-GROUNDING"
        assert body["groundingStatus"] == "blocked"
        # The operator still gets the registered values rather than a blank turn.
        assert "1490,23 Wh" in body["answer"]
    finally:
        _teardown()


def test_the_fallback_still_passes_the_check_after_the_alias_change():
    envelope = _summary_env(
        warnings=[
            EnvelopeWarning(
                code="CONSTRAINT_VIOLATED",
                severity="critical",
                message="Enerji tasarrufu profilinde soc kısıtı sağlanmıyor.",
            )
        ]
    )
    verdict = validate_draft(
        deterministic_fallback(envelope), envelope, _tokens(envelope)
    )
    assert verdict.ok, diagnostic(verdict)


# ── the summary path end to end, on a scripted provider ──────────────────────

def test_a_faithful_summary_is_verified_rather_than_falling_back():
    draft = (
        "Rota 3,100 km uzunluğunda ve 2,45 h sürüyor. Toplam enerji tüketimi "
        "1490,23 Wh, minimum batarya %34,2. En dik eğim 12,34°."
    )
    _install(
        StubProvider(
            script=[ProviderReply(text=draft, tool_calls=[])],
            structured_script=[json.dumps({"action": "answer_from_context"})],
        )
    )
    try:
        body = client.post("/api/ai/chat", json=_payload()).json()
        assert body["groundingStatus"] == "verified", body["answer"]
        assert body["errorCode"] is None
        assert body["answer"] == draft
    finally:
        _teardown()
