import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require
from app.core.db import get_session
from app.core.pagination import Page, PageParams
from app.modules.mail import service
from app.modules.mail.schemas import (
    EmailAccountBrief,
    EmailAccountIn,
    EmailAccountOut,
    EmailAccountUpdateIn,
    EmailJobListParams,
    EmailJobOut,
    LeadEmailPage,
    TestEmailAccepted,
)

router = APIRouter(tags=["mail"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/email-accounts", response_model=list[EmailAccountOut])
async def list_accounts(
    session: Session, ctx: AuthContext = Depends(require(service.MANAGE))
) -> list[EmailAccountOut]:
    return await service.list_accounts(session, ctx)


@router.get("/email-accounts/choices", response_model=list[EmailAccountBrief])
async def account_choices(
    session: Session, _: AuthContext = Depends(require("edition.manage", service.MANAGE))
) -> list[EmailAccountBrief]:
    return await service.account_choices(session)


@router.post("/email-accounts", response_model=EmailAccountOut, status_code=status.HTTP_201_CREATED)
async def create_account(
    data: EmailAccountIn, session: Session, ctx: AuthContext = Depends(require(service.MANAGE))
) -> EmailAccountOut:
    return await service.create_account(session, ctx, data)


@router.get("/email-accounts/{account_id}", response_model=EmailAccountOut)
async def get_account(
    account_id: uuid.UUID, session: Session, ctx: AuthContext = Depends(require(service.MANAGE))
) -> EmailAccountOut:
    return await service.get_account(session, ctx, account_id)


@router.patch("/email-accounts/{account_id}", response_model=EmailAccountOut)
async def update_account(
    account_id: uuid.UUID,
    data: EmailAccountUpdateIn,
    session: Session,
    ctx: AuthContext = Depends(require(service.MANAGE)),
) -> EmailAccountOut:
    return await service.update_account(session, ctx, account_id, data)


@router.post("/email-accounts/{account_id}/default", response_model=EmailAccountOut)
async def set_default(
    account_id: uuid.UUID, session: Session, ctx: AuthContext = Depends(require(service.MANAGE))
) -> EmailAccountOut:
    return await service.set_default(session, ctx, account_id)


@router.post(
    "/email-accounts/{account_id}/test",
    response_model=TestEmailAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def send_test(
    account_id: uuid.UUID, session: Session, ctx: AuthContext = Depends(require(service.MANAGE))
) -> TestEmailAccepted:
    return await service.send_test(session, ctx, account_id)


@router.get("/email-jobs", response_model=Page[EmailJobOut])
async def list_jobs(
    session: Session,
    params: Annotated[EmailJobListParams, Query()],
    ctx: AuthContext = Depends(require(service.READ_LOG, service.MANAGE)),
) -> Page[EmailJobOut]:
    return await service.list_jobs(session, ctx, params)


@router.get("/email-jobs/{job_id}", response_model=EmailJobOut)
async def get_job(
    job_id: uuid.UUID,
    session: Session,
    ctx: AuthContext = Depends(require(service.READ_LOG, service.MANAGE)),
) -> EmailJobOut:
    return await service.get_job(session, ctx, job_id)


@router.get("/visitor-leads/{lead_id}/emails", response_model=LeadEmailPage)
async def lead_emails(
    lead_id: uuid.UUID,
    session: Session,
    params: Annotated[PageParams, Query()],
    ctx: AuthContext = Depends(require("visitor.read")),
) -> LeadEmailPage:
    return await service.lead_emails(session, ctx, lead_id, params)
