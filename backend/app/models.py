"""Imports every model so Alembic sees the full metadata."""

from app.core.audit import AuditLog
from app.core.db import Base
from app.core.outbox import OutboxEvent
from app.modules.exhibitions.models import Edition, EditionCounter, Exhibition, Venue
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
from app.modules.importexport.models import ImportJob, ImportMappingPreset, ImportRowError
from app.modules.visitors.models import (
    EditionFieldOption,
    VisitorCustomFieldDefinition,
    VisitorLead,
)

__all__ = [
    "AuditLog",
    "Base",
    "Edition",
    "EditionCounter",
    "EditionFieldOption",
    "Exhibition",
    "ImportJob",
    "ImportMappingPreset",
    "ImportRowError",
    "OutboxEvent",
    "PasswordResetToken",
    "Permission",
    "Role",
    "RolePermission",
    "Team",
    "User",
    "UserRoleAssignment",
    "UserTeamMembership",
    "Venue",
    "VisitorCustomFieldDefinition",
    "VisitorLead",
]
