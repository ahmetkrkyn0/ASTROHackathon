"""K1 types: the canonical display string is the whole grounding strategy.

K5 does not parse numbers. It masks registered display strings out of the
draft and asserts no digit survives. That only works if the display string is
a pure, total function of (value, unit, precision) -- so these tests pin the
format hard, especially the absence of a thousands separator, which is what
removes `1.490,23` from the system at the source.

Contract: docs/ai/LunaPath_AI_Chatbot_Scope_v0.3.md section 13.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import pytest

from app.ai_analysis import (
    AnalysisEnvelope,
    EnvelopeWarning,
    Metric,
    Provenance,
    format_display,
    make_metric,
    percent_of_ratio,
)


# -- format_display -----------------------------------------------------------

def test_decimal_separator_is_a_comma():
    assert format_display(1490.23, "Wh", 2) == "1490,23 Wh"


def test_there_is_no_thousands_separator():
    # This single choice is why K5 never has to decide whether 1.490 is 1490.
    assert format_display(1490.23, "Wh", 2) == "1490,23 Wh"
    assert format_display(1234567.5, "m", 1) == "1234567,5 m"


def test_precision_is_applied_exactly():
    assert format_display(0.13215, "dimensionless", 5) == "0,13215"
    assert format_display(0.13215, "dimensionless", 2) == "0,13"


def test_a_dimensionless_value_carries_no_unit_token():
    assert format_display(0.5, "dimensionless", 1) == "0,5"


def test_an_integer_count_renders_without_a_decimal_part():
    assert format_display(4, "dimensionless", 0) == "4"


def test_the_unit_follows_exactly_one_space():
    assert format_display(3.4147, "h", 2) == "3,41 h"


def test_negative_values_use_an_ascii_hyphen():
    rendered = format_display(-183.1, "degC", 1)
    assert rendered == "-183,1 degC"
    assert "−" not in rendered


def test_precision_defaults_come_from_the_unit():
    # Wh defaults to 2 decimals; the caller does not have to remember.
    assert format_display(1490.234, "Wh") == "1490,23 Wh"


def test_a_non_finite_value_cannot_be_rendered():
    with pytest.raises(ValueError):
        format_display(float("nan"), "Wh", 2)


def test_rounding_happens_once_here_and_is_half_up():
    # K5 has zero tolerance, so this is the only place rounding occurs.
    assert format_display(13.25, "%", 1) == "13,3 %"


# -- Metric -------------------------------------------------------------------

def _prov() -> Provenance:
    return Provenance(source="DERIVED", layer="thermal")


def test_a_metric_carries_its_own_display_string():
    metric = make_metric(
        key="total_energy_consumed_wh",
        label="Toplam enerji tüketimi",
        value=1490.23,
        unit="Wh",
        provenance=_prov(),
    )
    assert metric.display == "1490,23 Wh"
    assert metric.quantity.unit == "Wh"


def test_a_metric_without_a_unit_cannot_be_built():
    with pytest.raises(Exception):
        make_metric(key="x", label="X", value=1.0, unit="", provenance=_prov())


def test_a_metric_of_a_non_finite_value_cannot_be_built():
    with pytest.raises(Exception):
        make_metric(
            key="x", label="X", value=float("inf"), unit="Wh", provenance=_prov()
        )


# -- derived percentages ------------------------------------------------------

def test_a_percentage_derived_from_a_ratio_is_marked_derived():
    ratio = make_metric(
        key="barrier_share",
        label="Bariyer payı",
        value=0.13215,
        unit="dimensionless",
        provenance=Provenance(source="MODEL"),
    )
    pct = percent_of_ratio(ratio, key="barrier_share_pct", label="Bariyer payı")
    assert pct.provenance.source == "DERIVED"


def test_a_derived_percentage_names_the_metric_it_came_from():
    ratio = make_metric(
        key="barrier_share",
        label="Bariyer payı",
        value=0.13215,
        unit="dimensionless",
        provenance=Provenance(source="MODEL"),
    )
    pct = percent_of_ratio(ratio, key="barrier_share_pct", label="Bariyer payı")
    assert "barrier_share" in (pct.provenance.note or "")


def test_the_percentage_value_is_computed_by_k1_not_the_model():
    ratio = make_metric(
        key="barrier_share",
        label="Bariyer payı",
        value=0.13215,
        unit="dimensionless",
        provenance=Provenance(source="MODEL"),
    )
    pct = percent_of_ratio(ratio, key="barrier_share_pct", label="Bariyer payı")
    assert pct.display == "13,2 %"


# -- envelope -----------------------------------------------------------------

def test_an_envelope_exposes_its_registry_and_warnings():
    metric = make_metric(
        key="total_distance_km",
        label="Toplam mesafe",
        value=3.0996,
        unit="km",
        provenance=_prov(),
    )
    envelope = AnalysisEnvelope(
        capability="C-SUMMARY",
        request_echo={"kind": "current_plan"},
        ok=True,
        payload={"anything": 1},
        numeric_registry=[metric],
        warnings=[
            EnvelopeWarning(
                code="CELL_COST_BREAKDOWN_WEIGHT_MISMATCH",
                severity="caution",
                message="...",
            )
        ],
        provenance_summary=[_prov()],
        backend_version="0.3.0",
    )
    assert envelope.numeric_registry[0].display == "3,100 km"
    assert envelope.warnings[0].suppressible is False


def test_a_warning_cannot_be_marked_suppressible():
    # N-14: no level, and no caller, may hide one.
    with pytest.raises(Exception):
        EnvelopeWarning(
            code="X", severity="caution", message="m", suppressible=True
        )


def test_display_strings_of_a_registry_are_unique_enough_to_mask():
    # Two metrics may legitimately share a display; masking is by string, and
    # N-2 only requires that SOME metric backs the number.
    a = make_metric(key="a", label="A", value=4, unit="dimensionless",
                    provenance=_prov(), precision=0)
    b = make_metric(key="b", label="B", value=4, unit="dimensionless",
                    provenance=_prov(), precision=0)
    assert a.display == b.display == "4"


def test_a_count_must_be_registered_with_zero_precision():
    loose = make_metric(key="n", label="N", value=4, unit="dimensionless",
                        provenance=_prov())
    assert loose.display == "4,00000"
    tight = make_metric(key="n", label="N", value=4, unit="dimensionless",
                        provenance=_prov(), precision=0)
    assert tight.display == "4"
