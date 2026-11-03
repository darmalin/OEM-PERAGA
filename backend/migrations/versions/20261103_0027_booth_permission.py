"""booth.manage permission for Super Admin and Exhibition Admin

Revision ID: 0027
Revises: 0026
Create Date: 2026-11-03

Phase 3 of docs/EXHIBITOR_LEADS_SALES_PIPELINE.md.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = {"booth.manage": "Create and edit the booths of an edition"}
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
