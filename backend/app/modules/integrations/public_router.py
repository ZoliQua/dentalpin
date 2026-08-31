"""Token-authenticated public read API — mounted at ``/api/v1/integrations/public/``.

The consumer surface for the ``dp_`` API tokens Phase 1 already issues
(issue #65 §2/§5): Zapier / Make / n8n authenticate with
``Authorization: Bearer dp_…`` — no JWT, no cookie — and read data scoped
to the token's clinic and scopes. Read-only in this slice; write actions
(§4) come with idempotency-key support later.

Lives under the module prefix (``/api/v1/integrations/public/…``) because
a module owns exactly one mount point — the path is part of the public
contract now, so keep it stable.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.router import limiter
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db
from app.modules.patients.models import Patient

from .models import ApiToken
from .schemas import PublicPatientResponse, PublicTokenInfo

public_router = APIRouter()

# One shared limit for the whole public surface; generous enough for a
# polling Zap, tight enough that a runaway loop can't hammer the API.
_RATE = "120/minute"


async def _resolve_token(request: Request, db: AsyncSession) -> ApiToken:
    auth = request.headers.get("Authorization", "")
    scheme, _, credentials = auth.partition(" ")
    if scheme.lower() != "bearer" or not credentials.startswith("dp_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed API token (expected 'Authorization: Bearer dp_…')",
        )
    token_hash = hashlib.sha256(credentials.encode("utf-8")).hexdigest()
    token = (
        await db.execute(select(ApiToken).where(ApiToken.token_hash == token_hash))
    ).scalar_one_or_none()
    if token is None or token.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked API token"
        )
    # Best-effort usage tracking; committed with the request's session.
    token.last_used_at = datetime.now(UTC)
    return token


def require_token(*scopes: str):
    """Dependency: authenticate a ``dp_`` bearer token and check scopes."""

    async def dependency(
        request: Request, db: Annotated[AsyncSession, Depends(get_db)]
    ) -> ApiToken:
        token = await _resolve_token(request, db)
        missing = [s for s in scopes if s not in (token.scopes or [])]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Token lacks required scope(s): {', '.join(missing)}",
            )
        return token

    return dependency


def _public_patient(p: Patient) -> PublicPatientResponse:
    return PublicPatientResponse(
        id=p.id,
        first_name=p.first_name,
        last_name=p.last_name,
        phone=p.phone,
        email=p.email,
        national_id=p.national_id,
        date_of_birth=p.date_of_birth,
        status=p.status,
        created_at=p.created_at,
    )


@public_router.get("/ping", response_model=ApiResponse[PublicTokenInfo])
@limiter.limit(_RATE)
async def ping(
    request: Request,
    token: Annotated[ApiToken, Depends(require_token())],
) -> ApiResponse[PublicTokenInfo]:
    """Token introspection — Zapier's auth test calls this."""
    return ApiResponse(
        data=PublicTokenInfo(
            clinic_id=token.clinic_id, token_name=token.name, scopes=token.scopes or []
        )
    )


@public_router.get("/patients", response_model=PaginatedApiResponse[PublicPatientResponse])
@limiter.limit(_RATE)
async def search_patients(
    request: Request,
    token: Annotated[ApiToken, Depends(require_token("patients:read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    phone: str | None = Query(default=None, max_length=32),
    email: str | None = Query(default=None, max_length=255),
    national_id: str | None = Query(default=None, max_length=50),
    q: str | None = Query(default=None, max_length=100, description="Name substring"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[PublicPatientResponse]:
    """Find patients — powers Zapier's search / search-or-create pattern.

    Exact-ish match on ``phone`` / ``email`` / ``national_id`` (whitespace
    and case tolerant), substring on ``q`` against the full name.
    """
    stmt = select(Patient).where(Patient.clinic_id == token.clinic_id)
    if phone:
        normalized = phone.replace(" ", "").replace("-", "")
        stmt = stmt.where(func.replace(func.replace(Patient.phone, " ", ""), "-", "") == normalized)
    if email:
        stmt = stmt.where(func.lower(Patient.email) == email.strip().lower())
    if national_id:
        stmt = stmt.where(func.upper(Patient.national_id) == national_id.strip().upper())
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                (Patient.first_name + " " + Patient.last_name).ilike(like),
                Patient.first_name.ilike(like),
                Patient.last_name.ilike(like),
            )
        )

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        (
            await db.execute(
                stmt.order_by(Patient.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return PaginatedApiResponse(
        data=[_public_patient(p) for p in rows], total=total, page=page, page_size=page_size
    )


@public_router.get("/patients/{patient_id}", response_model=ApiResponse[PublicPatientResponse])
@limiter.limit(_RATE)
async def get_patient(
    request: Request,
    patient_id: UUID,
    token: Annotated[ApiToken, Depends(require_token("patients:read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[PublicPatientResponse]:
    patient = (
        await db.execute(
            select(Patient).where(Patient.clinic_id == token.clinic_id, Patient.id == patient_id)
        )
    ).scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return ApiResponse(data=_public_patient(patient))
