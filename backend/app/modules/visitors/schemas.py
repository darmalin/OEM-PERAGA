import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.core.pagination import PageParams
from app.modules.exhibitions.schemas import Country
from app.modules.visitors.rules import (
    FIELD_KEY_RE,
    Attend,
    BuyerType,
    CustomFieldType,
    Gender,
    LeadSource,
    OptionField,
    QrStatus,
    RegistrationStatus,
    TelemarketingStatus,
)

Text200 = Annotated[str, Field(max_length=200)]
Text300 = Annotated[str, Field(max_length=300)]


def _website(v: str | None) -> str | None:
    if v is None or not v.strip():
        return None
    v = v.strip()
    candidate = v if "://" in v else f"https://{v}"
    HttpUrl(candidate)  # raises on garbage
    return v


Website = Annotated[str | None, AfterValidator(_website)]


class LeadFields(BaseModel):
    """Editable Person fields. Email/phone are raw strings; the service normalizes them."""

    model_config = ConfigDict(extra="forbid")

    lead_date: datetime | None = None
    first_name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    gender: Gender | None = None
    company_name: Text300 | None = None
    job_title: Text200 | None = None
    country: Country | None = None
    city: str | None = Field(default=None, max_length=120)
    website: Website = Field(default=None, max_length=500)
    business_type: str | None = Field(default=None, max_length=100)
    branch: str | None = Field(default=None, max_length=100)
    exhibition_type: str | None = Field(default=None, max_length=100)
    product_categories: str | None = Field(default=None, max_length=2000)
    comment: str | None = Field(default=None, max_length=5000)
    lead_source_id: uuid.UUID | None = None
    custom_fields: dict[str, Any] | None = None


class LeadCreateIn(LeadFields):
    edition_id: uuid.UUID
    first_name: str = Field(min_length=1, max_length=200)
    source: LeadSource = LeadSource.MANUAL
    external_source: str | None = Field(default=None, max_length=50)
    external_id: str | None = Field(default=None, max_length=100)


class LeadUpdateIn(LeadFields):
    version: int

    @field_validator("first_name")
    @classmethod
    def _not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("First Name is required.")
        return v


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    edition_id: uuid.UUID
    registration_code: str
    lead_date: datetime
    first_name: str
    email: str | None
    phone: str | None
    phone_normalized: str | None
    gender: Gender | None
    company_name: str | None
    job_title: str | None
    country: str | None
    city: str | None
    website: str | None
    business_type: str | None
    branch: str | None
    exhibition_type: str | None
    source: LeadSource
    lead_source_id: uuid.UUID | None
    lead_owner_id: uuid.UUID | None
    lead_owner_name: str | None = None
    product_categories: str | None
    comment: str | None
    is_valid_lead: bool
    is_invalid: bool
    attend: Attend | None
    b2b_matching: bool
    buyer_type: BuyerType | None
    verification_updated_at: datetime | None
    telemarketing_status: TelemarketingStatus
    registration_status: RegistrationStatus
    qr_status: QrStatus
    call_attempts: int
    last_call_at: datetime | None
    next_followup_at: datetime | None
    external_source: str | None
    external_id: str | None
    custom_fields: dict[str, Any]
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    version: int


class LeadListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    edition_id: uuid.UUID
    registration_code: str
    lead_date: datetime
    first_name: str
    email: str | None
    phone: str | None
    company_name: str | None
    country: str | None
    source: LeadSource
    lead_source_id: uuid.UUID | None
    lead_owner_id: uuid.UUID | None
    lead_owner_name: str | None = None
    telemarketing_status: TelemarketingStatus
    registration_status: RegistrationStatus
    qr_status: QrStatus
    is_valid_lead: bool
    is_invalid: bool
    attend: Attend | None
    last_call_at: datetime | None
    next_followup_at: datetime | None
    updated_at: datetime


SORTABLE = (
    "lead_date",
    "created_at",
    "updated_at",
    "first_name",
    "registration_code",
    "company_name",
    "last_call_at",
    "next_followup_at",
)
SortParam = Literal[
    "lead_date", "-lead_date", "created_at", "-created_at", "updated_at", "-updated_at",
    "first_name", "-first_name", "registration_code", "-registration_code",
    "company_name", "-company_name", "last_call_at", "-last_call_at",
    "next_followup_at", "-next_followup_at",
]  # fmt: skip


class LeadFilters(BaseModel):
    """Filters shared by the list, assignments by filter, reports, and exports."""

    model_config = ConfigDict(extra="forbid")

    q: str | None = Field(default=None, max_length=200)
    telemarketing_status: list[TelemarketingStatus] | None = None
    registration_status: RegistrationStatus | None = None
    qr_status: QrStatus | None = None
    lead_owner_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    unassigned: bool | None = None
    source: LeadSource | None = None
    lead_source_id: uuid.UUID | None = None
    country: str | None = Field(default=None, max_length=2)
    is_valid_lead: bool | None = None
    is_invalid: bool | None = None
    attend: Attend | None = None
    buyer_type: BuyerType | None = None
    lead_date_from: datetime | None = None
    lead_date_to: datetime | None = None


class LeadListParams(PageParams, LeadFilters):
    # None: every edition the caller may read (the Exhibition Type filter set to All).
    edition_id: uuid.UUID | None = None
    sort: SortParam = "-updated_at"


# --- custom field definitions ----------------------------------------------------------------


def _field_key(v: str) -> str:
    if not FIELD_KEY_RE.match(v):
        raise ValueError("Use lowercase letters, digits, and underscores, starting with a letter.")
    return v


class CustomFieldIn(BaseModel):
    edition_id: uuid.UUID
    field_key: Annotated[str, AfterValidator(_field_key)]
    label: str = Field(min_length=1, max_length=200)
    field_type: CustomFieldType
    required: bool = False
    options: list[Annotated[str, Field(min_length=1, max_length=100)]] = []
    validation: dict[str, Any] = {}
    sort_order: int = 0
    is_active: bool = True
    in_import: bool = True
    in_export: bool = True


class CustomFieldUpdateIn(BaseModel):
    version: int
    label: str | None = Field(default=None, min_length=1, max_length=200)
    required: bool | None = None
    options: list[Annotated[str, Field(min_length=1, max_length=100)]] | None = None
    validation: dict[str, Any] | None = None
    sort_order: int | None = None
    is_active: bool | None = None
    in_import: bool | None = None
    in_export: bool | None = None


class CustomFieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    edition_id: uuid.UUID
    field_key: str
    label: str
    field_type: CustomFieldType
    required: bool
    options: list[str]
    validation: dict[str, Any]
    sort_order: int
    is_active: bool
    in_import: bool
    in_export: bool
    version: int


class EditionScopedParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edition_id: uuid.UUID
    include_inactive: bool = False


# --- configurable select options -------------------------------------------------------------


class FieldOptionIn(BaseModel):
    edition_id: uuid.UUID
    field: OptionField
    value: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=200)
    sort_order: int = 0
    is_active: bool = True


class FieldOptionUpdateIn(BaseModel):
    version: int
    label: str | None = Field(default=None, min_length=1, max_length=200)
    sort_order: int | None = None
    is_active: bool | None = None


class FieldOptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    edition_id: uuid.UUID
    field: OptionField
    value: str
    label: str
    sort_order: int
    is_active: bool
    version: int


class FieldOptionParams(EditionScopedParams):
    field: OptionField | None = None


# --- lead sources (global master data) --------------------------------------------------------


class LeadSourceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    sort_order: int = Field(default=0, ge=0, le=10_000)
    is_active: bool = True


class LeadSourceUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    is_active: bool | None = None


class LeadSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    sort_order: int
    is_active: bool
    version: int


class LeadSourceParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_inactive: bool = False
