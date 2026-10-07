"""core — unique membership per clinic+user (#590 follow-up).

``clinic_memberships`` had no unique constraint, so duplicated rows
made membership existence checks blow up with ``MultipleResultsFound``
(500 on control registration until the callers were hardened with
``LIMIT 1``). One row per user per clinic is also the only sane
semantic: the effective role would otherwise be ambiguous.

The backfill keeps the latest-created row per (clinic_id, user_id)
(last write wins, mirroring what an update would have produced) and
drops the rest. NULL created_at (pre-TimestampMixin rows) sorts as
oldest; id breaks ties deterministically.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM clinic_memberships AS doomed "
            "USING clinic_memberships AS keeper "
            "WHERE doomed.clinic_id = keeper.clinic_id "
            "AND doomed.user_id = keeper.user_id "
            "AND ("
            "  COALESCE(doomed.created_at, '-infinity'::timestamptz) < "
            "    COALESCE(keeper.created_at, '-infinity'::timestamptz) "
            "  OR ("
            "    COALESCE(doomed.created_at, '-infinity'::timestamptz) = "
            "      COALESCE(keeper.created_at, '-infinity'::timestamptz) "
            "    AND doomed.id < keeper.id"
            "  )"
            ")"
        )
    )
    op.create_unique_constraint(
        "uq_clinic_memberships_clinic_user",
        "clinic_memberships",
        ["clinic_id", "user_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_clinic_memberships_clinic_user", "clinic_memberships", type_="unique")
