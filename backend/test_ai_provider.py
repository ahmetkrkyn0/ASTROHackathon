"""The provider boundary, exercised without a network.

The stub exists so the tool loop, the sanitizers and the endpoint can all be
tested for real. It is selected explicitly and never inherited: a missing API
key is a configuration error, because answering anyway with a canned string
would be the assistant claiming a computation it never made.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import pytest

from app.ai_provider import (
    DEFAULT_MODEL,
    AiProviderError,
    ProviderReply,
    StubProvider,
    resolve_provider,
)


def test_the_default_model_is_the_locked_one():
    assert DEFAULT_MODEL == "gpt-5.6-terra"


def test_stub_is_selected_explicitly():
    provider = resolve_provider({"LUNAPATH_AI_PROVIDER": "stub"})
    assert isinstance(provider, StubProvider)


def test_openai_without_a_key_is_a_configuration_error_not_a_stub():
    # Silently degrading to canned text would make the assistant claim
    # deterministic evidence it never had.
    with pytest.raises(AiProviderError) as excinfo:
        resolve_provider({"LUNAPATH_AI_PROVIDER": "openai"})
    assert excinfo.value.code == "AI_NOT_CONFIGURED"


def test_openai_is_the_default_provider_when_unset():
    with pytest.raises(AiProviderError) as excinfo:
        resolve_provider({})
    assert excinfo.value.code == "AI_NOT_CONFIGURED"


def test_an_unknown_provider_name_is_refused():
    with pytest.raises(AiProviderError) as excinfo:
        resolve_provider({"LUNAPATH_AI_PROVIDER": "definitely-not-a-provider"})
    assert excinfo.value.code == "AI_PROVIDER_UNKNOWN"


def test_the_model_id_can_be_overridden_by_environment():
    provider = resolve_provider(
        {
            "LUNAPATH_AI_PROVIDER": "openai",
            "LUNAPATH_OPENAI_API_KEY": "test-key-not-real",
            "LUNAPATH_OPENAI_MODEL": "gpt-5.6-terra-mini",
        }
    )
    assert provider.model == "gpt-5.6-terra-mini"


def test_configuration_errors_do_not_echo_the_key():
    provider = resolve_provider(
        {
            "LUNAPATH_AI_PROVIDER": "openai",
            "LUNAPATH_OPENAI_API_KEY": "sk-secret-value-here",
        }
    )
    assert "sk-secret-value-here" not in repr(provider)


# ── the stub's scripted behaviours ───────────────────────────────────────────

def test_stub_answers_directly_by_default():
    reply = StubProvider().respond(system="", messages=[], tools=[])
    assert isinstance(reply, ProviderReply)
    assert reply.tool_calls == []
    assert reply.text


def test_stub_can_be_scripted_to_request_a_tool_then_answer():
    provider = StubProvider(
        script=[
            ProviderReply(text=None, tool_calls=[("inspect_cell", {"row": 5, "col": 5}, "c1")]),
            ProviderReply(text="The cell is cold.", tool_calls=[]),
        ]
    )
    first = provider.respond(system="", messages=[], tools=[])
    assert first.tool_calls[0][0] == "inspect_cell"
    second = provider.respond(system="", messages=[], tools=[])
    assert second.text == "The cell is cold."


def test_stub_records_what_it_was_asked():
    provider = StubProvider()
    provider.respond(system="RULES", messages=[{"role": "user", "content": "hi"}], tools=[])
    assert provider.calls[0]["system"] == "RULES"


# A schema the API refuses is a bug here, not a provider limitation. Reading it
# as "parameter unsupported" made the provider drop Structured Outputs and
# answer in prose, which surfaced as E-SCHEMA with nothing naming the cause.

def test_rejected_schema_is_not_mistaken_for_an_unsupported_parameter():
    from app.ai_provider import _looks_unsupported

    rejection = Exception(
        "Error code: 400 - {'error': {'message': \"Invalid schema for "
        "response_format 'router_output': schema must be a JSON Schema of "
        "'type: \\\"object\\\"', got 'type: \\\"None\\\"'.\", 'type': "
        "'invalid_request_error', 'code': 'invalid_json_schema'}}"
    )
    assert _looks_unsupported(rejection) is False


def test_a_genuinely_unsupported_parameter_still_degrades():
    from app.ai_provider import _looks_unsupported

    assert _looks_unsupported(Exception("Unknown parameter: 'text.format'."))
    assert _looks_unsupported(Exception("Unsupported parameter: 'text'."))
    assert _looks_unsupported(Exception("Unrecognized request argument: 'text'."))
