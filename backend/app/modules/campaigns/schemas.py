import uuid
from datetime import date, datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.campaigns.rules import GTM_RE, LinkState
from app.modules.exhibitions.schemas import Country
from app.modules.visitors.rules import CustomFieldType

Utm = Field(default=None, max_length=200)


def _gtm(v: str | None) -> str | None:
    if v is None or not v.strip():
        return None
    v = v.strip().upper()
    if not GTM_RE.match(v):
        raise ValueError("Use a Google Tag Manager container ID like GTM-ABC1234.")
    return v


def _period(starts_at: datetime | None, ends_at: datetime | None) -> None:
    if starts_at is not None and ends_at is not None and ends_at <= starts_at:
        raise ValueError("The end is before the start.")


class CampaignLinkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edition_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    lead_source_id: uuid.UUID | None = None
    is_active: bool = True
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    max_submissions: int | None = Field(default=None, ge=1, le=1_000_000)
    gtm_container_id: str | None = Field(default=None, max_length=20)

    _gtm = field_validator("gtm_container_id")(_gtm)

    @model_validator(mode="after")
    def _check(self) -> Self:
        _period(self.starts_at, self.ends_at)
        return self


class CampaignLinkUpdateIn(BaseModel):
    """Only the fields sent change; null clears an optional one."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    lead_source_id: uuid.UUID | None = None
    is_active: bool | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    max_submissions: int | None = Field(default=None, ge=1, le=1_000_000)
    gtm_container_id: str | None = Field(default=None, max_length=20)
    version: int

    _gtm = field_validator("gtm_container_id")(_gtm)


class CampaignLinkParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edition_id: uuid.UUID | None = None  # None: every edition the caller may read


class CampaignLinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    edition_id: uuid.UUID
    name: str
    token: str
    url: str = ""
    lead_source_id: uuid.UUID | None
    is_active: bool
    starts_at: datetime | None
    ends_at: datetime | None
    max_submissions: int | None
    submission_count: int
    gtm_container_id: str | None
    state: LinkState = LinkState.OPEN
    created_at: datetime
    updated_at: datetime
    version: int


# --- public form (no login) ------------------------------------------------------------------


class PublicEdition(BaseModel):
    name: str
    start_date: date
    end_date: date
    venue_name: str | None
    city: str | None
    country: str | None


class PublicField(BaseModel):
    key: str
    label: str
    type: CustomFieldType
    required: bool
    options: list[str]


class PublicCampaignOut(BaseModel):
    """What the form needs. No campaign name, counts, or other internal settings."""

    edition: PublicEdition
    custom_fields: list[PublicField]
    gtm_container_id: str | None
    consent_version: str
    # Signed load time; the submission must bring it back (bot and replay check).
    ticket: str


class PublicSubmissionIn(BaseModel):
    """Only the form's own fields. Owner, status, source, and the rest are not accepted."""

    model_config = ConfigDict(extra="forbid")

    first_name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    company_name: str | None = Field(default=None, max_length=300)
    job_title: str | None = Field(default=None, max_length=200)
    country: Country | None = None
    city: str | None = Field(default=None, max_length=120)
    custom_fields: dict[str, Any] | None = None
    consent: Literal[True]
    ticket: str = Field(max_length=100)
    utm_source: str | None = Utm
    utm_medium: str | None = Utm
    utm_campaign: str | None = Utm
    utm_term: str | None = Utm
    utm_content: str | None = Utm
    # Honeypot: hidden on the form, so only bots fill it.
    contact_fax: str | None = Field(default=None, max_length=100)


class PublicSubmissionOut(BaseModel):
    """Same answer for new, duplicate, and bot submissions: the form reveals nothing."""

    status: Literal["RECEIVED"] = "RECEIVED"
