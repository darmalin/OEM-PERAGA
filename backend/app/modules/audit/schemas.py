import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.pagination import PageParams


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    occurred_at: datetime
    actor_user_id: uuid.UUID | None
    actor_name: str | None = None
    source: str
    edition_id: uuid.UUID | None
    entity_type: str
    entity_id: uuid.UUID | None
    action: str
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    request_id: str | None


class AuditLogParams(PageParams):
    edition_id: uuid.UUID | None = None
    entity_type: str | None = Field(default=None, max_length=64)
    entity_id: uuid.UUID | None = None
    actor_user_id: uuid.UUID | None = None
    action: str | None = Field(default=None, max_length=64)
    occurred_from: datetime | None = None
    occurred_to: datetime | None = None
