"""whatsapp_webhook: initial schema.

One table (own Alembic branch ``whatsapp_webhook`` per ADR 0002, so
uninstall is branch-scoped and drops only this):
    - ``whatsapp_webhook_settings`` — per-clinic hook URL + signing secret.

Revision ID: wwh_0001
Revises:
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "wwh_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("whatsapp_webhook",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_webhook_settings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=False),
        sa.Column("target_url", sa.Text(), nullable=False),
        sa.Column("signing_secret_encrypted", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_delivery_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id"),
    )
    op.create_index(
        "idx_whatsapp_webhook_settings_clinic", "whatsapp_webhook_settings", ["clinic_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_whatsapp_webhook_settings_clinic", table_name="whatsapp_webhook_settings")
    op.drop_table("whatsapp_webhook_settings")
