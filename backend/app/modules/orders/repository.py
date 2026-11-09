"""Order form queries. Forms and catalog items are edition master data: callers resolve the
edition scope before these run."""

import uuid
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, Select, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import Scope
from app.modules.exhibitors.models import Booth, ExhibitorContract, ExhibitorLead, ExhibitorPayment
from app.modules.exhibitors.repository import scope_clause
from app.modules.orders.models import (
    ExhibitorFormWaiver,
    ExhibitorOrder,
    ExhibitorOrderCounter,
    ExhibitorOrderFile,
    ExhibitorOrderLine,
    OrderForm,
    OrderFormAllowance,
    OrderFormItem,
    OrderFormOption,
)
from app.modules.orders.rules import AllowanceTier, OrderStatus
from app.modules.orders.schemas import (
    OrderFormItemListParams,
    OrderFormListParams,
    StaffOrderListParams,
)

EXPORT_MAX_ROWS = 20000


def _active_items() -> ColumnElement[int]:
    return func.count(OrderFormItem.id).filter(OrderFormItem.is_active.is_(True))


async def list_forms(
    session: AsyncSession, edition_id: uuid.UUID, p: OrderFormListParams
) -> tuple[Sequence[tuple[OrderForm, int]], int]:
    total = (
        await session.scalar(
            select(func.count()).select_from(OrderForm).where(OrderForm.edition_id == edition_id)
        )
        or 0
    )
    stmt = (
        select(OrderForm, _active_items())
        .outerjoin(OrderFormItem, OrderFormItem.form_id == OrderForm.id)
        .where(OrderForm.edition_id == edition_id)
        .group_by(OrderForm.id)
        .order_by(OrderForm.sort_order, OrderForm.code)
        .offset(p.offset)
        .limit(p.page_size)
    )
    rows = (await session.execute(stmt)).all()
    return [(form, int(count)) for form, count in rows], total


async def get_form(
    session: AsyncSession, form_id: uuid.UUID, *, for_update: bool = False
) -> OrderForm | None:
    stmt = select(OrderForm).where(OrderForm.id == form_id)
    if for_update:
        stmt = stmt.with_for_update()
    return await session.scalar(stmt)


async def active_item_count(session: AsyncSession, form_id: uuid.UUID) -> int:
    stmt = select(_active_items()).where(OrderFormItem.form_id == form_id)
    return int(await session.scalar(stmt) or 0)


async def sent_order_count(session: AsyncSession, form_id: uuid.UUID) -> int:
    """Orders past DRAFT: their prices are in the form's currency."""
    stmt = select(func.count()).where(
        ExhibitorOrder.form_id == form_id, ExhibitorOrder.status != OrderStatus.DRAFT
    )
    return int(await session.scalar(stmt) or 0)


async def edition_forms(session: AsyncSession, edition_id: uuid.UUID) -> Sequence[OrderForm]:
    """All forms of an edition (at most a few dozen), for copying."""
    stmt = select(OrderForm).where(OrderForm.edition_id == edition_id).order_by(OrderForm.code)
    return (await session.scalars(stmt)).all()


async def form_items(session: AsyncSession, form_id: uuid.UUID) -> Sequence[OrderFormItem]:
    """Every item of one form, inactive ones included (copy and import)."""
    stmt = (
        select(OrderFormItem)
        .where(OrderFormItem.form_id == form_id)
        .order_by(OrderFormItem.sort_order, OrderFormItem.code)
    )
    return (await session.scalars(stmt)).all()


async def list_items(
    session: AsyncSession, form_id: uuid.UUID, p: OrderFormItemListParams
) -> tuple[Sequence[OrderFormItem], int]:
    conds = [OrderFormItem.form_id == form_id]
    if not p.include_inactive:
        conds.append(OrderFormItem.is_active.is_(True))
    total = await session.scalar(select(func.count()).select_from(OrderFormItem).where(*conds))
    stmt = (
        select(OrderFormItem)
        .where(*conds)
        .order_by(OrderFormItem.sort_order, OrderFormItem.code, OrderFormItem.id)
        .offset(p.offset)
        .limit(p.page_size)
    )
    return (await session.scalars(stmt)).all(), int(total or 0)


async def get_item(
    session: AsyncSession, item_id: uuid.UUID, *, for_update: bool = False
) -> OrderFormItem | None:
    stmt = select(OrderFormItem).where(OrderFormItem.id == item_id)
    if for_update:
        stmt = stmt.with_for_update()
    return await session.scalar(stmt)


# --- portal and orders -------------------------------------------------------------------


async def published_forms(session: AsyncSession, edition_id: uuid.UUID) -> Sequence[OrderForm]:
    stmt = (
        select(OrderForm)
        .where(OrderForm.edition_id == edition_id, OrderForm.is_published.is_(True))
        .order_by(OrderForm.sort_order, OrderForm.code)
    )
    return (await session.scalars(stmt)).all()


async def published_form(
    session: AsyncSession, edition_id: uuid.UUID, code: str
) -> OrderForm | None:
    stmt = select(OrderForm).where(
        OrderForm.edition_id == edition_id,
        OrderForm.code == code,
        OrderForm.is_published.is_(True),
    )
    return await session.scalar(stmt)


async def active_items(session: AsyncSession, form_id: uuid.UUID) -> Sequence[OrderFormItem]:
    """The catalog the portal shows; a form has hundreds of items at most."""
    stmt = (
        select(OrderFormItem)
        .where(OrderFormItem.form_id == form_id, OrderFormItem.is_active.is_(True))
        .order_by(OrderFormItem.sort_order, OrderFormItem.code, OrderFormItem.id)
    )
    return (await session.scalars(stmt)).all()


async def lead_orders(
    session: AsyncSession, lead_id: uuid.UUID, form_id: uuid.UUID | None = None
) -> Sequence[ExhibitorOrder]:
    """Orders of one exhibitor (optionally on one form), newest first."""
    stmt = select(ExhibitorOrder).where(ExhibitorOrder.exhibitor_lead_id == lead_id)
    if form_id is not None:
        stmt = stmt.where(ExhibitorOrder.form_id == form_id)
    stmt = stmt.order_by(ExhibitorOrder.created_at.desc(), ExhibitorOrder.id.desc())
    return (await session.scalars(stmt)).all()


async def get_order(
    session: AsyncSession, order_id: uuid.UUID, *, for_update: bool = False
) -> ExhibitorOrder | None:
    stmt = select(ExhibitorOrder).where(ExhibitorOrder.id == order_id)
    if for_update:
        stmt = stmt.with_for_update()
    return await session.scalar(stmt)


async def order_lines(
    session: AsyncSession, order_ids: Sequence[uuid.UUID]
) -> Sequence[ExhibitorOrderLine]:
    if not order_ids:
        return []
    stmt = (
        select(ExhibitorOrderLine)
        .where(ExhibitorOrderLine.order_id.in_(order_ids))
        .order_by(ExhibitorOrderLine.sort_order, ExhibitorOrderLine.created_at)
    )
    return (await session.scalars(stmt)).all()


async def order_files(
    session: AsyncSession, order_ids: Sequence[uuid.UUID]
) -> Sequence[ExhibitorOrderFile]:
    if not order_ids:
        return []
    stmt = (
        select(ExhibitorOrderFile)
        .where(ExhibitorOrderFile.order_id.in_(order_ids))
        .order_by(ExhibitorOrderFile.created_at)
    )
    return (await session.scalars(stmt)).all()


async def get_line(session: AsyncSession, line_id: uuid.UUID) -> ExhibitorOrderLine | None:
    return await session.get(ExhibitorOrderLine, line_id)


async def get_file(session: AsyncSession, file_id: uuid.UUID) -> ExhibitorOrderFile | None:
    return await session.get(ExhibitorOrderFile, file_id)


async def waived_form_ids(session: AsyncSession, lead_id: uuid.UUID) -> set[uuid.UUID]:
    stmt = select(ExhibitorFormWaiver.form_id).where(
        ExhibitorFormWaiver.exhibitor_lead_id == lead_id
    )
    return set((await session.scalars(stmt)).all())


async def get_waiver(
    session: AsyncSession, lead_id: uuid.UUID, form_id: uuid.UUID
) -> ExhibitorFormWaiver | None:
    stmt = select(ExhibitorFormWaiver).where(
        ExhibitorFormWaiver.exhibitor_lead_id == lead_id, ExhibitorFormWaiver.form_id == form_id
    )
    return await session.scalar(stmt)


async def next_order_number(session: AsyncSession, edition_id: uuid.UUID) -> int:
    """Next per-edition number; the row lock is held until the transaction ends."""
    stmt = (
        insert(ExhibitorOrderCounter)
        .values(edition_id=edition_id, last_value=1)
        .on_conflict_do_update(
            index_elements=[ExhibitorOrderCounter.edition_id],
            set_={"last_value": ExhibitorOrderCounter.last_value + 1},
        )
        .returning(ExhibitorOrderCounter.last_value)
    )
    return int((await session.execute(stmt)).scalar_one())


# --- staff review ------------------------------------------------------------------------

StaffOrderRow = tuple[ExhibitorOrder, str, str, str, uuid.UUID | None, str | None, str | None, int]


def _staff_select() -> Select[Any]:
    unpriced = (
        select(func.count(ExhibitorOrderLine.id))
        .where(
            ExhibitorOrderLine.order_id == ExhibitorOrder.id,
            ExhibitorOrderLine.unit_price.is_(None),
        )
        .correlate(ExhibitorOrder)
        .scalar_subquery()
    )
    return (
        select(
            ExhibitorOrder,
            OrderForm.code,
            OrderForm.title,
            ExhibitorLead.company_name,
            ExhibitorLead.booth_id,
            Booth.code,
            ExhibitorContract.status,
            unpriced,
        )
        .join(OrderForm, OrderForm.id == ExhibitorOrder.form_id)
        .join(ExhibitorLead, ExhibitorLead.id == ExhibitorOrder.exhibitor_lead_id)
        .outerjoin(Booth, Booth.id == ExhibitorLead.booth_id)
        .outerjoin(ExhibitorContract, ExhibitorContract.exhibitor_lead_id == ExhibitorLead.id)
    )


def _row(r: Any) -> StaffOrderRow:
    return (r[0], r[1], r[2], r[3], r[4], r[5], r[6], int(r[7] or 0))


async def staff_orders(
    session: AsyncSession, scope: Scope, p: StaffOrderListParams
) -> tuple[list[StaffOrderRow], int]:
    """Sent orders of the leads in scope; drafts stay private to the exhibitor."""
    conds: list[ColumnElement[bool]] = [
        scope_clause(scope),
        ExhibitorOrder.edition_id == p.edition_id,
        ExhibitorOrder.status != OrderStatus.DRAFT,
    ]
    if p.form_id is not None:
        conds.append(ExhibitorOrder.form_id == p.form_id)
    if p.status is not None:
        conds.append(ExhibitorOrder.status == p.status)
    if p.exhibitor_lead_id is not None:
        conds.append(ExhibitorOrder.exhibitor_lead_id == p.exhibitor_lead_id)
    if p.q and p.q.strip():
        like = f"%{p.q.strip().lower()}%"
        conds.append(
            or_(
                func.lower(ExhibitorLead.company_name).like(like),
                func.lower(ExhibitorOrder.order_number).like(like),
            )
        )
    total = await session.scalar(
        select(func.count())
        .select_from(ExhibitorOrder)
        .join(ExhibitorLead, ExhibitorLead.id == ExhibitorOrder.exhibitor_lead_id)
        .where(*conds)
    )
    stmt = (
        _staff_select()
        .where(*conds)
        .order_by(ExhibitorOrder.submitted_at.desc().nulls_last(), ExhibitorOrder.id.desc())
        .offset(p.offset)
        .limit(p.page_size)
    )
    return [_row(r) for r in (await session.execute(stmt)).all()], int(total or 0)


async def staff_order(
    session: AsyncSession, scope: Scope, order_id: uuid.UUID
) -> StaffOrderRow | None:
    stmt = _staff_select().where(
        scope_clause(scope),
        ExhibitorOrder.id == order_id,
        ExhibitorOrder.status != OrderStatus.DRAFT,
    )
    r = (await session.execute(stmt)).first()
    return _row(r) if r else None


async def export_rows(
    session: AsyncSession, scope: Scope, form_id: uuid.UUID, status: OrderStatus | None
) -> Sequence[tuple[ExhibitorOrder, str, str | None, ExhibitorOrderLine | None]]:
    """One row per order line (orders without lines once) for the per-form export."""
    conds: list[ColumnElement[bool]] = [
        scope_clause(scope),
        ExhibitorOrder.form_id == form_id,
        ExhibitorOrder.status != OrderStatus.DRAFT,
    ]
    if status is not None:
        conds.append(ExhibitorOrder.status == status)
    stmt = (
        select(ExhibitorOrder, ExhibitorLead.company_name, Booth.code, ExhibitorOrderLine)
        .join(ExhibitorLead, ExhibitorLead.id == ExhibitorOrder.exhibitor_lead_id)
        .outerjoin(Booth, Booth.id == ExhibitorLead.booth_id)
        .outerjoin(ExhibitorOrderLine, ExhibitorOrderLine.order_id == ExhibitorOrder.id)
        .where(*conds)
        .order_by(ExhibitorOrder.order_number, ExhibitorOrderLine.sort_order)
        .limit(EXPORT_MAX_ROWS + 1)
    )
    return [(r[0], r[1], r[2], r[3]) for r in (await session.execute(stmt)).all()]


async def form_options(session: AsyncSession, form_id: uuid.UUID) -> dict[str, list[str]]:
    stmt = (
        select(OrderFormOption.kind, OrderFormOption.value)
        .where(OrderFormOption.form_id == form_id)
        .order_by(OrderFormOption.kind, OrderFormOption.sort_order, OrderFormOption.value)
    )
    out: dict[str, list[str]] = {}
    for kind, value in (await session.execute(stmt)).all():
        out.setdefault(kind, []).append(value)
    return out


async def delete_options(session: AsyncSession, form_id: uuid.UUID, kind: str) -> None:
    await session.execute(
        delete(OrderFormOption).where(
            OrderFormOption.form_id == form_id, OrderFormOption.kind == kind
        )
    )


# --- allowances (free quantities by booth area) -------------------------------------------


async def allowances(
    session: AsyncSession, item_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[AllowanceTier]]:
    if not item_ids:
        return {}
    stmt = (
        select(OrderFormAllowance)
        .where(OrderFormAllowance.item_id.in_(item_ids))
        .order_by(OrderFormAllowance.min_area_sqm)
    )
    out: dict[uuid.UUID, list[AllowanceTier]] = {}
    for row in (await session.scalars(stmt)).all():
        out.setdefault(row.item_id, []).append(AllowanceTier(row.min_area_sqm, row.free_quantity))
    return out


async def delete_allowances(session: AsyncSession, item_id: uuid.UUID) -> None:
    await session.execute(delete(OrderFormAllowance).where(OrderFormAllowance.item_id == item_id))


async def free_used(
    session: AsyncSession, lead_id: uuid.UUID, exclude_order_id: uuid.UUID | None
) -> dict[uuid.UUID, int]:
    """Free quantity already taken per item by the exhibitor's other live orders."""
    live = (OrderStatus.SUBMITTED, OrderStatus.RETURNED, OrderStatus.APPROVED)
    stmt = (
        select(ExhibitorOrderLine.item_id, func.sum(ExhibitorOrderLine.free_quantity))
        .join(ExhibitorOrder, ExhibitorOrder.id == ExhibitorOrderLine.order_id)
        .where(
            ExhibitorOrder.exhibitor_lead_id == lead_id,
            ExhibitorOrder.status.in_(live),
            ExhibitorOrderLine.item_id.is_not(None),
        )
        .group_by(ExhibitorOrderLine.item_id)
    )
    if exclude_order_id is not None:
        stmt = stmt.where(ExhibitorOrder.id != exclude_order_id)
    return {item_id: int(n or 0) for item_id, n in (await session.execute(stmt)).all() if item_id}


# --- payments of orders (exhibitor_payments.order_id, migration 0034) ----------------------


async def order_payments(session: AsyncSession, order_id: uuid.UUID) -> Sequence[ExhibitorPayment]:
    stmt = (
        select(ExhibitorPayment)
        .where(ExhibitorPayment.order_id == order_id)
        .order_by(ExhibitorPayment.paid_on, ExhibitorPayment.created_at)
    )
    return (await session.scalars(stmt)).all()


async def order_payment(
    session: AsyncSession, order_id: uuid.UUID, payment_id: uuid.UUID, *, for_update: bool = False
) -> ExhibitorPayment | None:
    stmt = select(ExhibitorPayment).where(
        ExhibitorPayment.id == payment_id, ExhibitorPayment.order_id == order_id
    )
    if for_update:
        stmt = stmt.with_for_update()
    return await session.scalar(stmt)


async def order_payment_sums(
    session: AsyncSession, order_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, dict[str, Decimal]]:
    """Per order, the sum of its payments by status."""
    if not order_ids:
        return {}
    stmt = (
        select(
            ExhibitorPayment.order_id, ExhibitorPayment.status, func.sum(ExhibitorPayment.amount)
        )
        .where(ExhibitorPayment.order_id.in_(order_ids))
        .group_by(ExhibitorPayment.order_id, ExhibitorPayment.status)
    )
    out: dict[uuid.UUID, dict[str, Decimal]] = {}
    for order_id, status, total in (await session.execute(stmt)).all():
        if order_id is not None:
            out.setdefault(order_id, {})[status] = total
    return out


async def status_counts(session: AsyncSession, scope: Scope) -> dict[str, int]:
    stmt = (
        select(ExhibitorOrder.status, func.count())
        .join(ExhibitorLead, ExhibitorLead.id == ExhibitorOrder.exhibitor_lead_id)
        .where(scope_clause(scope), ExhibitorOrder.status != OrderStatus.DRAFT)
        .group_by(ExhibitorOrder.status)
    )
    return {status: int(n) for status, n in (await session.execute(stmt)).all()}


async def approved_orders(session: AsyncSession, scope: Scope) -> Sequence[ExhibitorOrder]:
    """Approved orders that cost money, in scope; an edition has hundreds at most."""
    stmt = (
        select(ExhibitorOrder)
        .join(ExhibitorLead, ExhibitorLead.id == ExhibitorOrder.exhibitor_lead_id)
        .where(
            scope_clause(scope),
            ExhibitorOrder.status == OrderStatus.APPROVED,
            ExhibitorOrder.total > 0,
        )
    )
    return (await session.scalars(stmt)).all()
