import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require
from app.core.db import get_session
from app.core.pagination import Page
from app.modules.audit.schemas import AuditLogOut
from app.modules.exhibitors import service
from app.modules.exhibitors.schemas import (
    ExhibitorLeadCreateIn,
    ExhibitorLeadListParams,
    ExhibitorLeadOut,
    ExhibitorLeadUpdateIn,
    StageChangeIn,
)

router = APIRouter(tags=["exhibitors"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/exhibitor-leads", response_model=Page[ExhibitorLeadOut])
async def list_leads(
    session: Session,
    params: Annotated[ExhibitorLeadListParams, Query()],
    ctx: AuthContext = Depends(require("exhibitor_lead.read")),
) -> Page[ExhibitorLeadOut]:
    return await service.list_leads(session, ctx, params)


@router.post(
    "/exhibitor-leads", response_model=ExhibitorLeadOut, status_code=status.HTTP_201_CREATED
)
async def create_lead(
    data: ExhibitorLeadCreateIn,
    session: Session,
    ctx: AuthContext = Depends(require("exhibitor_lead.create")),
) -> ExhibitorLeadOut:
    return await service.create_lead(session, ctx, data)


@router.get("/exhibitor-leads/{lead_id}", response_model=ExhibitorLeadOut)
async def get_lead(
    lead_id: uuid.UUID,
    session: Session,
    ctx: AuthContext = Depends(require("exhibitor_lead.read")),
) -> ExhibitorLeadOut:
    return await service.get_lead(session, ctx, lead_id)


@router.patch("/exhibitor-leads/{lead_id}", response_model=ExhibitorLeadOut)
async def update_lead(
    lead_id: uuid.UUID,
    data: ExhibitorLeadUpdateIn,
    session: Session,
    ctx: AuthContext = Depends(require("exhibitor_lead.update")),
) -> ExhibitorLeadOut:
    return await service.update_lead(session, ctx, lead_id, data)


@router.post("/exhibitor-leads/{lead_id}/stage", response_model=ExhibitorLeadOut)
async def change_stage(
    lead_id: uuid.UUID,
    data: StageChangeIn,
    session: Session,
    ctx: AuthContext = Depends(require("exhibitor_lead.update")),
) -> ExhibitorLeadOut:
    return await service.change_stage(session, ctx, lead_id, data)


@router.get("/exhibitor-leads/{lead_id}/activity", response_model=list[AuditLogOut])
async def lead_activity(
    lead_id: uuid.UUID,
    session: Session,
    ctx: AuthContext = Depends(require("exhibitor_lead.read")),
) -> list[AuditLogOut]:
    return await service.activity(session, ctx, lead_id)
