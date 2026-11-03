"""Exhibitor lead API (phase 2 of docs/EXHIBITOR_LEADS_SALES_PIPELINE.md)."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.modules.exhibitions.models import Edition
from app.modules.identity.models import Permission, Role, RolePermission
from tests.factories import RoleGrant, actor, make_edition

URL = "/api/v1/exhibitor-leads"
SALES_ROLE = "EXHIBITOR_SALES_TEST"


async def admin_for(edition: Edition) -> AsyncClient:
    _, client = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))
    return client


async def sales_role() -> None:
    """Custom role a sales person gets: exhibitor lead permissions only."""
    async with get_sessionmaker()() as session, session.begin():
        role = Role(code=SALES_ROLE, name="Exhibitor Sales")
        session.add(role)
        await session.flush()
        perms = await session.scalars(
            select(Permission.id).where(Permission.code.like("exhibitor_lead.%"))
        )
        session.add_all(RolePermission(role_id=role.id, permission_id=p) for p in perms)


async def create(client: AsyncClient, edition: Edition, **fields: Any) -> Any:
    body = {
        "edition_id": str(edition.id),
        "company_name": "Example Corp",
        "contact_name": "Test Contact",
        "email": "sales-001@example.test",
        **fields,
    }
    return await client.post(URL, json=body)


async def move(client: AsyncClient, lead: dict[str, Any], stage: str, **kw: Any) -> Any:
    return await client.post(
        f"{URL}/{lead['id']}/stage", json={"stage": stage, "version": lead["version"], **kw}
    )


async def test_create_normalizes_and_starts_as_lead() -> None:
    edition = await make_edition()
    client = await admin_for(edition)
    r = await create(
        client, edition, email=" Buyer@Example.TEST ", phone="0812-3456-7890",
        notes="  ", budget_estimate="25000000",
    )  # fmt: skip
    assert r.status_code == 201, r.text
    lead = r.json()
    assert lead["email"] == "Buyer@Example.TEST"
    assert lead["phone"] == "0812-3456-7890"
    assert lead["notes"] is None  # empty stored as NULL
    assert lead["stage"] == "LEAD"
    assert lead["budget_estimate"] == "25000000.00"
    assert lead["lead_owner_id"] is None


@pytest.mark.parametrize(
    ("fields", "field"),
    [
        ({"email": "not-an-email"}, "email"),
        ({"company_name": "   "}, "company_name"),
        ({"budget_estimate": "-1"}, None),
    ],
)
async def test_create_validation(fields: dict[str, str], field: str | None) -> None:
    edition = await make_edition()
    r = await create(await admin_for(edition), edition, **fields)
    assert r.status_code == 422, r.text
    if field:
        assert field in r.json()["error"]["fields"]


async def test_email_unique_per_edition() -> None:
    edition, other = await make_edition(), await make_edition()
    _, client = await actor(RoleGrant("SUPER_ADMIN"))
    assert (await create(client, edition)).status_code == 201
    r = await create(client, edition, email="SALES-001@example.test")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "DUPLICATE_EXHIBITOR_LEAD"
    assert (await create(client, other)).status_code == 201

    second = (await create(client, edition, email="sales-002@example.test")).json()
    r = await client.patch(
        f"{URL}/{second['id']}",
        json={"email": "sales-001@example.test", "version": second["version"]},
    )
    assert r.status_code == 409


async def test_stage_flow() -> None:
    edition = await make_edition()
    client = await admin_for(edition)
    lead = (await create(client, edition)).json()

    r = await move(client, lead, "OPPORTUNITY")
    assert r.status_code == 200, r.text
    lead = r.json()
    assert lead["stage"] == "OPPORTUNITY"
    assert lead["qualified_at"] is not None

    r = await move(client, lead, "LOST")
    assert r.status_code == 422
    assert "lost_reason" in r.json()["error"]["fields"]
    lead = (await move(client, lead, "LOST", lost_reason="Budget moved to next year")).json()
    assert lead["stage"] == "LOST"
    assert lead["lost_reason"] == "Budget moved to next year"

    r = await move(client, lead, "OPPORTUNITY")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INVALID_STAGE_TRANSITION"

    lead = (await move(client, lead, "LEAD")).json()
    assert lead["stage"] == "LEAD"
    assert lead["lost_reason"] is None

    # EXHIBITOR comes from the convert step (phase 4).
    assert (await move(client, lead, "EXHIBITOR")).status_code == 422

    r = await client.get(f"{URL}/{lead['id']}/activity")
    assert r.status_code == 200
    actions = [e["action"] for e in r.json()]
    assert actions.count("stage_change") == 3
    assert "create" in actions


async def test_stale_version_is_a_conflict() -> None:
    edition = await make_edition()
    client = await admin_for(edition)
    lead = (await create(client, edition)).json()
    r = await client.patch(f"{URL}/{lead['id']}", json={"notes": "a", "version": lead["version"]})
    assert r.status_code == 200
    r = await client.patch(f"{URL}/{lead['id']}", json={"notes": "b", "version": lead["version"]})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "VERSION_CONFLICT"


async def test_list_filters_and_paginates() -> None:
    edition = await make_edition()
    client = await admin_for(edition)
    for n in range(3):
        await create(client, edition, email=f"sales-{n:03d}@example.test", company_name=f"Co {n}")
    first = (await client.get(URL, params={"edition_id": str(edition.id)})).json()["items"][-1]
    await move(client, first, "OPPORTUNITY")

    r = await client.get(
        URL, params={"edition_id": str(edition.id), "stage": "OPPORTUNITY", "page_size": 1}
    )
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["stage"] == "OPPORTUNITY"

    r = await client.get(URL, params={"edition_id": str(edition.id), "q": "co 2"})
    assert [i["company_name"] for i in r.json()["items"]] == ["Co 2"]


async def test_owned_scope_sales_sees_only_own_leads() -> None:
    edition = await make_edition()
    await sales_role()
    admin = await admin_for(edition)
    sales, client = await actor(RoleGrant(SALES_ROLE, "OWNED", edition.id))
    other = (await create(admin, edition, email="other@example.test")).json()

    r = await create(client, edition)
    assert r.status_code == 201, r.text
    mine = r.json()
    assert mine["lead_owner_id"] == str(sales.id)

    items = (await client.get(URL, params={"edition_id": str(edition.id)})).json()["items"]
    assert [i["id"] for i in items] == [mine["id"]]
    assert (await client.get(f"{URL}/{other['id']}")).status_code == 404
    assert (await move(client, other, "OPPORTUNITY")).status_code == 404

    r = await client.patch(
        f"{URL}/{mine['id']}", json={"lead_owner_id": None, "version": mine["version"]}
    )
    assert r.status_code == 403
    r = await create(client, edition, email="x@example.test", lead_owner_id=other["id"])
    assert r.status_code == 403


async def test_permissions() -> None:
    edition, other = await make_edition(), await make_edition()
    admin = await admin_for(edition)
    lead = (await create(admin, edition)).json()

    _, agent = await actor(RoleGrant("TELEMARKETING_AGENT", "EDITION", edition.id))
    assert (await agent.get(URL, params={"edition_id": str(edition.id)})).status_code == 403
    assert (await create(agent, edition)).status_code == 403

    # An admin of another edition does not learn the lead exists.
    other_admin = await admin_for(other)
    assert (await other_admin.get(f"{URL}/{lead['id']}")).status_code == 404
    r = await other_admin.get(URL, params={"edition_id": str(edition.id)})
    assert r.status_code == 404
