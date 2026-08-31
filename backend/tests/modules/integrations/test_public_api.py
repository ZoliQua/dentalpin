"""Public read API (dp_ bearer tokens), trigger catalog, stable event ids."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email.encryption import encrypt_password
from app.modules.integrations.handlers import IntegrationsHandlers
from app.modules.integrations.models import ApiToken, WebhookDelivery, WebhookSubscription
from app.modules.integrations.service import IntegrationsService
from app.modules.integrations.triggers import SAMPLE_PAYLOADS, SUPPORTED_EVENT_TYPES
from app.modules.patients.models import Patient

PING = "/api/v1/integrations/public/ping"
PATIENTS = "/api/v1/integrations/public/patients"


async def _token(db, clinic_id, *, scopes=("patients:read",)) -> str:
    _, plaintext = await IntegrationsService.create_token(
        db, clinic_id, {"name": "zap", "scopes": list(scopes)}
    )
    await db.commit()
    return plaintext


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _patient(db, clinic_id, **kw) -> Patient:
    fields = dict(
        clinic_id=clinic_id,
        first_name="Ana",
        last_name="García",
        phone="+34 600 11 22 33",
        email="Ana@Example.com",
        national_id="12345678Z",
    )
    fields.update(kw)
    p = Patient(**fields)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


# --- auth ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_ping_introspects_token(client: AsyncClient, db_session, test_clinic):
    token = await _token(db_session, test_clinic.id)
    res = await client.get(PING, headers=_auth(token))
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["clinic_id"] == str(test_clinic.id)
    assert data["scopes"] == ["patients:read"]


@pytest.mark.asyncio
async def test_bad_and_revoked_tokens_are_401(client: AsyncClient, db_session, test_clinic):
    res = await client.get(PING, headers=_auth("dp_not-a-real-token"))
    assert res.status_code == 401

    res = await client.get(PING)  # no header at all
    assert res.status_code == 401

    token = await _token(db_session, test_clinic.id)
    row = (await db_session.execute(select(ApiToken))).scalars().first()
    row.revoked_at = datetime.now(UTC)
    await db_session.commit()
    res = await client.get(PING, headers=_auth(token))
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_missing_scope_is_403(client: AsyncClient, db_session, test_clinic):
    token = await _token(db_session, test_clinic.id, scopes=())
    res = await client.get(PATIENTS, headers=_auth(token))
    assert res.status_code == 403
    assert "patients:read" in res.json()["message"]


# --- patient search ------------------------------------------------------


@pytest.mark.asyncio
async def test_search_by_phone_is_format_tolerant(client: AsyncClient, db_session, test_clinic):
    await _patient(db_session, test_clinic.id)
    token = await _token(db_session, test_clinic.id)

    res = await client.get(PATIENTS, params={"phone": "+34600112233"}, headers=_auth(token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] == 1
    assert body["data"][0]["first_name"] == "Ana"


@pytest.mark.asyncio
async def test_search_by_email_and_nif_case_insensitive(
    client: AsyncClient, db_session, test_clinic
):
    p = await _patient(db_session, test_clinic.id)
    token = await _token(db_session, test_clinic.id)

    res = await client.get(PATIENTS, params={"email": "ana@example.com"}, headers=_auth(token))
    assert res.json()["total"] == 1

    res = await client.get(PATIENTS, params={"national_id": "12345678z"}, headers=_auth(token))
    assert res.json()["total"] == 1

    res = await client.get(f"{PATIENTS}/{p.id}", headers=_auth(token))
    assert res.status_code == 200
    assert res.json()["data"]["id"] == str(p.id)


@pytest.mark.asyncio
async def test_search_no_match_and_unknown_id_404(client: AsyncClient, db_session, test_clinic):
    token = await _token(db_session, test_clinic.id)
    res = await client.get(PATIENTS, params={"phone": "+34999999999"}, headers=_auth(token))
    assert res.json()["total"] == 0

    res = await client.get(f"{PATIENTS}/00000000-0000-0000-0000-000000000000", headers=_auth(token))
    assert res.status_code == 404


# --- trigger catalog -----------------------------------------------------


def test_every_supported_trigger_has_a_frozen_sample():
    assert set(SAMPLE_PAYLOADS) == set(SUPPORTED_EVENT_TYPES)
    for event_type, sample in SAMPLE_PAYLOADS.items():
        assert "clinic_id" in sample, event_type
        assert "occurred_at" in sample, event_type


@pytest.mark.asyncio
async def test_triggers_endpoint_serves_catalog(client: AsyncClient, auth_headers, test_clinic):
    res = await client.get("/api/v1/integrations/webhooks/triggers", headers=auth_headers)
    assert res.status_code == 200, res.text
    rows = res.json()["data"]
    assert {r["event_type"] for r in rows} == set(SUPPORTED_EVENT_TYPES)
    assert all(r["sample_payload"].get("clinic_id") for r in rows)


# --- stable event id -----------------------------------------------------


@pytest.mark.asyncio
async def test_one_event_id_shared_across_subscribers(db_session: AsyncSession, test_clinic):
    for n in (1, 2):
        db_session.add(
            WebhookSubscription(
                clinic_id=test_clinic.id,
                target_url=f"https://example.com/hook{n}",
                event_types=["patient.created"],
                secret_encrypted=encrypt_password("whsec"),
            )
        )
    await db_session.commit()

    await IntegrationsHandlers.on_patient_created(
        {"clinic_id": str(test_clinic.id), "patient_id": "p1"}, db=db_session
    )
    await db_session.commit()

    rows = (await db_session.execute(select(WebhookDelivery))).scalars().all()
    assert len(rows) == 2
    assert rows[0].event_id is not None
    assert rows[0].event_id == rows[1].event_id
    assert rows[0].id != rows[1].id
