"""Agenda module — appointments + scheduling + cabinets."""

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import (
    Appointment,
    AppointmentCabinetEvent,
    AppointmentStatusEvent,
    Cabinet,
)
from .router import router


class AgendaModule(BaseModule):
    """Scheduling module: appointments, appointment treatments, cabinets."""

    manifest = {
        "name": "agenda",
        "version": "0.4.0",
        "summary": "Appointments, scheduling, cabinets.",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "official",
        "depends": ["patients", "catalog", "odontogram"],
        "installable": True,
        "auto_install": True,
        "removable": False,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["*"],
            "hygienist": [
                "appointments.read",
                "appointments.write",
                "cabinets.read",
            ],
            "assistant": [
                "appointments.read",
                "appointments.write",
                "cabinets.read",
            ],
            "receptionist": [
                "appointments.read",
                "appointments.write",
                "cabinets.read",
            ],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "nav.appointments",
                    "icon": "i-lucide-calendar",
                    "to": "/appointments",
                    "permission": "agenda.appointments.read",
                    "order": 20,
                },
            ],
        },
    }

    def get_models(self) -> list:
        return [
            Cabinet,
            Appointment,
            AppointmentStatusEvent,
            AppointmentCabinetEvent,
        ]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return [
            "appointments.read",
            "appointments.write",
            "cabinets.read",
            "cabinets.write",
        ]

    def get_tools(self) -> list:
        from . import tools

        return tools.get_tools()

    def get_event_handlers(self) -> dict:
        from app.core.events import EventType

        from .events import on_clinic_created

        return {EventType.CLINIC_CREATED: on_clinic_created}
