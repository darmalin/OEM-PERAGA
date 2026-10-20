from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require
from app.core.db import get_session
from app.modules.reporting import service
from app.modules.reporting.schemas import Report, ReportParams

router = APIRouter(tags=["reports"])


@router.get("/reports/visitors", response_model=Report)
async def visitor_report(
    params: Annotated[ReportParams, Query()],
    session: Annotated[AsyncSession, Depends(get_session)],
    ctx: AuthContext = Depends(require("report.view")),
) -> Report:
    """Dashboard and report numbers. Poll it for near-real-time data (spec 11)."""
    return await service.visitor_report(session, ctx, params)
