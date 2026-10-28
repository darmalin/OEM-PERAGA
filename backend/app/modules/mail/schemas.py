import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.pagination import Page, PageParams
from app.core.validation import Email
from app.modules.mail.rules import EmailEvent, EmailJobStatus, EmailKind, SmtpSecurity

# --- accounts ------------------------------------------------------------------------------


class EmailAccountIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    from_name: str | None = Field(default=None, max_length=200)
    from_address: Email
    reply_to: Email | None = None
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    security: SmtpSecurity = SmtpSecurity.STARTTLS
    username: str | None = Field(default=None, max_length=320)
    password: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class EmailAccountUpdateIn(BaseModel):
    """Omit `password` (or send null) to keep the stored one; send a value to replace it."""

    model_config = ConfigDict(extra="forbid")

    version: int
    name: str | None = Field(default=None, min_length=1, max_length=100)
    from_name: str | None = Field(default=None, max_length=200)
    from_address: Email | None = None
    reply_to: Email | None = None
    host: str | None = Field(default=None, min_length=1, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    security: SmtpSecurity | None = None
    username: str | None = Field(default=None, max_length=320)
    password: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class EmailAccountOut(BaseModel):
    """No password, ever: only whether one is stored."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    from_name: str | None
    from_address: str
    reply_to: str | None
    host: str
    port: int
    security: SmtpSecurity
    username: str | None
    has_password: bool = False
    is_active: bool
    is_default: bool
    last_test_at: datetime | None
    last_test_ok: bool | None
    last_test_detail: str | None
    version: int


class EmailAccountBrief(BaseModel):
    """For pickers (edition email account): no SMTP details."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    from_address: str
    is_default: bool


# --- log -----------------------------------------------------------------------------------


class EmailLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event: EmailEvent
    detail: str | None
    occurred_at: datetime


class EmailJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: EmailKind
    edition_id: uuid.UUID | None = None
    recipient: str
    subject: str | None = None
    status: EmailJobStatus
    attempts: int
    template_version: int | None
    account_id: uuid.UUID | None = None
    account_name: str | None = None
    from_address: str | None = None
    registration_id: uuid.UUID | None = None
    visitor_lead_id: uuid.UUID | None = None
    queued_at: datetime
    sent_at: datetime | None
    provider_message_id: str | None
    error_summary: str | None
    logs: list[EmailLogOut] = []


class EmailJobListParams(PageParams):
    # None: every edition the caller may read; "system" (super admin) adds emails without one.
    edition_id: uuid.UUID | None = None
    scope: Literal["editions", "system"] = "editions"
    kind: EmailKind | None = None
    status: EmailJobStatus | None = None
    account_id: uuid.UUID | None = None
    q: str | None = Field(default=None, max_length=200)
    queued_from: datetime | None = None
    queued_to: datetime | None = None


class TestEmailAccepted(BaseModel):
    email_job_id: uuid.UUID
    recipient: str


class LeadEmailOut(BaseModel):
    """Visitor-facing email history; excludes account configuration and system-only logs."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: EmailKind
    recipient: str
    subject: str | None
    status: EmailJobStatus
    attempts: int
    from_address: str | None
    queued_at: datetime
    sent_at: datetime | None
    error_summary: str | None


class LeadEmailPage(Page[LeadEmailOut]):
    sent_count: int
    pending_count: int
    failed_count: int
    cancelled_count: int
