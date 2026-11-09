"""Staff review of exhibitor orders (Phase 4 of docs/EXHIBITOR_ORDER_FORMS.md).

Orders are read with exhibitor_lead.read and changed with exhibitor_order.review, both within the
caller's lead scope (edition, team, or own leads), like the rest of the exhibitor pages.
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from starlette.concurrency import run_in_threadpool

from app.core import audit
from app.core.authorization import AuthContext, Scope
from app.core.config import get_settings
from app.core.context import current_actor_id
from app.core.errors import Conflict, NotFound, ValidationFailed, check_version
from app.core.excel import write_workbook
from app.core.pagination import Page
from app.core.storage import get_storage
from app.modules.exhibitions import service as exhibitions_service
from app.modules.exhibitors import repository as exhibitors_repo
from app.modules.exhibitors.rules import ContractStatus
from app.modules.identity import repository as identity_repo
from app.modules.orders import repository as repo
from app.modules.orders.models import ExhibitorOrder
from app.modules.orders.portal import AUDIT_FIELDS, ENTITY, file_out, line_out
from app.modules.orders.rules import (
    CENT,
    OrderStatus,
    PricePeriod,
    all_priced,
    approval_needs_signed_contract,
    can_move,
    form_progress,
    line_amount,
    order_total,
)
from app.modules.orders.schemas import (
    LeadFormProgressOut,
    LeadOrdersOut,
    LinePriceIn,
    OrderCancelIn,
    OrderExportParams,
    OrderReviewIn,
    StaffOrderListParams,
    StaffOrderOut,
    StaffOrderRowOut,
)
from app.modules.visitors.rules import clean_text

READ = "exhibitor_lead.read"
REVIEW = "exhibitor_order.review"
_MIME = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


def _scope(ctx: AuthContext, edition_id: uuid.UUID, permission: str) -> Scope:
    return ctx.scope_for(edition_id, permission)


async def _edition_of(session: AsyncSession, order_id: uuid.UUID) -> uuid.UUID:
    order = await repo.get_order(session, order_id)
    if order is None or order.status == OrderStatus.DRAFT:
        raise NotFound("Order not found.")
    return order.edition_id


async def _row_in_scope(
    session: AsyncSession, ctx: AuthContext, order_id: uuid.UUID, permission: str
) -> repo.StaffOrderRow:
    """The order if its exhibitor is in the caller's scope for the permission, else 404."""
    edition_id = await _edition_of(session, order_id)
    try:
        scope = _scope(ctx, edition_id, permission)
    except NotFound as e:
        raise NotFound("Order not found.") from e
    row = await repo.staff_order(session, scope, order_id)
    if row is None:
        raise NotFound("Order not found.")
    return row


def _row_out(row: repo.StaffOrderRow) -> StaffOrderRowOut:
    order, code, title, company, booth_id, booth_code, contract_status, unpriced = row
    status = OrderStatus(order.status)
    signed = contract_status == ContractStatus.SIGNED
    costs_money = order.total > 0 or unpriced > 0
    return StaffOrderRowOut(
        id=order.id,
        order_number=order.order_number,
        status=status,
        form_id=order.form_id,
        form_code=code,
        form_title=title,
        exhibitor_lead_id=order.exhibitor_lead_id,
        company_name=company,
        booth_code=booth_code,
        total=order.total,
        currency=order.currency,
        unpriced_lines=unpriced,
        submitted_at=order.submitted_at,
        contract_signed=signed,
        waiting_for_contract=status == OrderStatus.SUBMITTED and costs_money and not signed,
        booth_changed=order.booth_id_at_submit is not None and booth_id != order.booth_id_at_submit,
    )


async def _detail(session: AsyncSession, row: repo.StaffOrderRow) -> StaffOrderOut:
    order = row[0]
    lines = await repo.order_lines(session, [order.id])
    files = await repo.order_files(session, [order.id])
    reviewer = (
        await identity_repo.get_user(session, order.reviewed_by) if order.reviewed_by else None
    )
    booth_at_submit = (
        await exhibitors_repo.booth_code(session, order.booth_id_at_submit)
        if order.booth_id_at_submit
        else None
    )
    return StaffOrderOut(
        **_row_out(row).model_dump(),
        price_period=PricePeriod(order.price_period) if order.price_period else None,
        remarks=order.remarks,
        booth_code_at_submit=booth_at_submit,
        area_sqm_at_submit=order.area_sqm_at_submit,
        review_notes=order.review_notes,
        reviewed_at=order.reviewed_at,
        reviewed_by_name=reviewer.full_name if reviewer else None,
        cancel_reason=order.cancel_reason,
        lines=[line_out(line) for line in lines],
        files=[file_out(f) for f in files],
        version=order.version,
    )


async def _record(
    session: AsyncSession, order: ExhibitorOrder, action: str, before: dict[str, Any], **extra: Any
) -> None:
    await audit.record(
        session,
        entity_type=ENTITY,
        entity_id=order.id,
        action=action,
        before=before,
        after=audit.snapshot(order, AUDIT_FIELDS) | {"review_notes": order.review_notes} | extra,
        edition_id=order.edition_id,
    )


# --- reading -----------------------------------------------------------------------------


async def list_orders(
    session: AsyncSession, ctx: AuthContext, params: StaffOrderListParams
) -> Page[StaffOrderRowOut]:
    if params.status == OrderStatus.DRAFT:
        raise ValidationFailed(fields={"status": "Drafts are private to the exhibitor."})
    scope = _scope(ctx, params.edition_id, READ)
    rows, total = await repo.staff_orders(session, scope, params)
    return Page(
        items=[_row_out(r) for r in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def get_order(session: AsyncSession, ctx: AuthContext, order_id: uuid.UUID) -> StaffOrderOut:
    return await _detail(session, await _row_in_scope(session, ctx, order_id, READ))


async def lead_orders(session: AsyncSession, ctx: AuthContext, lead_id: uuid.UUID) -> LeadOrdersOut:
    """Progress on every published form and the sent orders of one exhibitor (lead page tab)."""
    edition_id = await exhibitors_repo.edition_of(session, lead_id)
    if edition_id is None:
        raise NotFound("Exhibitor lead not found.")
    try:
        scope = _scope(ctx, edition_id, READ)
    except NotFound as e:
        raise NotFound("Exhibitor lead not found.") from e
    lead = await exhibitors_repo.get_lead(session, scope, lead_id)
    if lead is None:
        raise NotFound("Exhibitor lead not found.")
    forms = await repo.published_forms(session, edition_id)
    orders = await repo.lead_orders(session, lead.id)
    waived = await repo.waived_form_ids(session, lead.id)
    rows, _total = await repo.staff_orders(
        session,
        scope,
        StaffOrderListParams(edition_id=edition_id, exhibitor_lead_id=lead.id, page_size=500),
    )
    return LeadOrdersOut(
        forms=[
            LeadFormProgressOut(
                form_id=f.id,
                code=f.code,
                title=f.title,
                progress=form_progress(
                    [OrderStatus(o.status) for o in orders if o.form_id == f.id], f.id in waived
                ),
            )
            for f in forms
        ],
        orders=[_row_out(r) for r in rows],
    )


async def line_image(
    session: AsyncSession, ctx: AuthContext, order_id: uuid.UUID, line_id: uuid.UUID
) -> tuple[Iterator[bytes], str, str]:
    order = (await _row_in_scope(session, ctx, order_id, READ))[0]
    line = await repo.get_line(session, line_id)
    if line is None or line.order_id != order.id or line.image_key is None:
        raise NotFound("Picture not found.")
    ext = PurePosixPath(line.image_key).suffix
    chunks = await run_in_threadpool(
        get_storage().stream, get_settings().s3_bucket_orders, line.image_key
    )
    return chunks, f"item-{line.id}{ext}", _MIME[ext]


async def file_download(
    session: AsyncSession, ctx: AuthContext, order_id: uuid.UUID, file_id: uuid.UUID
) -> tuple[Iterator[bytes], str, str]:
    order = (await _row_in_scope(session, ctx, order_id, READ))[0]
    row = await repo.get_file(session, file_id)
    if row is None or row.order_id != order.id:
        raise NotFound("File not found.")
    ext = PurePosixPath(row.file_key).suffix
    chunks = await run_in_threadpool(
        get_storage().stream, get_settings().s3_bucket_orders, row.file_key
    )
    return chunks, f"{order.order_number}-{row.id}{ext}", row.content_type


# --- changes -----------------------------------------------------------------------------


async def _locked(
    session: AsyncSession, ctx: AuthContext, order_id: uuid.UUID, version: int
) -> tuple[ExhibitorOrder, repo.StaffOrderRow]:
    row = await _row_in_scope(session, ctx, order_id, REVIEW)
    order = await repo.get_order(session, order_id, for_update=True)
    if order is None:  # read a moment ago in this transaction
        raise NotFound("Order not found.")
    check_version(order.version, version)
    await exhibitions_service.ensure_writable(session, order.edition_id)
    return order, row


async def _reload(session: AsyncSession, ctx: AuthContext, order: ExhibitorOrder) -> StaffOrderOut:
    flag_modified(order, "details")  # bump the version even when only lines changed
    await session.flush()
    await session.refresh(order)
    return await get_order(session, ctx, order.id)


async def price_line(
    session: AsyncSession,
    ctx: AuthContext,
    order_id: uuid.UUID,
    line_id: uuid.UUID,
    data: LinePriceIn,
) -> StaffOrderOut:
    """Price an extra item the exhibitor described (decision O6); only while it waits for review."""
    order, _row = await _locked(session, ctx, order_id, data.version)
    if order.status != OrderStatus.SUBMITTED:
        raise Conflict(
            "Only an order waiting for review can be priced.", code="ORDER_NOT_SUBMITTED"
        )
    line = await repo.get_line(session, line_id)
    if line is None or line.order_id != order.id:
        raise NotFound("Line not found.")
    if line.item_id is not None:
        raise ValidationFailed(
            "Catalog items keep the price they were sent with.", code="CATALOG_PRICE"
        )
    before = audit.snapshot(order, AUDIT_FIELDS)
    line.unit_price = data.unit_price.quantize(CENT)
    line.amount = line_amount(line.quantity, line.free_quantity, line.unit_price)
    await session.flush()
    lines = await repo.order_lines(session, [order.id])
    order.total = order_total(x.amount for x in lines)
    order.updated_by = current_actor_id()
    out = await _reload(session, ctx, order)
    await _record(session, order, "price_line", before, line=line.name, unit_price=data.unit_price)
    return out


async def review_order(
    session: AsyncSession, ctx: AuthContext, order_id: uuid.UUID, data: OrderReviewIn
) -> StaffOrderOut:
    """Approve, or send back to the exhibitor with a reason."""
    order, row = await _locked(session, ctx, order_id, data.version)
    target = OrderStatus(data.decision)
    if order.status != OrderStatus.SUBMITTED or not can_move(OrderStatus(order.status), target):
        raise Conflict(
            "Only an order waiting for review can be reviewed.", code="ORDER_NOT_SUBMITTED"
        )
    notes = clean_text(data.notes)
    lines = await repo.order_lines(session, [order.id])
    if target == OrderStatus.RETURNED:
        if notes is None:
            raise ValidationFailed(fields={"notes": "Tell the exhibitor what to change."})
    else:
        if not all_priced(line.amount for line in lines):
            raise ValidationFailed("Set a price on every extra item first.", code="UNPRICED_LINES")
        if approval_needs_signed_contract(order.total) and row[6] != ContractStatus.SIGNED:
            raise ValidationFailed(
                "The booth contract is not signed yet; orders that cost money wait for it.",
                code="CONTRACT_NOT_SIGNED",
            )
    before = audit.snapshot(order, AUDIT_FIELDS)
    order.status = target
    order.review_notes = notes
    order.reviewed_by = current_actor_id()
    order.reviewed_at = datetime.now(UTC)
    order.updated_by = current_actor_id()
    out = await _reload(session, ctx, order)
    await _record(session, order, "approve" if target == OrderStatus.APPROVED else "return", before)
    return out


async def cancel_order(
    session: AsyncSession, ctx: AuthContext, order_id: uuid.UUID, data: OrderCancelIn
) -> StaffOrderOut:
    """Cancel a sent order with a reason. Payments for orders come in Phase 7, which will block
    cancelling an order that has pending or verified payments."""
    order, _row = await _locked(session, ctx, order_id, data.version)
    if not can_move(OrderStatus(order.status), OrderStatus.CANCELLED):
        raise Conflict("This order is already cancelled.", code="ORDER_CANCELLED")
    reason = clean_text(data.reason)
    if reason is None:
        raise ValidationFailed(fields={"reason": "Give the reason."})
    before = audit.snapshot(order, AUDIT_FIELDS)
    order.status = OrderStatus.CANCELLED
    order.cancel_reason = reason
    order.updated_by = current_actor_id()
    out = await _reload(session, ctx, order)
    await _record(session, order, "cancel", before, cancel_reason=reason)
    return out


# --- export ------------------------------------------------------------------------------

EXPORT_HEADERS = [
    "Order No.", "Status", "Company", "Booth", "Sent", "Price Period", "Item Code", "Item",
    "Size", "Quantity", "Free", "Unit Price", "Amount", "Currency", "Order Total", "Remarks",
]  # fmt: skip


async def export_form(
    session: AsyncSession, ctx: AuthContext, params: OrderExportParams
) -> tuple[bytes, str]:
    """One sheet, one row per order line, for the contractor or the badge printer.

    Synchronous: a form has at most a few hundred orders. Audited like other exports.
    """
    scope = _scope(ctx, params.edition_id, READ)
    form = await repo.get_form(session, params.form_id)
    if form is None or form.edition_id != params.edition_id:
        raise NotFound("Order form not found.")
    rows = await repo.export_rows(session, scope, form.id, params.status)
    if len(rows) > repo.EXPORT_MAX_ROWS:
        raise ValidationFailed(
            f"More than {repo.EXPORT_MAX_ROWS} rows; filter by status.", code="EXPORT_TOO_LARGE"
        )
    out_rows = []
    for order, company, booth, line in rows:
        out_rows.append(
            [
                order.order_number,
                order.status,
                company,
                booth,
                order.submitted_at.date().isoformat() if order.submitted_at else None,
                order.price_period,
                line.code if line else None,
                line.name if line else None,
                line.size if line else None,
                line.quantity if line else None,
                line.free_quantity if line else None,
                float(line.unit_price) if line and line.unit_price is not None else None,
                float(line.amount) if line and line.amount is not None else None,
                order.currency,
                float(order.total),
                order.remarks,
            ]
        )
    data = await run_in_threadpool(
        write_workbook, [(f"Form {form.code}", EXPORT_HEADERS, out_rows)]
    )
    await audit.record(
        session,
        entity_type=ENTITY,
        entity_id=None,
        action="export",
        after={"form_code": form.code, "status": params.status, "rows": len(rows)},
        edition_id=form.edition_id,
    )
    return data, f"orders-form-{form.code}.xlsx"
