"""order form allowances: free quantity of a catalog item by booth area

Revision ID: 0033
Revises: 0032
Create Date: 2026-11-09

Phase 6 of docs/EXHIBITOR_ORDER_FORMS.md (decision O9): e.g. parking passes or badges that come
free with the booth, more for larger booths.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "order_form_allowances",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("min_area_sqm", sa.Numeric(8, 2), nullable=False),
        sa.Column("free_quantity", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("min_area_sqm >= 0", name=op.f("ck_order_form_allowances_min_area_not_negative")),
        sa.CheckConstraint("free_quantity > 0", name=op.f("ck_order_form_allowances_free_quantity_positive")),
        sa.ForeignKeyConstraint(["edition_id"], ["exhibition_editions.id"], name=op.f("fk_order_form_allowances_edition_id_exhibition_editions")),
        sa.ForeignKeyConstraint(["item_id", "edition_id"], ["order_form_items.id", "order_form_items.edition_id"], name="fk_order_form_allowances_item_id_order_form_items", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_form_allowances")),
        sa.UniqueConstraint("item_id", "min_area_sqm", name=op.f("uq_order_form_allowances_item_id_min_area_sqm")),
    )  # fmt: skip


def downgrade() -> None:
    op.drop_table("order_form_allowances")
