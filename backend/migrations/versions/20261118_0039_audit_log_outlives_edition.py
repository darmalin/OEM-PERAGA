"""audit log keeps its edition id after the edition is deleted

Revision ID: 0039
Revises: 0038
Create Date: 2026-11-18

Editions can now be deleted while nothing links to them, but every edition already has audit
rows (its own create) and the audit log is append-only, so the foreign key would block every
delete. The column stays, without the constraint: like entity_id, it records which edition the
change belonged to, even after that edition is gone.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0039"
down_revision: str | None = "0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("fk_audit_logs_edition_id_exhibition_editions"), "audit_logs", type_="foreignkey"
    )


def downgrade() -> None:
    # NOT VALID: audit rows of deleted editions remain and would fail the check.
    op.execute(
        "ALTER TABLE audit_logs ADD CONSTRAINT fk_audit_logs_edition_id_exhibition_editions "
        "FOREIGN KEY (edition_id) REFERENCES exhibition_editions (id) NOT VALID"
    )
