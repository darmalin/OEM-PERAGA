import uuid
from collections import Counter
from datetime import UTC, datetime, time, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit, idempotency, outbox
from app.core.authorization import AuthContext, Scope
from app.core.config import get_settings
from app.core.db import new_id
from app.core.errors import NotFound, PermissionDenied, ValidationFailed, check_version
from app.core.pagination import Page
from app.modules.exhibitions import service as exhibitions_service
from app.modules.identity import service as identity_service
from app.modules.telemarketing import repository as repo
from app.modules.telemarketing.models import (
    AssignmentJob,
    LeadAssignmentHistory,
    VisitorCallActivity,
    VisitorFollowup,
    VisitorFollowupChange,
    VisitorVerification,
)
from app.modules.telemarketing.rules import (
    AssignmentMethod,
    FollowupAction,
    FollowupStatus,
    allowed_call_results,
    round_robin,
    telemarketing_status,
)
from app.modules.telemarketing.schemas import (
    MAX_ASSIGN,
    MAX_SYNC_ASSIGN,
    AgentOut,
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
from app.modules.visitors import service as visitors_service
from app.modules.visitors.schemas import LeadListItem, LeadOut

if TYPE_CHECKING:
    from app.modules.visitors.models import VisitorLead

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


# --- calls ---------------------------------------------------------------------------------


async def _followup_assignee(
    session: AsyncSession,
    ctx: AuthContext,
    scope: Scope,
    requested: uuid.UUID | None,
    lead_owner: uuid.UUID | None,
) -> uuid.UUID:
    target = requested or lead_owner or ctx.user.id
    if target == ctx.user.id:
        return target
    teams = _agent_teams(ctx, scope, None)
    allowed = (
        {
            u.id
            for u, _ in await identity_service.eligible_users(
                session, scope.edition_id, AGENT_PERMISSION, teams
            )
        }
        if teams is None or teams
        else set()
    )
    if target not in allowed:
        raise ValidationFailed(fields={"assigned_to": "This user cannot take follow-ups here."})
    return target


async def _new_followup(
    session: AsyncSession,
    lead: "VisitorLead",
    assigned_to: uuid.UUID,
    due_at: datetime,
    note: str | None,
    call_id: uuid.UUID | None,
    actor: uuid.UUID,
) -> VisitorFollowup:
    followup = VisitorFollowup(
        edition_id=lead.edition_id,
        visitor_lead_id=lead.id,
        assigned_to=assigned_to,
        due_at=due_at,
        status=FollowupStatus.OPEN,
        note=note,
        created_from_call_id=call_id,
        created_by=actor,
        updated_by=actor,
    )
    session.add(followup)
    await session.flush()
    session.add(
        VisitorFollowupChange(
            followup_id=followup.id,
            edition_id=lead.edition_id,
            action=FollowupAction.CREATE,
            new_due_at=due_at,
            note=note,
            actor_user_id=actor,
        )
    )
    await audit.record(
        session,
        entity_type="followup",
        entity_id=followup.id,
        action="create",
        after={"visitor_lead_id": lead.id, "assigned_to": assigned_to, "due_at": due_at},
        edition_id=lead.edition_id,
    )
    return followup


def _not_future(value: datetime, field: str) -> None:
    if value > datetime.now(UTC) + timedelta(minutes=5):
        raise ValidationFailed(fields={field: "Cannot be in the future."})


async def log_call(
    session: AsyncSession, ctx: AuthContext, lead_id: uuid.UUID, data: CallIn
) -> CallLoggedOut:
    """Record a call attempt; the lead row lock serializes attempt numbers (spec 6.3)."""
    allowed = allowed_call_results(get_settings().call_results_extra)
    if data.call_result not in allowed:
        raise ValidationFailed(fields={"call_result": f"Use one of: {', '.join(allowed)}."})
    scope = await visitors_service.scope_for_lead(session, ctx, lead_id)
    lead = await visitors_service.get_lead_entity(session, scope, lead_id, for_update=True)
    await exhibitions_service.ensure_writable(session, lead.edition_id)
    called_at = data.called_at or datetime.now(UTC)
    _not_future(called_at, "called_at")
    if data.next_followup_at is not None and data.next_followup_at <= called_at:
        raise ValidationFailed(fields={"next_followup_at": "Must be after the call."})

    call = VisitorCallActivity(
        edition_id=lead.edition_id,
        visitor_lead_id=lead.id,
        agent_id=ctx.user.id,
        attempt_number=lead.call_attempts + 1,
        call_result=data.call_result,
        called_at=called_at,
        duration_seconds=data.duration_seconds,
        notes=data.notes,
        next_followup_at=data.next_followup_at,
    )
    session.add(call)
    await session.flush()
    await audit.record(
        session,
        entity_type="call_activity",
        entity_id=call.id,
        action="create",
        after={
            "visitor_lead_id": lead.id,
            "attempt_number": call.attempt_number,
            "call_result": call.call_result,
            "called_at": called_at,
        },
        edition_id=lead.edition_id,
    )
    followup_id = None
    if data.next_followup_at is not None:
        assignee = await _followup_assignee(session, ctx, scope, None, lead.lead_owner_id)
        followup = await _new_followup(
            session, lead, assignee, data.next_followup_at, None, call.id, ctx.user.id
        )
        followup_id = followup.id

    # Status is always recomputed from the stored history, never incremented.
    results = await repo.call_results(session, lead.id)
    summary = {
        "telemarketing_status": telemarketing_status(results),
        "call_attempts": len(results),
        "last_call_at": max(called_at, lead.last_call_at or called_at),
        "next_followup_at": await repo.earliest_open_followup(session, lead.id),
    }
    lead = await visitors_service.apply_changes(session, lead, summary, action="call")
    return CallLoggedOut(
        call=CallOut.model_validate(call),
        telemarketing_status=lead.telemarketing_status,
        call_attempts=lead.call_attempts,
        followup_id=followup_id,
    )


async def list_calls(session: AsyncSession, ctx: AuthContext, lead_id: uuid.UUID) -> list[CallOut]:
    scope = await visitors_service.scope_for_lead(session, ctx, lead_id)
    await visitors_service.get_lead_entity(session, scope, lead_id)
    return [CallOut.model_validate(c) for c in await repo.calls_for_lead(session, scope, lead_id)]


# --- verification --------------------------------------------------------------------------


async def update_verification(
    session: AsyncSession, ctx: AuthContext, lead_id: uuid.UUID, data: VerificationIn
) -> LeadOut:
    """Partial verification save with history (spec 6.4)."""
    scope = await visitors_service.scope_for_lead(session, ctx, lead_id)
    lead = await visitors_service.get_lead_entity(session, scope, lead_id, for_update=True)
    check_version(lead.version, data.version)
    await exhibitions_service.ensure_writable(session, lead.edition_id)
    changes = data.model_dump(exclude_unset=True, exclude={"version"})
    if changes.get("is_valid_lead") and changes.get("is_invalid"):
        raise ValidationFailed(
            fields={"is_valid_lead": "Valid Lead and Invalid cannot both be set."}
        )
    # Radio semantics: choosing one side clears the other.
    if changes.get("is_valid_lead"):
        changes.setdefault("is_invalid", False)
    if changes.get("is_invalid"):
        changes.setdefault("is_valid_lead", False)
    for flag in ("is_valid_lead", "is_invalid", "b2b_matching"):
        if flag in changes and changes[flag] is None:
            changes[flag] = False
    if not changes:
        return await visitors_service.lead_out(session, lead)
    changes["verification_updated_at"] = datetime.now(UTC)
    lead = await visitors_service.apply_changes(session, lead, changes, action="verify")
    session.add(
        VisitorVerification(
            edition_id=lead.edition_id,
            visitor_lead_id=lead.id,
            is_valid_lead=lead.is_valid_lead,
            is_invalid=lead.is_invalid,
            attend=lead.attend,
            b2b_matching=lead.b2b_matching,
            buyer_type=lead.buyer_type,
            changed_by=ctx.user.id,
        )
    )
    await session.flush()
    return await visitors_service.lead_out(session, lead)


async def list_verifications(
    session: AsyncSession, ctx: AuthContext, lead_id: uuid.UUID
) -> list[VerificationOut]:
    scope = await visitors_service.scope_for_lead(session, ctx, lead_id)
    await visitors_service.get_lead_entity(session, scope, lead_id)
    rows = await repo.verifications_for_lead(session, scope, lead_id)
    return [VerificationOut.model_validate(v) for v in rows]


# --- follow-ups ----------------------------------------------------------------------------


async def _followup_out(
    session: AsyncSession, scope: Scope, rows: list[VisitorFollowup]
) -> list[FollowupOut]:
    labels = await visitors_service.lead_labels(session, scope, [f.visitor_lead_id for f in rows])
    out = []
    for f in rows:
        item = FollowupOut.model_validate(f)
        item.lead_first_name, item.lead_registration_code = labels.get(
            f.visitor_lead_id, (None, None)
        )
        out.append(item)
    return out


async def create_followup(
    session: AsyncSession, ctx: AuthContext, lead_id: uuid.UUID, data: FollowupIn
) -> FollowupOut:
    """Schedule a follow-up on a lead."""
    scope = await visitors_service.scope_for_lead(session, ctx, lead_id)
    lead = await visitors_service.get_lead_entity(session, scope, lead_id, for_update=True)
    await exhibitions_service.ensure_writable(session, lead.edition_id)
    if data.due_at <= datetime.now(UTC):
        raise ValidationFailed(fields={"due_at": "Must be in the future."})
    assignee = await _followup_assignee(session, ctx, scope, data.assigned_to, lead.lead_owner_id)
    followup = await _new_followup(
        session, lead, assignee, data.due_at, data.note, None, ctx.user.id
    )
    await visitors_service.apply_changes(
        session,
        lead,
        {"next_followup_at": await repo.earliest_open_followup(session, lead.id)},
        action="followup",
    )
    return (await _followup_out(session, scope, [followup]))[0]


async def update_followup(
    session: AsyncSession, ctx: AuthContext, followup_id: uuid.UUID, data: FollowupUpdateIn
) -> FollowupOut:
    """Reschedule, complete, or cancel an open follow-up; history keeps every change."""
    followup = await repo.get_followup(session, followup_id)
    if followup is None:
        raise NotFound("Follow-up not found.")
    try:
        scope = ctx.scope_for(followup.edition_id)
    except NotFound as e:
        raise NotFound("Follow-up not found.") from e
    visible = followup.assigned_to == ctx.user.id or (
        followup.visitor_lead_id
        in set(
            await visitors_service.scoped_lead_ids(
                session, scope, [followup.visitor_lead_id], None, 1
            )
        )
    )
    if not visible:
        raise NotFound("Follow-up not found.")
    check_version(followup.version, data.version)
    if followup.status != FollowupStatus.OPEN:
        raise ValidationFailed("Only open follow-ups can change.", code="FOLLOWUP_CLOSED")
    lead = await visitors_service.get_lead_internal(
        session, followup.edition_id, followup.visitor_lead_id, for_update=True
    )
    await exhibitions_service.ensure_writable(session, lead.edition_id)

    old_due = followup.due_at
    now = datetime.now(UTC)
    match data.action:
        case "RESCHEDULE":
            assert data.due_at is not None  # noqa: S101 - schema validator
            if data.due_at <= now:
                raise ValidationFailed(fields={"due_at": "Must be in the future."})
            followup.due_at = data.due_at
            action = FollowupAction.RESCHEDULE
        case "DONE":
            followup.status = FollowupStatus.DONE
            followup.completed_at = now
            action = FollowupAction.DONE
        case _:
            followup.status = FollowupStatus.CANCELLED
            followup.completed_at = now
            action = FollowupAction.CANCEL
    followup.updated_by = ctx.user.id
    await session.flush()
    session.add(
        VisitorFollowupChange(
            followup_id=followup.id,
            edition_id=followup.edition_id,
            action=action,
            old_due_at=old_due,
            new_due_at=followup.due_at,
            note=data.note,
            actor_user_id=ctx.user.id,
        )
    )
    await audit.record(
        session,
        entity_type="followup",
        entity_id=followup.id,
        action=action.lower(),
        before={"status": FollowupStatus.OPEN, "due_at": old_due},
        after={"status": followup.status, "due_at": followup.due_at},
        edition_id=followup.edition_id,
    )
    await visitors_service.apply_changes(
        session,
        lead,
        {"next_followup_at": await repo.earliest_open_followup(session, lead.id)},
        action="followup",
    )
    await session.refresh(followup)
    return (await _followup_out(session, scope, [followup]))[0]


async def followup_history(
    session: AsyncSession, ctx: AuthContext, followup_id: uuid.UUID
) -> list[FollowupChangeOut]:
    followup = await repo.get_followup(session, followup_id)
    if followup is None:
        raise NotFound("Follow-up not found.")
    scope = ctx.scope_for(followup.edition_id)
    if followup.assigned_to != ctx.user.id and not await visitors_service.scoped_lead_ids(
        session, scope, [followup.visitor_lead_id], None, 1
    ):
        raise NotFound("Follow-up not found.")
    return [
        FollowupChangeOut.model_validate(c)
        for c in await repo.followup_changes(session, followup_id)
    ]


def _bucket_range(
    bucket: str, timezone: str, now: datetime
) -> tuple[datetime | None, datetime | None]:
    """Today/overdue/upcoming in the edition's local calendar."""
    tz = ZoneInfo(timezone)
    local_midnight = datetime.combine(now.astimezone(tz).date(), time.min, tzinfo=tz)
    start, end = (
        local_midnight.astimezone(UTC),
        (local_midnight + timedelta(days=1)).astimezone(UTC),
    )
    return {
        "today": (start, end),
        "overdue": (None, now),
        "upcoming": (end, None),
    }.get(bucket, (None, None))


async def list_followups(
    session: AsyncSession, ctx: AuthContext, params: FollowupListParams
) -> Page[FollowupOut]:
    """Follow-ups in scope (or assigned to the caller), bucketed in edition local time."""
    scope = ctx.scope_for(params.edition_id)
    edition = await exhibitions_service.get_edition_by_id(session, params.edition_id)
    assert edition is not None  # noqa: S101 - scope_for passed
    due_from, due_to = _bucket_range(params.bucket, edition.timezone, datetime.now(UTC))
    rows, total = await repo.list_followups(
        session,
        visitors_service.visible_lead_ids(scope),
        scope,
        params.status,
        due_from,
        due_to,
        params.assigned_to,
        params.offset,
        params.page_size,
    )
    return Page(
        items=await _followup_out(session, scope, list(rows)),
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def my_queue(
    session: AsyncSession, ctx: AuthContext, params: QueueParams
) -> Page[LeadListItem]:
    """ "My Calls": the caller's leads, follow-ups due first, then NEW."""
    if params.agent_id not in (None, ctx.user.id):
        raise ValidationFailed(fields={"agent_id": "Use the team queue for other agents."})
    scope = ctx.scope_for(params.edition_id)
    return await visitors_service.owner_queue(
        session, scope, ctx.user.id, params.page, params.page_size
    )


async def team_queue(
    session: AsyncSession, ctx: AuthContext, params: QueueParams
) -> Page[LeadListItem]:
    """Manager view of one agent's queue, limited to the manager's scope."""
    if params.agent_id is None:
        raise ValidationFailed(fields={"agent_id": "Required."})
    scope = ctx.scope_for(params.edition_id)
    return await visitors_service.owner_queue(
        session, scope, params.agent_id, params.page, params.page_size
    )


# --- reminders (D4) ------------------------------------------------------------------------


async def queue_followup_reminders(session: AsyncSession) -> int:
    """Claim a reminder per follow-up due soon; the dedup key is followup:{id}:{due_at}."""
    s = get_settings()
    if not s.followup_reminders_enabled:
        return 0
    until = datetime.now(UTC) + timedelta(minutes=s.followup_reminder_lead_minutes)
    queued = 0
    for followup in await repo.due_for_reminder(session, until):
        key = f"followup:{followup.id}:{followup.due_at.isoformat()}"
        reminder_id = await repo.claim_reminder(session, key, followup.id)
        if reminder_id is None:
            continue
        await outbox.enqueue(
            session,
            "followup.reminder_due",
            "telemarketing.send_followup_reminder",
            {"reminder_id": str(reminder_id)},
            queue="email",
        )
        queued += 1
    return queued
