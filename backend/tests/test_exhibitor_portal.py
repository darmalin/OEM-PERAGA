"""Convert to exhibitor and the exhibitor portal sign-in (phase 4)."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.main import app
from app.modules.exhibitions.models import Edition
from app.modules.exhibitors.models import ExhibitorAccount, ExhibitorContract
from app.modules.exhibitors.service import portal_url
from tests.factories import RoleGrant, actor, make_edition
from tests.test_booths import add_booth, assign, opportunity
from tests.test_exhibitor_leads import SALES_ROLE, admin_for, create, sales_role

LEADS = "/api/v1/exhibitor-leads"
PORTAL = "/api/v1/portal"
PASSWORD = "booth-holder-secret-2027"


def portal_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def token_of(invitation: dict[str, Any]) -> str:
    return str(parse_qs(urlparse(invitation["url"]).query)["token"][0])


async def exhibitor(
    admin: AsyncClient, edition: Edition, email: str = "booth-001@example.test", code: str = "A01"
) -> dict[str, Any]:
    """Opportunity with a booth, converted. Returns the convert response."""
    booth = (await add_booth(admin, edition, code)).json()
    lead = await opportunity(admin, edition, email)
    lead = (await assign(admin, lead, booth["id"])).json()
    r = await admin.post(f"{LEADS}/{lead['id']}/convert", json={"version": lead["version"]})
    assert r.status_code == 200, r.text
    return dict(r.json())


async def accept(token: str, password: str = PASSWORD) -> tuple[AsyncClient, Any]:
    client = portal_client()
    r = await client.post(
        f"{PORTAL}/invitations/accept", json={"token": token, "password": password}
    )
    if r.status_code == 200:
        client.headers["X-CSRF-Token"] = r.json()["csrf_token"]
    return client, r


async def test_convert_creates_account_and_numbered_contract() -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    first = await exhibitor(admin, edition)
    assert first["lead"]["stage"] == "EXHIBITOR"
    assert first["lead"]["converted_at"] is not None
    assert first["contract_number"] == f"{edition.code}-C-0001"
    url = first["invitation"]["url"]
    assert url.startswith(f"{get_settings().public_base_url}/exhibitor/accept-invite?token=")

    second = await exhibitor(admin, edition, "booth-002@example.test", "A02")
    assert second["contract_number"] == f"{edition.code}-C-0002"

    async with get_sessionmaker()() as session:
        contract = await session.scalar(
            select(ExhibitorContract).where(
                ExhibitorContract.exhibitor_lead_id == uuid.UUID(first["lead"]["id"])
            )
        )
        account = await session.scalar(
            select(ExhibitorAccount).where(
                ExhibitorAccount.email_normalized == "booth-001@example.test"
            )
        )
    assert contract is not None and account is not None
    assert (contract.status, contract.booth_price, contract.total_amount) == (
        "DRAFT",
        Decimal("15000000.00"),
        Decimal("15000000.00"),
    )
    assert account.password_hash is None
    assert account.invite_token_hash != token_of(first["invitation"])  # only the hash is stored


async def test_convert_needs_an_opportunity_with_a_booth() -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    lead = (await create(admin, edition)).json()
    r = await admin.post(f"{LEADS}/{lead['id']}/convert", json={"version": lead["version"]})
    assert r.json()["error"]["code"] == "INVALID_STAGE_TRANSITION"
    lead = await opportunity(admin, edition, "booth-010@example.test")
    r = await admin.post(f"{LEADS}/{lead['id']}/convert", json={"version": lead["version"]})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "BOOTH_REQUIRED"

    await sales_role()
    _, sales = await actor(RoleGrant(SALES_ROLE, "EDITION", edition.id))
    r = await sales.post(f"{LEADS}/{lead['id']}/convert", json={"version": lead["version"]})
    assert r.status_code == 403


async def test_invitation_to_portal_session() -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    converted = await exhibitor(admin, edition)
    token = token_of(converted["invitation"])

    r = await portal_client().post(f"{PORTAL}/invitations/inspect", json={"token": token})
    assert r.json() == {"email": "booth-001@example.test", "purpose": "INVITATION"}

    _, r = await accept(token, "short")
    assert r.status_code == 422
    assert "password" in r.json()["error"]["fields"]

    client, r = await accept(token)
    assert r.status_code == 200, r.text
    assert get_settings().portal_session_cookie_name in r.cookies
    me = r.json()
    assert me["email"] == "booth-001@example.test"
    assert [
        (e["edition_id"], e["booth_code"], e["contract_number"], e["contract_status"])
        for e in me["exhibitors"]
    ] == [(str(edition.id), "A01", f"{edition.code}-C-0001", "DRAFT")]

    _, r = await accept(token)  # single use
    assert r.json()["error"]["code"] == "INVITATION_INVALID"

    assert (
        await client.post(f"{PORTAL}/auth/logout", headers={"X-CSRF-Token": "x"})
    ).status_code == 403
    assert (await client.post(f"{PORTAL}/auth/logout")).status_code == 204
    assert (await client.get(f"{PORTAL}/auth/me")).status_code == 401

    login = portal_client()
    r = await login.post(
        f"{PORTAL}/auth/login", json={"email": "BOOTH-001@example.test", "password": "wrong-pass"}
    )
    assert r.status_code == 401
    r = await login.post(
        f"{PORTAL}/auth/login", json={"email": "BOOTH-001@example.test", "password": PASSWORD}
    )
    assert r.status_code == 200, r.text
    assert (await login.get(f"{PORTAL}/auth/me")).status_code == 200

    r = await admin.get(f"{LEADS}/{converted['lead']['id']}/activity")
    assert "convert" in [e["action"] for e in r.json()]


async def test_staff_and_portal_sessions_do_not_mix() -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    portal, _ = await accept(token_of((await exhibitor(admin, edition))["invitation"]))
    assert (await portal.get("/api/v1/auth/me")).status_code == 401
    assert (await portal.get(LEADS, params={"edition_id": str(edition.id)})).status_code == 401
    assert (await admin.get(f"{PORTAL}/auth/me")).status_code == 401

    # The same session ID under the other cookie name is not a session there either.
    s = get_settings()
    stolen = portal.cookies[s.portal_session_cookie_name]
    staff_side = portal_client()
    staff_side.cookies.set(s.session_cookie_name, stolen)
    assert (await staff_side.get("/api/v1/auth/me")).status_code == 401


async def test_expired_and_reissued_invitations() -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    converted = await exhibitor(admin, edition)
    old = token_of(converted["invitation"])
    lead_id = converted["lead"]["id"]

    r = await admin.post(f"{LEADS}/{lead_id}/portal-invitation")
    assert r.status_code == 200, r.text
    new = token_of(r.json())
    assert (await accept(old))[1].json()["error"]["code"] == "INVITATION_INVALID"

    async with get_sessionmaker()() as session, session.begin():
        account = await session.scalar(select(ExhibitorAccount))
        assert account is not None
        account.invite_expires_at = datetime.now(UTC) - timedelta(minutes=1)
    assert (await accept(new))[1].json()["error"]["code"] == "INVITATION_INVALID"

    new = token_of((await admin.post(f"{LEADS}/{lead_id}/portal-invitation")).json())
    assert (await accept(new))[1].status_code == 200
    r = await admin.post(f"{LEADS}/{lead_id}/portal-invitation")
    assert r.json()["purpose"] == "PASSWORD_RESET"  # active account: the link resets


async def test_returning_exhibitor_reuses_the_account() -> None:
    edition, next_year = await make_edition(), await make_edition()
    admin = await admin_for(edition)
    portal, _ = await accept(token_of((await exhibitor(admin, edition))["invitation"]))

    _, super_admin = await actor(RoleGrant("SUPER_ADMIN"))
    again = await exhibitor(super_admin, next_year)
    assert again["invitation"] is None  # already has a password
    me = (await portal.get(f"{PORTAL}/auth/me")).json()
    assert {e["edition_id"] for e in me["exhibitors"]} == {str(edition.id), str(next_year.id)}


async def test_booth_move_reprices_a_draft_contract() -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    converted = await exhibitor(admin, edition)
    bigger = (await add_booth(admin, edition, "B01", price="20000000")).json()
    lead = (await assign(admin, converted["lead"], bigger["id"])).json()
    assert lead["booth_code"] == "B01"
    async with get_sessionmaker()() as session:
        contract = await session.scalar(select(ExhibitorContract))
    assert contract is not None
    assert (contract.booth_price, contract.total_amount) == (
        Decimal("20000000.00"),
        Decimal("20000000.00"),
    )


def test_portal_url_on_its_own_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "portal_base_url", "https://exhibitor.example.test/")
    assert (
        portal_url("accept-invite?token=t")
        == "https://exhibitor.example.test/accept-invite?token=t"
    )
