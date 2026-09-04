"""Shared webhook plumbing for modules that POST to clinic-supplied URLs.

Hoisted from the ``integrations`` module once a second consumer appeared
(``whatsapp_webhook``): Stripe-style HMAC signing (``signing``) and the
SSRF guard for clinic-supplied target URLs (``url_safety``). Core owns
these because optional modules cannot import each other — the seam any
webhook-emitting module builds on.
"""

from .signing import SIGNATURE_HEADER, sign, verify
from .url_safety import (
    UnsafeWebhookURLError,
    validate_before_dispatch,
    validate_new_url,
)

__all__ = [
    "SIGNATURE_HEADER",
    "sign",
    "verify",
    "UnsafeWebhookURLError",
    "validate_before_dispatch",
    "validate_new_url",
]
