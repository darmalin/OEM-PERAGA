import asyncio
import json
import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.modules.exhibitions.models import Edition
from app.modules.visitors.models import VisitorLead
from app.modules.visitors.schemas import LeadFilters
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
    # Registered on creation (owner decision 2026-10-22).
    assert lead["registration_status"] == "REGISTERED"
    assert lead["qr_status"] == "ACTIVE"
    r2 = await create(client, edition, email="second@example.test")
    assert r2.json()["registration_code"] == "IBTE2027000002"


async def test_update_rechecks_duplicates_and_version() -> None:
    edition = await make_edition()
    client = await admin_for(edition)
    first = (await create(client, edition, email="one@example.test")).json()
    second = (await create(client, edition, email="two@example.test")).json()
    url = f"/api/v1/visitor-leads/{second['id']}"
    v = second["version"]
    r = await client.patch(url, json={"version": v, "email": "ONE@example.test"})
    assert r.status_code == 409
    assert r.json()["error"]["fields"] == {"email": "Already used in this edition."}
    assert first["registration_code"] in r.json()["error"]["message"]
    r = await client.patch(url, json={"version": v, "company_name": "Khong"})
    assert r.status_code == 200 and r.json()["version"] == v + 1
    r = await client.patch(url, json={"version": v, "company_name": "Stale"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "VERSION_CONFLICT"
    r = await client.patch(url, json={"version": v + 1, "email": None})
    assert r.status_code == 422  # would leave neither email nor phone
    r = await client.patch(url, json={"version": v + 1, "first_name": "  "})
    assert r.status_code == 422


async def test_update_writes_audit_with_before_after() -> None:
    edition = await make_edition()
    client = await admin_for(edition)
    lead = (await create(client, edition, email="audit@example.test")).json()
    await client.patch(
        f"/api/v1/visitor-leads/{lead['id']}",
        json={"version": lead["version"], "city": "Ho Chi Minh City"},
    )
    timeline = (await client.get(f"/api/v1/visitor-leads/{lead['id']}/activity")).json()
    assert [t["action"] for t in timeline] == ["update", "register", "create"]
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
        f"/api/v1/visitor-leads/{lead_mine['id']}",
        json={"version": lead_mine["version"] + 1, "city": "Hanoi"},
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


async def test_list_conditions_from_the_filter_button() -> None:
    edition = await make_edition()
    client = await admin_for(edition)
    await create(
        client, edition, first_name="Alpha", email="alpha@example.test", company_name="Acme",
        city="Hanoi", job_title="Buyer Manager", phone="0812-3456-0001", country="ID",
    )  # fmt: skip
    await create(client, edition, first_name="Beta", email="beta@example.test",
                 company_name="Beta 100% Co")  # fmt: skip
    await create(client, edition, first_name="Gamma", email="gamma@example.test")

    async def names(*conds: tuple[str, str, Any]) -> list[str]:
        filters = json.dumps([{"field": f, "op": o, "value": v} for f, o, v in conds])
        r = await client.get(
            "/api/v1/visitor-leads",
            params={"edition_id": str(edition.id), "filters": filters, "sort": "first_name"},
        )
        assert r.status_code == 200, r.text
        return [i["first_name"] for i in r.json()["items"]]

    assert await names(("city", "contains", "HAN")) == ["Alpha"]
    assert await names(("company_name", "contains", "100%")) == ["Beta"]
    assert await names(("company_name", "contains", "%")) == ["Beta"]  # % is literal
    assert await names(("first_name", "starts_with", "gam")) == ["Gamma"]
    assert await names(("email", "equals", "BETA@example.test")) == ["Beta"]
    assert await names(("phone", "contains", "3456-0001")) == ["Alpha"]
    assert await names(("city", "not_set", None)) == ["Beta", "Gamma"]
    assert await names(("city", "is_set", None), ("job_title", "contains", "buyer")) == ["Alpha"]
    assert await names(("city", "is_set", None), ("job_title", "contains", "seller")) == []
    assert await names(("country", "is", "id")) == ["Alpha"]
    assert await names(("country", "is_not", "ID")) == ["Beta", "Gamma"]
    assert len(await names(("telemarketing_status", "is", "NEW"))) == 3
    assert await names(("telemarketing_status", "is_not", "NEW")) == []
    assert await names(("is_valid_lead", "is", True)) == []
    assert await names(("call_attempts", "gt", 0)) == []
    assert len(await names(("call_attempts", "equals", 0))) == 3
    today = datetime.now(ZoneInfo(get_settings().report_timezone)).date()
    span = [today.isoformat(), today.isoformat()]
    assert len(await names(("lead_date", "between", span))) == 3
    assert await names(("lead_date", "before", today.isoformat())) == []
    assert await names(("created_at", "after", today.isoformat())) == []
    assert await names(("last_call_at", "not_set", None), ("first_name", "contains", "a")) == [
        "Alpha", "Beta", "Gamma",
    ]  # fmt: skip

    bad = [
        [{"field": "password_hash", "op": "contains", "value": "x"}],  # not a filter field
        [{"field": "telemarketing_status", "op": "contains", "value": "N"}],  # wrong operator
        [{"field": "first_name", "op": "is_set"}],  # never empty
        [{"field": "is_valid_lead", "op": "is", "value": "yes"}],
        [{"field": "country", "op": "is", "value": "Indonesia"}],
        [{"field": "attend", "op": "is", "value": "MAYBE"}],
        [{"field": "phone", "op": "contains", "value": "12"}],
        [{"field": "lead_date", "op": "between", "value": ["2026-10-02", "2026-10-01"]}],
        [{"field": "city", "op": "contains", "value": "x", "sql": "1=1"}],
        [{"field": "city", "op": "is_set"}] * 21,
    ]
    for filters in bad:
        r = await client.get(
            "/api/v1/visitor-leads",
            params={"edition_id": str(edition.id), "filters": json.dumps(filters)},
        )
        assert r.status_code == 422, filters
    r = await client.get("/api/v1/visitor-leads", params={"filters": "not json"})
    assert r.status_code == 422

    # Stored export/assign params come back as JSON and validate again unchanged.
    f = LeadFilters.model_validate(
        {"filters": [{"field": "lead_date", "op": "between", "value": span},
                     {"field": "phone", "op": "contains", "value": "+62 812"}]}
    )  # fmt: skip
    assert LeadFilters.model_validate(f.model_dump(mode="json")) == f


async def test_filter_options_come_from_visible_leads() -> None:
    edition = await make_edition()
    other = await make_edition()
    client = await admin_for(edition)
    _, super_admin = await actor(RoleGrant("SUPER_ADMIN"))
    await create(client, edition, email="vn@example.test", country="VN")
    await create(client, edition, email="id@example.test", country="ID")
    await create(super_admin, other, email="th@example.test", country="TH")
    r = await client.get("/api/v1/visitor-leads/filter-options")
    assert r.status_code == 200, r.text
    assert r.json() == {"countries": ["ID", "VN"], "owners": [], "teams": []}
    r = await client.get(
        "/api/v1/visitor-leads/filter-options", params={"edition_id": str(other.id)}
    )
    assert r.status_code == 404


async def test_configurable_options_and_custom_fields() -> None:
    edition = await make_edition()
    client = await admin_for(edition)
    for field, value in (("BRANCH", "VIETNAM"),):
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
        custom_fields={"hall": "C", "x": 1},
    )  # fmt: skip
    assert r.status_code == 422
    assert set(r.json()["error"]["fields"]) == {
        "branch", "custom_fields.hall", "custom_fields.x",
    }  # fmt: skip
    # Product Categories Interested In is free text (owner decision 2026-10-22).
    r = await create(
        client, edition, email="x@example.test", branch="VIETNAM",
        product_categories="  Garment machinery, dyeing  ", custom_fields={"hall": "A"},
    )  # fmt: skip
    assert r.status_code == 201, r.text
    lead = r.json()
    assert lead["custom_fields"] == {"hall": "A"}
    assert lead["product_categories"] == "Garment machinery, dyeing"
    r = await create(client, edition, email="y@example.test", custom_fields={"hall": "A"},
                     product_categories=["a list"])  # fmt: skip
    assert r.status_code == 422

    # Deactivating a definition keeps old values but they no longer count as required.
    await client.patch(
        f"/api/v1/visitor-custom-fields/{hall_id}", json={"version": 1, "is_active": False}
    )
    r = await client.patch(
        f"/api/v1/visitor-leads/{lead['id']}", json={"version": lead["version"], "comment": "kept"}
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
    r = await client.patch(
        f"/api/v1/visitor-leads/{lead['id']}", json={"version": lead["version"], "city": "X"}
    )
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


async def test_new_lead_is_registered_without_email() -> None:
    """Owner decision 2026-10-22: every lead that comes in can enter the gate."""
    edition = await make_edition()
    client = await admin_for(edition)
    r = await create(client, edition, email="visitor-101@example.test")
    assert r.status_code == 201, r.text
    lead = r.json()
    assert lead["registration_status"] == "REGISTERED" and lead["qr_status"] == "ACTIVE"
    regs = (await client.get(f"/api/v1/visitor-registrations?edition_id={edition.id}")).json()[
        "items"
    ]
    assert [x["channel"] for x in regs] == ["ADMIN"]
    detail = (await client.get(f"/api/v1/visitor-registrations/{regs[0]['id']}")).json()
    assert detail["email_jobs"] == []  # QR email is sent by hand (Resend QR Email)


async def test_lead_list_across_editions_keeps_each_scope() -> None:
    first, second, hidden = await make_edition(), await make_edition(), await make_edition()
    _, client = await actor(
        RoleGrant("EXHIBITION_ADMIN", "EDITION", first.id),
        RoleGrant("EXHIBITION_ADMIN", "EDITION", second.id),
    )
    _, super_client = await actor(RoleGrant("SUPER_ADMIN"))
    for edition in (first, second, hidden):
        r = await create(super_client, edition, phone=f"0812{uuid.uuid4().int % 10**8:08d}")
        assert r.status_code == 201, r.text
    items = (await client.get("/api/v1/visitor-leads?page_size=100")).json()["items"]
    editions = {i["edition_id"] for i in items}
    assert {str(first.id), str(second.id)} <= editions
    assert str(hidden.id) not in editions
    one = (await client.get(f"/api/v1/visitor-leads?edition_id={first.id}")).json()["items"]
    assert {i["edition_id"] for i in one} == {str(first.id)}


async def test_register_backlog_registers_old_leads() -> None:
    from app.modules.registrations import service as registrations_service

    edition = await make_edition()
    async with get_sessionmaker()() as session, session.begin():
        lead = VisitorLead(
            edition_id=edition.id,
            registration_code=f"{edition.registration_id_prefix}{uuid.uuid4().int % 10**6:06d}",
            first_name="Visitor",
            email="visitor-102@example.test",
            email_normalized="visitor-102@example.test",
            source="MANUAL",
            custom_fields={},
        )
        session.add(lead)
    async with get_sessionmaker()() as session, session.begin():
        while await registrations_service.register_backlog(session, 500):
            pass
    async with get_sessionmaker()() as session:
        stored = await session.get(VisitorLead, lead.id)
    assert stored is not None and stored.registration_status == "REGISTERED"


async def test_register_backlog_cli_runs_in_a_fresh_process() -> None:
    """The CLI runs without the app loaded; every model must still be mapped."""
    import sys

    edition = await make_edition()
    async with get_sessionmaker()() as session, session.begin():
        lead = VisitorLead(
            edition_id=edition.id,
            registration_code=f"{edition.registration_id_prefix}{uuid.uuid4().int % 10**6:06d}",
            first_name="Visitor",
            email="visitor-103@example.test",
            email_normalized="visitor-103@example.test",
            source="EXCEL",
            custom_fields={},
        )
        session.add(lead)
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "app.cli",
        "register-backlog",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await asyncio.wait_for(proc.communicate(), timeout=120)
    assert proc.returncode == 0, err.decode()[-2000:]
    assert out.decode().startswith("registered ")
    async with get_sessionmaker()() as session:
        stored = await session.get(VisitorLead, lead.id)
    assert stored is not None and stored.registration_status == "REGISTERED"


async def test_lead_source_master_data_and_lead_field() -> None:
    """Global "Source" master data (owner decision 2026-10-22); "source" stays the channel."""
    edition = await make_edition()
    _, root = await actor(RoleGrant("SUPER_ADMIN"))
    admin = await admin_for(edition)
    name = f"2026 test {uuid.uuid4().hex[:6]}"
    assert (await admin.post("/api/v1/lead-sources", json={"name": name})).status_code == 403
    r = await root.post("/api/v1/lead-sources", json={"name": name, "sort_order": 1})
    assert r.status_code == 201, r.text
    source = r.json()
    r = await root.post("/api/v1/lead-sources", json={"name": name})
    assert r.status_code == 409 and r.json()["error"]["code"] == "DUPLICATE_LEAD_SOURCE"
    listed = (await admin.get("/api/v1/lead-sources")).json()
    assert source["id"] in [s["id"] for s in listed]

    r = await create(admin, edition, email="visitor-104@example.test", lead_source_id=source["id"])
    assert r.status_code == 201, r.text
    lead = r.json()
    assert lead["lead_source_id"] == source["id"] and lead["source"] == "MANUAL"
    items = (
        await admin.get(
            f"/api/v1/visitor-leads?edition_id={edition.id}&lead_source_id={source['id']}"
        )
    ).json()["items"]
    assert [i["id"] for i in items] == [lead["id"]]

    r = await root.patch(
        f"/api/v1/lead-sources/{source['id']}", json={"version": 1, "is_active": False}
    )
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert source["id"] not in [s["id"] for s in (await admin.get("/api/v1/lead-sources")).json()]
    r = await create(admin, edition, email="visitor-105@example.test", lead_source_id=source["id"])
    assert r.status_code == 422 and "lead_source_id" in r.json()["error"]["fields"]
    # A lead that already has the inactive source keeps it on later edits.
    r = await admin.patch(
        f"/api/v1/visitor-leads/{lead['id']}",
        json={"version": lead["version"], "city": "Hanoi", "lead_source_id": source["id"]},
    )
    assert r.status_code == 200, r.text
    r = await create(
        admin, edition, email="visitor-106@example.test", lead_source_id=str(uuid.uuid4())
    )
    assert r.status_code == 422
