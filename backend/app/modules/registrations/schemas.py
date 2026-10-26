import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.pagination import PageParams
from app.modules.mail.rules import EmailJobStatus
from app.modules.mail.schemas import EmailJobOut
from app.modules.registrations.rules import (
    CredentialStatus,
    RegistrationChannel,
    RegistrationState,
)
from app.modules.visitors.rules import QrStatus

StaffChannel = Literal["ADMIN", "TELEMARKETING", "API"]
# Only the QR email has an editable template; system emails are written in code.
TemplateKey = Literal["QR_CONFIRMATION"]


class RegistrationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visitor_lead_id: uuid.UUID
    channel: StaffChannel = "ADMIN"
    # False registers and issues the QR without emailing it (e.g. printed on site).
    send_email: bool = True


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
    template_key: TemplateKey = "QR_CONFIRMATION"
    subject: str = Field(min_length=1, max_length=300)
    body_text: str = Field(min_length=1, max_length=20_000)
    body_html: str = Field(min_length=1, max_length=50_000)


class EmailTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    edition_id: uuid.UUID | None
    template_key: TemplateKey
    version: int
    subject: str
    body_text: str
    body_html: str
    created_at: datetime
    created_by: uuid.UUID | None


class EmailTemplateParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edition_id: uuid.UUID | None = None
    template_key: TemplateKey = "QR_CONFIRMATION"
