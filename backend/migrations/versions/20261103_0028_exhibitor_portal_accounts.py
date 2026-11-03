"""exhibitor portal accounts, contract number counter, exhibitor.invite permission

Revision ID: 0028
Revises: 0027
Create Date: 2026-11-03

Phase 4 of docs/EXHIBITOR_LEADS_SALES_PIPELINE.md. Owner decisions 2026-11-03: accounts
are created by an invitation link (no email needed), the portal has its own subdomain in
production, contract numbers are generated per edition.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSION = ("exhibitor.invite", "Convert exhibitor leads and issue portal invitation links")
ROLES = ("SUPER_ADMIN", "EXHIBITION_ADMIN")


def upgrade() -> None:
    op.create_table(
        "exhibitor_accounts",
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("email_normalized", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invite_token_hash", sa.String(64), nullable=True),
        sa.Column("invite_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint("(invite_token_hash IS NULL) = (invite_expires_at IS NULL)", name=op.f("ck_exhibitor_accounts_invite_complete")),
        sa.CheckConstraint("activated_at IS NULL OR password_hash IS NOT NULL", name=op.f("ck_exhibitor_accounts_activated_has_password")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_exhibitor_accounts_created_by_users")),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name=op.f("fk_exhibitor_accounts_updated_by_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exhibitor_accounts")),
        sa.UniqueConstraint("email_normalized", name=op.f("uq_exhibitor_accounts_email_normalized")),
    )  # fmt: skip
    op.create_index(
        "uq_exhibitor_accounts_invite_token_hash",
        "exhibitor_accounts",
        ["invite_token_hash"],
        unique=True,
        postgresql_where=sa.text("invite_token_hash IS NOT NULL"),
    )

    op.add_column("exhibitor_leads", sa.Column("exhibitor_account_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_exhibitor_leads_exhibitor_account_id_exhibitor_accounts"),
        "exhibitor_leads",
        "exhibitor_accounts",
        ["exhibitor_account_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_exhibitor_leads_exhibitor_account_id"),
        "exhibitor_leads",
        ["exhibitor_account_id"],
    )
    op.create_index(
        "uq_exhibitor_leads_edition_account",
        "exhibitor_leads",
        ["edition_id", "exhibitor_account_id"],
        unique=True,
        postgresql_where=sa.text("exhibitor_account_id IS NOT NULL"),
    )
    # Fails if an EXHIBITOR row without an account exists; none can, conversion starts here.
    op.create_check_constraint(
        "exhibitor_has_account",
        "exhibitor_leads",
        "stage <> 'EXHIBITOR' OR exhibitor_account_id IS NOT NULL",
    )

    op.create_table(
        "exhibitor_contract_counters",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["exhibition_editions.id"],
            name=op.f("fk_exhibitor_contract_counters_edition_id_exhibition_editions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("edition_id", name=op.f("pk_exhibitor_contract_counters")),
    )

    code, description = PERMISSION
    op.execute(
        sa.text(
            "INSERT INTO permissions (id, code, description) "
            "VALUES (gen_random_uuid(), :code, :description) ON CONFLICT (code) DO NOTHING"
        ).bindparams(code=code, description=description)
    )
    op.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT r.id, p.id FROM roles r, permissions p "
            "WHERE r.code = ANY(:roles) AND p.code = :code ON CONFLICT DO NOTHING"
        ).bindparams(roles=list(ROLES), code=code)
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id = "
            "(SELECT id FROM permissions WHERE code = :code)"
        ).bindparams(code=PERMISSION[0])
    )
    op.execute(sa.text("DELETE FROM permissions WHERE code = :code").bindparams(code=PERMISSION[0]))
    op.drop_table("exhibitor_contract_counters")
    op.drop_constraint(
        op.f("ck_exhibitor_leads_exhibitor_has_account"), "exhibitor_leads", type_="check"
    )
    op.drop_index("uq_exhibitor_leads_edition_account", table_name="exhibitor_leads")
    op.drop_index(op.f("ix_exhibitor_leads_exhibitor_account_id"), table_name="exhibitor_leads")
    op.drop_constraint(
        op.f("fk_exhibitor_leads_exhibitor_account_id_exhibitor_accounts"),
        "exhibitor_leads",
        type_="foreignkey",
    )
    op.drop_column("exhibitor_leads", "exhibitor_account_id")
    op.drop_table("exhibitor_accounts")
