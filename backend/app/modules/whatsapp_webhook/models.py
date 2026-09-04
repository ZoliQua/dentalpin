"""whatsapp_webhook models — per-clinic webhook target + signing secret.

The signing secret is Fernet-encrypted at rest via the project-wide
``app.core.email.encryption`` util (same scheme as SMTP passwords and the
kapso credentials). The table lives on the module's own Alembic branch so
uninstall drops it cleanly.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.core.auth.models import Clinic


class WhatsappWebhookSettings(Base, TimestampMixin):
    """Per-clinic webhook delivery config for the WhatsApp channel."""

    __tablename__ = "whatsapp_webhook_settings"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), unique=True, index=True)

    # Where the signed JSON payload is POSTed (Zapier / Make / n8n hook).
    target_url: Mapped[str] = mapped_column(Text)
    signing_secret_encrypted: Mapped[str] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_error: Mapped[str | None] = mapped_column(Text, default=None)

    clinic: Mapped["Clinic"] = relationship(foreign_keys=[clinic_id])

    __table_args__ = (Index("idx_whatsapp_webhook_settings_clinic", "clinic_id"),)
