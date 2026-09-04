"""telephony models — per-clinic gateway config + persistent call log.

The webhook signing secret is Fernet-encrypted at rest
(``app.core.email.encryption``). Tables live on the module's own Alembic
branch so uninstall drops them cleanly.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.core.auth.models import Clinic
    from app.modules.patients.models import Patient


class TelephonySettings(Base, TimestampMixin):
    """Per-clinic CTI gateway config (issue #64 §8, phase-1 subset)."""

    __tablename__ = "telephony_settings"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), unique=True, index=True)

    signing_secret_encrypted: Mapped[str] = mapped_column(Text)
    # ISO-3166 alpha-2 used to normalize local-format caller numbers to
    # E.164 (issue #64 §1). Defaults from the clinic's country at save.
    default_country: Mapped[str] = mapped_column(String(2), default="ES")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    clinic: Mapped["Clinic"] = relationship(foreign_keys=[clinic_id])

    __table_args__ = (Index("idx_telephony_settings_clinic", "clinic_id"),)


class CallLog(Base, TimestampMixin):
    """One row per call — created on the first CTI event, updated by the
    rest (``call_id`` is the provider's id for the whole call)."""

    __tablename__ = "telephony_call_logs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)

    provider: Mapped[str] = mapped_column(String(50), default="webhook")
    call_id: Mapped[str] = mapped_column(String(200))
    direction: Mapped[str] = mapped_column(String(10))  # inbound | outbound

    from_number: Mapped[str] = mapped_column(String(32))  # E.164 when parseable
    to_number: Mapped[str | None] = mapped_column(String(32), default=None)
    agent_extension: Mapped[str | None] = mapped_column(String(20), default=None)

    # Matched caller, when exactly one patient owned the number.
    patient_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("patients.id"), default=None, index=True
    )

    # Last observed state: ringing | answered | ended | missed
    status: Mapped[str] = mapped_column(String(20), default="ringing", index=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, default=None)

    note: Mapped[str | None] = mapped_column(Text, default=None)

    patient: Mapped["Patient | None"] = relationship(foreign_keys=[patient_id])

    __table_args__ = (
        UniqueConstraint("clinic_id", "provider", "call_id", name="uq_telephony_call"),
        Index("idx_telephony_call_logs_clinic_status", "clinic_id", "status"),
        Index("idx_telephony_call_logs_clinic_created", "clinic_id", "created_at"),
    )
