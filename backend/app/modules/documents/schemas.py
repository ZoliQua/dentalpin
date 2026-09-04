"""Pydantic schemas for the documents module."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

_DATE_FIELDS = ("valid_from", "valid_until")

# ---------------------------------------------------------------------------
# Create / Update schemas
# ---------------------------------------------------------------------------


class MedicationItem(BaseModel):
    """A single medication line in a prescription."""

    name: str
    dose: str = ""
    frequency: str = ""
    duration: str = ""
    notes: str = ""


class PrescriptionContent(BaseModel):
    """Content payload for a prescription document."""

    diagnosis: str = ""
    medications: list[MedicationItem] = Field(default_factory=list)
    notes: str = ""


class MedicalCertificateContent(BaseModel):
    """Content payload for a medical certificate."""

    diagnosis: str = ""
    description: str = ""
    recommendations: str = ""
    valid_from: date | None = None
    valid_until: date | None = None

    @field_validator("valid_from", "valid_until", mode="before")
    @classmethod
    def _empty_date_is_none(cls, value: object) -> object:
        if value == "":
            return None
        return value


class ReferralContent(BaseModel):
    """Content payload for a referral letter."""

    referred_to: str = ""
    specialty: str = ""
    reason: str = ""
    clinical_summary: str = ""
    notes: str = ""


class RadiologyRequestContent(BaseModel):
    """Content payload for a radiology request."""

    exam_type: str = ""
    region: str = ""
    clinical_question: str = ""
    notes: str = ""


CONTENT_SCHEMAS: dict[str, type[BaseModel]] = {
    "prescription": PrescriptionContent,
    "medical_certificate": MedicalCertificateContent,
    "referral": ReferralContent,
    "radiology_request": RadiologyRequestContent,
}


class DocumentCreate(BaseModel):
    """Schema for creating a new document."""

    patient_id: UUID
    document_type: Literal[
        "prescription",
        "medical_certificate",
        "referral",
        "radiology_request",
    ]
    title: str = Field(..., max_length=200)
    content: dict = Field(default_factory=dict)

    @field_validator("content")
    @classmethod
    def _validate_content(cls, value: object, info) -> dict:
        """Validate ``content`` against the type-specific schema.

        The typed content schemas are the single source of truth for
        each document type's shape. Validating here normalizes
        (date coercion, defaults) and rejects payloads that don't fit
        the declared document_type with a 422.
        """
        if not isinstance(value, dict):
            return value
        schema = CONTENT_SCHEMAS.get(str(info.data.get("document_type", "")))
        if schema is None:
            return value
        parsed = schema.model_validate(value)
        dumped = parsed.model_dump(exclude_none=True)
        # ``date`` objects are not JSON-serializable for the JSONB
        # column — normalize to ISO strings.
        return {
            k: v.isoformat() if k in _DATE_FIELDS and isinstance(v, date) else v
            for k, v in dumped.items()
        }


class DocumentUpdate(BaseModel):
    """Schema for updating an existing document (partial)."""

    title: str | None = Field(default=None, max_length=200)
    content: dict | None = None
    status: Literal["draft", "generated", "archived"] | None = None


# ---------------------------------------------------------------------------
# Letterhead settings
# ---------------------------------------------------------------------------


class LetterheadSettings(BaseModel):
    """Per-clinic letterhead overrides for generated PDFs.

    Persisted under ``clinic.settings["documents"]["letterhead"]``.
    Every field is optional — an unset field falls back to the
    clinic's native profile (name, address, phone, email, tax_id).
    ``logo`` holds an inline data-URL or empty string.
    """

    name: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    registration_number: str | None = None
    logo: str | None = None


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class DocumentResponse(BaseModel):
    """Schema returned to the client."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    patient_id: UUID
    document_type: str
    title: str
    status: str
    content: dict
    file_path: str | None = None
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime


class DocumentGenerateRequest(BaseModel):
    """Request to generate (render) a document as PDF."""

    document_id: UUID
