import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import idempotency
from app.core.authorization import AuthContext, require
from app.core.db import get_session
from app.core.pagination import Page
from app.modules.mail.schemas import EmailJobOut
from app.modules.registrations import service
from app.modules.registrations.schemas import (
    EmailTemplateIn,
    EmailTemplateOut,
    EmailTemplateParams,
    RegistrationDetailOut,
    RegistrationIn,
    RegistrationListParams,
    RegistrationOut,
    RevokeQrIn,
)

router = APIRouter(tags=["registrations"])
Session = Annotated[AsyncSession, Depends(get_session)]
IdempotencyHeader = Annotated[str | None, Header(alias="Idempotency-Key")]


@router.post(
    "/visitor-registrations", response_model=RegistrationOut, status_code=status.HTTP_201_CREATED
)
async def create_registration(
    data: RegistrationIn,
    session: Session,
    idempotency_key: IdempotencyHeader = None,
    ctx: AuthContext = Depends(require("registration.create")),
) -> RegistrationOut:
    key = idempotency.validate_key(idempotency_key, required=True)
    assert key is not None  # noqa: S101 - required=True
    return await service.create_registration(session, ctx, data, key)


@router.get("/visitor-registrations", response_model=Page[RegistrationOut])
async def list_registrations(
    session: Session,
    params: Annotated[RegistrationListParams, Query()],
    ctx: AuthContext = Depends(require("registration.read")),
) -> Page[RegistrationOut]:
    return await service.list_registrations(session, ctx, params)


@router.get("/visitor-registrations/{registration_id}", response_model=RegistrationDetailOut)
async def get_registration(
    registration_id: uuid.UUID,
    session: Session,
    ctx: AuthContext = Depends(require("registration.read")),
) -> RegistrationDetailOut:
    return await service.get_registration(session, ctx, registration_id)


@router.post(
    "/visitor-registrations/{registration_id}/resend-qr",
    response_model=EmailJobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def resend_qr(
    registration_id: uuid.UUID,
    session: Session,
    idempotency_key: IdempotencyHeader = None,
    ctx: AuthContext = Depends(require("registration.resend_qr")),
) -> EmailJobOut:
    key = idempotency.validate_key(idempotency_key, required=True)
    assert key is not None  # noqa: S101 - required=True
    return await service.resend_qr(session, ctx, registration_id, key)


@router.post(
    "/visitor-registrations/{registration_id}/revoke-qr", response_model=RegistrationDetailOut
)
async def revoke_qr(
    registration_id: uuid.UUID,
    data: RevokeQrIn,
    session: Session,
    ctx: AuthContext = Depends(require("registration.resend_qr")),
) -> RegistrationDetailOut:
    return await service.revoke_qr(session, ctx, registration_id, data)


@router.get("/email-templates", response_model=list[EmailTemplateOut])
async def list_email_templates(
    session: Session,
    params: Annotated[EmailTemplateParams, Query()],
    ctx: AuthContext = Depends(require("edition.manage")),
) -> list[EmailTemplateOut]:
    return await service.list_templates(session, ctx, params.edition_id, params.template_key)


@router.post(
    "/email-templates", response_model=EmailTemplateOut, status_code=status.HTTP_201_CREATED
)
async def create_email_template(
    data: EmailTemplateIn,
    session: Session,
    ctx: AuthContext = Depends(require("edition.manage")),
) -> EmailTemplateOut:
    return await service.create_template_version(session, ctx, data)
