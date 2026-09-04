"""Suppliers module — 1:1 extension on top of contacts for procurement."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import Supplier
from .router import router


class SuppliersModule(BaseModule):
    """Suppliers module: extending contacts with procurement attributes.

    Provides atomic CRUD for the Contact + Supplier row pairing, allowing
    vendors to live inside the unified contacts directory while unlocking
    purchase-order and inventory relationships.
    """

    manifest = {
        "name": "suppliers",
        "version": "0.1.0",
        "summary": "Procurement vendors and suppliers (extends contacts).",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "official",
        "depends": ["contacts"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        # Same role matrix as contacts
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["read"],
            "hygienist": ["read"],
            "assistant": ["read", "write"],
            "receptionist": ["read", "write"],
        },
    }

    def get_models(self) -> list:
        return [Supplier]

    def get_router(self) -> APIRouter:
        return router

    def get_tools(self) -> list:
        from .tools import get_all_tools

        return get_all_tools()

    def get_permissions(self) -> list[str]:
        return ["read", "write"]
