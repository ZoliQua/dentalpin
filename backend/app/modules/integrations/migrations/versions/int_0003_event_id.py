"""integrations: add event_id to webhook_deliveries.

Issue #65, Phase 2. ``event_id`` is a stable identifier shared by
every delivery queued for the same source event publish (all
subscriptions that match one bus event get the same ``event_id``),
so a receiver can dedupe (issue #65 §1). Nullable/backfilled with the
delivery's own id at dispatch time when absent (pre-Phase-2 rows).

Revision ID: int_0003
Revises: int_0002
Create Date: 2026-08-30
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
    op.create_index(
        op.f("ix_webhook_deliveries_event_id"), "webhook_deliveries", ["event_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_webhook_deliveries_event_id"), table_name="webhook_deliveries")
    op.drop_column("webhook_deliveries", "event_id")
