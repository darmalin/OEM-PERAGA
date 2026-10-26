"""Identity queries. Users, roles, and teams are global (not edition data)."""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Row, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models import (
    EditionTeam,
    PasswordResetToken,
    Permission,
    Role,
    RolePermission,
    Team,
    User,
    UserRoleAssignment,
    UserTeamMembership,
)


async def get_user(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def touch_last_login(session: AsyncSession, user_id: uuid.UUID, at: datetime) -> None:
    """Plain UPDATE so a login does not bump the user's form version."""
    await session.execute(update(User).where(User.id == user_id).values(last_login_at=at))


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email))


async def list_users(
    session: AsyncSession,
    q: str | None,
    is_active: bool | None,
    offset: int,
    limit: int,
    edition_ids: set[uuid.UUID] | None = None,
) -> tuple[Sequence[User], int]:
    """edition_ids None: everyone. Otherwise users with a role in those editions, or none."""
    stmt = select(User)
    if edition_ids is not None:
        has_any = select(UserRoleAssignment.id).where(UserRoleAssignment.user_id == User.id)
        has_inside = has_any.where(UserRoleAssignment.edition_id.in_(edition_ids))
        stmt = stmt.where(or_(~has_any.exists(), has_inside.exists()))
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(User.full_name).like(like), User.email.like(like)))
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = await session.scalars(stmt.order_by(User.full_name, User.id).offset(offset).limit(limit))
    return rows.all(), total


async def grant_rows(
    session: AsyncSession, user_id: uuid.UUID
) -> Sequence[Row[UserRoleAssignment, str, str]]:
    """One row per (assignment, permission code)."""
    stmt = (
        select(UserRoleAssignment, Role.code, Permission.code)
        .join(Role, Role.id == UserRoleAssignment.role_id)
        .join(RolePermission, RolePermission.role_id == Role.id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(UserRoleAssignment.user_id == user_id)
    )
    return (await session.execute(stmt)).all()


async def list_assignments(
    session: AsyncSession, user_id: uuid.UUID
) -> Sequence[Row[UserRoleAssignment, str]]:
    stmt = (
        select(UserRoleAssignment, Role.code)
        .join(Role, Role.id == UserRoleAssignment.role_id)
        .where(UserRoleAssignment.user_id == user_id)
        .order_by(UserRoleAssignment.created_at)
    )
    return (await session.execute(stmt)).all()


async def get_assignment(
    session: AsyncSession, user_id: uuid.UUID, assignment_id: uuid.UUID
) -> UserRoleAssignment | None:
    return await session.scalar(
        select(UserRoleAssignment).where(
            UserRoleAssignment.id == assignment_id, UserRoleAssignment.user_id == user_id
        )
    )


async def user_team_ids(session: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    rows = await session.scalars(
        select(UserTeamMembership.team_id).where(UserTeamMembership.user_id == user_id)
    )
    return list(rows.all())


async def users_with_permission(
    session: AsyncSession,
    edition_id: uuid.UUID,
    permission: str,
    team_ids: set[uuid.UUID] | None,
) -> Sequence[User]:
    """Active users holding the permission in the edition, optionally limited to teams."""
    stmt = (
        select(User)
        .join(UserRoleAssignment, UserRoleAssignment.user_id == User.id)
        .join(RolePermission, RolePermission.role_id == UserRoleAssignment.role_id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(
            User.is_active.is_(True),
            Permission.code == permission,
            or_(
                UserRoleAssignment.edition_id == edition_id,
                UserRoleAssignment.edition_id.is_(None),
            ),
        )
        .distinct()
        .order_by(User.full_name, User.id)
    )
    if team_ids is not None:
        stmt = stmt.where(
            User.id.in_(
                select(UserTeamMembership.user_id).where(UserTeamMembership.team_id.in_(team_ids))
            )
        )
    return (await session.scalars(stmt)).all()


async def team_ids_by_user(
    session: AsyncSession, user_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[uuid.UUID]]:
    rows = await session.execute(
        select(UserTeamMembership.user_id, UserTeamMembership.team_id).where(
            UserTeamMembership.user_id.in_(user_ids)
        )
    )
    out: dict[uuid.UUID, list[uuid.UUID]] = {}
    for user_id, team_id in rows.all():
        out.setdefault(user_id, []).append(team_id)
    return out


async def get_role(session: AsyncSession, role_id: uuid.UUID) -> Role | None:
    return await session.get(Role, role_id)


async def get_role_by_code(session: AsyncSession, code: str) -> Role | None:
    return await session.scalar(select(Role).where(Role.code == code))


async def list_roles_with_permissions(
    session: AsyncSession,
) -> list[tuple[Role, list[str]]]:
    roles = (
        await session.scalars(select(Role).order_by(Role.sort_order, Role.name, Role.code))
    ).all()
    rows = await session.execute(
        select(RolePermission.role_id, Permission.code).join(
            Permission, Permission.id == RolePermission.permission_id
        )
    )
    perms: dict[uuid.UUID, list[str]] = {}
    for role_id, code in rows.all():
        perms.setdefault(role_id, []).append(code)
    return [(r, sorted(perms.get(r.id, []))) for r in roles]


async def list_permissions(session: AsyncSession) -> Sequence[Permission]:
    return (await session.scalars(select(Permission).order_by(Permission.code))).all()


async def permission_ids(session: AsyncSession, codes: list[str]) -> dict[str, uuid.UUID]:
    rows = await session.execute(
        select(Permission.code, Permission.id).where(Permission.code.in_(codes))
    )
    return {code: pid for code, pid in rows.all()}


async def replace_role_permissions(
    session: AsyncSession, role_id: uuid.UUID, permission_ids: list[uuid.UUID]
) -> None:
    await session.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
    session.add_all(RolePermission(role_id=role_id, permission_id=p) for p in permission_ids)
    await session.flush()


async def get_team(session: AsyncSession, team_id: uuid.UUID) -> Team | None:
    return await session.get(Team, team_id)


async def list_teams(session: AsyncSession) -> list[tuple[Team, list[uuid.UUID]]]:
    teams = (await session.scalars(select(Team).order_by(Team.name))).all()
    rows = await session.execute(select(UserTeamMembership.team_id, UserTeamMembership.user_id))
    members: dict[uuid.UUID, list[uuid.UUID]] = {}
    for team_id, user_id in rows.all():
        members.setdefault(team_id, []).append(user_id)
    return [(t, members.get(t.id, [])) for t in teams]


async def team_member_ids(session: AsyncSession, team_id: uuid.UUID) -> list[uuid.UUID]:
    rows = await session.scalars(
        select(UserTeamMembership.user_id).where(UserTeamMembership.team_id == team_id)
    )
    return list(rows.all())


async def get_membership(
    session: AsyncSession, team_id: uuid.UUID, user_id: uuid.UUID
) -> UserTeamMembership | None:
    return await session.get(UserTeamMembership, (team_id, user_id))


async def get_reset_token(session: AsyncSession, token_hash: str) -> PasswordResetToken | None:
    return await session.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == token_hash)
        .with_for_update()
    )


async def edition_team_id(session: AsyncSession, edition_id: uuid.UUID) -> uuid.UUID | None:
    return await session.scalar(
        select(EditionTeam.team_id).where(EditionTeam.edition_id == edition_id)
    )


async def team_exists(session: AsyncSession, team_id: uuid.UUID) -> bool:
    return await session.scalar(select(Team.id).where(Team.id == team_id)) is not None


async def set_edition_team(
    session: AsyncSession,
    edition_id: uuid.UUID,
    team_id: uuid.UUID | None,
    actor_id: uuid.UUID | None,
) -> None:
    await session.execute(delete(EditionTeam).where(EditionTeam.edition_id == edition_id))
    if team_id is not None:
        session.add(EditionTeam(edition_id=edition_id, team_id=team_id, created_by=actor_id))
    await session.flush()


async def role_permission_codes(session: AsyncSession, role_id: uuid.UUID) -> set[str]:
    rows = await session.scalars(
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == role_id)
    )
    return set(rows.all())
