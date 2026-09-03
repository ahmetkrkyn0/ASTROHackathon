"""Source assertions over the assistant feature module.

The frontend has no test runner -- no vitest, no jest, no config, and eslint is
not installed either (see docs/frontend/FRONTEND_MODULAR_SHELL.md §13). The
only executable checks are `npm run typecheck` and `npm run build`, and neither
of them can say whether a chip is offered before a route exists or whether a
local marker reaches the wire.

So these are source assertions, and they are deliberately narrow: each one
pins a decision that has a reason, not a spelling. They run in the backend
suite because that is where a runner already exists, and because several of
them are really assertions about the CONTRACT between the two sides -- the
message roles the server accepts, the evidence source it emits.

They are a stand-in for real component tests, not a substitute. Anything about
behaviour over time is beyond what reading a file can prove.
"""

from __future__ import annotations

import os
import re

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "frontend", "src"))
_ASSISTANT = os.path.join(_SRC, "features", "assistant")


def _read(*parts: str) -> str:
    with open(os.path.join(*parts), encoding="utf-8") as handle:
        return handle.read()


CHAT_PANEL = _read(_ASSISTANT, "ChatPanel.tsx")
USE_ASSISTANT = _read(_ASSISTANT, "useAssistant.ts")
INDEX = _read(_ASSISTANT, "index.tsx")
STYLES = _read(_ASSISTANT, "assistant.css")
APP = _read(_SRC, "App.tsx")
SHELL_CSS = _read(_SRC, "shell", "shell.css")
REGISTRY = _read(_SRC, "features", "registry.ts")


# ── the mode is derived, never chosen ────────────────────────────────────────

def test_the_mode_comes_from_the_mission_and_not_from_a_control():
    assert "export type AssistantMode = 'planning' | 'analysis'" in USE_ASSISTANT
    assert "missionSnapshot.currentPlan === null ? 'planning' : 'analysis'" in USE_ASSISTANT
    # No toggle, no setter, no persisted preference: a control here would let
    # the panel offer route analysis with no route.
    assert "setMode" not in USE_ASSISTANT
    assert "setMode" not in CHAT_PANEL
    assert "AssistantMode" in CHAT_PANEL


def test_the_panel_receives_the_mode_rather_than_deriving_a_second_one():
    assert "mode={mode}" in INDEX
    assert "mode: AssistantMode" in CHAT_PANEL


# ── before a route: the guide ────────────────────────────────────────────────

def test_the_planning_identity_is_the_mission_guide():
    assert "title: 'Görev Rehberi'" in CHAT_PANEL
    assert "kicker: 'Planlama desteği'" in CHAT_PANEL
    # The read-only badge is not mode-specific and stays where it was.
    assert "Salt okunur" in CHAT_PANEL


def test_the_analysis_identity_is_unchanged():
    assert "title: 'Analiz Asistanı'" in CHAT_PANEL
    assert "kicker: 'Görev karar desteği'" in CHAT_PANEL


def test_the_planning_empty_state_names_what_the_guide_covers():
    intro = CHAT_PANEL[
        CHAT_PANEL.index("planning: {") : CHAT_PANEL.index("analysis: {")
    ]
    for topic in ("Rover seçimi", "rota öncelikleri", "katmanları", "2D/3D"):
        assert topic in intro, topic


@pytest.mark.parametrize(
    "label",
    [
        "Bu ekranı nasıl kullanırım?",
        "Rover seçimlerini açıkla",
        "Route priorities ne işe yarıyor?",
        "Katmanları açıkla",
        "Start ve Goal nasıl seçilir?",
        "2D ve 3D farkı nedir?",
    ],
)
def test_each_planning_suggestion_is_offered(label):
    assert f"label: '{label}'" in CHAT_PANEL


def test_no_analysis_chip_is_offered_before_a_route_exists():
    """The planning list is closed, and the analysis branch is unreachable.

    The cell chip is gated on a placed endpoint rather than on a plan, so
    without the early return it could appear with no route at all.
    """
    block = CHAT_PANEL[
        CHAT_PANEL.index("const PLANNING_SUGGESTIONS") : CHAT_PANEL.index(
            "function conversationForWire"
        )
    ]
    for analysis_only in ("Rotayı özetle", "Hedef hücreyi", "karşılaştır", "Riskleri"):
        assert analysis_only not in block, analysis_only
    assert "if (mode === 'planning') return [...PLANNING_SUGGESTIONS]" in CHAT_PANEL


# ── after a route: the analysis chips ────────────────────────────────────────

@pytest.mark.parametrize(
    "label",
    [
        "Rotayı özetle",
        "Enerji ve bataryayı açıkla",
        "Riskleri açıkla",
        "Görev profillerini karşılaştır",
    ],
)
def test_each_analysis_suggestion_is_offered(label):
    assert f"label: '{label}'" in CHAT_PANEL


def test_the_cell_chip_still_names_the_cell_it_means():
    assert "mission.goal ? 'Hedef hücreyi analiz et'" in CHAT_PANEL


def test_the_expensive_chip_is_still_gated_on_the_endpoints():
    assert "mission.start !== null && mission.goal !== null" in CHAT_PANEL


# ── the transition ───────────────────────────────────────────────────────────

def test_a_finished_route_opens_the_assistant():
    assert "const hadPlanRef = useRef(missionSnapshot.currentPlan !== null)" in USE_ASSISTANT
    # The transition, not the level: planResult is cleared by five different
    # actions, and a level-triggered effect would reopen on every one of them.
    assert "if (hasPlan && !had) open()" in USE_ASSISTANT


def test_opening_the_assistant_sends_nothing():
    """The operator gets access to the analysis, not an answer they did not ask for."""
    for forbidden in ("postAiChat", "send(", "fetch("):
        assert forbidden not in USE_ASSISTANT, forbidden


def test_the_mode_change_does_not_submit_a_request():
    effect = CHAT_PANEL[
        CHAT_PANEL.index("if (modeRef.current === mode) return") : CHAT_PANEL.index(
            "const handleScroll"
        )
    ]
    assert "send(" not in effect
    assert "postAiChat" not in effect


def test_the_transition_marks_the_transcript_without_clearing_it():
    assert "'Rota oluşturuldu · Analiz modu'" in CHAT_PANEL
    assert "role: 'divider'" in CHAT_PANEL
    # setTurns([]) belongs to "Yeni sohbet" and to nothing else.
    assert CHAT_PANEL.count("setTurns([])") == 1
    assert "const startNewChat" in CHAT_PANEL


def test_an_empty_transcript_gets_no_divider():
    assert "if (current.length === 0) return current" in CHAT_PANEL


def test_new_chat_and_minimize_remain_different_controls():
    assert "className=\"chat-new\"" in CHAT_PANEL
    assert "className=\"chat-minimize\"" in CHAT_PANEL
    assert "onClick={startNewChat}" in CHAT_PANEL
    assert "onClick={onMinimize}" in CHAT_PANEL


def test_escape_still_only_minimizes():
    assert "event.key !== 'Escape'" in USE_ASSISTANT
    assert "setTurns" not in USE_ASSISTANT


# ── what travels, and what does not ──────────────────────────────────────────

def test_the_wire_history_is_taken_from_the_filtered_conversation():
    assert "conversationForWire(history)" in CHAT_PANEL
    # The raw transcript is never mapped straight onto the wire any more.
    assert "history.map((turn) => ({ role: turn.role" not in CHAT_PANEL


def test_the_divider_is_local_and_resets_the_history():
    body = CHAT_PANEL[
        CHAT_PANEL.index("function conversationForWire") : CHAT_PANEL.index(
            "interface ChatPanelProps"
        )
    ]
    # Everything before the last divider is dropped: planning turns are not
    # history for an analysis question.
    assert "from = index + 1" in body
    assert "turn.role !== 'divider'" in body


def test_an_empty_turn_cannot_poison_the_conversation():
    """ChatMessage.content is min_length=1, so an empty turn 422s the request.

    A transport failure appends exactly such a turn. Replaying it made every
    LATER question in the same conversation fail until "Yeni sohbet".
    """
    body = CHAT_PANEL[
        CHAT_PANEL.index("function conversationForWire") : CHAT_PANEL.index(
            "interface ChatPanelProps"
        )
    ]
    assert "turn.content.trim().length > 0" in body


def test_the_server_message_roles_are_still_the_only_two_that_travel():
    from app.ai_contract import ChatMessage

    assert ChatMessage.model_fields["role"].annotation.__args__ == ("user", "assistant")
    assert "role: turn.role as 'user' | 'assistant'" in CHAT_PANEL


def test_the_guide_evidence_source_has_a_label():
    """The label the panel shows for a guide answer matches what K1 emits."""
    from app.ai_chat import _evidence_for
    from app.ai_analysis import AnalysisEnvelope

    envelope = AnalysisEnvelope(capability="C-GUIDE", ok=True)
    assert _evidence_for(envelope)[0].source == "planning-guide"
    assert "'planning-guide': 'Planlama rehberi'" in CHAT_PANEL


# ── the explanation level is still an explicit choice ────────────────────────

def test_nothing_is_sent_before_a_level_is_chosen():
    assert "if (!question || pending || !levelChosen) return" in CHAT_PANEL
    assert "canSend = levelChosen && !pending" in CHAT_PANEL
    assert "disabled={pending || !levelChosen}" in CHAT_PANEL


@pytest.mark.parametrize("label", ["Basit", "Mühendislik", "Teknik"])
def test_the_three_levels_survive(label):
    assert f"label: '{label}'" in CHAT_PANEL


# ── the published cross-file contracts ───────────────────────────────────────

def test_the_window_id_and_class_names_are_unchanged():
    assert "const CHAT_WINDOW_ID = 'analysis-assistant-window'" in INDEX
    assert "`chat-window ${isOpen ? 'is-open' : ''}`" in INDEX
    # shell.css moves the toast stack with a sibling selector keyed off both.
    assert ".chat-window.is-open ~ .toast-stack" in SHELL_CSS


def test_the_overlay_slot_still_precedes_the_toast_stack():
    """The general sibling combinator only looks forward."""
    assert APP.index("<GlobalOverlaySlot />") < APP.index('className="toast-stack"')


def test_the_assistant_is_still_mounted_through_the_registry():
    assert "slot: 'globalOverlay'" in REGISTRY
    assert "Component: Assistant" in REGISTRY


def test_no_assistant_state_moved_back_into_app():
    for leaked in ("ChatPanel", "useAssistant", "AssistantMode", "chatOpen"):
        assert leaked not in APP, leaked


def test_new_styling_uses_the_feature_prefix():
    assert ".lp-assistant-divider" in STYLES
    assert "lp-assistant-divider" in CHAT_PANEL


def test_the_feature_owns_its_own_files_only():
    """features -> mission/api/overlay is allowed; the reverse is not."""
    for source in (CHAT_PANEL, USE_ASSISTANT, INDEX):
        assert not re.search(r"from '\.\./\.\./App", source)
        assert not re.search(r"from '\.\./\.\./features/", source)
