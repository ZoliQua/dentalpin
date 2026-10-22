"""catalog: a deleted treatment frees its internal code.

``uq_catalog_item_clinic_code`` was a full ``UNIQUE (clinic_id,
internal_code)``, but ``CatalogService.delete_item`` is a soft delete
with no restore and the router's duplicate pre-check
(``get_item_by_code``) skips deleted rows. Re-using a deleted item's
code passed the check and failed the INSERT with an unhandled
``IntegrityError`` — a 500, and the code was burned for good (#736).

Replaces the constraint with a partial unique index over live rows
only. The name is kept so anything that asks Postgres about it by name
keeps working. Historical rows (budget lines, plan items, invoices)
reference the deleted item by FK, so a reused code rewrites nothing.

The downgrade restores the full constraint; it fails if a code has
been reused since, which is the state the old constraint cannot hold.

Revision ID: cat_0005
Revises: cat_0004
Create Date: 2026-10-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "cat_0005"
down_revision: str | None = "cat_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_catalog_item_clinic_code", "treatment_catalog_items", type_="unique")
    op.create_index(
        "uq_catalog_item_clinic_code",
        "treatment_catalog_items",
        ["clinic_id", "internal_code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_catalog_item_clinic_code", table_name="treatment_catalog_items")
    op.create_unique_constraint(
        "uq_catalog_item_clinic_code",
        "treatment_catalog_items",
        ["clinic_id", "internal_code"],
    )
