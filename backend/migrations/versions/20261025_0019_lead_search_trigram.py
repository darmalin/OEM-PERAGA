"""trigram indexes for "contains" search on visitor leads

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-25

The list search and the Filter button match text anywhere in a value (LIKE '%x%'), which a
btree index cannot serve. pg_trgm GIN indexes on the same expressions the queries use
(lowercased text, the already-normalized email and phone) keep it fast on large editions.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEXES = {
    "ix_visitor_leads_first_name_trgm": "lower(first_name)",
    "ix_visitor_leads_company_name_trgm": "lower(company_name)",
    "ix_visitor_leads_email_trgm": "email_normalized",
    "ix_visitor_leads_phone_trgm": "phone_normalized",
    "ix_visitor_leads_registration_code_trgm": "lower(registration_code)",
}


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for name, expr in INDEXES.items():
        op.execute(f"CREATE INDEX {name} ON visitor_leads USING gin (({expr}) gin_trgm_ops)")


def downgrade() -> None:
    for name in INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
    # The extension stays: dropping it could break objects created after this revision.
