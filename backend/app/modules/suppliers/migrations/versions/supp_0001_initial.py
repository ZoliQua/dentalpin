"""suppliers: initial schema.

Tables:
    - ``suppliers`` — 1:1 extension of contacts for procurement vendors.

Lives on its own Alembic branch (``suppliers``) per ADR 0002.
Depends on ``contacts`` since the PK is an FK to ``contacts.id``.

Revision ID: supp_0001
Revises:
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "supp_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = ("suppliers",)
depends_on: str | Sequence[str] | None = ("con_0001",)


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("website", sa.String(length=2048), nullable=True),
        sa.Column("payment_terms", sa.String(length=255), nullable=True),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("is_preferred", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["id"], ["contacts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_suppliers_clinic_id", "suppliers", ["clinic_id"])


def downgrade() -> None:
    op.drop_index("ix_suppliers_clinic_id", table_name="suppliers")
    op.drop_table("suppliers")
