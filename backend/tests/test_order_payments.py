"""Payments of approved service orders (Phase 7 of docs/EXHIBITOR_ORDER_FORMS.md)."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.db import get_sessionmaker, new_id
from app.core.storage import MemoryStorage
from app.modules.exhibitors.models import ExhibitorPayment
from tests.factories import RoleGrant, actor
from tests.test_exhibitor_leads import SALES_ROLE, sales_role
from tests.test_order_portal import Setup, setup, today
from tests.test_order_review import sign

ORDERS = "/api/v1/exhibitor-orders"
PDF = b"%PDF-1.7\n%%EOF\n"


async def approved(s: Setup, **lines: int) -> dict[str, Any]:
    """An approved order that costs money (the contract is signed first)."""
    await sign(s)
    order = await s.draft()
    order = (await s.save(order, lines=[s.line(code, qty) for code, qty in lines.items()])).json()
    sent = (await s.submit(order)).json()
    staff = (await s.admin.get(f"{ORDERS}/{sent['id']}")).json()
    r = await s.admin.post(
        f"{ORDERS}/{sent['id']}/review", json={"decision": "APPROVED", "version": staff["version"]}
    )
    assert r.status_code == 200, r.text
    return dict(r.json())


async def pay(s: Setup, order: dict[str, Any], amount: str, **kw: Any) -> Any:
    body = {"amount": amount, "paid_on": str(today()), "method": "BANK_TRANSFER", **kw}
    return await s.admin.post(f"{ORDERS}/{order['id']}/payments", json=body)


async def review(
    s: Setup,
    order: dict[str, Any],
    payment: dict[str, Any],
    decision: str,
    notes: str | None = None,
) -> Any:
    return await s.admin.post(
        f"{ORDERS}/{order['id']}/payments/{payment['id']}/review",
        json={"decision": decision, "notes": notes, "version": payment["version"]},
    )


async def test_installments_until_paid() -> None:
    s = await setup()
    order = await approved(s, **{"E-001": 2})  # 200.00
    assert order["payment_state"] == "UNPAID"

    first = (await pay(s, order, "120", reference="TRX-1")).json()
    assert (first["status"], first["order_id"], first["contract_id"]) == (
        "PENDING",
        order["id"],
        None,
    )
    r = await pay(s, order, "100")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "PAYMENT_EXCEEDS_TOTAL"
    assert (await pay(s, order, "80", paid_on=str(today() + timedelta(days=1)))).status_code == 422
    second = (await pay(s, order, "80")).json()

    r = await s.admin.get(f"{ORDERS}/{order['id']}/payments")
    body = r.json()
    assert (body["total_amount"], body["pending_amount"], body["payment_state"]) == (
        "200.00",
        "200.00",
        "UNPAID",
    )
    assert len(body["items"]) == 2

    assert (await review(s, order, first, "VERIFIED")).status_code == 200
    rows = (await s.admin.get(ORDERS, params={"edition_id": str(s.edition.id)})).json()["items"]
    assert rows[0]["payment_state"] == "PARTIAL"
    assert (await review(s, order, second, "VERIFIED")).status_code == 200
    assert (await s.admin.get(f"{ORDERS}/{order['id']}")).json()["payment_state"] == "PAID"
    assert (await s.admin.get(f"{ORDERS}/{order['id']}/payments")).json()[
        "outstanding_amount"
    ] == "0.00"

    # The exhibitor sees the order paid, and the payments without internal notes.
    assert (await s.detail())["sent_orders"][0]["payment_state"] == "PAID"
    r = await s.portal.get(s.url(f"/orders/{order['id']}/payments"))
    assert r.status_code == 200, r.text
    assert [p["status"] for p in r.json()["items"]] == ["VERIFIED", "VERIFIED"]
    assert "notes" not in r.json()["items"][0]


async def test_only_approved_orders_that_cost_money() -> None:
    s = await setup()
    await sign(s)
    order = (await s.save(await s.draft(), lines=[s.line("E-001", 1)])).json()
    sent = (await s.submit(order)).json()
    r = await pay(s, sent, "10")
    assert r.json()["error"]["code"] == "ORDER_NOT_APPROVED"
    assert (await s.admin.get(f"{ORDERS}/{sent['id']}")).json()["payment_state"] is None


async def test_reject_and_review_rules() -> None:
    s = await setup()
    order = await approved(s, **{"E-002": 2})  # 100.00
    payment = (await pay(s, order, "100")).json()
    r = await review(s, order, payment, "REJECTED")
    assert r.status_code == 422
    assert "notes" in r.json()["error"]["fields"]
    rejected = (await review(s, order, payment, "REJECTED", "Wrong account")).json()
    assert (rejected["status"], rejected["notes"]) == ("REJECTED", "Wrong account")
    assert (await review(s, order, rejected, "VERIFIED")).json()["error"][
        "code"
    ] == "PAYMENT_REVIEWED"
    # A rejected payment frees its amount again.
    assert (await pay(s, order, "100")).status_code == 201


async def test_proof(storage: MemoryStorage) -> None:
    s = await setup()
    order = await approved(s, **{"E-001": 1})
    payment = (await pay(s, order, "100")).json()
    url = f"{ORDERS}/{order['id']}/payments/{payment['id']}/proof"
    r = await s.admin.post(
        url,
        data={"version": str(payment["version"])},
        files={"file": ("slip.pdf", PDF, "application/pdf")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["has_proof"] is True
    assert (await s.admin.get(url)).content == PDF
    r = await s.admin.post(
        url,
        data={"version": str(r.json()["version"])},
        files={"file": ("slip.gif", b"GIF89a", "image/gif")},
    )
    assert r.status_code == 422


async def test_cancel_needs_no_open_payments() -> None:
    s = await setup()
    order = await approved(s, **{"E-001": 1})
    payment = (await pay(s, order, "50")).json()
    current = (await s.admin.get(f"{ORDERS}/{order['id']}")).json()
    r = await s.admin.post(
        f"{ORDERS}/{order['id']}/cancel",
        json={"reason": "Not needed", "version": current["version"]},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ORDER_HAS_PAYMENTS"
    await review(s, order, payment, "REJECTED", "Refunded by bank")
    r = await s.admin.post(
        f"{ORDERS}/{order['id']}/cancel",
        json={"reason": "Not needed", "version": current["version"]},
    )
    assert r.status_code == 200, r.text


async def test_contract_payments_do_not_mix_with_order_payments() -> None:
    s = await setup()
    order = await approved(s, **{"E-001": 2})
    await pay(s, order, "200")
    contract = (await s.admin.get(f"/api/v1/exhibitor-leads/{s.lead_id}/payments")).json()
    assert (contract["items"], contract["pending_amount"]) == ([], "0.00")
    pipeline = (
        await s.admin.get(
            "/api/v1/exhibitor-leads/pipeline", params={"edition_id": str(s.edition.id)}
        )
    ).json()
    assert all(m["pending_amount"] == "0.00" for m in pipeline["money"])
    # And the other way: a contract payment is not an order payment.
    r = await s.admin.post(
        f"/api/v1/exhibitor-leads/{s.lead_id}/payments",
        json={"amount": "1000", "paid_on": str(today()), "method": "CASH"},
    )
    assert r.status_code == 201, r.text
    assert (await s.admin.get(f"{ORDERS}/{order['id']}/payments")).json()[
        "pending_amount"
    ] == "200.00"


async def test_access() -> None:
    s = await setup()
    order = await approved(s, **{"E-001": 1})
    await sales_role()
    _, sales = await actor(RoleGrant(SALES_ROLE, "EDITION", s.edition.id))
    r = await sales.post(
        f"{ORDERS}/{order['id']}/payments",
        json={"amount": "1", "paid_on": str(today()), "method": "CASH"},
    )
    assert r.status_code == 403
    assert (await sales.get(f"{ORDERS}/{order['id']}/payments")).status_code == 200
    other = await setup("booth-002@example.test")
    assert (await other.admin.get(f"{ORDERS}/{order['id']}/payments")).status_code == 404
    assert (await other.portal.get(other.url(f"/orders/{order['id']}/payments"))).status_code == 404


async def test_a_payment_has_exactly_one_target() -> None:
    s = await setup()
    order = await approved(s, **{"E-001": 1})
    contract = (await s.admin.get(f"/api/v1/exhibitor-leads/{s.lead_id}/contract")).json()
    for kw in ({}, {"order_id": order["id"], "contract_id": contract["id"]}):
        with pytest.raises(IntegrityError, match="one_target"):
            async with get_sessionmaker()() as session, session.begin():
                session.add(
                    ExhibitorPayment(
                        id=new_id(),
                        edition_id=s.edition.id,
                        amount=Decimal("1"),
                        paid_on=date.today(),
                        method="CASH",
                        status="PENDING",
                        **kw,
                    )
                )
                await session.flush()


async def test_summary() -> None:
    s = await setup()
    order = await approved(s, **{"E-001": 2})  # 200.00
    payment = (await pay(s, order, "150")).json()
    await review(s, order, payment, "VERIFIED")
    await pay(s, order, "50")
    second = (await s.save(await s.draft(), lines=[s.line("E-002", 1)])).json()
    await s.submit(second)
    r = await s.admin.get(f"{ORDERS}/summary", params={"edition_id": str(s.edition.id)})
    assert r.status_code == 200, r.text
    assert r.json() == {
        "waiting_for_review": 1,
        "returned": 0,
        "approved": 1,
        "money": [
            {
                "currency": "IDR",
                "approved_orders": 1,
                "approved_value": "200.00",
                "verified_amount": "150.00",
                "pending_amount": "50.00",
                "outstanding_amount": "50.00",
                "paid_orders": 0,
            }
        ],
    }
