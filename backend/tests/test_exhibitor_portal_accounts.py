"""Portal password reset links and account disable/enable (known-gaps F6, F7)."""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.core.audit import AuditLog
from app.core.db import get_sessionmaker
from tests.factories import RoleGrant, actor, make_edition
from tests.test_booths import add_booth, assign, opportunity
from tests.test_exhibitor_leads import SALES_ROLE, admin_for, sales_role
from tests.test_exhibitor_portal import (
    LEADS,
    PASSWORD,
    PORTAL,
    accept,
    exhibitor,
    portal_client,
    token_of,
)

NEW_PASSWORD = "booth-holder-new-2027"


async def login(email: str, password: str) -> Any:
    return await portal_client().post(
        f"{PORTAL}/auth/login", json={"email": email, "password": password}
    )


def account_url(lead_id: str) -> str:
    return f"{LEADS}/{lead_id}/portal-account"


async def test_password_reset_link() -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    converted = await exhibitor(admin, edition)
    lead_id = converted["lead"]["id"]
    old_session, _ = await accept(token_of(converted["invitation"]))

    r = await admin.post(f"{LEADS}/{lead_id}/portal-invitation")
    assert r.status_code == 200, r.text
    link = r.json()
    assert link["purpose"] == "PASSWORD_RESET"
    expires = datetime.fromisoformat(link["expires_at"])
    assert expires < datetime.now(UTC) + timedelta(hours=25)  # shorter than an invitation

    info = await portal_client().post(
        f"{PORTAL}/invitations/inspect", json={"token": token_of(link)}
    )
    assert info.json() == {"email": "booth-001@example.test", "purpose": "PASSWORD_RESET"}

    fresh, r = await accept(token_of(link), NEW_PASSWORD)
    assert r.status_code == 200, r.text
    assert (await old_session.get(f"{PORTAL}/auth/me")).status_code == 401  # other sessions end
    assert (await fresh.get(f"{PORTAL}/auth/me")).status_code == 200
    assert (await login("booth-001@example.test", PASSWORD)).status_code == 401
    assert (await login("booth-001@example.test", NEW_PASSWORD)).status_code == 200
    assert (await accept(token_of(link), "another-pass-2027"))[1].json()["error"][
        "code"
    ] == "INVITATION_INVALID"

    account = (await admin.get(account_url(lead_id))).json()
    assert (account["has_password"], account["link_expires_at"]) == (True, None)


async def test_disable_and_enable() -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    converted = await exhibitor(admin, edition)
    lead_id = converted["lead"]["id"]
    portal, _ = await accept(token_of(converted["invitation"]))
    account = (await admin.get(account_url(lead_id))).json()
    assert (account["is_active"], account["has_password"], account["email"]) == (
        True,
        True,
        "booth-001@example.test",
    )
    assert account["last_login_at"] is not None

    pending = token_of((await admin.post(f"{LEADS}/{lead_id}/portal-invitation")).json())
    r = await admin.put(account_url(lead_id), json={"is_active": False})
    assert r.status_code == 200, r.text
    disabled = r.json()
    assert (disabled["is_active"], disabled["link_expires_at"]) == (False, None)
    assert (await portal.get(f"{PORTAL}/auth/me")).status_code == 401
    assert (await login("booth-001@example.test", PASSWORD)).status_code == 401
    assert (await accept(pending))[1].json()["error"]["code"] == "INVITATION_INVALID"
    r = await admin.post(f"{LEADS}/{lead_id}/portal-invitation")
    assert r.json()["error"]["code"] == "ACCOUNT_INACTIVE"

    # The account is shared across editions: converting the same email elsewhere is refused too.
    _, super_admin = await actor(RoleGrant("SUPER_ADMIN"))
    other = await make_edition()
    booth = (await add_booth(super_admin, other)).json()
    lead = await opportunity(super_admin, other, "booth-001@example.test")
    lead = (await assign(super_admin, lead, booth["id"])).json()
    r = await super_admin.post(f"{LEADS}/{lead['id']}/convert", json={"version": lead["version"]})
    assert r.json()["error"]["code"] == "ACCOUNT_INACTIVE"

    r = await admin.put(account_url(lead_id), json={"is_active": True})
    assert r.json()["is_active"] is True
    assert (await login("booth-001@example.test", PASSWORD)).status_code == 200
    # No version: the sign-in above changed the account, and disabling still works.
    r = await admin.put(account_url(lead_id), json={"is_active": False})
    assert (r.status_code, r.json()["is_active"]) == (200, False)
    r = await admin.put(account_url(lead_id), json={"is_active": False})
    assert r.status_code == 200  # already disabled: nothing changes

    async with get_sessionmaker()() as session:
        actions = set(
            (
                await session.scalars(
                    select(AuditLog.action).where(AuditLog.entity_type == "exhibitor_account")
                )
            ).all()
        )
    assert {"deactivate_account", "activate_account"} <= actions


async def test_permissions() -> None:
    edition = await make_edition()
    await sales_role()
    admin = await admin_for(edition)
    converted = await exhibitor(admin, edition)
    lead_id = converted["lead"]["id"]
    _, sales = await actor(RoleGrant(SALES_ROLE, "EDITION", edition.id))
    account = await sales.get(account_url(lead_id))
    assert account.status_code == 200
    r = await sales.put(account_url(lead_id), json={"is_active": False})
    assert r.status_code == 403
    assert (await sales.post(f"{LEADS}/{lead_id}/portal-invitation")).status_code == 403

    lead = (
        await admin.post(
            LEADS,
            json={
                "edition_id": str(edition.id),
                "company_name": "Not Yet",
                "contact_name": "C",
                "email": "nope@example.test",
            },
        )
    ).json()
    r = await admin.get(account_url(lead["id"]))
    assert r.json()["error"]["code"] == "NOT_AN_EXHIBITOR"
