"""gdpr: single active retention policy per (clinic, category).

``erasure_eligible`` collapses policies by category, so two active rows
for one category gate erasure nondeterministically (#562 RET-01,
advisory ADV-01). The service supersedes on create, but concurrent
creates can both pass the update and insert. This partial unique index
is the backstop: at most one active policy per (clinic, data_category).

Lives on the module's own Alembic branch (``gdpr``).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "gdpr_0002"
down_revision: str | Sequence[str] | None = "gdpr_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Reconcile pre-existing duplicates first: without this, the unique
    # index below aborts the migration (and container boot, which
    # migrates on every start) on any database holding two active rows
    # for one (clinic, category) (#562 ADV-S1-01). Newest wins, the rest
    # stay as history (inactive) — the same rule the service applies.
    op.execute(
        sa.text(
            "UPDATE retention_policies SET is_active = false "
            "WHERE is_active = true AND id NOT IN ("
            "SELECT DISTINCT ON (clinic_id, data_category) id "
            "FROM retention_policies WHERE is_active = true "
            "ORDER BY clinic_id, data_category, updated_at DESC, "
            "created_at DESC, id DESC)"
        )
    )
    op.create_index(
        "ix_retention_policies_clinic_category_active",
        "retention_policies",
        ["clinic_id", "data_category"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_retention_policies_clinic_category_active",
        table_name="retention_policies",
    )
