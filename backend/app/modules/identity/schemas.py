import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.pagination import PageParams
from app.core.validation import Email
from app.modules.identity.rules import ScopeType


class LoginIn(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class GrantOut(BaseModel):
    role_code: str
    scope_type: ScopeType
    edition_id: uuid.UUID | None
    team_id: uuid.UUID | None
    gate_id: uuid.UUID | None = None


class UserBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str


class EditionBrief(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    status: str
    timezone: str
    start_date: date
    end_date: date


class MeOut(BaseModel):
    user: UserBrief
    permissions: list[str]
    grants: list[GrantOut]
    editions: list[EditionBrief]
    csrf_token: str


class PasswordResetRequestIn(BaseModel):
    email: Email


class PasswordResetConfirmIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    new_password: str = Field(max_length=1024)


class MessageOut(BaseModel):
    message: str


class RoleAssignmentIn(BaseModel):
    role_id: uuid.UUID
    scope_type: ScopeType
    edition_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _team_needed(self) -> "RoleAssignmentIn":
        if self.scope_type == ScopeType.TEAM and self.team_id is None:
            raise ValueError("team_id is required for TEAM scope")
        return self


class RoleAssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role_id: uuid.UUID
    role_code: str
    scope_type: ScopeType
    edition_id: uuid.UUID | None
    team_id: uuid.UUID | None
    created_at: datetime


class UserCreateIn(BaseModel):
    email: Email
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(max_length=1024)


class UserUpdateIn(BaseModel):
    version: int
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    is_active: bool | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int


class UserDetailOut(UserOut):
    role_assignments: list[RoleAssignmentOut]
    team_ids: list[uuid.UUID]


class UserListParams(PageParams):
    q: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None


class PermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    description: str


class RoleOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str
    is_system: bool
    permissions: list[str]


class RoleCreateIn(BaseModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,99}$")
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    permissions: list[str] = []


class RolePermissionsIn(BaseModel):
    permissions: list[str]


class TeamIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    member_ids: list[uuid.UUID] = []


class TeamMemberIn(BaseModel):
    user_id: uuid.UUID
