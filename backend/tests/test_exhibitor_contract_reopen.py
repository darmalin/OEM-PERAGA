"""Reopening a signed contract after a wrong PDF (known-gaps F8)."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import select

from app.core.audit import AuditLog
from app.core.db import get_sessionmaker
from app.core.storage import MemoryStorage
from tests.factories import RoleGrant, actor, make_edition
from tests.test_booths import add_booth, assign
from tests.test_exhibitor_contracts import PDF, contract_url, upload
from tests.test_exhibitor_leads import SALES_ROLE, admin_for, sales_role
from tests.test_exhibitor_payments import pay, review, signed


async def reopen(client: AsyncClient, lead_id: str, reason: str = "Wrong PDF uploaded") -> Any:
    contract = (await client.get(contract_url(lead_id, portal=False))).json()
    return await client.post(
        f"{contract_url(lead_id, portal=False)}/reopen",
        json={"reason": reason, "version": contract["version"]},
    )


async def test_reopen_and_sign_again(storage: MemoryStorage) -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    portal, lead_id = await signed(admin, edition)
    [(bucket, old_key)] = list(storage.objects)

    r = await reopen(admin, lead_id, "  Signed the 2026 draft by mistake  ")
    assert r.status_code == 200, r.text
    contract = r.json()
    assert (contract["status"], contract["signed_at"], contract["signed_file_name"]) == (
        "DRAFT",
        None,
        None,
    )
    assert contract["pic_name"] is not None  # the filled details stay

    # The exhibitor sees a Draft again, can edit it, and sign with the right file.
    url = contract_url(lead_id)
    mine = (await portal.get(url)).json()
    assert mine["status"] == "DRAFT"
    r = await portal.patch(url, json={"tax_id": "01.234.567.8-901.000", "version": mine["version"]})
    assert r.status_code == 200, r.text
    r = await upload(portal, url, r.json()["version"], data=PDF + b"% right one\n")
    assert r.json()["status"] == "SIGNED"
    assert len(storage.objects) == 2 and (bucket, old_key) in storage.objects  # old file kept

    async with get_sessionmaker()() as session:
        entry = await session.scalar(select(AuditLog).where(AuditLog.action == "reopen"))
    assert entry is not None
    assert entry.after is not None and entry.after["reason"] == "Signed the 2026 draft by mistake"
    assert entry.before is not None and entry.before["signed_file_key"] == old_key


async def test_reopened_contract_frees_the_booth(storage: MemoryStorage) -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    _, lead_id = await signed(admin, edition)
    bigger = (await add_booth(admin, edition, "B01", price="20000000")).json()
    lead = (await admin.get(f"/api/v1/exhibitor-leads/{lead_id}")).json()
    assert (await assign(admin, lead, bigger["id"])).json()["error"]["code"] == "CONTRACT_SIGNED"

    assert (await reopen(admin, lead_id)).status_code == 200
    lead = (await admin.get(f"/api/v1/exhibitor-leads/{lead_id}")).json()
    assert (await assign(admin, lead, bigger["id"])).status_code == 200
    contract = (await admin.get(contract_url(lead_id, portal=False))).json()
    assert contract["total_amount"] == "20000000.00"  # a Draft follows its booth again


async def test_blocked_by_payments(storage: MemoryStorage) -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    _, lead_id = await signed(admin, edition)

    pending = (await pay(admin, lead_id, "1000000")).json()
    r = await reopen(admin, lead_id)
    assert (r.status_code, r.json()["error"]["code"]) == (409, "CONTRACT_HAS_PAYMENTS")

    verified = (await review(admin, lead_id, pending, "VERIFIED")).json()
    assert verified["status"] == "VERIFIED"
    assert (await reopen(admin, lead_id)).json()["error"]["code"] == "CONTRACT_HAS_PAYMENTS"


async def test_rejected_payments_do_not_block(storage: MemoryStorage) -> None:
    # They were never taken against the total.
    edition = await make_edition()
    admin = await admin_for(edition)
    _, lead_id = await signed(admin, edition)
    rejected = (await pay(admin, lead_id, "500000")).json()
    await review(admin, lead_id, rejected, "REJECTED", notes="Bounced")
    assert (await reopen(admin, lead_id)).status_code == 200


async def test_rules_and_permissions(storage: MemoryStorage) -> None:
    edition = await make_edition()
    await sales_role()
    admin = await admin_for(edition)
    portal, lead_id = await signed(admin, edition)

    assert (await reopen(admin, lead_id, "   ")).status_code == 422
    r = await admin.post(
        f"{contract_url(lead_id, portal=False)}/reopen", json={"reason": "x", "version": 999}
    )
    assert r.status_code == 409  # stale version

    _, sales = await actor(RoleGrant(SALES_ROLE, "EDITION", edition.id))
    assert (await reopen(sales, lead_id)).status_code == 403  # exhibitor.invite only
    r = await portal.post(
        f"{contract_url(lead_id, portal=False)}/reopen", json={"reason": "x", "version": 1}
    )
    assert r.status_code == 401  # not a portal route

    assert (await reopen(admin, lead_id)).status_code == 200
    r = await reopen(admin, lead_id)
    assert (r.status_code, r.json()["error"]["code"]) == (409, "CONTRACT_NOT_SIGNED")
