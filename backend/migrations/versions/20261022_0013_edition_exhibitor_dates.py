"""edition remarks and exhibitor dates (display only)

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-22

From the old system's Exhibition form. Stored and shown now; the Exhibitor Portal phase
(FEATURES/11) gives them meaning.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DATES = (
    "price_regular_from",
    "price_regular_to",
    "price_surcharge_from",
    "price_surcharge_to",
    "price_onsite_from",
    "price_onsite_to",
    "order_expired_on",
    "catalog_expired_on",
)


def upgrade() -> None:
    op.add_column("exhibition_editions", sa.Column("remarks", sa.Text(), nullable=True))
    for name in _DATES:
        op.add_column("exhibition_editions", sa.Column(name, sa.Date(), nullable=True))


def downgrade() -> None:
    for name in reversed(_DATES):
        op.drop_column("exhibition_editions", name)
    op.drop_column("exhibition_editions", "remarks")
