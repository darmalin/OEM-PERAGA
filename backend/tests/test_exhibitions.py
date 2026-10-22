import asyncio
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.audit import AuditLog
from app.core.db import get_sessionmaker
from app.modules.exhibitions import service as exhibitions_service
from app.modules.exhibitions.models import EditionCounter
from app.modules.exhibitions.rules import EditionStatus, can_transition
from tests.factories import RoleGrant, actor, make_edition, make_gate


def edition_body(exhibition_id: str, **over: Any) -> dict[str, Any]:
    return {
        "exhibition_id": exhibition_id,
        "year": 2027,
        "start_date": "2027-05-10",
        "end_date": "2027-05-12",
        "timezone": "Asia/Jakarta",
        "default_currency": "idr",
        "country": "id",
        **over,
    }


@pytest.mark.parametrize(
    ("current", "target", "ok"),
    [
        (EditionStatus.DRAFT, EditionStatus.ACTIVE, True),
        (EditionStatus.DRAFT, EditionStatus.CLOSED, False),
        (EditionStatus.ACTIVE, EditionStatus.CLOSED, True),
        (EditionStatus.ACTIVE, EditionStatus.DRAFT, False),
        (EditionStatus.CLOSED, EditionStatus.ACTIVE, True),
        (EditionStatus.CLOSED, EditionStatus.ARCHIVED, True),
        (EditionStatus.ARCHIVED, EditionStatus.ACTIVE, False),
    ],
)
def test_status_lifecycle(current: EditionStatus, target: EditionStatus, ok: bool) -> None:
    assert can_transition(current, target) is ok


async def _create_exhibition(client: AsyncClient, code: str = "IBTE") -> dict[str, Any]:
    r = await client.post("/api/v1/exhibitions", json={"code": code, "name": f"{code} Expo"})
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_exhibition_and_edition() -> None:
    _, admin = await actor(RoleGrant("SUPER_ADMIN"))
    ex = await _create_exhibition(admin, "ibte")
    assert ex["code"] == "IBTE"
    r = await admin.post("/api/v1/exhibitions", json={"code": "IBTE", "name": "Dup"})
    assert r.status_code == 409

    r = await admin.post("/api/v1/editions", json=edition_body(ex["id"]))
    assert r.status_code == 201, r.text
    edition = r.json()
    assert edition["code"] == "IBTE2027"
    assert edition["registration_id_prefix"] == "IBTE2027"
    assert edition["status"] == "DRAFT"
    assert edition["default_currency"] == "IDR" and edition["country"] == "ID"

    async with get_sessionmaker()() as session:
        counter = await session.get(EditionCounter, uuid.UUID(edition["id"]))
        assert counter is not None and counter.last_value == 0
        audits = await session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.edition_id == counter.edition_id)
        )
        assert audits == 1


async def test_second_edition_same_year_rejected_by_db() -> None:
    _, admin = await actor(RoleGrant("SUPER_ADMIN"))
    ex = await _create_exhibition(admin)
    assert (await admin.post("/api/v1/editions", json=edition_body(ex["id"]))).status_code == 201
    r = await admin.post("/api/v1/editions", json=edition_body(ex["id"], code="IBTE2027B"))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "DUPLICATE_EDITION"
    assert r.json()["error"]["fields"] == {"year": "Already has an edition."}
    r = await admin.post("/api/v1/editions", json=edition_body(ex["id"], year=2028))
    assert r.status_code == 201


@pytest.mark.parametrize(
    ("over", "field"),
    [
        ({"end_date": "2027-05-01"}, "request"),
        ({"timezone": "Mars/Base"}, "timezone"),
        ({"country": "XX"}, "country"),
        ({"default_currency": "RUPIAH"}, "default_currency"),
    ],
)
async def test_edition_validation(over: dict[str, Any], field: str) -> None:
    _, admin = await actor(RoleGrant("SUPER_ADMIN"))
    ex = await _create_exhibition(admin)
    r = await admin.post("/api/v1/editions", json=edition_body(ex["id"], **over))
    assert r.status_code == 422
    assert field in r.json()["error"]["fields"]


async def test_status_transition_through_patch() -> None:
    _, admin = await actor(RoleGrant("SUPER_ADMIN"))
    ex = await _create_exhibition(admin)
    edition = (await admin.post("/api/v1/editions", json=edition_body(ex["id"]))).json()
    url = f"/api/v1/editions/{edition['id']}"
    r = await admin.patch(url, json={"version": 1, "status": "CLOSED"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"
    r = await admin.patch(url, json={"version": 1, "status": "ACTIVE"})
    assert r.status_code == 200 and r.json()["version"] == 2
    r = await admin.patch(url, json={"version": 1, "city": "Jakarta"})
    assert r.status_code == 409


async def test_out_of_scope_edition_is_404_and_hidden() -> None:
    mine, other = await make_edition(), await make_edition()
    _, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", mine.id))

    listed = (await admin.get("/api/v1/editions")).json()
    assert [e["id"] for e in listed["items"]] == [str(mine.id)]
    assert (await admin.get(f"/api/v1/editions/{mine.id}")).status_code == 200
    r = await admin.get(f"/api/v1/editions/{other.id}")
    assert r.status_code == 404
    r = await admin.patch(f"/api/v1/editions/{other.id}", json={"version": 1, "city": "X"})
    assert r.status_code == 404

    exhibitions = (await admin.get("/api/v1/exhibitions")).json()["items"]
    assert [e["id"] for e in exhibitions] == [str(mine.exhibition_id)]
    assert (await admin.get(f"/api/v1/exhibitions/{other.exhibition_id}")).status_code == 404


async def test_edition_admin_edits_own_edition_but_not_master_data() -> None:
    mine = await make_edition()
    _, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", mine.id))
    r = await admin.patch(f"/api/v1/editions/{mine.id}", json={"version": 1, "city": "Jakarta"})
    assert r.status_code == 200
    assert (
        await admin.post("/api/v1/exhibitions", json={"code": "NEW", "name": "N"})
    ).status_code == 403
    body = edition_body(str(mine.exhibition_id), year=2030)
    assert (await admin.post("/api/v1/editions", json=body)).status_code == 403


async def test_agent_reads_but_cannot_edit_edition() -> None:
    edition = await make_edition()
    _, agent = await actor(RoleGrant("TELEMARKETING_AGENT", "OWNED", edition.id))
    assert (await agent.get(f"/api/v1/editions/{edition.id}")).status_code == 200
    r = await agent.patch(f"/api/v1/editions/{edition.id}", json={"version": 1, "city": "X"})
    assert r.status_code == 403


async def test_me_lists_allowed_editions() -> None:
    mine, _other = await make_edition(), await make_edition()
    gate = await make_gate(mine)
    _, agent = await actor(RoleGrant("GATE_STAFF", "GATE", mine.id, gate_id=gate.id))
    me = (await agent.get("/api/v1/auth/me")).json()
    assert [e["id"] for e in me["editions"]] == [str(mine.id)]


async def test_registration_id_counter_is_unique_under_concurrency() -> None:
    edition = await make_edition(exhibition_code="IBTE", year=2027)

    async def next_id() -> str:
        async with get_sessionmaker()() as session, session.begin():
            return await exhibitions_service.next_registration_id(session, edition.id)

    ids = await asyncio.gather(*(next_id() for _ in range(25)))
    assert len(set(ids)) == 25
    assert sorted(ids)[0] == "IBTE2027000001"
    assert sorted(ids)[-1] == "IBTE2027000025"


async def test_venue_crud() -> None:
    _, admin = await actor(RoleGrant("SUPER_ADMIN"))
    r = await admin.post(
        "/api/v1/venues", json={"name": "JIExpo", "city": "Jakarta", "country": "ID"}
    )
    assert r.status_code == 201
    venue = r.json()
    r = await admin.patch(
        f"/api/v1/venues/{venue['id']}", json={"version": 1, "name": "JIExpo Kemayoran"}
    )
    assert r.status_code == 200 and r.json()["name"] == "JIExpo Kemayoran"
    ex = await _create_exhibition(admin)
    r = await admin.post(
        "/api/v1/editions", json=edition_body(ex["id"], venue_id=str(uuid.uuid4()))
    )
    assert r.status_code == 422


async def test_edition_remarks_and_exhibitor_dates_are_stored() -> None:
    """Display-only fields from the old Exhibition form (FEATURES/02 "Exhibitor dates")."""
    _, admin = await actor(RoleGrant("SUPER_ADMIN"))
    ex = await _create_exhibition(admin)
    body = edition_body(
        ex["id"],
        remarks="The 23rd Indonesia International Textile and Garment Machinery Exhibition",
        price_regular_from="2026-09-01",
        price_regular_to="2027-03-01",
        price_onsite_from="2027-04-01",
        price_onsite_to="2027-04-17",
        catalog_expired_on="2027-02-23",
    )
    r = await admin.post("/api/v1/editions", json=body)
    assert r.status_code == 201, r.text
    edition = r.json()
    assert edition["price_regular_to"] == "2027-03-01" and edition["order_expired_on"] is None
    assert edition["remarks"].startswith("The 23rd")
    url = f"/api/v1/editions/{edition['id']}"
    r = await admin.patch(
        url,
        json={
            "version": edition["version"],
            "price_surcharge_from": "2027-03-31",
            "price_surcharge_to": "2027-03-02",
        },
    )
    assert r.status_code == 422 and "price_surcharge_to" in r.json()["error"]["fields"]
    r = await admin.patch(
        url, json={"version": edition["version"], "price_regular_to": "2026-08-01"}
    )
    assert r.status_code == 422 and "price_regular_to" in r.json()["error"]["fields"]
    r = await admin.patch(
        url, json={"version": edition["version"], "order_expired_on": "2027-04-01"}
    )
    assert r.status_code == 200 and r.json()["order_expired_on"] == "2027-04-01"
