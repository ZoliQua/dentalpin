"""whatsapp_webhook HTTP surface — mounted at ``/api/v1/whatsapp_webhook/``.

Settings only; unlike kapso there is no inbound endpoint — delivery
status/replies would come back through whatever the clinic's automation
does, which is out of scope for the webhook adapter (the hook is
fire-and-forget by design).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import ClinicContext, get_clinic_context, require_permission
from app.core.schemas import ApiResponse
from app.core.webhooks.url_safety import UnsafeWebhookURLError
from app.database import get_db

from .schemas import WebhookSettingsResponse, WebhookSettingsUpdate, WebhookTestRequest
from .service import WebhookService

router = APIRouter()


def _settings_response(settings, *, secret: str | None = None) -> WebhookSettingsResponse:
    return WebhookSettingsResponse(
        target_url=settings.target_url if settings else None,
        is_active=bool(settings and settings.is_active),
        has_signing_secret=bool(settings and settings.signing_secret_encrypted),
        last_delivery_at=settings.last_delivery_at if settings else None,
        last_error=settings.last_error if settings else None,
        signing_secret=secret,
    )


@router.get("/settings", response_model=ApiResponse[WebhookSettingsResponse])
async def get_settings(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("whatsapp_webhook.settings.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[WebhookSettingsResponse]:
    settings = await WebhookService.get_settings(db, ctx.clinic_id)
    return ApiResponse(data=_settings_response(settings))


@router.put("/settings", response_model=ApiResponse[WebhookSettingsResponse])
async def update_settings(
    data: WebhookSettingsUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("whatsapp_webhook.settings.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[WebhookSettingsResponse]:
    try:
        settings, secret = await WebhookService.upsert_settings(
            db, ctx.clinic_id, data.model_dump()
        )
    except UnsafeWebhookURLError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return ApiResponse(data=_settings_response(settings, secret=secret))


@router.post("/test", response_model=ApiResponse[dict])
async def test_delivery(
    data: WebhookTestRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("whatsapp_webhook.settings.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[dict]:
    ok, error = await WebhookService.send_test(db, ctx.clinic_id, data.to_number)
    return ApiResponse(data={"success": ok, "error": error})
