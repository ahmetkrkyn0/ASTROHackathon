"""The mission report's verdict, decided here and read by two shells.

The frontend's report screen owns the same decision in
`frontend/src/features/mission-report/report.ts`, and the two must agree: an
operator who is told GO on screen and NO-GO by the assistant has learned
nothing except not to trust either. `test_report_verdict.py` pins them against
a shared fixture, the way `test_review_fixes` pins `cost_vec` against
`cost_engine`.

Two things are deliberately NOT here.

The reason texts carry no digits. The frontend interpolates its numbers with
`toFixed(1)`, which produces dot decimals that `ai_grounding` blocks by
construction -- so the assistant's copy of a reason states the finding and
nothing else, and the numbers travel separately as registered metrics
(`ai_analysis.verdict_registry`). Every text below is checked digit-free by a
test, because a number that creeps in here blocks a whole answer downstream.

And no AI type is imported. This module answers "what is the disposition of
this route", which the ROS 2 shell and a future `/api/report` want as much as
the assistant does, so it stays framework-free like `cost_engine`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Optional

Verdict = Literal["GO", "GO-WITH-RISK", "NO-GO"]
Severity = Literal["blocking", "warning", "clear"]

# Below this the battery reserve is close enough to matter to the verdict.
# Mirror of BATTERY_WATCH_PCT in report.ts; the parity test extracts that
# literal and compares it to this one.
BATTERY_WATCH_PCT = 30.0


@dataclass(frozen=True)
class VerdictReason:
    """One finding behind a verdict.

    `text` is what the operator reads and carries no quantity. `metric_keys`
    names the registered metrics that quantify it, so the AI layer can register
    exactly what a fired reason needs and nothing more.
    """

    code: str
    severity: Severity
    text: str
    metric_keys: tuple[str, ...]


@dataclass(frozen=True)
class VerdictResult:
    verdict: Verdict
    #: Worst finding first, blocking before warning.
    reasons: tuple[VerdictReason, ...]


# The wording avoids "sürüş" on purpose. ai_grounding's N-8 rule exempts
# "tanımlı kısıt", and "tanımlı sürüş kısıtları" puts a word between the two,
# missing the exemption. No trigger fires either way, but the shorter phrasing
# is safe on both legs rather than one.
_REASONS: dict[str, VerdictReason] = {
    reason.code: reason
    for reason in (
        VerdictReason(
            code="STRANDED",
            severity="blocking",
            text=(
                "Rover, rota tamamlanmadan enerjisiz kaldı; rota bu hâliyle "
                "tamamlanamıyor."
            ),
            metric_keys=("stranded_at_step",),
        ),
        VerdictReason(
            code="EXECUTION_TRUNCATED",
            severity="blocking",
            text="Yürütme kesildi: planlanan düğümlerin tamamı sürülebilir değil.",
            metric_keys=("execution_planned_nodes", "execution_executable_nodes"),
        ),
        VerdictReason(
            code="SHADOW_LIMIT_EXCEEDED",
            severity="blocking",
            text=(
                "Kesintisiz gölge süresi, rover için tanımlı gölge limitini aştı."
            ),
            metric_keys=("max_continuous_shadow", "shadow_limit"),
        ),
        VerdictReason(
            code="CRITICAL_STEPS",
            severity="blocking",
            text="Risk modeli en az bir adımı CRITICAL seviyesinde işaretledi.",
            metric_keys=("critical_steps_count",),
        ),
        VerdictReason(
            code="HIGH_RISK_STEPS",
            severity="warning",
            text="Risk modeli en az bir adımı HIGH ya da üzeri seviyede işaretledi.",
            metric_keys=("high_or_above_steps_count",),
        ),
        VerdictReason(
            code="BATTERY_WATCH",
            severity="warning",
            text="Batarya, raporun izleme eşiğinin altına indi.",
            metric_keys=("min_battery", "battery_watch_threshold"),
        ),
        VerdictReason(
            code="PEAK_POWER_EXCEEDED",
            severity="warning",
            text="En az bir adımda tepe güç bütçesi aşıldı.",
            metric_keys=("peak_power_exceeded_steps",),
        ),
        VerdictReason(
            code="RECHARGES_REQUIRED",
            severity="warning",
            text="Rota, şarj molası gerektiriyor.",
            metric_keys=("total_recharges",),
        ),
        VerdictReason(
            code="NO_VIOLATION",
            severity="clear",
            text="Tanımlı kısıtların hiçbiri ihlal edilmedi.",
            metric_keys=(),
        ),
    )
}

# Stating the verdict is not stating that the route is safe, and the wording
# has to keep those apart -- N-8 blocks the second claim outright. Each of
# these matches the "tanımlı kısıt" exemption and trips no trigger.
_VERDICT_SENTENCES: dict[str, str] = {
    "GO": "Karar: GO — tanımlı kısıtların hiçbiri ihlal edilmedi.",
    "GO-WITH-RISK": (
        "Karar: GO-WITH-RISK — rota, tanımlı kısıtlardan engelleyici olanları "
        "ihlal etmiyor, ancak kayıtlı risk bulguları var."
    ),
    "NO-GO": (
        "Karar: NO-GO — rota, tanımlı kısıtlardan en az birini ihlal ediyor "
        "ya da tamamlanamıyor."
    ),
}


def reason(code: str) -> VerdictReason:
    """The reason with this code. KeyError is the right failure: a caller
    naming a code that does not exist is a bug, not a missing finding."""
    return _REASONS[code]


def reason_codes() -> tuple[str, ...]:
    """Every code this module can produce, in table order."""
    return tuple(_REASONS)


def verdict_sentence(verdict: str) -> str:
    return _VERDICT_SENTENCES[verdict]


def _number(value: Any) -> Optional[float]:
    """A finite real number, or None.

    `bool` is excluded before `int`, because in Python True is 1 and a boolean
    flag arriving where a count is expected would read as "one step".
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    return None


def _is_positive(value: Any) -> bool:
    """`value > 0` the way JavaScript answers it for an absent field.

    `undefined > 0` is false in JS and `None > 0` raises in Python, so an
    absent count must be read as "no finding" rather than as an error.
    """
    number = _number(value)
    return number is not None and number > 0


def decide_verdict(
    summary: Mapping[str, Any],
    execution: Optional[Mapping[str, Any]] = None,
) -> VerdictResult:
    """The route's disposition, from the simulation summary alone.

    NO-GO is reserved for things the rover cannot survive or did not finish:
    a stranded run, a truncated execution, a breached shadow limit, or a step
    the risk model called CRITICAL. Everything softer degrades to GO-WITH-RISK
    rather than to NO-GO, because a report that says NO-GO for a 28% battery
    trough teaches the operator to ignore it.

    Absence is never a finding. An omitted count, an omitted battery figure and
    an omitted `execution` block all mean "nothing to report", which is what
    the frontend's `undefined` comparisons already do.
    """
    blocking: list[VerdictReason] = []
    warnings: list[VerdictReason] = []
    steps = execution or {}

    # `stranded` and `shadow_limit_exceeded` are read for truthiness, not as
    # numbers: shadow_limit_exceeded is boolean|null and null means the rover
    # has no shadow limit, which must not block.
    if summary.get("stranded"):
        blocking.append(_REASONS["STRANDED"])
    if steps.get("truncated"):
        blocking.append(_REASONS["EXECUTION_TRUNCATED"])
    if summary.get("shadow_limit_exceeded"):
        blocking.append(_REASONS["SHADOW_LIMIT_EXCEEDED"])
    if _is_positive(summary.get("critical_steps_count")):
        blocking.append(_REASONS["CRITICAL_STEPS"])

    if _is_positive(summary.get("high_or_above_steps_count")):
        warnings.append(_REASONS["HIGH_RISK_STEPS"])
    battery = _number(summary.get("min_battery_pct"))
    if battery is not None and battery < BATTERY_WATCH_PCT:
        warnings.append(_REASONS["BATTERY_WATCH"])
    if _is_positive(summary.get("peak_power_exceeded_steps")):
        warnings.append(_REASONS["PEAK_POWER_EXCEEDED"])
    if _is_positive(summary.get("total_recharges")):
        warnings.append(_REASONS["RECHARGES_REQUIRED"])

    if blocking:
        return VerdictResult("NO-GO", tuple(blocking + warnings))
    if warnings:
        return VerdictResult("GO-WITH-RISK", tuple(warnings))
    return VerdictResult("GO", (_REASONS["NO_VIOLATION"],))


def _quantity_value(value: Any) -> Any:
    """The number inside a `{value, unit}` pair, or the value itself."""
    if isinstance(value, Mapping):
        return value.get("value")
    return value


def decide_verdict_from_snapshot(plan: Mapping[str, Any]) -> VerdictResult:
    """The same decision, from the flattened shape the assistant receives.

    `sanitizePlanForAi` sends unit-tagged quantities and bare counts rather
    than the raw `/api/plan` summary, so the field names differ. Normalising
    here rather than duplicating the eight conditions is the whole point: there
    is one decision and two readers.
    """
    execution = plan.get("execution")
    steps = execution if isinstance(execution, Mapping) else {}
    summary = {
        # The wire carries `stranded` at the top level and again inside
        # execution; either is the same flag.
        "stranded": plan.get("stranded") or steps.get("stranded"),
        "shadow_limit_exceeded": plan.get("shadow_limit_exceeded"),
        "critical_steps_count": plan.get("critical_steps_count"),
        "high_or_above_steps_count": plan.get("high_or_above_steps_count"),
        "min_battery_pct": _quantity_value(plan.get("min_battery")),
        "peak_power_exceeded_steps": plan.get("peak_power_exceeded_steps"),
        "total_recharges": plan.get("total_recharges"),
    }
    return decide_verdict(summary, steps)
