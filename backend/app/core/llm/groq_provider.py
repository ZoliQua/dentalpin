"""Groq implementation of the neutral :class:`Provider` protocol.

Speaks Groq's OpenAI-compatible endpoint
(``https://api.groq.com/openai/v1``) through the ``openai`` SDK, so the
wire format — Chat Completions streaming, tool calling, usage chunks — is
identical to :class:`OpenAIProvider` and this subclass only sets the
endpoint and the key. Tool dialect is ``"openai"``; dotted tool names map
``.`` <-> ``-`` exactly like the OpenAI provider.

Groq serves open-weight models at high speed with a free developer tier;
quotas and terms are the operator's Groq account. The mandatory PHI
redactor still runs upstream of every provider.
"""

from __future__ import annotations

from app.core.llm.base import LLMConfigError
from app.core.llm.openai_provider import OpenAIProvider

#: Groq's OpenAI-compatible base URL
#: (https://console.groq.com/docs/openai).
GROQ_OPENAI_COMPAT_BASE_URL = "https://api.groq.com/openai/v1/"


class GroqProvider(OpenAIProvider):
    """Streams completions from Groq, speaking neutral types."""

    def __init__(self, *, api_key: str) -> None:
        if not api_key:
            raise LLMConfigError("Groq provider requires GROQ_API_KEY")
        super().__init__(api_key=api_key, base_url=GROQ_OPENAI_COMPAT_BASE_URL)
