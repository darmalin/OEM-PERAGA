"""Quotation API shapes (docs/EXHIBITOR_QUOTATIONS.md)."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.modules.quotations.rules import QuotationStatus, StandType

Currency = Annotated[str, StringConstraints(pattern=r"^[A-Za-z]{3}$", to_upper=True)]
Money = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]
Sqm = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]
Percent = Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)]
Code = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=20, pattern=r"^[A-Za-z0-9-]+$"
    ),
]


class Rate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: Currency
    stand_type: StandType
    rate: Money  # per sqm


class TermIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=60)
    percent: Annotated[Decimal, Field(gt=0, le=100, max_digits=5, decimal_places=2)]
    due_on: date | None = None


def _terms_total(terms: list[TermIn]) -> None:
    if terms and sum((t.percent for t in terms), Decimal(0)) != 100:
        raise ValueError("The payment terms must add up to 100%.")


# --- settings ----------------------------------------------------------------------------


class SettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Code
    company_code: Code = "PNJS"
    start_number: int = Field(default=1, ge=1, le=999_999)
    place: str = Field(default="Jakarta", min_length=1, max_length=100)
    letter_name: str | None = Field(default=None, max_length=500)
    event_text: str | None = Field(default=None, max_length=500)
    rates: list[Rate] = Field(default_factory=list, max_length=20)
    shell_includes: str | None = Field(default=None, max_length=1000)
    discount_label: str = Field(default="Special Discount", min_length=1, max_length=60)
    vat_rate: Percent = Decimal(12)
    vat_base_num: int = Field(default=11, ge=1, le=100)
    vat_base_den: int = Field(default=12, ge=1, le=100)
    terms: list[TermIn] = Field(default_factory=list, max_length=10)
    signer_name: str | None = Field(default=None, max_length=200)
    signer_title: str | None = Field(default=None, max_length=200)
    version: int | None = None  # None creates; otherwise the version being edited

    @model_validator(mode="after")
    def _check(self) -> "SettingsIn":
        if self.vat_base_num > self.vat_base_den:
            raise ValueError("The tax base cannot be more than 1 (e.g. 11/12).")
        _terms_total(self.terms)
        pairs = [(r.currency, r.stand_type) for r in self.rates]
        if len(pairs) != len(set(pairs)):
            raise ValueError("One rate per currency and stand type.")
        return self


class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    exists: bool = True  # False: not saved yet, these are the defaults
    edition_id: uuid.UUID
    code: str | None
    company_code: str
    start_number: int
    next_number: int | None = None  # what the next quotation this year will get
    place: str
    letter_name: str | None
    event_text: str | None
    rates: list[Rate]
    shell_includes: str | None
    discount_label: str
    vat_rate: Decimal
    vat_base_num: int
    vat_base_den: int
    terms: list[TermIn]
    signer_name: str | None
    signer_title: str | None
    has_signature: bool = False
    version: int | None = None


# --- quotations --------------------------------------------------------------------------


class QuotationIn(BaseModel):
    """What staff fill in. Omitted values come from the settings and the lead."""

    model_config = ConfigDict(extra="forbid")

    stand_type: StandType
    currency: Currency | None = None  # the edition's default currency
    booth_id: uuid.UUID | None = None
    booth_code: str | None = Field(default=None, max_length=30)  # a booth not in the list yet
    width_m: Annotated[Decimal, Field(gt=0, max_digits=8, decimal_places=2)] | None = None
    length_m: Annotated[Decimal, Field(gt=0, max_digits=8, decimal_places=2)] | None = None
    area_sqm: Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)] | None = None
    complimentary_sqm: Sqm = Decimal(0)
    stand_rate: Money | None = None
    raw_rate: Money | None = None
    discount_label: str | None = Field(default=None, max_length=60)
    discount_percent: Percent = Decimal(0)
    vat: bool | None = None  # None: on for IDR, off for other currencies
    terms: list[TermIn] | None = None
    issued_on: date | None = None  # today in the edition's timezone
    recipient_company: str | None = Field(default=None, max_length=300)
    recipient_address: str | None = Field(default=None, max_length=1000)
    attention: str | None = Field(default=None, max_length=200)
    includes: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=2000)
    replaces_id: uuid.UUID | None = None  # a revision supersedes this quotation

    @model_validator(mode="after")
    def _check(self) -> "QuotationIn":
        # A listed booth can supply the area; otherwise the size is needed.
        no_size = self.area_sqm is None and (self.width_m is None or self.length_m is None)
        if no_size and self.booth_id is None:
            raise ValueError("Enter the width and length, or the area.")
        if self.booth_id is not None and self.booth_code is not None:
            raise ValueError("Choose a listed booth or type a booth code, not both.")
        if self.terms is not None:
            _terms_total(self.terms)
        return self


class TermOut(BaseModel):
    label: str
    percent: Decimal
    due_on: date | None
    amount: Decimal


class QuotationPreviewOut(BaseModel):
    """The summary shown before Create: every amount, nothing saved, no number taken."""

    number: str  # the number it would get now; another quotation may take it first
    issued_on: date
    recipient_company: str
    recipient_address: str | None
    attention: str | None
    stand_type: StandType
    currency: str
    booth_code: str | None
    width_m: Decimal | None
    length_m: Decimal | None
    area_sqm: Decimal
    complimentary_sqm: Decimal
    charged_sqm: Decimal
    stand_rate: Decimal
    raw_rate: Decimal
    discount_label: str | None
    discount_percent: Decimal
    vat_rate: Decimal
    vat_base_num: int
    vat_base_den: int
    gross_amount: Decimal
    discount_amount: Decimal
    cost_amount: Decimal
    vat_amount: Decimal
    total_amount: Decimal
    terms: list[TermOut]
    includes: str | None
    notes: str | None


class QuotationOut(QuotationPreviewOut):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    edition_id: uuid.UUID
    exhibitor_lead_id: uuid.UUID
    status: QuotationStatus
    booth_id: uuid.UUID | None
    replaces_id: uuid.UUID | None
    replaced_by_number: str | None = None
    accepted_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    created_by_name: str | None = None
    created_at: datetime
    version: int


class QuotationCancelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=1000)
    version: int
