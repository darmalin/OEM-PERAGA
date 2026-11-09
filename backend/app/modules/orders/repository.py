"""Order form queries. Forms and catalog items are edition master data: callers resolve the
edition scope before these run."""

import uuid
from collections.abc import Sequence

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.orders.models import (
    ExhibitorFormWaiver,
    ExhibitorOrder,
    ExhibitorOrderCounter,
    ExhibitorOrderFile,
    ExhibitorOrderLine,
    OrderForm,
    OrderFormItem,
)
from app.modules.orders.rules import OrderStatus
from app.modules.orders.schemas import OrderFormItemListParams, OrderFormListParams


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
