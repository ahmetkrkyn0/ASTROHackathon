"""Source assertions over the feature-to-assistant ask channel.

A separate file from `test_frontend_assistant_contract.py`, whose docstring
scopes it to the assistant module. This one is about the channel BETWEEN two
features, and the property it protects is a boundary: the mission report may
put a question in the assistant's composer and may not ask it.

The distinction is the whole point. The assistant is read-only over the mission
-- it cannot move the route -- and this channel must not become the way that
gets undone in reverse: a feature that could call `send` would be asking the
model on the operator's behalf, with no level chosen and no keystroke.

Same caveat as the sibling file: reading a file cannot prove behaviour over
time. These pin decisions that have a reason, not spellings.
"""

from __future__ import annotations

import os
import re

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "frontend", "src"))
_INTENT = os.path.join(_SRC, "intent")
_ASSISTANT = os.path.join(_SRC, "features", "assistant")
_REPORT = os.path.join(_SRC, "features", "mission-report")


def _read(*parts: str) -> str:
    with open(os.path.join(*parts), encoding="utf-8") as handle:
        return handle.read()


INTENT_TYPES = _read(_INTENT, "types.ts")
INTENT_CONTEXT = _read(_INTENT, "AssistantAskContext.ts")
INTENT_PROVIDER = _read(_INTENT, "AssistantAskProvider.tsx")
CHAT_PANEL = _read(_ASSISTANT, "ChatPanel.tsx")
USE_ASSISTANT = _read(_ASSISTANT, "useAssistant.ts")
REPORT_INDEX = _read(_REPORT, "index.tsx")
REPORT_MODAL = _read(_REPORT, "MissionReportModal.tsx")
REPORT_TS = _read(_REPORT, "report.ts")
APP = _read(_SRC, "App.tsx")

_INTENT_FILES = {
    "types.ts": INTENT_TYPES,
    "AssistantAskContext.ts": INTENT_CONTEXT,
    "AssistantAskProvider.tsx": INTENT_PROVIDER,
}


# ── the channel carries text, and only text ──────────────────────────────────


def test_the_ask_type_carries_a_question_and_a_closed_origin():
    assert "question: string" in INTENT_TYPES
    assert "export type AssistantAskOrigin = 'mission-report'" in INTENT_TYPES


@pytest.mark.parametrize("name", sorted(_INTENT_FILES))
def test_no_intent_file_can_reach_the_network(name):
    """The channel is a message, not a client. If it could fetch, a feature
    could ask the model directly and the panel's gates would be decoration."""
    source = _INTENT_FILES[name]
    for forbidden in ("postAiChat", "fetch(", "/api/", "XMLHttpRequest"):
        assert forbidden not in source, (name, forbidden)


@pytest.mark.parametrize("name", sorted(_INTENT_FILES))
def test_the_intent_folder_never_imports_a_feature(name):
    """`intent → features` would make this a service locator. The direction is
    features → intent, and only that."""
    assert "from '../features/" not in _INTENT_FILES[name], name


def test_the_channel_has_no_consume_or_clear():
    """One-way by construction: the consumer tracks what it applied, so no
    producer can replay, retract, or observe delivery."""
    assert "isFreshAsk" in INTENT_TYPES
    for writer in ("consume", "clearAsk", "setAsk(null)"):
        assert writer not in INTENT_CONTEXT, writer


def test_the_reader_and_the_writer_are_separate_hooks():
    """The MissionValue/MissionActions split, for the same reason: the reader
    gets a value, the writer gets a function, neither gets the other."""
    assert "export function useAssistantAsk(): AssistantAsk | null" in INTENT_CONTEXT
    assert "export function useAskAssistant(): RequestAsk" in INTENT_CONTEXT


# ── the assistant reads it and still cannot be made to send ──────────────────


def test_the_assistant_shell_only_reads_the_channel():
    assert "useAssistantAsk" in USE_ASSISTANT
    assert "useAskAssistant" not in USE_ASSISTANT
    for forbidden in ("send(", "postAiChat", "fetch(", "setTurns", "setMode"):
        assert forbidden not in USE_ASSISTANT, forbidden


def test_the_ask_effect_fills_the_composer_and_nothing_else():
    found = re.search(
        r"useEffect\(\(\) => \{\s*if \(!ask \|\| ask\.id === appliedAskIdRef.*?\}, \[ask\]\)",
        CHAT_PANEL,
        re.S,
    )
    assert found, "the ask effect was not found in ChatPanel"
    effect = found.group(0)
    assert "setDraft(ask.question)" in effect
    for forbidden in ("send(", "postAiChat", "setLevel", "setLevelChosen", "setPending"):
        assert forbidden not in effect, forbidden


def test_the_send_guard_is_still_in_place():
    """The operator picks a level and presses Gönder. A prefilled composer
    changes neither."""
    assert "if (!question || pending || !levelChosen) return" in CHAT_PANEL


def test_the_composer_is_still_disabled_until_a_level_is_chosen():
    assert "disabled={pending || !levelChosen}" in CHAT_PANEL


# ── the report suggests a question and never asks it ─────────────────────────


@pytest.mark.parametrize(
    "name,source",
    [
        ("index.tsx", REPORT_INDEX),
        ("MissionReportModal.tsx", REPORT_MODAL),
        ("report.ts", REPORT_TS),
    ],
)
def test_the_report_never_calls_the_ai(name, source):
    """It reads a plan already in mission state. If it fetched, every finished
    route would spend a model call nobody asked for."""
    for forbidden in ("postAiChat", "api/assistant", "/api/ai"):
        assert forbidden not in source, (name, forbidden)


def test_the_report_never_imports_the_assistant():
    """Features are imported from outside only through their index, and never
    by each other. The channel is what replaces the import."""
    assert "features/assistant" not in REPORT_INDEX
    assert "from '../../features/" not in REPORT_INDEX
    assert "useAskAssistant" in REPORT_INDEX


def test_the_report_closes_itself_when_it_asks():
    """It is registered after the assistant in the same globalOverlay slot, so
    registration order is paint order and a full-screen report would cover the
    panel the question just landed in."""
    found = re.search(
        r"const askAssistant = useCallback\(.*?\[close, requestAsk\],\s*\)",
        REPORT_INDEX,
        re.S,
    )
    assert found, "askAssistant was not found in the report's index"
    assert "close()" in found.group(0)
    assert "requestAsk(question, 'mission-report')" in found.group(0)


def test_the_question_is_a_fixed_string_per_verdict():
    for verdict in ("GO", "GO-WITH-RISK", "NO-GO"):
        assert re.search(
            rf"'?{re.escape(verdict)}'?:\s*\n?\s*'Görev raporundaki karar özetini açıkla",
            REPORT_TS,
        ), verdict


def test_the_question_names_the_verdict_it_asks_about():
    assert "bu rota neden NO-GO?" in REPORT_TS
    assert "GO-WITH-RISK kararının risk bulguları neler?" in REPORT_TS


# ── the shell wiring ─────────────────────────────────────────────────────────


def test_the_provider_is_mounted_in_the_shell():
    assert "<AssistantAskProvider>" in APP
    assert "</AssistantAskProvider>" in APP


def test_the_provider_wraps_the_slot_both_features_live_in():
    """Both the assistant and the report are globalOverlay features, so the
    provider has to be outside that slot or one of them throws."""
    opened = APP.index("<AssistantAskProvider>")
    closed = APP.index("</AssistantAskProvider>")
    slot = APP.index("<GlobalOverlaySlot />")
    assert opened < slot < closed


def test_the_toast_stack_still_follows_the_overlay_slot():
    """shell.css keys the toast stack off a sibling combinator; a provider
    inserted between them would break the offset silently."""
    assert APP.index("<GlobalOverlaySlot />") < APP.index('className="toast-stack"')


def test_no_assistant_state_moved_into_the_shell_with_the_provider():
    """The sibling file pins this for the assistant; repeated here because the
    provider is the kind of change that tempts someone to hoist more."""
    for forbidden in ("ChatPanel", "useAssistant", "AssistantMode", "chatOpen"):
        assert forbidden not in APP, forbidden
