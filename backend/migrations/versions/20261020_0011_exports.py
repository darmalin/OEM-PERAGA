"""exports

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "export_jobs",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("object_key", sa.String(length=100), nullable=True),
        sa.Column("error_summary", sa.String(length=500), nullable=True),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
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
            "kind IN ('VISITORS', 'REPORT')", name=op.f("ck_export_jobs_kind_valid")
        ),
        sa.CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'EXPIRED')",
            name=op.f("ck_export_jobs_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["exhibition_editions.id"],
            name=op.f("fk_export_jobs_edition_id_exhibition_editions"),
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"], ["users.id"], name=op.f("fk_export_jobs_requested_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_export_jobs")),
    )
    op.create_index(
        "ix_export_jobs_edition_created", "export_jobs", ["edition_id", "created_at"], unique=False
    )
    op.create_index(
        "ix_export_jobs_status_expires", "export_jobs", ["status", "expires_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_export_jobs_status_expires", table_name="export_jobs")
    op.drop_index("ix_export_jobs_edition_created", table_name="export_jobs")
    op.drop_table("export_jobs")
