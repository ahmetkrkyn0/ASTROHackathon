"""Wire types for the decision-support chat layer.

The mission snapshot is a VALUE. The browser sends what the user has already
chosen -- start, goal, rover, weights, and the plan they already ran -- and
the chat layer reads it. There is no path from here back into mission state:
no setter crosses this boundary, and the tools that consume the snapshot take
their coordinates from it rather than from the model.

See docs/ai/LunaPath_AI_Chatbot_Scope_v0.3.md sections 5 and 7.
"""

from __future__ import annotations

import math
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# A conversation the user can plausibly have in one sitting. Beyond this the
# window is being used as storage, which this stateless slice does not offer.
MAX_MESSAGES = 12
MAX_MESSAGE_CHARS = 4000

# The planner validates weights to [0, 2] on /api/plan. /api/layers and
# /api/terrain do not validate them at all, so the AI layer performs its own
# check rather than trusting the backend to have done it.
WEIGHT_MIN = 0.0
WEIGHT_MAX = 2.0


class ChatMessage(BaseModel):
    """One turn of conversation.

    Only ``user`` and ``assistant`` are accepted. A client-supplied ``system``
    or ``developer`` turn would let the page rewrite the operating rules, and
    a ``tool`` turn would let it fabricate evidence that no tool produced.
    """

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class PlanWeightsIn(BaseModel):
    w_slope: float
    w_energy: float
    w_shadow: float
    w_thermal: float

    @field_validator("w_slope", "w_energy", "w_shadow", "w_thermal")
    @classmethod
    def _in_range(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("weight must be a finite number")
        if not WEIGHT_MIN <= v <= WEIGHT_MAX:
            raise ValueError(
                f"weight must be in [{WEIGHT_MIN}, {WEIGHT_MAX}], got {v}"
            )
        return v


class CellRef(BaseModel):
    row: int = Field(ge=0)
    col: int = Field(ge=0)


class AiMissionSnapshot(BaseModel):
    """What the assistant may read about the mission on screen.

    Deliberately not a mirror of the frontend's state: it holds values the
    assistant reasons over and nothing that could change what the user sees.
    """

    start: Optional[list[int]] = None
    goal: Optional[list[int]] = None
    roverId: str
    weights: PlanWeightsIn
    focusedCell: Optional[CellRef] = None
    # The already-sanitized plan evidence, or None when the user has not run
    # a plan yet. Sanitizing happens in ai_evidence before it gets here.
    currentPlan: Optional[dict[str, Any]] = None

    @field_validator("start", "goal")
    @classmethod
    def _pixel_pair(cls, v: Optional[list[int]]) -> Optional[list[int]]:
        if v is None:
            return None
        if len(v) != 2:
            raise ValueError("a grid endpoint is exactly [row, col]")
        for component in v:
            if isinstance(component, bool) or not isinstance(component, int):
                raise ValueError("grid indices are integers")
            if component < 0:
                raise ValueError("grid indices are non-negative")
        return list(v)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=MAX_MESSAGES)
    mission: AiMissionSnapshot

    @model_validator(mode="after")
    def _ends_with_a_question(self) -> "ChatRequest":
        if self.messages[-1].role != "user":
            raise ValueError("the last message must be the user's question")
        if not self.messages[-1].content.strip():
            raise ValueError("the user's question is empty")
        return self


class EvidenceItem(BaseModel):
    """One block of deterministic evidence behind an answer.

    ``rawValidity`` is the four-rung backend ladder and ``displayPedigree``
    the three-level badge the UI already renders. Both travel: the weakest
    input is computed on the raw ladder, and collapsing it early would lose
    the distinction between MODEL and DERIVED before that happens.
    """

    source: str
    label: str
    rawValidity: Optional[str] = None
    displayPedigree: Optional[str] = None


class LimitationItem(BaseModel):
    code: str
    message: str


class ToolUsage(BaseModel):
    comparisonUsed: bool = False
    readCalls: int = 0


class ChatResponse(BaseModel):
    answer: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    limitations: list[LimitationItem] = Field(default_factory=list)
    toolUsage: ToolUsage = Field(default_factory=ToolUsage)
