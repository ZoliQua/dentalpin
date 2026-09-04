"""Supplier models — 1:1 extension of the core Contact."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.contacts.models import Contact


class Supplier(Base, TimestampMixin):
    """Procurement-specific data for a Contact(type='supplier').

    This is a 1:1 extension table. The primary key matches ``contacts.id``.
    """

    __tablename__ = "suppliers"

    # The PK is also the FK to contacts.id, enforcing the 1:1 mapping.
    id: Mapped[UUID] = mapped_column(ForeignKey("contacts.id"), primary_key=True)

    # Denormalized for rapid multi-tenant filtering without a join.
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    website: Mapped[str | None] = mapped_column(String(2048), default=None)
    payment_terms: Mapped[str | None] = mapped_column(String(255), default=None)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, default=None)

    # Used by inventory_reorder to prioritize where to reorder from.
    is_preferred: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    contact: Mapped[Contact] = relationship(foreign_keys=[id])
