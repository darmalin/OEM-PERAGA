import asyncio
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.db import get_sessionmaker
from app.modules.exhibitions.models import Edition
from app.modules.visitors.models import VisitorLead
from tests.factories import RoleGrant, actor, make_edition, make_user


async def admin_for(edition: Edition) -> AsyncClient:
    _, client = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))
    return client


async def create(client: AsyncClient, edition: Edition, **fields: Any) -> Any:
    body = {"edition_id": str(edition.id), "first_name": "Tho", **fields}
    return await client.post("/api/v1/visitor-leads", json=body)


# spec 5.2 duplicate table, row for row. Existing lead: a@example.test / +6281234567890.
DUPLICATE_TABLE = [
    (
        "same email, different phone",
        "same",
        {"email": "a@example.test", "phone": "081299990000"},
        409,
    ),
    (
        "different email, same phone",
        "same",
        {"email": "b@example.test", "phone": "0812-3456-7890"},
        409,
    ),
    (
        "same email and phone",
        "same",
        {"email": "A@Example.test", "phone": "+62 812 3456 7890"},
        409,
    ),
    ("same email, other edition", "other", {"email": "a@example.test"}, 201),
    ("same phone, other edition", "other", {"phone": "081234567890"}, 201),
    ("email empty, phone unique", "same", {"email": "", "phone": "081277778888"}, 201),
    ("phone empty, email unique", "same", {"email": "c@example.test", "phone": " "}, 201),
    ("email and phone empty", "same", {"email": "", "phone": ""}, 422),
]


@pytest.mark.parametrize(("case", "where", "fields", "expected"), DUPLICATE_TABLE)
async def test_duplicate_rules(
    case: str, where: str, fields: dict[str, str], expected: int
) -> None:
    edition = await make_edition()
    other = await make_edition()
    _, client = await actor(RoleGrant("SUPER_ADMIN"))
    r = await create(client, edition, email="a@example.test", phone="081234567890", country="ID")
    assert r.status_code == 201, r.text
    target = edition if where == "same" else other
    r = await create(client, target, country="ID", **fields)
    assert r.status_code == expected, (case, r.text)
    if expected == 409:
        assert r.json()["error"]["code"] == "DUPLICATE_VISITOR"
        assert set(r.json()["error"]["fields"]) <= {"email", "phone"}


async def test_create_normalizes_and_generates_registration_code() -> None:
    edition = await make_edition(exhibition_code="IBTE", year=2027)
    client = await admin_for(edition)
    r = await create(
        client, edition, email="  Quoc@Example.TEST ", phone="0912 345 678", country="vn",
        company_name="  ", website="example.test", gender="MALE",
    )  # fmt: skip
    assert r.status_code == 201, r.text
    lead = r.json()
    assert lead["registration_code"] == "IBTE2027000001"
    assert lead["email"] == "Quoc@Example.TEST"
    assert lead["phone_normalized"] == "+84912345678"
    assert lead["country"] == "VN"
    assert lead["company_name"] is None  # empty stored as NULL
    assert lead["source"] == "MANUAL"
    assert lead["telemarketing_status"] == "NEW"
    assert lead["registration_status"] == "NOT_REGISTERED"
    assert lead["qr_status"] == "NONE"
    r2 = await create(client, edition, email="second@example.test")
    assert r2.json()["registration_code"] == "IBTE2027000002"


async def test_update_rechecks_duplicates_and_version() -> None:
    edition = await make_edition()
    client = await admin_for(edition)
    first = (await create(client, edition, email="one@example.test")).json()
    second = (await create(client, edition, email="two@example.test")).json()
    url = f"/api/v1/visitor-leads/{second['id']}"
    r = await client.patch(url, json={"version": 1, "email": "ONE@example.test"})
    assert r.status_code == 409
    assert r.json()["error"]["fields"] == {"email": "Already used in this edition."}
    assert first["registration_code"] in r.json()["error"]["message"]
    r = await client.patch(url, json={"version": 1, "company_name": "Khong"})
    assert r.status_code == 200 and r.json()["version"] == 2
    r = await client.patch(url, json={"version": 1, "company_name": "Stale"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "VERSION_CONFLICT"
    r = await client.patch(url, json={"version": 2, "email": None})
    assert r.status_code == 422  # would leave neither email nor phone
    r = await client.patch(url, json={"version": 2, "first_name": "  "})
    assert r.status_code == 422


async def test_update_writes_audit_with_before_after() -> None:
    edition = await make_edition()
    client = await admin_for(edition)
    lead = (await create(client, edition, email="audit@example.test")).json()
    await client.patch(
        f"/api/v1/visitor-leads/{lead['id']}", json={"version": 1, "city": "Ho Chi Minh City"}
    )
    timeline = (await client.get(f"/api/v1/visitor-leads/{lead['id']}/activity")).json()
    assert [t["action"] for t in timeline] == ["update", "create"]
    assert timeline[0]["before"] == {"city": None}
    assert timeline[0]["after"] == {"city": "Ho Chi Minh City"}
    assert timeline[0]["edition_id"] == str(edition.id)


async def test_parallel_creates_same_email_produce_one_row() -> None:
    edition = await make_edition()
    clients = [await admin_for(edition) for _ in range(6)]
    results = await asyncio.gather(
        *(create(c, edition, email="race@example.test") for c in clients)
    )
    codes = sorted(r.status_code for r in results)
    assert codes.count(201) == 1 and codes.count(409) == 5
    async with get_sessionmaker()() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(VisitorLead)
            .where(VisitorLead.edition_id == edition.id)
        )
    assert count == 1


async def test_parallel_creates_never_share_registration_code() -> None:
    edition = await make_edition()
    clients = [await admin_for(edition) for _ in range(10)]
    results = await asyncio.gather(
        *(create(c, edition, email=f"p{i}@example.test") for i, c in enumerate(clients))
    )
    codes = [r.json()["registration_code"] for r in results]
    assert all(r.status_code == 201 for r in results)
    assert len(set(codes)) == 10


async def test_scope_owned_team_and_other_edition() -> None:
    edition, other = await make_edition(), await make_edition()
    _, admin = await actor(RoleGrant("SUPER_ADMIN"))
    _, team_admin = await actor(RoleGrant("SUPER_ADMIN"))
    r = await team_admin.post("/api/v1/teams", json={"name": "TM Hanoi"})
    team_id = uuid.UUID(r.json()["id"])

    agent = await make_user(RoleGrant("TELEMARKETING_AGENT", "OWNED", edition.id), teams=(team_id,))
    teammate = await make_user(
        RoleGrant("TELEMARKETING_AGENT", "OWNED", edition.id), teams=(team_id,)
    )
    lead_mine = (await create(admin, edition, email="mine@example.test")).json()
    lead_mate = (await create(admin, edition, email="mate@example.test")).json()
    lead_none = (await create(admin, edition, email="none@example.test")).json()
    lead_other = (await create(admin, other, email="other@example.test")).json()
    async with get_sessionmaker()() as session, session.begin():
        for lead_id, owner in ((lead_mine["id"], agent.id), (lead_mate["id"], teammate.id)):
            row = await session.get(VisitorLead, uuid.UUID(lead_id))
            assert row is not None
            row.lead_owner_id = owner

    from tests.factories import login_client

    agent_client = await login_client(agent.email)
    listed = (
        await agent_client.get("/api/v1/visitor-leads", params={"edition_id": str(edition.id)})
    ).json()
    assert [i["id"] for i in listed["items"]] == [lead_mine["id"]]
    assert (await agent_client.get(f"/api/v1/visitor-leads/{lead_mate['id']}")).status_code == 404
    assert (await agent_client.get(f"/api/v1/visitor-leads/{lead_none['id']}")).status_code == 404
    assert (await agent_client.get(f"/api/v1/visitor-leads/{lead_other['id']}")).status_code == 404
    r = await agent_client.get("/api/v1/visitor-leads", params={"edition_id": str(other.id)})
    assert r.status_code == 404
    r = await agent_client.patch(
        f"/api/v1/visitor-leads/{lead_mine['id']}", json={"version": 2, "city": "Hanoi"}
    )
    assert r.status_code == 200, r.text

    leader = await make_user(RoleGrant("TELEMARKETING_MANAGER", "TEAM", edition.id, team_id))
    leader_client = await login_client(leader.email)
    listed = (
        await leader_client.get("/api/v1/visitor-leads", params={"edition_id": str(edition.id)})
    ).json()
    assert {i["id"] for i in listed["items"]} == {lead_mine["id"], lead_mate["id"]}


async def test_agent_cannot_create_leads() -> None:
    edition = await make_edition()
    _, agent = await actor(RoleGrant("TELEMARKETING_AGENT", "OWNED", edition.id))
    assert (await create(agent, edition, email="x@example.test")).status_code == 403


async def test_list_filters_search_sort_and_unknown_params() -> None:
    edition = await make_edition()
    client = await admin_for(edition)
    await create(
        client, edition, first_name="Alpha", email="alpha@example.test", company_name="Acme"
    )
    await create(client, edition, first_name="Beta", phone="081234500001", country="ID")
    base = {"edition_id": str(edition.id)}
    r = await client.get("/api/v1/visitor-leads", params={**base, "q": "acme"})
    assert [i["first_name"] for i in r.json()["items"]] == ["Alpha"]
    r = await client.get("/api/v1/visitor-leads", params={**base, "q": "34500001"})
    assert [i["first_name"] for i in r.json()["items"]] == ["Beta"]
    r = await client.get("/api/v1/visitor-leads", params={**base, "sort": "first_name"})
    assert [i["first_name"] for i in r.json()["items"]] == ["Alpha", "Beta"]
    r = await client.get(
        "/api/v1/visitor-leads",
        params={**base, "telemarketing_status": ["NEW", "ANSWER"], "page_size": 1},
    )
    assert r.json()["total"] == 2 and len(r.json()["items"]) == 1
    r = await client.get("/api/v1/visitor-leads", params={**base, "unassigned": "true"})
    assert r.json()["total"] == 2
    r = await client.get("/api/v1/visitor-leads", params={**base, "status": "NEW"})
    assert r.status_code == 422  # no generic status filter, unknown params rejected
    r = await client.get("/api/v1/visitor-leads", params={**base, "sort": "password"})
    assert r.status_code == 422
    r = await client.get("/api/v1/visitor-leads", params={**base, "page_size": 501})
    assert r.status_code == 422


async def test_configurable_options_and_custom_fields() -> None:
    edition = await make_edition()
    client = await admin_for(edition)
    for field, value in (("BRANCH", "VIETNAM"), ("PRODUCT_CATEGORY", "personal_care")):
        r = await client.post(
            "/api/v1/edition-field-options",
            json={
                "edition_id": str(edition.id),
                "field": field,
                "value": value,
                "label": value.title(),
            },
        )
        assert r.status_code == 201, r.text
    r = await client.post(
        "/api/v1/visitor-custom-fields",
        json={"edition_id": str(edition.id), "field_key": "hall", "label": "Hall",
              "field_type": "select", "options": ["A", "B"], "required": True},
    )  # fmt: skip
    assert r.status_code == 201, r.text
    hall_id = r.json()["id"]
    r = await client.post(
        "/api/v1/visitor-custom-fields",
        json={
            "edition_id": str(edition.id),
            "field_key": "hall",
            "label": "Dup",
            "field_type": "text",
        },
    )
    assert r.status_code == 409

    r = await create(client, edition, email="x@example.test", branch="VIETNAM")
    assert r.status_code == 422 and r.json()["error"]["fields"] == {
        "custom_fields.hall": "Required."
    }
    r = await create(
        client, edition, email="x@example.test", branch="NOWHERE",
        product_categories=["personal_care", "bogus"], custom_fields={"hall": "C", "x": 1},
    )  # fmt: skip
    assert r.status_code == 422
    assert set(r.json()["error"]["fields"]) == {
        "branch", "product_categories", "custom_fields.hall", "custom_fields.x",
    }  # fmt: skip
    r = await create(
        client, edition, email="x@example.test", branch="VIETNAM",
        product_categories=["personal_care"], custom_fields={"hall": "A"},
    )  # fmt: skip
    assert r.status_code == 201, r.text
    lead = r.json()
    assert lead["custom_fields"] == {"hall": "A"}

    # Deactivating a definition keeps old values but they no longer count as required.
    await client.patch(
        f"/api/v1/visitor-custom-fields/{hall_id}", json={"version": 1, "is_active": False}
    )
    r = await client.patch(
        f"/api/v1/visitor-leads/{lead['id']}", json={"version": 1, "comment": "kept"}
    )
    assert r.status_code == 200 and r.json()["custom_fields"] == {"hall": "A"}


async def test_archived_edition_is_read_only() -> None:
    edition = await make_edition()
    client = await admin_for(edition)
    lead = (await create(client, edition, email="arch@example.test")).json()
    async with get_sessionmaker()() as session, session.begin():
        row = await session.get(Edition, edition.id)
        assert row is not None
        row.status = "ARCHIVED"
    r = await create(client, edition, email="new@example.test")
    assert r.status_code == 422 and r.json()["error"]["code"] == "EDITION_ARCHIVED"
    r = await client.patch(f"/api/v1/visitor-leads/{lead['id']}", json={"version": 1, "city": "X"})
    assert r.status_code == 422
    assert (await client.get(f"/api/v1/visitor-leads/{lead['id']}")).status_code == 200


async def test_db_rejects_valid_and_invalid_together() -> None:
    edition = await make_edition()
    client = await admin_for(edition)
    lead = (await create(client, edition, email="ck@example.test")).json()
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        async with get_sessionmaker()() as session, session.begin():
            row = await session.get(VisitorLead, uuid.UUID(lead["id"]))
            assert row is not None
            row.is_valid_lead = True
            row.is_invalid = True
