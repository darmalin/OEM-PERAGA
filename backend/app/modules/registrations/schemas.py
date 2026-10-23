import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.pagination import PageParams
from app.modules.exhibitions.schemas import Country
from app.modules.registrations.rules import (
    CredentialStatus,
    EmailEvent,
    EmailJobStatus,
    EmailKind,
    RegistrationChannel,
    RegistrationState,
)
from app.modules.visitors.rules import QrStatus
from app.modules.visitors.schemas import Website

StaffChannel = Literal["ADMIN", "TELEMARKETING", "API"]


class RegistrationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visitor_lead_id: uuid.UUID
    channel: StaffChannel = "ADMIN"
    # False registers and issues the QR without emailing it (e.g. printed on site).
    send_email: bool = True


class EmailLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event: EmailEvent
    detail: str | None
    occurred_at: datetime


class EmailJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: EmailKind
    recipient: str
    status: EmailJobStatus
    attempts: int
    template_version: int
    queued_at: datetime
    sent_at: datetime | None
    provider_message_id: str | None
    error_summary: str | None
    logs: list[EmailLogOut] = []


class CredentialOut(BaseModel):
    """Never includes the token or its hash."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: CredentialStatus
    issued_at: datetime
    revoked_at: datetime | None
    revoke_reason: str | None


class RegistrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    edition_id: uuid.UUID
    visitor_lead_id: uuid.UUID
    registration_code: str
    first_name: str
    channel: RegistrationChannel
    status: RegistrationState
    registered_at: datetime
    registered_by: uuid.UUID | None
    qr_status: QrStatus
    email_status: EmailJobStatus | None = None
    version: int


class RegistrationDetailOut(RegistrationOut):
    credentials: list[CredentialOut] = []
    email_jobs: list[EmailJobOut] = []


class RegistrationListParams(PageParams):
    edition_id: uuid.UUID
    visitor_lead_id: uuid.UUID | None = None
    channel: RegistrationChannel | None = None
    qr_status: QrStatus | None = None
    email_status: EmailJobStatus | None = None
    q: str | None = Field(default=None, max_length=200)


class RevokeQrIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)
    # Issue a new credential right away (spec 7.2: rotating means revoke old + issue new).
    reissue: bool = False
    send_email: bool = True


class EmailTemplateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # None = system default (needs global edition.manage).
    edition_id: uuid.UUID | None = None
    template_key: EmailKind = EmailKind.QR_CONFIRMATION
    subject: str = Field(min_length=1, max_length=300)
    body_text: str = Field(min_length=1, max_length=20_000)
    body_html: str = Field(min_length=1, max_length=50_000)


class EmailTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    edition_id: uuid.UUID | None
    template_key: EmailKind
    version: int
    subject: str
    body_text: str
    body_html: str
    created_at: datetime
    created_by: uuid.UUID | None


class EmailTemplateParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edition_id: uuid.UUID | None = None
    template_key: EmailKind = EmailKind.QR_CONFIRMATION


class PublicRegistrationIn(BaseModel):
    """Website form. `contact_fax` is a honeypot: the form hides it, bots fill it."""

    model_config = ConfigDict(extra="forbid")

    first_name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    company_name: str | None = Field(default=None, max_length=300)
    job_title: str | None = Field(default=None, max_length=200)
    country: Country | None = None
    city: str | None = Field(default=None, max_length=120)
    website: Website = Field(default=None, max_length=500)
    product_categories: str | None = Field(default=None, max_length=2000)
    custom_fields: dict[str, Any] | None = None
    contact_fax: str | None = Field(default=None, max_length=100)


class PublicRegistrationAccepted(BaseModel):
    """Same answer for new and duplicate visitors, so the form never reveals who exists."""

    status: Literal["RECEIVED"] = "RECEIVED"
    message: str = (
        "Thank you. If the details are valid, a confirmation email with your QR code will follow."
    )
