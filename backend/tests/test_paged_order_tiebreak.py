"""Paginated queries must order on a unique key.

``ORDER BY expense_date DESC LIMIT 20 OFFSET 20`` is not a stable slice
when several rows share a date: Postgres' top-N sort returns tied rows in
whatever order the heap leaves them, and that order differs between
``OFFSET 0`` and ``OFFSET 20``. Walking the pages then shows some rows
twice and never shows others. Every paginated ``order_by`` ends on the
primary key so the slice is deterministic.
"""

from __future__ import annotations

import ast
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.expenses.models import Expense
from app.modules.expenses.service import ExpenseService

APP_DIR = Path(__file__).resolve().parents[1] / "app"


def _calls(node: ast.AST, name: str) -> list[ast.Call]:
    return [
        n
        for n in ast.walk(node)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == name
    ]


def _orders_on_id(call: ast.Call) -> bool:
    return any(
        isinstance(n, ast.Attribute) and n.attr == "id" for arg in call.args for n in ast.walk(arg)
    )


def test_every_paginated_query_orders_on_a_unique_key() -> None:
    offenders: list[str] = []
    checked = 0
    for path in sorted(APP_DIR.rglob("*.py")):
        if {"migrations", "seeds"} & set(path.parts):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            offsets = _calls(fn, "offset")
            if not offsets:
                continue
            checked += 1
            if not any(_orders_on_id(call) for call in _calls(fn, "order_by")):
                offenders.append(f"{path.relative_to(APP_DIR)}:{offsets[0].lineno} {fn.name}")
    # Floor: the scan must keep finding the list queries it is guarding.
    assert checked > 40
    assert not offenders, (
        "Paginated query without a primary-key tie-breaker in order_by "
        "(append `<Model>.id`):\n" + "\n".join(offenders)
    )


@pytest.mark.asyncio
async def test_paging_through_same_day_rows_returns_each_row_once(
    db_session: AsyncSession, test_clinic: Clinic
) -> None:
    # A bank-statement import lands many expenses on the same few days.
    days = [date(2026, 9, 1) + timedelta(days=i % 3) for i in range(120)]
    db_session.add_all(
        Expense(clinic_id=test_clinic.id, category="other", amount=Decimal("1"), expense_date=d)
        for d in days
    )
    await db_session.flush()

    seen = []
    page = 1
    while True:
        rows, total = await ExpenseService.list_expenses(
            db_session, test_clinic.id, page=page, page_size=20
        )
        if not rows:
            break
        seen.extend(r.id for r in rows)
        page += 1

    assert total == 120
    assert len(seen) == 120
    assert len(set(seen)) == 120
