"""exhibitor contracts: VAT, payment terms, and the accepted quotation

Revision ID: 0037
Revises: 0036
Create Date: 2026-11-13

Phase 4 of docs/EXHIBITOR_QUOTATIONS.md: an accepted quotation carries its VAT and payment terms
into the contract. Existing contracts get no VAT (rate 0) and no terms.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0037"
down_revision: str | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "exhibitor_contracts",
        sa.Column("vat_rate", sa.Numeric(precision=5, scale=2), server_default="0", nullable=False),
    )
    op.add_column(
        "exhibitor_contracts",
        sa.Column("vat_base_num", sa.Integer(), server_default="11", nullable=False),
    )
    op.add_column(
        "exhibitor_contracts",
        sa.Column("vat_base_den", sa.Integer(), server_default="12", nullable=False),
    )
    op.add_column(
        "exhibitor_contracts",
        sa.Column(
            "vat_amount", sa.Numeric(precision=14, scale=2), server_default="0", nullable=False
        ),
    )
    op.add_column(
        "exhibitor_contracts",
        sa.Column(
            "payment_terms",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column("exhibitor_contracts", sa.Column("quotation_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_exhibitor_contracts_quotation_id_exhibitor_quotations"),
        "exhibitor_contracts",
        "exhibitor_quotations",
        ["quotation_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_exhibitor_contracts_quotation_id_exhibitor_quotations"),
        "exhibitor_contracts",
        type_="foreignkey",
    )
    op.drop_column("exhibitor_contracts", "quotation_id")
    op.drop_column("exhibitor_contracts", "payment_terms")
    op.drop_column("exhibitor_contracts", "vat_amount")
    op.drop_column("exhibitor_contracts", "vat_base_den")
    op.drop_column("exhibitor_contracts", "vat_base_num")
    op.drop_column("exhibitor_contracts", "vat_rate")
