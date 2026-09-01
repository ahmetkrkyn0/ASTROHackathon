"""K5 -- the deterministic gate between the model's draft and the operator.

The strategy is mask-then-scan, not parse. K5 deletes every whitelisted
identifier and every registered display string from the draft, then asserts no
digit survives. It therefore owns no number parser and never has to decide
whether `1.490` means one thousand four hundred ninety.

Tolerance is zero by construction: rounding happened once, in K1's
format_display. These tests exist to keep it that way.

Contract: docs/ai/LunaPath_AI_Chatbot_Scope_v0.3.md sections 12 and 15.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import pytest

from app.ai_analysis import (
    AnalysisEnvelope,
    EnvelopeWarning,
    Provenance,
    make_metric,
    percent_of_ratio,
)
from app.ai_grounding import (
    deterministic_fallback,
    tr_fold,
    validate_draft,
    whitelist_tokens,
)


def _prov() -> Provenance:
    return Provenance(source="DERIVED", layer="thermal")


def _envelope(*metrics, warnings=(), backend_version="0.3.0") -> AnalysisEnvelope:
    return AnalysisEnvelope(
        capability="C-SUMMARY",
        request_echo={},
        ok=True,
        payload={},
        numeric_registry=list(metrics),
        warnings=list(warnings),
        provenance_summary=[_prov()],
        backend_version=backend_version,
    )


def _energy():
    return make_metric(
        key="total_energy_consumed_wh",
        label="Toplam enerji tüketimi",
        value=1490.23,
        unit="Wh",
        provenance=_prov(),
    )


def _ratio():
    return make_metric(
        key="barrier_share",
        label="Bariyer payı",
        value=0.13215,
        unit="dimensionless",
        provenance=Provenance(source="MODEL"),
    )


def _count(n: int = 4):
    return make_metric(
        key="profile_count",
        label="Profil sayısı",
        value=n,
        unit="dimensionless",
        provenance=_prov(),
        precision=0,
    )


EMPTY = frozenset()


# -- numeric grounding: the registered value passes ---------------------------

def test_a_registered_display_string_is_accepted():
    verdict = validate_draft(
        "Toplam enerji tüketimi 1490,23 Wh olarak hesaplandı.", _envelope(_energy()), EMPTY
    )
    assert verdict.ok


def test_prose_with_no_numbers_at_all_is_accepted():
    verdict = validate_draft(
        "Mevcut kanıt bu sapmanın nedenini belirlemiyor.", _envelope(), EMPTY
    )
    assert verdict.ok


def test_a_turkish_suffix_after_the_unit_is_accepted():
    verdict = validate_draft(
        "1490,23 Wh'lik tüketim bekleniyor.", _envelope(_energy()), EMPTY
    )
    assert verdict.ok


def test_a_registered_count_is_accepted():
    verdict = validate_draft("4 profil karşılaştırıldı.", _envelope(_count()), EMPTY)
    assert verdict.ok


# -- numeric grounding: everything else fails closed --------------------------

def test_a_unit_conversion_the_model_performed_is_blocked():
    # 1490,23 Wh is registered; 1,49 kWh is the model doing arithmetic (N-1).
    verdict = validate_draft("Yaklaşık 1,49 kWh harcanıyor.", _envelope(_energy()), EMPTY)
    assert not verdict.ok
    assert any(v.code == "UNREGISTERED_NUMBER" for v in verdict.violations)


def test_a_percentage_the_model_computed_is_blocked():
    # 0,13215 is registered as a ratio; 13,2 % is not registered.
    verdict = validate_draft("Bariyer payı %13,2 civarında.", _envelope(_ratio()), EMPTY)
    assert not verdict.ok


def test_a_registered_derived_percentage_is_accepted():
    ratio = _ratio()
    pct = percent_of_ratio(ratio, key="barrier_share_pct", label="Bariyer payı")
    verdict = validate_draft(
        "Bariyer payı 13,2 % olarak kayıtlı.", _envelope(ratio, pct), EMPTY
    )
    assert verdict.ok


def test_a_bare_percent_sign_without_a_registered_percentage_is_blocked():
    verdict = validate_draft("Enerjinin yüzde biri kayboldu.", _envelope(_energy()), EMPTY)
    assert not verdict.ok


def test_extra_precision_beyond_the_registered_display_is_blocked():
    # Registered 1490,23 must not license 1490,236.
    verdict = validate_draft("Tüketim 1490,236 Wh.", _envelope(_energy()), EMPTY)
    assert not verdict.ok


def test_a_registered_display_cannot_be_masked_out_of_a_longer_number():
    # 31490,23 contains 1490,23 as a suffix; the lookbehind must stop that.
    verdict = validate_draft("Tüketim 31490,23 Wh.", _envelope(_energy()), EMPTY)
    assert not verdict.ok


def test_looser_rounding_than_the_registered_precision_is_blocked():
    verdict = validate_draft("Tüketim yaklaşık 1490,2 Wh.", _envelope(_energy()), EMPTY)
    assert not verdict.ok


def test_a_dot_decimal_rendering_of_a_registered_value_is_blocked():
    # Accepting comma-dot equivalence would force a thousands-separator
    # decision, which is exactly the parser this design refuses to own.
    verdict = validate_draft("Tüketim 1490.23 Wh.", _envelope(_energy()), EMPTY)
    assert not verdict.ok


def test_an_entirely_invented_number_is_blocked():
    verdict = validate_draft("Rota 12 krater içeriyor.", _envelope(_energy()), EMPTY)
    assert not verdict.ok


# -- spelled-out numbers: the digit scan alone is not enough ------------------

def test_a_number_spelled_in_words_before_a_counted_noun_is_blocked():
    # Without this the model evades the whole validator by writing it out.
    verdict = validate_draft("Üç profil karşılaştırıldı.", _envelope(_count()), EMPTY)
    assert not verdict.ok
    assert any(v.code == "UNREGISTERED_NUMBER_WORD" for v in verdict.violations)


def test_the_registered_digit_form_is_still_the_way_to_say_it():
    verdict = validate_draft("4 profil karşılaştırıldı.", _envelope(_count()), EMPTY)
    assert verdict.ok


def test_a_numeral_word_away_from_a_counted_noun_does_not_fire():
    # Bounded to the nouns K1 actually counts; no general Turkish parser.
    verdict = validate_draft("Yüzey sıcaklığı düşük görünüyor.", _envelope(), EMPTY)
    assert verdict.ok


# -- identifier whitelist -----------------------------------------------------

def test_a_runtime_rover_name_containing_a_digit_is_not_a_violation():
    tokens = whitelist_tokens(_envelope(), rover_names=["LPR-1 (Varsayilan)"])
    verdict = validate_draft("LPR-1 (Varsayilan) seçili.", _envelope(), tokens)
    assert verdict.ok


def test_a_runtime_profile_name_is_not_a_violation():
    tokens = whitelist_tokens(_envelope(), profile_names=["Golge Gecis"])
    verdict = validate_draft("Golge Gecis profili daha uzun.", _envelope(), tokens)
    assert verdict.ok


def test_the_envelope_backend_version_is_whitelisted():
    envelope = _envelope(backend_version="0.3.0")
    tokens = whitelist_tokens(envelope)
    verdict = validate_draft("Backend sürümü 0.3.0.", envelope, tokens)
    assert verdict.ok


def test_a_version_string_the_model_invented_is_blocked():
    envelope = _envelope(backend_version="0.3.0")
    tokens = whitelist_tokens(envelope)
    verdict = validate_draft("Veri seti 2026-09-01 tarihli.", envelope, tokens)
    assert not verdict.ok


def test_the_whitelist_does_not_carry_unrelated_spec_identifiers():
    # Correction 6: minimal. NASA-STD-7009B is not needed by a first-cut answer.
    tokens = whitelist_tokens(_envelope())
    assert not any("7009" in token for token in tokens)


def test_a_longer_whitelist_token_wins_over_a_shorter_one():
    tokens = whitelist_tokens(_envelope(), rover_names=["CNSA Yutu-2"])
    verdict = validate_draft("CNSA Yutu-2 daha yavaş.", _envelope(), tokens)
    assert verdict.ok


# -- list markers -------------------------------------------------------------

def test_a_leading_list_marker_is_structural_not_analytic():
    draft = "Bulgular:\n1. Enerji 1490,23 Wh.\n2. Mesafe kayıtlı değil."
    verdict = validate_draft(draft, _envelope(_energy()), EMPTY)
    # The second line has no number, so only the markers could have tripped it.
    assert verdict.ok


def test_a_mid_sentence_ordinal_is_still_blocked():
    # At line start "2." is indistinguishable from a list marker, so the case
    # that matters is an ordinal inside a sentence. Profiles must be named,
    # not indexed -- an index is something the operator cannot verify.
    verdict = validate_draft("Bence 2. profil daha iyi.", _envelope(_count()), EMPTY)
    assert not verdict.ok


# -- Turkish case folding -----------------------------------------------------

def test_turkish_dotted_capital_i_folds_correctly():
    assert tr_fold("KESİNLİKLE") == "kesinlikle"
    assert tr_fold("IŞIK") == "ışık"


def test_an_uppercase_certainty_claim_does_not_evade_the_scan():
    verdict = validate_draft("BU ROTA KESİNLİKLE UYGUN.", _envelope(), EMPTY)
    assert not verdict.ok


# -- forbidden claims ---------------------------------------------------------

@pytest.mark.parametrize(
    "draft",
    [
        "Bu rota güvenlidir.",
        "Sistem rover'ı korur.",
        "Otonom navigasyon sağlıyoruz.",
        "Gerçek zamanlı engel kaçınma yapıyor.",
        "Gerçek NASA verisiyle çalışıyoruz.",
        "Bu alanda ilk çözüm.",
        "Rover üzerinde çalışabilir.",
        "Uçuş yazılımı olarak sertifikalı.",
        "Kesinlikle sorun çıkmaz.",
        "%100 garanti veriyoruz.",
    ],
)
def test_forbidden_claims_are_blocked(draft):
    verdict = validate_draft(draft, _envelope(), EMPTY)
    assert not verdict.ok, draft
    assert any(v.code.startswith("N-") for v in verdict.violations), draft


@pytest.mark.parametrize(
    "draft",
    [
        "Güvenlik marjı dar görünüyor.",
        "Rota, tanımlı kısıtları ihlal etmiyor.",
        "Bu bir otonom navigasyon sistemi değildir.",
        "Yerel engel kaçınma kapsam dışıdır.",
        "Termal katman türetilmiş veriye dayanıyor.",
        "İlk adımda mesafe kaydedildi.",
        "Bu, tek değişkenli bir perturbasyon değildir.",
        "Uçuş yazılımı olarak tasarlanmamıştır.",
        "Sonuç garanti edilemez.",
    ],
)
def test_legitimate_engineering_prose_is_not_blocked(draft):
    verdict = validate_draft(draft, _envelope(), EMPTY)
    assert verdict.ok, f"{draft} -> {[v.code for v in verdict.violations]}"


def test_the_safety_rule_keys_on_the_adjective_not_the_compound_noun():
    # guvenli(?!k) is the whole trick: guvenlik marji is exempt for free.
    assert validate_draft("Güvenlik faktörü 2 kat.", _envelope(
        make_metric(key="k", label="K", value=2, unit="dimensionless",
                    provenance=_prov(), precision=0)), EMPTY).ok


# -- deterministic fallback ---------------------------------------------------

def test_the_fallback_lists_only_registered_values():
    envelope = _envelope(_energy(), _count())
    text = deterministic_fallback(envelope)
    assert "1490,23 Wh" in text
    assert "4" in text


def test_the_fallback_passes_its_own_grounding_check():
    # Self-consistency: the safety net must not itself be ungrounded.
    envelope = _envelope(_energy(), _count())
    text = deterministic_fallback(envelope)
    assert validate_draft(text, envelope, whitelist_tokens(envelope)).ok


def test_the_fallback_repeats_mandatory_warnings():
    envelope = _envelope(
        _energy(),
        warnings=[
            EnvelopeWarning(
                code="CELL_COST_BREAKDOWN_WEIGHT_MISMATCH",
                severity="caution",
                message="Ağırlıklar uyuşmuyor.",
            )
        ],
    )
    assert "Ağırlıklar uyuşmuyor." in deterministic_fallback(envelope)


def test_the_fallback_performs_no_arithmetic():
    envelope = _envelope(_ratio())
    text = deterministic_fallback(envelope)
    assert "13,2" not in text
    assert "0,13215" in text
