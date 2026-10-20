"""assignment

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("scope", sa.String(length=200), nullable=False),
        sa.Column("key", sa.String(length=200), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_idempotency_keys")),
        sa.UniqueConstraint("scope", "key", name=op.f("uq_idempotency_keys_scope_key")),
    )
    op.create_index(
        op.f("ix_idempotency_keys_expires_at"), "idempotency_keys", ["expires_at"], unique=False
    )
    op.create_table(
        "assignment_jobs",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("request", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("lead_count", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED')",
            name=op.f("ck_assignment_jobs_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_assignment_jobs_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["exhibition_editions.id"],
            name=op.f("fk_assignment_jobs_edition_id_exhibition_editions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assignment_jobs")),
    )
    op.create_index(
        op.f("ix_assignment_jobs_edition_id"), "assignment_jobs", ["edition_id"], unique=False
    )
    op.create_table(
        "round_robin_cursors",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("pool_key", sa.String(length=64), nullable=False),
        sa.Column("last_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["exhibition_editions.id"],
            name=op.f("fk_round_robin_cursors_edition_id_exhibition_editions"),
        ),
        sa.ForeignKeyConstraint(
            ["last_user_id"], ["users.id"], name=op.f("fk_round_robin_cursors_last_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_round_robin_cursors")),
        sa.UniqueConstraint(
            "edition_id", "pool_key", name=op.f("uq_round_robin_cursors_edition_id_pool_key")
        ),
    )
    op.create_table(
        "lead_assignment_history",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("visitor_lead_id", sa.Uuid(), nullable=False),
        sa.Column("from_user_id", sa.Uuid(), nullable=True),
        sa.Column("to_user_id", sa.Uuid(), nullable=False),
        sa.Column("method", sa.String(length=20), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "method IN ('MANUAL', 'BULK', 'ROUND_ROBIN')",
            name=op.f("ck_lead_assignment_history_method_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_lead_assignment_history_actor_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["exhibition_editions.id"],
            name=op.f("fk_lead_assignment_history_edition_id_exhibition_editions"),
        ),
        sa.ForeignKeyConstraint(
            ["from_user_id"],
            ["users.id"],
            name=op.f("fk_lead_assignment_history_from_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["to_user_id"], ["users.id"], name=op.f("fk_lead_assignment_history_to_user_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["visitor_lead_id"],
            ["visitor_leads.id"],
            name=op.f("fk_lead_assignment_history_visitor_lead_id_visitor_leads"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lead_assignment_history")),
    )
    op.create_index(
        op.f("ix_lead_assignment_history_batch_id"),
        "lead_assignment_history",
        ["batch_id"],
        unique=False,
    )
    op.create_index(
        "ix_lead_assignment_history_edition",
        "lead_assignment_history",
        ["edition_id", "assigned_at"],
        unique=False,
    )
    op.create_index(
        "ix_lead_assignment_history_lead",
        "lead_assignment_history",
        ["visitor_lead_id", "assigned_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lead_assignment_history_to_user_id"),
        "lead_assignment_history",
        ["to_user_id"],
        unique=False,
    )
    op.execute(
        "CREATE TRIGGER lead_assignment_history_append_only BEFORE UPDATE OR DELETE "
        "ON lead_assignment_history FOR EACH ROW EXECUTE FUNCTION ems_forbid_mutation()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER lead_assignment_history_append_only ON lead_assignment_history")
    op.drop_index(
        op.f("ix_lead_assignment_history_to_user_id"), table_name="lead_assignment_history"
    )
    op.drop_index("ix_lead_assignment_history_lead", table_name="lead_assignment_history")
    op.drop_index("ix_lead_assignment_history_edition", table_name="lead_assignment_history")
    op.drop_index(op.f("ix_lead_assignment_history_batch_id"), table_name="lead_assignment_history")
    op.drop_table("lead_assignment_history")
    op.drop_table("round_robin_cursors")
    op.drop_index(op.f("ix_assignment_jobs_edition_id"), table_name="assignment_jobs")
    op.drop_table("assignment_jobs")
    op.drop_index(op.f("ix_idempotency_keys_expires_at"), table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
