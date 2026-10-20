"""registrations

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-20
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPEND_ONLY = ("email_templates", "email_logs")

# System default QR email, version 1. A snapshot: later changes are new template versions.
DEFAULT_SUBJECT = "Your entry QR code for {{ edition_name }}"
DEFAULT_TEXT = """Hello {{ first_name }},

You are registered for {{ edition_name }}, {{ start_date }} to {{ end_date }}\
{% if city %} in {{ city }}{% endif %}.

Registration ID: {{ registration_code }}

Show the attached QR code at the entrance gate. The code is personal; do not share it.
"""
DEFAULT_HTML = """<p>Hello {{ first_name }},</p>
<p>You are registered for <strong>{{ edition_name }}</strong>, {{ start_date }} to {{ end_date }}\
{% if city %} in {{ city }}{% endif %}.</p>
<p>Registration ID: <strong>{{ registration_code }}</strong></p>
<p><img src="cid:{{ qr_cid }}" alt="Entry QR code" width="240" height="240"></p>
<p>Show this QR code at the entrance gate. The code is personal; do not share it.</p>
"""


def upgrade() -> None:
    op.create_table(
        "email_templates",
        sa.Column("edition_id", sa.Uuid(), nullable=True),
        sa.Column("template_key", sa.String(length=50), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "template_key IN ('QR_CONFIRMATION')",
            name=op.f("ck_email_templates_template_key_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_email_templates_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["exhibition_editions.id"],
            name=op.f("fk_email_templates_edition_id_exhibition_editions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_templates")),
        sa.UniqueConstraint(
            "edition_id",
            "template_key",
            "version",
            name=op.f("uq_email_templates_edition_id_template_key_version"),
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_table(
        "visitor_registrations",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("visitor_lead_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("registered_by", sa.Uuid(), nullable=True),
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
            "channel IN ('WEBSITE', 'ADMIN', 'TELEMARKETING', 'API', 'IMPORT')",
            name=op.f("ck_visitor_registrations_channel_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('REGISTERED', 'CANCELLED')",
            name=op.f("ck_visitor_registrations_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["exhibition_editions.id"],
            name=op.f("fk_visitor_registrations_edition_id_exhibition_editions"),
        ),
        sa.ForeignKeyConstraint(
            ["registered_by"],
            ["users.id"],
            name=op.f("fk_visitor_registrations_registered_by_users"),
        ),
        sa.ForeignKeyConstraint(
            ["visitor_lead_id"],
            ["visitor_leads.id"],
            name=op.f("fk_visitor_registrations_visitor_lead_id_visitor_leads"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_visitor_registrations")),
    )
    op.create_index(
        "ix_visitor_registrations_edition_registered",
        "visitor_registrations",
        ["edition_id", "registered_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_visitor_registrations_visitor_lead_id"),
        "visitor_registrations",
        ["visitor_lead_id"],
        unique=False,
    )
    op.create_index(
        "uq_visitor_registrations_active_lead",
        "visitor_registrations",
        ["edition_id", "visitor_lead_id"],
        unique=True,
        postgresql_where=sa.text("status = 'REGISTERED'"),
    )
    op.create_table(
        "qr_credentials",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("registration_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_enc", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column(
            "issued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("issued_by", sa.Uuid(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.Uuid(), nullable=True),
        sa.Column("revoke_reason", sa.String(length=500), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "(status = 'REVOKED') = (revoked_at IS NOT NULL)",
            name=op.f("ck_qr_credentials_revoked_at_matches"),
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'REVOKED')", name=op.f("ck_qr_credentials_status_valid")
        ),
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["exhibition_editions.id"],
            name=op.f("fk_qr_credentials_edition_id_exhibition_editions"),
        ),
        sa.ForeignKeyConstraint(
            ["issued_by"], ["users.id"], name=op.f("fk_qr_credentials_issued_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["registration_id"],
            ["visitor_registrations.id"],
            name=op.f("fk_qr_credentials_registration_id_visitor_registrations"),
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by"], ["users.id"], name=op.f("fk_qr_credentials_revoked_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_qr_credentials")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_qr_credentials_token_hash")),
    )
    op.create_index(
        op.f("ix_qr_credentials_edition_id"), "qr_credentials", ["edition_id"], unique=False
    )
    op.create_index(
        op.f("ix_qr_credentials_registration_id"),
        "qr_credentials",
        ["registration_id"],
        unique=False,
    )
    op.create_index(
        "uq_qr_credentials_active_registration",
        "qr_credentials",
        ["registration_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_table(
        "email_jobs",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("registration_id", sa.Uuid(), nullable=True),
        sa.Column("qr_credential_id", sa.Uuid(), nullable=True),
        sa.Column("recipient", sa.String(length=320), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("template_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column(
            "queued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_message_id", sa.String(length=300), nullable=True),
        sa.Column("error_summary", sa.String(length=500), nullable=True),
        sa.Column("triggered_by", sa.Uuid(), nullable=True),
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
        sa.CheckConstraint("kind IN ('QR_CONFIRMATION')", name=op.f("ck_email_jobs_kind_valid")),
        sa.CheckConstraint(
            "status IN ('QUEUED', 'SENDING', 'SENT', 'FAILED', 'CANCELLED')",
            name=op.f("ck_email_jobs_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["exhibition_editions.id"],
            name=op.f("fk_email_jobs_edition_id_exhibition_editions"),
        ),
        sa.ForeignKeyConstraint(
            ["qr_credential_id"],
            ["qr_credentials.id"],
            name=op.f("fk_email_jobs_qr_credential_id_qr_credentials"),
        ),
        sa.ForeignKeyConstraint(
            ["registration_id"],
            ["visitor_registrations.id"],
            name=op.f("fk_email_jobs_registration_id_visitor_registrations"),
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["email_templates.id"],
            name=op.f("fk_email_jobs_template_id_email_templates"),
        ),
        sa.ForeignKeyConstraint(
            ["triggered_by"], ["users.id"], name=op.f("fk_email_jobs_triggered_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_jobs")),
    )
    op.create_index(
        "ix_email_jobs_edition_status", "email_jobs", ["edition_id", "status"], unique=False
    )
    op.create_index(
        "ix_email_jobs_registration", "email_jobs", ["registration_id", "queued_at"], unique=False
    )
    op.create_table(
        "email_logs",
        sa.Column("email_job_id", sa.Uuid(), nullable=False),
        sa.Column("event", sa.String(length=20), nullable=False),
        sa.Column("detail", sa.String(length=500), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["email_job_id"], ["email_jobs.id"], name=op.f("fk_email_logs_email_job_id_email_jobs")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_logs")),
    )
    op.create_index(
        op.f("ix_email_logs_email_job_id"), "email_logs", ["email_job_id"], unique=False
    )
    for table in APPEND_ONLY:
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION ems_forbid_mutation()"
        )
    templates = sa.table(
        "email_templates",
        sa.column("id", sa.Uuid()),
        sa.column("template_key", sa.String()),
        sa.column("version", sa.Integer()),
        sa.column("subject", sa.String()),
        sa.column("body_text", sa.Text()),
        sa.column("body_html", sa.Text()),
    )
    op.bulk_insert(
        templates,
        [
            {
                "id": uuid.UUID("01920000-0000-7000-8000-000000000001"),
                "template_key": "QR_CONFIRMATION",
                "version": 1,
                "subject": DEFAULT_SUBJECT,
                "body_text": DEFAULT_TEXT,
                "body_html": DEFAULT_HTML,
            }
        ],
    )


def downgrade() -> None:
    for table in APPEND_ONLY:
        op.execute(f"DROP TRIGGER {table}_append_only ON {table}")
    op.drop_index(op.f("ix_email_logs_email_job_id"), table_name="email_logs")
    op.drop_table("email_logs")
    op.drop_index("ix_email_jobs_registration", table_name="email_jobs")
    op.drop_index("ix_email_jobs_edition_status", table_name="email_jobs")
    op.drop_table("email_jobs")
    op.drop_index(
        "uq_qr_credentials_active_registration",
        table_name="qr_credentials",
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.drop_index(op.f("ix_qr_credentials_registration_id"), table_name="qr_credentials")
    op.drop_index(op.f("ix_qr_credentials_edition_id"), table_name="qr_credentials")
    op.drop_table("qr_credentials")
    op.drop_index(
        "uq_visitor_registrations_active_lead",
        table_name="visitor_registrations",
        postgresql_where=sa.text("status = 'REGISTERED'"),
    )
    op.drop_index(
        op.f("ix_visitor_registrations_visitor_lead_id"), table_name="visitor_registrations"
    )
    op.drop_index("ix_visitor_registrations_edition_registered", table_name="visitor_registrations")
    op.drop_table("visitor_registrations")
    op.drop_table("email_templates")
