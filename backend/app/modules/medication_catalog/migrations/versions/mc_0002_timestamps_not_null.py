"""medication_catalog — make the TimestampMixin columns NOT NULL.

``TimestampMixin`` (``app/database.py``) declares ``created_at`` /
``updated_at`` as ``Mapped[datetime]``, i.e. NOT NULL, and fills them
from Python on insert. ``mc_0001`` created the two columns with a
``now()`` server default but without ``nullable=False``, so the table
was the one place where the column could hold NULL while every response
schema types it as a required ``datetime``.

Existing rows are backfilled from the server clock before the ALTER —
in practice there are none, because the ORM has always sent a value.

Revision ID: mc_0002
Revises: mc_0001
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "mc_0002"
down_revision: str | None = "mc_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "medication_catalog_items"
COLUMNS = ("created_at", "updated_at")


def upgrade() -> None:
    for column in COLUMNS:
        op.execute(f"UPDATE {TABLE} SET {column} = now() WHERE {column} IS NULL")  # noqa: S608
        op.alter_column(
            TABLE,
            column,
            existing_type=sa.DateTime(timezone=True),
            existing_server_default=sa.text("now()"),
            nullable=False,
        )


def downgrade() -> None:
    for column in COLUMNS:
        op.alter_column(
            TABLE,
            column,
            existing_type=sa.DateTime(timezone=True),
            existing_server_default=sa.text("now()"),
            nullable=True,
        )
