"""telephony — CTI gateway: inbound call events, caller→patient match, call log.

Issue #64, phase 1. The vendor-agnostic core of the design: a public
HMAC-verified webhook accepts normalized CTI events from any source
(Zapier / Make / a PBX call-flow), numbers are normalized to E.164,
callers are matched against patients, every call lands in a persistent
log, and `call.*` events go on the bus. The screen-pop is a polling call
card in the receptionist UI (`/calls` + the `callPop` client plugin).

Vendor adapters (aircall / 3cx / twilio_voice) arrive later as their own
community modules posting into the same gateway. Community, removable.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import CallLog, TelephonySettings
from .router import router

# Table names exercised by the round-trip uninstall test.
TELEPHONY_TABLES = {"telephony_settings", "telephony_call_logs"}


class TelephonyModule(BaseModule):
    manifest = {
        "name": "telephony",
        "version": "0.1.0",
        "summary": "CTI: aviso en pantalla de llamadas entrantes + registro de llamadas.",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "community",
        "depends": ["patients"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            "receptionist": ["calls.read", "calls.write"],
            "dentist": ["calls.read"],
            "hygienist": [],
            "assistant": ["calls.read"],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "nav.telephonyCalls",
                    "icon": "i-lucide-phone-incoming",
                    "to": "/calls",
                    "permission": "telephony.calls.read",
                    "order": 92,
                }
            ],
        },
    }

    def get_models(self) -> list:
        return [TelephonySettings, CallLog]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        # Namespaced → telephony.settings.* / telephony.calls.*
        return ["settings.read", "settings.write", "calls.read", "calls.write"]
