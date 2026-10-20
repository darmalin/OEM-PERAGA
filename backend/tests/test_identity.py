import uuid

import pytest
from fastapi.routing import APIRoute
from httpx import AsyncClient
from sqlalchemy import select

from app.core.authorization import AuthContext, CurrentUser, Grant, is_guard
from app.core.db import get_sessionmaker
from app.core.email import MemorySender
from app.core.errors import NotFound
from app.core.outbox import OutboxEvent
from app.main import app
from app.modules.identity.rules import BASELINE_ROLES, PERMISSIONS, ScopeType, password_problems
from app.modules.identity.tasks import send_password_reset_email
from tests.factories import PASSWORD, RoleGrant, actor, login_client, make_edition, make_user

# Routes reachable without a permission guard (BACKEND_RULES/security-permissions.md).
PUBLIC_ROUTES = {
    ("GET", "/api/v1/health/live"),
    ("GET", "/api/v1/health/ready"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/password-reset/request"),
    ("POST", "/api/v1/auth/password-reset/confirm"),
}


def _guarded(route: APIRoute) -> bool:
    stack = list(route.dependant.dependencies)
    while stack:
        dep = stack.pop()
        if is_guard(dep.call):
            return True
        stack.extend(dep.dependencies)
    return False


def test_every_route_requires_a_permission() -> None:
    missing = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods:
            if (method, route.path) in PUBLIC_ROUTES or route.path.startswith("/api/v1/public/"):
                continue
            if route.path.startswith("/api/v1/gate/device/"):
                continue  # device-credential endpoints, checked in test_gate
            if not _guarded(route):
                missing.append(f"{method} {route.path}")
    assert missing == []


def test_seeded_roles_only_reference_known_permissions() -> None:
    for _name, perms in BASELINE_ROLES.values():
        assert set(perms) <= set(PERMISSIONS)
    assert "visitor.export" not in BASELINE_ROLES["TELEMARKETING_AGENT"][1]


@pytest.mark.parametrize(
    ("password", "ok"),
    [("short", False), ("password1234", False), ("aaaaaaaaaaaaaaaa", False), (PASSWORD, True)],
)
def test_password_policy(password: str, ok: bool) -> None:
    assert (password_problems(password, 12) == []) is ok


def _ctx(*grants: Grant) -> AuthContext:
    return AuthContext(CurrentUser(uuid.uuid4(), "a@example.test", "A"), "visitor.read", grants)


def test_scope_resolution() -> None:
    e1, e2, team = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    perms = frozenset({"visitor.read"})
    ctx = _ctx(Grant(perms, ScopeType.OWNED, e1), Grant(perms, ScopeType.TEAM, e1, team))
    scope = ctx.scope_for(e1)
    assert not scope.full_access and scope.owned and scope.team_ids == {team}
    with pytest.raises(NotFound):
        ctx.scope_for(e2)
    assert ctx.edition_ids() == {e1}

    glob = _ctx(Grant(perms, ScopeType.EDITION, None))
    assert glob.scope_for(e2).full_access
    assert glob.edition_ids() is None


async def test_login_me_and_cookie_flags(client: AsyncClient) -> None:
    edition = (await make_edition()).id
    user = await make_user(RoleGrant("TELEMARKETING_AGENT", "OWNED", edition))
    r = await client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    assert r.status_code == 200
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    me = (await client.get("/api/v1/auth/me")).json()
    assert me["user"]["email"] == user.email
    assert "telemarketing.call" in me["permissions"]
    assert me["grants"] == [
        {
            "role_code": "TELEMARKETING_AGENT",
            "scope_type": "OWNED",
            "edition_id": str(edition),
            "team_id": None,
            "gate_id": None,
        }
    ]


async def test_wrong_password_then_lockout(client: AsyncClient) -> None:
    user = await make_user()
    for _ in range(5):
        r = await client.post(
            "/api/v1/auth/login", json={"email": user.email, "password": "x" * 12}
        )
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"
    r = await client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "ACCOUNT_LOCKED"


async def test_unknown_email_same_error(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.test", "password": PASSWORD}
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_not_logged_in_is_401(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    assert (await client.get("/api/v1/users")).status_code == 401


async def test_csrf_required_on_unsafe_methods() -> None:
    _, c = await actor(RoleGrant("SUPER_ADMIN"))
    del c.headers["X-CSRF-Token"]
    r = await c.post("/api/v1/teams", json={"name": "Team A"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "CSRF_FAILED"
    r = await c.post("/api/v1/teams", json={"name": "Team A"}, headers={"X-CSRF-Token": "wrong"})
    assert r.status_code == 403


async def test_logout_kills_session() -> None:
    _, c = await actor(RoleGrant("SUPER_ADMIN"))
    assert (await c.post("/api/v1/auth/logout")).status_code == 204
    c.cookies.clear()
    assert (await c.get("/api/v1/auth/me")).status_code == 401


async def test_deactivation_invalidates_sessions_immediately() -> None:
    _, admin = await actor(RoleGrant("SUPER_ADMIN"))
    victim = await make_user(RoleGrant("TELEMARKETING_AGENT", "OWNED", (await make_edition()).id))
    victim_client = await login_client(victim.email)
    assert (await victim_client.get("/api/v1/auth/me")).status_code == 200
    r = await admin.patch(f"/api/v1/users/{victim.id}", json={"version": 1, "is_active": False})
    assert r.status_code == 200, r.text
    assert (await victim_client.get("/api/v1/auth/me")).status_code == 401


async def test_user_update_version_conflict() -> None:
    _, admin = await actor(RoleGrant("SUPER_ADMIN"))
    user = await make_user()
    r = await admin.patch(f"/api/v1/users/{user.id}", json={"version": 1, "full_name": "New"})
    assert r.status_code == 200
    r = await admin.patch(f"/api/v1/users/{user.id}", json={"version": 1, "full_name": "Again"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "VERSION_CONFLICT"


async def test_password_reset_flow(client: AsyncClient, mailbox: MemorySender) -> None:
    user = await make_user()
    old_session = await login_client(user.email)
    r = await client.post("/api/v1/auth/password-reset/request", json={"email": user.email})
    assert r.status_code == 202
    neutral = r.json()["message"]
    r = await client.post(
        "/api/v1/auth/password-reset/request", json={"email": "ghost@example.test"}
    )
    assert r.status_code == 202 and r.json()["message"] == neutral

    async with get_sessionmaker()() as session:
        events = (await session.scalars(select(OutboxEvent))).all()
    assert len(events) == 1
    assert "token" not in str(events[0].payload.get("token_enc", ""))[:5]
    assert await send_password_reset_email(events[0].id) is True
    assert await send_password_reset_email(events[0].id) is False  # idempotent
    assert len(mailbox.outbox) == 1
    token = mailbox.outbox[0].text.split("token=")[1].split()[0]

    new_password = "a-brand-new-long-passphrase"
    r = await client.post(
        "/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": new_password}
    )
    assert r.status_code == 200
    r = await client.post(
        "/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": new_password}
    )
    assert r.status_code == 422  # single use
    assert (await old_session.get("/api/v1/auth/me")).status_code == 401
    await login_client(user.email, new_password)


async def test_agent_cannot_manage_users() -> None:
    _, agent = await actor(RoleGrant("TELEMARKETING_AGENT", "OWNED", (await make_edition()).id))
    r = await agent.get("/api/v1/users")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "PERMISSION_DENIED"


async def test_user_crud_and_role_assignment() -> None:
    _, admin = await actor(RoleGrant("SUPER_ADMIN"))
    r = await admin.post(
        "/api/v1/users",
        json={"email": "New.Agent@Example.test", "full_name": "New Agent", "password": PASSWORD},
    )
    assert r.status_code == 201, r.text
    user = r.json()
    assert user["email"] == "new.agent@example.test"
    r = await admin.post(
        "/api/v1/users",
        json={"email": "new.agent@example.test", "full_name": "Dup", "password": PASSWORD},
    )
    assert r.status_code == 409

    roles = {x["code"]: x for x in (await admin.get("/api/v1/roles")).json()}
    team = (await admin.post("/api/v1/teams", json={"name": "TM Jakarta"})).json()
    r = await admin.post(
        f"/api/v1/users/{user['id']}/role-assignments",
        json={"role_id": roles["TELEMARKETING_AGENT"]["id"], "scope_type": "TEAM"},
    )
    assert r.status_code == 422  # TEAM scope needs team_id
    r = await admin.post(
        f"/api/v1/users/{user['id']}/role-assignments",
        json={
            "role_id": roles["TELEMARKETING_AGENT"]["id"],
            "scope_type": "TEAM",
            "edition_id": str((await make_edition()).id),
            "team_id": team["id"],
        },
    )
    assert r.status_code == 201, r.text
    detail = (await admin.get(f"/api/v1/users/{user['id']}")).json()
    assert detail["role_assignments"][0]["role_code"] == "TELEMARKETING_AGENT"
    r = await admin.delete(f"/api/v1/users/{user['id']}/role-assignments/{r.json()['id']}")
    assert r.status_code == 204


async def test_edition_admin_cannot_grant_outside_their_edition() -> None:
    mine, other = (await make_edition()).id, (await make_edition()).id
    _, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", mine))
    target = await make_user()
    roles = {x["code"]: x["id"] for x in (await admin.get("/api/v1/roles")).json()}
    body = {"role_id": roles["TELEMARKETING_AGENT"], "scope_type": "OWNED"}
    url = f"/api/v1/users/{target.id}/role-assignments"
    assert (await admin.post(url, json={**body, "edition_id": str(mine)})).status_code == 201
    assert (await admin.post(url, json={**body, "edition_id": str(other)})).status_code == 404
    assert (await admin.post(url, json=body)).status_code == 403  # cross-edition


async def test_role_permission_matrix_editing() -> None:
    _, admin = await actor(RoleGrant("SUPER_ADMIN"))
    roles = {x["code"]: x for x in (await admin.get("/api/v1/roles")).json()}
    r = await admin.put(
        f"/api/v1/roles/{roles['SUPER_ADMIN']['id']}/permissions", json={"permissions": []}
    )
    assert r.status_code == 422
    r = await admin.put(
        f"/api/v1/roles/{roles['GATE_STAFF']['id']}/permissions",
        json={"permissions": ["gate.scan", "nope.nope"]},
    )
    assert r.status_code == 422
    r = await admin.post(
        "/api/v1/roles",
        json={"code": "QA_VIEWER", "name": "QA Viewer", "permissions": ["visitor.read"]},
    )
    assert r.status_code == 201
    assert r.json()["permissions"] == ["visitor.read"]


async def test_exhibition_admin_cannot_edit_roles() -> None:
    _, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", (await make_edition()).id))
    assert (await admin.get("/api/v1/roles")).status_code == 200
    r = await admin.post("/api/v1/roles", json={"code": "X_ROLE", "name": "X"})
    assert r.status_code == 403
