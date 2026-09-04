"""telephony HTTP surface — mounted at ``/api/v1/telephony/``.

Settings + call log are JWT/RBAC-gated. ``POST /events/{clinic_id}`` is
PUBLIC (auth is per-route): the PBX / Zapier posts normalized CTI events
there, verified by the clinic's HMAC signature (``X-DentalPin-Signature``,
same Stripe scheme as the outbound webhooks — ``app.core.webhooks``).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.auth.router import limiter
from app.core.email.encryption import decrypt_password
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.core.webhooks.signing import SIGNATURE_HEADER, verify
from app.database import get_db

from .models import CallLog
from .schemas import (
    CallLogResponse,
    CallNoteUpdate,
    TelephonySettingsResponse,
    TelephonySettingsUpdate,
)
from .service import TelephonyService

router = APIRouter()


def _settings_response(settings, *, secret: str | None = None) -> TelephonySettingsResponse:
    return TelephonySettingsResponse(
        default_country=settings.default_country if settings else None,
        is_active=bool(settings and settings.is_active),
        has_signing_secret=bool(settings and settings.signing_secret_encrypted),
        last_event_at=settings.last_event_at if settings else None,
        webhook_path=(f"/api/v1/telephony/events/{settings.clinic_id}" if settings else None),
        signing_secret=secret,
    )


def _call_response(row: CallLog) -> CallLogResponse:
    patient = row.patient
    return CallLogResponse(
        id=row.id,
        provider=row.provider,
        call_id=row.call_id,
        direction=row.direction,
        from_number=row.from_number,
        to_number=row.to_number,
        agent_extension=row.agent_extension,
        patient_id=row.patient_id,
        patient_name=patient.full_name if patient else None,
        status=row.status,
        started_at=row.started_at,
        answered_at=row.answered_at,
        ended_at=row.ended_at,
        duration_seconds=row.duration_seconds,
        note=row.note,
        created_at=row.created_at,
    )


@router.get("/settings", response_model=ApiResponse[TelephonySettingsResponse])
async def get_settings(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("telephony.settings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[TelephonySettingsResponse]:
    settings = await TelephonyService.get_settings(db, ctx.clinic_id)
    return ApiResponse(data=_settings_response(settings))


@router.put("/settings", response_model=ApiResponse[TelephonySettingsResponse])
async def update_settings(
    data: TelephonySettingsUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("telephony.settings.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[TelephonySettingsResponse]:
    settings, secret = await TelephonyService.upsert_settings(db, ctx.clinic_id, data.model_dump())
    return ApiResponse(data=_settings_response(settings, secret=secret))


@router.get("/status", response_model=ApiResponse[dict])
async def gateway_status(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("telephony.calls.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[dict]:
    """Cheap probe for the screen-pop plugin: is the gateway configured
    and active for this clinic? Lets clients back off the 15s poll to a
    slow re-check instead of hammering /calls/active for nothing."""
    settings = await TelephonyService.get_settings(db, ctx.clinic_id)
    return ApiResponse(data={"active": bool(settings and settings.is_active)})


@router.get("/calls", response_model=PaginatedApiResponse[CallLogResponse])
async def list_calls(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("telephony.calls.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: str | None = Query(default=None, alias="status", max_length=20),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[CallLogResponse]:
    rows, total = await TelephonyService.list_calls(
        db, ctx.clinic_id, status=status_filter, page=page, page_size=page_size
    )
    return PaginatedApiResponse(
        data=[_call_response(r) for r in rows], total=total, page=page, page_size=page_size
    )


@router.get("/calls/active", response_model=ApiResponse[list[CallLogResponse]])
async def active_calls(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("telephony.calls.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[CallLogResponse]]:
    """Ringing/answered calls of the last minutes — the screen-pop poll."""
    rows = await TelephonyService.active_calls(db, ctx.clinic_id)
    return ApiResponse(data=[_call_response(r) for r in rows])


@router.put("/calls/{call_log_id}/note", response_model=ApiResponse[CallLogResponse])
async def set_call_note(
    call_log_id: UUID,
    data: CallNoteUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("telephony.calls.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[CallLogResponse]:
    row = (
        await db.execute(
            select(CallLog)
            .options(selectinload(CallLog.patient))
            .where(CallLog.id == call_log_id, CallLog.clinic_id == ctx.clinic_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
    row.note = data.note
    await db.flush()
    return ApiResponse(data=_call_response(row))


# --------------------------------------------------------------------------- #
# PUBLIC CTI ingest — no JWT. Verified by the clinic's HMAC signature.
# --------------------------------------------------------------------------- #
@router.post("/events/{clinic_id}")
@limiter.limit("240/minute")
async def ingest_cti_event(
    clinic_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Normalized CTI event intake (issue #64 §1).

    The clinic id lives in the path (the PBX/Zap is configured with the
    full URL); authenticity comes from the HMAC signature over the raw
    body with that clinic's secret — a guessed clinic id without the
    secret is a 401. Unusable events are accepted-and-ignored so a
    misconfigured PBX doesn't retry-storm us.
    """
    settings = await TelephonyService.get_settings(db, clinic_id)
    if settings is None or not settings.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Telephony not configured"
        )

    raw = await request.body()
    secret = decrypt_password(settings.signing_secret_encrypted)
    if not secret or not verify(secret, raw, request.headers.get(SIGNATURE_HEADER, "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    import json

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    row = await TelephonyService.ingest_event(db, settings, payload)
    await db.commit()
    return {"ok": True, "call_log_id": str(row.id) if row else None}
