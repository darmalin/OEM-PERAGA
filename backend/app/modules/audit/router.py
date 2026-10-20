from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require
from app.core.db import get_session
from app.core.pagination import Page
from app.modules.audit import service
from app.modules.audit.schemas import AuditLogOut, AuditLogParams

router = APIRouter(tags=["audit"])


@router.get("/audit-logs", response_model=Page[AuditLogOut])
async def list_audit_logs(
    params: Annotated[AuditLogParams, Query()],
    session: AsyncSession = Depends(get_session),
    ctx: AuthContext = Depends(require("audit_log.read")),
) -> Page[AuditLogOut]:
    return await service.list_logs(session, ctx, params)
