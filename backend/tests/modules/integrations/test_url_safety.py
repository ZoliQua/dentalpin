"""SSRF guard on webhook target_url — creation-time and dispatch-time.

Resolution runs via the event loop's own resolver
(``loop.getaddrinfo``), not ``socket.getaddrinfo`` — see
``url_safety.py``. Tests patch the running loop's ``getaddrinfo``
directly, not the ``socket`` module.
"""

import asyncio
import socket

import pytest

from app.core.webhooks.url_safety import (
    UnsafeWebhookURLError,
    validate_before_dispatch,
    validate_new_url,
)


def _patch_getaddrinfo(monkeypatch, *, result=None, exc=None):
    loop = asyncio.get_running_loop()

    async def fake(host, port):
        if exc is not None:
            raise exc
        return result

    monkeypatch.setattr(loop, "getaddrinfo", fake)


@pytest.mark.asyncio
async def test_rejects_non_https_scheme():
    with pytest.raises(UnsafeWebhookURLError, match="https"):
        await validate_new_url("http://example.com/hook")


@pytest.mark.asyncio
async def test_rejects_loopback_ip_literal():
    with pytest.raises(UnsafeWebhookURLError, match="disallowed"):
        await validate_new_url("https://127.0.0.1/hook")


@pytest.mark.asyncio
async def test_rejects_private_ip_literal():
    with pytest.raises(UnsafeWebhookURLError, match="disallowed"):
        await validate_new_url("https://10.0.0.5/hook")


@pytest.mark.asyncio
async def test_rejects_cloud_metadata_ip_literal():
    with pytest.raises(UnsafeWebhookURLError, match="disallowed"):
        await validate_new_url("https://169.254.169.254/latest/meta-data/")


@pytest.mark.asyncio
async def test_rejects_localhost_hostname(monkeypatch):
    _patch_getaddrinfo(monkeypatch, result=[(socket.AF_INET, None, None, "", ("127.0.0.1", 0))])
    with pytest.raises(UnsafeWebhookURLError, match="disallowed"):
        await validate_new_url("https://localhost/hook")


@pytest.mark.asyncio
async def test_rejects_hostname_that_resolves_to_link_local(monkeypatch):
    """Same category as cloud-metadata — a hostname (not just a raw IP
    literal) can resolve to 169.254.0.0/16."""
    _patch_getaddrinfo(
        monkeypatch, result=[(socket.AF_INET, None, None, "", ("169.254.169.254", 0))]
    )
    with pytest.raises(UnsafeWebhookURLError, match="disallowed"):
        await validate_new_url("https://metadata.internal/hook")


@pytest.mark.asyncio
async def test_rejects_unresolvable_hostname(monkeypatch):
    _patch_getaddrinfo(monkeypatch, exc=socket.gaierror("nope"))
    with pytest.raises(UnsafeWebhookURLError, match="could not resolve"):
        await validate_new_url("https://does-not-exist.invalid/hook")


@pytest.mark.asyncio
async def test_accepts_public_https_hostname(monkeypatch):
    _patch_getaddrinfo(
        monkeypatch, result=[(socket.AF_INET, None, None, "", ("93.184.216.34", 0))]
    )  # public
    await validate_new_url("https://example.com/hook")  # must not raise


@pytest.mark.asyncio
async def test_dispatch_time_check_catches_repointed_hostname(monkeypatch):
    """A subscription created against a safe IP can be repointed later
    (DNS rebinding / delayed re-point) — the dispatch-time check must
    catch it independently of the creation-time check."""
    _patch_getaddrinfo(monkeypatch, result=[(socket.AF_INET, None, None, "", ("10.0.0.9", 0))])
    with pytest.raises(UnsafeWebhookURLError, match="disallowed"):
        await validate_before_dispatch("https://was-safe-now-internal.example.com/hook")


@pytest.mark.asyncio
async def test_resolution_does_not_block_the_event_loop(monkeypatch):
    """A slow/non-resolving host must not freeze the API — resolution
    must go through the loop's own (thread-pool-backed) resolver, not
    a blocking call made directly on the event loop thread. Regression
    test for the pre-fix code, which called ``socket.getaddrinfo``
    (blocking) directly instead of ``await loop.getaddrinfo(...)``."""
    loop = asyncio.get_running_loop()
    ticked = False

    async def _tick_marker():
        nonlocal ticked
        ticked = True

    def blocking_getaddrinfo(host, port):
        # A real blocking resolver call would starve the loop for its
        # duration; scheduling and awaiting another coroutine here
        # proves the loop can still make progress concurrently only if
        # url_safety awaited rather than called this directly on the
        # loop thread. Patching `socket.getaddrinfo` (not
        # `loop.getaddrinfo`) simulates "the old, unfixed code path" —
        # if url_safety still called `socket.getaddrinfo` directly,
        # this fake would be hit; since it now goes through
        # `loop.getaddrinfo` (with the loop's own resolver, not this
        # patched one), this fake must NOT be hit at all.
        raise AssertionError("socket.getaddrinfo was called directly — not awaited via the loop")

    monkeypatch.setattr(socket, "getaddrinfo", blocking_getaddrinfo)
    monkeypatch.setattr(
        loop,
        "getaddrinfo",
        lambda host, port: asyncio.sleep(
            0, result=[(socket.AF_INET, None, None, "", ("93.184.216.34", 0))]
        ),
    )
    await asyncio.gather(validate_new_url("https://example.com/hook"), _tick_marker())
    assert ticked
