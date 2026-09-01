"""The fixed K2 -> K3 -> K1 -> K4 -> K5 pipeline behind POST /api/ai/chat.

Not an agent loop. The model is asked exactly two questions per turn -- what
should run, and how to say the result -- and everything between and after
those two points is deterministic. That shape is what makes the guarantees
checkable: the router cannot answer, the gate cannot interpret, the
verbalizer cannot compute, and the validator cannot rewrite.

Two defenses stack rather than replace each other. Sanitization decides what
the model may see; grounding decides what the operator may be told. A field
stripped upstream can never be quoted, and a number invented downstream can
never survive.

Contract: docs/ai/LunaPath_AI_Chatbot_Scope_v0.3.md sections 12, 14 and 15.
"""

from __future__ import annotations

import json
import time
from typing import Any, Mapping, Optional

from .ai_analysis import (
    AnalysisEnvelope,
    EnvelopeWarning,
    Provenance,
    cell_registry,
    compare_registry,
    constraint_warnings,
    plan_registry,
)
from .ai_contract import (
    AiMissionSnapshot,
    ChatMessage,
    ChatResponse,
    EvidenceItem,
    ExplanationLevel,
    LimitationItem,
    RouterAnswerFromContext,
    RouterClarify,
    RouterFailure,
    RouterInvoke,
    RouterRefuse,
    ToolUsage,
    WarningItem,
)
from .ai_evidence import display_pedigree, weakest_validity
from .ai_grounding import deterministic_fallback, validate_draft, whitelist_tokens
from .ai_prompt import VERBALIZER_PROMPT
from .ai_router import gate, gate_message, refusal_code, route, tool_error_code
from .ai_tools import AiToolError, AnalysisProvider, ToolBudget

# Informational scope notes. Disjoint from warnings by meaning: these say what
# the feature cannot establish, never that evidence validity is compromised.
_CAPABILITY_LIMITATIONS: dict[str, tuple[tuple[str, str], ...]] = {
    "C-COMPARE": (
        (
            "DISCRETE_SENSITIVITY_ONLY",
            "Duyarlılık, önceden tanımlı dört profil üzerinden ayrıktır; tek "
            "değişkenli bir perturbasyon değildir.",
        ),
        (
            "NO_ROUTE_WIDE_DECOMPOSITION",
            "Rota geneli maliyet ayrışması bu sürümde mevcut değil.",
        ),
    ),
    "C-POINT": (
        (
            "CELL_SCOPED_DECOMPOSITION",
            "Maliyet ayrışması yalnızca tek hücre için geçerlidir.",
        ),
    ),
    "C-SUMMARY": (
        (
            "NO_CAUSAL_ATTRIBUTION",
            "Bu özet, geometrik sapmaların kesin nedenini belirleyemez.",
        ),
    ),
}

_CLARIFY_TEXT: dict[str, str] = {
    "start": "başlangıç noktası",
    "goal": "hedef noktası",
    "cell": "haritada seçili bir hücre",
    "rover": "seçili bir rover",
    "plan": "hesaplanmış bir rota",
}


def _provenance_for(grids: Mapping[str, Any]) -> Provenance:
    """The weakest input rung across the loaded layers.

    Computed on the raw four-rung ladder; the three-level badge is derived
    from it for display and never replaces it.
    """
    metadata = grids.get("metadata") or {}
    validity = metadata.get("layer_validity") or {}
    weakest = weakest_validity(validity.values())
    return Provenance(source=weakest or "SYNTHETIC")


def _build_envelope(
    capability: str,
    params: Mapping[str, Any],
    provider: AnalysisProvider,
    grids: Mapping[str, Any],
) -> AnalysisEnvelope:
    """K1: run the deterministic analysis and register what may be said."""
    started = time.perf_counter()
    provenance = _provenance_for(grids)
    payload = provider.invoke(capability, params)

    warnings: list[EnvelopeWarning] = []
    if capability == "C-SUMMARY":
        plan = payload.get("plan") or {}
        registry = plan_registry(plan, provenance)
    elif capability == "C-POINT":
        registry = cell_registry(payload, provenance)
        for item in payload.get("limitations") or []:
            # The weight mismatch invalidates the decomposition as an
            # explanation of this plan, so it is a validity fact, not a
            # scope note -- it belongs in warnings.
            warnings.append(
                EnvelopeWarning(
                    code=item["code"], severity="caution", message=item["message"]
                )
            )
    else:
        registry = compare_registry(payload, provenance)
        warnings.extend(constraint_warnings(payload))

    return AnalysisEnvelope(
        capability=capability,
        request_echo=dict(params),
        ok=True,
        payload=dict(payload),
        numeric_registry=registry,
        warnings=warnings,
        provenance_summary=[provenance],
        compute_ms=round((time.perf_counter() - started) * 1000.0, 1),
        backend_version=str((grids.get("metadata") or {}).get("cost_model") or ""),
    )


def _verbalizer_input(
    envelope: AnalysisEnvelope, question: str, level: ExplanationLevel
) -> list[dict[str, Any]]:
    """What K4 sees: registered metrics and nothing raw."""
    briefing = {
        "capability": envelope.capability,
        "explanation_level": level,
        "metrics": [
            {
                "key": metric.key,
                "label": metric.label,
                "display": metric.display,
                "provenance": metric.provenance.source,
            }
            for metric in envelope.numeric_registry
        ],
        "warnings": [
            {"code": w.code, "severity": w.severity, "message": w.message}
            for w in envelope.warnings
        ],
        "provenance_summary": [p.source for p in envelope.provenance_summary],
    }
    return [
        {
            "role": "user",
            "content": (
                "Doğrulanmış analiz kaydı:\n"
                + json.dumps(briefing, ensure_ascii=False, indent=2)
            ),
        },
        {"role": "user", "content": question},
    ]


def _evidence_for(envelope: AnalysisEnvelope) -> list[EvidenceItem]:
    source = {
        "C-SUMMARY": "current-plan",
        "C-POINT": "cell-telemetry",
        "C-COMPARE": "profile-comparison",
    }.get(envelope.capability, envelope.capability)
    label = {
        "C-SUMMARY": "Ekrandaki mevcut rota",
        "C-POINT": "Seçili hücre telemetrisi",
        "C-COMPARE": "Dört görev profili, yan yana",
    }.get(envelope.capability, envelope.capability)
    raw = envelope.provenance_summary[0].source if envelope.provenance_summary else None
    return [
        EvidenceItem(
            source=source,
            label=label,
            rawValidity=raw,
            displayPedigree=display_pedigree(raw),
        )
    ]


def _limitations_for(capability: str) -> list[LimitationItem]:
    return [
        LimitationItem(code=code, message=message)
        for code, message in _CAPABILITY_LIMITATIONS.get(capability, ())
    ]


def _refusal(
    code: str,
    budget: ToolBudget,
    level: ExplanationLevel,
    message: Optional[str] = None,
) -> ChatResponse:
    """A deterministic Turkish refusal. Never generated by a model."""
    return ChatResponse(
        answer=message or gate_message(code),
        evidence=[],
        limitations=[],
        warnings=[],
        toolUsage=ToolUsage(
            comparisonUsed=budget.compare_calls > 0, readCalls=budget.read_calls
        ),
        errorCode=code,
        groundingStatus="not_applicable",
        explanationLevel=level,
    )


def run_chat(
    provider: Any,
    grids: Mapping[str, Any],
    snapshot: AiMissionSnapshot,
    messages: list[ChatMessage],
    explanation_level: ExplanationLevel = "L2",
) -> ChatResponse:
    """One question, routed, gated, analysed, verbalized and validated."""
    budget = ToolBudget()
    analysis = AnalysisProvider(grids=dict(grids), snapshot=snapshot, budget=budget)
    question = messages[-1].content

    # ── K2 ───────────────────────────────────────────────────────────────
    decision = route(
        provider,
        question=question,
        history=messages[:-1],
        capabilities=analysis.get_capabilities(),
        context=analysis.get_context(),
    )

    if isinstance(decision, RouterFailure):
        return _refusal("E-SCHEMA", budget, explanation_level)
    if isinstance(decision, RouterRefuse):
        return _refusal(refusal_code(decision.code), budget, explanation_level)
    if isinstance(decision, RouterClarify):
        wanted = ", ".join(_CLARIFY_TEXT.get(m, m) for m in decision.missing)
        return _refusal(
            "E-CONTEXT",
            budget,
            explanation_level,
            message=f"Bunu cevaplayabilmem için şu eksik: {wanted}.",
        )

    # ── K3 ───────────────────────────────────────────────────────────────
    verdict = gate(decision, provider=analysis, budget=budget)
    if not verdict.ok:
        return _refusal(verdict.code or "E-SCHEMA", budget, explanation_level,
                        verdict.message_tr)

    if isinstance(decision, RouterAnswerFromContext):
        capability, params = "C-SUMMARY", {}
    else:
        assert isinstance(decision, RouterInvoke)
        capability, params = decision.capability, dict(decision.params)

    # ── K1 ───────────────────────────────────────────────────────────────
    try:
        envelope = _build_envelope(capability, params, analysis, grids)
    except AiToolError as exc:
        return _refusal(tool_error_code(exc), budget, explanation_level)

    # ── K4 ───────────────────────────────────────────────────────────────
    reply = provider.respond(
        VERBALIZER_PROMPT,
        _verbalizer_input(envelope, question, explanation_level),
        [],
    )
    draft = (reply.text or "").strip()

    # ── K5 ───────────────────────────────────────────────────────────────
    tokens = whitelist_tokens(
        envelope,
        rover_names=_rover_names(),
        profile_names=_profile_names(),
    )
    ground = validate_draft(draft, envelope, tokens) if draft else None

    if ground is not None and ground.ok:
        answer, status, error_code = draft, "verified", None
    else:
        # Blocked, not repaired. A silent correction hides the failure.
        answer = deterministic_fallback(envelope)
        status, error_code = "blocked", "E-GROUNDING"

    warnings = [
        WarningItem(code=w.code, severity=w.severity, message=w.message)
        for w in envelope.warnings
    ]
    if error_code == "E-GROUNDING":
        warnings.append(
            WarningItem(
                code="E-GROUNDING",
                severity="caution",
                message=(
                    "Modelin yanıtı doğrulanamadı; yalnızca kayıtlı analiz "
                    "değerleri gösteriliyor."
                ),
            )
        )

    return ChatResponse(
        answer=answer,
        evidence=_evidence_for(envelope),
        limitations=_limitations_for(capability),
        warnings=warnings,
        toolUsage=ToolUsage(
            comparisonUsed=budget.compare_calls > 0, readCalls=budget.read_calls
        ),
        errorCode=error_code,
        groundingStatus=status,
        explanationLevel=explanation_level,
    )


def _rover_names() -> list[str]:
    from .constants import rover_catalog

    names: list[str] = []
    for entry in rover_catalog():
        names.extend(str(entry[key]) for key in ("id", "name") if entry.get(key))
    return names


def _profile_names() -> list[str]:
    from .scenarios import MISSION_PROFILES

    names: list[str] = []
    for profile_id, profile in MISSION_PROFILES.items():
        names.append(profile_id)
        if profile.get("name"):
            names.append(str(profile["name"]))
    return names
