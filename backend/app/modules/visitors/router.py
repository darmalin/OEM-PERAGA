import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require
from app.core.db import get_session
from app.core.pagination import Page
from app.modules.audit.schemas import AuditLogOut
from app.modules.visitors import service
from app.modules.visitors.schemas import (
    CustomFieldIn,
    CustomFieldOut,
    CustomFieldUpdateIn,
    EditionScopedParams,
    FieldOptionIn,
    FieldOptionOut,
    FieldOptionParams,
    FieldOptionUpdateIn,
    LeadCreateIn,
    LeadListItem,
    LeadListParams,
    LeadOut,
    LeadUpdateIn,
)

router = APIRouter(tags=["visitors"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/visitor-leads", response_model=Page[LeadListItem])
async def list_leads(
    session: Session,
    params: Annotated[LeadListParams, Query()],
    ctx: AuthContext = Depends(require("visitor.read")),
) -> Page[LeadListItem]:
    return await service.list_leads(session, ctx, params)


@router.post("/visitor-leads", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
async def create_lead(
    data: LeadCreateIn, session: Session, ctx: AuthContext = Depends(require("visitor.create"))
) -> LeadOut:
    return await service.create_lead(session, ctx, data)


@router.get("/visitor-leads/{lead_id}", response_model=LeadOut)
async def get_lead(
    lead_id: uuid.UUID, session: Session, ctx: AuthContext = Depends(require("visitor.read"))
) -> LeadOut:
    return await service.get_lead(session, ctx, lead_id)


@router.patch("/visitor-leads/{lead_id}", response_model=LeadOut)
async def update_lead(
    lead_id: uuid.UUID,
    data: LeadUpdateIn,
    session: Session,
    ctx: AuthContext = Depends(require("visitor.update")),
) -> LeadOut:
    return await service.update_lead(session, ctx, lead_id, data)


@router.get("/visitor-leads/{lead_id}/activity", response_model=list[AuditLogOut])
async def lead_activity(
    lead_id: uuid.UUID, session: Session, ctx: AuthContext = Depends(require("visitor.read"))
) -> list[AuditLogOut]:
    return await service.activity(session, ctx, lead_id)


@router.get("/visitor-custom-fields", response_model=list[CustomFieldOut])
async def list_custom_fields(
    session: Session,
    params: Annotated[EditionScopedParams, Query()],
    ctx: AuthContext = Depends(require("visitor.read", "edition.manage")),
) -> list[CustomFieldOut]:
    return await service.list_custom_fields(
        session, ctx, params.edition_id, params.include_inactive
    )


@router.post(
    "/visitor-custom-fields", response_model=CustomFieldOut, status_code=status.HTTP_201_CREATED
)
async def create_custom_field(
    data: CustomFieldIn, session: Session, ctx: AuthContext = Depends(require("edition.manage"))
) -> CustomFieldOut:
    return await service.create_custom_field(session, ctx, data)


@router.patch("/visitor-custom-fields/{field_id}", response_model=CustomFieldOut)
async def update_custom_field(
    field_id: uuid.UUID,
    data: CustomFieldUpdateIn,
    session: Session,
    ctx: AuthContext = Depends(require("edition.manage")),
) -> CustomFieldOut:
    return await service.update_custom_field(session, ctx, field_id, data)


@router.get("/edition-field-options", response_model=list[FieldOptionOut])
async def list_field_options(
    session: Session,
    params: Annotated[FieldOptionParams, Query()],
    ctx: AuthContext = Depends(require("visitor.read", "edition.manage")),
) -> list[FieldOptionOut]:
    return await service.list_field_options(
        session, ctx, params.edition_id, params.field, params.include_inactive
    )


@router.post(
    "/edition-field-options", response_model=FieldOptionOut, status_code=status.HTTP_201_CREATED
)
async def create_field_option(
    data: FieldOptionIn, session: Session, ctx: AuthContext = Depends(require("edition.manage"))
) -> FieldOptionOut:
    return await service.create_field_option(session, ctx, data)


@router.patch("/edition-field-options/{option_id}", response_model=FieldOptionOut)
async def update_field_option(
    option_id: uuid.UUID,
    data: FieldOptionUpdateIn,
    session: Session,
    ctx: AuthContext = Depends(require("edition.manage")),
) -> FieldOptionOut:
    return await service.update_field_option(session, ctx, option_id, data)
