"""The verdict decision, and its parity with the frontend's copy.

The mission report decides GO / GO-WITH-RISK / NO-GO on screen, and
`app.report` decides it again so the assistant can state it. Two copies is the
same arrangement as `cost_engine` and `cost_vec`, and it needs the same
protection: an operator told GO by the report and NO-GO by the assistant has
learned only not to trust either.

The behavioural half is driven by a fixture both suites read, so a condition
cannot be changed on one side alone. The source half pins the two things a
fixture cannot see -- that neither side holds a reason code the other does not,
and that the shared threshold is one number in two files.

The third group is about the AI layer without importing it: every reason text
must be digit-free, because `ai_grounding` blocks a whole answer over one
unregistered digit and these strings are handed to the verbalizer verbatim.
"""

from __future__ import annotations

import json
import os
import re

import pytest

from app.report import (
    BATTERY_WATCH_PCT,
    decide_verdict,
    decide_verdict_from_snapshot,
    reason,
    reason_codes,
    verdict_sentence,
)

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "frontend", "src"))
_REPORT_FEATURE = os.path.join(_SRC, "features", "mission-report")


def _read(*parts: str) -> str:
    with open(os.path.join(*parts), encoding="utf-8") as handle:
        return handle.read()


REPORT_TS = _read(_REPORT_FEATURE, "report.ts")
MODAL_TSX = _read(_REPORT_FEATURE, "MissionReportModal.tsx")
FIXTURE = json.loads(_read(_REPORT_FEATURE, "verdictCases.json"))

# Every quantity a reason may cite has to be a key some registry can produce.
# Kept here rather than imported from ai_analysis so this module stays free of
# the AI stack; test_ai_verdict_summary asserts the other direction.
_REGISTERABLE_KEYS = {
    "stranded_at_step",
    "execution_planned_nodes",
    "execution_executable_nodes",
    "max_continuous_shadow",
    "shadow_limit",
    "critical_steps_count",
    "high_or_above_steps_count",
    "min_battery",
    "battery_watch_threshold",
    "peak_power_exceeded_steps",
    "total_recharges",
}


def _case_summary(case: dict) -> dict:
    """The merged summary, with `absent` keys removed rather than nulled.

    Removing is the point: JS `undefined < 30` is false and Python `None < 30`
    raises, so "the field is missing" is its own case. Writing null would not
    express it -- JS coerces null to 0 and the comparison would be true.
    """
    summary = dict(FIXTURE["base"])
    summary.update(case["summary"])
    for key in case["absent"]:
        summary.pop(key, None)
    return summary


# ── parity, from the shared fixture ──────────────────────────────────────────


@pytest.mark.parametrize("case", FIXTURE["cases"], ids=lambda case: case["name"])
def test_the_verdict_matches_the_frontend_fixture(case):
    result = decide_verdict(_case_summary(case), case["execution"])
    assert result.verdict == case["verdict"]
    assert [one.code for one in result.reasons] == case["codes"]


def test_the_fixture_exercises_every_reason_code():
    """A code no case produces is a condition nothing compares across the two
    implementations."""
    seen = {code for case in FIXTURE["cases"] for code in case["codes"]}
    assert seen == set(reason_codes())


def test_blocking_reasons_come_before_warnings():
    case = next(
        one
        for one in FIXTURE["cases"]
        if one["name"] == "every finding at once, blocking before warning"
    )
    result = decide_verdict(_case_summary(case), case["execution"])
    severities = [reason(code).severity for code in [one.code for one in result.reasons]]
    assert severities == ["blocking"] * 4 + ["warning"] * 4


# ── the flat wire shape reaches the same decision ────────────────────────────


def test_the_snapshot_adapter_reads_a_unit_tagged_battery():
    plan = {"min_battery": {"value": 22.4, "unit": "%"}}
    result = decide_verdict_from_snapshot(plan)
    assert result.verdict == "GO-WITH-RISK"
    assert [one.code for one in result.reasons] == ["BATTERY_WATCH"]


def test_the_snapshot_adapter_blocks_on_a_truncated_execution():
    plan = {
        "min_battery": {"value": 80.0, "unit": "%"},
        "execution": {"truncated": True, "planned_nodes": 90, "executable_nodes": 40},
    }
    assert decide_verdict_from_snapshot(plan).verdict == "NO-GO"


def test_an_empty_snapshot_is_a_GO_rather_than_an_error():
    """Every field is optional on the wire; absence must not raise."""
    result = decide_verdict_from_snapshot({})
    assert result.verdict == "GO"
    assert [one.code for one in result.reasons] == ["NO_VIOLATION"]


def test_the_snapshot_adapter_finds_stranded_inside_execution():
    """The wire carries the flag twice; either spelling is the same finding."""
    plan = {"execution": {"stranded": True, "truncated": False}}
    assert decide_verdict_from_snapshot(plan).verdict == "NO-GO"


# ── the two copies name the same findings ────────────────────────────────────


def test_neither_side_holds_a_reason_code_the_other_does_not():
    block = re.search(
        r"export const VERDICT_REASON_CODES = \[(.*?)\] as const",
        REPORT_TS,
        re.S,
    )
    assert block, "VERDICT_REASON_CODES not found in report.ts"
    frontend = set(re.findall(r"'([A-Z_]+)'", block.group(1)))
    assert frontend == set(reason_codes())


def test_the_battery_threshold_is_one_number_in_two_files():
    found = re.search(r"export const BATTERY_WATCH_PCT = ([\d.]+)", REPORT_TS)
    assert found, "BATTERY_WATCH_PCT not exported from report.ts"
    assert float(found.group(1)) == BATTERY_WATCH_PCT


def test_the_report_modal_no_longer_keeps_its_own_copy_of_the_threshold():
    """It had one, and a second copy of a policy number drifts silently."""
    assert "BATTERY_RESERVE_PCT" not in MODAL_TSX
    assert "BATTERY_WATCH_PCT" in MODAL_TSX


# ── properties the AI layer depends on ───────────────────────────────────────


@pytest.mark.parametrize("code", reason_codes())
def test_no_reason_text_carries_a_digit(code):
    """K5 masks registered display strings and then blocks on any digit left.
    A number written into a reason blocks the whole answer, silently."""
    assert re.search(r"\d", reason(code).text) is None


@pytest.mark.parametrize("code", reason_codes())
def test_every_cited_metric_key_is_registerable(code):
    for key in reason(code).metric_keys:
        assert key in _REGISTERABLE_KEYS


@pytest.mark.parametrize("verdict", ["GO", "GO-WITH-RISK", "NO-GO"])
def test_no_verdict_sentence_carries_a_digit(verdict):
    assert re.search(r"\d", verdict_sentence(verdict)) is None


@pytest.mark.parametrize("verdict", ["GO", "GO-WITH-RISK", "NO-GO"])
def test_every_verdict_sentence_names_its_own_label(verdict):
    assert verdict in verdict_sentence(verdict)


@pytest.mark.parametrize("verdict", ["GO", "GO-WITH-RISK", "NO-GO"])
def test_no_verdict_sentence_claims_safety(verdict):
    """N-8's own vocabulary, checked here so a rewording cannot reintroduce the
    claim without this test failing before ai_grounding ever sees it."""
    sentence = verdict_sentence(verdict).lower()
    for word in ("güvenli", "risksiz", "tehlikesiz", "kesinlikle", "garanti"):
        assert word not in sentence
