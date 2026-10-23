"""Pure rules for outgoing email: kinds, delivery states, sending accounts."""

from enum import StrEnum


class EmailKind(StrEnum):
    QR_CONFIRMATION = "QR_CONFIRMATION"
    PASSWORD_RESET = "PASSWORD_RESET"  # noqa: S105 - an email kind, not a secret
    FOLLOWUP_REMINDER = "FOLLOWUP_REMINDER"
    TEST = "TEST"


# Emails about the system itself go through the default account, never an edition's.
SYSTEM_KINDS = frozenset({EmailKind.PASSWORD_RESET, EmailKind.FOLLOWUP_REMINDER})


class EmailJobStatus(StrEnum):
    QUEUED = "QUEUED"
    SENDING = "SENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    # The credential was revoked before the email went out.
    CANCELLED = "CANCELLED"


FINAL_EMAIL_STATUSES = frozenset(
    {EmailJobStatus.SENT, EmailJobStatus.FAILED, EmailJobStatus.CANCELLED}
)


class EmailEvent(StrEnum):
    QUEUED = "QUEUED"
    ATTEMPT = "ATTEMPT"
    SENT = "SENT"
    RETRY = "RETRY"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SmtpSecurity(StrEnum):
    NONE = "NONE"
    STARTTLS = "STARTTLS"
    SSL = "SSL"
