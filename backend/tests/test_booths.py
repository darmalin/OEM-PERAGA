"""Booths and booth assignment (phase 3 of docs/EXHIBITOR_LEADS_SALES_PIPELINE.md)."""

import asyncio
import uuid
from typing import Any

from httpx import AsyncClient

from app.core.storage import MemoryStorage
from app.modules.exhibitions.models import Edition
from tests.factories import RoleGrant, actor, make_edition
from tests.test_exhibitor_leads import SALES_ROLE, admin_for, create, move, sales_role

BOOTHS = "/api/v1/booths"
LEADS = "/api/v1/exhibitor-leads"


async def add_booth(client: AsyncClient, edition: Edition, code: str = "A01", **kw: Any) -> Any:
    body = {"edition_id": str(edition.id), "code": code, "area_sqm": "9", "price": "15000000"}
    r = await client.post(BOOTHS, json=body | kw)
    return r


async def opportunity(client: AsyncClient, edition: Edition, email: str) -> dict[str, Any]:
    lead = (await create(client, edition, email=email)).json()
    r = await move(client, lead, "OPPORTUNITY")
    assert r.status_code == 200, r.text
    return dict(r.json())


async def assign(client: AsyncClient, lead: dict[str, Any], booth_id: str | None) -> Any:
    return await client.put(
        f"{LEADS}/{lead['id']}/booth", json={"booth_id": booth_id, "version": lead["version"]}
    )


async def booths(client: AsyncClient, edition: Edition, **params: Any) -> list[dict[str, Any]]:
    r = await client.get(BOOTHS, params={"edition_id": str(edition.id), **params})
    assert r.status_code == 200, r.text
    return list(r.json()["items"])


async def test_create_and_edit_booth() -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    r = await add_booth(admin, edition, code=" A01 ", hall="Hall 1")
    assert r.status_code == 201, r.text
    booth = r.json()
    assert booth["code"] == "A01"
    assert booth["currency"] == "IDR"  # edition default
    assert booth["price"] == "15000000.00"
    assert booth["is_available"] is True

    r = await add_booth(admin, edition, code="A01")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "DUPLICATE_BOOTH_CODE"
    assert (await add_booth(admin, edition, code="A02", area_sqm="0")).status_code == 422
    assert (await add_booth(admin, edition, code="A03", currency="US")).status_code == 422

    r = await admin.patch(
        f"{BOOTHS}/{booth['id']}", json={"price": "17500000", "version": booth["version"]}
    )
    assert r.status_code == 200, r.text
    assert r.json()["price"] == "17500000.00"
    r = await admin.patch(f"{BOOTHS}/{booth['id']}", json={"code": "", "version": 99})
    assert r.status_code == 409  # stale version first


async def test_assign_move_and_release() -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    a01 = (await add_booth(admin, edition, "A01")).json()
    a02 = (await add_booth(admin, edition, "A02")).json()

    lead = (await create(admin, edition)).json()
    r = await assign(admin, lead, a01["id"])
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "BOOTH_NEEDS_OPPORTUNITY"

    lead = await opportunity(admin, edition, "sales-010@example.test")
    r = await assign(admin, lead, a01["id"])
    assert r.status_code == 200, r.text
    lead = r.json()
    assert lead["booth_code"] == "A01"
    assert lead["booth_assigned_at"] is not None

    taken = await booths(admin, edition, available="false")
    assert [(b["code"], b["exhibitor_lead_id"]) for b in taken] == [("A01", lead["id"])]

    other = await opportunity(admin, edition, "sales-011@example.test")
    r = await assign(admin, other, a01["id"])
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "BOOTH_TAKEN"

    lead = (await assign(admin, lead, a02["id"])).json()
    assert lead["booth_code"] == "A02"
    assert (await assign(admin, other, a01["id"])).status_code == 200  # A01 was freed

    lead = (await assign(admin, lead, None)).json()
    assert lead["booth_id"] is None
    assert [b["code"] for b in await booths(admin, edition, available="true")] == ["A02"]

    r = await admin.get(f"{LEADS}/{lead['id']}/activity")
    assert [e["action"] for e in r.json()].count("booth_change") == 3


async def test_leaving_opportunity_releases_the_booth() -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    booth = (await add_booth(admin, edition)).json()
    lead = await opportunity(admin, edition, "sales-020@example.test")
    lead = (await assign(admin, lead, booth["id"])).json()
    lead = (await move(admin, lead, "LOST", lost_reason="No budget")).json()
    assert lead["booth_id"] is None
    assert (await booths(admin, edition))[0]["is_available"] is True


async def test_booth_rules() -> None:
    edition, other_edition = await make_edition(), await make_edition()
    admin = await admin_for(edition)
    _, super_admin = await actor(RoleGrant("SUPER_ADMIN"))
    foreign = (await add_booth(super_admin, other_edition)).json()
    booth = (await add_booth(admin, edition)).json()
    inactive = (await add_booth(admin, edition, "B01", is_active=False)).json()
    lead = await opportunity(admin, edition, "sales-030@example.test")

    assert (await assign(admin, lead, foreign["id"])).status_code == 404
    assert (await assign(admin, lead, str(uuid.uuid4()))).status_code == 404
    r = await assign(admin, lead, inactive["id"])
    assert r.json()["error"]["code"] == "BOOTH_INACTIVE"
    assert [b["code"] for b in await booths(admin, edition)] == ["A01"]
    assert len(await booths(admin, edition, include_inactive="true")) == 2

    lead = (await assign(admin, lead, booth["id"])).json()
    r = await admin.patch(
        f"{BOOTHS}/{booth['id']}", json={"is_active": False, "version": booth["version"]}
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "BOOTH_IN_USE"


async def test_signed_contract_freezes_the_booth(storage: MemoryStorage) -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    a01 = (await add_booth(admin, edition, "A01")).json()
    a02 = (await add_booth(admin, edition, "A02")).json()
    lead = await opportunity(admin, edition, "sales-040@example.test")
    lead = (await assign(admin, lead, a01["id"])).json()

    r = await admin.post(f"{LEADS}/{lead['id']}/convert", json={"version": lead["version"]})
    assert r.status_code == 200, r.text
    url = f"{LEADS}/{lead['id']}/contract"
    version = (await admin.get(url)).json()["version"]
    fields = {"pic_name": "Test Contact", "company_address": "Jl. Example 1", "version": version}
    version = (await admin.patch(url, json=fields)).json()["version"]
    r = await admin.post(
        f"{url}/signed-copy",
        data={"version": str(version)},
        files={"file": ("signed.pdf", b"%PDF-1.7\n", "application/pdf")},
    )
    assert r.status_code == 200, r.text
    lead = (await admin.get(f"{LEADS}/{lead['id']}")).json()
    assert (await assign(admin, lead, None)).status_code == 422  # an exhibitor keeps a booth
    r = await assign(admin, lead, a02["id"])
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "CONTRACT_SIGNED"


async def test_two_sales_assign_one_booth_at_once() -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    booth = (await add_booth(admin, edition)).json()
    leads = [await opportunity(admin, edition, f"sales-05{n}@example.test") for n in (1, 2)]
    _, second = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))
    results = await asyncio.gather(
        assign(admin, leads[0], booth["id"]), assign(second, leads[1], booth["id"])
    )
    assert sorted(r.status_code for r in results) == [200, 409]


async def test_permissions_and_holder_visibility() -> None:
    edition = await make_edition()
    await sales_role()
    admin = await admin_for(edition)
    booth = (await add_booth(admin, edition)).json()
    held = await opportunity(admin, edition, "sales-060@example.test")
    await assign(admin, held, booth["id"])

    _, sales = await actor(RoleGrant(SALES_ROLE, "OWNED", edition.id))
    listed = await booths(sales, edition)
    assert listed[0]["is_available"] is False
    assert listed[0]["exhibitor_lead_id"] is None  # holder hidden from OWNED scope
    assert listed[0]["exhibitor_company_name"] is None
    assert (await add_booth(sales, edition, "Z01")).status_code == 403

    _, agent = await actor(RoleGrant("TELEMARKETING_AGENT", "EDITION", edition.id))
    r = await agent.get(BOOTHS, params={"edition_id": str(edition.id)})
    assert r.status_code == 403
