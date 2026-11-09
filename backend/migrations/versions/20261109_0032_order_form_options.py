"""order form options: the choices of a form's questions

Revision ID: 0032
Revises: 0031
Create Date: 2026-11-09

Phase 5 of docs/EXHIBITOR_ORDER_FORMS.md (decision O10): product categories, stand services,
official contractors and forwarders, and seminar dates, set by staff per form.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "order_form_options",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("form_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("value", sa.String(200), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('OFFICIAL_CONTRACTOR', 'OFFICIAL_FORWARDER', 'PRODUCT_CATEGORY', 'SEMINAR_DATE', 'STAND_SERVICE')",
            name=op.f("ck_order_form_options_kind_valid"),
        ),
        sa.ForeignKeyConstraint(["edition_id"], ["exhibition_editions.id"], name=op.f("fk_order_form_options_edition_id_exhibition_editions")),
        sa.ForeignKeyConstraint(["form_id", "edition_id"], ["order_forms.id", "order_forms.edition_id"], name="fk_order_form_options_form_id_order_forms", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_form_options")),
        sa.UniqueConstraint("form_id", "kind", "value", name=op.f("uq_order_form_options_form_id_kind_value")),
    )  # fmt: skip
    op.create_index(
        "ix_order_form_options_form_kind_sort",
        "order_form_options",
        ["form_id", "kind", "sort_order"],
    )


def downgrade() -> None:
    op.drop_table("order_form_options")
