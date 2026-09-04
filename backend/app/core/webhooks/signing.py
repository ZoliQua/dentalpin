"""Outbound webhook delivery signing — Stripe's exact scheme.

Header ``X-DentalPin-Signature``: ``t=<unix_ts>,v1=<hex_hmac>``.
Signed string is ``f"{timestamp}.{payload}"`` over the raw body bytes
(never a re-serialized copy — formatting drift breaks the signature).
5-minute tolerance on verify, same as Stripe. Receivers already
carrying a Stripe webhook verifier can reuse it unmodified, minus the
header name.

Named ``X-DentalPin-Signature`` rather than ``X-Integrations-Signature``:
it's a public contract once shipped, and the product name is the
right one to commit to long-term, not the internal module name.
"""

import hashlib
import hmac
import time

SIGNATURE_HEADER = "X-DentalPin-Signature"
DEFAULT_TOLERANCE_SECONDS = 300


def _signed_string(timestamp: int, payload: bytes) -> bytes:
    return f"{timestamp}.".encode() + payload


def sign(secret: str, payload: bytes, *, timestamp: int | None = None) -> str:
    """Build the ``X-DentalPin-Signature`` header value for ``payload``.

    ``timestamp`` defaults to now (unix seconds); pass explicitly only
    in tests that need a fixed clock.
    """
    ts = timestamp if timestamp is not None else int(time.time())
    mac = hmac.new(secret.encode(), _signed_string(ts, payload), hashlib.sha256).hexdigest()
    return f"t={ts},v1={mac}"


def verify(
    secret: str,
    payload: bytes,
    header: str,
    *,
    tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS,
) -> bool:
    """Verify an ``X-DentalPin-Signature`` header against ``payload``.

    Checks the HMAC first (constant-time), then the timestamp tolerance —
    a malformed or forged header is always rejected regardless of clock,
    and a stale-but-correctly-signed header is rejected only after the
    signature itself is confirmed genuine.
    """
    ts_raw, mac = _parse_header(header)
    if ts_raw is None or mac is None:
        return False
    try:
        ts = int(ts_raw)
    except ValueError:
        return False

    expected = hmac.new(secret.encode(), _signed_string(ts, payload), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac, expected):
        return False

    return abs(time.time() - ts) <= tolerance_seconds


def _parse_header(header: str) -> tuple[str | None, str | None]:
    """Parse ``t=<ts>,v1=<mac>`` into ``(ts, mac)``, tolerant of extra
    ``v1=`` entries (Stripe allows multiple signing secrets during
    rotation — we don't yet, but the parse shouldn't break if a future
    delivery carries one) and out-of-order fields."""
    ts = None
    mac = None
    for part in (header or "").split(","):
        key, _, value = part.strip().partition("=")
        if key == "t" and ts is None:
            ts = value
        elif key == "v1" and mac is None:
            mac = value
    return ts, mac
