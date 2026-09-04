"""telephony: initial schema.

Two tables (own Alembic branch ``telephony`` per ADR 0002, so uninstall
is branch-scoped and drops only these):
    - ``telephony_settings`` — per-clinic gateway secret + defaults.
    - ``telephony_call_logs`` — one row per call, updated across events.

The ``patient_id`` FK to ``patients`` is legal: ``patients`` is in
``manifest.depends``.

Revision ID: tel_0001
Revises:
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "tel_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("telephony",)
# patients lives on its own migration chain; the FK below needs it
# ordered first on a fresh install — same pattern as prel_0001/labo_0001.
depends_on: str | Sequence[str] | None = ("pat_0003",)


def upgrade() -> None:
    op.create_table(
        "telephony_settings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("signing_secret_encrypted", sa.Text(), nullable=False),
        sa.Column("default_country", sa.String(length=2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id"),
    )
    op.create_index("idx_telephony_settings_clinic", "telephony_settings", ["clinic_id"])

    op.create_table(
        "telephony_call_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("call_id", sa.String(length=200), nullable=False),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("from_number", sa.String(length=32), nullable=False),
        sa.Column("to_number", sa.String(length=32), nullable=True),
        sa.Column("agent_extension", sa.String(length=20), nullable=True),
        sa.Column("patient_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id", "provider", "call_id", name="uq_telephony_call"),
    )
    op.create_index("ix_telephony_call_logs_clinic_id", "telephony_call_logs", ["clinic_id"])
    op.create_index("ix_telephony_call_logs_patient_id", "telephony_call_logs", ["patient_id"])
    op.create_index("ix_telephony_call_logs_status", "telephony_call_logs", ["status"])
    op.create_index(
        "idx_telephony_call_logs_clinic_status", "telephony_call_logs", ["clinic_id", "status"]
    )
    op.create_index(
        "idx_telephony_call_logs_clinic_created", "telephony_call_logs", ["clinic_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_telephony_call_logs_clinic_created", table_name="telephony_call_logs")
    op.drop_index("idx_telephony_call_logs_clinic_status", table_name="telephony_call_logs")
    op.drop_index("ix_telephony_call_logs_status", table_name="telephony_call_logs")
    op.drop_index("ix_telephony_call_logs_patient_id", table_name="telephony_call_logs")
    op.drop_index("ix_telephony_call_logs_clinic_id", table_name="telephony_call_logs")
    op.drop_table("telephony_call_logs")
    op.drop_index("idx_telephony_settings_clinic", table_name="telephony_settings")
    op.drop_table("telephony_settings")
