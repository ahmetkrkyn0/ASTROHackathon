"""The language-model boundary: one method, two implementations.

Small on purpose. No agent framework, no plugin system, no chain -- the model
understands the question, picks one of two approved tools, and phrases
evidence LunaPath already computed. That is the whole job, and a framework
would add indirection between the model's output and the checks that make it
safe.

The OpenAI path uses the Responses API with custom functions ONLY. No
built-in tool -- web search, file search, code interpreter, computer use,
shell -- is enabled, so the model's entire reach is the two schemas handed to
it by ai_tools.tool_specifications().

Configuration is read from the process environment. Nothing in this module is
importable by the frontend, and the key is never logged, echoed in an error,
or included in a repr.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

DEFAULT_MODEL = "gpt-5.6-terra"

# LunaPath performs the technical computation. The model's work is intent,
# tool selection and phrasing, none of which needs deep reasoning -- and the
# question already costs ~21 s when a comparison runs.
DEFAULT_REASONING_EFFORT = "low"
DEFAULT_MAX_OUTPUT_TOKENS = 1200

# (name, arguments, call_id)
ToolCall = tuple[str, dict[str, Any], str]


class AiProviderError(Exception):
    """Configuration or upstream failure, with a code the endpoint maps."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class ProviderReply:
    """One model turn: either prose, or a request to run tools."""

    text: Optional[str]
    tool_calls: list[ToolCall] = field(default_factory=list)


class StubProvider:
    """Deterministic offline provider for tests and explicit local checks.

    Never a silent fallback: reaching it requires LUNAPATH_AI_PROVIDER=stub.
    Without that, a missing key raises rather than producing an answer that
    looks real.
    """

    model = "stub"

    def __init__(self, script: Optional[Sequence[ProviderReply]] = None) -> None:
        self._script = list(script or [])
        self.calls: list[dict[str, Any]] = []

    def respond(
        self,
        system: str,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
    ) -> ProviderReply:
        self.calls.append(
            {"system": system, "messages": list(messages), "tools": list(tools)}
        )
        if self._script:
            return self._script.pop(0)
        return ProviderReply(
            text=(
                "Stub provider: no language model was called. "
                "Set LUNAPATH_AI_PROVIDER=openai with a key for real answers."
            ),
            tool_calls=[],
        )


class OpenAiProvider:
    """OpenAI Responses API with custom function calling."""

    def __init__(self, api_key: str, model: str) -> None:
        # Held privately so it cannot surface through repr or a traceback.
        self._api_key = api_key
        self.model = model
        self._client: Any = None

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"OpenAiProvider(model={self.model!r})"

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise AiProviderError(
                    "AI_NOT_CONFIGURED",
                    "The openai package is not installed on the server.",
                ) from exc
            self._client = OpenAI(api_key=self._api_key)
        return self._client

    def respond(
        self,
        system: str,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
    ) -> ProviderReply:
        client = self._get_client()
        try:
            response = client.responses.create(
                model=self.model,
                instructions=system,
                input=list(messages),
                tools=list(tools),
                # Custom functions only. Parallel calls are off so the budget
                # is spent one decision at a time.
                parallel_tool_calls=False,
                reasoning={"effort": DEFAULT_REASONING_EFFORT},
                max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
            )
        except AiProviderError:
            raise
        except Exception as exc:
            # The message may carry request context but never the key, which
            # the SDK does not echo.
            raise AiProviderError(
                "AI_UPSTREAM_ERROR", f"The language model call failed: {exc}"
            ) from exc

        return _parse_response(response)


def _parse_response(response: Any) -> ProviderReply:
    """Pull text and function calls out of a Responses API result."""
    import json

    tool_calls: list[ToolCall] = []
    text_parts: list[str] = []

    for item in getattr(response, "output", None) or []:
        item_type = getattr(item, "type", None)
        if item_type == "function_call":
            raw_arguments = getattr(item, "arguments", None) or "{}"
            try:
                arguments = json.loads(raw_arguments)
            except (TypeError, ValueError):
                # A malformed argument object is not a reason to guess; the
                # registry will reject it and tell the model why.
                arguments = {}
            if not isinstance(arguments, dict):
                arguments = {}
            tool_calls.append(
                (
                    getattr(item, "name", "") or "",
                    arguments,
                    getattr(item, "call_id", None) or getattr(item, "id", "") or "",
                )
            )
        elif item_type == "message":
            for chunk in getattr(item, "content", None) or []:
                chunk_text = getattr(chunk, "text", None)
                if chunk_text:
                    text_parts.append(chunk_text)

    if not text_parts:
        direct = getattr(response, "output_text", None)
        if direct:
            text_parts.append(direct)

    return ProviderReply(
        text="\n".join(text_parts).strip() or None, tool_calls=tool_calls
    )


def resolve_provider(env: Optional[Mapping[str, str]] = None):
    """Build the configured provider, or explain why it cannot be built."""
    environment = os.environ if env is None else env
    name = (environment.get("LUNAPATH_AI_PROVIDER") or "openai").strip().lower()

    if name == "stub":
        return StubProvider()

    if name != "openai":
        raise AiProviderError(
            "AI_PROVIDER_UNKNOWN",
            f"Unknown AI provider {name!r}. Set LUNAPATH_AI_PROVIDER to "
            "'openai' or 'stub'.",
        )

    api_key = (environment.get("LUNAPATH_OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise AiProviderError(
            "AI_NOT_CONFIGURED",
            "LUNAPATH_OPENAI_API_KEY is not set on the server, so the "
            "decision-support assistant is unavailable.",
        )

    model = (environment.get("LUNAPATH_OPENAI_MODEL") or "").strip() or DEFAULT_MODEL
    return OpenAiProvider(api_key=api_key, model=model)
