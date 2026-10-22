import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.core.config import get_settings
from app.core.db import get_sessionmaker, task_session
from app.core.email import MemorySender
from app.core.outbox import OutboxEvent
from app.modules.exhibitions.models import Edition
from app.modules.identity.models import User
from app.modules.telemarketing.models import VisitorCallActivity, VisitorVerification
from app.modules.telemarketing.rules import (
    LeadQuality,
    call_verification_errors,
    next_status,
    telemarketing_status,
)
from app.modules.telemarketing.tasks import queue_reminders_once, send_reminder_event
from app.modules.visitors.models import VisitorLead
from tests.factories import RoleGrant, actor, login_client, make_edition, make_user


# Status table v2 (owner decisions 2026-10-22, FEATURES/07), row for row.
@pytest.mark.parametrize(
    ("results", "status"),
    [
        ([], "NEW"),
        (["ANSWER"], "ANSWER"),
        (["NO_ANSWER"], "NO_ANSWER"),
        (["BUSY"], "NO_ANSWER"),
        (["ANSWER", "ANSWER"], "RECONTACTED"),
        (["ANSWER", "NO_ANSWER"], "ANSWER"),  # reached once stays reached
        (["NO_ANSWER", "ANSWER"], "RECONTACTED"),
        (["NO_ANSWER", "NO_ANSWER"], "RETRY_NO_ANSWER"),
        (["NO_ANSWER", "NO_ANSWER", "NO_ANSWER"], "RETRY_NO_ANSWER"),
        (["NO_ANSWER", "NO_ANSWER", "ANSWER"], "RECONTACTED"),
        (["ANSWER", "ANSWER", "NO_ANSWER", "ANSWER"], "RECONTACTED"),
    ],
)
def test_status_function(results: list[str], status: str) -> None:
    assert telemarketing_status(results) == status


@pytest.mark.parametrize(
    ("current", "answered", "expected"),
    [
        ("NEW", True, "ANSWER"),
        ("NEW", False, "NO_ANSWER"),
        ("ANSWER", True, "RECONTACTED"),
        ("ANSWER", False, "ANSWER"),
        ("NO_ANSWER", True, "RECONTACTED"),
        ("NO_ANSWER", False, "RETRY_NO_ANSWER"),
        ("RETRY_NO_ANSWER", True, "RECONTACTED"),
        ("RETRY_NO_ANSWER", False, "RETRY_NO_ANSWER"),
        ("RECONTACTED", True, "RECONTACTED"),
        ("RECONTACTED", False, "RECONTACTED"),
    ],
)
def test_next_status(current: str, answered: bool, expected: str) -> None:
    assert next_status(current, answered) == expected


VAL, INV, UND = LeadQuality.VALID, LeadQuality.INVALID, LeadQuality.UNDECIDED


@pytest.mark.parametrize(
    ("answered", "moves", "quality", "attend", "extra", "fields"),
    [
        (True, True, VAL, "ATTEND", [], set()),
        (True, True, VAL, None, [], {"attend"}),
        (True, True, INV, "ATTEND", [], {"lead_quality"}),
        (True, True, None, None, [], {"lead_quality", "attend"}),
        (True, False, VAL, None, [], {"attend"}),  # answered again: still Valid + Attend
        (False, True, INV, None, [], set()),
        (False, True, UND, None, [], set()),
        (False, True, None, None, [], {"lead_quality"}),
        (False, True, VAL, "ATTEND", ["attend"], {"attend"}),
        (False, True, VAL, None, ["b2b_matching", "buyer_type"], {"b2b_matching", "buyer_type"}),
        (False, False, None, None, [], set()),  # unanswered, status stays: nothing required
        (False, False, INV, None, [], set()),
    ],
)
def test_call_verification_rules(
    answered: bool,
    moves: bool,
    quality: LeadQuality | None,
    attend: str | None,
    extra: list[str],
    fields: set[str],
) -> None:
    assert set(call_verification_errors(answered, moves, quality, attend, extra)) == fields


async def setup() -> tuple[Edition, User, AsyncClient, str]:
    """Edition, agent (OWNED) with a client, and a lead owned by the agent."""
    edition = await make_edition()
    agent = await make_user(RoleGrant("TELEMARKETING_AGENT", "OWNED", edition.id))
    async with get_sessionmaker()() as session, session.begin():
        lead = VisitorLead(
            edition_id=edition.id,
            registration_code=f"T{uuid.uuid4().hex[:10]}",
            first_name="Tho",
            email_normalized="tho@example.test",
            email="tho@example.test",
            source="MANUAL",
            lead_owner_id=agent.id,
            custom_fields={},
        )
        session.add(lead)
    return edition, agent, await login_client(agent.email), str(lead.id)


ANSWERED = {"lead_quality": "VALID", "attend": "ATTEND"}
UNANSWERED = {"lead_quality": "UNDECIDED"}


async def call(client: AsyncClient, lead_id: str, result: str, **kw: Any) -> Any:
    """Log a call; verification defaults to the minimum the result needs."""
    kw.setdefault("verification", ANSWERED if result == "ANSWER" else UNANSWERED)
    if kw["verification"] is None:
        del kw["verification"]
    return await client.post(
        f"/api/v1/visitor-leads/{lead_id}/calls", json={"call_result": result, **kw}
    )


async def test_status_follows_call_history() -> None:
    _, _, client, lead_id = await setup()
    expected = ["NO_ANSWER", "RECONTACTED", "RECONTACTED"]
    for result, status in zip(["NO_ANSWER", "ANSWER", "ANSWER"], expected, strict=True):
        r = await call(client, lead_id, result, notes="rang twice")
        assert r.status_code == 201, r.text
        assert r.json()["telemarketing_status"] == status
    calls = (await client.get(f"/api/v1/visitor-leads/{lead_id}/calls")).json()
    assert [c["attempt_number"] for c in calls] == [1, 2, 3]
    lead = (await client.get(f"/api/v1/visitor-leads/{lead_id}")).json()
    assert lead["telemarketing_status"] == telemarketing_status([c["call_result"] for c in calls])
    assert lead["call_attempts"] == 3 and lead["last_call_at"] is not None
    actions = [
        a["action"] for a in (await client.get(f"/api/v1/visitor-leads/{lead_id}/activity")).json()
    ]
    # The lead timeline records changes; the third call left the status as it was. Every call
    # is still in the call history above.
    assert actions.count("call") == 2


async def test_reached_lead_stays_reached_and_every_call_is_logged() -> None:
    """Scenario 4: answered, then not answered: stays ANSWER, the call is still recorded."""
    _, _, client, lead_id = await setup()
    assert (await call(client, lead_id, "ANSWER")).json()["telemarketing_status"] == "ANSWER"
    r = await call(client, lead_id, "NO_ANSWER", verification=None)
    assert r.status_code == 201, r.text
    assert r.json()["telemarketing_status"] == "ANSWER"
    lead = (await client.get(f"/api/v1/visitor-leads/{lead_id}")).json()
    assert lead["attend"] == "ATTEND" and lead["is_valid_lead"]  # verification kept
    assert (await call(client, lead_id, "ANSWER")).json()["telemarketing_status"] == "RECONTACTED"
    for result in ("ANSWER", "NO_ANSWER"):
        r = await call(client, lead_id, result)
        assert r.status_code == 201 and r.json()["telemarketing_status"] == "RECONTACTED"
    calls = (await client.get(f"/api/v1/visitor-leads/{lead_id}/calls")).json()
    assert len(calls) == 5


async def test_retry_no_answer_reaches_recontacted() -> None:
    """Scenarios 3 and 5: misses stay RETRY_NO_ANSWER until a call is answered."""
    _, _, client, lead_id = await setup()
    for expected in ("NO_ANSWER", "RETRY_NO_ANSWER", "RETRY_NO_ANSWER"):
        r = await call(client, lead_id, "NO_ANSWER")
        assert r.json()["telemarketing_status"] == expected
    r = await call(client, lead_id, "ANSWER")
    assert r.json()["telemarketing_status"] == "RECONTACTED"
    assert r.json()["call_attempts"] == 4


async def test_call_verification_rules_over_the_api() -> None:
    _, _, client, lead_id = await setup()
    url = f"/api/v1/visitor-leads/{lead_id}/calls"
    assert (await client.post(url, json={"call_result": "ANSWER"})).status_code == 422
    r = await call(client, lead_id, "ANSWER", verification={"lead_quality": "VALID"})
    assert r.status_code == 422 and "attend" in r.json()["error"]["fields"]
    r = await call(
        client, lead_id, "ANSWER", verification={"lead_quality": "INVALID", "attend": "ATTEND"}
    )
    assert r.status_code == 422 and "lead_quality" in r.json()["error"]["fields"]
    r = await call(client, lead_id, "NO_ANSWER", verification=None)
    assert r.status_code == 422 and "lead_quality" in r.json()["error"]["fields"]
    r = await call(
        client, lead_id, "NO_ANSWER", verification={"lead_quality": "INVALID", "attend": "ATTEND"}
    )
    assert r.status_code == 422 and "attend" in r.json()["error"]["fields"]
    assert (await client.get(url)).json() == []

    r = await call(client, lead_id, "NO_ANSWER", verification={"lead_quality": "INVALID"})
    assert r.status_code == 201, r.text
    lead = (await client.get(f"/api/v1/visitor-leads/{lead_id}")).json()
    assert lead["is_invalid"] and not lead["is_valid_lead"] and lead["attend"] is None
    r = await call(
        client,
        lead_id,
        "ANSWER",
        verification={"lead_quality": "VALID", "attend": "ATTEND_SOURCING", "buyer_type": "B_SIDE"},
    )
    assert r.status_code == 201, r.text
    lead = (await client.get(f"/api/v1/visitor-leads/{lead_id}")).json()
    assert lead["is_valid_lead"] and lead["attend"] == "ATTEND_SOURCING"
    assert lead["buyer_type"] == "B_SIDE" and lead["telemarketing_status"] == "RECONTACTED"
    history = (await client.get(f"/api/v1/visitor-leads/{lead_id}/verifications")).json()
    assert len(history) == 2  # one history row per call that carried verification


async def test_unreached_lead_verification_tab_takes_lead_quality_only() -> None:
    _, _, client, lead_id = await setup()
    await call(client, lead_id, "NO_ANSWER")
    lead = (await client.get(f"/api/v1/visitor-leads/{lead_id}")).json()
    url = f"/api/v1/visitor-leads/{lead_id}/verification"
    r = await client.patch(url, json={"version": lead["version"], "attend": "ATTEND"})
    assert r.status_code == 422 and "attend" in r.json()["error"]["fields"]
    r = await client.patch(url, json={"version": lead["version"], "is_valid_lead": True})
    assert r.status_code == 200 and r.json()["is_valid_lead"]


async def test_parallel_calls_get_distinct_attempt_numbers() -> None:
    edition, _, _, lead_id = await setup()
    clients = []
    for _ in range(2):
        _, c = await actor(RoleGrant("TELEMARKETING_MANAGER", "EDITION", edition.id))
        clients.append(c)
    results = await asyncio.gather(*(call(c, lead_id, "NO_ANSWER") for c in clients))
    assert sorted(r.json()["call"]["attempt_number"] for r in results) == [1, 2]
    async with get_sessionmaker()() as session:
        lead = await session.get(VisitorLead, uuid.UUID(lead_id))
    assert lead is not None and lead.telemarketing_status == "RETRY_NO_ANSWER"


async def test_call_validation_and_no_edit_or_delete() -> None:
    _, _, client, lead_id = await setup()
    assert (await call(client, lead_id, "BUSY")).status_code == 422  # not configured (D7)
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    assert (await call(client, lead_id, "ANSWER", called_at=future)).status_code == 422
    r = await call(client, lead_id, "ANSWER")
    call_id = r.json()["call"]["id"]
    assert (
        await client.patch(f"/api/v1/visitor-leads/{lead_id}/calls/{call_id}", json={})
    ).status_code in (404, 405)
    assert (
        await client.delete(f"/api/v1/visitor-leads/{lead_id}/calls/{call_id}")
    ).status_code in (404, 405)
    with pytest.raises(DBAPIError, match="append-only"):
        async with get_sessionmaker()() as session, session.begin():
            await session.execute(
                text("UPDATE visitor_call_activities SET call_result = 'NO_ANSWER'")
            )


async def test_extra_call_result_via_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "call_results_extra", ["BUSY"])
    _, _, client, lead_id = await setup()
    assert (await client.get("/api/v1/telemarketing/call-results")).json() == [
        "ANSWER",
        "NO_ANSWER",
        "BUSY",
    ]
    r = await call(client, lead_id, "BUSY")
    assert r.status_code == 201 and r.json()["telemarketing_status"] == "NO_ANSWER"


async def test_agent_cannot_call_other_agents_lead() -> None:
    edition, _, _, lead_id = await setup()
    other = await make_user(RoleGrant("TELEMARKETING_AGENT", "OWNED", edition.id))
    client = await login_client(other.email)
    assert (await call(client, lead_id, "ANSWER")).status_code == 404


async def test_partial_verification_with_history() -> None:
    _, _, client, lead_id = await setup()
    url = f"/api/v1/visitor-leads/{lead_id}/verification"
    r = await client.patch(url, json={"version": 1, "attend": "HANG_UP_IMMEDIATELY"})
    assert r.status_code == 200, r.text
    lead = r.json()
    assert lead["attend"] == "HANG_UP_IMMEDIATELY" and lead["is_valid_lead"] is False
    r = await client.patch(
        url, json={"version": lead["version"], "is_valid_lead": True, "buyer_type": "B_SIDE"}
    )
    lead = r.json()
    assert lead["is_valid_lead"] and not lead["is_invalid"] and lead["buyer_type"] == "B_SIDE"
    r = await client.patch(url, json={"version": lead["version"], "is_invalid": True})
    lead = r.json()
    assert lead["is_invalid"] and not lead["is_valid_lead"]  # radio semantics
    r = await client.patch(
        url, json={"version": lead["version"], "is_valid_lead": True, "is_invalid": True}
    )
    assert r.status_code == 422
    r = await client.patch(url, json={"version": 1, "b2b_matching": True})
    assert r.status_code == 409  # stale version
    r = await client.patch(url, json={"version": lead["version"], "attend": "MAYBE"})
    assert r.status_code == 422

    history = (await client.get(f"/api/v1/visitor-leads/{lead_id}/verifications")).json()
    assert len(history) == 3
    assert history[0]["is_invalid"] is True and history[-1]["attend"] == "HANG_UP_IMMEDIATELY"
    # A call result is recorded separately from Attend (spec 4.2).
    assert (await client.get(f"/api/v1/visitor-leads/{lead_id}")).json()[
        "telemarketing_status"
    ] == "NEW"


async def test_followups_from_call_and_lifecycle() -> None:
    _, _, client, lead_id = await setup()
    due = datetime.now(UTC) + timedelta(hours=2)
    r = await call(client, lead_id, "NO_ANSWER", next_followup_at=due.isoformat())
    followup_id = r.json()["followup_id"]
    assert followup_id is not None
    lead = (await client.get(f"/api/v1/visitor-leads/{lead_id}")).json()
    assert lead["next_followup_at"] is not None
    one = (await client.get(f"/api/v1/followups/{followup_id}")).json()
    assert (one["status"], one["lead_first_name"], one["version"]) == ("OPEN", "Tho", 1)
    _, outsider = await actor(RoleGrant("TELEMARKETING_AGENT", "OWNED", (await make_edition()).id))
    assert (await outsider.get(f"/api/v1/followups/{followup_id}")).status_code == 404

    later = due + timedelta(days=3)
    r = await client.patch(
        f"/api/v1/followups/{followup_id}",
        json={"version": 1, "action": "RESCHEDULE", "due_at": later.isoformat()},
    )
    assert r.status_code == 200, r.text
    r = await client.patch(
        f"/api/v1/followups/{followup_id}", json={"version": 2, "action": "DONE", "note": "talked"}
    )
    assert r.json()["status"] == "DONE"
    r = await client.patch(
        f"/api/v1/followups/{followup_id}", json={"version": 3, "action": "CANCEL"}
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "FOLLOWUP_CLOSED"
    history = (await client.get(f"/api/v1/followups/{followup_id}/history")).json()
    assert [h["action"] for h in history] == ["CREATE", "RESCHEDULE", "DONE"]
    lead = (await client.get(f"/api/v1/visitor-leads/{lead_id}")).json()
    assert lead["next_followup_at"] is None


async def test_followup_buckets_in_edition_timezone() -> None:
    edition, agent, client, lead_id = await setup()
    now = datetime.now(UTC)
    future_today = await client.post(
        f"/api/v1/visitor-leads/{lead_id}/followups",
        json={"due_at": (now + timedelta(minutes=1)).isoformat()},
    )
    assert future_today.status_code == 201
    upcoming = await client.post(
        f"/api/v1/visitor-leads/{lead_id}/followups",
        json={"due_at": (now + timedelta(days=3)).isoformat()},
    )
    assert upcoming.status_code == 201
    # An overdue one, created directly (the API refuses past due dates).
    async with get_sessionmaker()() as session, session.begin():
        from app.modules.telemarketing.models import VisitorFollowup

        session.add(
            VisitorFollowup(
                edition_id=edition.id,
                visitor_lead_id=uuid.UUID(lead_id),
                assigned_to=agent.id,
                due_at=now - timedelta(days=2),
                status="OPEN",
            )
        )
    base = {"edition_id": str(edition.id)}
    overdue = (await client.get("/api/v1/followups", params={**base, "bucket": "overdue"})).json()
    upcoming_list = (
        await client.get("/api/v1/followups", params={**base, "bucket": "upcoming"})
    ).json()
    assert overdue["total"] == 1
    assert [f["id"] for f in upcoming_list["items"]] == [upcoming.json()["id"]]
    assert upcoming_list["items"][0]["lead_first_name"] == "Tho"
    all_open = (await client.get("/api/v1/followups", params={**base, "bucket": "all"})).json()
    assert all_open["total"] == 3


async def test_my_queue_orders_followups_then_new() -> None:
    edition, agent, client, lead_id = await setup()
    async with get_sessionmaker()() as session, session.begin():
        for name in ("Fresh", "Called"):
            session.add(VisitorLead(edition_id=edition.id, registration_code=f"Q{name}", first_name=name,
                                    email_normalized=f"{name.lower()}@example.test", source="MANUAL",
                                    lead_owner_id=agent.id, custom_fields={},
                                    telemarketing_status="NEW" if name == "Fresh" else "NO_ANSWER"))  # fmt: skip
    await client.post(
        f"/api/v1/visitor-leads/{lead_id}/followups",
        json={"due_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat()},
    )
    queue = (
        await client.get("/api/v1/telemarketing/my-queue", params={"edition_id": str(edition.id)})
    ).json()
    assert [i["first_name"] for i in queue["items"]] == ["Tho", "Fresh", "Called"]
    r = await client.get(
        "/api/v1/telemarketing/team-queue",
        params={"edition_id": str(edition.id), "agent_id": str(agent.id)},
    )
    assert r.status_code == 403  # agents lack telemarketing.view_team
    _, mgr = await actor(RoleGrant("TELEMARKETING_MANAGER", "EDITION", edition.id))
    r = await mgr.get(
        "/api/v1/telemarketing/team-queue",
        params={"edition_id": str(edition.id), "agent_id": str(agent.id)},
    )
    assert r.json()["total"] == 3


async def test_reminders_disabled_by_default_and_never_twice(
    monkeypatch: pytest.MonkeyPatch, mailbox: MemorySender
) -> None:
    _, agent, client, lead_id = await setup()
    await client.post(
        f"/api/v1/visitor-leads/{lead_id}/followups",
        json={"due_at": (datetime.now(UTC) + timedelta(minutes=10)).isoformat()},
    )
    assert await queue_reminders_once() == 0  # D4 not decided: off

    monkeypatch.setattr(get_settings(), "followup_reminders_enabled", True)
    assert await queue_reminders_once() == 1
    assert await queue_reminders_once() == 0  # same followup + due_at: already claimed
    async with task_session() as session:
        event = await session.scalar(
            select(OutboxEvent).where(
                OutboxEvent.task_name == "telemarketing.send_followup_reminder"
            )
        )
    assert event is not None
    assert await send_reminder_event(event.id) is True
    assert await send_reminder_event(event.id) is False
    assert len(mailbox.outbox) == 1 and mailbox.outbox[0].to == agent.email


async def test_verification_rows_append_only() -> None:
    _, _, client, lead_id = await setup()
    await client.patch(
        f"/api/v1/visitor-leads/{lead_id}/verification", json={"version": 1, "b2b_matching": True}
    )
    async with get_sessionmaker()() as session:
        assert len((await session.scalars(select(VisitorVerification))).all()) == 1
        assert (await session.scalars(select(VisitorCallActivity))).all() == []
    with pytest.raises(DBAPIError, match="append-only"):
        async with get_sessionmaker()() as session, session.begin():
            await session.execute(text("DELETE FROM visitor_verifications"))
