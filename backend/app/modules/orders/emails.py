"""Emails when an exhibitor submits an order (owner request 2026-11-18).

Two emails per submit, through the shared queue (mail.service.queue_email, mail.tasks.deliver):
the exhibitor who submitted gets "Order received" with the full order; the sales person who owns
the lead and the team inbox in EMS_ORDER_ALERT_EMAIL get a short alert with a link to the desk,
one email per address.
Both are rendered at send time from the order as it is then, so a retry never mails stale data.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from html import escape
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.exhibitions import service as exhibitions_service
from app.modules.exhibitors.models import ExhibitorAccount, ExhibitorLead
from app.modules.exhibitors.service import portal_url
from app.modules.identity.models import User
from app.modules.mail import service as mail_service
from app.modules.mail.rules import EmailKind
from app.modules.orders import details
from app.modules.orders import repository as repo
from app.modules.orders.models import ExhibitorOrder, OrderForm

TASK = "orders.send_order_email"


async def queue_submitted(
    session: AsyncSession, lead: ExhibitorLead, order: ExhibitorOrder, account_id: uuid.UUID
) -> None:
    """Queue both emails in the submit's transaction; the worker sends them after commit."""
    account = await session.get(ExhibitorAccount, account_id)
    if account is not None:
        await mail_service.queue_email(
            session,
            kind=EmailKind.ORDER_RECEIVED,
            recipient=account.email,
            task=TASK,
            payload={"order_id": str(order.id)},
            edition_id=order.edition_id,
        )
    for recipient in await alert_recipients(session, lead):
        await mail_service.queue_email(
            session,
            kind=EmailKind.ORDER_ALERT,
            recipient=recipient,
            task=TASK,
            payload={"order_id": str(order.id)},
            edition_id=order.edition_id,
        )


async def alert_recipients(session: AsyncSession, lead: ExhibitorLead) -> list[str]:
    """The active lead owner, then the team inbox addresses, without repeats."""
    owner = await session.get(User, lead.lead_owner_id) if lead.lead_owner_id else None
    candidates = [owner.email] if owner is not None and owner.is_active else []
    candidates += get_settings().order_alert_email.split(",")
    found: list[str] = []
    for address in (a.strip() for a in candidates):
        if address and address.lower() not in (f.lower() for f in found):
            found.append(address)
    return found


@dataclass(frozen=True)
class Rendered:
    subject: str
    text: str
    html: str


def _money(amount: Decimal | None, currency: str) -> str:
    return "" if amount is None else f"{currency} {amount:,.0f}"


async def render(session: AsyncSession, kind: str, order_id: uuid.UUID) -> Rendered | None:
    """The email for one order; None when the order is gone (nothing to send)."""
    order = await session.get(ExhibitorOrder, order_id)
    if order is None or order.order_number is None:
        return None
    form = await session.get(OrderForm, order.form_id)
    lead = await session.get(ExhibitorLead, order.exhibitor_lead_id)
    edition = await exhibitions_service.get_edition_by_id(session, order.edition_id)
    if form is None or lead is None or edition is None:
        return None
    lines = list(await repo.order_lines(session, [order.id]))
    files = await repo.order_files(session, [order.id])
    form_name = f"{form.code.lstrip('0')}. {form.title}"
    rows = [
        (
            line.name + (f" ({line.size})" if line.size else ""),
            str(line.quantity),
            _money(line.unit_price, form.currency),
            _money(line.amount, form.currency),
        )
        for line in lines
    ]
    answers = details.summary(form.details_type, order.details or {})
    facts: list[tuple[str, str]] = [
        ("Order number", order.order_number),
        ("Order form", form_name),
        ("Exhibition", edition.name),
        ("Company", lead.company_name),
    ]
    if rows:
        facts.append(("Total", _money(order.total, form.currency)))
    extra: list[tuple[str, str]] = []
    if answers:
        extra.append(("Answers", answers))
    if files:
        extra.append(("Attachments", ", ".join(f.file_name for f in files)))
    if order.remarks:
        extra.append(("Notes / Remarks", order.remarks))

    if kind == EmailKind.ORDER_ALERT:
        link = f"{get_settings().public_base_url.rstrip('/')}/app/exhibitor-orders/{order.id}"
        subject = f"New order {order.order_number} from {lead.company_name}: {form.title}"
        intro = f"{lead.company_name} submitted an order on the exhibitor portal. Review it here:"
        steps: list[str] = []
        button = "Review the Order"
    else:
        link = portal_url(f"e/{lead.id}/forms/{form.code}")
        subject = f"Order {order.order_number} received: {form.title}"
        intro = (
            f"Dear {lead.contact_name}, thank you. We received your order for "
            f"{edition.name}. It is locked now; contact your sales person if anything must change."
        )
        steps = [
            "The organizer reviews your order and confirms the total.",
            "After approval, our finance team sends you the invoice.",
            "Once paid, everything you ordered is supplied onsite at the show.",
        ]
        button = "View Your Order"
    return Rendered(
        subject=subject[:300],
        text=_text(intro, facts, rows, extra, steps, link),
        html=_html(intro, facts, rows, extra, steps, link, button),
    )


def _text(
    intro: str,
    facts: list[tuple[str, str]],
    rows: list[tuple[str, str, str, str]],
    extra: list[tuple[str, str]],
    steps: list[str],
    link: str,
) -> str:
    out = [intro, ""]
    out += [f"{k}: {v}" for k, v in facts]
    if rows:
        out += ["", "Items:"] + [
            f"- {name} x {qty} @ {price} = {amount}" for name, qty, price, amount in rows
        ]
    if extra:
        out += [""] + [f"{k}: {v}" for k, v in extra]
    if steps:
        out += ["", "What happens next:"] + [f"{n}. {s}" for n, s in enumerate(steps, 1)]
    out += ["", link, "", "PERAGA Expo"]
    return "\n".join(out) + "\n"


def _html(
    intro: str,
    facts: list[tuple[str, str]],
    rows: list[tuple[str, str, str, str]],
    extra: list[tuple[str, str]],
    steps: list[str],
    link: str,
    button: str,
) -> str:
    """Inline styles only: mail clients drop style sheets. Colours of the portal."""
    cell = "padding:6px 8px;border-bottom:1px solid #e5e7eb;"
    parts = [
        '<div style="font-family:Arial,sans-serif;font-size:14px;line-height:1.5;color:#181818;'
        'max-width:640px;">',
        f"<p>{escape(intro)}</p>",
        '<table style="border-collapse:collapse;margin:12px 0;">',
        *(
            f'<tr><td style="padding:2px 16px 2px 0;color:#6b7280;">{escape(k)}</td>'
            f'<td style="padding:2px 0;font-weight:bold;">{escape(v)}</td></tr>'
            for k, v in facts
        ),
        "</table>",
    ]
    if rows:
        head = "".join(
            f'<th style="{cell}text-align:{a};background:#b80f0a;color:#fff;">{h}</th>'
            for h, a in (
                ("Item", "left"),
                ("Qty", "right"),
                ("Price", "right"),
                ("Amount", "right"),
            )
        )
        body = "".join(
            f'<tr><td style="{cell}">{escape(n)}</td><td style="{cell}text-align:right;">{q}</td>'
            f'<td style="{cell}text-align:right;">{escape(p)}</td>'
            f'<td style="{cell}text-align:right;">{escape(a)}</td></tr>'
            for n, q, p, a in rows
        )
        parts.append(
            f'<table style="border-collapse:collapse;width:100%;margin:8px 0 16px;">'
            f"<tr>{head}</tr>{body}</table>"
        )
    parts += [f"<p><b>{escape(k)}:</b> {escape(v).replace(chr(10), '<br>')}</p>" for k, v in extra]
    if steps:
        parts.append("<p><b>What happens next</b></p><ol>")
        parts += [f"<li>{escape(s)}</li>" for s in steps]
        parts.append("</ol>")
    parts += [
        f'<p style="margin:20px 0;"><a href="{escape(link)}" style="background:#b80f0a;color:#fff;'
        f'padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:bold;">'
        f"{escape(button)}</a></p>",
        '<p style="color:#6b7280;font-size:12px;">PERAGA Expo · Online Exhibitor Manual</p>',
        "</div>",
    ]
    return "".join(parts)


def payload_order_id(payload: dict[str, Any]) -> uuid.UUID:
    return uuid.UUID(payload["order_id"])
