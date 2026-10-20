"""exhibitions

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exhibitions",
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
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
            ["created_by"], ["users.id"], name=op.f("fk_exhibitions_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], name=op.f("fk_exhibitions_updated_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exhibitions")),
        sa.UniqueConstraint("code", name=op.f("uq_exhibitions_code")),
    )
    op.create_table(
        "venues",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=True),
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
            ["created_by"], ["users.id"], name=op.f("fk_venues_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], name=op.f("fk_venues_updated_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_venues")),
    )
    op.create_table(
        "exhibition_editions",
        sa.Column("exhibition_id", sa.Uuid(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("venue_id", sa.Uuid(), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("default_currency", sa.String(length=3), nullable=False),
        sa.Column("registration_id_prefix", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("email_sender_name", sa.String(length=200), nullable=True),
        sa.Column("email_reply_to", sa.String(length=320), nullable=True),
        sa.Column("public_registration_open", sa.Boolean(), nullable=False),
        sa.Column("scanner_cache_ttl_minutes", sa.Integer(), nullable=True),
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
            "status IN ('DRAFT', 'ACTIVE', 'CLOSED', 'ARCHIVED')",
            name=op.f("ck_exhibition_editions_status_valid"),
        ),
        sa.CheckConstraint(
            "end_date >= start_date", name=op.f("ck_exhibition_editions_dates_ordered")
        ),
        sa.CheckConstraint(
            "year BETWEEN 2000 AND 2100", name=op.f("ck_exhibition_editions_year_range")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_exhibition_editions_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["exhibition_id"],
            ["exhibitions.id"],
            name=op.f("fk_exhibition_editions_exhibition_id_exhibitions"),
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], name=op.f("fk_exhibition_editions_updated_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["venue_id"], ["venues.id"], name=op.f("fk_exhibition_editions_venue_id_venues")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exhibition_editions")),
        sa.UniqueConstraint("code", name=op.f("uq_exhibition_editions_code")),
        sa.UniqueConstraint(
            "exhibition_id", "year", name=op.f("uq_exhibition_editions_exhibition_id_year")
        ),
    )
    op.create_index(
        op.f("ix_exhibition_editions_exhibition_id"),
        "exhibition_editions",
        ["exhibition_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_exhibition_editions_venue_id"), "exhibition_editions", ["venue_id"], unique=False
    )
    op.create_table(
        "edition_counters",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("last_value", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["exhibition_editions.id"],
            name=op.f("fk_edition_counters_edition_id_exhibition_editions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("edition_id", name=op.f("pk_edition_counters")),
    )
    op.create_foreign_key(
        op.f("fk_audit_logs_edition_id_exhibition_editions"),
        "audit_logs",
        "exhibition_editions",
        ["edition_id"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("fk_user_role_assignments_edition_id_exhibition_editions"),
        "user_role_assignments",
        "exhibition_editions",
        ["edition_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_user_role_assignments_edition_id_exhibition_editions"),
        "user_role_assignments",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_audit_logs_edition_id_exhibition_editions"), "audit_logs", type_="foreignkey"
    )
    op.drop_table("edition_counters")
    op.drop_index(op.f("ix_exhibition_editions_venue_id"), table_name="exhibition_editions")
    op.drop_index(op.f("ix_exhibition_editions_exhibition_id"), table_name="exhibition_editions")
    op.drop_table("exhibition_editions")
    op.drop_table("venues")
    op.drop_table("exhibitions")
