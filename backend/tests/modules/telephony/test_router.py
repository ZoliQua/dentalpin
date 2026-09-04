"""Telephony API: settings secret show-once, HMAC-verified ingest, call log."""

import json

import pytest
from httpx import AsyncClient

from app.core.webhooks.signing import SIGNATURE_HEADER, sign

SETTINGS = "/api/v1/telephony/settings"
CALLS = "/api/v1/telephony/calls"


async def _configure(client: AsyncClient, auth_headers) -> str:
    res = await client.put(SETTINGS, json={"default_country": "ES"}, headers=auth_headers)
    assert res.status_code == 200, res.text
    return res.json()["data"]["signing_secret"]


def _signed(payload: dict, secret: str) -> tuple[bytes, dict]:
    raw = json.dumps(payload).encode()
    return raw, {"Content-Type": "application/json", SIGNATURE_HEADER: sign(secret, raw)}


def _event(call_id="c-1", **kw):
    base = {
        "event": "call.ringing",
        "call_id": call_id,
        "direction": "inbound",
        "from_number": "600 11 22 33",
        "provider": "webhook",
    }
    base.update(kw)
    return base


@pytest.mark.asyncio
async def test_settings_secret_shown_once_and_rotates(
    client: AsyncClient, auth_headers, test_clinic
):
    secret = await _configure(client, auth_headers)
    assert secret.startswith("tel_")

    res = await client.get(SETTINGS, headers=auth_headers)
    body = res.json()["data"]
    assert body["signing_secret"] is None
    assert body["has_signing_secret"] is True
    assert body["webhook_path"].endswith(str(test_clinic.id))

    res = await client.put(SETTINGS, json={"rotate_secret": True}, headers=auth_headers)
    assert res.json()["data"]["signing_secret"] not in (None, secret)


@pytest.mark.asyncio
async def test_ingest_requires_valid_signature(client: AsyncClient, auth_headers, test_clinic):
    secret = await _configure(client, auth_headers)
    url = f"/api/v1/telephony/events/{test_clinic.id}"

    raw, headers = _signed(_event(), "wrong-secret")
    res = await client.post(url, content=raw, headers=headers)
    assert res.status_code == 401

    raw, headers = _signed(_event(), secret)
    res = await client.post(url, content=raw, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["call_log_id"]


@pytest.mark.asyncio
async def test_ingest_unconfigured_clinic_404(client: AsyncClient, test_clinic):
    raw, headers = _signed(_event(), "whatever")
    res = await client.post(
        f"/api/v1/telephony/events/{test_clinic.id}", content=raw, headers=headers
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_call_log_and_active_endpoints(client: AsyncClient, auth_headers, test_clinic):
    secret = await _configure(client, auth_headers)
    url = f"/api/v1/telephony/events/{test_clinic.id}"
    raw, headers = _signed(_event(call_id="c-9"), secret)
    await client.post(url, content=raw, headers=headers)

    res = await client.get(CALLS, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["total"] == 1
    assert res.json()["data"][0]["status"] == "ringing"
    assert res.json()["data"][0]["from_number"] == "+34600112233"

    res = await client.get(f"{CALLS}/active", headers=auth_headers)
    assert res.status_code == 200
    assert len(res.json()["data"]) == 1

    # note write
    call_id = (await client.get(CALLS, headers=auth_headers)).json()["data"][0]["id"]
    res = await client.put(
        f"{CALLS}/{call_id}/note", json={"note": "asked to reschedule"}, headers=auth_headers
    )
    assert res.status_code == 200
    assert res.json()["data"]["note"] == "asked to reschedule"


@pytest.mark.asyncio
async def test_matched_patient_renders_in_log_active_and_note(
    client: AsyncClient, auth_headers, test_clinic
):
    """The headline use case: a known patient calls — their name must
    render on the log, the screen-pop poll, and the note round-trip
    (regression: the lazy ``CallLog.patient`` load raised MissingGreenlet
    in the async request context before eager loading was added)."""
    res = await client.post(
        "/api/v1/patients",
        json={"first_name": "Ana", "last_name": "Llamadora", "phone": "+34600112233"},
        headers=auth_headers,
    )
    assert res.status_code == 201, res.text

    secret = await _configure(client, auth_headers)
    raw, headers = _signed(_event(call_id="c-match"), secret)
    res = await client.post(
        f"/api/v1/telephony/events/{test_clinic.id}", content=raw, headers=headers
    )
    assert res.status_code == 200, res.text

    res = await client.get(CALLS, headers=auth_headers)
    assert res.status_code == 200, res.text
    row = res.json()["data"][0]
    assert row["patient_id"] is not None
    assert row["patient_name"] == "Ana Llamadora"

    res = await client.get(f"{CALLS}/active", headers=auth_headers)
    assert res.status_code == 200, res.text
    assert res.json()["data"][0]["patient_name"] == "Ana Llamadora"

    res = await client.put(
        f"{CALLS}/{row['id']}/note", json={"note": "pidió cita"}, headers=auth_headers
    )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["patient_name"] == "Ana Llamadora"


@pytest.mark.asyncio
async def test_ingest_accepts_and_ignores_unusable_event(
    client: AsyncClient, auth_headers, test_clinic
):
    secret = await _configure(client, auth_headers)
    raw, headers = _signed({"event": "call.exotic", "call_id": "x"}, secret)
    res = await client.post(
        f"/api/v1/telephony/events/{test_clinic.id}", content=raw, headers=headers
    )
    assert res.status_code == 200
    assert res.json()["call_log_id"] is None


@pytest.mark.asyncio
async def test_status_probe(client: AsyncClient, auth_headers, test_clinic):
    res = await client.get("/api/v1/telephony/status", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["data"] == {"active": False}

    await _configure(client, auth_headers)
    res = await client.get("/api/v1/telephony/status", headers=auth_headers)
    assert res.json()["data"] == {"active": True}

    await client.put(SETTINGS, json={"is_active": False}, headers=auth_headers)
    res = await client.get("/api/v1/telephony/status", headers=auth_headers)
    assert res.json()["data"] == {"active": False}
