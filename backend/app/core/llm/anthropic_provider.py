"""Anthropic implementation of the neutral :class:`Provider` protocol.

Maps the neutral message/event types in ``base.py`` to and from the
Anthropic Messages streaming API. The orchestrator already requests
tool schemas in the ``anthropic`` dialect (``tools/schema.py``), so
this file only adapts names, message shapes, and stream events.

Tool calling is forced single (``disable_parallel_tool_use``) so the
orchestrator can apply its one-tool-per-turn inline-confirmation model
without juggling partially-resolved tool batches — same posture as the
OpenAI provider.

``Done.stop_reason`` carries Anthropic's native values (``end_turn``,
``tool_use``, ``max_tokens``) verbatim; nothing upstream branches on
the vocabulary — it is informational SSE payload only.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from app.core.llm.base import (
    Done,
    LLMConfigError,
    ProviderEvent,
    ProviderMessage,
    Role,
    TextBlock,
    TextDelta,
    ToolResultBlock,
    ToolUse,
    ToolUseBlock,
    Usage,
)


class AnthropicProvider:
    """Streams completions from Anthropic, speaking neutral types."""

    def __init__(self, *, api_key: str) -> None:
        if not api_key:
            raise LLMConfigError("Anthropic provider requires ANTHROPIC_API_KEY")
        # Imported lazily so the dependency is only needed when the
        # provider is actually instantiated (keeps test/import light).
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=api_key)

    async def complete(
        self,
        *,
        system: str,
        messages: list[ProviderMessage],
        tools: list[dict],
        model: str,
        max_tokens: int,
    ) -> AsyncIterator[ProviderEvent]:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": _to_anthropic_messages(messages),
            "max_tokens": max_tokens,
            "stream": True,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = [_sanitize_tool_schema(t) for t in tools]
            kwargs["tool_choice"] = {"type": "auto", "disable_parallel_tool_use": True}

        # content-block index -> {"id": str, "name": str, "args": str}
        pending: dict[int, dict[str, str]] = {}
        input_tokens = 0
        output_tokens = 0
        stop_reason = "end_turn"

        stream = await self._client.messages.create(**kwargs)
        async for event in stream:
            kind = event.type

            if kind == "message_start":
                input_tokens = event.message.usage.input_tokens

            elif kind == "content_block_start":
                block = event.content_block
                if block.type == "tool_use":
                    pending[event.index] = {"id": block.id, "name": block.name, "args": ""}

            elif kind == "content_block_delta":
                delta = event.delta
                if delta.type == "text_delta":
                    yield TextDelta(text=delta.text)
                elif delta.type == "input_json_delta" and event.index in pending:
                    pending[event.index]["args"] += delta.partial_json

            elif kind == "message_delta":
                if event.delta.stop_reason:
                    stop_reason = event.delta.stop_reason
                if event.usage is not None:
                    output_tokens = event.usage.output_tokens

        yield Usage(input_tokens=input_tokens, output_tokens=output_tokens)

        for slot in pending.values():
            yield ToolUse(
                id=slot["id"],
                name=_from_anthropic_name(slot["name"]),
                input=_parse_args(slot["args"]),
            )

        yield Done(stop_reason=stop_reason)


# Anthropic restricts tool names to ``^[a-zA-Z0-9_-]{1,128}$``, but our
# tool registry namespaces with a dot (``patients.search_patients``).
# Tool / module names are snake_case with no hyphens, so ``.`` <-> ``-``
# is a lossless bijection confined to this provider — same trick as the
# OpenAI provider.
def _to_anthropic_name(qualified: str) -> str:
    return qualified.replace(".", "-")


def _from_anthropic_name(safe: str) -> str:
    return safe.replace("-", ".")


def _sanitize_tool_schema(tool: dict[str, Any]) -> dict[str, Any]:
    return {**tool, "name": _to_anthropic_name(tool["name"])}


def _parse_args(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _to_anthropic_messages(messages: list[ProviderMessage]) -> list[dict[str, Any]]:
    """Serialize neutral messages into Anthropic's wire shape.

    Tool results become ``tool_result`` blocks on a ``user`` message.
    Adjacent same-role messages are merged into one turn (a tool-result
    turn followed by a real user turn must arrive as a single ``user``
    message), so content is always a block list, never a bare string.
    """
    out: list[dict[str, Any]] = []

    def _push(role: str, blocks: list[dict[str, Any]]) -> None:
        if not blocks:
            return
        if out and out[-1]["role"] == role:
            out[-1]["content"].extend(blocks)
        else:
            out.append({"role": role, "content": blocks})

    for msg in messages:
        if msg.role is Role.USER:
            text = _join_text(msg)
            if text:
                _push("user", [{"type": "text", "text": text}])

        elif msg.role is Role.ASSISTANT:
            blocks: list[dict[str, Any]] = []
            text = _join_text(msg)
            if text:
                blocks.append({"type": "text", "text": text})
            for block in msg.content:
                if isinstance(block, ToolUseBlock):
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": block.id,
                            "name": _to_anthropic_name(block.name),
                            "input": block.input,
                        }
                    )
            _push("assistant", blocks)

        elif msg.role is Role.TOOL:
            results: list[dict[str, Any]] = []
            for block in msg.content:
                if isinstance(block, ToolResultBlock):
                    wire: dict[str, Any] = {
                        "type": "tool_result",
                        "tool_use_id": block.tool_call_id,
                        "content": _stringify(block.content),
                    }
                    if block.is_error:
                        wire["is_error"] = True
                    results.append(wire)
            _push("user", results)

    return out


def _join_text(msg: ProviderMessage) -> str:
    return "".join(b.text for b in msg.content if isinstance(b, TextBlock))


def _stringify(content: Any) -> str:
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False, default=str)
