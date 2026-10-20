import contextlib
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from pwdlib import PasswordHash
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import outbox, ratelimit, sessions
from app.core.authorization import AuthContext, CurrentUser, Grant
from app.core.config import get_settings
from app.core.context import current_actor_id
from app.core.crypto import encrypt, new_token, sha256_hex
from app.core.errors import (
    Conflict,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    RateLimited,
    ValidationFailed,
    check_version,
)
from app.core.pagination import Page
from app.modules.identity import repository as repo
from app.modules.identity.models import (
    PasswordResetToken,
    Role,
    Team,
    User,
    UserRoleAssignment,
    UserTeamMembership,
)
from app.modules.identity.rules import PERMISSIONS, ScopeType, normalize_email, password_problems
from app.modules.identity.schemas import (
    GrantOut,
    MeOut,
    RoleAssignmentIn,
    RoleAssignmentOut,
    RoleCreateIn,
    RoleOut,
    TeamOut,
    UserBrief,
    UserCreateIn,
    UserDetailOut,
    UserListParams,
    UserOut,
    UserUpdateIn,
)

_hasher = PasswordHash.recommended()
# Verified against when the email is unknown, so timing does not reveal which emails exist.
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing")


def hash_password(password: str) -> str:
    problems = password_problems(password, get_settings().password_min_length)
    if problems:
        raise ValidationFailed(fields={"password": " ".join(problems)})
    return _hasher.hash(password)


# --- principal ---------------------------------------------------------------------------


async def load_principal(
    session: AsyncSession, user_id: uuid.UUID
) -> tuple[CurrentUser | None, list[Grant]]:
    """Load an active user and their grants; (None, []) when missing or deactivated."""
    user = await repo.get_user(session, user_id)
    if user is None or not user.is_active:
        return None, []
    perms: dict[uuid.UUID, set[str]] = defaultdict(set)
    assignments: dict[uuid.UUID, UserRoleAssignment] = {}
    for assignment, _role_code, perm_code in await repo.grant_rows(session, user_id):
        perms[assignment.id].add(perm_code)
        assignments[assignment.id] = assignment
    grants = [
        Grant(
            permissions=frozenset(perms[a.id]),
            scope_type=ScopeType(a.scope_type),
            edition_id=a.edition_id,
            team_id=a.team_id,
            gate_id=getattr(a, "gate_id", None),
        )
        for a in assignments.values()
    ]
    return CurrentUser(user.id, user.email, user.full_name), grants


async def me(session: AsyncSession, ctx: AuthContext) -> MeOut:
    """Current user, effective permissions, and grants."""
    rows = await repo.list_assignments(session, ctx.user.id)
    assert ctx.session is not None  # noqa: S101 - set by load_auth
    return MeOut(
        user=UserBrief(id=ctx.user.id, email=ctx.user.email, full_name=ctx.user.full_name),
        permissions=sorted({p for g in ctx.grants for p in g.permissions}),
        grants=[
            GrantOut(
                role_code=code,
                scope_type=ScopeType(a.scope_type),
                edition_id=a.edition_id,
                team_id=a.team_id,
                gate_id=getattr(a, "gate_id", None),
            )
            for a, code in rows
        ],
        csrf_token=ctx.session.csrf_token,
    )


# --- login / logout ------------------------------------------------------------------------


async def login(
    session: AsyncSession, email: str, password: str, client_ip: str
) -> tuple[User, sessions.SessionData]:
    """Verify credentials with per-IP and per-account limits, then open a new session."""
    s = get_settings()
    email = normalize_email(email)
    account_key = f"login:acct:{sha256_hex(email)}"
    await ratelimit.hit(
        f"login:ip:{client_ip}", s.login_max_attempts_per_ip, s.login_window_seconds
    )
    if await ratelimit.count(account_key) >= s.login_max_failures_per_account:
        raise RateLimited("Account temporarily locked. Try again later.", code="ACCOUNT_LOCKED")

    user = await repo.get_user_by_email(session, email)
    valid = _hasher.verify(
        password, user.password_hash if user and user.password_hash else _DUMMY_HASH
    )
    if not (user and user.is_active and user.password_hash and valid):
        # The lockout itself is enforced above on the next attempt.
        with contextlib.suppress(RateLimited):
            await ratelimit.hit(
                account_key, s.login_max_failures_per_account, s.login_window_seconds
            )
        raise NotAuthenticated("Invalid email or password.", code="INVALID_CREDENTIALS")

    await ratelimit.reset(account_key)
    await repo.touch_last_login(session, user.id, datetime.now(UTC))
    # A fresh session ID on every login prevents session fixation.
    return user, await sessions.create(user.id)


async def logout(ctx: AuthContext) -> None:
    if ctx.session:
        await sessions.destroy(ctx.session.session_id)


# --- password reset ------------------------------------------------------------------------


async def request_password_reset(session: AsyncSession, email: str, client_ip: str) -> None:
    """Always succeeds from the caller's view; never reveals whether the email exists."""
    await ratelimit.hit(f"pwreset:ip:{client_ip}", 10, 3600)
    email = normalize_email(email)
    await ratelimit.hit(f"pwreset:acct:{sha256_hex(email)}", 3, 3600)
    user = await repo.get_user_by_email(session, email)
    if user is None or not user.is_active:
        return
    token = new_token()
    record = PasswordResetToken(
        user_id=user.id,
        token_hash=sha256_hex(token),
        expires_at=datetime.now(UTC) + timedelta(seconds=get_settings().password_reset_ttl_seconds),
    )
    session.add(record)
    await session.flush()
    await outbox.enqueue(
        session,
        "identity.password_reset_requested",
        "identity.send_password_reset",
        {"reset_id": str(record.id), "token_enc": encrypt(token)},
        queue="email",
    )


async def confirm_password_reset(session: AsyncSession, token: str, new_password: str) -> None:
    """Single-use, short-lived token; all existing sessions are dropped."""
    record = await repo.get_reset_token(session, sha256_hex(token))
    now = datetime.now(UTC)
    if record is None or record.used_at is not None or record.expires_at < now:
        raise ValidationFailed("Reset link is invalid or expired.", code="RESET_TOKEN_INVALID")
    user = await repo.get_user(session, record.user_id)
    if user is None or not user.is_active:
        raise ValidationFailed("Reset link is invalid or expired.", code="RESET_TOKEN_INVALID")
    user.password_hash = hash_password(new_password)
    record.used_at = now
    await session.flush()
    await sessions.destroy_all_for_user(user.id)


# --- users ---------------------------------------------------------------------------------


async def _user_detail(session: AsyncSession, user: User) -> UserDetailOut:
    rows = await repo.list_assignments(session, user.id)
    return UserDetailOut(
        **UserOut.model_validate(user).model_dump(),
        role_assignments=[_assignment_out(a, code) for a, code in rows],
        team_ids=await repo.user_team_ids(session, user.id),
    )


def _assignment_out(a: UserRoleAssignment, role_code: str) -> RoleAssignmentOut:
    return RoleAssignmentOut(
        id=a.id,
        role_id=a.role_id,
        role_code=role_code,
        scope_type=ScopeType(a.scope_type),
        edition_id=a.edition_id,
        team_id=a.team_id,
        created_at=a.created_at,
    )


async def list_users(session: AsyncSession, params: UserListParams) -> Page[UserOut]:
    """Paginated user list with search."""
    rows, total = await repo.list_users(
        session, params.q, params.is_active, params.offset, params.page_size
    )
    return Page(
        items=[UserOut.model_validate(u) for u in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def get_user(session: AsyncSession, user_id: uuid.UUID) -> UserDetailOut:
    user = await repo.get_user(session, user_id)
    if user is None:
        raise NotFound("User not found.")
    return await _user_detail(session, user)


async def create_user(session: AsyncSession, data: UserCreateIn) -> UserDetailOut:
    """Create a user with a password that passes the policy."""
    email = normalize_email(data.email)
    if await repo.get_user_by_email(session, email):
        raise Conflict(
            "Email already in use.", code="DUPLICATE_USER", fields={"email": "Already in use."}
        )
    actor = current_actor_id()
    user = User(
        email=email,
        full_name=data.full_name.strip(),
        password_hash=hash_password(data.password),
        is_active=True,
        created_by=actor,
        updated_by=actor,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as e:
        raise Conflict(
            "Email already in use.", code="DUPLICATE_USER", fields={"email": "Already in use."}
        ) from e
    await session.refresh(user)
    return await _user_detail(session, user)


async def update_user(
    session: AsyncSession, user_id: uuid.UUID, data: UserUpdateIn, ctx: AuthContext
) -> UserDetailOut:
    """Edit name or active flag; deactivation kills sessions immediately."""
    user = await repo.get_user(session, user_id)
    if user is None:
        raise NotFound("User not found.")
    check_version(user.version, data.version)
    if data.is_active is False and user.id == ctx.user.id:
        raise ValidationFailed(fields={"is_active": "You cannot deactivate yourself."})
    if data.full_name is not None:
        user.full_name = data.full_name.strip()
    if data.is_active is not None:
        user.is_active = data.is_active
    user.updated_by = ctx.user.id
    await session.flush()
    await session.refresh(user)
    if not user.is_active:
        await sessions.destroy_all_for_user(user.id)
    return await _user_detail(session, user)


def _check_can_grant(ctx: AuthContext, edition_id: uuid.UUID | None) -> None:
    """Edition admins may only grant within editions where they hold user.manage fully."""
    if edition_id is None:
        if not ctx.has_global("user.manage"):
            raise PermissionDenied("Only global administrators can grant cross-edition roles.")
        return
    if not ctx.scope_for(edition_id, "user.manage").full_access:
        raise PermissionDenied()


async def add_role_assignment(
    session: AsyncSession, user_id: uuid.UUID, data: RoleAssignmentIn, ctx: AuthContext
) -> RoleAssignmentOut:
    """Grant a role with a scope."""
    user = await repo.get_user(session, user_id)
    if user is None:
        raise NotFound("User not found.")
    role = await repo.get_role(session, data.role_id)
    if role is None:
        raise ValidationFailed(fields={"role_id": "Unknown role."})
    if data.team_id is not None and await repo.get_team(session, data.team_id) is None:
        raise ValidationFailed(fields={"team_id": "Unknown team."})
    _check_can_grant(ctx, data.edition_id)
    assignment = UserRoleAssignment(
        user_id=user.id,
        role_id=role.id,
        scope_type=data.scope_type,
        edition_id=data.edition_id,
        team_id=data.team_id,
        created_by=ctx.user.id,
    )
    session.add(assignment)
    try:
        await session.flush()
    except IntegrityError as e:
        raise ValidationFailed(fields={"edition_id": "Unknown edition."}) from e
    await session.refresh(assignment)
    return _assignment_out(assignment, role.code)


async def remove_role_assignment(
    session: AsyncSession, user_id: uuid.UUID, assignment_id: uuid.UUID, ctx: AuthContext
) -> None:
    """Revoke one role assignment."""
    assignment = await repo.get_assignment(session, user_id, assignment_id)
    if assignment is None:
        raise NotFound("Role assignment not found.")
    _check_can_grant(ctx, assignment.edition_id)
    await session.delete(assignment)
    await session.flush()


# --- roles ---------------------------------------------------------------------------------


def _role_out(role: Role, perms: list[str]) -> RoleOut:
    return RoleOut(
        id=role.id,
        code=role.code,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permissions=perms,
    )


async def list_roles(session: AsyncSession) -> list[RoleOut]:
    """Roles with their permission codes (the permission matrix)."""
    return [_role_out(r, p) for r, p in await repo.list_roles_with_permissions(session)]


async def list_permissions(session: AsyncSession) -> list[tuple[str, str]]:
    return [(p.code, p.description) for p in await repo.list_permissions(session)]


async def _permission_ids(session: AsyncSession, codes: list[str]) -> list[uuid.UUID]:
    unknown = sorted(set(codes) - set(PERMISSIONS))
    if unknown:
        raise ValidationFailed(fields={"permissions": f"Unknown: {', '.join(unknown)}"})
    ids = await repo.permission_ids(session, sorted(set(codes)))
    return list(ids.values())


async def create_role(session: AsyncSession, data: RoleCreateIn) -> RoleOut:
    """Create a custom role (bundle of permissions)."""
    if await repo.get_role_by_code(session, data.code):
        raise Conflict("Role code already exists.", fields={"code": "Already exists."})
    role = Role(code=data.code, name=data.name, description=data.description, is_system=False)
    session.add(role)
    await session.flush()
    await repo.replace_role_permissions(
        session, role.id, await _permission_ids(session, data.permissions)
    )
    await session.refresh(role)
    return _role_out(role, sorted(set(data.permissions)))


async def set_role_permissions(
    session: AsyncSession, role_id: uuid.UUID, codes: list[str]
) -> RoleOut:
    """Replace a role's permissions. SUPER_ADMIN always keeps every permission."""
    role = await repo.get_role(session, role_id)
    if role is None:
        raise NotFound("Role not found.")
    if role.code == "SUPER_ADMIN":
        raise ValidationFailed("SUPER_ADMIN permissions cannot be changed.", code="ROLE_LOCKED")
    await repo.replace_role_permissions(session, role.id, await _permission_ids(session, codes))
    return _role_out(role, sorted(set(codes)))


# --- teams ---------------------------------------------------------------------------------


async def list_teams(session: AsyncSession) -> list[TeamOut]:
    return [TeamOut(id=t.id, name=t.name, member_ids=m) for t, m in await repo.list_teams(session)]


async def create_team(session: AsyncSession, name: str) -> TeamOut:
    """Create a team."""
    team = Team(name=name.strip(), created_by=current_actor_id(), updated_by=current_actor_id())
    session.add(team)
    try:
        await session.flush()
    except IntegrityError as e:
        raise Conflict("Team name already exists.", fields={"name": "Already exists."}) from e
    return TeamOut(id=team.id, name=team.name, member_ids=[])


async def add_team_member(session: AsyncSession, team_id: uuid.UUID, user_id: uuid.UUID) -> TeamOut:
    """Add a user to a team (idempotent)."""
    team = await repo.get_team(session, team_id)
    if team is None:
        raise NotFound("Team not found.")
    if await repo.get_user(session, user_id) is None:
        raise ValidationFailed(fields={"user_id": "Unknown user."})
    if await repo.get_membership(session, team_id, user_id) is None:
        session.add(UserTeamMembership(team_id=team_id, user_id=user_id))
        await session.flush()
    return TeamOut(
        id=team.id, name=team.name, member_ids=await repo.team_member_ids(session, team_id)
    )


async def remove_team_member(session: AsyncSession, team_id: uuid.UUID, user_id: uuid.UUID) -> None:
    membership = await repo.get_membership(session, team_id, user_id)
    if membership is None:
        raise NotFound("Membership not found.")
    await session.delete(membership)
    await session.flush()


async def user_exists_active(session: AsyncSession, user_id: uuid.UUID) -> bool:
    user = await repo.get_user(session, user_id)
    return bool(user and user.is_active)


async def create_superuser(
    session: AsyncSession, email: str, full_name: str, password: str
) -> User:
    """Bootstrap: user with SUPER_ADMIN on every edition."""
    role = await repo.get_role_by_code(session, "SUPER_ADMIN")
    if role is None:
        raise RuntimeError("roles are not seeded; run migrations first")
    email = normalize_email(email)
    user = await repo.get_user_by_email(session, email)
    if user is None:
        user = User(email=email, full_name=full_name, password_hash=hash_password(password))
        session.add(user)
        await session.flush()
    session.add(UserRoleAssignment(user_id=user.id, role_id=role.id, scope_type=ScopeType.EDITION))
    await session.flush()
    return user
