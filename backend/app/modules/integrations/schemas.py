"""integrations Pydantic schemas.

``secret`` is returned ONLY from ``WebhookSubscriptionCreated`` (the
create response) — never again after (secrets.token_urlsafe(32),
shown once). Every other response uses
``WebhookSubscriptionResponse``, which carries no secret at all.

``target_url`` is NOT validated for SSRF safety here — a Pydantic
validator can't ``await``, and the check needs the event loop's
resolver (see ``url_safety.py``). It's validated in ``service.py``
instead, at create/update, before the row is written.
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .triggers import SUPPORTED_EVENT_TYPES, SUPPORTED_TOKEN_SCOPES


class WebhookSubscriptionCreate(BaseModel):
    description: str | None = Field(default=None, max_length=255)
    target_url: str = Field(max_length=2048)
    event_types: list[str] = Field(min_length=1)

    @field_validator("event_types")
    @classmethod
    def _known_event_types(cls, value: list[str]) -> list[str]:
        unsupported = sorted(set(value) - SUPPORTED_EVENT_TYPES)
        if unsupported:
            raise ValueError(
                f"unsupported event type(s) in Phase 1: {unsupported}. "
                f"Supported: {sorted(SUPPORTED_EVENT_TYPES)}"
            )
        return value


class WebhookSubscriptionUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=255)
    target_url: str | None = Field(default=None, max_length=2048)
    event_types: list[str] | None = Field(default=None, min_length=1)
    is_active: bool | None = None

    @field_validator("event_types")
    @classmethod
    def _known_event_types(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        unsupported = sorted(set(value) - SUPPORTED_EVENT_TYPES)
        if unsupported:
            raise ValueError(
                f"unsupported event type(s) in Phase 1: {unsupported}. "
                f"Supported: {sorted(SUPPORTED_EVENT_TYPES)}"
            )
        return value


class WebhookSubscriptionResponse(BaseModel):
    id: UUID
    description: str | None
    target_url: str
    event_types: list[str]
    is_active: bool
    consecutive_failures: int
    disabled_at: datetime | None
    disabled_reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class WebhookSubscriptionCreated(WebhookSubscriptionResponse):
    """Create response only — carries the plaintext secret exactly once."""

    secret: str = Field(description="Shown once. Store it now; it cannot be retrieved again.")


class ApiTokenCreate(BaseModel):
    name: str = Field(max_length=255)
    scopes: list[str] = Field(default_factory=list)

    @field_validator("scopes")
    @classmethod
    def _known_scopes(cls, value: list[str]) -> list[str]:
        unsupported = sorted(set(value) - SUPPORTED_TOKEN_SCOPES)
        if unsupported:
            raise ValueError(
                f"unsupported scope(s): {unsupported}. Supported: {sorted(SUPPORTED_TOKEN_SCOPES)}"
            )
        return value


class ApiTokenResponse(BaseModel):
    id: UUID
    name: str
    scopes: list[str]
    last_used_at: datetime | None
    revoked_at: datetime | None
    revoked_reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiTokenCreated(ApiTokenResponse):
    """Create response only — carries the plaintext token exactly once."""

    token: str = Field(description="Shown once. Store it now; it cannot be retrieved again.")


class PublicTokenInfo(BaseModel):
    """``GET /public/ping`` — token introspection for a consumer's auth
    test (Zapier/Make call this to validate the pasted token)."""

    clinic_id: UUID
    token_name: str
    scopes: list[str]


class PublicPatientResponse(BaseModel):
    """Patient record exposed through the token-authenticated public API.

    A deliberate subset of ``patients.PatientResponse``: identity + core
    contact fields only. Billing details, photo, notes and internal
    lifecycle flags are not exposed to third-party token holders (issue #65
    §2/§12). Multi-tenancy is enforced by the router (queries are
    clinic-scoped off the token).
    """

    id: UUID
    first_name: str
    last_name: str
    phone: str | None
    email: str | None
    national_id: str | None
    date_of_birth: date | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
