"""payments for service orders: exhibitor_payments.order_id

Revision ID: 0034
Revises: 0033
Create Date: 2026-11-09

Phase 7 of docs/EXHIBITOR_ORDER_FORMS.md (decision O3): an approved order is paid with the same
payment tagging as the booth contract. A payment points at the contract or at one order; contract
payments are unchanged (every contract payment query filters on contract_id).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("exhibitor_payments", sa.Column("order_id", sa.Uuid(), nullable=True))
    op.alter_column("exhibitor_payments", "contract_id", existing_type=sa.Uuid(), nullable=True)
    op.create_foreign_key(
        "fk_exhibitor_payments_order_id_exhibitor_orders",
        "exhibitor_payments",
        "exhibitor_orders",
        ["order_id", "edition_id"],
        ["id", "edition_id"],
    )
    op.create_index("ix_exhibitor_payments_order_id", "exhibitor_payments", ["order_id"])
    op.create_check_constraint(
        "ck_exhibitor_payments_one_target",
        "exhibitor_payments",
        "num_nonnulls(contract_id, order_id) = 1",
    )


def downgrade() -> None:
    # Irreversible for order payments: they cannot exist without the column. Contract payments
    # are kept as they are.
    op.execute("DELETE FROM exhibitor_payments WHERE order_id IS NOT NULL")
    op.drop_constraint("ck_exhibitor_payments_one_target", "exhibitor_payments", type_="check")
    op.drop_index("ix_exhibitor_payments_order_id", table_name="exhibitor_payments")
    op.drop_constraint(
        "fk_exhibitor_payments_order_id_exhibitor_orders", "exhibitor_payments", type_="foreignkey"
    )
    op.alter_column("exhibitor_payments", "contract_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_column("exhibitor_payments", "order_id")
