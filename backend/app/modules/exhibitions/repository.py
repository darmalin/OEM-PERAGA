"""Exhibition queries. Edition visibility is passed in as a set of IDs (None = all)."""

import uuid
from collections.abc import Sequence

from sqlalchemy import Row, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.exhibitions.models import Edition, EditionCounter, Exhibition, Venue
from app.modules.exhibitions.rules import EditionStatus


async def list_venues(session: AsyncSession) -> Sequence[Venue]:
    return (await session.scalars(select(Venue).order_by(Venue.name).limit(1000))).all()


async def get_venue(session: AsyncSession, venue_id: uuid.UUID) -> Venue | None:
    return await session.get(Venue, venue_id)


async def list_exhibitions(
    session: AsyncSession,
    edition_ids: set[uuid.UUID] | None,
    q: str | None,
    is_active: bool | None,
    offset: int,
    limit: int,
) -> tuple[Sequence[Exhibition], int]:
    stmt = select(Exhibition)
    if edition_ids is not None:
        stmt = stmt.where(
            Exhibition.id.in_(select(Edition.exhibition_id).where(Edition.id.in_(edition_ids)))
        )
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(func.lower(Exhibition.name).like(like), func.lower(Exhibition.code).like(like))
        )
    if is_active is not None:
        stmt = stmt.where(Exhibition.is_active.is_(is_active))
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = await session.scalars(stmt.order_by(Exhibition.code).offset(offset).limit(limit))
    return rows.all(), total


async def get_exhibition(
    session: AsyncSession, exhibition_id: uuid.UUID, edition_ids: set[uuid.UUID] | None
) -> Exhibition | None:
    stmt = select(Exhibition).where(Exhibition.id == exhibition_id)
    if edition_ids is not None:
        stmt = stmt.where(
            Exhibition.id.in_(select(Edition.exhibition_id).where(Edition.id.in_(edition_ids)))
        )
    return await session.scalar(stmt)


async def list_editions(
    session: AsyncSession,
    edition_ids: set[uuid.UUID] | None,
    exhibition_id: uuid.UUID | None,
    status: EditionStatus | None,
    year: int | None,
    offset: int,
    limit: int,
) -> tuple[Sequence[Row[Edition, str]], int]:
    stmt = select(Edition, Exhibition.code).join(Exhibition, Exhibition.id == Edition.exhibition_id)
    if edition_ids is not None:
        stmt = stmt.where(Edition.id.in_(edition_ids))
    if exhibition_id:
        stmt = stmt.where(Edition.exhibition_id == exhibition_id)
    if status:
        stmt = stmt.where(Edition.status == status)
    if year:
        stmt = stmt.where(Edition.year == year)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = await session.execute(
        stmt.order_by(Edition.start_date.desc(), Edition.code).offset(offset).limit(limit)
    )
    return rows.all(), total


async def get_edition(session: AsyncSession, edition_id: uuid.UUID) -> Edition | None:
    """Callers must already have resolved scope for this edition."""
    return await session.get(Edition, edition_id)


async def exhibition_code(session: AsyncSession, exhibition_id: uuid.UUID) -> str | None:
    return await session.scalar(select(Exhibition.code).where(Exhibition.id == exhibition_id))


async def increment_counter(session: AsyncSession, edition_id: uuid.UUID) -> int:
    """Row-locked increment; concurrent callers never get the same value."""
    value = await session.scalar(
        update(EditionCounter)
        .where(EditionCounter.edition_id == edition_id)
        .values(last_value=EditionCounter.last_value + 1)
        .returning(EditionCounter.last_value)
    )
    if value is None:
        raise LookupError(f"no counter for edition {edition_id}")
    return int(value)
