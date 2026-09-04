"""Pydantic schemas for the suppliers module."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SupplierCreate(BaseModel):
    """Schema for atomic creation of a Contact + Supplier row."""

    # Contact fields
    name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=2000)

    # Supplier fields
    website: str | None = Field(default=None, max_length=2048)
    payment_terms: str | None = Field(default=None, max_length=255)
    lead_time_days: int | None = Field(default=None, ge=0)
    is_preferred: bool = False


class SupplierUpdate(BaseModel):
    """Schema for atomic update of a Contact + Supplier row."""

    # Contact fields
    name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None

    # Supplier fields
    website: str | None = Field(default=None, max_length=2048)
    payment_terms: str | None = Field(default=None, max_length=255)
    lead_time_days: int | None = Field(default=None, ge=0)
    is_preferred: bool | None = None


class SupplierResponse(BaseModel):
    """Composited view of the Contact and Supplier rows."""

    model_config = ConfigDict(from_attributes=True)

    # From Contact
    id: UUID
    clinic_id: UUID
    name: str
    contact_type: str
    phone: str | None
    email: str | None
    address: str | None
    notes: str | None
    is_active: bool

    # From Supplier
    website: str | None
    payment_terms: str | None
    lead_time_days: int | None
    is_preferred: bool

    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_rows(cls, contact, supplier) -> SupplierResponse:
        return cls(
            id=contact.id,
            clinic_id=contact.clinic_id,
            name=contact.name,
            contact_type=contact.contact_type,
            phone=contact.phone,
            email=contact.email,
            address=contact.address,
            notes=contact.notes,
            is_active=contact.is_active,
            website=supplier.website,
            payment_terms=supplier.payment_terms,
            lead_time_days=supplier.lead_time_days,
            is_preferred=supplier.is_preferred,
            created_at=supplier.created_at,
            updated_at=supplier.updated_at,
        )
