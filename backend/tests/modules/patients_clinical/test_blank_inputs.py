"""A cleared input sends "" -- a typed optional field must save as None (no 422)."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["emergency-contact", "legal-guardian"])
async def test_cleared_email_saves_as_none(
    client: AsyncClient, auth_headers: dict, test_patient, path: str
):
    url = f"/api/v1/patients_clinical/patients/{test_patient.id}/{path}"
    body = {"name": "Ana", "phone": "+34111111", "relationship": "parent"}

    res = await client.put(url, json={**body, "email": "ana@example.com"}, headers=auth_headers)
    assert res.status_code == 200, res.text
    assert res.json()["data"]["email"] == "ana@example.com"

    res = await client.put(url, json={**body, "email": ""}, headers=auth_headers)
    assert res.status_code == 200, res.text
    assert res.json()["data"]["email"] is None


@pytest.mark.asyncio
async def test_cleared_medical_history_inputs_save_as_none(
    client: AsyncClient, auth_headers: dict, test_patient
):
    """The form PUTs the whole history; a cleared number/date input is ""."""
    url = f"/api/v1/patients_clinical/patients/{test_patient.id}/medical-history"
    filled = {
        "is_pregnant": True,
        "pregnancy_week": 20,
        "is_on_anticoagulants": True,
        "inr_value": 2.5,
        "last_inr_date": "2026-10-01",
        "surgical_history": [{"procedure": "Apendicectomía", "surgery_date": "2010-05-01"}],
    }
    res = await client.put(url, json=filled, headers=auth_headers)
    assert res.status_code == 200, res.text

    cleared = {
        **filled,
        "pregnancy_week": "",
        "inr_value": "",
        "last_inr_date": "",
        "surgical_history": [{"procedure": "Apendicectomía", "surgery_date": ""}],
    }
    res = await client.put(url, json=cleared, headers=auth_headers)
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["pregnancy_week"] is None
    assert data["inr_value"] is None
    assert data["last_inr_date"] is None
    assert data["surgical_history"][0]["surgery_date"] is None
