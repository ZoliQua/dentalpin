"""whatsapp_webhook business logic: settings upsert, secret lifecycle, test send."""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.core.email.encryption import decrypt_password, encrypt_password
from app.core.webhooks.signing import SIGNATURE_HEADER, sign
from app.core.webhooks.url_safety import validate_new_url

from . import client
from .models import WhatsappWebhookSettings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class WebhookService:
    @staticmethod
    async def get_settings(db: AsyncSession, clinic_id: UUID) -> WhatsappWebhookSettings | None:
        return (
            await db.execute(
                select(WhatsappWebhookSettings).where(
                    WhatsappWebhookSettings.clinic_id == clinic_id
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def upsert_settings(
        db: AsyncSession, clinic_id: UUID, data: dict
    ) -> tuple[WhatsappWebhookSettings, str | None]:
        """Create/update the clinic's config.

        Returns ``(settings, plaintext_secret)`` — the secret is non-None
        only when it was (re)generated in this call: on first save, or when
        the caller passed ``rotate_secret=True``. It is never derivable
        again afterwards (same show-once contract as the integrations
        module's subscription secrets).

        Raises ``UnsafeWebhookURLError`` for a target URL that fails the
        SSRF check (https-only, no private/loopback/metadata ranges).
        """
        settings = await WebhookService.get_settings(db, clinic_id)

        url = data.get("target_url")
        if url is not None:
            await validate_new_url(url)

        plaintext_secret: str | None = None
        if settings is None:
            if not url:
                raise ValueError("target_url is required")
            plaintext_secret = _generate_secret()
            settings = WhatsappWebhookSettings(
                clinic_id=clinic_id,
                target_url=url,
                signing_secret_encrypted=encrypt_password(plaintext_secret),
                is_active=data.get("is_active", True),
            )
            db.add(settings)
        else:
            if url is not None:
                settings.target_url = url
            if data.get("is_active") is not None:
                settings.is_active = data["is_active"]
            if data.get("rotate_secret"):
                plaintext_secret = _generate_secret()
                settings.signing_secret_encrypted = encrypt_password(plaintext_secret)

        await db.flush()
        return settings, plaintext_secret

    @staticmethod
    async def send_test(
        db: AsyncSession, clinic_id: UUID, to_number: str
    ) -> tuple[bool, str | None]:
        """POST a signed test payload to the configured hook.

        Deliberately not routed through the outbox/adapter: the admin is
        looking at the settings page and wants the outcome *now*, not a
        queued row. Same payload shape (documented contract) with
        ``type: "notification.test"``.
        """
        settings = await WebhookService.get_settings(db, clinic_id)
        if settings is None or not settings.is_active:
            return False, "webhook not configured or inactive"
        secret = decrypt_password(settings.signing_secret_encrypted)
        if not secret:
            return False, "could not decrypt signing secret"

        body = json.dumps(
            {
                "type": "notification.test",
                "to": to_number,
                "clinic_id": str(clinic_id),
                "text": "DentalPin webhook test",
                "occurred_at": datetime.now(UTC).isoformat(),
            },
            ensure_ascii=False,
        ).encode("utf-8")
        headers = {"Content-Type": "application/json", SIGNATURE_HEADER: sign(secret, body)}

        try:
            response = await client.post_webhook(settings.target_url, body, headers)
        except client.WebhookDeliveryError as exc:
            settings.last_error = str(exc)[:500]
            await db.flush()
            return False, str(exc)[:500]

        if response.status_code >= 300:
            error = f"HTTP {response.status_code}: {response.text[:200]}"
            settings.last_error = error
            await db.flush()
            return False, error

        settings.last_delivery_at = datetime.now(UTC)
        settings.last_error = None
        await db.flush()
        return True, None


def _generate_secret() -> str:
    # ``whsec_`` prefix for secret-scanning tools, mirroring the dp_ API
    # tokens (and Stripe's own webhook-secret prefix).
    return "whsec_" + secrets.token_urlsafe(32)
