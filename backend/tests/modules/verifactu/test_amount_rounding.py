"""A Veri*Factu record declares the cent the invoice row actually holds.

``invoices.total`` and ``invoice_items.line_tax`` are ``NUMERIC(_, 2)``
columns, so PostgreSQL rounds every value written to them *half away
from zero*. The fiscal record is built from the same figures in Python,
and the amount it declares is one of the eight fields hashed into the
``Huella`` — a chain that cannot be rewritten once AEAT accepts it.

The two sides therefore have to round a half-cent the same way, and the
``Decimal`` default does not: ``Decimal("9.085").quantize(Decimal("0.01"))``
is ``9.08`` (``ROUND_HALF_EVEN``) while the column stores ``9.09``. The
same bias sits in ``f"{d:.2f}"``.

The live issue path reloads the invoice in a fresh session, so the values
reaching the hook are already the rounded ones from the database and the
bias has no fractional input to act on. That is a property of the current
call order, not a guarantee — ``_build_desglose`` takes whatever ORM
object it is handed, and a caller that builds and issues in one session
hands it unrounded lines. These tests pin the rounding itself, so the
fiscal record cannot drift a cent away from the invoice if that call
order ever changes.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth.models import Clinic, User
from app.modules.billing.models import Invoice, InvoiceItem
from app.modules.billing.service import InvoiceService
from app.modules.patients.models import Patient
from app.modules.verifactu.hook import _build_desglose, _format_amount
from app.modules.verifactu.services import hash_chain

# (value, the cent PostgreSQL stores for it in a NUMERIC(_, 2) column).
# Measured against PostgreSQL 16, not derived from the docs:
#   select 9.085::numeric(12,2)   -> 9.09
#   select (-9.085)::numeric(12,2) -> -9.09
HALF_CENTS: list[tuple[str, str]] = [
    ("9.085", "9.09"),
    ("6.055", "6.06"),
    ("1.585", "1.59"),
    ("2.645", "2.65"),
    ("0.005", "0.01"),
    # Credit-note lines are negative; "half up" has to mean away from
    # zero on that side too, which is what PostgreSQL does.
    ("-9.085", "-9.09"),
    ("-0.005", "-0.01"),
]


@pytest.mark.parametrize(("raw", "stored"), HALF_CENTS)
def test_declared_amount_is_the_cent_postgres_stores(raw: str, stored: str) -> None:
    assert _format_amount(Decimal(raw)) == Decimal(stored)


@pytest.mark.parametrize(("raw", "stored"), HALF_CENTS)
def test_huella_formats_the_same_cent(raw: str, stored: str) -> None:
    """The hashed string and the declared amount cannot disagree."""
    assert hash_chain._format_amount(Decimal(raw)) == f"{Decimal(stored):.2f}"


def test_the_cases_above_actually_separate_the_two_modes() -> None:
    """Keeps the parametrization load-bearing.

    ``6.055`` rounds to ``6.06`` under either mode — a table of only such
    values would pass no matter which mode the code picked. This asserts
    some case still tells them apart, so the suite cannot quietly stop
    covering the bug.
    """

    diverging = [
        raw
        for raw, _ in HALF_CENTS
        if Decimal(raw).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        != Decimal(raw).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    ]
    assert diverging, "no case here distinguishes half-up from half-even"


def test_float_input_takes_the_same_route() -> None:
    """``_format_amount`` accepts floats; they must not skip the mode."""
    assert _format_amount(9.085) == Decimal("9.09")


@pytest.mark.asyncio
@pytest.mark.parametrize("n_lines", [2, 3, 5])
async def test_desglose_declares_the_stored_invoice_total(
    db_session: AsyncSession, n_lines: int
) -> None:
    """End to end, with the lines still unrounded in the session.

    Three lines of 2.50 EUR at 21% owe 0.525 of tax each, so the totals
    carry a half-cent. ``recalculate_totals`` leaves the last line
    unrounded in the identity map, which is the state a caller that
    builds and issues in one session would pass to the hook — the
    arrangement this test fixes in place. ``ImporteTotal`` has to be the
    cent PostgreSQL stored, and the desglose has to add up to it, or AEAT
    rejects the record.
    """

    clinic_id, patient_id, user_id = uuid4(), uuid4(), uuid4()
    today = date(2026, 6, 15)

    db_session.add(Clinic(id=clinic_id, name="Rounding", tax_id="B12345678"))
    db_session.add(
        User(
            id=user_id,
            email=f"u-{user_id}@x.test",
            password_hash="x",
            first_name="A",
            last_name="B",
            is_active=True,
        )
    )
    await db_session.flush()
    db_session.add(
        Patient(
            id=patient_id,
            clinic_id=clinic_id,
            first_name="Ana",
            last_name="Gil",
            status="active",
        )
    )
    invoice = Invoice(
        clinic_id=clinic_id,
        patient_id=patient_id,
        status="draft",
        issue_date=today,
        due_date=today,
        created_by=user_id,
    )
    db_session.add(invoice)
    await db_session.flush()

    for n in range(n_lines):
        item = InvoiceItem(
            clinic_id=clinic_id,
            invoice_id=invoice.id,
            description=f"Linea {n}",
            unit_price=Decimal("2.50"),
            quantity=1,
            vat_rate=21.0,
        )
        db_session.add(item)
        await InvoiceService.calculate_item_totals(item)
    await db_session.flush()
    await InvoiceService.recalculate_totals(db_session, invoice)

    lines, cuota_total, importe_total = _build_desglose(invoice)

    # The row as the database holds it, read back through a query that
    # repopulates the instance rather than trusting the identity map.
    stored = (
        await db_session.execute(
            select(Invoice)
            .options(selectinload(Invoice.items))
            .where(Invoice.id == invoice.id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    stored_tax = sum((i.line_tax for i in stored.items), Decimal("0"))

    assert importe_total == stored.total
    assert cuota_total == stored_tax
    declared = sum((line.base_imponible for line in lines), Decimal("0")) + sum(
        ((line.cuota_repercutida or Decimal("0")) for line in lines), Decimal("0")
    )
    assert declared == importe_total


def test_already_rounded_amounts_are_untouched() -> None:
    """The fix must not move any amount that was already on a cent.

    Every huella recorded before this change was computed over
    two-decimal values; if quantizing them moved anything, existing
    chains would stop validating.
    """
    for raw in ("0.00", "21.00", "121.00", "9.09", "-9.09", "1234567.89"):
        assert _format_amount(Decimal(raw)) == Decimal(raw)
        assert hash_chain._format_amount(Decimal(raw)) == f"{Decimal(raw):.2f}"
