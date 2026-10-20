import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import idempotency
from app.core.authorization import AuthContext, require
from app.core.db import get_session
from app.modules.telemarketing import service
from app.modules.telemarketing.schemas import (
    AgentOut,
    AgentParams,
    AssignmentAccepted,
    AssignmentHistoryOut,
    AssignmentIn,
    AssignmentJobOut,
    AssignmentResult,
)

router = APIRouter(tags=["telemarketing"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.post(
    "/visitor-leads/assignments",
    response_model=AssignmentResult | AssignmentAccepted,
    responses={202: {"model": AssignmentAccepted}},
)
async def assign_leads(
    data: AssignmentIn,
    response: Response,
    session: Session,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ctx: AuthContext = Depends(require("visitor.assign")),
) -> AssignmentResult | AssignmentAccepted:
    key = idempotency.validate_key(idempotency_key, required=False)
    result = await service.assign(session, ctx, data, key)
    if isinstance(result, AssignmentAccepted):
        response.status_code = status.HTTP_202_ACCEPTED
    return result


@router.get("/visitor-leads/assignments/jobs/{job_id}", response_model=AssignmentJobOut)
async def assignment_job(
    job_id: uuid.UUID, session: Session, ctx: AuthContext = Depends(require("visitor.assign"))
) -> AssignmentJobOut:
    return await service.get_job(session, ctx, job_id)


@router.get("/visitor-leads/assignable-agents", response_model=list[AgentOut])
async def assignable_agents(
    session: Session,
    params: Annotated[AgentParams, Query()],
    ctx: AuthContext = Depends(require("visitor.assign")),
) -> list[AgentOut]:
    return await service.assignable_agents(session, ctx, params.edition_id, params.team_id)


@router.get("/visitor-leads/{lead_id}/assignments", response_model=list[AssignmentHistoryOut])
async def lead_assignments(
    lead_id: uuid.UUID, session: Session, ctx: AuthContext = Depends(require("visitor.read"))
) -> list[AssignmentHistoryOut]:
    return await service.lead_assignment_history(session, ctx, lead_id)
