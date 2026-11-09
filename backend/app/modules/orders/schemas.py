import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.core.pagination import PageParams
from app.modules.orders.rules import AttachmentPurpose, DetailsType

Currency = Annotated[str, StringConstraints(pattern=r"^[A-Za-z]{3}$", to_upper=True)]
FormCode = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[0-9]{2}[a-z]?$")]
Money = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]


# --- forms -------------------------------------------------------------------------------


class OrderFormFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=200)
    details_type: DetailsType | None = None
    has_catalog: bool | None = None
    allow_custom_items: bool | None = None
    attachment_purposes: list[AttachmentPurpose] | None = Field(default=None, max_length=5)
    deadline_on: date | None = None
    closes_on: date | None = None
    secondary_deadline_label: str | None = Field(default=None, max_length=100)
    secondary_deadline_on: date | None = None
    instructions: str | None = Field(default=None, max_length=10000)
    currency: Currency | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10000)
    is_published: bool | None = None

    @field_validator("attachment_purposes")
    @classmethod
    def _unique(cls, v: list[AttachmentPurpose] | None) -> list[AttachmentPurpose] | None:
        return None if v is None else list(dict.fromkeys(v))


class OrderFormCreateIn(OrderFormFields):
    edition_id: uuid.UUID
    code: FormCode
    title: str = Field(max_length=200)
    currency: Currency | None = None  # edition default currency when omitted


class OrderFormUpdateIn(OrderFormFields):
    """The code is fixed once created: exhibitors and staff know a form by its number."""

    version: int


class OrderFormOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    edition_id: uuid.UUID
    code: str
    title: str
    details_type: DetailsType | None
    has_catalog: bool
    allow_custom_items: bool
    attachment_purposes: list[AttachmentPurpose]
    deadline_on: date | None
    closes_on: date | None
    secondary_deadline_label: str | None
    secondary_deadline_on: date | None
    instructions: str | None
    currency: str
    sort_order: int
    is_published: bool
    active_item_count: int = 0
    created_at: datetime
    updated_at: datetime
    version: int


class OrderFormListParams(PageParams):
    edition_id: uuid.UUID
    page_size: int = Field(default=100, ge=1, le=500)


class CopyFormsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_edition_id: uuid.UUID
    to_edition_id: uuid.UUID


class CopyFormsOut(BaseModel):
    forms_copied: int
    items_copied: int
    skipped_codes: list[str]  # already present in the target edition


# --- catalog items -----------------------------------------------------------------------


class OrderFormItemFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section: str | None = Field(default=None, max_length=200)
    code: str | None = Field(default=None, max_length=30)
    name: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=2000)
    size: str | None = Field(default=None, max_length=100)
    unit: str | None = Field(default=None, max_length=50)
    price_regular: Money | None = None
    price_surcharge: Money | None = None
    price_onsite: Money | None = None
    max_quantity: int | None = Field(default=None, gt=0, le=100000)
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=100000)


class OrderFormItemCreateIn(OrderFormItemFields):
    code: str = Field(max_length=30)
    name: str = Field(max_length=300)
    price_regular: Money


class OrderFormItemUpdateIn(OrderFormItemFields):
    version: int


class OrderFormItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    form_id: uuid.UUID
    section: str | None
    code: str
    name: str
    description: str | None
    size: str | None
    unit: str | None
    price_regular: Decimal
    price_surcharge: Decimal | None
    price_onsite: Decimal | None
    max_quantity: int | None
    is_active: bool
    sort_order: int
    has_image: bool = False
    created_at: datetime
    updated_at: datetime
    version: int


class OrderFormItemListParams(PageParams):
    page_size: int = Field(default=200, ge=1, le=500)
    include_inactive: bool = False


class ItemImportRowError(BaseModel):
    row: int  # spreadsheet row number, header is row 1
    errors: dict[str, str]


class ItemImportOut(BaseModel):
    created: int
    updated: int
    errors: list[ItemImportRowError]  # nothing is saved when this is not empty
