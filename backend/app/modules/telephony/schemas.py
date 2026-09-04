"""telephony Pydantic schemas. The signing secret is shown once."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TelephonySettingsUpdate(BaseModel):
    default_country: str | None = Field(default=None, pattern="^[A-Za-z]{2}$")
    is_active: bool | None = None
    rotate_secret: bool = Field(
        default=False, description="Generate a new signing secret (returned once)."
    )


class TelephonySettingsResponse(BaseModel):
    default_country: str | None
    is_active: bool
    has_signing_secret: bool
    last_event_at: datetime | None
    webhook_path: str | None
    # Present only in the response to the save that (re)generated it.
    signing_secret: str | None = None


class CallLogResponse(BaseModel):
    id: UUID
    provider: str
    call_id: str
    direction: str
    from_number: str
    to_number: str | None
    agent_extension: str | None
    patient_id: UUID | None
    patient_name: str | None = None
    status: str
    started_at: datetime | None
    answered_at: datetime | None
    ended_at: datetime | None
    duration_seconds: int | None
    note: str | None
    created_at: datetime


class CallNoteUpdate(BaseModel):
    note: str = Field(max_length=2000)
