"""Clinical notes module — administrative + diagnosis + treatment + plan notes.

Owns the polymorphic ``clinical_notes`` table. Notes attach to one of:

- ``patient``    → administrative or diagnosis notes
- ``treatment``  → per-treatment notes (live with the underlying odontogram
  ``Treatment`` row, so they survive across diagnosis → plan → completion)
- ``plan``       → plan-level (whole treatment plan) notes

Document attachments live in the ``media`` module since revision
``cn_0002`` (issue #55). At import time we register four owner_types
(``patient``, ``treatment``, ``plan``, ``clinical_note``) with
``media.attachment_registry`` so other modules can attach to a note
without importing this module.

UI surfaces (Summary tab feed, diagnosis sidebar, per-row note button,
plan timeline) are mounted via the slot registry — host modules
(``patients``, ``odontogram``, ``treatment_plan``) only expose slot points
and never import this module's services. Backend reads from those modules
go through the explicit ``manifest.depends`` declaration.
"""

from typing import Any

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import ClinicalNote
from .router import router


class ClinicalNotesModule(BaseModule):
    manifest = {
        "name": "clinical_notes",
        "version": "0.2.0",
        "summary": (
            "Polymorphic clinical notes (administrative, diagnosis, treatment, "
            "treatment plan) with author. Attachments delegated to media."
        ),
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "official",
        "depends": ["patients", "odontogram", "treatment_plan", "media", "agenda"],
        "installable": True,
        "auto_install": True,
        "removable": False,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["notes.read", "notes.write"],
            "hygienist": ["notes.read", "notes.write"],
            "assistant": ["notes.read", "notes.write"],
            "receptionist": ["notes.read", "notes.write"],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [],
        },
    }

    def on_activate(self) -> None:
        # Attachment owner_types with media.attachment_registry —
        # re-attached per boot while installed (ADR 0020, issue #325;
        # used to run at import time).
        from .owner_resolvers import register as register_attachment_owners

        register_attachment_owners()

    def get_models(self) -> list:
        return [ClinicalNote]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["notes.read", "notes.write"]

    def get_event_handlers(self) -> dict[str, Any]:
        return {}
