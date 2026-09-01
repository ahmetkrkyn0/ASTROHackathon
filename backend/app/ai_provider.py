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

    def __init__(
        self,
        script: Optional[Sequence[ProviderReply]] = None,
        structured_script: Optional[Sequence[str]] = None,
    ) -> None:
        self._script = list(script or [])
        self._structured_script = list(structured_script or [])
        self.calls: list[dict[str, Any]] = []
        self.structured_calls: list[dict[str, Any]] = []

    def respond_structured(
        self,
        *,
        system: str,
        messages: Sequence[Mapping[str, Any]],
        schema_name: str,
        json_schema: Mapping[str, Any],
        max_output_tokens: int = 400,
    ) -> str:
        self.structured_calls.append(
            {"system": system, "messages": list(messages), "schema": schema_name}
        )
        if self._structured_script:
            return self._structured_script.pop(0)
        return '{"action": "answer_from_context"}'

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
        # Cached after one probe so an unsupported parameter costs at
        # most a single extra call per provider instance.
        self._structured_supported: Optional[bool] = None

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

    def respond_structured(
        self,
        *,
        system: str,
        messages: Sequence[Mapping[str, Any]],
        schema_name: str,
        json_schema: Mapping[str, Any],
        max_output_tokens: int = 400,
    ) -> str:
        """Ask for a JSON reply constrained by *json_schema*.

        Returns the raw JSON text; parsing and validation belong to the
        caller, which validates with Pydantic whether or not the provider
        honoured the schema. Structured Outputs is an optimization here, not
        the guarantee -- so a provider that rejects the parameter degrades to
        an unconstrained call rather than failing the turn.

        The parameter shape was read off the installed SDK
        (openai==3.6.0): responses.create takes `text`, and its format config
        is flat -- type/name/schema/strict together, not nested under a
        `json_schema` key. There is no `response_format` on this API.
        """
        client = self._get_client()
        kwargs: dict[str, Any] = dict(
            model=self.model,
            instructions=system,
            input=list(messages),
            reasoning={"effort": DEFAULT_REASONING_EFFORT},
            max_output_tokens=max_output_tokens,
        )
        if self._structured_supported is not False:
            kwargs["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": dict(json_schema),
                    "strict": False,
                }
            }

        try:
            response = client.responses.create(**kwargs)
        except TypeError:
            self._structured_supported = False
            kwargs.pop("text", None)
            response = client.responses.create(**kwargs)
        except Exception as exc:
            if _looks_unsupported(exc) and "text" in kwargs:
                self._structured_supported = False
                kwargs.pop("text", None)
                try:
                    response = client.responses.create(**kwargs)
                except Exception as retry_exc:
                    raise AiProviderError(
                        "AI_UPSTREAM_ERROR",
                        f"The language model call failed: {retry_exc}",
                    ) from retry_exc
            else:
                raise AiProviderError(
                    "AI_UPSTREAM_ERROR", f"The language model call failed: {exc}"
                ) from exc

        return (_parse_response(response).text or "").strip()

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


def _looks_unsupported(exc: Exception) -> bool:
    """Whether an upstream error reads as "that parameter is not allowed"."""
    text = str(exc).lower()
    return any(
        marker in text
        for marker in ("unsupported", "unknown parameter", "unrecognized", "invalid_request")
    )
