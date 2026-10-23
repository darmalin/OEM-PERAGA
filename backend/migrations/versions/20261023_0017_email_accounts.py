"""email accounts and one email log for every email

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-23

- email_accounts: SMTP accounts managed in the app (Super Admin), one default for system email.
- email_jobs becomes the log of every email (QR, password reset, follow-up reminder, test):
  edition and template become optional, and each job records the account it went through.
- exhibition_editions.email_account_id: the account an edition's QR emails use.
- Permissions email_account.manage (Super Admin) and email_log.read (Super and Exhibition Admin).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_KINDS_NEW = "kind IN ('QR_CONFIRMATION', 'PASSWORD_RESET', 'FOLLOWUP_REMINDER', 'TEST')"
_KINDS_OLD = "kind IN ('QR_CONFIRMATION')"
# Frozen at this revision: new permission codes and the baseline roles that get them.
_PERMISSIONS = {
    "email_account.manage": ("Manage email sending accounts", ["SUPER_ADMIN"]),
    "email_log.read": ("View the email log", ["SUPER_ADMIN", "EXHIBITION_ADMIN"]),
}


def upgrade() -> None:
    op.create_table(
        "email_accounts",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("from_name", sa.String(length=200), nullable=True),
        sa.Column("from_address", sa.String(length=320), nullable=False),
        sa.Column("reply_to", sa.String(length=320), nullable=True),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("security", sa.String(length=10), nullable=False),
        sa.Column("username", sa.String(length=320), nullable=True),
        sa.Column("password_enc", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("last_test_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_ok", sa.Boolean(), nullable=True),
        sa.Column("last_test_detail", sa.String(length=500), nullable=True),
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
            "security IN ('NONE', 'STARTTLS', 'SSL')", name=op.f("ck_email_accounts_security_valid")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_email_accounts_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], name=op.f("fk_email_accounts_updated_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_accounts")),
        sa.UniqueConstraint("name", name=op.f("uq_email_accounts_name")),
    )
    op.create_index(
        "uq_email_accounts_default",
        "email_accounts",
        ["is_default"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )

    op.alter_column("email_jobs", "edition_id", existing_type=sa.Uuid(), nullable=True)
    op.alter_column("email_jobs", "template_id", existing_type=sa.Uuid(), nullable=True)
    op.alter_column("email_jobs", "template_version", existing_type=sa.Integer(), nullable=True)
    op.add_column("email_jobs", sa.Column("visitor_lead_id", sa.Uuid(), nullable=True))
    op.add_column("email_jobs", sa.Column("user_id", sa.Uuid(), nullable=True))
    op.add_column("email_jobs", sa.Column("subject", sa.String(length=300), nullable=True))
    op.add_column("email_jobs", sa.Column("account_id", sa.Uuid(), nullable=True))
    op.add_column("email_jobs", sa.Column("from_address", sa.String(length=320), nullable=True))
    op.create_foreign_key(
        op.f("fk_email_jobs_visitor_lead_id_visitor_leads"),
        "email_jobs",
        "visitor_leads",
        ["visitor_lead_id"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("fk_email_jobs_user_id_users"), "email_jobs", "users", ["user_id"], ["id"]
    )
    op.create_foreign_key(
        op.f("fk_email_jobs_account_id_email_accounts"),
        "email_jobs",
        "email_accounts",
        ["account_id"],
        ["id"],
    )
    op.drop_constraint(op.f("ck_email_jobs_kind_valid"), "email_jobs", type_="check")
    op.create_check_constraint(op.f("ck_email_jobs_kind_valid"), "email_jobs", _KINDS_NEW)
    op.create_index("ix_email_jobs_queued", "email_jobs", ["queued_at"], unique=False)
    # Existing QR emails: link the lead, so the log can show who an email was for.
    op.execute(
        "UPDATE email_jobs j SET visitor_lead_id = r.visitor_lead_id "
        "FROM visitor_registrations r WHERE r.id = j.registration_id"
    )

    op.add_column("exhibition_editions", sa.Column("email_account_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_exhibition_editions_email_account_id_email_accounts"),
        "exhibition_editions",
        "email_accounts",
        ["email_account_id"],
        ["id"],
    )

    conn = op.get_bind()
    for code, (description, roles) in _PERMISSIONS.items():
        conn.execute(
            sa.text(
                "INSERT INTO permissions (id, code, description) "
                "VALUES (gen_random_uuid(), :code, :d) ON CONFLICT (code) DO NOTHING"
            ),
            {"code": code, "d": description},
        )
        conn.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "SELECT r.id, p.id FROM roles r JOIN permissions p ON p.code = :code "
                "WHERE r.code = ANY(:roles) ON CONFLICT DO NOTHING"
            ),
            {"code": code, "roles": roles},
        )


def downgrade() -> None:
    conn = op.get_bind()
    for code in _PERMISSIONS:
        conn.execute(
            sa.text(
                "DELETE FROM role_permissions WHERE permission_id IN "
                "(SELECT id FROM permissions WHERE code = :code)"
            ),
            {"code": code},
        )
        conn.execute(sa.text("DELETE FROM permissions WHERE code = :code"), {"code": code})
    op.drop_constraint(
        op.f("fk_exhibition_editions_email_account_id_email_accounts"),
        "exhibition_editions",
        type_="foreignkey",
    )
    op.drop_column("exhibition_editions", "email_account_id")
    op.drop_index("ix_email_jobs_queued", table_name="email_jobs")
    # Emails other than QR cannot live in the old table shape.
    op.execute(
        "DELETE FROM email_logs WHERE email_job_id IN "
        "(SELECT id FROM email_jobs WHERE kind <> 'QR_CONFIRMATION')"
    )
    op.execute("DELETE FROM email_jobs WHERE kind <> 'QR_CONFIRMATION'")
    op.drop_constraint(op.f("ck_email_jobs_kind_valid"), "email_jobs", type_="check")
    op.create_check_constraint(op.f("ck_email_jobs_kind_valid"), "email_jobs", _KINDS_OLD)
    for name in ("account_id_email_accounts", "user_id_users", "visitor_lead_id_visitor_leads"):
        op.drop_constraint(op.f(f"fk_email_jobs_{name}"), "email_jobs", type_="foreignkey")
    for column in ("from_address", "account_id", "subject", "user_id", "visitor_lead_id"):
        op.drop_column("email_jobs", column)
    op.alter_column("email_jobs", "template_version", existing_type=sa.Integer(), nullable=False)
    op.alter_column("email_jobs", "template_id", existing_type=sa.Uuid(), nullable=False)
    op.alter_column("email_jobs", "edition_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_index("uq_email_accounts_default", table_name="email_accounts")
    op.drop_table("email_accounts")
