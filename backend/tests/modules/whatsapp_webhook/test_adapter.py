"""WebhookWhatsappAdapter unit tests (outbound HTTP mocked)."""

import json

import pytest

from app.core.email.encryption import encrypt_password
from app.core.webhooks.signing import SIGNATURE_HEADER, verify
from app.modules.notifications.channels import Channel, OutboundMessage, SendStatus
from app.modules.whatsapp_webhook import client as webhook_client
from app.modules.whatsapp_webhook.adapter import WebhookWhatsappAdapter
from app.modules.whatsapp_webhook.models import WhatsappWebhookSettings


async def _settings(db, clinic_id, *, active=True, url="https://example.com/hook"):
    s = WhatsappWebhookSettings(
        clinic_id=clinic_id,
        target_url=url,
        signing_secret_encrypted=encrypt_password("whsec_test"),
        is_active=active,
    )
    db.add(s)
    await db.commit()
    return s


def _msg(clinic_id, **kw):
    base = dict(
        channel=Channel.WHATSAPP,
        to_address="+34600111222",
        clinic_id=clinic_id,
        template_key="appointment_reminder",
        locale="es",
        context={"patient_name": "Ana", "appointment_date": "01/09/2026"},
        to_name="Ana",
        message_kind="template",
    )
    base.update(kw)
    return OutboundMessage(**base)


class _Resp:
    def __init__(self, status_code=200, body=None, text=""):
        self.status_code = status_code
        self._body = body
        self.text = text

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


@pytest.mark.asyncio
async def test_send_posts_signed_payload(db_session, test_clinic, monkeypatch):
    await _settings(db_session, test_clinic.id)
    captured = {}

    async def fake_post(url, body, headers):
        captured.update(url=url, body=body, headers=headers)
        return _Resp(200, {"id": "evt_123"})

    monkeypatch.setattr(webhook_client, "post_webhook", fake_post)
    res = await WebhookWhatsappAdapter().send(db_session, _msg(test_clinic.id))

    assert res.status == SendStatus.SENT
    assert res.provider_message_id == "evt_123"
    assert captured["url"] == "https://example.com/hook"

    payload = json.loads(captured["body"])
    assert payload["type"] == "notification.whatsapp"
    assert payload["to"] == "+34600111222"
    assert payload["template_key"] == "appointment_reminder"
    assert payload["context"]["patient_name"] == "Ana"

    # The signature must verify against the exact bytes that were sent.
    assert verify("whsec_test", captured["body"], captured["headers"][SIGNATURE_HEADER])


@pytest.mark.asyncio
async def test_http_error_maps_to_failed_and_records_last_error(
    db_session, test_clinic, monkeypatch
):
    settings = await _settings(db_session, test_clinic.id)

    async def fake_post(url, body, headers):
        return _Resp(500, text="zap exploded")

    monkeypatch.setattr(webhook_client, "post_webhook", fake_post)
    res = await WebhookWhatsappAdapter().send(db_session, _msg(test_clinic.id))
    assert res.status == SendStatus.FAILED
    assert "500" in res.error_message
    assert "500" in settings.last_error


@pytest.mark.asyncio
async def test_transport_error_maps_to_failed(db_session, test_clinic, monkeypatch):
    await _settings(db_session, test_clinic.id)

    async def boom(url, body, headers):
        raise webhook_client.WebhookDeliveryError("connect timeout")

    monkeypatch.setattr(webhook_client, "post_webhook", boom)
    res = await WebhookWhatsappAdapter().send(db_session, _msg(test_clinic.id))
    assert res.status == SendStatus.FAILED
    assert "timeout" in res.error_message


@pytest.mark.asyncio
async def test_supports_requires_active_settings(db_session, test_clinic):
    adapter = WebhookWhatsappAdapter()
    assert not await adapter.supports(db_session, test_clinic.id)
    await _settings(db_session, test_clinic.id, active=False)
    assert not await adapter.supports(db_session, test_clinic.id)


@pytest.mark.asyncio
async def test_supports_true_when_active(db_session, test_clinic):
    await _settings(db_session, test_clinic.id, active=True)
    assert await WebhookWhatsappAdapter().supports(db_session, test_clinic.id)


def test_registry_lists_all_adapters_for_a_channel():
    """Two vendors on one channel must both be reachable — the gateway
    picks the *configured* one via ``supports``, so the registry has to
    surface every candidate, not just the last registered."""
    from app.modules.notifications.channels.registry import ChannelRegistry

    class _A:
        channel = Channel.WHATSAPP
        adapter_name = "vendor_a"

    class _B:
        channel = Channel.WHATSAPP
        adapter_name = "vendor_b"

    reg = ChannelRegistry()
    reg.register(_A())
    reg.register(_B())
    names = [a.adapter_name for a in reg.adapters_for_channel(Channel.WHATSAPP)]
    assert names == ["vendor_b", "vendor_a"]  # most recent first
