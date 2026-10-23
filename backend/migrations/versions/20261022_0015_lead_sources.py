"""lead sources: global master data for the lead "Source" select

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-22

The existing visitor_leads.source (how the lead came in) stays and is labelled "Channel".
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lead_sources",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_lead_sources_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], name=op.f("fk_lead_sources_updated_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lead_sources")),
        sa.UniqueConstraint("name", name=op.f("uq_lead_sources_name")),
    )
    op.add_column("visitor_leads", sa.Column("lead_source_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_visitor_leads_lead_source_id_lead_sources"),
        "visitor_leads",
        "lead_sources",
        ["lead_source_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_visitor_leads_lead_source_id"), "visitor_leads", ["lead_source_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_visitor_leads_lead_source_id", table_name="visitor_leads")
    op.drop_constraint(
        "fk_visitor_leads_lead_source_id_lead_sources", "visitor_leads", type_="foreignkey"
    )
    op.drop_column("visitor_leads", "lead_source_id")
    op.drop_table("lead_sources")
