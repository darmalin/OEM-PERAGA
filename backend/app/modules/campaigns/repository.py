import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.campaigns.models import CampaignLink


async def list_links(
    session: AsyncSession, edition_ids: set[uuid.UUID] | None
) -> Sequence[CampaignLink]:
    stmt = select(CampaignLink).order_by(CampaignLink.created_at.desc(), CampaignLink.id)
    if edition_ids is not None:
        stmt = stmt.where(CampaignLink.edition_id.in_(edition_ids))
    return (await session.scalars(stmt)).all()


async def get_link(session: AsyncSession, link_id: uuid.UUID) -> CampaignLink | None:
    return await session.get(CampaignLink, link_id)


async def link_by_token(
    session: AsyncSession, token: str, *, for_update: bool = False
) -> CampaignLink | None:
    stmt = select(CampaignLink).where(CampaignLink.token == token)
    if for_update:
        stmt = stmt.with_for_update()
    return await session.scalar(stmt)


async def name_taken(
    session: AsyncSession, edition_id: uuid.UUID, name: str, exclude: uuid.UUID | None = None
) -> bool:
    stmt = select(CampaignLink.id).where(
        CampaignLink.edition_id == edition_id, CampaignLink.name == name
    )
    if exclude is not None:
        stmt = stmt.where(CampaignLink.id != exclude)
    return await session.scalar(stmt) is not None
