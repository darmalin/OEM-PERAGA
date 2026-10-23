"""Dashboard numbers per call (FEATURES/10 "Dashboard"), checked by hand on a small scenario."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from httpx import AsyncClient
from sqlalchemy import update

from app.core.db import get_sessionmaker
from app.modules.exhibitions.models import Edition
from app.modules.visitors.models import VisitorLead
from tests.factories import RoleGrant, actor, make_edition

ANSWERED = {
    "lead_quality": "VALID",
    "attend": "ATTEND",
    "buyer_type": "B_SIDE",
    "b2b_matching": True,
}


async def lead(client: AsyncClient, edition: Edition, n: int) -> str:
    r = await client.post(
        "/api/v1/visitor-leads",
        json={"edition_id": str(edition.id), "first_name": f"Visitor {n:03d}",
              "email": f"visitor{n:03d}@example.test", "country": "VN"},
    )  # fmt: skip
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def call(client: AsyncClient, lead_id: str, result: str, verification: Any = None) -> None:
    body: dict[str, Any] = {"call_result": result}
    if verification is not None:
        body["verification"] = verification
    r = await client.post(f"/api/v1/visitor-leads/{lead_id}/calls", json=body)
    assert r.status_code == 201, r.text


async def world() -> tuple[Edition, AsyncClient, uuid.UUID, dict[str, str]]:
    """A: answered then missed. B: missed then answered. C: never called, created 2 days ago."""
    edition = await make_edition()
    user, client = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))
    ids = {name: await lead(client, edition, i) for i, name in enumerate("ABC", start=1)}
    await call(client, ids["A"], "ANSWER", ANSWERED)
    await call(client, ids["A"], "NO_ANSWER")  # status stays Answer; counts as a later miss
    await call(client, ids["B"], "NO_ANSWER", {"lead_quality": "INVALID"})
    await call(
        client, ids["B"], "ANSWER",
        {"lead_quality": "VALID", "attend": "NOT_ATTEND", "buyer_type": "C_SIDE"},
    )  # fmt: skip
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(
            update(VisitorLead)
            .where(VisitorLead.id == uuid.UUID(ids["C"]))
            .values(created_at=datetime.now(UTC) - timedelta(days=2))
        )
    return edition, client, user.id, ids


def today() -> Any:
    return datetime.now(ZoneInfo("Asia/Jakarta")).date()


async def dashboard(client: AsyncClient, **params: Any) -> Any:
    r = await client.get("/api/v1/reports/dashboard", params=params)
    assert r.status_code == 200, r.text
    return r.json()


async def test_totals_count_calls_and_pending() -> None:
    edition, client, _, _ = await world()
    d = today()
    out = await dashboard(client, date_from=str(d - timedelta(days=2)), date_to=str(d))
    [row] = out["rows"]
    assert out["timezone"] == "Asia/Jakarta"
    assert (row["added"], row["pending"], row["total"]) == (3, 1, 4)
    assert (row["answer"], row["non_answer"]) == (1, 1)
    assert (row["recontacted"], row["retry_no_answer"]) == (1, 1)
    assert (row["valid"], row["no_valid"]) == (2, 1)
    assert (row["attend"], row["not_attend"], row["b2b_matching"]) == (1, 1, 1)
    assert (row["b_side"], row["c_side"]) == (1, 1)

    valid = await dashboard(client, date_from=str(d), date_to=str(d), lead_quality="VALID")
    assert valid["rows"][0]["total"] == 2
    first = await dashboard(client, date_from=str(d), date_to=str(d), edition_id=str(edition.id))
    assert first["rows"][0]["total"] == 4 and first["rows"][0]["added"] == 2


async def test_daily_rows_carry_pending_forward() -> None:
    _, client, _, _ = await world()
    d = today()
    out = await dashboard(
        client, date_from=str(d - timedelta(days=2)), date_to=str(d), group_by="day"
    )
    by_day = {r["day"]: r for r in out["rows"]}
    two_ago, yesterday = str(d - timedelta(days=2)), str(d - timedelta(days=1))
    assert (by_day[two_ago]["added"], by_day[two_ago]["pending"]) == (1, 1)
    assert by_day[yesterday]["pending"] == 1 and by_day[yesterday]["total"] == 0
    assert (by_day[str(d)]["added"], by_day[str(d)]["pending"], by_day[str(d)]["total"]) == (
        2,
        1,
        4,
    )


async def test_recaps_by_edition_source_and_user_with_scope() -> None:
    edition, client, user_id, _ = await world()
    other = await make_edition()
    _, other_admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", other.id))
    other_lead = await lead(other_admin, other, 9)
    await call(other_admin, other_lead, "ANSWER", ANSWERED)
    d = str(today())

    by_edition = await dashboard(client, date_from=d, date_to=d, group_by="day_edition")
    assert {k["label"] for k in by_edition["keys"]} == {edition.code}  # the other edition is hidden
    assert sum(r["total"] for r in by_edition["rows"]) == 4

    by_user = await dashboard(client, date_from=d, date_to=d, group_by="day_user")
    mine = [r for r in by_user["rows"] if r["key"] == str(user_id)]
    assert mine and mine[0]["total"] == 4
    assert any(k["id"] == str(user_id) and k["editions"] == edition.code for k in by_user["keys"])

    by_source = await dashboard(client, date_from=d, date_to=d, group_by="day_source")
    assert by_source["keys"][-1]["label"] == "No source"
    assert sum(r["total"] for r in by_source["rows"] if r["key"] is None) == 4

    options = (await client.get("/api/v1/reports/dashboard/options")).json()
    assert options["countries"] == ["VN"]


async def test_dashboard_validation_and_permission() -> None:
    edition = await make_edition()
    _, agent = await actor(RoleGrant("GATE_STAFF", "EDITION", edition.id))
    d = str(today())
    r = await agent.get("/api/v1/reports/dashboard", params={"date_from": d, "date_to": d})
    assert r.status_code == 403
    _, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))
    r = await admin.get(
        "/api/v1/reports/dashboard", params={"date_from": d, "date_to": "2000-01-01"}
    )
    assert r.status_code == 422


async def test_email_report_counts_lead_emails(mailbox: Any) -> None:
    from sqlalchemy import select

    from app.core.outbox import OutboxEvent
    from app.modules.registrations.tasks import send_qr_email_event

    edition = await make_edition()
    _, client = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))
    leads = [await lead(client, edition, n) for n in (21, 22, 23)]
    for lead_id in leads:
        regs = (
            await client.get(
                "/api/v1/visitor-registrations",
                params={"edition_id": str(edition.id), "visitor_lead_id": lead_id},
            )
        ).json()["items"]
        r = await client.post(
            f"/api/v1/visitor-registrations/{regs[0]['id']}/resend-qr",
            headers={"Idempotency-Key": uuid.uuid4().hex},
        )
        assert r.status_code == 202, r.text
    async with get_sessionmaker()() as session:
        events = list(
            await session.scalars(
                select(OutboxEvent.id)
                .where(OutboxEvent.event_type == "mail.qr_confirmation")
                .order_by(OutboxEvent.created_at)
            )
        )
    assert await send_qr_email_event(events[0]) == "SENT"
    assert await send_qr_email_event(events[1], final_attempt=True) == "SENT"
    # The third stays queued: waiting.
    # A password reset (system email) never shows here.
    await client.post("/api/v1/auth/password-reset/request", json={"email": "nobody@example.test"})

    d = str(today())
    r = await client.get("/api/v1/reports/dashboard/email", params={"date_from": d, "date_to": d})
    assert r.status_code == 200, r.text
    out = r.json()
    t = out["totals"]
    assert (t["queued"], t["sent"], t["waiting"], t["failed"]) == (3, 2, 1, 0)
    assert (t["sent_today"], t["waiting_now"], t["all_time"]) == (2, 1, 3)
    assert out["days"] == [{"day": d, "queued": 3, "sent": 2, "failed": 0, "waiting": 1}]
    assert [w["lead_name"] for w in out["waiting"]] == ["Visitor 023"]
    assert {c["key"]: c["count"] for c in out["by_status"]} == {"SENT": 2, "QUEUED": 1}

    other = await make_edition()
    _, stranger = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", other.id))
    r = await stranger.get("/api/v1/reports/dashboard/email", params={"date_from": d, "date_to": d})
    assert r.json()["totals"]["all_time"] == 0
