"""Imports every model so Alembic sees the full metadata."""

from app.core.db import Base
from app.core.outbox import OutboxEvent
from app.modules.identity.models import (
    PasswordResetToken,
    Permission,
    Role,
    RolePermission,
    Team,
    User,
    UserRoleAssignment,
    UserTeamMembership,
)

__all__ = [
    "Base",
    "OutboxEvent",
    "PasswordResetToken",
    "Permission",
    "Role",
    "RolePermission",
    "Team",
    "User",
    "UserRoleAssignment",
    "UserTeamMembership",
]
