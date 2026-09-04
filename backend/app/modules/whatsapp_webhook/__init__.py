"""whatsapp_webhook — WhatsApp delivery for notifications via a signed webhook.

Community, removable. The lowest-friction WhatsApp path from issue #63:
instead of a vendor API (kapso / Cloud API), the clinic pastes a Zapier /
Make / n8n hook URL and DentalPin POSTs each rendered WhatsApp
notification there as signed JSON; the clinic's automation routes it to
WhatsApp (or Telegram, SMS, anything).

Registers a ``WebhookWhatsappAdapter`` into the notifications channel
registry from ``on_activate`` (ADR 0020 — never at import time). That is
the only cross-module dependency, declared in ``manifest.depends``.

Issue #63. See ADR 0016 (channel adapters).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter

from app.core.plugins import BaseModule
from app.modules.notifications.channels import channel_registry

from .adapter import WebhookWhatsappAdapter
from .models import WhatsappWebhookSettings
from .router import router

if TYPE_CHECKING:
    from app.core.plugins.base import ModuleContext

# Table names exercised by the round-trip uninstall test.
WEBHOOK_TABLES = {"whatsapp_webhook_settings"}


class WhatsappWebhookModule(BaseModule):
    manifest = {
        "name": "whatsapp_webhook",
        "version": "0.1.0",
        "summary": "WhatsApp para notifications vía webhook firmado (Zapier/Make/n8n).",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "community",
        "depends": ["notifications"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {"admin": ["*"]},
        "frontend": {"layer_path": "frontend", "navigation": []},
    }

    def get_models(self) -> list:
        return [WhatsappWebhookSettings]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        # Namespaced → whatsapp_webhook.settings.read / .write
        return ["settings.read", "settings.write"]

    def on_activate(self) -> None:
        # Idempotent in the registry. Not registered ⇒ the gateway falls
        # back to the next configured channel (email).
        channel_registry.register(WebhookWhatsappAdapter())

    async def uninstall(self, ctx: ModuleContext) -> None:
        channel_registry.unregister("whatsapp_webhook")
