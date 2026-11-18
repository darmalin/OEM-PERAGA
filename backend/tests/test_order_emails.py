"""Emails when an exhibitor submits an order (orders.emails, owner request 2026-11-18)."""

import uuid
from typing import Any

from sqlalchemy import text

from app.core.db import get_sessionmaker
from app.core.email import MemorySender, get_email_sender
from app.modules.mail.rules import EmailKind
from app.modules.orders import emails
from app.modules.orders.tasks import send_order_email_event
from tests.factories import RoleGrant, actor
from tests.test_order_portal import setup


async def rows(sql: str, **params: Any) -> list[Any]:
    async with get_sessionmaker()() as session:
        return list((await session.execute(text(sql), params)).all())


async def test_submit_emails_the_exhibitor_and_the_sales_owner() -> None:
    s = await setup("orders@example.test")
    sales, _ = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", s.edition.id))
    async with get_sessionmaker()() as session:
        await session.execute(
            text("UPDATE exhibitor_leads SET lead_owner_id = :u WHERE id = :l"),
            {"u": sales.id, "l": uuid.UUID(s.lead_id)},
        )
        await session.commit()

    order = await s.draft()
    order = (
        await s.save(order, lines=[s.line("E-001", 2)], remarks="Install <before> move-in.")
    ).json()
    sent = (await s.submit(order)).json()
    assert sent["status"] == "SUBMITTED"

    jobs = await rows(
        "SELECT kind, recipient, edition_id FROM email_jobs ORDER BY kind",
    )
    assert [(k, r) for k, r, _ in jobs] == [
        (EmailKind.ORDER_ALERT, sales.email),
        (EmailKind.ORDER_RECEIVED, "orders@example.test"),
    ]
    assert all(e == s.edition.id for _, _, e in jobs)

    async with get_sessionmaker()() as session:
        mine = await emails.render(session, EmailKind.ORDER_RECEIVED, uuid.UUID(sent["id"]))
        alert = await emails.render(session, EmailKind.ORDER_ALERT, uuid.UUID(sent["id"]))
    assert mine is not None and alert is not None
    number = sent["order_number"]
    assert mine.subject.startswith(f"Order {number} received")
    assert "finance team sends you the invoice" in mine.text
    assert f"/e/{s.lead_id}/forms/04" in mine.text
    assert "Install &lt;before&gt; move-in." in mine.html  # escaped
    assert alert.subject.startswith(f"New order {number} from ")
    assert f"/app/exhibitor-orders/{sent['id']}" in alert.text

    # The worker renders and sends through the shared queue.
    (event_id,) = (
        await rows(
            "SELECT e.id FROM outbox_events e JOIN email_jobs j"
            " ON e.payload->>'email_job_id' = j.id::text WHERE j.kind = 'ORDER_RECEIVED'"
        )
    )[0]
    sender = get_email_sender()
    assert isinstance(sender, MemorySender)
    before = len(sender.outbox)
    assert await send_order_email_event(event_id) == "SENT"
    assert sender.outbox[before].to == "orders@example.test"
    assert sender.outbox[before].subject == mine.subject


async def test_no_owner_no_alert() -> None:
    s = await setup("solo@example.test")
    order = await s.draft()
    order = (await s.save(order, lines=[s.line("E-001", 1)])).json()
    assert (await s.submit(order)).status_code == 200
    assert [k for (k,) in await rows("SELECT kind FROM email_jobs")] == [EmailKind.ORDER_RECEIVED]
