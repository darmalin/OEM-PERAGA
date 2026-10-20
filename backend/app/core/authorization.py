"""Permission + scope checks used by every module (BACKEND_RULES/security-permissions.md).

`require("visitor.read")` returns an AuthContext or raises 401/403.
`ctx.scope_for(edition_id)` resolves what the caller may see in that edition or raises 404.
Repositories apply the Scope in SQL; results are never filtered in Python.
"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import sessions
from app.core.config import get_settings
from app.core.context import actor_id_var
from app.core.db import get_session
from app.core.errors import NotAuthenticated, NotFound, PermissionDenied
from app.modules.identity.rules import PERMISSIONS, ScopeType

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


@dataclass(frozen=True)
class Grant:
    """One role assignment, flattened to the permissions it carries."""

    permissions: frozenset[str]
    scope_type: ScopeType
    edition_id: uuid.UUID | None
    team_id: uuid.UUID | None = None
    gate_id: uuid.UUID | None = None

    def covers(self, edition_id: uuid.UUID) -> bool:
        return self.edition_id is None or self.edition_id == edition_id


@dataclass(frozen=True)
class Scope:
    """What the caller may access inside one edition.

    full_access: every record in the edition (EDITION scope).
    Otherwise records owned by user_id or by members of team_ids; gate data limited to gate_ids.
    """

    edition_id: uuid.UUID
    user_id: uuid.UUID
    full_access: bool
    team_ids: frozenset[uuid.UUID] = field(default_factory=frozenset)
    gate_ids: frozenset[uuid.UUID] = field(default_factory=frozenset)
    owned: bool = False

    @property
    def gate_only(self) -> bool:
        return not self.full_access and not self.team_ids and not self.owned


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    email: str
    full_name: str


@dataclass(frozen=True)
class AuthContext:
    user: CurrentUser
    permission: str
    grants: tuple[Grant, ...]
    session: sessions.SessionData | None = None

    def has(self, permission: str, edition_id: uuid.UUID | None = None) -> bool:
        return any(
            permission in g.permissions and (edition_id is None or g.covers(edition_id))
            for g in self.grants
        )

    def _grants_for(self, permission: str, edition_id: uuid.UUID) -> list[Grant]:
        return [g for g in self.grants if permission in g.permissions and g.covers(edition_id)]

    def scope_for(self, edition_id: uuid.UUID, permission: str | None = None) -> Scope:
        """Resolve the scope for the required permission, or 404 to hide the edition."""
        grants = self._grants_for(permission or self.permission, edition_id)
        if not grants:
            raise NotFound("Edition not found.", code="EDITION_NOT_FOUND")
        return Scope(
            edition_id=edition_id,
            user_id=self.user.id,
            full_access=any(g.scope_type == ScopeType.EDITION for g in grants),
            team_ids=frozenset(
                g.team_id for g in grants if g.scope_type == ScopeType.TEAM and g.team_id
            ),
            gate_ids=frozenset(
                g.gate_id for g in grants if g.scope_type == ScopeType.GATE and g.gate_id
            ),
            owned=any(g.scope_type == ScopeType.OWNED for g in grants),
        )

    def edition_ids(self, permission: str | None = None) -> set[uuid.UUID] | None:
        """Editions the permission applies to; None means every edition."""
        perm = permission or self.permission
        ids: set[uuid.UUID] = set()
        for g in self.grants:
            if perm not in g.permissions:
                continue
            if g.edition_id is None:
                return None
            ids.add(g.edition_id)
        return ids

    def has_global(self, permission: str) -> bool:
        return any(
            permission in g.permissions
            and g.edition_id is None
            and g.scope_type == ScopeType.EDITION
            for g in self.grants
        )


async def load_auth(request: Request, session: AsyncSession) -> AuthContext:
    """Authenticate the session cookie and load the user's grants."""
    from app.modules.identity import service as identity_service

    cookie = request.cookies.get(get_settings().session_cookie_name)
    sess = await sessions.load(cookie) if cookie else None
    if sess is None:
        raise NotAuthenticated()
    if request.method in UNSAFE_METHODS and not sessions.csrf_matches(
        sess, request.headers.get("X-CSRF-Token")
    ):
        raise PermissionDenied("CSRF token missing or invalid.", code="CSRF_FAILED")
    user, grants = await identity_service.load_principal(session, sess.user_id)
    if user is None:
        await sessions.destroy(sess.session_id)
        raise NotAuthenticated()
    actor_id_var.set(user.id)
    return AuthContext(user=user, permission="", grants=tuple(grants), session=sess)


def require(*permissions: str) -> Callable[..., Awaitable[AuthContext]]:
    """Dependency: caller must hold at least one of the permissions in some scope."""
    for p in permissions:
        if p not in PERMISSIONS:
            raise ValueError(f"unknown permission {p}")

    async def dependency(
        request: Request, session: AsyncSession = Depends(get_session)
    ) -> AuthContext:
        ctx = await load_auth(request, session)
        for p in permissions:
            if ctx.has(p):
                return AuthContext(ctx.user, p, ctx.grants, ctx.session)
        raise PermissionDenied()

    dependency.__ems_require__ = permissions  # type: ignore[attr-defined]
    return dependency


async def authenticated(
    request: Request, session: AsyncSession = Depends(get_session)
) -> AuthContext:
    """Dependency for endpoints any logged-in user may call (e.g. /auth/me)."""
    return await load_auth(request, session)


authenticated.__ems_require__ = ()  # type: ignore[attr-defined]


def is_guard(dependency: Any) -> bool:
    return hasattr(dependency, "__ems_require__")
