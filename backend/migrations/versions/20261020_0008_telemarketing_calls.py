"""telemarketing_calls

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPEND_ONLY = ("visitor_call_activities", "visitor_verifications", "visitor_followup_changes")


def upgrade() -> None:
    op.create_table(
        "visitor_call_activities",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("visitor_lead_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("call_result", sa.String(length=30), nullable=False),
        sa.Column("called_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("next_followup_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "attempt_number >= 1", name=op.f("ck_visitor_call_activities_attempt_positive")
        ),
        sa.CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name=op.f("ck_visitor_call_activities_duration_ok"),
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"], ["users.id"], name=op.f("fk_visitor_call_activities_agent_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["exhibition_editions.id"],
            name=op.f("fk_visitor_call_activities_edition_id_exhibition_editions"),
        ),
        sa.ForeignKeyConstraint(
            ["visitor_lead_id"],
            ["visitor_leads.id"],
            name=op.f("fk_visitor_call_activities_visitor_lead_id_visitor_leads"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_visitor_call_activities")),
        sa.UniqueConstraint(
            "visitor_lead_id",
            "attempt_number",
            name=op.f("uq_visitor_call_activities_visitor_lead_id_attempt_number"),
        ),
    )
    op.create_index(
        "ix_visitor_call_activities_agent_called",
        "visitor_call_activities",
        ["agent_id", "called_at"],
        unique=False,
    )
    op.create_index(
        "ix_visitor_call_activities_edition_called",
        "visitor_call_activities",
        ["edition_id", "called_at"],
        unique=False,
    )
    op.create_table(
        "visitor_verifications",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("visitor_lead_id", sa.Uuid(), nullable=False),
        sa.Column("is_valid_lead", sa.Boolean(), nullable=False),
        sa.Column("is_invalid", sa.Boolean(), nullable=False),
        sa.Column("attend", sa.String(length=30), nullable=True),
        sa.Column("b2b_matching", sa.Boolean(), nullable=False),
        sa.Column("buyer_type", sa.String(length=10), nullable=True),
        sa.Column("changed_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "NOT (is_valid_lead AND is_invalid)",
            name=op.f("ck_visitor_verifications_valid_xor_invalid"),
        ),
        sa.ForeignKeyConstraint(
            ["changed_by"], ["users.id"], name=op.f("fk_visitor_verifications_changed_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["exhibition_editions.id"],
            name=op.f("fk_visitor_verifications_edition_id_exhibition_editions"),
        ),
        sa.ForeignKeyConstraint(
            ["visitor_lead_id"],
            ["visitor_leads.id"],
            name=op.f("fk_visitor_verifications_visitor_lead_id_visitor_leads"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_visitor_verifications")),
    )
    op.create_index(
        op.f("ix_visitor_verifications_edition_id"),
        "visitor_verifications",
        ["edition_id"],
        unique=False,
    )
    op.create_index(
        "ix_visitor_verifications_lead",
        "visitor_verifications",
        ["visitor_lead_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "visitor_followups",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("visitor_lead_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_to", sa.Uuid(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_from_call_id", sa.Uuid(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('OPEN', 'DONE', 'CANCELLED')",
            name=op.f("ck_visitor_followups_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to"], ["users.id"], name=op.f("fk_visitor_followups_assigned_to_users")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_visitor_followups_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["created_from_call_id"],
            ["visitor_call_activities.id"],
            name=op.f("fk_visitor_followups_created_from_call_id_visitor_call_activities"),
        ),
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["exhibition_editions.id"],
            name=op.f("fk_visitor_followups_edition_id_exhibition_editions"),
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], name=op.f("fk_visitor_followups_updated_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["visitor_lead_id"],
            ["visitor_leads.id"],
            name=op.f("fk_visitor_followups_visitor_lead_id_visitor_leads"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_visitor_followups")),
    )
    op.create_index(
        "ix_visitor_followups_assignee_due",
        "visitor_followups",
        ["assigned_to", "status", "due_at"],
        unique=False,
    )
    op.create_index(
        "ix_visitor_followups_edition_status_due",
        "visitor_followups",
        ["edition_id", "status", "due_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_visitor_followups_visitor_lead_id"),
        "visitor_followups",
        ["visitor_lead_id"],
        unique=False,
    )
    op.create_table(
        "followup_reminders",
        sa.Column("dedup_key", sa.String(length=120), nullable=False),
        sa.Column("followup_id", sa.Uuid(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["followup_id"],
            ["visitor_followups.id"],
            name=op.f("fk_followup_reminders_followup_id_visitor_followups"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_followup_reminders")),
        sa.UniqueConstraint("dedup_key", name=op.f("uq_followup_reminders_dedup_key")),
    )
    op.create_index(
        op.f("ix_followup_reminders_followup_id"),
        "followup_reminders",
        ["followup_id"],
        unique=False,
    )
    op.create_table(
        "visitor_followup_changes",
        sa.Column("followup_id", sa.Uuid(), nullable=False),
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("old_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("new_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_visitor_followup_changes_actor_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["exhibition_editions.id"],
            name=op.f("fk_visitor_followup_changes_edition_id_exhibition_editions"),
        ),
        sa.ForeignKeyConstraint(
            ["followup_id"],
            ["visitor_followups.id"],
            name=op.f("fk_visitor_followup_changes_followup_id_visitor_followups"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_visitor_followup_changes")),
    )
    op.create_index(
        op.f("ix_visitor_followup_changes_followup_id"),
        "visitor_followup_changes",
        ["followup_id"],
        unique=False,
    )
    for table in APPEND_ONLY:
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION ems_forbid_mutation()"
        )


def downgrade() -> None:
    for table in APPEND_ONLY:
        op.execute(f"DROP TRIGGER {table}_append_only ON {table}")
    op.drop_index(
        op.f("ix_visitor_followup_changes_followup_id"), table_name="visitor_followup_changes"
    )
    op.drop_table("visitor_followup_changes")
    op.drop_index(op.f("ix_followup_reminders_followup_id"), table_name="followup_reminders")
    op.drop_table("followup_reminders")
    op.drop_index(op.f("ix_visitor_followups_visitor_lead_id"), table_name="visitor_followups")
    op.drop_index("ix_visitor_followups_edition_status_due", table_name="visitor_followups")
    op.drop_index("ix_visitor_followups_assignee_due", table_name="visitor_followups")
    op.drop_table("visitor_followups")
    op.drop_index("ix_visitor_verifications_lead", table_name="visitor_verifications")
    op.drop_index(op.f("ix_visitor_verifications_edition_id"), table_name="visitor_verifications")
    op.drop_table("visitor_verifications")
    op.drop_index("ix_visitor_call_activities_edition_called", table_name="visitor_call_activities")
    op.drop_index("ix_visitor_call_activities_agent_called", table_name="visitor_call_activities")
    op.drop_table("visitor_call_activities")
