import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require
from app.core.db import get_session
from app.core.pagination import Page
from app.modules.exhibitions import service
from app.modules.exhibitions.schemas import (
    EditionIn,
    EditionListParams,
    EditionOut,
    EditionUpdateIn,
    ExhibitionIn,
    ExhibitionListParams,
    ExhibitionOut,
    ExhibitionUpdateIn,
    VenueIn,
    VenueOut,
    VenueUpdateIn,
)

router = APIRouter(tags=["exhibitions"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/venues", response_model=list[VenueOut])
async def list_venues(
    session: Session, _: AuthContext = Depends(require("exhibition.read", "edition.manage"))
) -> list[VenueOut]:
    return await service.list_venues(session)


@router.post("/venues", response_model=VenueOut, status_code=status.HTTP_201_CREATED)
async def create_venue(
    data: VenueIn, session: Session, ctx: AuthContext = Depends(require("exhibition.manage"))
) -> VenueOut:
    return await service.create_venue(session, ctx, data)


@router.patch("/venues/{venue_id}", response_model=VenueOut)
async def update_venue(
    venue_id: uuid.UUID,
    data: VenueUpdateIn,
    session: Session,
    ctx: AuthContext = Depends(require("exhibition.manage")),
) -> VenueOut:
    return await service.update_venue(session, ctx, venue_id, data)


@router.get("/exhibitions", response_model=Page[ExhibitionOut])
async def list_exhibitions(
    session: Session,
    params: Annotated[ExhibitionListParams, Query()],
    ctx: AuthContext = Depends(require("exhibition.read")),
) -> Page[ExhibitionOut]:
    return await service.list_exhibitions(session, ctx, params)


@router.post("/exhibitions", response_model=ExhibitionOut, status_code=status.HTTP_201_CREATED)
async def create_exhibition(
    data: ExhibitionIn, session: Session, ctx: AuthContext = Depends(require("exhibition.manage"))
) -> ExhibitionOut:
    return await service.create_exhibition(session, ctx, data)


@router.get("/exhibitions/{exhibition_id}", response_model=ExhibitionOut)
async def get_exhibition(
    exhibition_id: uuid.UUID,
    session: Session,
    ctx: AuthContext = Depends(require("exhibition.read")),
) -> ExhibitionOut:
    return await service.get_exhibition(session, ctx, exhibition_id)


@router.patch("/exhibitions/{exhibition_id}", response_model=ExhibitionOut)
async def update_exhibition(
    exhibition_id: uuid.UUID,
    data: ExhibitionUpdateIn,
    session: Session,
    ctx: AuthContext = Depends(require("exhibition.manage")),
) -> ExhibitionOut:
    return await service.update_exhibition(session, ctx, exhibition_id, data)


@router.get("/editions", response_model=Page[EditionOut])
async def list_editions(
    session: Session,
    params: Annotated[EditionListParams, Query()],
    ctx: AuthContext = Depends(require("edition.read")),
) -> Page[EditionOut]:
    return await service.list_editions(session, ctx, params)


@router.post("/editions", response_model=EditionOut, status_code=status.HTTP_201_CREATED)
async def create_edition(
    data: EditionIn, session: Session, ctx: AuthContext = Depends(require("edition.manage"))
) -> EditionOut:
    return await service.create_edition(session, ctx, data)


@router.get("/editions/{edition_id}", response_model=EditionOut)
async def get_edition(
    edition_id: uuid.UUID, session: Session, ctx: AuthContext = Depends(require("edition.read"))
) -> EditionOut:
    return await service.get_edition(session, ctx, edition_id)


@router.patch("/editions/{edition_id}", response_model=EditionOut)
async def update_edition(
    edition_id: uuid.UUID,
    data: EditionUpdateIn,
    session: Session,
    ctx: AuthContext = Depends(require("edition.manage")),
) -> EditionOut:
    return await service.update_edition(session, ctx, edition_id, data)
