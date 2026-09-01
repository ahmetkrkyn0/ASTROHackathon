"""The bounded tool-calling loop behind POST /api/ai/chat.

Not an agent. The model gets a fixed number of rounds, two read-only tools,
and a budget it cannot see. A tool it did not earn is reported back to it as
a typed error rather than executed, so a model that asks for route planning
gets told no and carries on with the evidence it has.

The loop terminates on the first turn that produces prose, on the round cap,
or on a provider failure. It never terminates by giving up quietly: a turn
that produced no answer says so.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Optional

from .ai_contract import (
    AiMissionSnapshot,
    ChatMessage,
    ChatResponse,
    EvidenceItem,
    LimitationItem,
    ToolUsage,
)
from .ai_evidence import display_pedigree
from .ai_prompt import system_prompt
from .ai_provider import AiProviderError, ProviderReply
from .ai_tools import (
    MAX_TOOL_ROUNDS,
    AiToolError,
    ToolBudget,
    ToolRegistry,
    tool_specifications,
)

_NO_ANSWER = (
    "I could not complete an answer within the tool budget for this question. "
    "Try asking about one thing at a time."
)


def _mission_context(snapshot: AiMissionSnapshot, grids: Mapping[str, Any]) -> str:
    """What the assistant knows before it calls anything.

    The current plan is already sanitized by the time it arrives. Grid facts
    come from the loaded metadata rather than from any design document,
    because the two disagree and only one of them describes what is running.
    """
    metadata = grids.get("metadata") or {}
    shape = metadata.get("shape") or []
    resolution_m = metadata.get("resolution_m")

    context: dict[str, Any] = {
        "rover_id": snapshot.roverId,
        "weights": snapshot.weights.model_dump(),
        "start": snapshot.start,
        "goal": snapshot.goal,
        "grid": {
            "rows": int(shape[0]) if len(shape) > 0 else None,
            "cols": int(shape[1]) if len(shape) > 1 else None,
            "resolution_m": resolution_m,
        },
    }
    if len(shape) > 0 and resolution_m:
        context["grid"]["span_km"] = round(
            (int(shape[0]) * float(resolution_m)) / 1000.0, 4
        )
    if metadata.get("layer_validity"):
        context["layer_validity"] = dict(metadata["layer_validity"])
    if snapshot.focusedCell is not None:
        context["focused_cell"] = snapshot.focusedCell.model_dump()
    if snapshot.currentPlan is not None:
        context["current_plan"] = snapshot.currentPlan
    else:
        context["current_plan"] = None
        context["note"] = "The operator has not run a plan yet."

    return (
        "Current mission context (deterministic LunaPath values):\n"
        + json.dumps(context, ensure_ascii=False, indent=2)
    )


def _evidence_for(
    tool_name: str, result: Mapping[str, Any]
) -> list[EvidenceItem]:
    """One entry per tool result, carrying provenance when the data has it."""
    if tool_name == "inspect_cell":
        provenance = result.get("provenance") or {}
        return [
            EvidenceItem(
                source="cell-telemetry",
                label=f"Cell ({result.get('row')}, {result.get('col')})",
                rawValidity=provenance.get("rawValidity"),
                displayPedigree=provenance.get("displayPedigree"),
            )
        ]
    if tool_name == "compare_mission_profiles":
        count = len(result.get("profiles") or [])
        return [
            EvidenceItem(
                source="profile-comparison",
                label=f"{count} mission profiles, solved side by side",
                # The comparison derives from the same grids the route used;
                # the per-cell provenance travels with cell evidence instead.
                rawValidity=None,
                displayPedigree=None,
            )
        ]
    return []


def _plan_evidence(snapshot: AiMissionSnapshot, grids: Mapping[str, Any]):
    if snapshot.currentPlan is None:
        return []
    metadata = grids.get("metadata") or {}
    from .ai_evidence import weakest_validity

    raw = weakest_validity((metadata.get("layer_validity") or {}).values())
    return [
        EvidenceItem(
            source="current-plan",
            label="The route currently on screen",
            rawValidity=raw,
            displayPedigree=display_pedigree(raw),
        )
    ]


def run_chat(
    provider: Any,
    grids: Mapping[str, Any],
    snapshot: AiMissionSnapshot,
    messages: list[ChatMessage],
) -> ChatResponse:
    """One question, answered within a fixed tool budget."""
    budget = ToolBudget()
    registry = ToolRegistry(grids=grids, snapshot=snapshot, budget=budget)

    conversation: list[dict[str, Any]] = [
        {"role": "user", "content": _mission_context(snapshot, grids)}
    ]
    for message in messages:
        conversation.append({"role": message.role, "content": message.content})

    evidence: list[EvidenceItem] = list(_plan_evidence(snapshot, grids))
    limitations: list[LimitationItem] = []
    seen_limitations: set[str] = set()
    answer: Optional[str] = None

    tools = tool_specifications()

    for _ in range(MAX_TOOL_ROUNDS):
        reply: ProviderReply = provider.respond(
            system=system_prompt(), messages=conversation, tools=tools
        )

        if not reply.tool_calls:
            answer = (reply.text or "").strip() or None
            break

        for name, arguments, call_id in reply.tool_calls:
            # Echo the request so the model's own turn stays in the
            # transcript it sees next round.
            conversation.append(
                {
                    "type": "function_call",
                    "name": name,
                    "arguments": json.dumps(arguments, ensure_ascii=False),
                    "call_id": call_id,
                }
            )
            try:
                result = registry.call(name, arguments)
            except AiToolError as exc:
                # Refused, not executed. The model is told why so it can
                # answer from what it already has.
                output = exc.as_tool_output()
            else:
                output = result
                evidence.extend(_evidence_for(name, result))
                for item in result.get("limitations") or []:
                    if item["code"] not in seen_limitations:
                        seen_limitations.add(item["code"])
                        limitations.append(LimitationItem(**item))

            conversation.append(
                {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": json.dumps(output, ensure_ascii=False, default=str),
                }
            )

    return ChatResponse(
        answer=answer or _NO_ANSWER,
        evidence=evidence,
        limitations=limitations,
        toolUsage=ToolUsage(
            comparisonUsed=budget.compare_calls > 0,
            readCalls=budget.read_calls,
        ),
    )
