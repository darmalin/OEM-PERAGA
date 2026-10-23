from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require
from app.core.db import get_session
from app.modules.reporting import service
from app.modules.reporting.schemas import (
    DashboardOptions,
    DashboardOut,
    DashboardParams,
    EmailReportOut,
    Report,
    ReportParams,
)

router = APIRouter(tags=["reports"])


@router.get("/reports/visitors", response_model=Report)
async def visitor_report(
    params: Annotated[ReportParams, Query()],
    session: Annotated[AsyncSession, Depends(get_session)],
    ctx: AuthContext = Depends(require("report.view")),
) -> Report:
    """Dashboard and report numbers. Poll it for near-real-time data (spec 11)."""
    return await service.visitor_report(session, ctx, params)


@router.get("/reports/dashboard", response_model=DashboardOut)
async def dashboard(
    params: Annotated[DashboardParams, Query()],
    session: Annotated[AsyncSession, Depends(get_session)],
    ctx: AuthContext = Depends(require("report.view")),
) -> DashboardOut:
    """Dashboard tabs: totals, per day, and per day by edition, source, or user."""
    return await service.dashboard(session, ctx, params)


@router.get("/reports/dashboard/email", response_model=EmailReportOut)
async def email_report(
    params: Annotated[DashboardParams, Query()],
    session: Annotated[AsyncSession, Depends(get_session)],
    ctx: AuthContext = Depends(require("report.view")),
) -> EmailReportOut:
    """Email Report tab: emails about leads (QR, reminders) in the caller's editions."""
    return await service.email_report(session, ctx, params)


@router.get("/reports/dashboard/options", response_model=DashboardOptions)
async def dashboard_options(
    session: Annotated[AsyncSession, Depends(get_session)],
    ctx: AuthContext = Depends(require("report.view")),
) -> DashboardOptions:
    return await service.dashboard_options(session, ctx)
