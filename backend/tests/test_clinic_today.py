"""Server-side "today" is the clinic's calendar date (#718).

``date.today()`` is the server's date (UTC in the images). Every check
below uses a zone whose date differs from the server's at the moment the
test runs — UTC+14 and UTC-12 are 26 hours apart, so one of them always
does — so the server's answer and the clinic's always disagree.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.core.utils.dates import clinic_today_for
from app.modules.billing.models import Invoice
from app.modules.billing.service import InvoiceService
from app.modules.patients.models import Patient


def _zone_off_server_date() -> str:
    for zone in ("Pacific/Kiritimati", "Etc/GMT+12"):
        if datetime.now(ZoneInfo(zone)).date() != date.today():
            return zone
    raise AssertionError("unreachable: the two zones are 26 hours apart")


@pytest.mark.asyncio
async def test_clinic_today_for_reads_the_clinic_zone(
    db_session: AsyncSession, test_clinic: Clinic
) -> None:
    zone = _zone_off_server_date()
    test_clinic.timezone = zone
    await db_session.commit()

    assert await clinic_today_for(db_session, test_clinic.id) == datetime.now(ZoneInfo(zone)).date()


@pytest.mark.asyncio
async def test_overdue_invoices_are_judged_by_the_clinic_date(
    db_session: AsyncSession, test_clinic: Clinic
) -> None:
    zone = _zone_off_server_date()
    test_clinic.timezone = zone
    user_id = (await db_session.execute(select(User))).scalars().first().id
    patient = Patient(id=uuid4(), clinic_id=test_clinic.id, first_name="Ana", last_name="Pérez")
    db_session.add(patient)
    clinic_date = datetime.now(ZoneInfo(zone)).date()
    server_date = date.today()
    # Overdue for exactly one of the two clocks: past due for a clinic
    # that is a day ahead, not yet due for one a day behind.
    due = min(clinic_date, server_date)
    db_session.add(
        Invoice(
            id=uuid4(),
            clinic_id=test_clinic.id,
            patient_id=patient.id,
            status="issued",
            invoice_number="FAC-T-0001",
            issue_date=due,
            due_date=due,
            subtotal=Decimal("10.00"),
            total=Decimal("10.00"),
            created_by=user_id,
        )
    )
    await db_session.commit()

    _, total = await InvoiceService.list_invoices(db_session, test_clinic.id, overdue=True)

    assert total == (1 if due < clinic_date else 0)
