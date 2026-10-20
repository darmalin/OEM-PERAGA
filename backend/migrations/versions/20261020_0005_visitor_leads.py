"""visitor_leads

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "edition_field_options",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("field", sa.String(length=30), nullable=False),
        sa.Column("value", sa.String(length=100), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
        sa.CheckConstraint(
            "field IN ('BUSINESS_TYPE', 'BRANCH', 'EXHIBITION_TYPE', 'PRODUCT_CATEGORY')",
            name=op.f("ck_edition_field_options_field_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["exhibition_editions.id"],
            name=op.f("fk_edition_field_options_edition_id_exhibition_editions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_edition_field_options")),
        sa.UniqueConstraint(
            "edition_id",
            "field",
            "value",
            name=op.f("uq_edition_field_options_edition_id_field_value"),
        ),
    )
    op.create_table(
        "visitor_custom_field_definitions",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("field_key", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("field_type", sa.String(length=20), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("validation", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("in_import", sa.Boolean(), nullable=False),
        sa.Column("in_export", sa.Boolean(), nullable=False),
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
        sa.CheckConstraint(
            "field_type IN ('text', 'textarea', 'number', 'date', 'select', 'multi_select', 'checkbox')",
            name=op.f("ck_visitor_custom_field_definitions_field_type_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_visitor_custom_field_definitions_created_by_users"),
        ),
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["exhibition_editions.id"],
            name=op.f("fk_visitor_custom_field_definitions_edition_id_exhibition_editions"),
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=op.f("fk_visitor_custom_field_definitions_updated_by_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_visitor_custom_field_definitions")),
        sa.UniqueConstraint(
            "edition_id",
            "field_key",
            name=op.f("uq_visitor_custom_field_definitions_edition_id_field_key"),
        ),
    )
    op.create_table(
        "visitor_leads",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("registration_code", sa.String(length=40), nullable=False),
        sa.Column(
            "lead_date", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("first_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("email_normalized", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("phone_normalized", sa.String(length=32), nullable=True),
        sa.Column("gender", sa.String(length=10), nullable=True),
        sa.Column("company_name", sa.String(length=300), nullable=True),
        sa.Column("job_title", sa.String(length=200), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("website", sa.String(length=500), nullable=True),
        sa.Column("business_type", sa.String(length=100), nullable=True),
        sa.Column("branch", sa.String(length=100), nullable=True),
        sa.Column("exhibition_type", sa.String(length=100), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("lead_owner_id", sa.Uuid(), nullable=True),
        sa.Column(
            "product_categories",
            postgresql.ARRAY(sa.String(length=100)),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("is_valid_lead", sa.Boolean(), nullable=False),
        sa.Column("is_invalid", sa.Boolean(), nullable=False),
        sa.Column("attend", sa.String(length=30), nullable=True),
        sa.Column("b2b_matching", sa.Boolean(), nullable=False),
        sa.Column("buyer_type", sa.String(length=10), nullable=True),
        sa.Column("verification_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("telemarketing_status", sa.String(length=20), nullable=False),
        sa.Column("registration_status", sa.String(length=20), nullable=False),
        sa.Column("qr_status", sa.String(length=10), nullable=False),
        sa.Column("call_attempts", sa.Integer(), nullable=False),
        sa.Column("last_call_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_followup_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_source", sa.String(length=50), nullable=True),
        sa.Column("external_id", sa.String(length=100), nullable=True),
        sa.Column(
            "custom_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
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
        sa.CheckConstraint(
            "attend IS NULL OR attend IN ('ATTEND', 'ATTEND_SOURCING', 'UNDER_CONSIDERATION', 'NOT_ATTEND', 'HANG_UP_IMMEDIATELY')",
            name=op.f("ck_visitor_leads_attend_valid"),
        ),
        sa.CheckConstraint(
            "buyer_type IS NULL OR buyer_type IN ('B_SIDE', 'C_SIDE')",
            name=op.f("ck_visitor_leads_buyer_type_valid"),
        ),
        sa.CheckConstraint(
            "gender IS NULL OR gender IN ('MALE', 'FEMALE', 'OTHER')",
            name=op.f("ck_visitor_leads_gender_valid"),
        ),
        sa.CheckConstraint(
            "qr_status IN ('NONE', 'ACTIVE', 'REVOKED')",
            name=op.f("ck_visitor_leads_qr_status_valid"),
        ),
        sa.CheckConstraint(
            "registration_status IN ('NOT_REGISTERED', 'REGISTERED', 'CANCELLED')",
            name=op.f("ck_visitor_leads_registration_status_valid"),
        ),
        sa.CheckConstraint(
            "source IN ('EXCEL', 'API', 'MANUAL', 'WEBSITE', 'TELEMARKETING')",
            name=op.f("ck_visitor_leads_source_valid"),
        ),
        sa.CheckConstraint(
            "telemarketing_status IN ('NEW', 'ANSWER', 'NO_ANSWER', 'RECONTACTED', 'RETRY_NO_ANSWER')",
            name=op.f("ck_visitor_leads_tm_status_valid"),
        ),
        sa.CheckConstraint(
            "NOT (is_valid_lead AND is_invalid)", name=op.f("ck_visitor_leads_valid_xor_invalid")
        ),
        sa.CheckConstraint(
            "email_normalized IS NOT NULL OR phone_normalized IS NOT NULL",
            name=op.f("ck_visitor_leads_email_or_phone"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_visitor_leads_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["exhibition_editions.id"],
            name=op.f("fk_visitor_leads_edition_id_exhibition_editions"),
        ),
        sa.ForeignKeyConstraint(
            ["lead_owner_id"], ["users.id"], name=op.f("fk_visitor_leads_lead_owner_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], name=op.f("fk_visitor_leads_updated_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_visitor_leads")),
        sa.UniqueConstraint(
            "edition_id",
            "registration_code",
            name=op.f("uq_visitor_leads_edition_id_registration_code"),
        ),
    )
    op.create_index(
        "ix_visitor_leads_edition_followup",
        "visitor_leads",
        ["edition_id", "next_followup_at"],
        unique=False,
    )
    op.create_index(
        "ix_visitor_leads_edition_owner",
        "visitor_leads",
        ["edition_id", "lead_owner_id"],
        unique=False,
    )
    op.create_index(
        "ix_visitor_leads_edition_tm_status",
        "visitor_leads",
        ["edition_id", "telemarketing_status"],
        unique=False,
    )
    op.create_index(
        "ix_visitor_leads_edition_updated",
        "visitor_leads",
        ["edition_id", sa.literal_column("updated_at DESC")],
        unique=False,
    )
    op.create_index(
        op.f("ix_visitor_leads_registration_code"),
        "visitor_leads",
        ["registration_code"],
        unique=False,
    )
    op.create_index(
        "uq_visitor_leads_edition_email",
        "visitor_leads",
        ["edition_id", "email_normalized"],
        unique=True,
        postgresql_where=sa.text("email_normalized IS NOT NULL"),
    )
    op.create_index(
        "uq_visitor_leads_edition_external",
        "visitor_leads",
        ["edition_id", "external_source", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )
    op.create_index(
        "uq_visitor_leads_edition_phone",
        "visitor_leads",
        ["edition_id", "phone_normalized"],
        unique=True,
        postgresql_where=sa.text("phone_normalized IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_visitor_leads_edition_phone",
        table_name="visitor_leads",
        postgresql_where=sa.text("phone_normalized IS NOT NULL"),
    )
    op.drop_index(
        "uq_visitor_leads_edition_external",
        table_name="visitor_leads",
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )
    op.drop_index(
        "uq_visitor_leads_edition_email",
        table_name="visitor_leads",
        postgresql_where=sa.text("email_normalized IS NOT NULL"),
    )
    op.drop_index(op.f("ix_visitor_leads_registration_code"), table_name="visitor_leads")
    op.drop_index("ix_visitor_leads_edition_updated", table_name="visitor_leads")
    op.drop_index("ix_visitor_leads_edition_tm_status", table_name="visitor_leads")
    op.drop_index("ix_visitor_leads_edition_owner", table_name="visitor_leads")
    op.drop_index("ix_visitor_leads_edition_followup", table_name="visitor_leads")
    op.drop_table("visitor_leads")
    op.drop_table("visitor_custom_field_definitions")
    op.drop_table("edition_field_options")
