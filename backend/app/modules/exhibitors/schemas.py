import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.pagination import PageParams
from app.modules.exhibitors.rules import PaymentMethod, PaymentState, PaymentStatus, SalesStage


class ExhibitorLeadFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str | None = Field(default=None, max_length=300)
    contact_name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    product_categories: str | None = Field(default=None, max_length=2000)
    booth_preference: str | None = Field(default=None, max_length=2000)
    budget_estimate: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    notes: str | None = Field(default=None, max_length=5000)
    lead_owner_id: uuid.UUID | None = None


class ExhibitorLeadCreateIn(ExhibitorLeadFields):
    edition_id: uuid.UUID
    company_name: str = Field(max_length=300)
    contact_name: str = Field(max_length=200)
    email: str = Field(max_length=320)


class ExhibitorLeadUpdateIn(ExhibitorLeadFields):
    version: int


class StageChangeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # EXHIBITOR is reached through the convert step (phase 4), not here.
    stage: Literal[SalesStage.LEAD, SalesStage.OPPORTUNITY, SalesStage.LOST]
    lost_reason: str | None = Field(default=None, max_length=2000)
    version: int


class ExhibitorLeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    edition_id: uuid.UUID
    company_name: str
    contact_name: str
    email: str
    phone: str | None
    phone_normalized: str | None
    product_categories: str | None
    booth_preference: str | None
    budget_estimate: Decimal | None
    notes: str | None
    stage: SalesStage
    lost_reason: str | None
    qualified_at: datetime | None
    converted_at: datetime | None
    booth_id: uuid.UUID | None
    booth_code: str | None = None
    booth_assigned_at: datetime | None
    lead_owner_id: uuid.UUID | None
    lead_owner_name: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int


SortParam = Literal[
    "created_at", "-created_at", "updated_at", "-updated_at", "company_name", "-company_name",
]  # fmt: skip


class ExhibitorLeadListParams(PageParams):
    edition_id: uuid.UUID
    q: str | None = Field(default=None, max_length=200)
    stage: list[SalesStage] | None = None
    lead_owner_id: uuid.UUID | None = None
    sort: SortParam = "-updated_at"


class BoothAssignIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    booth_id: uuid.UUID | None  # None releases the booth
    version: int


# --- booths ------------------------------------------------------------------------------

Currency = Annotated[str, StringConstraints(pattern=r"^[A-Za-z]{3}$", to_upper=True)]


class BoothFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str | None = Field(default=None, max_length=30)
    hall: str | None = Field(default=None, max_length=100)
    area_sqm: Decimal | None = Field(default=None, gt=0, max_digits=8, decimal_places=2)
    price: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    currency: Currency | None = None
    is_active: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)


class BoothCreateIn(BoothFields):
    edition_id: uuid.UUID
    code: str = Field(max_length=30)
    area_sqm: Decimal = Field(gt=0, max_digits=8, decimal_places=2)
    price: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    currency: Currency | None = None  # edition default currency when omitted


class BoothUpdateIn(BoothFields):
    version: int


class BoothOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    edition_id: uuid.UUID
    code: str
    hall: str | None
    area_sqm: Decimal
    price: Decimal
    currency: str
    is_active: bool
    notes: str | None
    is_available: bool = True
    # The holder is shown only to callers with edition-wide access (sales may hold OWNED scope).
    exhibitor_lead_id: uuid.UUID | None = None
    exhibitor_company_name: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int


class BoothListParams(PageParams):
    edition_id: uuid.UUID
    q: str | None = Field(default=None, max_length=100)
    available: bool | None = None
    include_inactive: bool = False


# --- convert and invitations (staff) -----------------------------------------------------


class ConvertIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int


LinkPurpose = Literal["INVITATION", "PASSWORD_RESET"]


class InvitationOut(BaseModel):
    """The raw link is shown once; only its hash is stored. INVITATION for an account without a
    password, PASSWORD_RESET for one that has a password (shorter lifetime)."""

    url: str
    expires_at: datetime
    purpose: LinkPurpose = "INVITATION"


class PortalAccountOut(BaseModel):
    """The lead's portal account as staff see it; never the hashes."""

    email: str
    is_active: bool
    has_password: bool
    activated_at: datetime | None
    last_login_at: datetime | None
    link_expires_at: datetime | None


class PortalAccountUpdateIn(BaseModel):
    """A target state, not a form edit: no version, since every sign-in bumps the account's
    version and disabling must not fail because the exhibitor just signed in."""

    model_config = ConfigDict(extra="forbid")

    is_active: bool


class ConvertOut(BaseModel):
    lead: ExhibitorLeadOut
    contract_number: str
    # None when the account already has a password (an exhibitor from another edition).
    invitation: InvitationOut | None


class ContractFieldsIn(BaseModel):
    """What the exhibitor fills in while the contract is DRAFT. Empty text clears a field."""

    model_config = ConfigDict(extra="forbid")

    pic_name: str | None = Field(default=None, max_length=200)
    company_address: str | None = Field(default=None, max_length=2000)
    tax_id: str | None = Field(default=None, max_length=30)
    version: int


class ContractUpdateIn(ContractFieldsIn):
    """Staff edit: the exhibitor's fields plus the discount."""

    discount_amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)


class ContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    edition_id: uuid.UUID
    exhibitor_lead_id: uuid.UUID
    contract_number: str | None
    pic_name: str | None
    company_address: str | None
    tax_id: str | None
    booth_price: Decimal
    discount_amount: Decimal
    total_amount: Decimal | None
    currency: str
    status: str
    signed_at: datetime | None
    signed_file_name: str | None
    version: int
    updated_at: datetime
    company_name: str = ""
    booth_code: str | None = None


class PaymentCreateIn(BaseModel):
    """One installment as the exhibitor paid it. Recorded PENDING, verified by hand."""

    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    paid_on: date
    method: PaymentMethod
    reference: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)


class PaymentReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal[PaymentStatus.VERIFIED, PaymentStatus.REJECTED]
    notes: str | None = Field(default=None, max_length=2000)
    version: int


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contract_id: uuid.UUID
    amount: Decimal
    paid_on: date
    method: str
    reference: str | None
    status: str
    has_proof: bool = False
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    notes: str | None
    created_at: datetime
    version: int


class PaymentTotals(BaseModel):
    total_amount: Decimal
    currency: str
    verified_amount: Decimal
    pending_amount: Decimal
    outstanding_amount: Decimal
    payment_state: PaymentState


class PaymentsOut(PaymentTotals):
    items: list[PaymentOut]


class PortalPaymentOut(BaseModel):
    """What the exhibitor sees of a payment: no internal notes, no reviewer."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    amount: Decimal
    paid_on: date
    method: str
    reference: str | None
    status: str
    reviewed_at: datetime | None


class PortalPaymentsOut(PaymentTotals):
    items: list[PortalPaymentOut]


class PipelineParams(BaseModel):
    edition_id: uuid.UUID


class StageCount(BaseModel):
    stage: SalesStage
    count: int


class PipelineMoney(BaseModel):
    """Per currency: booths can be priced in different currencies."""

    currency: str
    signed_contracts: int
    signed_value: Decimal
    verified_amount: Decimal
    pending_amount: Decimal
    outstanding_amount: Decimal
    paid_contracts: int


class PipelineOut(BaseModel):
    """Sales pipeline of one edition, counted inside the caller's lead scope."""

    stages: list[StageCount]
    draft_contracts: int
    booths_for_sale: int
    booths_held: int
    money: list[PipelineMoney]


# --- exhibitor portal --------------------------------------------------------------------


class InvitationTokenIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=20, max_length=200)


class InvitationInfoOut(BaseModel):
    email: str
    purpose: LinkPurpose


class AcceptInvitationIn(InvitationTokenIn):
    password: str = Field(max_length=200)


class PortalLoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(max_length=320)
    password: str = Field(max_length=200)


class PortalExhibitorOut(BaseModel):
    exhibitor_lead_id: uuid.UUID
    edition_id: uuid.UUID
    edition_name: str
    edition_start_date: date
    edition_end_date: date
    company_name: str
    booth_code: str | None
    contract_number: str | None
    contract_status: str | None
    payment_state: PaymentState | None = None


class PortalMeOut(BaseModel):
    account_id: uuid.UUID
    email: str
    csrf_token: str
    exhibitors: list[PortalExhibitorOut]
