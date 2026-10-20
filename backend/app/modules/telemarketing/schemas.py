import uuid
from datetime import datetime
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.telemarketing.rules import AssignmentMethod
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
