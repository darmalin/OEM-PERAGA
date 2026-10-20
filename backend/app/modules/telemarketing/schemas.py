import uuid
from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.pagination import PageParams
from app.modules.telemarketing.rules import AssignmentMethod, FollowupStatus
from app.modules.visitors.rules import Attend, BuyerType
from app.modules.visitors.schemas import LeadFilters

MAX_SYNC_ASSIGN = 500
MAX_ASSIGN = 50_000


class AssignmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edition_id: uuid.UUID
    method: AssignmentMethod
    lead_ids: list[uuid.UUID] | None = Field(default=None, max_length=MAX_ASSIGN)
    filter: LeadFilters | None = None
    agent_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    # Round robin cursor pool; also limits eligible agents to this team.
    team_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _shape(self) -> Self:
        if (self.lead_ids is None) == (self.filter is None):
            raise ValueError("Send either lead_ids or filter.")
        if self.method != AssignmentMethod.ROUND_ROBIN and len(set(self.agent_ids)) != 1:
            raise ValueError("Manual and bulk assignment take exactly one agent.")
        if self.method == AssignmentMethod.MANUAL and (
            self.lead_ids is None or len(self.lead_ids) != 1
        ):
            raise ValueError("Manual assignment takes exactly one lead.")
        return self


class AssignmentResult(BaseModel):
    batch_id: uuid.UUID
    assigned: int
    unchanged: int
    per_agent: dict[str, int]


class AssignmentAccepted(BaseModel):
    job_id: uuid.UUID
    status: str


class AssignmentJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    edition_id: uuid.UUID
    status: str
    lead_count: int
    result: dict[str, Any] | None
    error_summary: str | None
    created_at: datetime
    finished_at: datetime | None


class AssignmentHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    visitor_lead_id: uuid.UUID
    from_user_id: uuid.UUID | None
    to_user_id: uuid.UUID
    method: AssignmentMethod
    actor_user_id: uuid.UUID | None
    batch_id: uuid.UUID
    assigned_at: datetime


class AgentOut(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    team_ids: list[uuid.UUID]


class AgentParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edition_id: uuid.UUID
    team_id: uuid.UUID | None = None


# --- calls ---------------------------------------------------------------------------------


class CallIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    call_result: str = Field(min_length=1, max_length=30)
    called_at: datetime | None = None
    duration_seconds: int | None = Field(default=None, ge=0, le=24 * 3600)
    notes: str | None = Field(default=None, max_length=5000)
    next_followup_at: datetime | None = None


class CallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    visitor_lead_id: uuid.UUID
    agent_id: uuid.UUID
    attempt_number: int
    call_result: str
    called_at: datetime
    duration_seconds: int | None
    notes: str | None
    next_followup_at: datetime | None
    created_at: datetime


class CallLoggedOut(BaseModel):
    call: CallOut
    telemarketing_status: str
    call_attempts: int
    followup_id: uuid.UUID | None


# --- verification --------------------------------------------------------------------------


class VerificationIn(BaseModel):
    """Partial save allowed (spec 6.4). Valid Lead and Invalid are mutually exclusive."""

    model_config = ConfigDict(extra="forbid")

    version: int
    is_valid_lead: bool | None = None
    is_invalid: bool | None = None
    attend: Attend | None = None
    b2b_matching: bool | None = None
    buyer_type: BuyerType | None = None


class VerificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    visitor_lead_id: uuid.UUID
    is_valid_lead: bool
    is_invalid: bool
    attend: Attend | None
    b2b_matching: bool
    buyer_type: BuyerType | None
    changed_by: uuid.UUID | None
    created_at: datetime


# --- follow-ups ----------------------------------------------------------------------------


class FollowupIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    due_at: datetime
    assigned_to: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=2000)


class FollowupUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    action: Literal["RESCHEDULE", "DONE", "CANCEL"]
    due_at: datetime | None = None
    note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _due(self) -> Self:
        if self.action == "RESCHEDULE" and self.due_at is None:
            raise ValueError("due_at is required to reschedule.")
        return self


class FollowupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    edition_id: uuid.UUID
    visitor_lead_id: uuid.UUID
    lead_first_name: str | None = None
    lead_registration_code: str | None = None
    assigned_to: uuid.UUID
    due_at: datetime
    status: FollowupStatus
    note: str | None
    created_from_call_id: uuid.UUID | None
    completed_at: datetime | None
    version: int


class FollowupChangeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    action: str
    old_due_at: datetime | None
    new_due_at: datetime | None
    note: str | None
    actor_user_id: uuid.UUID | None
    created_at: datetime


class FollowupListParams(PageParams):
    edition_id: uuid.UUID
    bucket: Literal["today", "overdue", "upcoming", "all"] = "today"
    status: FollowupStatus = FollowupStatus.OPEN
    assigned_to: uuid.UUID | None = None


class QueueParams(PageParams):
    edition_id: uuid.UUID
    agent_id: uuid.UUID | None = None
