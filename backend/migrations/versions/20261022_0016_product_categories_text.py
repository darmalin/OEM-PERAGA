"""product categories become free text

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-22

Owner decision 2026-10-22: "Product Categories Interested In" is free text, like the old system.
Existing multi-select values become their option labels joined with ", ", in the stored order.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("visitor_leads", sa.Column("product_categories_text", sa.Text(), nullable=True))
    op.execute(
        """
        UPDATE visitor_leads l
        SET product_categories_text = (
            SELECT string_agg(coalesce(o.label, c.v), ', ' ORDER BY c.ord)
            FROM unnest(l.product_categories) WITH ORDINALITY AS c(v, ord)
            LEFT JOIN edition_field_options o
              ON o.edition_id = l.edition_id AND o.field = 'PRODUCT_CATEGORY' AND o.value = c.v
        )
        WHERE cardinality(l.product_categories) > 0
        """
    )
    op.drop_column("visitor_leads", "product_categories")
    op.alter_column(
        "visitor_leads", "product_categories_text", new_column_name="product_categories"
    )


def downgrade() -> None:
    """Back to an array of the comma-separated parts (labels, not the original option values)."""
    op.add_column(
        "visitor_leads",
        sa.Column(
            "product_categories_array",
            postgresql.ARRAY(sa.String(length=100)),
            server_default="{}",
            nullable=False,
        ),
    )
    op.execute(
        """
        UPDATE visitor_leads
        SET product_categories_array = string_to_array(product_categories, ', ')::varchar(100)[]
        WHERE product_categories IS NOT NULL
        """
    )
    op.drop_column("visitor_leads", "product_categories")
    op.alter_column(
        "visitor_leads", "product_categories_array", new_column_name="product_categories"
    )
