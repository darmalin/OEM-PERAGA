"""Order form queries. Forms and catalog items are edition master data: callers resolve the
edition scope before these run."""

import uuid
from collections.abc import Sequence

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.orders.models import ExhibitorOrder, OrderForm, OrderFormItem
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
