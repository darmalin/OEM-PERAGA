import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require
from app.core.db import get_session
from app.modules.quotations import service
from app.modules.quotations.schemas import (
    QuotationCancelIn,
    QuotationIn,
    QuotationOut,
    QuotationPreviewOut,
    SettingsIn,
    SettingsOut,
)

router = APIRouter(tags=["quotations"])
Session = Annotated[AsyncSession, Depends(get_session)]
Read = Depends(require(service.READ))
Write = Depends(require(service.WRITE))
ManageSettings = Depends(require(service.SETTINGS))


@router.get("/editions/{edition_id}/quotation-settings", response_model=SettingsOut)
async def get_settings(
    edition_id: uuid.UUID, session: Session, ctx: AuthContext = Read
) -> SettingsOut:
    return await service.get_settings(session, ctx, edition_id)


@router.put("/editions/{edition_id}/quotation-settings", response_model=SettingsOut)
async def save_settings(
    edition_id: uuid.UUID, data: SettingsIn, session: Session, ctx: AuthContext = ManageSettings
) -> SettingsOut:
    return await service.save_settings(session, ctx, edition_id, data)


@router.get("/exhibitor-leads/{lead_id}/quotations", response_model=list[QuotationOut])
async def list_quotations(
    lead_id: uuid.UUID, session: Session, ctx: AuthContext = Read
) -> list[QuotationOut]:
    return await service.list_for_lead(session, ctx, lead_id)


@router.post("/exhibitor-leads/{lead_id}/quotations/preview", response_model=QuotationPreviewOut)
async def preview_quotation(
    lead_id: uuid.UUID, data: QuotationIn, session: Session, ctx: AuthContext = Write
) -> QuotationPreviewOut:
    return await service.preview(session, ctx, lead_id, data)


@router.post(
    "/exhibitor-leads/{lead_id}/quotations",
    response_model=QuotationOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_quotation(
    lead_id: uuid.UUID, data: QuotationIn, session: Session, ctx: AuthContext = Write
) -> QuotationOut:
    return await service.create(session, ctx, lead_id, data)


@router.get("/quotations/{quotation_id}", response_model=QuotationOut)
async def get_quotation(
    quotation_id: uuid.UUID, session: Session, ctx: AuthContext = Read
) -> QuotationOut:
    return await service.get(session, ctx, quotation_id)


@router.post("/quotations/{quotation_id}/cancel", response_model=QuotationOut)
async def cancel_quotation(
    quotation_id: uuid.UUID, data: QuotationCancelIn, session: Session, ctx: AuthContext = Write
) -> QuotationOut:
    return await service.cancel(session, ctx, quotation_id, data)
