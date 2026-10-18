"""OpenRouter implementation of the neutral :class:`Provider` protocol.

Speaks OpenRouter's OpenAI-compatible endpoint
(``https://openrouter.ai/api/v1``) through the ``openai`` SDK, so the wire
format — Chat Completions streaming, tool calling, usage chunks — is
identical to :class:`OpenAIProvider` and this subclass only sets the
endpoint and the key. Tool dialect is ``"openai"``; dotted tool names map
``.`` <-> ``-`` exactly like the OpenAI provider.

OpenRouter is a model gateway: the clinic picks any model id (the default
below is a stable cheap one, overridable per clinic). Billing, rate limits
and data handling are the operator's OpenRouter account terms; the
mandatory PHI redactor still runs upstream of every provider.
"""

from __future__ import annotations

from app.core.llm.base import LLMConfigError
from app.core.llm.openai_provider import OpenAIProvider

#: OpenRouter's OpenAI-compatible base URL (https://openrouter.ai/docs).
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/"


class OpenRouterProvider(OpenAIProvider):
    """Streams completions via OpenRouter, speaking neutral types."""

    def __init__(self, *, api_key: str) -> None:
        if not api_key:
            raise LLMConfigError("OpenRouter provider requires OPENROUTER_API_KEY")
        super().__init__(api_key=api_key, base_url=OPENROUTER_BASE_URL)
