"""teams per edition, and imports that share new leads among them

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-25

Owner request 2026-10-25: an edition has teams; an import can hand its new leads round robin
to the members who may call (telemarketing.call), e.g. 500 leads over 5 callers = 100 each.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "edition_teams",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["edition_id"], ["exhibition_editions.id"], name=op.f("fk_edition_teams_edition_id_exhibition_editions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["team_id"], ["teams.id"], name=op.f("fk_edition_teams_team_id_teams"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_edition_teams_created_by_users")
        ),
        sa.PrimaryKeyConstraint("edition_id", "team_id", name=op.f("pk_edition_teams")),
    )  # fmt: skip
    op.create_index(op.f("ix_edition_teams_team_id"), "edition_teams", ["team_id"])

    op.add_column(
        "import_jobs",
        sa.Column("auto_assign", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "import_jobs",
        sa.Column("assigned_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "import_jobs",
        sa.Column(
            "assign_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )

    op.drop_constraint(
        op.f("ck_lead_assignment_history_method_valid"), "lead_assignment_history", type_="check"
    )
    op.create_check_constraint(
        "method_valid",
        "lead_assignment_history",
        "method IN ('MANUAL', 'BULK', 'ROUND_ROBIN', 'IMPORT')",
    )


def downgrade() -> None:
    # History is append-only; a downgrade relabels import rows as round robin, the closest.
    op.execute(
        "ALTER TABLE lead_assignment_history DISABLE TRIGGER lead_assignment_history_append_only"
    )
    op.execute("UPDATE lead_assignment_history SET method = 'ROUND_ROBIN' WHERE method = 'IMPORT'")
    op.execute(
        "ALTER TABLE lead_assignment_history ENABLE TRIGGER lead_assignment_history_append_only"
    )
    op.drop_constraint(
        op.f("ck_lead_assignment_history_method_valid"), "lead_assignment_history", type_="check"
    )
    op.create_check_constraint(
        "method_valid", "lead_assignment_history", "method IN ('MANUAL', 'BULK', 'ROUND_ROBIN')"
    )
    op.drop_column("import_jobs", "assign_summary")
    op.drop_column("import_jobs", "assigned_count")
    op.drop_column("import_jobs", "auto_assign")
    op.drop_index(op.f("ix_edition_teams_team_id"), table_name="edition_teams")
    op.drop_table("edition_teams")
