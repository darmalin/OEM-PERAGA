"""imports

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_jobs",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("import_type", sa.String(length=30), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.String(length=100), nullable=False),
        sa.Column("column_mapping", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=True),
        sa.Column("checkpoint_row", sa.Integer(), nullable=False),
        sa.Column("processed_count", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("invalid_count", sa.Integer(), nullable=False),
        sa.Column("registered_count", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("errors_object_key", sa.String(length=100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
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
            "import_type IN ('LEADS_ONLY', 'LEADS_AND_REGISTER')",
            name=op.f("ck_import_jobs_import_type_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'COMPLETED_WITH_ERRORS', 'FAILED')",
            name=op.f("ck_import_jobs_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_import_jobs_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["exhibition_editions.id"],
            name=op.f("fk_import_jobs_edition_id_exhibition_editions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_jobs")),
    )
    op.create_index(
        "ix_import_jobs_edition_created", "import_jobs", ["edition_id", "created_at"], unique=False
    )
    op.create_table(
        "import_mapping_presets",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("mapping", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["exhibition_editions.id"],
            name=op.f("fk_import_mapping_presets_edition_id_exhibition_editions"),
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], name=op.f("fk_import_mapping_presets_updated_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_mapping_presets")),
        sa.UniqueConstraint("edition_id", name=op.f("uq_import_mapping_presets_edition_id")),
    )
    op.create_table(
        "import_errors",
        sa.Column("import_job_id", sa.Uuid(), nullable=False),
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("reason_code", sa.String(length=30), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("row_preview", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["exhibition_editions.id"],
            name=op.f("fk_import_errors_edition_id_exhibition_editions"),
        ),
        sa.ForeignKeyConstraint(
            ["import_job_id"],
            ["import_jobs.id"],
            name=op.f("fk_import_errors_import_job_id_import_jobs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_errors")),
    )
    op.create_index(
        op.f("ix_import_errors_edition_id"), "import_errors", ["edition_id"], unique=False
    )
    op.create_index(
        "ix_import_errors_job_row", "import_errors", ["import_job_id", "row_number"], unique=False
    )
    op.execute(
        "CREATE TRIGGER import_errors_append_only BEFORE UPDATE OR DELETE ON import_errors "
        "FOR EACH ROW EXECUTE FUNCTION ems_forbid_mutation()"
    )
    op.add_column("visitor_leads", sa.Column("import_job_id", sa.Uuid(), nullable=True))
    op.create_index(
        op.f("ix_visitor_leads_import_job_id"), "visitor_leads", ["import_job_id"], unique=False
    )
    op.create_foreign_key(
        op.f("fk_visitor_leads_import_job_id_import_jobs"),
        "visitor_leads",
        "import_jobs",
        ["import_job_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_visitor_leads_import_job_id_import_jobs"), "visitor_leads", type_="foreignkey"
    )
    op.drop_index(op.f("ix_visitor_leads_import_job_id"), table_name="visitor_leads")
    op.drop_column("visitor_leads", "import_job_id")
    op.execute("DROP TRIGGER import_errors_append_only ON import_errors")
    op.drop_index("ix_import_errors_job_row", table_name="import_errors")
    op.drop_index(op.f("ix_import_errors_edition_id"), table_name="import_errors")
    op.drop_table("import_errors")
    op.drop_table("import_mapping_presets")
    op.drop_index("ix_import_jobs_edition_created", table_name="import_jobs")
    op.drop_table("import_jobs")
