"""exhibitor lead permissions for Super Admin and Exhibition Admin

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-03

Phase 2 of docs/EXHIBITOR_LEADS_SALES_PIPELINE.md. Sales staff get them through a custom role.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = {
    "exhibitor_lead.read": "View exhibitor leads",
    "exhibitor_lead.create": "Create exhibitor leads",
    "exhibitor_lead.update": "Edit exhibitor leads and move their sales stage",
}
ROLES = ("SUPER_ADMIN", "EXHIBITION_ADMIN")


def upgrade() -> None:
    # 0002 seeds from the live catalog, so on a fresh database these rows already exist.
    for code, description in PERMISSIONS.items():
        op.execute(
            sa.text(
                "INSERT INTO permissions (id, code, description) "
                "VALUES (gen_random_uuid(), :code, :description) ON CONFLICT (code) DO NOTHING"
            ).bindparams(code=code, description=description)
        )
    op.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT r.id, p.id FROM roles r, permissions p "
            "WHERE r.code = ANY(:roles) AND p.code = ANY(:perms) ON CONFLICT DO NOTHING"
        ).bindparams(roles=list(ROLES), perms=list(PERMISSIONS))
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE code = ANY(:perms))"
        ).bindparams(perms=list(PERMISSIONS))
    )
    op.execute(
        sa.text("DELETE FROM permissions WHERE code = ANY(:perms)").bindparams(
            perms=list(PERMISSIONS)
        )
    )
