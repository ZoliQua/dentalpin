"""A duplicate series prefix is a 409, not a 500.

``invoice_series`` carries one unique constraint,
``uq_invoice_series_clinic_prefix`` on ``(clinic_id, prefix)``. Neither
``POST /series`` nor ``PUT /series/{id}`` checked for the collision and
neither caught ``IntegrityError``, so renaming a series onto an existing
prefix — or creating one twice — returned 500 with the raw asyncpg
message in the body. Found by a generated-request sweep of the write
surface, then reproduced by hand on both verbs.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.auth.models import Clinic


@pytest.mark.asyncio
async def test_create_series_with_taken_prefix_is_conflict(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
):
    first = await client.post(
        "/api/v1/billing/series",
        json={"prefix": "DUP", "series_type": "invoice"},
        headers=auth_headers,
    )
    assert first.status_code == 201, first.text

    again = await client.post(
        "/api/v1/billing/series",
        json={"prefix": "DUP", "series_type": "invoice"},
        headers=auth_headers,
    )
    assert again.status_code == 409, again.text
    assert "DUP" in again.text


@pytest.mark.asyncio
async def test_create_series_with_taken_prefix_ignores_series_type(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
):
    # The constraint is (clinic_id, prefix) — not (clinic_id, prefix,
    # series_type) — so a credit-note series cannot borrow an invoice
    # series' prefix either.
    created = await client.post(
        "/api/v1/billing/series",
        json={"prefix": "SHARED", "series_type": "invoice"},
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text

    clash = await client.post(
        "/api/v1/billing/series",
        json={"prefix": "SHARED", "series_type": "credit_note"},
        headers=auth_headers,
    )
    assert clash.status_code == 409, clash.text


@pytest.mark.asyncio
async def test_rename_series_onto_taken_prefix_is_conflict(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
):
    a = await client.post(
        "/api/v1/billing/series",
        json={"prefix": "AAA", "series_type": "invoice"},
        headers=auth_headers,
    )
    b = await client.post(
        "/api/v1/billing/series",
        json={"prefix": "BBB", "series_type": "invoice"},
        headers=auth_headers,
    )
    assert a.status_code == 201 and b.status_code == 201
    b_id = b.json()["data"]["id"]

    clash = await client.put(
        f"/api/v1/billing/series/{b_id}",
        json={"prefix": "AAA"},
        headers=auth_headers,
    )
    assert clash.status_code == 409, clash.text
    assert "AAA" in clash.text

    # The rejected rename left the row alone.
    listing = await client.get("/api/v1/billing/series", headers=auth_headers)
    prefixes = {s["prefix"] for s in listing.json()["data"]}
    assert {"AAA", "BBB"} <= prefixes


@pytest.mark.asyncio
async def test_rename_series_to_a_free_prefix_still_works(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
):
    created = await client.post(
        "/api/v1/billing/series",
        json={"prefix": "OLD", "series_type": "invoice"},
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    series_id = created.json()["data"]["id"]

    renamed = await client.put(
        f"/api/v1/billing/series/{series_id}",
        json={"prefix": "NEW"},
        headers=auth_headers,
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["prefix"] == "NEW"
