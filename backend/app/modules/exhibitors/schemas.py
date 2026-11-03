import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.pagination import PageParams
from app.modules.exhibitors.rules import SalesStage


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
