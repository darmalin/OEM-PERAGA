"""exhibitor lead booth price: the price agreed for the held booth

Revision ID: 0035
Revises: 0034
Create Date: 2026-11-13

Phase 1 of docs/EXHIBITOR_QUOTATIONS.md (owner request 2026-11-13): the booth list price is only
the starting point; staff set the price agreed with the company. It goes into the contract at
Convert. Leads already holding a booth start at that booth's current price.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0035"
down_revision: str | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("exhibitor_leads", sa.Column("booth_price", sa.Numeric(14, 2), nullable=True))
    op.execute(
        "UPDATE exhibitor_leads l SET booth_price = b.price FROM booths b WHERE b.id = l.booth_id"
    )
    op.create_check_constraint(
        op.f("ck_exhibitor_leads_booth_price_not_negative"),
        "exhibitor_leads",
        "booth_price IS NULL OR booth_price >= 0",
    )
    # A price belongs to a held booth. A held booth without one uses its list price.
    op.create_check_constraint(
        op.f("ck_exhibitor_leads_booth_price_with_booth"),
        "exhibitor_leads",
        "booth_price IS NULL OR booth_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_exhibitor_leads_booth_price_with_booth"), "exhibitor_leads", type_="check"
    )
    op.drop_constraint(
        op.f("ck_exhibitor_leads_booth_price_not_negative"), "exhibitor_leads", type_="check"
    )
    op.drop_column("exhibitor_leads", "booth_price")
