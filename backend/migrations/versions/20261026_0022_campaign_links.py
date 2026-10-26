"""campaign links: public lead forms per edition, with campaign and UTM on the lead

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-26

Owner request 2026-10-26. Replaces the unused website registration endpoint (by edition
code), so editions lose public_registration_open.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UTM = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content")
OLD_SOURCES = "'EXCEL', 'API', 'MANUAL', 'WEBSITE', 'TELEMARKETING'"
OLD_CHANNELS = "'WEBSITE', 'ADMIN', 'TELEMARKETING', 'API', 'IMPORT'"


def upgrade() -> None:
    op.create_table(
        "campaign_links",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("token", sa.String(32), nullable=False),
        sa.Column("lead_source_id", sa.Uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_submissions", sa.Integer(), nullable=True),
        sa.Column("submission_count", sa.Integer(), nullable=False),
        sa.Column("gtm_container_id", sa.String(20), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint("max_submissions IS NULL OR max_submissions > 0", name=op.f("ck_campaign_links_max_submissions_positive")),
        sa.CheckConstraint("starts_at IS NULL OR ends_at IS NULL OR starts_at < ends_at", name=op.f("ck_campaign_links_period_valid")),
        sa.ForeignKeyConstraint(["edition_id"], ["exhibition_editions.id"], name=op.f("fk_campaign_links_edition_id_exhibition_editions")),
        sa.ForeignKeyConstraint(["lead_source_id"], ["lead_sources.id"], name=op.f("fk_campaign_links_lead_source_id_lead_sources")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_campaign_links_created_by_users")),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name=op.f("fk_campaign_links_updated_by_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaign_links")),
        sa.UniqueConstraint("token", name=op.f("uq_campaign_links_token")),
        sa.UniqueConstraint("edition_id", "name", name=op.f("uq_campaign_links_edition_id")),
    )  # fmt: skip
    op.create_index(op.f("ix_campaign_links_edition_id"), "campaign_links", ["edition_id"])

    for col in UTM:
        op.add_column("visitor_leads", sa.Column(col, sa.String(200), nullable=True))
    op.add_column("visitor_leads", sa.Column("campaign_link_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_visitor_leads_campaign_link_id_campaign_links"),
        "visitor_leads",
        "campaign_links",
        ["campaign_link_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_visitor_leads_campaign_link_id"), "visitor_leads", ["campaign_link_id"]
    )

    op.create_table(
        "campaign_submissions",
        sa.Column("campaign_link_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ip_hash", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("consent_version", sa.String(20), nullable=True),
        sa.Column("visitor_lead_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("outcome IN ('CREATED', 'DUPLICATE', 'BOT')", name=op.f("ck_campaign_submissions_outcome_valid")),
        sa.ForeignKeyConstraint(["campaign_link_id"], ["campaign_links.id"], name=op.f("fk_campaign_submissions_campaign_link_id_campaign_links"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["visitor_lead_id"], ["visitor_leads.id"], name=op.f("fk_campaign_submissions_visitor_lead_id_visitor_leads")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaign_submissions")),
    )  # fmt: skip
    op.create_index(
        "ix_campaign_submissions_link_created",
        "campaign_submissions",
        ["campaign_link_id", "created_at"],
    )

    op.drop_constraint(op.f("ck_visitor_leads_source_valid"), "visitor_leads", type_="check")
    op.create_check_constraint(
        "source_valid", "visitor_leads", f"source IN ({OLD_SOURCES}, 'CAMPAIGN')"
    )
    op.drop_constraint(
        op.f("ck_visitor_registrations_channel_valid"), "visitor_registrations", type_="check"
    )
    op.create_check_constraint(
        "channel_valid", "visitor_registrations", f"channel IN ({OLD_CHANNELS}, 'CAMPAIGN')"
    )
    op.drop_column("exhibition_editions", "public_registration_open")


def downgrade() -> None:
    op.add_column(
        "exhibition_editions",
        sa.Column(
            "public_registration_open", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
    )
    # Campaign rows become website rows, the closest older value.
    op.execute("UPDATE visitor_registrations SET channel = 'WEBSITE' WHERE channel = 'CAMPAIGN'")
    op.execute("UPDATE visitor_leads SET source = 'WEBSITE' WHERE source = 'CAMPAIGN'")
    op.drop_constraint(
        op.f("ck_visitor_registrations_channel_valid"), "visitor_registrations", type_="check"
    )
    op.create_check_constraint(
        "channel_valid", "visitor_registrations", f"channel IN ({OLD_CHANNELS})"
    )
    op.drop_constraint(op.f("ck_visitor_leads_source_valid"), "visitor_leads", type_="check")
    op.create_check_constraint("source_valid", "visitor_leads", f"source IN ({OLD_SOURCES})")
    op.drop_index("ix_campaign_submissions_link_created", table_name="campaign_submissions")
    op.drop_table("campaign_submissions")
    op.drop_index(op.f("ix_visitor_leads_campaign_link_id"), table_name="visitor_leads")
    op.drop_constraint(
        op.f("fk_visitor_leads_campaign_link_id_campaign_links"),
        "visitor_leads",
        type_="foreignkey",
    )
    op.drop_column("visitor_leads", "campaign_link_id")
    for col in UTM:
        op.drop_column("visitor_leads", col)
    op.drop_index(op.f("ix_campaign_links_edition_id"), table_name="campaign_links")
    op.drop_table("campaign_links")
