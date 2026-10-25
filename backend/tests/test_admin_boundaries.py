"""What an Exhibition Admin may do to users and roles: never more than their own access."""

from typing import Any

from httpx import AsyncClient

from tests.factories import RoleGrant, actor, make_edition, make_user


async def role_ids(client: AsyncClient) -> dict[str, str]:
    r = await client.get("/api/v1/roles")
    assert r.status_code == 200, r.text
    return {x["code"]: x["id"] for x in r.json()}


async def grant(client: AsyncClient, user_id: Any, role_id: str, edition_id: Any) -> Any:
    return await client.post(
        f"/api/v1/users/{user_id}/role-assignments",
        json={"role_id": role_id, "scope_type": "EDITION", "edition_id": str(edition_id)},
    )


async def test_no_one_grants_or_revokes_a_role_above_their_own() -> None:
    edition = await make_edition()
    me, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))
    roles = await role_ids(admin)
    newcomer = await make_user()

    # The hole: an edition admin made themselves Super Admin of their edition.
    r = await grant(admin, me.id, roles["SUPER_ADMIN"], edition.id)
    assert r.status_code == 403 and r.json()["error"]["code"] == "ROLE_ABOVE_YOURS"
    r = await grant(admin, newcomer.id, roles["SUPER_ADMIN"], edition.id)
    assert r.status_code == 403
    # Roles within their own access are fine, their own role included.
    assert (
        await grant(admin, newcomer.id, roles["TELEMARKETING_AGENT"], edition.id)
    ).status_code == 201
    assert (
        await grant(admin, newcomer.id, roles["EXHIBITION_ADMIN"], edition.id)
    ).status_code == 201

    # Nor can they take a higher role away from someone.
    boss = await make_user(RoleGrant("SUPER_ADMIN", "EDITION", edition.id))
    detail = (await admin.get(f"/api/v1/users/{boss.id}")).json()
    (assignment,) = detail["role_assignments"]
    r = await admin.delete(f"/api/v1/users/{boss.id}/role-assignments/{assignment['id']}")
    assert r.status_code == 403


async def test_roles_change_only_with_global_role_manage() -> None:
    edition = await make_edition()
    # Super Admin scoped to one edition holds role.manage there, but roles are global.
    _, scoped = await actor(RoleGrant("SUPER_ADMIN", "EDITION", edition.id))
    _, platform = await actor(RoleGrant("SUPER_ADMIN"))
    roles = await role_ids(platform)
    agent_role = roles["TELEMARKETING_AGENT"]
    perms = ["edition.read", "visitor.read"]

    r = await scoped.put(f"/api/v1/roles/{agent_role}/permissions", json={"permissions": perms})
    assert r.status_code == 403
    r = await scoped.post("/api/v1/roles", json={"code": "SNEAKY", "name": "Sneaky"})
    assert r.status_code == 403
    r = await platform.post("/api/v1/roles", json={"code": "AUDITOR_X", "name": "Auditor X"})
    assert r.status_code == 201, r.text


async def test_edition_admins_see_and_edit_only_users_inside_their_editions() -> None:
    mine = await make_edition()
    other = await make_edition()
    _, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", mine.id))
    platform_admin = await make_user(RoleGrant("SUPER_ADMIN"))
    inside = await make_user(RoleGrant("TELEMARKETING_AGENT", "OWNED", mine.id))
    both = await make_user(
        RoleGrant("TELEMARKETING_AGENT", "OWNED", mine.id),
        RoleGrant("TELEMARKETING_AGENT", "OWNED", other.id),
    )
    elsewhere = await make_user(RoleGrant("TELEMARKETING_AGENT", "OWNED", other.id))
    unassigned = await make_user()

    r = await admin.get("/api/v1/users", params={"page_size": 500})
    listed = {u["id"] for u in r.json()["items"]}
    assert {str(inside.id), str(both.id), str(unassigned.id)} <= listed
    assert str(platform_admin.id) not in listed and str(elsewhere.id) not in listed

    # Hidden users are not found; shared users are visible but not editable.
    assert (await admin.get(f"/api/v1/users/{platform_admin.id}")).status_code == 404
    assert (await admin.get(f"/api/v1/users/{elsewhere.id}")).status_code == 404

    async def deactivate(user: Any) -> int:
        detail = (await admin.get(f"/api/v1/users/{user.id}")).json()
        r = await admin.patch(
            f"/api/v1/users/{user.id}",
            json={"is_active": False, "version": detail.get("version", 1)},
        )
        return r.status_code

    assert await deactivate(both) == 403
    assert await deactivate(inside) == 200
    assert await deactivate(unassigned) == 200
    r = await admin.patch(
        f"/api/v1/users/{platform_admin.id}", json={"is_active": False, "version": 1}
    )
    assert r.status_code == 404

    # A shared user's detail shows only the assignments inside the admin's editions.
    detail = (await admin.get(f"/api/v1/users/{both.id}")).json()
    assert {a["edition_id"] for a in detail["role_assignments"]} == {str(mine.id)}

    # A global Super Admin still manages everyone.
    _, platform = await actor(RoleGrant("SUPER_ADMIN"))
    assert (await platform.get(f"/api/v1/users/{elsewhere.id}")).status_code == 200
