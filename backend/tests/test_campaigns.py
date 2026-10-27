"""Campaign links: admin management and the public form's safety rules."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.storage import MemoryStorage
from app.modules.campaigns.models import CampaignSubmission
from app.modules.campaigns.rules import form_ticket
from app.modules.campaigns.service import _key
from app.modules.exhibitions.models import Edition
from app.modules.mail.models import EmailJob
from app.modules.registrations.models import VisitorRegistration
from app.modules.visitors.models import VisitorLead
from tests.factories import RoleGrant, actor, make_edition, make_gate
from tests.test_exports import rows, run_exports, workbook

LINKS = "/api/v1/campaign-links"


def public(token: str) -> str:
    return f"/api/v1/public/campaigns/{token}"


def ticket(token: str, age: timedelta = timedelta(seconds=10)) -> str:
    """A ticket as the form got it `age` ago (real visitors take seconds to fill the form)."""
    return form_ticket(_key(), token, datetime.now(UTC) - age)


def body(token: str, **fields: Any) -> dict[str, Any]:
    return {"first_name": "Ana", "consent": True, "ticket": ticket(token), **fields}


async def make_link(admin: AsyncClient, edition: Edition, **fields: Any) -> Any:
    r = await admin.post(LINKS, json={"edition_id": str(edition.id), "name": "IG Oct", **fields})
    assert r.status_code == 201, r.text
    return r.json()


async def leads(edition: Edition) -> list[VisitorLead]:
    async with get_sessionmaker()() as session:
        rows = await session.scalars(
            select(VisitorLead).where(VisitorLead.edition_id == edition.id)
        )
        return list(rows.all())


async def outcomes(link_id: str) -> list[str]:
    async with get_sessionmaker()() as session:
        rows = await session.scalars(
            select(CampaignSubmission.outcome)
            .where(CampaignSubmission.campaign_link_id == link_id)
            .order_by(CampaignSubmission.created_at)
        )
        return list(rows.all())


async def test_admin_manages_links() -> None:
    edition = await make_edition()
    _, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))
    _, agent = await actor(RoleGrant("TELEMARKETING_AGENT", "OWNED", edition.id))
    link = await make_link(admin, edition, gtm_container_id=" gtm-abc1234 ")
    assert link["gtm_container_id"] == "GTM-ABC1234"
    assert link["state"] == "OPEN" and link["submission_count"] == 0
    assert link["url"].endswith(f"/r/{link['token']}") and len(link["token"]) == 12

    r = await admin.post(LINKS, json={"edition_id": str(edition.id), "name": "IG Oct"})
    assert r.status_code == 409  # one name per edition
    for bad in ({"gtm_container_id": "<script>"}, {"max_submissions": 0},
                {"starts_at": "2027-01-02T00:00:00Z", "ends_at": "2027-01-01T00:00:00Z"}):  # fmt: skip
        r = await admin.post(LINKS, json={"edition_id": str(edition.id), "name": "Bad", **bad})
        assert r.status_code == 422, bad

    # Agents can see links (to filter leads by campaign) but not change them.
    assert (await agent.get(LINKS, params={"edition_id": str(edition.id)})).status_code == 200
    r = await agent.post(LINKS, json={"edition_id": str(edition.id), "name": "Mine"})
    assert r.status_code == 403

    r = await admin.patch(f"{LINKS}/{link['id']}", json={"is_active": False, "version": 1})
    assert r.status_code == 200 and r.json()["state"] == "INACTIVE"
    r = await admin.patch(f"{LINKS}/{link['id']}", json={"name": "x", "version": 1})
    assert r.status_code == 409  # stale version

    r = await admin.get(f"{LINKS}/{link['id']}/qr.png")
    assert r.status_code == 200 and r.content.startswith(b"\x89PNG")
    assert r.headers["content-disposition"] == 'attachment; filename="qr-ig-oct.png"'

    old = link["token"]
    r = await admin.post(f"{LINKS}/{link['id']}/new-url")
    assert r.status_code == 200 and r.json()["token"] != old

    async with get_sessionmaker()() as session:
        actions = list(
            await session.scalars(
                text(
                    "SELECT action FROM audit_logs WHERE entity_type = 'campaign_link' "
                    "ORDER BY occurred_at"
                )
            )
        )
    assert actions == ["create", "update", "new_url"]

    other = await make_edition()
    _, other_admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", other.id))
    r = await other_admin.patch(f"{LINKS}/{link['id']}", json={"is_active": True, "version": 2})
    assert r.status_code == 404


async def test_public_form_registers_without_email_or_owner(client: AsyncClient) -> None:
    edition = await make_edition()
    _, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))
    _, platform = await actor(RoleGrant("SUPER_ADMIN"))
    r = await platform.post("/api/v1/lead-sources", json={"name": f"IG {edition.id}"})
    assert r.status_code == 201, r.text
    source = r.json()
    r = await admin.post(
        "/api/v1/visitor-custom-fields",
        json={"edition_id": str(edition.id), "field_key": "hall", "label": "Hall",
              "field_type": "select", "options": ["A", "B"], "required": True},
    )  # fmt: skip
    assert r.status_code == 201, r.text
    link = await make_link(
        admin, edition, lead_source_id=source["id"], gtm_container_id="GTM-X1Y2Z3"
    )
    token = link["token"]

    r = await client.get(public(token))
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    form = r.json()
    assert form["edition"]["name"] == edition.name and form["gtm_container_id"] == "GTM-X1Y2Z3"
    assert [f["key"] for f in form["custom_fields"]] == ["hall"]
    assert "IG Oct" not in r.text  # the campaign name stays internal

    r = await client.post(
        f"{public(token)}/registrations",
        json=body(token, email="Ana@Example.test", custom_fields={"hall": "A"},
                  utm_source="instagram", utm_campaign="promo-okt"),
    )  # fmt: skip
    assert r.status_code == 202, r.text
    assert r.json() == {"status": "RECEIVED"}
    (lead,) = await leads(edition)
    assert lead.source == "CAMPAIGN" and str(lead.campaign_link_id) == link["id"]
    assert str(lead.lead_source_id) == source["id"]
    assert (lead.utm_source, lead.utm_campaign, lead.utm_medium) == ("instagram", "promo-okt", None)
    assert lead.lead_owner_id is None and lead.custom_fields == {"hall": "A"}
    assert lead.registration_status == "REGISTERED" and lead.qr_status == "ACTIVE"
    async with get_sessionmaker()() as session:
        reg = await session.scalar(
            select(VisitorRegistration).where(VisitorRegistration.visitor_lead_id == lead.id)
        )
        assert reg is not None and reg.channel == "CAMPAIGN"
        assert await session.scalar(select(EmailJob.id)) is None  # no email is sent
    links = (await admin.get(LINKS, params={"edition_id": str(edition.id)})).json()
    assert links[0]["submission_count"] == 1
    assert await outcomes(link["id"]) == ["CREATED"]

    # Custom field rules apply to the public form too.
    r = await client.post(
        f"{public(token)}/registrations", json=body(token, email="b@example.test")
    )
    assert r.status_code == 422 and "custom_fields.hall" in str(r.json())


async def test_public_form_reveals_nothing_and_stops_bots(client: AsyncClient) -> None:
    edition = await make_edition()
    _, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))
    link = await make_link(admin, edition)
    token = link["token"]
    url = f"{public(token)}/registrations"

    first = await client.post(url, json=body(token, email="dup@example.test"))
    again = await client.post(url, json=body(token, email="DUP@example.test", first_name="Other"))
    honeypot = await client.post(url, json=body(token, email="bot1@example.test", contact_fax="1"))
    too_fast = await client.post(
        url, json={**body(token, email="bot2@example.test"), "ticket": ticket(token, timedelta(0))}
    )
    forged = await client.post(
        url, json={**body(token, email="bot3@example.test"), "ticket": "1.x"}
    )
    stale = await client.post(
        url, json={**body(token, email="bot4@example.test"), "ticket": ticket(token, timedelta(hours=3))}
    )  # fmt: skip
    answers = [r.json() for r in (first, again, honeypot, too_fast, forged, stale)]
    assert all(r.status_code == 202 for r in (first, again, honeypot, too_fast, forged, stale))
    assert all(a == answers[0] for a in answers)
    assert len(await leads(edition)) == 1
    assert await outcomes(link["id"]) == ["CREATED", "DUPLICATE", "BOT", "BOT", "BOT", "BOT"]

    # Fields that are not on the form are refused, not quietly applied.
    for extra in ({"lead_owner_id": "00000000-0000-4000-8000-000000000000"},
                  {"telemarketing_status": "ANSWER"}, {"source": "MANUAL"}):  # fmt: skip
        r = await client.post(url, json=body(token, email="x@example.test", **extra))
        assert r.status_code == 422, extra
    r = await client.post(url, json={**body(token, email="c@example.test"), "consent": False})
    assert r.status_code == 422
    r = await client.post(url, json=body(token))  # no email or phone
    assert r.status_code == 422


async def test_closed_links_answer_alike(client: AsyncClient) -> None:
    edition = await make_edition()
    _, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    cases = {
        "inactive": await make_link(admin, edition, name="Off", is_active=False),
        "not started": await make_link(admin, edition, name="Soon", starts_at=future),
        "ended": await make_link(admin, edition, name="Done", ends_at=past),
    }
    full = await make_link(admin, edition, name="Full", max_submissions=1)
    r = await client.post(
        f"{public(full['token'])}/registrations", json=body(full["token"], email="f@example.test")
    )
    assert r.status_code == 202
    cases["full"] = full
    for name, link in cases.items():
        r = await client.get(public(link["token"]))
        assert r.status_code == 404 and r.json()["error"]["code"] == "CAMPAIGN_CLOSED", name
    for token in ("doesnotexist", "A" * 200, "%3Cscript%3E"):
        r = await client.get(public(token))
        assert r.status_code == 404 and r.json()["error"]["code"] == "CAMPAIGN_CLOSED"

    # A new URL kills the old one; a closed edition closes its links.
    link = await make_link(admin, edition, name="Rotate")
    await admin.post(f"{LINKS}/{link['id']}/new-url")
    assert (await client.get(public(link["token"]))).status_code == 404
    open_link = await make_link(admin, edition, name="Open")
    async with get_sessionmaker()() as session, session.begin():
        row = await session.get(Edition, edition.id)
        assert row is not None
        row.status = "CLOSED"
    assert (await client.get(public(open_link["token"]))).status_code == 404


async def test_public_form_rate_limit(client: AsyncClient) -> None:
    edition = await make_edition()
    _, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))
    token = (await make_link(admin, edition))["token"]
    url = f"{public(token)}/registrations"
    for i in range(get_settings().campaign_submissions_per_ip_per_hour):
        r = await client.post(url, json=body(token, email=f"rl-{i:03d}@example.test"))
        assert r.status_code == 202
    r = await client.post(url, json=body(token, email="rl-last@example.test"))
    assert r.status_code == 429


async def test_leads_filter_by_campaign_and_utm(client: AsyncClient) -> None:
    edition = await make_edition()
    _, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))
    a = await make_link(admin, edition, name="A")
    b = await make_link(admin, edition, name="B")
    for link, email, utm in ((a, "a@example.test", "ig"), (b, "b@example.test", "wa")):
        r = await client.post(
            f"{public(link['token'])}/registrations",
            json=body(link["token"], email=email, utm_source=utm),
        )
        assert r.status_code == 202
    base = {"edition_id": str(edition.id)}
    r = await admin.get("/api/v1/visitor-leads", params={**base, "campaign_link_id": a["id"]})
    assert [i["email"] for i in r.json()["items"]] == ["a@example.test"]
    assert r.json()["items"][0]["campaign_link_id"] == a["id"]
    cond = '[{"field": "utm_source", "op": "equals", "value": "WA"}]'
    r = await admin.get("/api/v1/visitor-leads", params={**base, "filters": cond})
    assert [i["email"] for i in r.json()["items"]] == ["b@example.test"]


async def test_export_has_campaign_and_utm(client: AsyncClient, storage: MemoryStorage) -> None:
    edition = await make_edition()
    _, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))
    link = await make_link(admin, edition, name="Poster Hall A")
    r = await client.post(
        f"{public(link['token'])}/registrations",
        json=body(link["token"], email="poster@example.test", utm_medium="poster"),
    )
    assert r.status_code == 202
    r = await admin.post("/api/v1/exports/visitors", json={"edition_id": str(edition.id)})
    assert r.status_code == 202, r.text
    assert await run_exports() == ["COMPLETED"]
    ws = workbook(storage)["Visitor Leads"]
    header, row = rows(ws)[:2]
    data = dict(zip(header, row, strict=True))
    assert (data["Campaign"], data["UTM Medium"], data["UTM Source"]) == (
        "Poster Hall A", "poster", None,
    )  # fmt: skip


async def test_campaign_dashboard(client: AsyncClient) -> None:
    edition = await make_edition()
    gate = await make_gate(edition)
    _, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))
    a = await make_link(admin, edition, name="IG")
    b = await make_link(admin, edition, name="WA")

    # Two opens from one visitor on one day count once.
    assert (await client.get(public(a["token"]))).status_code == 200
    assert (await client.get(public(a["token"]))).status_code == 200
    assert (await client.get(public(b["token"]))).status_code == 200

    async def post(link: Any, **fields: Any) -> None:
        r = await client.post(
            f"{public(link['token'])}/registrations", json=body(link["token"], **fields)
        )
        assert r.status_code == 202

    await post(a, email="one@example.test", utm_source="instagram", utm_medium="story")
    await post(a, email="two@example.test", utm_source="instagram", utm_medium="feed")
    await post(a, email="ONE@example.test")  # duplicate
    await post(a, email="bot@example.test", contact_fax="x")  # bot
    await post(b, email="three@example.test", utm_source="wa")

    # Lead "one" is called, answered, valid, plans to attend, and is let in at the gate.
    async with get_sessionmaker()() as session, session.begin():
        lead = await session.scalar(
            select(VisitorLead).where(VisitorLead.email == "one@example.test")
        )
        assert lead is not None
        lead.call_attempts, lead.telemarketing_status = 1, "ANSWER"
        lead.is_valid_lead, lead.attend = True, "ATTEND"
        reg_id = await session.scalar(
            select(VisitorRegistration.id).where(VisitorRegistration.visitor_lead_id == lead.id)
        )
    r = await admin.post(
        "/api/v1/gate/overrides",
        json={"scan_event_id": str(uuid.uuid4()), "gate_id": str(gate.id),
              "registration_id": str(reg_id), "reason": "Dashboard test"},
    )  # fmt: skip
    assert r.status_code == 201, r.text

    url = "/api/v1/reports/campaigns"
    r = await admin.get(url, params={"edition_id": str(edition.id)})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["totals"] == {
        "views": 2,
        "registrations": 3,
        "duplicates": 1,
        "bots": 1,
        "conversion": 1.5,
    }
    assert sum(day["registrations"] for day in d["days"]) == 3
    assert d["funnel"] == {"registered": 3, "called": 1, "answered": 1, "valid": 1, "attend": 1,
                           "checked_in": 1}  # fmt: skip
    assert d["utm_source"][0] == {"key": "instagram", "count": 2}
    rows = {c["name"]: c for c in d["campaigns"]}
    assert (rows["IG"]["views"], rows["IG"]["registrations"], rows["IG"]["checked_in"]) == (1, 2, 1)
    assert (rows["WA"]["views"], rows["WA"]["registrations"], rows["WA"]["valid"]) == (1, 1, 0)

    one = (
        await admin.get(url, params={"edition_id": str(edition.id), "campaign_link_id": b["id"]})
    ).json()
    assert one["totals"]["registrations"] == 1 and [c["name"] for c in one["campaigns"]] == ["WA"]
    future = (datetime.now(UTC) + timedelta(days=2)).date().isoformat()
    empty = (
        await admin.get(url, params={"edition_id": str(edition.id), "date_from": future})
    ).json()
    assert empty["totals"]["registrations"] == 0 and empty["funnel"]["registered"] == 0

    # Who may open it: edition managers and telemarketing managers, not gate or agents.
    _, manager = await actor(RoleGrant("TELEMARKETING_MANAGER", "EDITION", edition.id))
    _, supervisor = await actor(RoleGrant("GATE_SUPERVISOR", "EDITION", edition.id))
    _, agent = await actor(RoleGrant("TELEMARKETING_AGENT", "OWNED", edition.id))
    assert (await manager.get(url, params={"edition_id": str(edition.id)})).status_code == 200
    assert (await supervisor.get(url, params={"edition_id": str(edition.id)})).status_code == 403
    assert (await agent.get(url, params={"edition_id": str(edition.id)})).status_code == 403
    other = await make_edition()
    r = await admin.get(url, params={"edition_id": str(other.id)})
    assert r.status_code == 404
