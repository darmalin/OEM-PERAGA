import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import idempotency
from app.core.authorization import AuthContext, require
from app.core.config import get_settings
from app.core.db import get_session
from app.core.pagination import Page
from app.modules.telemarketing import service
from app.modules.telemarketing.rules import allowed_call_results
from app.modules.telemarketing.schemas import (
    AgentOut,
    AgentParams,
    AssignmentAccepted,
    AssignmentHistoryOut,
    AssignmentIn,
    AssignmentJobOut,
    AssignmentResult,
    CallIn,
    CallLoggedOut,
    CallOut,
    FollowupChangeOut,
    FollowupIn,
    FollowupListParams,
    FollowupOut,
    FollowupUpdateIn,
    QueueParams,
    VerificationIn,
    VerificationOut,
)
from app.modules.visitors.schemas import LeadListItem, LeadOut

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


# --- calls, verification, follow-ups, queues ----------------------------------------------


@router.post(
    "/visitor-leads/{lead_id}/calls",
    response_model=CallLoggedOut,
    status_code=status.HTTP_201_CREATED,
)
async def log_call(
    lead_id: uuid.UUID,
    data: CallIn,
    session: Session,
    ctx: AuthContext = Depends(require("telemarketing.call")),
) -> CallLoggedOut:
    return await service.log_call(session, ctx, lead_id, data)


@router.get("/visitor-leads/{lead_id}/calls", response_model=list[CallOut])
async def list_calls(
    lead_id: uuid.UUID, session: Session, ctx: AuthContext = Depends(require("visitor.read"))
) -> list[CallOut]:
    return await service.list_calls(session, ctx, lead_id)


@router.patch("/visitor-leads/{lead_id}/verification", response_model=LeadOut)
async def update_verification(
    lead_id: uuid.UUID,
    data: VerificationIn,
    session: Session,
    ctx: AuthContext = Depends(require("visitor.verify")),
) -> LeadOut:
    return await service.update_verification(session, ctx, lead_id, data)


@router.get("/visitor-leads/{lead_id}/verifications", response_model=list[VerificationOut])
async def list_verifications(
    lead_id: uuid.UUID, session: Session, ctx: AuthContext = Depends(require("visitor.read"))
) -> list[VerificationOut]:
    return await service.list_verifications(session, ctx, lead_id)


@router.post(
    "/visitor-leads/{lead_id}/followups",
    response_model=FollowupOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_followup(
    lead_id: uuid.UUID,
    data: FollowupIn,
    session: Session,
    ctx: AuthContext = Depends(require("telemarketing.followup")),
) -> FollowupOut:
    return await service.create_followup(session, ctx, lead_id, data)


@router.get("/followups", response_model=Page[FollowupOut])
async def list_followups(
    session: Session,
    params: Annotated[FollowupListParams, Query()],
    ctx: AuthContext = Depends(require("telemarketing.followup")),
) -> Page[FollowupOut]:
    return await service.list_followups(session, ctx, params)


@router.get("/followups/{followup_id}", response_model=FollowupOut)
async def get_followup(
    followup_id: uuid.UUID,
    session: Session,
    ctx: AuthContext = Depends(require("telemarketing.followup")),
) -> FollowupOut:
    return await service.get_followup(session, ctx, followup_id)


@router.patch("/followups/{followup_id}", response_model=FollowupOut)
async def update_followup(
    followup_id: uuid.UUID,
    data: FollowupUpdateIn,
    session: Session,
    ctx: AuthContext = Depends(require("telemarketing.followup")),
) -> FollowupOut:
    return await service.update_followup(session, ctx, followup_id, data)


@router.get("/followups/{followup_id}/history", response_model=list[FollowupChangeOut])
async def followup_history(
    followup_id: uuid.UUID,
    session: Session,
    ctx: AuthContext = Depends(require("telemarketing.followup")),
) -> list[FollowupChangeOut]:
    return await service.followup_history(session, ctx, followup_id)


@router.get("/telemarketing/my-queue", response_model=Page[LeadListItem])
async def my_queue(
    session: Session,
    params: Annotated[QueueParams, Query()],
    ctx: AuthContext = Depends(require("telemarketing.call")),
) -> Page[LeadListItem]:
    return await service.my_queue(session, ctx, params)


@router.get("/telemarketing/team-queue", response_model=Page[LeadListItem])
async def team_queue(
    session: Session,
    params: Annotated[QueueParams, Query()],
    ctx: AuthContext = Depends(require("telemarketing.view_team")),
) -> Page[LeadListItem]:
    return await service.team_queue(session, ctx, params)


@router.get("/telemarketing/call-results", response_model=list[str])
async def call_results(_: AuthContext = Depends(require("telemarketing.call"))) -> list[str]:
    return allowed_call_results(get_settings().call_results_extra)
