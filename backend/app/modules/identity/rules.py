"""Pure identity rules: permission catalog, baseline roles, password policy."""

from enum import StrEnum


class ScopeType(StrEnum):
    EDITION = "EDITION"
    TEAM = "TEAM"
    OWNED = "OWNED"
    GATE = "GATE"


# spec 9.1
PERMISSIONS: dict[str, str] = {
    "exhibition.read": "View exhibitions",
    "exhibition.manage": "Create and edit exhibitions",
    "edition.read": "View editions",
    "edition.manage": "Create and edit editions",
    "visitor.read": "View visitor leads",
    "visitor.create": "Create visitor leads",
    "visitor.update": "Edit visitor leads",
    "visitor.import": "Import visitor leads from Excel",
    "visitor.export": "Export visitor leads",
    "visitor.assign": "Assign leads to agents",
    "visitor.verify": "Edit visitor verification",
    "telemarketing.call": "Log call attempts",
    "telemarketing.followup": "Manage follow-ups",
    "telemarketing.view_team": "View the team's telemarketing queue",
    "telemarketing.reassign": "Reassign leads that already have an owner",
    "registration.create": "Register visitors",
    "registration.read": "View registrations",
    "registration.resend_qr": "Resend or revoke QR credentials",
    "gate.scan": "Scan QR codes at a gate",
    "gate.view_history": "View scan history",
    "gate.manage_devices": "Manage gates and scanner devices",
    "gate.override": "Override a gate scan result",
    "report.view": "View reports and dashboard",
    "report.export": "Export reports",
    "user.manage": "Manage users, teams, and role assignments",
    "role.manage": "Edit role permissions",
    "audit_log.read": "Read the audit log",
    "email_account.manage": "Manage email sending accounts",
    "email_log.read": "View the email log",
}

_TM_MANAGER = [
    "exhibition.read",
    "edition.read",
    "visitor.read",
    "visitor.create",
    "visitor.update",
    "visitor.import",
    "visitor.export",
    "visitor.assign",
    "visitor.verify",
    "telemarketing.call",
    "telemarketing.followup",
    "telemarketing.view_team",
    "telemarketing.reassign",
    "registration.create",
    "registration.read",
    "registration.resend_qr",
    "report.view",
    "report.export",
]

BASELINE_ROLES: dict[str, tuple[str, list[str]]] = {
    "SUPER_ADMIN": ("Super Admin", list(PERMISSIONS)),
    "EXHIBITION_ADMIN": (
        "Exhibition Admin",
        [
            p
            for p in PERMISSIONS
            if p not in ("exhibition.manage", "role.manage", "email_account.manage")
        ],
    ),
    "TELEMARKETING_MANAGER": ("Telemarketing Manager", _TM_MANAGER),
    "TELEMARKETING_AGENT": (
        "Telemarketing Agent",
        [
            "exhibition.read",
            "edition.read",
            "visitor.read",
            "visitor.update",
            "visitor.verify",
            "telemarketing.call",
            "telemarketing.followup",
            "registration.create",
            "registration.read",
        ],
    ),
    "GATE_SUPERVISOR": (
        "Gate Supervisor",
        [
            "exhibition.read",
            "edition.read",
            "registration.read",
            "gate.scan",
            "gate.view_history",
            "gate.manage_devices",
            "gate.override",
            "report.view",
        ],
    ),
    "GATE_STAFF": ("Gate Staff", ["edition.read", "gate.scan"]),
}

_COMMON_PASSWORDS = frozenset(
    {
        "password1234",
        "123456789012",
        "qwertyuiop12",
        "passwordpassword",
        "iloveyou1234",
        "admin1234567",
        "welcome12345",
        "changeme1234",
        "letmein12345",
        "password123!",
        "p@ssw0rd1234",
        "qwerty123456",
        "abc123456789",
    }
)


def password_problems(password: str, min_length: int) -> list[str]:
    """Return human-readable policy violations; empty means acceptable."""
    problems: list[str] = []
    if len(password) < min_length:
        problems.append(f"Must be at least {min_length} characters.")
    if password.lower() in _COMMON_PASSWORDS or len(set(password)) < 4:
        problems.append("Password is too common.")
    return problems


def normalize_email(email: str) -> str:
    return email.strip().lower()
