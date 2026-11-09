import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.core.pagination import PageParams
from app.modules.orders.rules import (
    AttachmentPurpose,
    DetailsType,
    FormProgress,
    OptionKind,
    OrderStatus,
    PricePeriod,
)

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


class AllowanceTierIO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_area_sqm: Decimal = Field(ge=0, max_digits=8, decimal_places=2)
    free_quantity: int = Field(gt=0, le=9999)


class AllowancesIn(BaseModel):
    """Replaces the item's tiers; an empty list removes the allowance."""

    model_config = ConfigDict(extra="forbid")

    tiers: list[AllowanceTierIO] = Field(max_length=20)


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
    # Free quantity by booth area (decision O9), smallest area first.
    allowances: list[AllowanceTierIO] = Field(default_factory=list)
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


# --- portal ------------------------------------------------------------------------------
# Never carries prices, totals, or statuses from the exhibitor: the server computes them.


class PortalOrderFormOut(BaseModel):
    """One row of the portal's form list."""

    code: str
    title: str
    has_catalog: bool
    details_type: DetailsType | None
    deadline_on: date | None
    closes_on: date | None  # the form's own date, else the edition's Order Expired date
    secondary_deadline_label: str | None
    secondary_deadline_on: date | None
    is_closed: bool
    progress: FormProgress
    open_order_id: uuid.UUID | None
    sent_orders: int  # submitted, returned, or approved


class PortalOrderFormsOut(BaseModel):
    forms: list[PortalOrderFormOut]
    # Today's catalog price period; None when ordering is not open (no period covers today).
    price_period: PricePeriod | None


class PortalCatalogItemOut(BaseModel):
    id: uuid.UUID
    section: str | None
    code: str
    name: str
    description: str | None
    size: str | None
    unit: str | None
    unit_price: Decimal  # in today's price period (Regular while ordering is not open)
    max_quantity: int | None
    has_image: bool
    # Still free for this exhibitor's booth, after the exhibitor's other sent orders.
    free_quantity: int = 0


class PortalOrderLineOut(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID | None  # None: an extra item the exhibitor described
    section: str | None
    code: str | None
    name: str
    size: str | None
    quantity: int
    free_quantity: int
    unit_price: Decimal | None  # None until staff price an extra item
    amount: Decimal | None
    has_image: bool
    notes: str | None


class PortalOrderFileOut(BaseModel):
    id: uuid.UUID
    purpose: AttachmentPurpose
    file_name: str
    size_bytes: int
    created_at: datetime


class PortalOrderOut(BaseModel):
    id: uuid.UUID
    form_code: str
    order_number: str | None
    status: OrderStatus
    price_period: PricePeriod | None
    remarks: str | None
    total: Decimal
    currency: str
    submitted_at: datetime | None
    # Staff's reason when the order came back (RETURNED) or was cancelled.
    review_notes: str | None
    cancel_reason: str | None
    unpriced_lines: int  # extra items still waiting for a price from staff
    details: dict[str, Any]  # answers to the form's questions (orders/details.py)
    # Submitted and costs money, but the booth contract is not signed yet (decision O2).
    waiting_for_contract: bool
    lines: list[PortalOrderLineOut]
    files: list[PortalOrderFileOut]
    version: int


class PortalOrderFormDetailOut(BaseModel):
    code: str
    title: str
    instructions: str | None
    currency: str
    has_catalog: bool
    allow_custom_items: bool
    details_type: DetailsType | None
    attachment_purposes: list[AttachmentPurpose]
    deadline_on: date | None
    closes_on: date | None
    secondary_deadline_label: str | None
    secondary_deadline_on: date | None
    is_closed: bool
    price_period: PricePeriod | None
    progress: FormProgress
    not_required: bool
    options: dict[OptionKind, list[str]]  # choices of the form's questions
    company_name: str
    booth_code: str | None
    items: list[PortalCatalogItemOut]
    open_order: PortalOrderOut | None
    sent_orders: list[PortalOrderOut]  # newest first


class OrderLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: uuid.UUID
    quantity: int = Field(gt=0, le=9999)


class CustomLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID | None = None  # an existing extra line keeps its picture
    name: str = Field(max_length=300)
    size: str | None = Field(default=None, max_length=100)
    quantity: int = Field(gt=0, le=9999)
    notes: str | None = Field(default=None, max_length=500)


class OrderDraftIn(BaseModel):
    """Replaces the order's lines; lines left out are removed."""

    model_config = ConfigDict(extra="forbid")

    lines: list[OrderLineIn] = Field(default_factory=list, max_length=500)
    custom_lines: list[CustomLineIn] = Field(default_factory=list, max_length=20)
    # Answers to the form's questions; checked against the form's schema (orders/details.py).
    details: dict[str, Any] = Field(default_factory=dict)
    remarks: str | None = Field(default=None, max_length=2000)
    version: int


class OrderVersionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int


# --- staff review ------------------------------------------------------------------------


class StaffOrderListParams(PageParams):
    edition_id: uuid.UUID
    form_id: uuid.UUID | None = None
    # Drafts are the exhibitor's own work in progress and never listed for staff.
    status: OrderStatus | None = None
    q: str | None = Field(default=None, max_length=100)  # company or order number
    exhibitor_lead_id: uuid.UUID | None = None


class StaffOrderRowOut(BaseModel):
    id: uuid.UUID
    order_number: str | None
    status: OrderStatus
    form_id: uuid.UUID
    form_code: str
    form_title: str
    exhibitor_lead_id: uuid.UUID
    company_name: str
    booth_code: str | None
    total: Decimal
    currency: str
    unpriced_lines: int
    submitted_at: datetime | None
    contract_signed: bool
    # Submitted, costs money, contract not signed: cannot be approved yet (decision O2).
    waiting_for_contract: bool
    # The exhibitor's booth is not the one the order was sent for (decision O2).
    booth_changed: bool


class StaffOrderOut(StaffOrderRowOut):
    details_type: DetailsType | None
    details: dict[str, Any]
    price_period: PricePeriod | None
    remarks: str | None
    booth_code_at_submit: str | None
    area_sqm_at_submit: Decimal | None
    review_notes: str | None
    reviewed_at: datetime | None
    reviewed_by_name: str | None
    cancel_reason: str | None
    lines: list[PortalOrderLineOut]
    files: list[PortalOrderFileOut]
    version: int


class LinePriceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_price: Money
    version: int  # the order's version


class OrderReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["APPROVED", "RETURNED"]
    notes: str | None = Field(default=None, max_length=2000)  # required to return
    version: int


class OrderCancelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(max_length=2000)
    version: int


class LeadFormProgressOut(BaseModel):
    form_id: uuid.UUID
    code: str
    title: str
    progress: FormProgress


class LeadOrdersOut(BaseModel):
    forms: list[LeadFormProgressOut]  # published forms of the lead's edition
    orders: list[StaffOrderRowOut]  # sent orders, newest first


class OrderExportParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edition_id: uuid.UUID
    form_id: uuid.UUID
    status: OrderStatus | None = None


class FormOptionsOut(BaseModel):
    options: dict[OptionKind, list[str]]


class FormOptionsIn(BaseModel):
    """Replaces the choices of one kind; answers already sent keep their text."""

    model_config = ConfigDict(extra="forbid")

    kind: OptionKind
    values: list[
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    ] = Field(max_length=200)
