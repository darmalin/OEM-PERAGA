import uuid
from collections import Counter
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import idempotency, outbox
from app.core.authorization import AuthContext, Scope
from app.core.db import new_id
from app.core.errors import NotFound, PermissionDenied, ValidationFailed
from app.modules.exhibitions import service as exhibitions_service
from app.modules.identity import service as identity_service
from app.modules.telemarketing import repository as repo
from app.modules.telemarketing.models import AssignmentJob, LeadAssignmentHistory
from app.modules.telemarketing.rules import AssignmentMethod, round_robin
from app.modules.telemarketing.schemas import (
    MAX_ASSIGN,
    MAX_SYNC_ASSIGN,
    AgentOut,
    AssignmentAccepted,
    AssignmentHistoryOut,
    AssignmentIn,
    AssignmentJobOut,
    AssignmentResult,
)
from app.modules.visitors import service as visitors_service

AGENT_PERMISSION = "telemarketing.call"


# --- agents --------------------------------------------------------------------------------


def _agent_teams(
    ctx: AuthContext, scope: Scope, team_id: uuid.UUID | None
) -> set[uuid.UUID] | None:
    """Agents selectable by the caller: any in the edition with full scope, else own teams."""
    if team_id is not None:
        if not scope.full_access and team_id not in scope.team_ids:
            raise PermissionDenied("You can only assign within your teams.")
        return {team_id}
    if scope.full_access:
        return None
    return set(scope.team_ids)


async def assignable_agents(
    session: AsyncSession, ctx: AuthContext, edition_id: uuid.UUID, team_id: uuid.UUID | None
) -> list[AgentOut]:
    """Agents the caller may assign leads to in this edition."""
    scope = ctx.scope_for(edition_id)
    teams = _agent_teams(ctx, scope, team_id)
    if teams is not None and not teams:
        return []
    rows = await identity_service.eligible_users(session, edition_id, AGENT_PERMISSION, teams)
    return [AgentOut(id=u.id, full_name=u.full_name, email=u.email, team_ids=t) for u, t in rows]


async def _check_agents(
    session: AsyncSession, ctx: AuthContext, scope: Scope, data: AssignmentIn
) -> list[uuid.UUID]:
    allowed = {a.id for a in await assignable_agents(session, ctx, scope.edition_id, data.team_id)}
    bad = [a for a in data.agent_ids if a not in allowed]
    if bad:
        raise ValidationFailed(
            "Some agents cannot receive leads in this edition.",
            fields={"agent_ids": f"Not assignable: {', '.join(str(b) for b in bad)}"},
        )
    return sorted(set(data.agent_ids))


# --- assignment ----------------------------------------------------------------------------


async def assign(
    session: AsyncSession, ctx: AuthContext, data: AssignmentIn, idempotency_key: str | None
) -> AssignmentResult | AssignmentAccepted:
    """POST /visitor-leads/assignments: small batches inline, large ones in the worker."""
    claim_id = None
    if idempotency_key:
        claim_id, stored = await idempotency.claim(
            session, f"assignments:{ctx.user.id}", idempotency_key, data.model_dump(mode="json")
        )
        if stored is not None:
            if "job_id" in stored.response:
                return AssignmentAccepted.model_validate(stored.response)
            return AssignmentResult.model_validate(stored.response)

    scope = ctx.scope_for(data.edition_id)
    await exhibitions_service.ensure_writable(session, data.edition_id)
    await _check_agents(session, ctx, scope, data)
    lead_ids = await visitors_service.scoped_lead_ids(
        session, scope, data.lead_ids, data.filter, MAX_ASSIGN + 1
    )
    if data.lead_ids is not None and len(lead_ids) != len(set(data.lead_ids)):
        raise NotFound("Some leads were not found.", fields={"lead_ids": "Not found."})
    if len(lead_ids) > MAX_ASSIGN:
        raise ValidationFailed(f"At most {MAX_ASSIGN} leads per assignment.")
    if not lead_ids:
        raise ValidationFailed("No leads match.", fields={"lead_ids": "No leads."})

    result: AssignmentResult | AssignmentAccepted
    if len(lead_ids) > MAX_SYNC_ASSIGN:
        job = AssignmentJob(
            edition_id=data.edition_id,
            status="QUEUED",
            request={
                **data.model_dump(mode="json"),
                "lead_ids": [str(i) for i in lead_ids],
                "filter": None,
            },
            lead_count=len(lead_ids),
            created_by=ctx.user.id,
        )
        session.add(job)
        await session.flush()
        await outbox.enqueue(
            session, "assignment.requested", "telemarketing.run_assignment", {"job_id": str(job.id)}
        )
        result = AssignmentAccepted(job_id=job.id, status=job.status)
    else:
        result = await execute_assignment(session, ctx, scope, data, lead_ids)
    if claim_id is not None:
        await idempotency.store(session, claim_id, 200, result.model_dump(mode="json"))
    return result


async def execute_assignment(
    session: AsyncSession,
    ctx: AuthContext,
    scope: Scope,
    data: AssignmentIn,
    lead_ids: list[uuid.UUID],
) -> AssignmentResult:
    """Apply an assignment under locks: cursor first, then leads in ID order."""
    agents = sorted(set(data.agent_ids))
    cursor = None
    if data.method == AssignmentMethod.ROUND_ROBIN:
        cursor = await repo.lock_cursor(
            session, scope.edition_id, str(data.team_id) if data.team_id else "edition"
        )
    leads = {lead.id: lead for lead in await visitors_service.lock_leads(session, scope, lead_ids)}
    ordered = [i for i in lead_ids if i in leads]  # creation order, from the selection query

    if data.method == AssignmentMethod.ROUND_ROBIN:
        assert cursor is not None  # noqa: S101
        pairs, last = round_robin(ordered, agents, cursor.last_user_id)
        cursor.last_user_id = last
    else:
        pairs = [(lead_id, agents[0]) for lead_id in ordered]

    can_reassign = ctx.has("telemarketing.reassign", scope.edition_id)
    for lead_id, agent in pairs:
        owner = leads[lead_id].lead_owner_id
        if owner is not None and owner != agent and not can_reassign:
            raise PermissionDenied(
                "Changing the owner of an assigned lead needs telemarketing.reassign.",
                code="REASSIGN_NOT_ALLOWED",
            )

    batch_id = new_id()
    per_agent: Counter[str] = Counter()
    unchanged = 0
    for lead_id, agent in pairs:
        lead = leads[lead_id]
        if lead.lead_owner_id == agent:
            unchanged += 1
            continue
        session.add(
            LeadAssignmentHistory(
                edition_id=scope.edition_id,
                visitor_lead_id=lead.id,
                from_user_id=lead.lead_owner_id,
                to_user_id=agent,
                method=data.method,
                actor_user_id=ctx.user.id,
                batch_id=batch_id,
            )
        )
        await visitors_service.apply_changes(
            session, lead, {"lead_owner_id": agent}, action="assign"
        )
        per_agent[str(agent)] += 1
    await session.flush()
    return AssignmentResult(
        batch_id=batch_id,
        assigned=sum(per_agent.values()),
        unchanged=unchanged,
        per_agent=dict(per_agent),
    )


async def run_assignment_job(session: AsyncSession, job_id: uuid.UUID) -> str | None:
    """Worker: re-check the requester's current permissions, then apply."""
    job = await repo.get_job(session, job_id)
    if job is None or job.status not in ("QUEUED", "RUNNING"):
        return None
    job.status = "RUNNING"
    await session.commit()
    try:
        principal, grants = await identity_service.load_principal(session, job.created_by)
        if principal is None:
            raise PermissionDenied("Requester is no longer active.")
        ctx = AuthContext(user=principal, permission="visitor.assign", grants=tuple(grants))
        if not ctx.has("visitor.assign", job.edition_id):
            raise PermissionDenied()
        scope = ctx.scope_for(job.edition_id)
        data = AssignmentIn.model_validate(job.request)
        lead_ids = await visitors_service.scoped_lead_ids(
            session, scope, data.lead_ids, None, MAX_ASSIGN
        )
        from app.core.context import actor_id_var

        actor_id_var.set(principal.id)
        result = await execute_assignment(session, ctx, scope, data, lead_ids)
        job.status = "COMPLETED"
        job.result = result.model_dump(mode="json")
    except (PermissionDenied, NotFound, ValidationFailed) as e:
        await session.rollback()
        job = await repo.get_job(session, job_id)
        assert job is not None  # noqa: S101
        job.status = "FAILED"
        job.error_summary = e.message
    job.finished_at = datetime.now(UTC)
    await session.commit()
    return job.status


async def get_job(session: AsyncSession, ctx: AuthContext, job_id: uuid.UUID) -> AssignmentJobOut:
    edition_id = await repo.edition_of_job(session, job_id)
    if edition_id is None:
        raise NotFound("Assignment job not found.")
    ctx.scope_for(edition_id)
    job = await repo.get_job(session, job_id, edition_id)
    if job is None:
        raise NotFound("Assignment job not found.")
    return AssignmentJobOut.model_validate(job)


async def lead_assignment_history(
    session: AsyncSession, ctx: AuthContext, lead_id: uuid.UUID
) -> list[AssignmentHistoryOut]:
    """Assignment history of one lead (newest first)."""
    scope = await visitors_service.scope_for_lead(session, ctx, lead_id)
    await visitors_service.get_lead_entity(session, scope, lead_id)
    return [
        AssignmentHistoryOut.model_validate(h)
        for h in await repo.lead_history(session, scope, lead_id)
    ]
