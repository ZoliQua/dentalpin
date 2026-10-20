"""Ollama implementation of the neutral :class:`Provider` protocol.

Speaks a self-hosted Ollama server's OpenAI-compatible endpoint
(``<base>/v1/chat/completions``) through the ``openai`` SDK, so the wire
format — Chat Completions streaming, tool calling, usage chunks — is
identical to :class:`OpenAIProvider` and this subclass only sets the
endpoint. Tool dialect is ``"openai"``; dotted tool names map
``.`` <-> ``-`` exactly like the OpenAI provider.

Ollama needs no API key (the ``openai`` SDK refuses an empty one, so a
placeholder stands in); pointed at a host on the operator's network, every
prompt stays there. Tool calling only works on pulled models that support
it; the mandatory PHI redactor still runs upstream (the local-tier
relaxation from the #332 brief stays deferred). Token-budget accounting
reads the streamed usage chunks, so a server that omits them leaves
``monthly_token_limit`` unenforced and ``GET /metrics`` reading zero.

Being self-hosted, this is the one provider whose misconfiguration is a
*dropped connection* rather than a missing key: selection is not probed at
save time, so an unreachable ``OLLAMA_BASE_URL`` only surfaces on the first
chat turn. The adapter therefore translates the SDK's bare
``Connection error.`` into a message naming the setting.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.core.llm.base import LLMConfigError, ProviderEvent, ProviderMessage
from app.core.llm.openai_provider import OpenAIProvider

#: Ollama's default server root; the OpenAI-compatible API lives under
#: ``/v1``. Matches the ``OLLAMA_BASE_URL`` default in ``app.config``.
OLLAMA_DEFAULT_BASE_URL = "http://ollama:11434"

#: Ollama ignores the value, but the OpenAI SDK rejects an empty key.
OLLAMA_PLACEHOLDER_API_KEY = "ollama"


def _openai_compatible_url(base_url: str | None) -> str:
    """Normalize a server root (with or without a trailing ``/v1``)."""
    root = (base_url or "").strip().rstrip("/") or OLLAMA_DEFAULT_BASE_URL
    if root.endswith("/v1"):
        return f"{root}/"
    return f"{root}/v1/"


class OllamaProvider(OpenAIProvider):
    """Streams completions from a local Ollama server, speaking neutral types."""

    def __init__(self, *, base_url: str | None = None) -> None:
        self._endpoint_url = _openai_compatible_url(base_url)
        super().__init__(
            api_key=OLLAMA_PLACEHOLDER_API_KEY,
            base_url=self._endpoint_url,
        )

    async def complete(
        self,
        *,
        system: str,
        messages: list[ProviderMessage],
        tools: list[dict],
        model: str,
        max_tokens: int,
    ) -> AsyncIterator[ProviderEvent]:
        """Stream a completion, naming ``OLLAMA_BASE_URL`` when the host is unreachable.

        Wraps the inherited generator so a connection failure reports the
        endpoint and the setting to check, like every keyed provider names its
        missing key; chunks already yielded are passed through. The wrapper
        spans the whole iteration, and the SDK raises ``APIConnectionError``
        only before the first chunk, which is where an unreachable
        ``OLLAMA_BASE_URL`` surfaces. A stalled server is the timeout subclass,
        reported apart from an unreachable host.
        """
        from openai import APIConnectionError, APITimeoutError

        try:
            async for event in super().complete(
                system=system,
                messages=messages,
                tools=tools,
                model=model,
                max_tokens=max_tokens,
            ):
                yield event
        except APITimeoutError as exc:
            raise LLMConfigError(
                f"Ollama provider timed out on {self._endpoint_url} "
                "(check OLLAMA_BASE_URL points at a running Ollama server)"
            ) from exc
        except APIConnectionError as exc:
            raise LLMConfigError(
                f"Ollama provider cannot reach {self._endpoint_url} "
                "(check OLLAMA_BASE_URL points at a running Ollama server)"
            ) from exc
