"""Team activation and optimistic locking.

Revision ID: 0024
Revises: 0023
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "teams", sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False)
    )
    op.add_column("teams", sa.Column("version", sa.Integer(), server_default="1", nullable=False))


def downgrade() -> None:
    op.drop_column("teams", "version")
    op.drop_column("teams", "is_active")
