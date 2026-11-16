"""exhibitor payments: up to five proof files per payment

Revision ID: 0038
Revises: 0037
Create Date: 2026-11-16

A payment paid in parts comes with one slip per transfer, so a payment now holds a list of proof
files ([{"key", "name"}]) instead of one. An existing proof becomes the first file in the list.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0038"
down_revision: str | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "exhibitor_payments",
        sa.Column(
            "proof_files",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.execute(
        "UPDATE exhibitor_payments SET proof_files = jsonb_build_array(jsonb_build_object("
        "'key', proof_file_key, 'name', 'proof' || substring(proof_file_key from '\\.[^.]+$')))"
        " WHERE proof_file_key IS NOT NULL"
    )
    op.drop_column("exhibitor_payments", "proof_file_key")


def downgrade() -> None:
    op.add_column(
        "exhibitor_payments", sa.Column("proof_file_key", sa.String(length=500), nullable=True)
    )
    # Only the first file fits the old column; the others stay in storage, unlinked.
    op.execute("UPDATE exhibitor_payments SET proof_file_key = proof_files -> 0 ->> 'key'")
    op.drop_column("exhibitor_payments", "proof_files")
