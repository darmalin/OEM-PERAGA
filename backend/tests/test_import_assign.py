"""The edition's team and imports that share new leads among their callers (owner request 2026-10-25)."""

from collections import Counter

from sqlalchemy import func, select

from app.core.db import get_sessionmaker
from app.core.storage import MemoryStorage
from app.modules.telemarketing.models import LeadAssignmentHistory
from app.modules.visitors.models import VisitorLead
from tests.factories import RoleGrant, actor, make_edition, make_gate, make_user
from tests.test_imports import run, upload, xlsx


def rows(prefix: str, n: int) -> bytes:
    return xlsx(
        ["First Name", "Email"], [[f"{prefix} {i}", f"{prefix}-{i}@example.test"] for i in range(n)]
    )


async def owners(edition_id: object) -> Counter[object]:
    async with get_sessionmaker()() as session:
        result = await session.execute(
            select(VisitorLead.lead_owner_id, func.count())
            .where(VisitorLead.edition_id == edition_id)
            .group_by(VisitorLead.lead_owner_id)
        )
        return Counter({owner: n for owner, n in result.all()})


async def test_import_shares_new_leads_among_the_edition_teams_callers(
    storage: MemoryStorage,
) -> None:
    edition = await make_edition()
    gate = await make_gate(edition)
    _, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))
    team = (await admin.post("/api/v1/teams", json={"name": f"Sales {edition.id}"})).json()["id"]
    other_team = (await admin.post("/api/v1/teams", json={"name": f"Other {edition.id}"})).json()[
        "id"
    ]
    callers = [
        await make_user(RoleGrant("TELEMARKETING_AGENT", "OWNED", edition.id), teams=(team,))
        for _ in range(3)
    ]
    # In the team but not callers, or not active, or callers outside the team: no leads.
    await make_user(RoleGrant("GATE_STAFF", "GATE", edition.id, gate_id=gate.id), teams=(team,))
    await make_user(
        RoleGrant("TELEMARKETING_AGENT", "OWNED", edition.id), teams=(team,), active=False
    )
    await make_user(RoleGrant("TELEMARKETING_AGENT", "OWNED", edition.id), teams=(other_team,))
    base = f"/api/v1/editions/{edition.id}/team"
    recipients = "/api/v1/visitor-leads/imports/recipients"

    # No teams yet: nobody receives, and an auto-assign import is refused up front.
    assert (await admin.get(base)).json() == {"edition_id": str(edition.id), "team_id": None}
    assert (await admin.get(recipients, params={"edition_id": str(edition.id)})).json() == []
    r = await upload(admin, edition, rows("early", 2), auto_assign="true")
    assert r.status_code == 422 and "auto_assign" in r.json()["error"]["fields"]

    r = await admin.put(base, json={"team_id": other_team})
    assert r.status_code == 200, r.text
    r = await admin.put(base, json={"team_id": team})  # one team: this replaces the other
    assert r.status_code == 200, r.text
    assert (await admin.get(base)).json()["team_id"] == team
    r = await admin.get(recipients, params={"edition_id": str(edition.id)})
    assert {x["id"] for x in r.json()} == {str(c.id) for c in callers}

    # 7 leads over 3 callers: 3/2/2, every lead owned, history marked IMPORT.
    r = await upload(admin, edition, rows("first", 7), auto_assign="true")
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]
    assert await run(job_id) == "COMPLETED"
    job = (await admin.get(f"/api/v1/visitor-leads/imports/{job_id}")).json()
    assert job["auto_assign"] is True and job["assigned_count"] == 7
    assert sorted(a["count"] for a in job["assigned_to"]) == [2, 2, 3]
    assert {a["user_id"] for a in job["assigned_to"]} == {str(c.id) for c in callers}
    assert set((await owners(edition.id)).keys()) == {c.id for c in callers}

    # The next import carries on from the last caller: 9 leads end 3/3/3.
    r = await upload(admin, edition, rows("second", 2), auto_assign="true")
    assert await run(r.json()["job_id"]) == "COMPLETED"
    assert sorted((await owners(edition.id)).values()) == [3, 3, 3]
    async with get_sessionmaker()() as session:
        methods = await session.scalars(
            select(LeadAssignmentHistory.method)
            .where(LeadAssignmentHistory.edition_id == edition.id)
            .distinct()
        )
        assert list(methods) == ["IMPORT"]

    # Without the option, leads stay unassigned as before.
    r = await upload(admin, edition, rows("plain", 2))
    assert await run(r.json()["job_id"]) == "COMPLETED"
    assert (await owners(edition.id))[None] == 2


async def test_edition_teams_permissions_and_validation() -> None:
    edition = await make_edition()
    _, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))
    _, agent = await actor(RoleGrant("TELEMARKETING_AGENT", "OWNED", edition.id))
    other = await make_edition()
    base = f"/api/v1/editions/{edition.id}/team"
    unknown = "00000000-0000-4000-8000-000000000000"

    assert (await agent.put(base, json={"team_id": None})).status_code == 403
    assert (await agent.get(base)).status_code == 200
    r = await admin.put(base, json={"team_id": unknown})
    assert r.status_code == 422 and "team_id" in r.json()["error"]["fields"]
    assert (await admin.put(base, json={"team_id": None})).json()["team_id"] is None
    assert (await admin.get(f"/api/v1/editions/{other.id}/team")).status_code == 404
    r = await admin.post(
        "/api/v1/visitor-leads/assignments",
        json={"edition_id": str(edition.id), "method": "IMPORT", "lead_ids": [unknown],
              "agent_ids": [unknown]},
    )  # fmt: skip
    assert r.status_code == 422
