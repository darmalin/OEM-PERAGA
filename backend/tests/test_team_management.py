import uuid

from sqlalchemy import select

from app.core.audit import AuditLog
from app.core.db import get_sessionmaker
from app.modules.identity.models import User
from tests.factories import RoleGrant, actor, make_edition, make_user
from tests.test_registrations import make_lead


async def test_team_edit_multi_members_disable_enable_and_delete() -> None:
    _, admin = await actor(RoleGrant("SUPER_ADMIN"))
    edition = await make_edition()
    users = [
        await make_user(RoleGrant("TELEMARKETING_AGENT", "OWNED", edition.id)),
        await make_user(RoleGrant("TELEMARKETING_AGENT", "OWNED", edition.id)),
    ]
    created = await admin.post("/api/v1/teams", json={"name": "Flexible Team"})
    assert created.status_code == 201, created.text
    team = created.json()
    assert team["is_active"] and team["version"] == 1
    url = f"/api/v1/teams/{team['id']}"
    response = await admin.post(
        f"{url}/members/batch", json={"user_ids": [str(u.id) for u in users]}
    )
    assert response.status_code == 200, response.text
    team = response.json()
    assert set(team["member_ids"]) == {str(u.id) for u in users}
    assert team["version"] == 2
    response = await admin.patch(url, json={"version": team["version"], "name": "Renamed Team"})
    assert response.status_code == 200 and response.json()["name"] == "Renamed Team"
    team = response.json()
    assert (await admin.patch(url, json={"version": 1, "name": "Stale"})).status_code == 409
    disabled = await admin.patch(url, json={"version": team["version"], "is_active": False})
    assert disabled.status_code == 200 and disabled.json()["is_active"] is False
    team = disabled.json()
    assert len(team["member_ids"]) == 2
    assert (
        await admin.post(f"{url}/members/batch", json={"user_ids": [str(users[0].id)]})
    ).status_code == 422
    enabled = await admin.patch(url, json={"version": team["version"], "is_active": True})
    assert enabled.status_code == 200 and enabled.json()["is_active"] is True
    assert (await admin.delete(f"{url}/members/{users[0].id}")).status_code == 204
    team = (await admin.get(url)).json()
    assert team["member_ids"] == [str(users[1].id)]
    assert (await admin.delete(url, params={"version": team["version"]})).status_code == 204
    assert (await admin.get(url)).status_code == 404
    async with get_sessionmaker()() as session:
        assert all([await session.get(User, u.id) is not None for u in users])
        audits = (
            await session.scalars(
                select(AuditLog).where(AuditLog.entity_id == uuid.UUID(team["id"]))
            )
        ).all()
        assert {"create", "update", "member_added", "member_removed", "delete"} <= {
            a.action for a in audits
        }


async def test_team_names_and_bulk_membership_are_validated_atomically() -> None:
    _, admin = await actor(RoleGrant("SUPER_ADMIN"))
    assert (await admin.post("/api/v1/teams", json={"name": "   "})).status_code == 422
    team = (await admin.post("/api/v1/teams", json={"name": "First"})).json()
    other = (await admin.post("/api/v1/teams", json={"name": "Second"})).json()
    url = f"/api/v1/teams/{team['id']}"
    assert (await admin.patch(url, json={"version": 1, "name": other["name"]})).status_code == 409
    assert (await admin.patch(url, json={"version": 1, "name": " "})).status_code == 422
    edition = await make_edition()
    user = await make_user(RoleGrant("TELEMARKETING_AGENT", "OWNED", edition.id))
    response = await admin.post(
        f"{url}/members/batch", json={"user_ids": [str(user.id), str(uuid.uuid4())]}
    )
    assert response.status_code == 422
    assert (await admin.get(url)).json()["member_ids"] == []
    assert (await admin.post(f"{url}/members/batch", json={"user_ids": []})).status_code == 422
    body = {"user_ids": [str(user.id), str(user.id)]}
    assert (await admin.post(f"{url}/members/batch", json=body)).status_code == 200
    current = (await admin.get(url)).json()
    assert current["member_ids"] == [str(user.id)]
    assert (await admin.post(f"{url}/members/batch", json=body)).json()["version"] == current[
        "version"
    ]


async def test_disabled_team_stops_team_access_import_assignment_and_new_grants() -> None:
    _, root = await actor(RoleGrant("SUPER_ADMIN"))
    edition = await make_edition()
    team = (await root.post("/api/v1/teams", json={"name": "Import Team"})).json()
    team_id = uuid.UUID(team["id"])
    agent = await make_user(RoleGrant("TELEMARKETING_AGENT", "OWNED", edition.id))
    _, manager = await actor(RoleGrant("TELEMARKETING_MANAGER", "TEAM", edition.id, team_id))
    url = f"/api/v1/teams/{team_id}"
    team = (await root.post(f"{url}/members", json={"user_id": str(agent.id)})).json()
    lead = await make_lead(edition, owner=agent.id)
    assert (await manager.get(f"/api/v1/visitor-leads/{lead}")).status_code == 200
    assert (
        await root.put(f"/api/v1/editions/{edition.id}/team", json={"team_id": str(team_id)})
    ).status_code == 200
    recipients = f"/api/v1/visitor-leads/imports/recipients?edition_id={edition.id}"
    assert len((await root.get(recipients)).json()) == 1
    assert (await root.delete(url, params={"version": team["version"]})).status_code == 409
    team = (await root.patch(url, json={"version": team["version"], "is_active": False})).json()
    assert (await manager.get(f"/api/v1/visitor-leads/{lead}")).status_code == 403
    assert (await root.get(recipients)).json() == []
    assert (
        await root.put(f"/api/v1/editions/{edition.id}/team", json={"team_id": str(team_id)})
    ).status_code == 422
    target = await make_user()
    roles = (await root.get("/api/v1/roles")).json()
    role_id = next(r["id"] for r in roles if r["code"] == "TELEMARKETING_MANAGER")
    response = await root.post(
        f"/api/v1/users/{target.id}/role-assignments",
        json={
            "role_id": role_id,
            "scope_type": "TEAM",
            "edition_id": str(edition.id),
            "team_id": str(team_id),
        },
    )
    assert response.status_code == 422
    assert (
        await root.patch(url, json={"version": team["version"], "is_active": True})
    ).status_code == 200
    assert (await manager.get(f"/api/v1/visitor-leads/{lead}")).status_code == 200
    assert len((await root.get(recipients)).json()) == 1


async def test_team_changes_require_permission_and_respect_edition_boundaries() -> None:
    mine, other = await make_edition(), await make_edition()
    _, root = await actor(RoleGrant("SUPER_ADMIN"))
    _, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", mine.id))
    _, agent = await actor(RoleGrant("TELEMARKETING_AGENT", "OWNED", mine.id))
    user = await make_user(RoleGrant("TELEMARKETING_AGENT", "OWNED", other.id))
    team = (await root.post("/api/v1/teams", json={"name": "Other Edition Team"})).json()
    url = f"/api/v1/teams/{team['id']}"
    team = (await root.post(f"{url}/members", json={"user_id": str(user.id)})).json()
    for client in (admin, agent):
        assert (
            await client.patch(url, json={"version": team["version"], "name": "Changed"})
        ).status_code in (403, 404)
        assert (await client.delete(url, params={"version": team["version"]})).status_code in (
            403,
            404,
        )
    assert (
        await agent.post(f"{url}/members/batch", json={"user_ids": [str(user.id)]})
    ).status_code == 403


async def test_only_active_agent_level_users_can_join_teams() -> None:
    from tests.factories import login_client

    edition = await make_edition()
    _, root = await actor(RoleGrant("SUPER_ADMIN"))
    agent = await make_user(RoleGrant("TELEMARKETING_AGENT", "OWNED", edition.id))
    manager = await make_user(RoleGrant("TELEMARKETING_MANAGER", "EDITION", edition.id))
    mixed = await make_user(
        RoleGrant("TELEMARKETING_AGENT", "OWNED", edition.id),
        RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id),
    )
    inactive = await make_user(RoleGrant("TELEMARKETING_AGENT", "OWNED", edition.id), active=False)
    unassigned = await make_user()
    options = await root.get("/api/v1/teams/member-options")
    assert options.status_code == 200, options.text
    assert [user["id"] for user in options.json()["items"]] == [str(agent.id)]
    team = (await root.post("/api/v1/teams", json={"name": "Agents Only"})).json()
    url = f"/api/v1/teams/{team['id']}/members"
    for user in (manager, mixed, inactive, unassigned):
        assert (await root.post(url, json={"user_id": str(user.id)})).status_code == 422
        assert (
            await root.post(f"{url}/batch", json={"user_ids": [str(agent.id), str(user.id)]})
        ).status_code == 422
        assert (await root.get(f"/api/v1/teams/{team['id']}")).json()["member_ids"] == []
    assert (await root.post(url, json={"user_id": str(agent.id)})).status_code == 200
    client = await login_client(agent.email)
    assert (await client.get("/api/v1/teams/member-options")).status_code == 403


async def test_agent_member_choices_are_scoped_and_paginated() -> None:
    mine, other = await make_edition(), await make_edition()
    _, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", mine.id))
    agents = [await make_user(RoleGrant("TELEMARKETING_AGENT", "OWNED", mine.id)) for _ in range(3)]
    await make_user(RoleGrant("TELEMARKETING_AGENT", "OWNED", other.id))
    result = await admin.get("/api/v1/teams/member-options", params={"page": 2, "page_size": 2})
    assert result.status_code == 200
    assert result.json()["total"] == 3 and len(result.json()["items"]) == 1
    all_options = (await admin.get("/api/v1/teams/member-options")).json()["items"]
    assert {user["id"] for user in all_options} == {str(agent.id) for agent in agents}
