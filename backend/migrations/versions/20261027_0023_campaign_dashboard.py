"""campaign dashboard: campaign.view permission and daily form opens

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-27

Owner decision 2026-10-27: a Marketing menu with campaign links and their dashboard for
edition managers (Super Admin, Exhibition Admin) and Telemarketing Managers.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLES = ("SUPER_ADMIN", "EXHIBITION_ADMIN", "TELEMARKETING_MANAGER")


def upgrade() -> None:
    op.execute(
        "INSERT INTO permissions (id, code, description) VALUES (gen_random_uuid(), "
        "'campaign.view', 'View campaign links and the campaign dashboard') "
        "ON CONFLICT (code) DO NOTHING"
    )
    op.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT r.id, p.id FROM roles r, permissions p "
            "WHERE r.code = ANY(:roles) AND p.code = 'campaign.view' ON CONFLICT DO NOTHING"
        ).bindparams(roles=list(ROLES))
    )
    op.create_table(
        "campaign_views",
        sa.Column("campaign_link_id", sa.Uuid(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("views", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["campaign_link_id"],
            ["campaign_links.id"],
            name=op.f("fk_campaign_views_campaign_link_id_campaign_links"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("campaign_link_id", "day", name=op.f("pk_campaign_views")),
    )


def downgrade() -> None:
    op.drop_table("campaign_views")
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id = "
        "(SELECT id FROM permissions WHERE code = 'campaign.view')"
    )
    op.execute("DELETE FROM permissions WHERE code = 'campaign.view'")
