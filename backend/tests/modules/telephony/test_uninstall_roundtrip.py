"""telephony round-trip uninstall test.

Install → uninstall → reinstall must drop ONLY the telephony tables and
leave every other module untouched. Marked ``alembic_roundtrip`` and
excluded from the default pytest run.
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

TELEPHONY_TABLES = {"telephony_settings", "telephony_call_logs"}


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


def test_telephony_uninstall_roundtrip_is_branch_scoped() -> None:
    _alembic("upgrade", "heads")
    before = _list_tables()
    assert TELEPHONY_TABLES.issubset(before), (
        f"expected telephony tables at heads; missing: {TELEPHONY_TABLES - before}"
    )
    baseline_other = before - TELEPHONY_TABLES

    _alembic("downgrade", "telephony@-1")
    after_down = _list_tables()
    assert TELEPHONY_TABLES.isdisjoint(after_down), "uninstall left telephony tables behind"
    assert after_down == baseline_other, "uninstall touched other modules' tables"

    _alembic("upgrade", "heads")
    after_up = _list_tables()
    assert after_up == before, "reinstall did not restore the schema"
