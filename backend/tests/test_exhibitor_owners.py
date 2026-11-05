"""Lead Owner of exhibitor leads: who can own them, who may assign (FRONTEND_RULES W16)."""

from typing import Any

from httpx import AsyncClient

from app.core.db import get_sessionmaker
from app.modules.identity.models import User
from tests.factories import RoleGrant, actor, make_edition
from tests.test_exhibitor_leads import SALES_ROLE, URL, admin_for, create, sales_role


async def owners(client: AsyncClient, edition_id: object) -> Any:
    return await client.get(f"{URL}/owners", params={"edition_id": str(edition_id)})


async def test_owner_list_and_assign() -> None:
    edition, other = await make_edition(), await make_edition()
    await sales_role()
    admin_user, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))
    sales, sales_client = await actor(RoleGrant(SALES_ROLE, "EDITION", edition.id))
    elsewhere, _ = await actor(RoleGrant(SALES_ROLE, "EDITION", other.id))
    agent, _ = await actor(RoleGrant("TELEMARKETING_AGENT", "EDITION", edition.id))

    r = await owners(admin, edition.id)
    assert r.status_code == 200, r.text
    ids = {o["id"] for o in r.json()["owners"]}
    assert {str(admin_user.id), str(sales.id)} <= ids
    assert str(elsewhere.id) not in ids and str(agent.id) not in ids  # other edition, no permission
    assert r.json()["can_assign"] is True

    lead = (await create(admin, edition)).json()
    r = await admin.patch(
        f"{URL}/{lead['id']}", json={"lead_owner_id": str(sales.id), "version": lead["version"]}
    )
    assert r.status_code == 200, r.text
    lead = r.json()
    assert (lead["lead_owner_id"], lead["lead_owner_name"]) == (str(sales.id), sales.full_name)
    listed = (
        await admin.get(URL, params={"edition_id": str(edition.id), "lead_owner_id": str(sales.id)})
    ).json()
    assert [i["id"] for i in listed["items"]] == [lead["id"]]

    for bad in (elsewhere.id, agent.id):
        r = await admin.patch(
            f"{URL}/{lead['id']}", json={"lead_owner_id": str(bad), "version": lead["version"]}
        )
        assert r.status_code == 422
        assert "lead_owner_id" in r.json()["error"]["fields"]
    r = await create(admin, edition, email="sales-300@example.test", lead_owner_id=str(agent.id))
    assert r.status_code == 422

    r = await admin.patch(
        f"{URL}/{lead['id']}", json={"lead_owner_id": None, "version": lead["version"]}
    )
    assert r.json()["lead_owner_id"] is None  # unassign

    # Same edition-wide sales role may assign as well; it is the scope that matters.
    assert (await owners(sales_client, edition.id)).json()["can_assign"] is True


async def test_scoped_users_cannot_assign() -> None:
    edition = await make_edition()
    await sales_role()
    admin = await admin_for(edition)
    sales, owned = await actor(RoleGrant(SALES_ROLE, "OWNED", edition.id))
    r = await owners(owned, edition.id)
    assert r.status_code == 200
    assert r.json()["can_assign"] is False
    mine = (await create(owned, edition)).json()
    assert mine["lead_owner_id"] == str(sales.id)

    # A disabled user drops out of the list and cannot be given leads.
    async with get_sessionmaker()() as session, session.begin():
        user = await session.get(User, sales.id)
        assert user is not None
        user.is_active = False
    assert str(sales.id) not in {
        o["id"] for o in (await owners(admin, edition.id)).json()["owners"]
    }
    lead = (await create(admin, edition, email="sales-301@example.test")).json()
    r = await admin.patch(
        f"{URL}/{lead['id']}", json={"lead_owner_id": str(sales.id), "version": lead["version"]}
    )
    assert r.status_code == 422

    _, agent = await actor(RoleGrant("TELEMARKETING_AGENT", "EDITION", edition.id))
    assert (await owners(agent, edition.id)).status_code == 403
