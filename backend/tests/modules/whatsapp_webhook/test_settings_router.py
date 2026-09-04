"""whatsapp_webhook settings API tests (secret show-once, SSRF gate, test send)."""

import pytest
from httpx import AsyncClient

from app.modules.whatsapp_webhook import client as webhook_client

SETTINGS = "/api/v1/whatsapp_webhook/settings"
TEST = "/api/v1/whatsapp_webhook/test"


@pytest.mark.asyncio
async def test_first_save_returns_secret_once(client: AsyncClient, auth_headers, test_clinic):
    res = await client.put(
        SETTINGS,
        json={"target_url": "https://example.com/hook"},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()["data"]
    assert body["signing_secret"].startswith("whsec_")
    assert body["has_signing_secret"] is True

    # Never returned again on a later read.
    res = await client.get(SETTINGS, headers=auth_headers)
    body = res.json()["data"]
    assert body["signing_secret"] is None
    assert body["has_signing_secret"] is True
    assert body["target_url"] == "https://example.com/hook"


@pytest.mark.asyncio
async def test_rotate_secret_returns_fresh_one(client: AsyncClient, auth_headers, test_clinic):
    first = await client.put(
        SETTINGS,
        json={"target_url": "https://example.com/hook"},
        headers=auth_headers,
    )
    old = first.json()["data"]["signing_secret"]

    res = await client.put(SETTINGS, json={"rotate_secret": True}, headers=auth_headers)
    new = res.json()["data"]["signing_secret"]
    assert new and new != old

    # A plain settings save does NOT rotate.
    res = await client.put(SETTINGS, json={"is_active": False}, headers=auth_headers)
    assert res.json()["data"]["signing_secret"] is None


@pytest.mark.asyncio
async def test_non_https_and_private_urls_rejected(client: AsyncClient, auth_headers, test_clinic):
    for url in ("http://hooks.example.com/x", "https://127.0.0.1/x", "https://169.254.169.254/x"):
        res = await client.put(SETTINGS, json={"target_url": url}, headers=auth_headers)
        assert res.status_code == 400, url


@pytest.mark.asyncio
async def test_first_save_requires_url(client: AsyncClient, auth_headers, test_clinic):
    res = await client.put(SETTINGS, json={"is_active": True}, headers=auth_headers)
    assert res.status_code == 400
    assert "target_url" in res.json()["message"]


@pytest.mark.asyncio
async def test_test_endpoint_reports_delivery(
    client: AsyncClient, auth_headers, test_clinic, monkeypatch
):
    await client.put(
        SETTINGS,
        json={"target_url": "https://example.com/hook"},
        headers=auth_headers,
    )

    class _Resp:
        status_code = 200
        text = ""

        def json(self):
            raise ValueError

    async def fake_post(url, body, headers):
        return _Resp()

    monkeypatch.setattr(webhook_client, "post_webhook", fake_post)
    res = await client.post(TEST, json={"to_number": "+34600112233"}, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["data"] == {"success": True, "error": None}
