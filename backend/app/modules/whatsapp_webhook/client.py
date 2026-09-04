"""Thin outbound HTTP client for the webhook adapter.

Isolated so tests ``monkeypatch.setattr`` this one function — same
pattern as ``integrations.client.post_webhook`` (this module cannot
import that one: optional modules never import each other; the shared
pieces live in ``app.core.webhooks``).
"""

from __future__ import annotations

import httpx

from app.core.webhooks.url_safety import UnsafeWebhookURLError, validate_before_dispatch

_REQUEST_TIMEOUT = 10.0


class WebhookDeliveryError(Exception):
    """Transport-level failure delivering a webhook (no HTTP response)."""


async def post_webhook(url: str, body: bytes, headers: dict[str, str]) -> httpx.Response:
    """POST ``body`` to ``url``. Raises :class:`WebhookDeliveryError` on
    transport failures (including a URL that now fails the SSRF check);
    a non-2xx HTTP response is returned normally."""
    try:
        await validate_before_dispatch(url)
    except UnsafeWebhookURLError as exc:
        raise WebhookDeliveryError(f"unsafe target_url: {exc}") from exc
    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT, follow_redirects=False) as client:
            return await client.post(url, content=body, headers=headers)
    except httpx.HTTPError as exc:
        raise WebhookDeliveryError(str(exc)) from exc
