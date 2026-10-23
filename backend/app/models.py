"""Imports every model so Alembic sees the full metadata."""

from app.core.audit import AuditLog
from app.core.db import Base
from app.core.idempotency import IdempotencyKey
from app.core.outbox import OutboxEvent
from app.modules.checkin.models import Gate, ScanAttempt, ScannerDevice, VisitorCheckin
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
from app.modules.importexport.models import (
    ExportJob,
    ImportJob,
    ImportMappingPreset,
    ImportRowError,
)
from app.modules.registrations.models import (
    EmailJob,
    EmailLog,
    EmailTemplate,
    QrCredential,
    VisitorRegistration,
)
from app.modules.telemarketing.models import (
    AssignmentJob,
    FollowupReminder,
    LeadAssignmentHistory,
    RoundRobinCursor,
    VisitorCallActivity,
    VisitorFollowup,
    VisitorFollowupChange,
    VisitorVerification,
)
from app.modules.visitors.models import (
    EditionFieldOption,
    LeadSourceOption,
    VisitorCustomFieldDefinition,
    VisitorLead,
)

__all__ = [
    "AssignmentJob",
    "AuditLog",
    "Base",
    "Edition",
    "EditionCounter",
    "EditionFieldOption",
    "EmailJob",
    "EmailLog",
    "EmailTemplate",
    "Exhibition",
    "ExportJob",
    "FollowupReminder",
    "Gate",
    "IdempotencyKey",
    "ImportJob",
    "ImportMappingPreset",
    "ImportRowError",
    "LeadAssignmentHistory",
    "LeadSourceOption",
    "OutboxEvent",
    "PasswordResetToken",
    "Permission",
    "QrCredential",
    "Role",
    "RolePermission",
    "RoundRobinCursor",
    "ScanAttempt",
    "ScannerDevice",
    "Team",
    "User",
    "UserRoleAssignment",
    "UserTeamMembership",
    "Venue",
    "VisitorCallActivity",
    "VisitorCheckin",
    "VisitorCustomFieldDefinition",
    "VisitorFollowup",
    "VisitorFollowupChange",
    "VisitorLead",
    "VisitorRegistration",
    "VisitorVerification",
]
