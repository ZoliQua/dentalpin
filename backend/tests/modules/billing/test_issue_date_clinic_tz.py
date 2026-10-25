"""An invoice's issue date and the year in its number follow the clinic's
calendar, not the server's.

The server runs on UTC, so ``date.today()`` is a day ahead of a UTC-6
clinic from 18:00 local and a day behind a UTC+2 clinic until 02:00.
Issuing with no explicit date used to stamp the UTC date on the invoice.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.core.utils.dates import clinic_today
from app.modules.billing.models import Invoice, InvoiceItem, InvoiceSeries
from app.modules.billing.service import InvoiceService
from app.modules.billing.workflow import InvoiceWorkflowService
from app.modules.patients.models import Patient


def _zone_off_utc_date() -> str:
    """A zone whose calendar date differs from UTC's right now.

    UTC+14 is a day ahead from 10:00 UTC; UTC-12 is a day behind until
    12:00 UTC, so one of the two always disagrees with the UTC date.
    """
    return "Pacific/Kiritimati" if datetime.now(UTC).hour >= 10 else "Etc/GMT+12"


async def _draft(db: AsyncSession, clinic: Clinic, **series_fields) -> Invoice:
    user_id = (await db.execute(select(User))).scalars().first().id
    patient = Patient(
        id=uuid4(),
        clinic_id=clinic.id,
        first_name="Ana",
        last_name="Pérez",
        national_id="12345678Z",
        national_id_type="dni",
    )
    db.add(patient)
    db.add(
        InvoiceSeries(
            id=uuid4(),
            clinic_id=clinic.id,
            prefix="FAC",
            series_type="invoice",
            is_default=True,
            **series_fields,
        )
    )
    inv = Invoice(
        id=uuid4(),
        clinic_id=clinic.id,
        patient_id=patient.id,
        status="draft",
        subtotal=Decimal("60.00"),
        total=Decimal("60.00"),
        created_by=user_id,
    )
    db.add(inv)
    await db.flush()
    db.add(
        InvoiceItem(
            id=uuid4(),
            clinic_id=clinic.id,
            invoice_id=inv.id,
            description="Limpieza",
            unit_price=Decimal("60.00"),
            quantity=1,
            vat_rate=0.0,
            line_subtotal=Decimal("60.00"),
            line_tax=Decimal("0.00"),
            line_total=Decimal("60.00"),
            display_order=0,
        )
    )
    await db.commit()
    return inv


def test_clinic_today_reads_the_clinic_zone() -> None:
    zone = _zone_off_utc_date()
    assert clinic_today(zone) == datetime.now(ZoneInfo(zone)).date()
    assert clinic_today(zone) != datetime.now(UTC).date()
    # Unknown or missing zones fall back to UTC instead of raising.
    assert clinic_today("Not/AZone") == datetime.now(UTC).date()
    assert clinic_today(None) == datetime.now(UTC).date()


@pytest.mark.asyncio
async def test_issue_without_a_date_uses_the_clinic_calendar(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic, db_session: AsyncSession
) -> None:
    zone = _zone_off_utc_date()
    test_clinic.timezone = zone
    await db_session.commit()
    inv = await _draft(db_session, test_clinic)

    resp = await client.post(
        f"/api/v1/billing/invoices/{inv.id}/issue", json={}, headers=auth_headers
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    local = datetime.now(ZoneInfo(zone)).date()
    assert data["issue_date"] == local.isoformat()
    assert data["invoice_number"].startswith(f"FAC-{local.year}-")


@pytest.mark.asyncio
async def test_number_year_and_issue_date_share_the_clinic_today(
    db_session: AsyncSession, test_clinic: Clinic
) -> None:
    """New Year's Day in the clinic while the server is still on 31 Dec."""
    draft = await _draft(db_session, test_clinic, last_reset_year=2026, current_number=41)
    user_id = (await db_session.execute(select(User))).scalars().first().id
    inv = await InvoiceService.get_invoice(
        db_session, test_clinic.id, draft.id, include_items=True, include_payments=False
    )

    issued = await InvoiceWorkflowService.issue_invoice(
        db_session, inv, user_id, today=date(2027, 1, 1)
    )

    assert issued.issue_date == date(2027, 1, 1)
    assert issued.invoice_number == "FAC-2027-0001"
