"""roles get a list position, highest access first

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-26

Owner request 2026-10-26: role lists and the role picker follow a number the Super Admin
sets. Baseline roles start in order of access; custom roles go after them (100).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Fixed here, not imported: a migration must not change when the app's defaults do.
BASELINE_ORDER = {
    "SUPER_ADMIN": 1,
    "EXHIBITION_ADMIN": 2,
    "TELEMARKETING_MANAGER": 3,
    "TELEMARKETING_AGENT": 4,
    "GATE_SUPERVISOR": 5,
    "GATE_STAFF": 6,
}


def upgrade() -> None:
    op.add_column(
        "roles", sa.Column("sort_order", sa.Integer(), server_default="100", nullable=False)
    )
    for code, order in BASELINE_ORDER.items():
        op.execute(
            sa.text("UPDATE roles SET sort_order = :o WHERE code = :c").bindparams(o=order, c=code)
        )


def downgrade() -> None:
    op.drop_column("roles", "sort_order")
