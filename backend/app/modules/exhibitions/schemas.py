import uuid
from datetime import date, datetime
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from app.core.pagination import PageParams
from app.core.validation import Email
from app.modules.exhibitions.rules import (
    CODE_RE,
    CURRENCY_RE,
    EditionStatus,
    is_valid_country,
    is_valid_timezone,
)


def _code(v: str) -> str:
    v = v.strip().upper()
    if not CODE_RE.match(v):
        raise ValueError("Use 2-20 letters or digits.")
    return v


def _country(v: str) -> str:
    v = v.strip().upper()
    if not is_valid_country(v):
        raise ValueError("Unknown ISO 3166 country code.")
    return v


def _timezone(v: str) -> str:
    if not is_valid_timezone(v):
        raise ValueError("Unknown IANA timezone.")
    return v


def _currency(v: str) -> str:
    v = v.strip().upper()
    if not CURRENCY_RE.match(v):
        raise ValueError("Use a 3-letter ISO 4217 code.")
    return v


Code = Annotated[str, AfterValidator(_code)]
Country = Annotated[str, AfterValidator(_country)]
Timezone = Annotated[str, AfterValidator(_timezone)]
Currency = Annotated[str, AfterValidator(_currency)]


class VenueIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    address: str | None = None
    city: str | None = Field(default=None, max_length=120)
    country: Country | None = None


class VenueUpdateIn(BaseModel):
    version: int
    name: str | None = Field(default=None, min_length=1, max_length=200)
    address: str | None = None
    city: str | None = Field(default=None, max_length=120)
    country: Country | None = None


class VenueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    address: str | None
    city: str | None
    country: str | None
    version: int


class ExhibitionIn(BaseModel):
    code: Code
    name: str = Field(min_length=1, max_length=200)
    is_active: bool = True


class ExhibitionUpdateIn(BaseModel):
    version: int
    name: str | None = Field(default=None, min_length=1, max_length=200)
    is_active: bool | None = None


class ExhibitionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    version: int


class ExhibitionListParams(PageParams):
    q: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None


class EditionIn(BaseModel):
    exhibition_id: uuid.UUID
    year: int = Field(ge=2000, le=2100)
    code: Code | None = None
    name: str | None = Field(default=None, max_length=200)
    start_date: date
    end_date: date
    venue_id: uuid.UUID | None = None
    country: Country | None = None
    city: str | None = Field(default=None, max_length=120)
    timezone: Timezone
    default_currency: Currency
    registration_id_prefix: Code | None = None
    email_sender_name: str | None = Field(default=None, max_length=200)
    email_reply_to: Email | None = None
    email_account_id: uuid.UUID | None = None
    public_registration_open: bool = False
    scanner_cache_ttl_minutes: int | None = Field(default=None, ge=5, le=7 * 24 * 60)
    remarks: str | None = Field(default=None, max_length=2000)
    price_regular_from: date | None = None
    price_regular_to: date | None = None
    price_surcharge_from: date | None = None
    price_surcharge_to: date | None = None
    price_onsite_from: date | None = None
    price_onsite_to: date | None = None
    order_expired_on: date | None = None
    catalog_expired_on: date | None = None

    @model_validator(mode="after")
    def _dates(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        return self


class EditionUpdateIn(BaseModel):
    version: int
    name: str | None = Field(default=None, min_length=1, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    venue_id: uuid.UUID | None = None
    country: Country | None = None
    city: str | None = Field(default=None, max_length=120)
    timezone: Timezone | None = None
    default_currency: Currency | None = None
    status: EditionStatus | None = None
    email_sender_name: str | None = Field(default=None, max_length=200)
    email_reply_to: Email | None = None
    email_account_id: uuid.UUID | None = None
    public_registration_open: bool | None = None
    scanner_cache_ttl_minutes: int | None = Field(default=None, ge=5, le=7 * 24 * 60)
    remarks: str | None = Field(default=None, max_length=2000)
    price_regular_from: date | None = None
    price_regular_to: date | None = None
    price_surcharge_from: date | None = None
    price_surcharge_to: date | None = None
    price_onsite_from: date | None = None
    price_onsite_to: date | None = None
    order_expired_on: date | None = None
    catalog_expired_on: date | None = None


class EditionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    exhibition_id: uuid.UUID
    exhibition_code: str | None = None
    year: int
    code: str
    name: str
    start_date: date
    end_date: date
    venue_id: uuid.UUID | None
    country: str | None
    city: str | None
    timezone: str
    default_currency: str
    registration_id_prefix: str
    status: EditionStatus
    email_sender_name: str | None
    email_reply_to: str | None
    email_account_id: uuid.UUID | None
    public_registration_open: bool
    scanner_cache_ttl_minutes: int | None
    remarks: str | None
    price_regular_from: date | None
    price_regular_to: date | None
    price_surcharge_from: date | None
    price_surcharge_to: date | None
    price_onsite_from: date | None
    price_onsite_to: date | None
    order_expired_on: date | None
    catalog_expired_on: date | None
    created_at: datetime
    updated_at: datetime
    version: int


class EditionListParams(PageParams):
    exhibition_id: uuid.UUID | None = None
    status: EditionStatus | None = None
    year: int | None = None
