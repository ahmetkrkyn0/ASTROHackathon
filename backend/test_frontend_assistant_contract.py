"""Source assertions over the assistant feature module.

The frontend now has vitest and eslint (package.json), which it did not when
this file was written. What it still has is no jsdom and no testing-library,
so nothing can render a component -- and none of `npm run typecheck`, `lint`,
`test` or `build` can say whether a chip is offered before a route exists or
whether a local marker reaches the wire.

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

def test_the_planning_identity_is_a_title_only():
    assert "title: 'Görev Rehberi'" in CHAT_PANEL


def test_the_analysis_identity_keeps_its_title():
    assert "title: 'Analiz Asistanı'" in CHAT_PANEL


def test_neither_identity_carries_a_kicker():
    """Two lines under the title, both removed in the UI review.

    The kicker restated the mode the title already names, and the read-only
    badge restated a guarantee that is structural rather than advisory: there
    is no route-planning tool in ai_tools.py, so no model output can move the
    route whether or not a badge says so. The claim itself did not go -- it is
    the header's title attribute now -- but the phrase did.

    Asserted as absence, so putting either back is a failing test rather than a
    quiet drift back to the old header.
    """
    for gone in ("Planlama desteği", "Görev karar desteği", "Salt okunur"):
        assert gone not in CHAT_PANEL, gone


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

def test_a_finished_route_does_not_open_the_assistant():
    """A solved route is not a request to be talked to.

    It used to open the window on the plan transition. That lands a panel over
    the map at the moment the operator wants to look at the route they just
    got, and it arrives unasked. The launcher is one click away.
    """
    assert "hadPlanRef" not in USE_ASSISTANT
    assert "if (hasPlan && !had) open()" not in USE_ASSISTANT


def test_an_ask_from_another_feature_still_opens_the_assistant():
    """The other auto-open path stays, because that one IS a request.

    A feature only publishes an ask because the operator pressed something --
    the report's "Ask the assistant" button is the only caller. Removing the
    plan-transition open must not take this with it, or that button would fill
    a composer nobody can see.
    """
    assert "openedAskRef" in USE_ASSISTANT
    assert "openedAskRef.current = ask.id" in USE_ASSISTANT


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


# ── unread: any completed turn that lands unseen ─────────────────────────────

def _send_body() -> str:
    return CHAT_PANEL[
        CHAT_PANEL.index("const send = useCallback(") : CHAT_PANEL.index(
            "const startNewChat = useCallback("
        )
    ]


def _catch_branch() -> str:
    body = _send_body()
    return body[body.index("} catch (err) {") : body.index("} finally {")]


def _finally_branch() -> str:
    """The finally block only -- not the useCallback dependency array below it.

    `onAnswerWhileHidden` legitimately appears in the deps, so the slice has to
    stop at the end of the block or the assertion measures the wrong thing.
    """
    body = _send_body()
    tail = body[body.index("} finally {") :]
    return tail[: tail.index("      }\n")]


def test_a_transport_failure_marks_unread():
    """The defect this pass closes.

    A failure that lands while the window is minimized used to append its turn
    and say nothing, so the operator sat waiting for a reply that had already
    come back.
    """
    assert "noteLanded()" in _catch_branch()


def test_a_landed_answer_still_marks_unread():
    body = _send_body()
    success = body[body.index("try {") : body.index("} catch (err) {")]
    assert "noteLanded()" in success


def test_unread_is_never_marked_from_finally():
    """`finally` also runs on the abort and stale-generation paths.

    Those return before appending anything, so marking there would point a dot
    at a turn that does not exist.
    """
    tail = _finally_branch()
    assert "noteLanded" not in tail
    assert "onAnswerWhileHidden" not in tail


@pytest.mark.parametrize("branch", ["success", "failure"])
def test_the_turn_is_appended_before_it_is_announced(branch):
    """No appended turn -> no unread. Appended while hidden -> unread."""
    body = _send_body()
    if branch == "success":
        section = body[body.index("try {") : body.index("} catch (err) {")]
    else:
        section = _catch_branch()
    guard = section.index("generationRef.current !== generation) return")
    append = section.index("setTurns((current) => [")
    announce = section.index("noteLanded()")
    assert guard < append < announce


def test_unread_is_only_marked_when_the_window_is_hidden():
    body = _send_body()
    helper = body[body.index("const noteLanded = () => {") :]
    helper = helper[: helper.index("}")]
    assert "if (!visibleRef.current) onAnswerWhileHidden?.()" in helper


def test_opening_the_assistant_still_clears_the_dot():
    assert "setIsOpen(true)" in USE_ASSISTANT
    open_body = USE_ASSISTANT[
        USE_ASSISTANT.index("const open = useCallback(") : USE_ASSISTANT.index(
            "const close = useCallback("
        )
    ]
    assert "setUnread(false)" in open_body


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
    # Matched by shape rather than by the template's exact text. shell.css names
    # `.chat-window` and `.is-open` as the published pair, and says so in its own
    # comment; a third class beside them -- the drag state -- leaves that
    # contract intact. Pinning the whole template made a legitimate addition
    # read as a broken contract, which is the opposite of what this asserts.
    window_class = re.search(r"className=\{`chat-window ([^`]*)`\}", INDEX)
    assert window_class, "the chat window's className template was not found"
    assert "isOpen ? 'is-open' : ''" in window_class.group(1)
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
