"""integrations: stable event id on deliveries.

Issue #65 §1 follow-up: every delivery row carries the id of the *event*
that produced it, shared across all subscriptions, so receivers can
dedupe. Nullable — pre-existing rows keep None and the dispatcher falls
back to the delivery id.

Revision ID: int_0003
Revises: int_0002
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "int_0003"
down_revision: str | None = "int_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("webhook_deliveries", sa.Column("event_id", sa.UUID(), nullable=True))
    op.create_index("ix_webhook_deliveries_event_id", "webhook_deliveries", ["event_id"])


def downgrade() -> None:
    op.drop_index("ix_webhook_deliveries_event_id", table_name="webhook_deliveries")
    op.drop_column("webhook_deliveries", "event_id")
