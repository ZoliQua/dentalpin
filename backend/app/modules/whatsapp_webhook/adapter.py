"""WebhookWhatsappAdapter — delivers the WhatsApp channel via a signed webhook.

Implements the notifications ``ChannelAdapter`` contract (the only
cross-module import; legal because ``notifications`` is in this module's
``depends``). Instead of talking to a WhatsApp API directly, it POSTs the
rendered message as JSON to a clinic-configured URL — a Zapier / Make /
n8n hook that routes it onward. Zero vendor onboarding for the clinic:
paste a hook URL, done.

Pure wire: load per-clinic config, build the payload, sign it
(``X-DentalPin-Signature``, Stripe scheme — same as the integrations
module's outbound webhooks, from ``app.core.webhooks``), map the response
to an ``AdapterResult``. No business logic.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.core.email.encryption import decrypt_password
from app.core.webhooks.signing import SIGNATURE_HEADER, sign
from app.modules.notifications.channels import (
    AdapterResult,
    Channel,
    OutboundMessage,
    SendStatus,
)

from . import client
from .models import WhatsappWebhookSettings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def _active_settings(db: AsyncSession, clinic_id: UUID) -> WhatsappWebhookSettings | None:
    return (
        await db.execute(
            select(WhatsappWebhookSettings).where(
                WhatsappWebhookSettings.clinic_id == clinic_id,
                WhatsappWebhookSettings.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()


def build_payload(msg: OutboundMessage) -> dict:
    """The wire shape the clinic's hook receives. Documented contract —
    changing a key is a breaking change for every Zap built on it."""
    return {
        "type": "notification.whatsapp",
        "to": msg.to_address,
        "to_name": msg.to_name,
        "clinic_id": str(msg.clinic_id),
        "patient_id": str(msg.patient_id) if msg.patient_id else None,
        "template_key": msg.template_key,
        "locale": msg.locale,
        "message_kind": msg.message_kind,
        # Rendered text when the gateway has one (session sends always do;
        # template sends only when a channel template with a text body is
        # configured) — else the receiver composes from ``context``.
        "text": msg.body_text,
        "context": msg.context,
        "occurred_at": datetime.now(UTC).isoformat(),
    }


class WebhookWhatsappAdapter:
    """WhatsApp delivery via a clinic-configured signed webhook."""

    channel = Channel.WHATSAPP
    adapter_name = "whatsapp_webhook"

    async def supports(self, db: AsyncSession, clinic_id: UUID) -> bool:
        return await _active_settings(db, clinic_id) is not None

    async def send(self, db: AsyncSession, msg: OutboundMessage) -> AdapterResult:
        settings = await _active_settings(db, msg.clinic_id)
        if settings is None:
            return AdapterResult(
                status=SendStatus.FAILED,
                provider=self.adapter_name,
                error_message="whatsapp_webhook not configured for this clinic",
            )

        secret = decrypt_password(settings.signing_secret_encrypted)
        if not secret:
            return AdapterResult(
                status=SendStatus.FAILED,
                provider=self.adapter_name,
                error_message="could not decrypt webhook signing secret",
            )

        body = json.dumps(build_payload(msg), ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            SIGNATURE_HEADER: sign(secret, body),
        }

        try:
            response = await client.post_webhook(settings.target_url, body, headers)
        except client.WebhookDeliveryError as exc:
            await self._record_outcome(db, settings, error=str(exc)[:500])
            return AdapterResult(
                status=SendStatus.FAILED, provider=self.adapter_name, error_message=str(exc)[:500]
            )

        if response.status_code >= 300:
            error = f"HTTP {response.status_code}: {response.text[:200]}"
            await self._record_outcome(db, settings, error=error)
            return AdapterResult(
                status=SendStatus.FAILED, provider=self.adapter_name, error_message=error
            )

        await self._record_outcome(db, settings, error=None)
        return AdapterResult(
            status=SendStatus.SENT,
            provider=self.adapter_name,
            provider_message_id=_response_id(response),
        )

    @staticmethod
    async def _record_outcome(
        db: AsyncSession, settings: WhatsappWebhookSettings, *, error: str | None
    ) -> None:
        """Track last delivery/error for the settings page health hint.

        Flush only — the gateway's dispatcher owns the commit for the
        whole delivery attempt (message status + this) so they land
        atomically.
        """
        if error is None:
            settings.last_delivery_at = datetime.now(UTC)
            settings.last_error = None
        else:
            settings.last_error = error
        await db.flush()


def _response_id(response) -> str | None:
    """Optional receiver-assigned id: a JSON object body with ``id``."""
    try:
        data = response.json()
    except ValueError:
        return None
    if isinstance(data, dict) and data.get("id") is not None:
        return str(data["id"])[:200]
    return None
