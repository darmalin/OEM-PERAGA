"""Payments of approved service orders (Phase 7 of docs/EXHIBITOR_ORDER_FORMS.md, decision O3).

Same tagging as the booth contract: staff record installments (PENDING) with optional proof, then
verify or reject each one; pending plus verified never exceed the order total. Rows live in
`exhibitor_payments` with `order_id` set instead of `contract_id`.
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import PurePosixPath
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core import audit
from app.core.authorization import AuthContext
from app.core.config import get_settings
from app.core.context import current_actor_id
from app.core.errors import Conflict, NotFound, ValidationFailed, check_version
from app.core.storage import get_storage, new_object_key
from app.modules.exhibitions import service as exhibitions_service
from app.modules.exhibitors.models import ExhibitorLead, ExhibitorPayment
from app.modules.exhibitors.rules import PaymentState, PaymentStatus, payment_state
from app.modules.exhibitors.schemas import (
    PaymentCreateIn,
    PaymentOut,
    PaymentReviewIn,
    PaymentsOut,
    PaymentTotals,
    PortalPaymentOut,
    PortalPaymentsOut,
)
from app.modules.orders import repository as repo
from app.modules.orders.models import ExhibitorOrder
from app.modules.orders.portal import check_file
from app.modules.orders.review import READ, _row_in_scope
from app.modules.orders.rules import OrderStatus
from app.modules.orders.schemas import OrderMoney, OrdersSummaryOut
from app.modules.visitors.rules import clean_text

RECORD = "exhibitor_payment.record"
VERIFY = "exhibitor_payment.verify"
ENTITY = "exhibitor_payment"
AUDIT_FIELDS = (
    "amount", "paid_on", "method", "reference", "status", "reviewed_by", "reviewed_at",
    "notes", "proof_file_key",
)  # fmt: skip
ZERO = Decimal("0.00")
PROOF_KINDS = (".pdf", ".jpg", ".jpeg", ".png")
PROOF_MAX_BYTES = 10 * 1024 * 1024
_MIME = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


def billable(order: ExhibitorOrder) -> bool:
    """Only an approved order that costs money is paid."""
    return order.status == OrderStatus.APPROVED and order.total > 0


def state_of(order: ExhibitorOrder, sums: dict[str, Decimal]) -> PaymentState | None:
    """UNPAID / PARTIAL / PAID for a billable order, None otherwise (nothing owed)."""
    if not billable(order):
        return None
    return payment_state(order.total, sums.get(PaymentStatus.VERIFIED, ZERO))


def _totals(order: ExhibitorOrder, sums: dict[str, Decimal]) -> PaymentTotals:
    verified = sums.get(PaymentStatus.VERIFIED, ZERO)
    total = order.total if billable(order) else ZERO
    return PaymentTotals(
        total_amount=total,
        currency=order.currency,
        verified_amount=verified,
        pending_amount=sums.get(PaymentStatus.PENDING, ZERO),
        outstanding_amount=max(total - verified, ZERO),
        payment_state=payment_state(total, verified),
    )


async def _sums(session: AsyncSession, order: ExhibitorOrder) -> dict[str, Decimal]:
    return (await repo.order_payment_sums(session, [order.id])).get(order.id, {})


def _payment_out(payment: ExhibitorPayment) -> PaymentOut:
    out = PaymentOut.model_validate(payment)
    out.has_proof = payment.proof_file_key is not None
    return out


async def _record(
    session: AsyncSession, payment: ExhibitorPayment, action: str, before: dict[str, Any] | None
) -> None:
    await audit.record(
        session,
        entity_type=ENTITY,
        entity_id=payment.id,
        action=action,
        before=before,
        after=audit.snapshot(payment, AUDIT_FIELDS) | {"order_id": payment.order_id},
        edition_id=payment.edition_id,
    )


async def _order(
    session: AsyncSession, ctx: AuthContext, order_id: uuid.UUID, permission: str, *, lock: bool
) -> ExhibitorOrder:
    """The order if its exhibitor is in the caller's scope for the permission. Locking the order
    row serializes payment changes of one order, as the contract row does for contracts."""
    await _row_in_scope(session, ctx, order_id, permission)
    order = await repo.get_order(session, order_id, for_update=lock)
    if order is None:
        raise NotFound("Order not found.")
    return order


async def _payment(
    session: AsyncSession, order: ExhibitorOrder, payment_id: uuid.UUID, *, lock: bool = False
) -> ExhibitorPayment:
    payment = await repo.order_payment(session, order.id, payment_id, for_update=lock)
    if payment is None:
        raise NotFound("Payment not found.")
    return payment


async def list_payments(
    session: AsyncSession, ctx: AuthContext, order_id: uuid.UUID
) -> PaymentsOut:
    order = await _order(session, ctx, order_id, READ, lock=False)
    items = [_payment_out(p) for p in await repo.order_payments(session, order.id)]
    return PaymentsOut(**_totals(order, await _sums(session, order)).model_dump(), items=items)


async def record_payment(
    session: AsyncSession, ctx: AuthContext, order_id: uuid.UUID, data: PaymentCreateIn
) -> PaymentOut:
    """A PENDING installment of an approved order. Never more than what is still owed."""
    order = await _order(session, ctx, order_id, RECORD, lock=True)
    edition = await exhibitions_service.ensure_writable(session, order.edition_id)
    if not billable(order):
        raise ValidationFailed(
            "Payments are recorded against an approved order that costs money.",
            code="ORDER_NOT_APPROVED",
        )
    if data.paid_on > datetime.now(ZoneInfo(edition.timezone)).date():
        raise ValidationFailed(fields={"paid_on": "Cannot be in the future."})
    sums = await _sums(session, order)
    open_amount = order.total - sums.get(PaymentStatus.VERIFIED, ZERO)
    open_amount -= sums.get(PaymentStatus.PENDING, ZERO)
    if data.amount > open_amount:
        raise ValidationFailed(
            "The payment is more than what is still owed.",
            code="PAYMENT_EXCEEDS_TOTAL",
            fields={"amount": f"At most {max(open_amount, ZERO)} {order.currency}."},
        )
    actor = current_actor_id()
    payment = ExhibitorPayment(
        edition_id=order.edition_id,
        order_id=order.id,
        amount=data.amount,
        paid_on=data.paid_on,
        method=data.method,
        reference=clean_text(data.reference),
        notes=clean_text(data.notes),
        status=PaymentStatus.PENDING,
        created_by=actor,
        updated_by=actor,
    )
    session.add(payment)
    await session.flush()
    await session.refresh(payment)
    await _record(session, payment, "record", None)
    return _payment_out(payment)


async def attach_proof(
    session: AsyncSession,
    ctx: AuthContext,
    order_id: uuid.UUID,
    payment_id: uuid.UUID,
    *,
    file_name: str,
    content_type: str | None,
    data: bytes,
    version: int,
) -> PaymentOut:
    """Transfer slip or receipt (PDF, JPG, PNG) of a PENDING payment; replaces an earlier one."""
    order = await _order(session, ctx, order_id, RECORD, lock=False)
    await exhibitions_service.ensure_writable(session, order.edition_id)
    payment = await _payment(session, order, payment_id, lock=True)
    check_version(payment.version, version)
    if payment.status != PaymentStatus.PENDING:
        raise Conflict("The payment is already reviewed.", code="PAYMENT_REVIEWED")
    ext = check_file(file_name, content_type, data, PROOF_KINDS, PROOF_MAX_BYTES)
    key = new_object_key(ext)
    await run_in_threadpool(
        get_storage().put, get_settings().s3_bucket_orders, key, data, _MIME[ext]
    )
    before = audit.snapshot(payment, AUDIT_FIELDS)
    payment.proof_file_key = key
    payment.updated_by = current_actor_id()
    await session.flush()
    await session.refresh(payment)
    await _record(session, payment, "attach_proof", before)
    return _payment_out(payment)


async def review_payment(
    session: AsyncSession,
    ctx: AuthContext,
    order_id: uuid.UUID,
    payment_id: uuid.UUID,
    data: PaymentReviewIn,
) -> PaymentOut:
    """Verify or reject a PENDING payment; a rejection needs a reason in notes."""
    order = await _order(session, ctx, order_id, VERIFY, lock=True)
    await exhibitions_service.ensure_writable(session, order.edition_id)
    payment = await _payment(session, order, payment_id, lock=True)
    check_version(payment.version, data.version)
    if payment.status != PaymentStatus.PENDING:
        raise Conflict("The payment is already reviewed.", code="PAYMENT_REVIEWED")
    notes = clean_text(data.notes)
    if data.decision == PaymentStatus.REJECTED and notes is None:
        raise ValidationFailed(fields={"notes": "Required when rejecting."})
    if data.decision == PaymentStatus.VERIFIED:
        verified = (await _sums(session, order)).get(PaymentStatus.VERIFIED, ZERO)
        if verified + payment.amount > order.total:
            raise ValidationFailed(
                "Verifying this payment would exceed the order total.",
                code="PAYMENT_EXCEEDS_TOTAL",
            )
    before = audit.snapshot(payment, AUDIT_FIELDS)
    payment.status = data.decision
    payment.reviewed_by = ctx.user.id
    payment.reviewed_at = datetime.now(UTC)
    if notes is not None:
        payment.notes = notes
    payment.updated_by = current_actor_id()
    await session.flush()
    await session.refresh(payment)
    await _record(
        session, payment, "verify" if data.decision == PaymentStatus.VERIFIED else "reject", before
    )
    return _payment_out(payment)


async def proof(
    session: AsyncSession, ctx: AuthContext, order_id: uuid.UUID, payment_id: uuid.UUID
) -> tuple[Iterator[bytes], str, str]:
    order = await _order(session, ctx, order_id, READ, lock=False)
    payment = await _payment(session, order, payment_id)
    if payment.proof_file_key is None:
        raise NotFound("The payment has no proof attached.")
    ext = PurePosixPath(payment.proof_file_key).suffix
    chunks = await run_in_threadpool(
        get_storage().stream, get_settings().s3_bucket_orders, payment.proof_file_key
    )
    return chunks, f"payment-{payment.id}{ext}", _MIME[ext]


async def portal_payments(
    session: AsyncSession, lead: ExhibitorLead, order_id: uuid.UUID
) -> PortalPaymentsOut:
    """What the exhibitor sees: totals and each payment, without internal notes or reviewer."""
    order = await repo.get_order(session, order_id)
    if order is None or order.exhibitor_lead_id != lead.id or order.status == OrderStatus.DRAFT:
        raise NotFound("Order not found.")
    items = [
        PortalPaymentOut.model_validate(p) for p in await repo.order_payments(session, order.id)
    ]
    return PortalPaymentsOut(
        **_totals(order, await _sums(session, order)).model_dump(), items=items
    )


async def summary(
    session: AsyncSession, ctx: AuthContext, edition_id: uuid.UUID
) -> OrdersSummaryOut:
    """Orders waiting for staff and the money of approved ones, per currency."""
    scope = ctx.scope_for(edition_id, READ)
    counts = await repo.status_counts(session, scope)
    orders = await repo.approved_orders(session, scope)
    sums = await repo.order_payment_sums(session, [o.id for o in orders])
    money: dict[str, OrderMoney] = {}
    for order in orders:
        m = money.setdefault(
            order.currency,
            OrderMoney(
                currency=order.currency,
                approved_orders=0,
                approved_value=ZERO,
                verified_amount=ZERO,
                pending_amount=ZERO,
                outstanding_amount=ZERO,
                paid_orders=0,
            ),
        )
        mine = sums.get(order.id, {})
        verified = mine.get(PaymentStatus.VERIFIED, ZERO)
        m.approved_orders += 1
        m.approved_value += order.total
        m.verified_amount += verified
        m.pending_amount += mine.get(PaymentStatus.PENDING, ZERO)
        m.outstanding_amount += max(order.total - verified, ZERO)
        m.paid_orders += int(verified >= order.total)
    return OrdersSummaryOut(
        waiting_for_review=counts.get(OrderStatus.SUBMITTED, 0),
        returned=counts.get(OrderStatus.RETURNED, 0),
        approved=counts.get(OrderStatus.APPROVED, 0),
        money=sorted(money.values(), key=lambda m: m.currency),
    )
