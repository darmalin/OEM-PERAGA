"""Payment tagging against a signed contract (phase 6)."""

import asyncio
from datetime import date, timedelta
from typing import Any

from httpx import AsyncClient

from app.core.storage import MemoryStorage
from app.modules.exhibitions.models import Edition
from tests.factories import RoleGrant, actor, make_edition
from tests.test_exhibitor_contracts import FIELDS, contract_url, fill, portal_exhibitor, upload
from tests.test_exhibitor_leads import SALES_ROLE, admin_for, sales_role
from tests.test_exhibitor_portal import LEADS, PORTAL

PNG = b"\x89PNG\r\n\x1a\n rest of the image"


async def signed(admin: AsyncClient, edition: Edition) -> tuple[AsyncClient, str]:
    """Exhibitor with a SIGNED contract of 15,000,000. Returns (portal client, lead id)."""
    portal, lead_id = await portal_exhibitor(admin, edition)
    url = contract_url(lead_id)
    r = await upload(portal, url, (await fill(portal, url, **FIELDS))["version"])
    assert r.status_code == 200, r.text
    return portal, lead_id


def payments_url(lead_id: str) -> str:
    return f"{LEADS}/{lead_id}/payments"


async def pay(client: AsyncClient, lead_id: str, amount: str, **kw: Any) -> Any:
    body = {"amount": amount, "paid_on": date.today().isoformat(), "method": "BANK_TRANSFER"}
    return await client.post(payments_url(lead_id), json=body | kw)


async def review(
    client: AsyncClient, lead_id: str, payment: dict[str, Any], decision: str, **kw: Any
) -> Any:
    return await client.post(
        f"{payments_url(lead_id)}/{payment['id']}/review",
        json={"decision": decision, "version": payment["version"]} | kw,
    )


async def summary(client: AsyncClient, lead_id: str) -> dict[str, Any]:
    r = await client.get(payments_url(lead_id))
    assert r.status_code == 200, r.text
    return dict(r.json())


async def test_installments_to_paid(storage: MemoryStorage) -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    portal, lead_id = await signed(admin, edition)

    s = await summary(admin, lead_id)
    assert (s["total_amount"], s["verified_amount"], s["payment_state"]) == (
        "15000000.00",
        "0.00",
        "UNPAID",
    )

    r = await pay(admin, lead_id, "5000000", reference=" TRX-001 ", notes="DP 1/3")
    assert r.status_code == 201, r.text
    deposit = r.json()
    assert (deposit["status"], deposit["reference"], deposit["has_proof"]) == (
        "PENDING",
        "TRX-001",
        False,
    )
    s = await summary(admin, lead_id)
    assert (s["pending_amount"], s["payment_state"]) == ("5000000.00", "UNPAID")

    r = await review(admin, lead_id, deposit, "VERIFIED")
    assert r.status_code == 200, r.text
    assert r.json()["reviewed_at"] is not None
    s = await summary(admin, lead_id)
    assert (s["verified_amount"], s["outstanding_amount"], s["payment_state"]) == (
        "5000000.00",
        "10000000.00",
        "PARTIAL",
    )

    rest = (await pay(admin, lead_id, "10000000", method="CASH")).json()
    await review(admin, lead_id, rest, "VERIFIED")
    s = await summary(admin, lead_id)
    assert (s["outstanding_amount"], s["payment_state"]) == ("0.00", "PAID")
    assert [p["amount"] for p in s["items"]] == ["5000000.00", "10000000.00"]

    me = (await portal.get(f"{PORTAL}/auth/me")).json()
    assert me["exhibitors"][0]["payment_state"] == "PAID"
    mine = (await portal.get(f"{PORTAL}/exhibitors/{lead_id}/payments")).json()
    assert mine["payment_state"] == "PAID"
    assert "notes" not in mine["items"][0] and "reviewed_by" not in mine["items"][0]


async def test_payment_needs_a_signed_contract(storage: MemoryStorage) -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    portal, lead_id = await portal_exhibitor(admin, edition)
    r = await pay(admin, lead_id, "1000")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "CONTRACT_NOT_SIGNED"
    me = (await portal.get(f"{PORTAL}/auth/me")).json()
    assert me["exhibitors"][0]["payment_state"] is None


async def test_payments_never_exceed_the_total(storage: MemoryStorage) -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    _, lead_id = await signed(admin, edition)

    r = await pay(admin, lead_id, "15000000.01")
    assert r.json()["error"]["code"] == "PAYMENT_EXCEEDS_TOTAL"
    first = (await pay(admin, lead_id, "10000000")).json()
    r = await pay(admin, lead_id, "6000000")  # pending amounts count as well
    assert r.json()["error"]["code"] == "PAYMENT_EXCEEDS_TOTAL"
    assert "amount" in r.json()["error"]["fields"]

    r = await review(admin, lead_id, first, "REJECTED")
    assert r.status_code == 422
    assert "notes" in r.json()["error"]["fields"]
    r = await review(admin, lead_id, first, "REJECTED", notes="Transfer not received")
    assert r.status_code == 200, r.text
    assert (r.json()["status"], r.json()["notes"]) == ("REJECTED", "Transfer not received")
    assert (await pay(admin, lead_id, "15000000")).status_code == 201  # rejected is not counted

    r = await review(admin, lead_id, r.json(), "VERIFIED")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "PAYMENT_REVIEWED"


async def test_parallel_payments_stay_within_the_total(storage: MemoryStorage) -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    _, lead_id = await signed(admin, edition)
    _, second = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))
    results = await asyncio.gather(
        pay(admin, lead_id, "10000000"), pay(second, lead_id, "10000000")
    )
    assert sorted(r.status_code for r in results) == [201, 422]


async def test_payment_input_rules(storage: MemoryStorage) -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    _, lead_id = await signed(admin, edition)
    tomorrow = (date.today() + timedelta(days=2)).isoformat()
    r = await pay(admin, lead_id, "1000", paid_on=tomorrow)
    assert "paid_on" in r.json()["error"]["fields"]
    assert (await pay(admin, lead_id, "0")).status_code == 422
    assert (await pay(admin, lead_id, "1000", method="CRYPTO")).status_code == 422
    assert (await pay(admin, lead_id, "1000.001")).status_code == 422


async def test_proof_upload_and_download(storage: MemoryStorage) -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    _, lead_id = await signed(admin, edition)
    payment = (await pay(admin, lead_id, "1000000")).json()
    url = f"{payments_url(lead_id)}/{payment['id']}/proof"

    async def send(name: str, data: bytes, content_type: str, version: int) -> Any:
        return await admin.post(
            url, data={"version": str(version)}, files={"file": (name, data, content_type)}
        )

    r = await send("slip.gif", b"GIF89a", "image/gif", payment["version"])
    assert r.status_code == 422
    r = await send("slip.png", b"%PDF-1.7", "image/png", payment["version"])
    assert r.status_code == 422  # content does not match the extension
    assert (await admin.get(url)).status_code == 404

    r = await send("bukti transfer.PNG", PNG, "image/png", payment["version"])
    assert r.status_code == 200, r.text
    payment = r.json()
    assert payment["has_proof"] is True
    r = await admin.get(url)
    assert (r.status_code, r.content, r.headers["content-type"]) == (200, PNG, "image/png")
    assert f'filename="payment-{payment["id"]}.png"' in r.headers["content-disposition"]

    payment = (await review(admin, lead_id, payment, "VERIFIED")).json()
    r = await send("slip.png", PNG, "image/png", payment["version"])
    assert r.json()["error"]["code"] == "PAYMENT_REVIEWED"


async def test_permissions_and_scope(storage: MemoryStorage) -> None:
    edition, other = await make_edition(), await make_edition()
    await sales_role()
    admin = await admin_for(edition)
    portal, lead_id = await signed(admin, edition)
    payment = (await pay(admin, lead_id, "1000000")).json()

    # The sales role reads leads but cannot record or verify payments.
    _, sales = await actor(RoleGrant(SALES_ROLE, "EDITION", edition.id))
    assert (await summary(sales, lead_id))["pending_amount"] == "1000000.00"
    assert (await pay(sales, lead_id, "1000")).status_code == 403
    assert (await review(sales, lead_id, payment, "VERIFIED")).status_code == 403

    _, outsider = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", other.id))
    assert (await outsider.get(payments_url(lead_id))).status_code == 404
    assert (await pay(outsider, lead_id, "1000")).status_code == 404
    assert (await review(outsider, lead_id, payment, "VERIFIED")).status_code == 404

    # A payment id under another lead is not found.
    _, other_lead = await portal_exhibitor(admin, edition, "booth-002@example.test", "A02")
    assert (await review(admin, other_lead, payment, "VERIFIED")).status_code == 404

    # The portal cannot record, and cannot read another exhibitor's payments.
    assert (await portal.post(payments_url(lead_id), json={})).status_code == 401
    r = await portal.get(f"{PORTAL}/exhibitors/{other_lead}/payments")
    assert r.status_code == 404
