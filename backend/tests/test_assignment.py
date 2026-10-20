import asyncio
import uuid
from collections import Counter
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.core.db import get_sessionmaker, task_session
from app.core.outbox import OutboxEvent
from app.modules.exhibitions.models import Edition
from app.modules.identity.models import User
from app.modules.telemarketing import service as tm_service
from app.modules.telemarketing.models import LeadAssignmentHistory
from app.modules.telemarketing.rules import round_robin
from app.modules.telemarketing.tasks import run_assignment_event
from app.modules.visitors.models import VisitorLead
from tests.factories import RoleGrant, actor, login_client, make_edition, make_user

A, B, C = (uuid.UUID(int=i) for i in (1, 2, 3))


def test_round_robin_10_leads_3_agents() -> None:
    leads = [uuid.uuid4() for _ in range(10)]
    pairs, last = round_robin(leads, [C, A, B], None)
    assert Counter(a for _, a in pairs) == {A: 4, B: 3, C: 3}
    assert [a for _, a in pairs][:4] == [A, B, C, A]
    assert last == A
    pairs, last = round_robin([uuid.uuid4() for _ in range(2)], [A, B, C], last)
    assert [a for _, a in pairs] == [B, C] and last == C
    pairs, _ = round_robin([uuid.uuid4()], [A, C], B)  # B left the pool: next in order
    assert [a for _, a in pairs] == [C]


async def leads_in(edition: Edition, n: int, owner: uuid.UUID | None = None) -> list[str]:
    ids = []
    async with get_sessionmaker()() as session, session.begin():
        for i in range(n):
            lead = VisitorLead(
                edition_id=edition.id,
                registration_code=f"T{uuid.uuid4().hex[:10]}",
                first_name=f"Lead {i}",
                email_normalized=f"{uuid.uuid4().hex}@example.test",
                source="MANUAL",
                lead_owner_id=owner,
                custom_fields={},
            )
            session.add(lead)
            await session.flush()
            ids.append(str(lead.id))
    return ids


async def agents(edition: Edition, n: int, teams: tuple[uuid.UUID, ...] = ()) -> list[User]:
    return [
        await make_user(RoleGrant("TELEMARKETING_AGENT", "OWNED", edition.id), teams=teams)
        for _ in range(n)
    ]


def body(
    edition: Edition, method: str, lead_ids: list[str], agent_ids: list[Any], **kw: Any
) -> dict[str, Any]:
    return {
        "edition_id": str(edition.id), "method": method, "lead_ids": lead_ids,
        "agent_ids": [str(a) for a in agent_ids], **kw,
    }  # fmt: skip


async def owners(lead_ids: list[str]) -> list[uuid.UUID | None]:
    async with get_sessionmaker()() as session:
        rows = await session.execute(
            select(VisitorLead.id, VisitorLead.lead_owner_id).where(
                VisitorLead.id.in_([uuid.UUID(i) for i in lead_ids])
            )
        )
        found = dict(rows.all())
    return [found[uuid.UUID(i)] for i in lead_ids]


async def manager(edition: Edition) -> AsyncClient:
    _, client = await actor(RoleGrant("TELEMARKETING_MANAGER", "EDITION", edition.id))
    return client


async def test_manual_and_bulk_assignment_with_history() -> None:
    edition = await make_edition()
    client = await manager(edition)
    (agent,) = await agents(edition, 1)
    ids = await leads_in(edition, 3)

    r = await client.post(
        "/api/v1/visitor-leads/assignments", json=body(edition, "MANUAL", ids[:1], [agent.id])
    )
    assert r.status_code == 200, r.text
    assert r.json()["assigned"] == 1
    r = await client.post(
        "/api/v1/visitor-leads/assignments", json=body(edition, "BULK", ids, [agent.id])
    )
    assert r.json()["assigned"] == 2 and r.json()["unchanged"] == 1
    assert await owners(ids) == [agent.id] * 3

    history = (await client.get(f"/api/v1/visitor-leads/{ids[0]}/assignments")).json()
    assert len(history) == 1
    assert history[0]["method"] == "MANUAL" and history[0]["to_user_id"] == str(agent.id)
    assert history[0]["actor_user_id"] is not None
    timeline = (await client.get(f"/api/v1/visitor-leads/{ids[0]}/activity")).json()
    assert timeline[0]["action"] == "assign"
    assert timeline[0]["after"] == {"lead_owner_id": str(agent.id)}

    r = await client.post(
        "/api/v1/visitor-leads/assignments", json=body(edition, "MANUAL", ids[:2], [agent.id])
    )
    assert r.status_code == 422  # manual takes one lead


async def test_round_robin_api_continues_from_cursor() -> None:
    edition = await make_edition()
    client = await manager(edition)
    pool = sorted(await agents(edition, 3), key=lambda u: u.id)
    ids = await leads_in(edition, 10)
    r = await client.post(
        "/api/v1/visitor-leads/assignments",
        json=body(edition, "ROUND_ROBIN", ids, [u.id for u in pool]),
    )
    assert r.status_code == 200, r.text
    counts = Counter(await owners(ids))
    assert sorted(counts.values()) == [3, 3, 4]
    assert counts[pool[0].id] == 4

    more = await leads_in(edition, 2)
    await client.post(
        "/api/v1/visitor-leads/assignments",
        json=body(edition, "ROUND_ROBIN", more, [u.id for u in pool]),
    )
    assert await owners(more) == [pool[1].id, pool[2].id]


async def test_reassign_needs_permission() -> None:
    edition = await make_edition()
    _, root = await actor(RoleGrant("SUPER_ADMIN"))
    r = await root.post(
        "/api/v1/roles",
        json={
            "code": "ASSIGNER",
            "name": "Assigner",
            "permissions": ["visitor.read", "visitor.assign"],
        },
    )
    assert r.status_code == 201
    assigner = await make_user(RoleGrant("ASSIGNER", "EDITION", edition.id))
    client = await login_client(assigner.email)
    first, second = await agents(edition, 2)
    ids = await leads_in(edition, 1, owner=first.id)
    fresh = await leads_in(edition, 1)

    r = await client.post(
        "/api/v1/visitor-leads/assignments", json=body(edition, "MANUAL", fresh, [second.id])
    )
    assert r.status_code == 200
    r = await client.post(
        "/api/v1/visitor-leads/assignments", json=body(edition, "MANUAL", ids, [second.id])
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "REASSIGN_NOT_ALLOWED"
    assert await owners(ids) == [first.id]

    mgr = await manager(edition)
    r = await mgr.post(
        "/api/v1/visitor-leads/assignments", json=body(edition, "MANUAL", ids, [second.id])
    )
    assert r.status_code == 200
    history = (await mgr.get(f"/api/v1/visitor-leads/{ids[0]}/assignments")).json()
    assert history[0]["from_user_id"] == str(first.id)


async def test_only_eligible_agents_and_visible_leads() -> None:
    edition, other = await make_edition(), await make_edition()
    client = await manager(edition)
    (outsider,) = await agents(other, 1)
    gate = await make_user(RoleGrant("GATE_STAFF", "GATE", edition.id))
    ids = await leads_in(edition, 1)
    for bad in (outsider.id, gate.id):
        r = await client.post(
            "/api/v1/visitor-leads/assignments", json=body(edition, "MANUAL", ids, [bad])
        )
        assert r.status_code == 422
    (agent,) = await agents(edition, 1)
    foreign = await leads_in(other, 1)
    r = await client.post(
        "/api/v1/visitor-leads/assignments", json=body(edition, "MANUAL", foreign, [agent.id])
    )
    assert r.status_code == 404
    listed = (
        await client.get(
            "/api/v1/visitor-leads/assignable-agents", params={"edition_id": str(edition.id)}
        )
    ).json()
    listed_ids = {a["id"] for a in listed}
    assert str(agent.id) in listed_ids  # the manager can also take calls, so is listed too
    assert str(outsider.id) not in listed_ids and str(gate.id) not in listed_ids


async def test_team_manager_limited_to_own_team() -> None:
    edition = await make_edition()
    _, root = await actor(RoleGrant("SUPER_ADMIN"))
    team_a = uuid.UUID((await root.post("/api/v1/teams", json={"name": "A"})).json()["id"])
    team_b = uuid.UUID((await root.post("/api/v1/teams", json={"name": "B"})).json()["id"])
    (in_team,) = await agents(edition, 1, teams=(team_a,))
    (other_team,) = await agents(edition, 1, teams=(team_b,))
    lead_mgr = await make_user(
        RoleGrant("TELEMARKETING_MANAGER", "TEAM", edition.id, team_a), teams=(team_a,)
    )
    client = await login_client(lead_mgr.email)
    ids = await leads_in(edition, 1, owner=in_team.id)
    r = await client.post(
        "/api/v1/visitor-leads/assignments", json=body(edition, "MANUAL", ids, [other_team.id])
    )
    assert r.status_code == 422
    listed = (
        await client.get(
            "/api/v1/visitor-leads/assignable-agents", params={"edition_id": str(edition.id)}
        )
    ).json()
    assert {a["id"] for a in listed} == {str(in_team.id), str(lead_mgr.id)}


async def test_parallel_round_robin_never_double_assigns() -> None:
    edition = await make_edition()
    pool = await agents(edition, 3)
    clients = [await manager(edition) for _ in range(2)]
    batches = [await leads_in(edition, 3), await leads_in(edition, 3)]
    results = await asyncio.gather(
        *(
            c.post(
                "/api/v1/visitor-leads/assignments",
                json=body(edition, "ROUND_ROBIN", b, [u.id for u in pool]),
            )
            for c, b in zip(clients, batches, strict=True)
        )
    )
    assert all(r.status_code == 200 for r in results)
    counts = Counter(await owners(batches[0] + batches[1]))
    assert sorted(counts.values()) == [2, 2, 2]


async def test_idempotent_assignment() -> None:
    edition = await make_edition()
    client = await manager(edition)
    first, second = await agents(edition, 2)
    ids = await leads_in(edition, 2)
    payload = body(edition, "BULK", ids, [first.id])
    headers = {"Idempotency-Key": "assign-key-0001"}
    r1 = await client.post("/api/v1/visitor-leads/assignments", json=payload, headers=headers)
    r2 = await client.post("/api/v1/visitor-leads/assignments", json=payload, headers=headers)
    assert r1.status_code == r2.status_code == 200
    assert r1.json() == r2.json()
    async with get_sessionmaker()() as session:
        rows = (await session.scalars(select(LeadAssignmentHistory))).all()
    assert len(rows) == 2
    r3 = await client.post(
        "/api/v1/visitor-leads/assignments",
        json=body(edition, "BULK", ids, [second.id]),
        headers=headers,
    )
    assert r3.status_code == 409 and r3.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


async def test_large_batch_runs_in_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tm_service, "MAX_SYNC_ASSIGN", 2)
    edition = await make_edition()
    client = await manager(edition)
    pool = await agents(edition, 2)
    await leads_in(edition, 5)
    r = await client.post(
        "/api/v1/visitor-leads/assignments",
        json={"edition_id": str(edition.id), "method": "ROUND_ROBIN", "filter": {"unassigned": True},
              "agent_ids": [str(u.id) for u in pool]},
    )  # fmt: skip
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]
    async with task_session() as session:
        event = await session.scalar(
            select(OutboxEvent).where(OutboxEvent.task_name == "telemarketing.run_assignment")
        )
    assert event is not None
    assert await run_assignment_event(event.id) == "COMPLETED"
    job = (await client.get(f"/api/v1/visitor-leads/assignments/jobs/{job_id}")).json()
    assert job["status"] == "COMPLETED" and job["result"]["assigned"] == 5


async def test_history_is_append_only() -> None:
    edition = await make_edition()
    client = await manager(edition)
    (agent,) = await agents(edition, 1)
    ids = await leads_in(edition, 1)
    await client.post(
        "/api/v1/visitor-leads/assignments", json=body(edition, "MANUAL", ids, [agent.id])
    )
    for stmt in (
        "UPDATE lead_assignment_history SET method = 'BULK'",
        "DELETE FROM lead_assignment_history",
    ):
        with pytest.raises(DBAPIError, match="append-only"):
            async with get_sessionmaker()() as session, session.begin():
                await session.execute(text(stmt))


async def test_agent_cannot_assign() -> None:
    edition = await make_edition()
    (agent,) = await agents(edition, 1)
    client = await login_client(agent.email)
    ids = await leads_in(edition, 1, owner=agent.id)
    r = await client.post(
        "/api/v1/visitor-leads/assignments", json=body(edition, "MANUAL", ids, [agent.id])
    )
    assert r.status_code == 403
