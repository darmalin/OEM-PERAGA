import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from httpx import AsyncClient

from app.core.db import get_sessionmaker
from app.modules.exhibitions.models import Edition
from app.modules.identity.models import Team, User
from app.modules.reporting.service import local_window
from app.modules.telemarketing.models import VisitorFollowup
from app.modules.visitors.models import VisitorLead
from tests.factories import RoleGrant, actor, login_client, make_edition, make_user
from tests.test_gate import activated_device, create_gate, registered_hash, scan

REPORT = "/api/v1/reports/visitors"


def test_local_window_is_half_open_in_edition_time() -> None:
    start, end = local_window(date(2027, 3, 10), date(2027, 3, 11), "Asia/Jakarta")
    assert start == datetime(2027, 3, 9, 17, 0, tzinfo=UTC)
    assert end == datetime(2027, 3, 11, 17, 0, tzinfo=UTC)
    assert local_window(None, None, "UTC") == (None, None)


async def make_team() -> uuid.UUID:
    async with get_sessionmaker()() as session, session.begin():
        team = Team(name=f"Team {uuid.uuid4().hex[:8]}")
        session.add(team)
    return team.id


async def lead(edition: Edition, owner: uuid.UUID | None = None, **fields: Any) -> str:
    email = f"{uuid.uuid4().hex[:12]}@example.test"
    async with get_sessionmaker()() as session, session.begin():
        row = VisitorLead(
            edition_id=edition.id,
            registration_code=f"R{uuid.uuid4().hex[:10]}",
            first_name="Visitor",
            email=email,
            email_normalized=email,
            source=fields.pop("source", "MANUAL"),
            lead_owner_id=owner,
            custom_fields={},
            **fields,
        )
        session.add(row)
    return str(row.id)


async def report(client: AsyncClient, edition: Edition, name: str, **params: Any) -> Any:
    r = await client.get(REPORT, params={"edition_id": str(edition.id), "report": name, **params})
    assert r.status_code == 200, r.text
    return r.json()


class World:
    """Edition with a team agent (2 leads), an outside agent (1 lead), and 1 unassigned lead."""

    edition: Edition
    admin: AsyncClient
    team_agent: User
    team_agent_client: AsyncClient
    other_agent: User
    manager: AsyncClient
    leads: list[str]


async def world() -> World:
    w = World()
    w.edition = await make_edition()
    _, w.admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", w.edition.id))
    team = await make_team()
    w.team_agent = await make_user(
        RoleGrant("TELEMARKETING_AGENT", "OWNED", w.edition.id), teams=(team,)
    )
    w.team_agent_client = await login_client(w.team_agent.email)
    w.other_agent = await make_user(RoleGrant("TELEMARKETING_AGENT", "OWNED", w.edition.id))
    _, w.manager = await actor(
        RoleGrant("TELEMARKETING_MANAGER", "TEAM", w.edition.id, team_id=team)
    )
    w.leads = [
        await lead(w.edition, w.team_agent.id, source="EXCEL", country="VN", is_valid_lead=True),
        await lead(w.edition, w.team_agent.id, country="VN", attend="ATTEND_SOURCING"),
        await lead(w.edition, w.other_agent.id, is_invalid=True, b2b_matching=True),
        await lead(w.edition, None, buyer_type="B_SIDE"),
    ]
    return w


async def test_leads_report_and_scope() -> None:
    w = await world()
    full = await report(w.admin, w.edition, "LEADS")
    assert (full["total"], full["new"], full["assigned"], full["unassigned"]) == (4, 4, 3, 1)
    assert {c["key"]: c["count"] for c in full["by_source"]} == {"MANUAL": 3, "EXCEL": 1}
    assert {c["key"]: c["count"] for c in full["by_country"]} == {"VN": 2, None: 2}

    team = await report(w.manager, w.edition, "LEADS")
    assert (team["total"], team["assigned"], team["unassigned"]) == (2, 2, 0)

    filtered = await report(w.admin, w.edition, "LEADS", source="EXCEL")
    assert filtered["total"] == 1


async def test_verification_report() -> None:
    w = await world()
    r = await report(w.admin, w.edition, "VERIFICATION")
    assert (r["valid"], r["invalid"], r["undecided"], r["b2b_matching"]) == (1, 1, 2, 1)
    assert {c["key"]: c["count"] for c in r["by_attend"]} == {"ATTEND_SOURCING": 1, None: 3}
    assert {c["key"]: c["count"] for c in r["by_buyer_type"]} == {"B_SIDE": 1, None: 3}


async def test_telemarketing_and_agents_reports() -> None:
    w = await world()
    calls = (
        (w.leads[0], "ANSWER", {"lead_quality": "VALID", "attend": "ATTEND"}),
        (w.leads[1], "NO_ANSWER", {"lead_quality": "UNDECIDED"}),
    )
    for lead_id, result, verification in calls:
        r = await w.team_agent_client.post(
            f"/api/v1/visitor-leads/{lead_id}/calls",
            json={"call_result": result, "verification": verification},
        )
        assert r.status_code == 201, r.text
    now = datetime.now(UTC)
    async with get_sessionmaker()() as session, session.begin():
        for due, status in ((now - timedelta(days=2), "OPEN"), (now - timedelta(days=3), "DONE")):
            session.add(
                VisitorFollowup(
                    edition_id=w.edition.id,
                    visitor_lead_id=uuid.UUID(w.leads[0]),
                    assigned_to=w.team_agent.id,
                    due_at=due,
                    status=status,
                )
            )
    tm = await report(w.admin, w.edition, "TELEMARKETING")
    assert (tm["attempts"], tm["answered"], tm["answer_rate"]) == (2, 1, 0.5)
    assert (tm["followups_open"], tm["followups_overdue"]) == (1, 1)
    statuses = {c["key"]: c["count"] for c in tm["leads_by_status"]}
    assert statuses == {"ANSWER": 1, "NO_ANSWER": 1, "NEW": 2}

    tomorrow = (datetime.now(ZoneInfo(w.edition.timezone)) + timedelta(days=1)).date()
    none = await report(w.admin, w.edition, "TELEMARKETING", date_from=str(tomorrow))
    assert (none["attempts"], none["answer_rate"]) == (0, None)

    agents = (await report(w.admin, w.edition, "AGENTS"))["agents"]
    by_id = {a["agent_id"]: a for a in agents}
    mine = by_id[str(w.team_agent.id)]
    assert (mine["leads_owned"], mine["attempts"], mine["answered"]) == (2, 2, 1)
    assert (mine["followups_total"], mine["followups_done"], mine["followup_completion"]) == (
        2,
        1,
        0.5,
    )
    assert by_id[str(w.other_agent.id)]["leads_owned"] == 1

    team_view = (await report(w.manager, w.edition, "AGENTS"))["agents"]
    assert [a["agent_id"] for a in team_view] == [str(w.team_agent.id)]


async def test_registration_report() -> None:
    w = await world()
    for lead_id, send in ((w.leads[0], True), (w.leads[1], False)):
        r = await w.admin.post(
            "/api/v1/visitor-registrations",
            json={"visitor_lead_id": lead_id, "send_email": send},
            headers={"Idempotency-Key": uuid.uuid4().hex},
        )
        assert r.status_code == 201
    r = await report(w.admin, w.edition, "REGISTRATION")
    assert (r["registered"], r["not_registered"], r["qr_active"], r["qr_revoked"]) == (2, 2, 2, 0)
    assert r["by_channel"] == [{"key": "ADMIN", "count": 2}]
    assert r["emails_by_status"] == [{"key": "QUEUED", "count": 1}]

    emails = await report(w.admin, w.edition, "EMAILS")
    assert (emails["total"], emails["by_status"]) == (1, [{"key": "QUEUED", "count": 1}])


async def test_attendance_and_gate_reports() -> None:
    edition = await make_edition()
    _, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))
    gate_id = await create_gate(admin, edition)
    _, device = await activated_device(admin, gate_id)
    v1 = await registered_hash(admin, edition, 1)
    v2 = await registered_hash(admin, edition, 2)
    for token_hash in (v1, v1, v2, "a" * 64):
        await scan(device, token_hash)

    att = await report(admin, edition, "ATTENDANCE")
    assert (
        att["total_scans"],
        att["valid_entries"],
        att["first_entries"],
        att["repeat_entries"],
        att["rejected"],
        att["unique_event_visitors"],
    ) == (4, 3, 2, 1, 1, 2)
    (day,) = att["by_day"]
    assert (day["unique_visitors"], day["first_entries"], day["repeat_entries"]) == (2, 2, 1)

    gates = await report(admin, edition, "GATES")
    (row,) = gates["by_gate"]
    assert (row["gate_code"], row["total_scans"], row["valid_entries"], row["rejected"]) == (
        "A",
        4,
        3,
        1,
    )
    assert sum(h["total_scans"] for h in gates["by_hour"]) == 4

    # A gate with no scans still appears with zeros.
    await create_gate(admin, edition, "B")
    gates = await report(admin, edition, "GATES")
    assert [(g["gate_code"], g["total_scans"]) for g in gates["by_gate"]] == [("A", 4), ("B", 0)]


async def test_edition_reports_need_edition_scope_and_permission() -> None:
    w = await world()
    for name in ("IMPORTS", "EMAILS"):
        r = await w.manager.get(REPORT, params={"edition_id": str(w.edition.id), "report": name})
        assert r.status_code == 403
    imports = await report(w.admin, w.edition, "IMPORTS")
    assert (imports["jobs"], imports["processed"]) == (0, 0)

    r = await w.team_agent_client.get(
        REPORT, params={"edition_id": str(w.edition.id), "report": "LEADS"}
    )
    assert r.status_code == 403  # agents have no report.view
    other = await make_edition()
    r = await w.admin.get(REPORT, params={"edition_id": str(other.id), "report": "LEADS"})
    assert r.status_code == 404
    bad = await w.admin.get(
        REPORT,
        params={
            "edition_id": str(w.edition.id),
            "report": "LEADS",
            "date_from": "2027-03-12",
            "date_to": "2027-03-10",
        },
    )
    assert bad.status_code == 422
