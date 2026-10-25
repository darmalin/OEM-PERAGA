import json
import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    HttpUrl,
    TypeAdapter,
    WithJsonSchema,
    field_validator,
    model_validator,
)

from app.core.pagination import PageParams
from app.modules.exhibitions.schemas import Country
from app.modules.visitors.rules import (
    CHOICE_ENUMS,
    CHOICE_IDS,
    CONDITION_FIELDS,
    CONDITION_OPS,
    FIELD_KEY_RE,
    MAX_CONDITIONS,
    NEVER_EMPTY,
    Attend,
    BuyerType,
    ConditionKind,
    ConditionOp,
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


_DATE = TypeAdapter(date)
_DATES = TypeAdapter(tuple[date, date])
_UUID = TypeAdapter(uuid.UUID)


class LeadCondition(BaseModel):
    """One row of the Filter button: field, operator, value. Fields and operators are a
    fixed list (rules.CONDITION_FIELDS); the value is checked and typed for the field."""

    model_config = ConfigDict(extra="forbid")

    field: str
    op: ConditionOp
    value: Any = None

    @model_validator(mode="after")
    def _check(self) -> "LeadCondition":
        kind = CONDITION_FIELDS.get(self.field)
        if kind is None:
            raise ValueError(f"Unknown filter field: {self.field}.")
        if self.op not in CONDITION_OPS[kind] or (
            self.op in (ConditionOp.IS_SET, ConditionOp.NOT_SET) and self.field in NEVER_EMPTY
        ):
            raise ValueError(f"Operator {self.op} does not apply to {self.field}.")
        if self.op in (ConditionOp.IS_SET, ConditionOp.NOT_SET):
            self.value = None
            return self
        self.value = _condition_value(self.field, kind, self.op, self.value)
        return self


def _condition_value(field: str, kind: ConditionKind, op: ConditionOp, value: Any) -> Any:
    if kind is ConditionKind.TEXT:
        if not isinstance(value, str) or not value.strip() or len(value) > 200:
            raise ValueError(f"Enter text to filter {field} by (up to 200 characters).")
        if field == "phone":
            digits = "".join(ch for ch in value if ch.isdigit())
            if len(digits) < 4:
                raise ValueError("Enter at least 4 digits of the phone number.")
            return digits
        return value.strip().lower()
    if kind is ConditionKind.CHOICE:
        if not isinstance(value, str) or not value:
            raise ValueError(f"Choose a value for {field}.")
        if field in CHOICE_IDS:
            return _UUID.validate_python(value)
        if field == "country":
            if len(value) != 2 or not value.isalpha():
                raise ValueError("Use a two-letter country code.")
            return value.upper()
        return CHOICE_ENUMS[field](value).value
    if kind is ConditionKind.BOOL:
        if not isinstance(value, bool):
            raise ValueError(f"Choose yes or no for {field}.")
        return value
    if kind is ConditionKind.DATE:
        if op is ConditionOp.BETWEEN:
            start, end = _DATES.validate_python(value)
            if end < start:
                raise ValueError("The end date is before the start date.")
            return (start, end)
        return _DATE.validate_python(value)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"Enter a whole number for {field}.")
    return value


def _conditions_json(v: Any) -> Any:
    # A query string carries the list as one JSON string (FastAPI hands it over as a list).
    if isinstance(v, list) and len(v) == 1 and isinstance(v[0], str):
        v = v[0]
    if isinstance(v, str):
        try:
            return json.loads(v) if v else None
        except json.JSONDecodeError as e:
            raise ValueError("Filters must be a JSON list.") from e
    return v


Conditions = Annotated[
    list[LeadCondition],
    Field(max_length=MAX_CONDITIONS),
    BeforeValidator(_conditions_json),
    WithJsonSchema(
        {
            "type": "string",
            "description": 'JSON list of {"field", "op", "value"}, all of which must match.',
        }
    ),
]


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
    filters: Conditions | None = None


class LeadFilterOptionsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edition_id: uuid.UUID | None = None  # None: every edition the caller may read


class FilterChoice(BaseModel):
    id: uuid.UUID
    name: str


class LeadFilterOptions(BaseModel):
    """Choices for the list filters, taken from the leads the caller can see."""

    countries: list[str]
    owners: list[FilterChoice]
    teams: list[FilterChoice]


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
