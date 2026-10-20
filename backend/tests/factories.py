"""Test data builders. All fixture data is clearly fake (example.test)."""

import itertools
import uuid
from dataclasses import dataclass

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.main import app
from app.modules.identity.models import Role, User, UserRoleAssignment, UserTeamMembership
from app.modules.identity.service import hash_password

PASSWORD = "correct-horse-battery-staple"
_seq = itertools.count(1)


@dataclass(frozen=True)
class RoleGrant:
    role: str
    scope: str = "EDITION"
    edition_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    gate_id: uuid.UUID | None = None


async def make_user(
    *grants: RoleGrant,
    email: str | None = None,
    teams: tuple[uuid.UUID, ...] = (),
    active: bool = True,
) -> User:
    n = next(_seq)
    async with get_sessionmaker()() as session, session.begin():
        user = User(
            email=email or f"user-{n:04d}@example.test",
            full_name=f"Test User {n:04d}",
            password_hash=hash_password(PASSWORD),
            is_active=active,
        )
        session.add(user)
        await session.flush()
        for g in grants:
            role_id = await session.scalar(select(Role.id).where(Role.code == g.role))
            assert role_id is not None, g.role
            assignment = UserRoleAssignment(
                user_id=user.id,
                role_id=role_id,
                scope_type=g.scope,
                edition_id=g.edition_id,
                team_id=g.team_id,
            )
            if g.gate_id is not None:
                assignment.gate_id = g.gate_id  # type: ignore[attr-defined]
            session.add(assignment)
        for team_id in teams:
            session.add(UserTeamMembership(team_id=team_id, user_id=user.id))
        await session.flush()
        return user


async def login_client(email: str, password: str = PASSWORD) -> AsyncClient:
    """A client with a live session cookie and the CSRF header preset."""
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    client.headers["X-CSRF-Token"] = r.json()["csrf_token"]
    return client


async def actor(*grants: RoleGrant, teams: tuple[uuid.UUID, ...] = ()) -> tuple[User, AsyncClient]:
    user = await make_user(*grants, teams=teams)
    return user, await login_client(user.email)
