"""Test data builders. All fixture data is clearly fake (example.test)."""

import itertools
import uuid
from dataclasses import dataclass
from datetime import date

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.main import app
from app.modules.checkin.models import Gate
from app.modules.exhibitions.models import Edition, EditionCounter, Exhibition
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
                gate_id=g.gate_id,
            )
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


async def make_edition(
    *, exhibition_code: str | None = None, year: int = 2027, timezone: str = "Asia/Jakarta"
) -> Edition:
    """Exhibition + ACTIVE edition + Registration ID counter."""
    n = next(_seq)
    code = exhibition_code or f"EX{n:04d}"
    async with get_sessionmaker()() as session, session.begin():
        ex = await session.scalar(select(Exhibition).where(Exhibition.code == code))
        if ex is None:
            ex = Exhibition(code=code, name=f"Exhibition {code}")
            session.add(ex)
            await session.flush()
        edition = Edition(
            exhibition_id=ex.id,
            year=year,
            code=f"{code}{year}",
            name=f"{code} {year}",
            start_date=date(year, 3, 10),
            end_date=date(year, 3, 12),
            timezone=timezone,
            default_currency="IDR",
            registration_id_prefix=f"{code}{year}",
            status="ACTIVE",
        )
        session.add(edition)
        await session.flush()
        session.add(EditionCounter(edition_id=edition.id, last_value=0))
        return edition


async def make_gate(edition: Edition, code: str | None = None) -> Gate:
    n = next(_seq)
    async with get_sessionmaker()() as session, session.begin():
        gate = Gate(edition_id=edition.id, code=code or f"G{n:04d}", name=f"Gate {n:04d}")
        session.add(gate)
        await session.flush()
        return gate
