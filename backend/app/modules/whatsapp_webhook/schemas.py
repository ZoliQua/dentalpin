"""whatsapp_webhook Pydantic schemas. The signing secret is shown once."""

from datetime import datetime

from pydantic import BaseModel, Field


class WebhookSettingsUpdate(BaseModel):
    target_url: str | None = Field(
        default=None, max_length=2000, description="HTTPS hook URL (Zapier/Make/n8n)."
    )
    is_active: bool | None = None
    rotate_secret: bool = Field(
        default=False, description="Generate a new signing secret (returned once)."
    )


class WebhookSettingsResponse(BaseModel):
    target_url: str | None
    is_active: bool
    has_signing_secret: bool
    last_delivery_at: datetime | None
    last_error: str | None
    # Present only in the response to the save that (re)generated it.
    signing_secret: str | None = None


class WebhookTestRequest(BaseModel):
    to_number: str = Field(..., max_length=32)
