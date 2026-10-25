import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, authenticated, require
from app.core.config import get_settings
from app.core.db import get_session
from app.core.pagination import Page
from app.modules.identity import service
from app.modules.identity.schemas import (
    EditionTeamIn,
    EditionTeamOut,
    LoginIn,
    MeOut,
    MessageOut,
    PasswordResetConfirmIn,
    PasswordResetRequestIn,
    PermissionOut,
    RoleAssignmentIn,
    RoleAssignmentOut,
    RoleCreateIn,
    RoleOut,
    RolePermissionsIn,
    TeamIn,
    TeamMemberIn,
    TeamOut,
    UserCreateIn,
    UserDetailOut,
    UserListParams,
    UserOut,
    UserUpdateIn,
)

auth_router = APIRouter(prefix="/auth", tags=["auth"])
router = APIRouter(tags=["identity"])

Session = Annotated[AsyncSession, Depends(get_session)]


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@auth_router.post("/login", response_model=MeOut)
async def login(data: LoginIn, request: Request, response: Response, session: Session) -> MeOut:
    s = get_settings()
    user, sess = await service.login(session, data.email, data.password, client_ip(request))
    response.set_cookie(
        s.session_cookie_name,
        sess.session_id,
        httponly=True,
        secure=s.session_cookie_secure,
        samesite="lax",
        path="/",
        max_age=s.session_absolute_timeout_seconds,
    )
    principal, grants = await service.load_principal(session, user.id)
    assert principal is not None  # noqa: S101 - just authenticated
    ctx = AuthContext(user=principal, permission="", grants=tuple(grants), session=sess)
    return await service.me(session, ctx)


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, ctx: AuthContext = Depends(authenticated)) -> None:
    await service.logout(ctx)
    response.delete_cookie(get_settings().session_cookie_name, path="/")


@auth_router.get("/me", response_model=MeOut)
async def me(session: Session, ctx: AuthContext = Depends(authenticated)) -> MeOut:
    return await service.me(session, ctx)


@auth_router.post(
    "/password-reset/request", response_model=MessageOut, status_code=status.HTTP_202_ACCEPTED
)
async def password_reset_request(
    data: PasswordResetRequestIn, request: Request, session: Session
) -> MessageOut:
    await service.request_password_reset(session, str(data.email), client_ip(request))
    return MessageOut(message="If the account exists, a reset link has been sent.")


@auth_router.post("/password-reset/confirm", response_model=MessageOut)
async def password_reset_confirm(data: PasswordResetConfirmIn, session: Session) -> MessageOut:
    await service.confirm_password_reset(session, data.token, data.new_password)
    return MessageOut(message="Password updated. Please log in.")


# --- users ---------------------------------------------------------------------------------


@router.get("/users", response_model=Page[UserOut])
async def list_users(
    session: Session,
    params: Annotated[UserListParams, Query()],
    _: AuthContext = Depends(require("user.manage")),
) -> Page[UserOut]:
    return await service.list_users(session, params)


@router.post("/users", response_model=UserDetailOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreateIn, session: Session, _: AuthContext = Depends(require("user.manage"))
) -> UserDetailOut:
    return await service.create_user(session, data)


@router.get("/users/{user_id}", response_model=UserDetailOut)
async def get_user(
    user_id: uuid.UUID, session: Session, _: AuthContext = Depends(require("user.manage"))
) -> UserDetailOut:
    return await service.get_user(session, user_id)


@router.patch("/users/{user_id}", response_model=UserDetailOut)
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdateIn,
    session: Session,
    ctx: AuthContext = Depends(require("user.manage")),
) -> UserDetailOut:
    return await service.update_user(session, user_id, data, ctx)


@router.post(
    "/users/{user_id}/role-assignments",
    response_model=RoleAssignmentOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_role_assignment(
    user_id: uuid.UUID,
    data: RoleAssignmentIn,
    session: Session,
    ctx: AuthContext = Depends(require("user.manage")),
) -> RoleAssignmentOut:
    return await service.add_role_assignment(session, user_id, data, ctx)


@router.delete(
    "/users/{user_id}/role-assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_role_assignment(
    user_id: uuid.UUID,
    assignment_id: uuid.UUID,
    session: Session,
    ctx: AuthContext = Depends(require("user.manage")),
) -> None:
    await service.remove_role_assignment(session, user_id, assignment_id, ctx)


# --- roles and permissions -----------------------------------------------------------------


@router.get("/roles", response_model=list[RoleOut])
async def list_roles(
    session: Session, _: AuthContext = Depends(require("user.manage", "role.manage"))
) -> list[RoleOut]:
    return await service.list_roles(session)


@router.post("/roles", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
async def create_role(
    data: RoleCreateIn, session: Session, _: AuthContext = Depends(require("role.manage"))
) -> RoleOut:
    return await service.create_role(session, data)


@router.put("/roles/{role_id}/permissions", response_model=RoleOut)
async def set_role_permissions(
    role_id: uuid.UUID,
    data: RolePermissionsIn,
    session: Session,
    _: AuthContext = Depends(require("role.manage")),
) -> RoleOut:
    return await service.set_role_permissions(session, role_id, data.permissions)


@router.get("/permissions", response_model=list[PermissionOut])
async def list_permissions(
    session: Session, _: AuthContext = Depends(require("user.manage", "role.manage"))
) -> list[PermissionOut]:
    return [
        PermissionOut(code=c, description=d) for c, d in await service.list_permissions(session)
    ]


# --- teams ---------------------------------------------------------------------------------


@router.get("/teams", response_model=list[TeamOut])
async def list_teams(
    session: Session, _: AuthContext = Depends(require("user.manage", "telemarketing.view_team"))
) -> list[TeamOut]:
    return await service.list_teams(session)


@router.post("/teams", response_model=TeamOut, status_code=status.HTTP_201_CREATED)
async def create_team(
    data: TeamIn, session: Session, _: AuthContext = Depends(require("user.manage"))
) -> TeamOut:
    return await service.create_team(session, data.name)


@router.get("/editions/{edition_id}/team", response_model=EditionTeamOut)
async def get_edition_team(
    edition_id: uuid.UUID,
    session: Session,
    ctx: AuthContext = Depends(require("edition.read")),
) -> EditionTeamOut:
    return await service.get_edition_team(session, ctx, edition_id)


@router.put("/editions/{edition_id}/team", response_model=EditionTeamOut)
async def set_edition_team(
    edition_id: uuid.UUID,
    data: EditionTeamIn,
    session: Session,
    ctx: AuthContext = Depends(require("edition.manage")),
) -> EditionTeamOut:
    return await service.set_edition_team(session, ctx, edition_id, data.team_id)


@router.post("/teams/{team_id}/members", response_model=TeamOut)
async def add_team_member(
    team_id: uuid.UUID,
    data: TeamMemberIn,
    session: Session,
    _: AuthContext = Depends(require("user.manage")),
) -> TeamOut:
    return await service.add_team_member(session, team_id, data.user_id)


@router.delete("/teams/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_team_member(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    session: Session,
    _: AuthContext = Depends(require("user.manage")),
) -> None:
    await service.remove_team_member(session, team_id, user_id)
