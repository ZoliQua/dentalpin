"""``alembic upgrade heads`` produces the columns the models declare.

``test_alembic_roundtrip`` compares two *database* rebuilds against each
other, so it catches a non-deterministic graph but not a migration that
disagrees with ``get_models()``: both rebuilds are equally wrong. Nothing
else closes that loop either — the test suite builds its schema from
metadata, so a column the migrations never create (or create with the
wrong nullability) is invisible until a real deployment runs
``dentalpin db upgrade``.

Alembic can answer the question directly: ``compare_metadata`` diffs the
live schema against ``Base.metadata``. Two tables were drifting when this
was written — ``medication_catalog_items`` and ``treatment_consumables``
had ``created_at`` / ``updated_at`` nullable in the database while
``TimestampMixin`` declares them ``Mapped[datetime]``, i.e. NOT NULL, and
every response schema types them as a required ``datetime``.

**Scope: columns and tables, not indexes.** Index and unique-constraint
differences are reported in bulk by autogenerate for reasons that are not
drift — a single-column ``index=True`` whose migration created a
composite with the same leading column, a unique constraint the model
spells as a unique index, partial and expression indexes it cannot
compare. All 37 ``add_index`` entries on a clean tree were of that shape
(e.g. the model's ``ix_payments_clinic_id`` against the migration's
``idx_payments_clinic_date (clinic_id, payment_date)``, which serves the
same lookups). Asserting on them would mean an allowlist of pure noise;
asserting on columns means every entry is a real finding.

Marked ``alembic_roundtrip``: it rebuilds the schema from scratch, so it
runs in the dedicated CI step after the main suite, like its siblings.
"""

from __future__ import annotations

import asyncio
import importlib
import pkgutil
import subprocess
from pathlib import Path

import asyncpg
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.ext.asyncio import create_async_engine

import app.modules as modules_pkg
from app.config import settings
from app.database import Base

pytestmark = pytest.mark.alembic_roundtrip

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"

# Diff kinds that mean the migrations and the models disagree about the
# shape of a row. Everything else autogenerate reports is index or
# constraint spelling — see the module docstring.
COLUMN_LEVEL = frozenset(
    {"add_table", "remove_table", "add_column", "remove_column", "modify_type", "modify_nullable"}
)


def _sync_dsn() -> str:
    return settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


async def _drop_public_tables() -> None:
    conn = await asyncpg.connect(_sync_dsn())
    try:
        rows = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        for row in rows:
            await conn.execute(f'DROP TABLE IF EXISTS "{row["tablename"]}" CASCADE')
    finally:
        await conn.close()


def _import_every_model() -> None:
    """Populate ``Base.metadata`` — a module not imported is not compared."""
    importlib.import_module("app.core.auth.models")
    for module in sorted(mod.name for mod in pkgutil.iter_modules(modules_pkg.__path__)):
        try:
            importlib.import_module(f"app.modules.{module}.models")
        except ModuleNotFoundError:
            continue


async def _compare() -> list:
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.connect() as conn:
            return await conn.run_sync(
                lambda sync_conn: compare_metadata(
                    MigrationContext.configure(sync_conn), Base.metadata
                )
            )
    finally:
        await engine.dispose()


def _kind(entry: object) -> str:
    """Diff entries are either a tuple or a list of tuples (per-column)."""
    if isinstance(entry, list):
        return _kind(entry[0]) if entry else "empty"
    if isinstance(entry, tuple) and entry and isinstance(entry[0], str):
        return entry[0]
    return "unknown"


def test_migrated_schema_matches_the_models() -> None:
    asyncio.run(_drop_public_tables())
    subprocess.run(
        ["alembic", "-c", str(ALEMBIC_INI), "upgrade", "heads"],
        cwd=BACKEND_ROOT,
        check=True,
    )

    _import_every_model()
    assert len(Base.metadata.tables) > 150, (
        f"model metadata looks wrong: {len(Base.metadata.tables)} tables"
    )

    # No synchronous driver is installed (asyncpg only), and
    # ``compare_metadata`` wants a sync connection — so run it inside
    # ``run_sync`` on the async engine, the same way ``env.py`` runs the
    # migrations themselves.
    diffs = asyncio.run(_compare())

    drift = [entry for entry in diffs if _kind(entry) in COLUMN_LEVEL]
    assert not drift, "\n".join(
        [
            "`alembic upgrade heads` does not produce the schema the models declare:",
            *(f"  {_kind(entry)}: {entry}" for entry in drift),
            "",
            "Add the migration the model is missing (or fix the model). "
            "Index and constraint spelling is out of scope here — see the "
            "module docstring.",
        ]
    )
