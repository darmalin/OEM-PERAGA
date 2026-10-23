"""verification history rows point at their call

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-23

The dashboard counts Valid, Attend, and buyer type per call. A call and its verification are
written in one transaction, so their created_at (transaction time) match: existing rows are
linked by that, once, with the append-only trigger paused for this one data fix.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("visitor_verifications", sa.Column("call_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_visitor_verifications_call_id_visitor_call_activities"),
        "visitor_verifications",
        "visitor_call_activities",
        ["call_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_visitor_verifications_call_id"), "visitor_verifications", ["call_id"], unique=False
    )
    op.execute(
        "ALTER TABLE visitor_verifications DISABLE TRIGGER visitor_verifications_append_only"
    )
    op.execute(
        "UPDATE visitor_verifications v SET call_id = c.id FROM visitor_call_activities c "
        "WHERE c.visitor_lead_id = v.visitor_lead_id AND c.created_at = v.created_at"
    )
    op.execute("ALTER TABLE visitor_verifications ENABLE TRIGGER visitor_verifications_append_only")


def downgrade() -> None:
    op.drop_index(op.f("ix_visitor_verifications_call_id"), table_name="visitor_verifications")
    op.drop_constraint(
        op.f("fk_visitor_verifications_call_id_visitor_call_activities"),
        "visitor_verifications",
        type_="foreignkey",
    )
    op.drop_column("visitor_verifications", "call_id")
