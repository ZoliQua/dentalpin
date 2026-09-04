"""whatsapp_webhook round-trip uninstall test.

Mirrors whatsapp_kapso: install → uninstall → reinstall must drop ONLY the
whatsapp_webhook table and leave every other module untouched. Marked
``alembic_roundtrip`` and excluded from the default pytest run.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import asyncpg
import pytest

from app.config import settings

pytestmark = pytest.mark.alembic_roundtrip

BACKEND_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"

WEBHOOK_TABLES = {"whatsapp_webhook_settings"}


def _alembic(*args: str) -> None:
    subprocess.run(["alembic", "-c", str(ALEMBIC_INI), *args], cwd=BACKEND_ROOT, check=True)


def _dsn() -> str:
    return settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


async def _list_tables_async() -> set[str]:
    conn = await asyncpg.connect(_dsn())
    try:
        rows = await conn.fetch(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name != 'alembic_version'"
        )
        return {row["table_name"] for row in rows}
    finally:
        await conn.close()


def _list_tables() -> set[str]:
    return asyncio.run(_list_tables_async())


def test_whatsapp_webhook_uninstall_roundtrip_is_branch_scoped() -> None:
    _alembic("upgrade", "heads")
    before = _list_tables()
    assert WEBHOOK_TABLES.issubset(before), (
        f"expected whatsapp_webhook tables at heads; missing: {WEBHOOK_TABLES - before}"
    )
    baseline_other = before - WEBHOOK_TABLES

    _alembic("downgrade", "whatsapp_webhook@-1")
    after_down = _list_tables()
    assert WEBHOOK_TABLES.isdisjoint(after_down), "uninstall left whatsapp_webhook tables behind"
    assert after_down == baseline_other, "uninstall touched other modules' tables"

    _alembic("upgrade", "heads")
    after_up = _list_tables()
    assert after_up == before, "reinstall did not restore the schema"
