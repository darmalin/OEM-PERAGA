import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require
from app.core.context import Source, source_var
from app.core.db import get_session
from app.modules.campaigns import service
from app.modules.campaigns.schemas import (
    CampaignLinkIn,
    CampaignLinkOut,
    CampaignLinkParams,
    CampaignLinkUpdateIn,
    PublicCampaignOut,
    PublicSubmissionIn,
    PublicSubmissionOut,
)
from app.modules.identity.router import client_ip

router = APIRouter(prefix="/campaign-links", tags=["campaigns"])
public_router = APIRouter(prefix="/public/campaigns", tags=["public"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=list[CampaignLinkOut])
async def list_links(
    session: Session,
    params: Annotated[CampaignLinkParams, Query()],
    ctx: AuthContext = Depends(require("visitor.read", "edition.manage")),
) -> list[CampaignLinkOut]:
    return await service.list_links(session, ctx, params.edition_id)


@router.post("", response_model=CampaignLinkOut, status_code=status.HTTP_201_CREATED)
async def create_link(
    data: CampaignLinkIn, session: Session, ctx: AuthContext = Depends(require("edition.manage"))
) -> CampaignLinkOut:
    return await service.create_link(session, ctx, data)


@router.patch("/{link_id}", response_model=CampaignLinkOut)
async def update_link(
    link_id: uuid.UUID,
    data: CampaignLinkUpdateIn,
    session: Session,
    ctx: AuthContext = Depends(require("edition.manage")),
) -> CampaignLinkOut:
    return await service.update_link(session, ctx, link_id, data)


@router.post("/{link_id}/new-url", response_model=CampaignLinkOut)
async def new_url(
    link_id: uuid.UUID, session: Session, ctx: AuthContext = Depends(require("edition.manage"))
) -> CampaignLinkOut:
    return await service.new_link_token(session, ctx, link_id)


@router.get("/{link_id}/qr.png", response_class=Response)
async def poster_qr(
    link_id: uuid.UUID,
    session: Session,
    ctx: AuthContext = Depends(require("visitor.read", "edition.manage")),
) -> Response:
    png, name = await service.poster_qr(session, ctx, link_id)
    return Response(
        png,
        media_type="image/png",
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "Cache-Control": "no-store",
        },
    )


# --- public: no login, no session cookie needed --------------------------------------------


@public_router.get("/{token}", response_model=PublicCampaignOut)
async def public_form(token: str, session: Session, response: Response) -> PublicCampaignOut:
    response.headers["Cache-Control"] = "no-store"
    return await service.public_form(session, token)


@public_router.post(
    "/{token}/registrations",
    response_model=PublicSubmissionOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def public_submit(
    token: str, data: PublicSubmissionIn, request: Request, session: Session, response: Response
) -> PublicSubmissionOut:
    source_var.set(Source.PUBLIC)
    response.headers["Cache-Control"] = "no-store"
    return await service.public_submit(session, token, data, client_ip(request))
