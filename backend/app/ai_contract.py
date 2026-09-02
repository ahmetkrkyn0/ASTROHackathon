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
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)

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


# ── explanation level (AI-02 section 7) ──────────────────────────────────────

# L2 is the visual default, but the operator must choose once per session
# before the first normal turn: AI-02 forbids inferring the level from
# behaviour, so the choice has to be made rather than guessed.
ExplanationLevel = Literal["L1", "L2", "L3"]
DEFAULT_EXPLANATION_LEVEL: ExplanationLevel = "L2"


# ── K2 router output (AI-02 section 6) ───────────────────────────────────────

# Only capabilities the audited backend actually has. C-CONTRAST and
# C-RECOURSE are described by the generic contract but are not available
# here, so the router cannot even name them.
# Full and partial capabilities are both routable; only the two genuinely
# absent ones are excluded, so the router cannot name what does not exist.
RoutableCapability = Literal[
    "C-SUMMARY",
    "C-POINT",
    "C-COMPARE",
    "C-DECOMPOSE",
    "C-BINDING",
    "C-INFEASIBLE",
    "C-SENSITIVITY",
]

# Closed vocabulary. A free-text rationale would be somewhere the router
# could hide prose or a number, which is exactly what K2 must not produce.
RationaleKey = Literal[
    "cell_question",
    "profile_tradeoff",
    "plan_summary",
    "constraint_margin",
    "provenance_question",
    "already_in_context",
    "ambiguous_target",
    "out_of_scope",
    "mutating_request",
]

MissingContext = Literal["start", "goal", "cell", "rover", "plan"]
RefusalCode = Literal["OUT_OF_SCOPE", "MUTATING_REQUEST", "UNSUPPORTED_CAPABILITY"]


class RouterInvoke(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["invoke"]
    capability: RoutableCapability
    params: dict[str, Any] = Field(default_factory=dict)
    rationale_key: RationaleKey


class RouterClarify(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["clarify"]
    missing: list[MissingContext] = Field(min_length=1, max_length=4)


class RouterRefuse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["refuse"]
    code: RefusalCode


class RouterAnswerFromContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["answer_from_context"]


RouterOutput = Annotated[
    Union[RouterInvoke, RouterClarify, RouterRefuse, RouterAnswerFromContext],
    Field(discriminator="action"),
]

ROUTER_ADAPTER: TypeAdapter = TypeAdapter(RouterOutput)


def parse_router_output(payload: Any):
    """Validate a router reply. Raises on anything the contract forbids."""
    return ROUTER_ADAPTER.validate_python(payload)


def router_json_schema() -> dict[str, Any]:
    """Schema handed to the provider, generated from the validator itself.

    Generated rather than hand-written so the two can never drift.
    """
    return ROUTER_ADAPTER.json_schema()


class RouterFailure(BaseModel):
    """The router could not produce a valid decision within its attempts."""

    code: Literal["E-SCHEMA"] = "E-SCHEMA"
    detail: Optional[str] = None

    @property
    def action(self) -> str:
        return "failure"


# ── wire types for warnings and grounding ────────────────────────────────────

class WarningItem(BaseModel):
    """Mandatory and never hidden.

    Distinct from LimitationItem by meaning, not by severity: a warning says
    the evidence's validity, grounding or constraints are materially affected,
    and N-14 forbids any explanation level from dropping one. A limitation
    says what the feature cannot establish. Nothing appears in both.
    """

    code: str
    severity: Literal["info", "caution", "critical"]
    message: str
    suppressible: Literal[False] = False


GroundingStatus = Literal["verified", "blocked", "not_applicable"]


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=MAX_MESSAGES)
    mission: AiMissionSnapshot
    # Additive: an older client that omits it still gets the default level.
    explanationLevel: ExplanationLevel = DEFAULT_EXPLANATION_LEVEL

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
    # Informational scope notes. Never carries a mandatory warning; the two
    # channels are disjoint by meaning and an item is never in both.
    limitations: list[LimitationItem] = Field(default_factory=list)
    # Mandatory, rendered independently of the prose, identical at every level.
    warnings: list[WarningItem] = Field(default_factory=list)
    toolUsage: ToolUsage = Field(default_factory=ToolUsage)
    errorCode: Optional[str] = None
    groundingStatus: GroundingStatus = "not_applicable"
    explanationLevel: ExplanationLevel = DEFAULT_EXPLANATION_LEVEL
