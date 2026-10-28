"""Reports (spec 11). Numbers come from the database only; every report applies the scope."""

import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, Scope
from app.core.config import get_settings
from app.core.errors import NotFound, PermissionDenied
from app.modules.exhibitions import service as exhibitions_service
from app.modules.reporting import repository as repo
from app.modules.reporting.repository import Window
from app.modules.reporting.schemas import (
    EDITION_REPORTS,
    AgentRow,
    AgentsReport,
    AttendanceDay,
    AttendanceReport,
    CampaignDashboardOut,
    CampaignDashboardParams,
    CampaignDay,
    CampaignFunnel,
    CampaignRow,
    CampaignTotals,
    Count,
    DashboardKey,
    DashboardOption,
    DashboardOptions,
    DashboardOut,
    DashboardParams,
    DashboardRow,
    EmailReportDay,
    EmailReportJob,
    EmailReportOut,
    EmailReportTotals,
    EmailsReport,
    GateRow,
    GatesReport,
    HourRow,
    ImportsReport,
    LeadsReport,
    RegistrationReport,
    Report,
    ReportParams,
    ReportType,
    TelemarketingReport,
    VerificationReport,
)
from app.modules.visitors import service as visitors_service
from app.modules.visitors.schemas import LeadFilters

PERMISSION = "report.view"


def local_window(date_from: date | None, date_to: date | None, timezone: str) -> Window:
    """Inclusive event-local dates to a half-open UTC window."""
    tz = ZoneInfo(timezone)
    start = datetime.combine(date_from, time.min, tz).astimezone(UTC) if date_from else None
    end = (
        datetime.combine(date_to + timedelta(days=1), time.min, tz).astimezone(UTC)
        if date_to
        else None
    )
    return start, end


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def _counts(rows: list[tuple[Any, int]]) -> list[Count]:
    return [Count(key=None if k is None else str(k), count=c) for k, c in rows]


def lead_filters(params: ReportParams) -> LeadFilters:
    return LeadFilters.model_validate(
        params.model_dump(include=set(LeadFilters.model_fields), exclude_unset=True)
    )


async def build(session: AsyncSession, scope: Scope, params: ReportParams, timezone: str) -> Report:
    """Compute one report for an already-resolved scope (API and export worker)."""
    now = datetime.now(UTC)
    window = local_window(params.date_from, params.date_to, timezone)
    base: dict[str, Any] = {"edition_id": scope.edition_id, "generated_at": now}
    lead_ids = visitors_service.filtered_lead_ids(scope, lead_filters(params))

    match params.report:
        case ReportType.LEADS:
            total, new, assigned = await repo.lead_overview(session, lead_ids)
            return LeadsReport(
                **base,
                total=total,
                new=new,
                assigned=assigned,
                unassigned=total - assigned,
                by_source=_counts(await repo.leads_by(session, lead_ids, "source")),
                by_country=_counts(await repo.leads_by(session, lead_ids, "country")),
            )
        case ReportType.TELEMARKETING:
            attempts, answered = await repo.call_totals(session, lead_ids, window)
            today = datetime.now(ZoneInfo(timezone)).date()
            open_, due_today, overdue = await repo.followup_totals(
                session, lead_ids, local_window(today, today, timezone), now
            )
            return TelemarketingReport(
                **base,
                attempts=attempts,
                answered=answered,
                answer_rate=_rate(answered, attempts),
                leads_by_status=_counts(
                    await repo.leads_by(session, lead_ids, "telemarketing_status")
                ),
                followups_open=open_,
                followups_due_today=due_today,
                followups_overdue=overdue,
            )
        case ReportType.VERIFICATION:
            valid, invalid, undecided, b2b = await repo.verification_totals(session, lead_ids)
            return VerificationReport(
                **base,
                valid=valid,
                invalid=invalid,
                undecided=undecided,
                by_attend=_counts(await repo.leads_by(session, lead_ids, "attend")),
                by_buyer_type=_counts(await repo.leads_by(session, lead_ids, "buyer_type")),
                b2b_matching=b2b,
            )
        case ReportType.REGISTRATION:
            registered, not_registered, qr_active, qr_revoked = await repo.registration_totals(
                session, lead_ids
            )
            return RegistrationReport(
                **base,
                registered=registered,
                not_registered=not_registered,
                by_channel=_counts(await repo.registrations_by_channel(session, lead_ids)),
                qr_active=qr_active,
                qr_revoked=qr_revoked,
                emails_by_status=_counts(
                    await repo.emails_by_status_for_leads(session, lead_ids, window)
                ),
            )
        case ReportType.AGENTS:
            rows = await repo.agent_rows(session, scope.edition_id, lead_ids, window)
            return AgentsReport(
                **base,
                agents=[
                    AgentRow(
                        agent_id=agent_id,
                        full_name=name,
                        leads_owned=owned,
                        attempts=attempts,
                        answered=answered,
                        followups_total=f_total,
                        followups_done=f_done,
                        followup_completion=_rate(f_done, f_total),
                    )
                    for agent_id, name, owned, attempts, answered, f_total, f_done in rows
                ],
            )
        case ReportType.ATTENDANCE:
            total, valid, first, rejected, unique = await repo.attendance_totals(
                session, scope, params.gate_id, window
            )
            return AttendanceReport(
                **base,
                unique_event_visitors=unique,
                total_scans=total,
                valid_entries=valid,
                first_entries=first,
                repeat_entries=valid - first,
                rejected=rejected,
                by_day=[
                    AttendanceDay(
                        local_date=day,
                        unique_visitors=uniq,
                        first_entries=f,
                        repeat_entries=v - f,
                        total_scans=t,
                        rejected=r,
                    )
                    for day, uniq, f, v, t, r in await repo.attendance_by_day(
                        session, scope, params.gate_id, window
                    )
                ],
            )
        case ReportType.GATES:
            return GatesReport(
                **base,
                by_gate=[
                    GateRow(
                        gate_id=gid,
                        gate_code=code,
                        gate_name=name,
                        total_scans=t,
                        valid_entries=v,
                        rejected=r,
                    )
                    for gid, code, name, t, v, r in await repo.by_gate(
                        session, scope, params.gate_id, window
                    )
                ],
                by_hour=[
                    HourRow(local_date=day, hour=int(h), total_scans=t, valid_entries=v)
                    for day, h, t, v in await repo.by_hour(
                        session, scope, params.gate_id, window, timezone
                    )
                ],
            )
        case ReportType.IMPORTS:
            (jobs, processed, created, duplicate, invalid), statuses = await repo.import_totals(
                session, scope.edition_id, window
            )
            return ImportsReport(
                **base,
                jobs=jobs,
                by_status=_counts(statuses),
                processed=processed,
                created=created,
                duplicate=duplicate,
                invalid=invalid,
            )
        case ReportType.EMAILS:
            statuses = await repo.email_status_totals(session, scope.edition_id, window)
            return EmailsReport(
                **base, total=sum(c for _, c in statuses), by_status=_counts(statuses)
            )


def scope_for_report(ctx: AuthContext, params: ReportParams, permission: str) -> Scope:
    scope = ctx.scope_for(params.edition_id, permission)
    if params.report in EDITION_REPORTS and not scope.full_access:
        raise PermissionDenied("This report needs access to the whole edition.")
    return scope


async def edition_timezone(session: AsyncSession, edition_id: Any) -> str:
    edition = await exhibitions_service.get_edition_by_id(session, edition_id)
    if edition is None:
        raise NotFound("Edition not found.", code="EDITION_NOT_FOUND")
    return edition.timezone


async def visitor_report(session: AsyncSession, ctx: AuthContext, params: ReportParams) -> Report:
    """GET /reports/visitors."""
    scope = scope_for_report(ctx, params, PERMISSION)
    return await build(session, scope, params, await edition_timezone(session, params.edition_id))


# --- dashboard -------------------------------------------------------------------------------

_GROUP_KEYS = {
    "day_edition": "edition",
    "day_source": "source",
    "day_user": "user",
    "day_team": "team",
}
_CALL_METRICS = (
    "total",
    "answer",
    "non_answer",
    "recontacted",
    "retry_no_answer",
    "valid",
    "no_valid",
    "attend",
    "attend_sourcing",
    "under_consideration",
    "not_attend",
    "hang_up_immediately",
    "b2b_matching",
    "b_side",
    "c_side",
)


async def _dashboard_scopes(
    session: AsyncSession, ctx: AuthContext, edition_id: uuid.UUID | None
) -> tuple[list[Scope], str]:
    """Scopes the dashboard reads, and the timezone of its days."""
    if edition_id is not None:
        return [ctx.scope_for(edition_id, PERMISSION)], await edition_timezone(session, edition_id)
    scopes = await visitors_service.readable_scopes(session, ctx, PERMISSION)
    return scopes, get_settings().report_timezone


def _days(date_from: date, date_to: date) -> list[date]:
    return [date_from + timedelta(days=i) for i in range((date_to - date_from).days + 1)]


def _key(value: Any) -> str | None:
    return None if value is None else str(value)


async def dashboard(
    session: AsyncSession, ctx: AuthContext, params: DashboardParams
) -> DashboardOut:
    """GET /reports/dashboard: every tab of the dashboard (FEATURES/10 "Dashboard")."""
    scopes, timezone = await _dashboard_scopes(session, ctx, params.edition_id)
    visible = visitors_service.lead_visibility(scopes)
    window = local_window(params.date_from, params.date_to, timezone)
    by_day = params.group_by != "total"
    key = _GROUP_KEYS.get(params.group_by)
    f = repo.DashFilters(**params.model_dump(exclude={"date_from", "date_to", "group_by"}))
    calls = await repo.dashboard_calls(session, visible, f, window, timezone, by_day, key)
    leads = await repo.dashboard_leads(session, visible, f, window, timezone, by_day, key)

    rows: dict[tuple[date | None, str | None], DashboardRow] = {}

    def row(day: date | None, k: str | None) -> DashboardRow:
        return rows.setdefault((day, k), DashboardRow(day=day, key=k))

    for r in calls:
        target = row(r.get("day"), _key(r.get("key")))
        for metric in _CALL_METRICS:
            setattr(target, metric, int(r[metric]))
    for r in leads["added"]:
        row(r.get("day"), _key(r.get("key"))).added = int(r["n"])

    # Pending = created by the end of the day - first called by then, per key.
    base: dict[str | None, int] = {}
    for r in leads["created_before"]:
        base[_key(r.get("key"))] = base.get(_key(r.get("key")), 0) + int(r["n"])
    for r in leads["called_before"]:
        base[_key(r.get("key"))] = base.get(_key(r.get("key")), 0) - int(r["n"])
    change: dict[tuple[date | None, str | None], int] = {}
    for name, sign in (("added", 1), ("called", -1)):
        for r in leads[name]:
            at = (r.get("day"), _key(r.get("key")))
            change[at] = change.get(at, 0) + sign * int(r["n"])
    keys = set(base) | {k for _, k in change} | {k for _, k in rows}
    if by_day:
        for k in keys:
            running = base.get(k, 0)
            for day in _days(params.date_from, params.date_to):
                running += change.get((day, k), 0)
                if running or (day, k) in rows:
                    row(day, k).pending = running
    else:
        row(None, None).pending = base.get(None, 0) + change.get((None, None), 0)

    out_keys: list[DashboardKey] = []
    if key == "edition":
        summaries = await exhibitions_service.edition_summaries(
            session, {s.edition_id for s in scopes}
        )
        out_keys = [DashboardKey(id=str(e.id), label=e.code) for e in summaries]
    elif key == "source":
        sources = await visitors_service.list_lead_sources(session, include_inactive=True)
        out_keys = [DashboardKey(id=str(s.id), label=s.name) for s in sources]
        out_keys.append(DashboardKey(id=None, label="No source"))
    elif key == "team":
        found = {uuid.UUID(k) for k in keys if k}
        out_keys = [
            DashboardKey(id=str(team_id), label=name)
            for team_id, name in await repo.dashboard_teams(session)
            if team_id in found
        ]
        if any(k is None for k in keys):
            out_keys.append(DashboardKey(id=None, label="No team"))
    elif key == "user":
        found = {uuid.UUID(k) for k in keys if k}
        agents = await repo.dashboard_agents(session, {s.edition_id for s in scopes}, found)
        out_keys = [
            DashboardKey(id=str(i), label=name, group=group, editions=eds)
            for i, name, group, eds in agents
            if not params.user_id or i == params.user_id
        ]
        if any(k is None for k in keys):
            out_keys.append(DashboardKey(id=None, label="Unassigned"))

    ordered = sorted(rows.values(), key=lambda r: (r.day or date.min, r.key or ""))
    return DashboardOut(
        timezone=timezone,
        today=datetime.now(ZoneInfo(timezone)).date(),
        date_from=params.date_from,
        date_to=params.date_to,
        group_by=params.group_by,
        rows=ordered if by_day else [row(None, None)],
        keys=out_keys,
    )


async def dashboard_options(session: AsyncSession, ctx: AuthContext) -> DashboardOptions:
    scopes = await visitors_service.readable_scopes(session, ctx, PERMISSION)
    visible = visitors_service.lead_visibility(scopes)
    agents = await repo.dashboard_agents(session, {s.edition_id for s in scopes}, set())
    return DashboardOptions(
        countries=await repo.dashboard_countries(session, visible),
        users=[DashboardOption(id=str(i), label=n) for i, n, _, _ in agents],
        teams=[DashboardOption(id=str(i), label=n) for i, n in await repo.dashboard_teams(session)],
    )


async def email_report(
    session: AsyncSession, ctx: AuthContext, params: DashboardParams
) -> EmailReportOut:
    """GET /reports/dashboard/email: the Email Report tab."""
    scopes, timezone = await _dashboard_scopes(session, ctx, params.edition_id)
    visible = visitors_service.lead_visibility(scopes)
    window = local_window(params.date_from, params.date_to, timezone)
    today = datetime.now(ZoneInfo(timezone)).date()
    f = repo.DashFilters(**params.model_dump(exclude={"date_from", "date_to", "group_by"}))
    totals = await repo.email_report_totals(
        session, visible, f, window, local_window(today, today, timezone)
    )
    by_day = {
        r["day"]: r for r in await repo.email_report_days(session, visible, f, window, timezone)
    }

    def job(row: Any) -> EmailReportJob:
        j, name = row
        return EmailReportJob(
            id=j.id,
            kind=j.kind,
            recipient=j.recipient,
            lead_name=name,
            visitor_lead_id=j.visitor_lead_id,
            status=j.status,
            attempts=j.attempts,
            queued_at=j.queued_at,
            error_summary=j.error_summary,
        )

    return EmailReportOut(
        timezone=timezone,
        today=today,
        totals=EmailReportTotals(**totals),
        days=[
            EmailReportDay(day=d, **{k: int(v) for k, v in by_day.get(d, {}).items() if k != "day"})
            for d in _days(params.date_from, params.date_to)
        ],
        by_status=_counts(await repo.email_report_by_status(session, visible, f, window)),
        waiting=[
            job(r)
            for r in await repo.email_report_jobs(
                session, visible, f, ("QUEUED", "SENDING"), newest_first=False, limit=20
            )
        ],
        recent_failed=[
            job(r)
            for r in await repo.email_report_jobs(
                session, visible, f, ("FAILED",), newest_first=True, limit=10
            )
        ],
    )


# --- campaign dashboard (Marketing menu) ---------------------------------------------------


async def campaign_dashboard(
    session: AsyncSession, ctx: AuthContext, params: CampaignDashboardParams
) -> CampaignDashboardOut:
    """Form opens and posts per campaign link (link-level counts, no personal data), and the
    funnel of the campaign leads the caller may see, from registered to checked in."""
    scope = ctx.scope_for(params.edition_id, "campaign.view")
    edition = await exhibitions_service.public_edition_info(session, params.edition_id)
    w = repo.CampaignWindow(
        edition_id=params.edition_id,
        link_id=params.campaign_link_id,
        date_from=params.date_from,
        date_to=params.date_to,
        timezone=edition.timezone,
    )
    visible = visitors_service.lead_visibility([scope])
    views = await repo.campaign_views(session, w)
    posts = await repo.campaign_submissions(session, w)
    funnel_rows = await repo.campaign_funnel(session, w, visible)

    totals = CampaignTotals(views=sum(views.values()))
    days: dict[date, CampaignDay] = {}
    for (day, _), n in views.items():
        days.setdefault(day, CampaignDay(day=day)).views += n
    per_link: dict[uuid.UUID, dict[str, int]] = {}
    for day, link, outcome, n in posts:
        stats = per_link.setdefault(link, {})
        stats[outcome] = stats.get(outcome, 0) + n
        if outcome == "CREATED":
            totals.registrations += n
            days.setdefault(day, CampaignDay(day=day)).registrations += n
        elif outcome == "DUPLICATE":
            totals.duplicates += n
        else:
            totals.bots += n
    if totals.views:
        totals.conversion = round(totals.registrations / totals.views, 4)

    funnel = CampaignFunnel()
    by_link: dict[uuid.UUID, tuple[int, ...]] = {}
    for link, *counts in funnel_rows:
        by_link[link] = tuple(counts)
        for name, n in zip(CampaignFunnel.model_fields, counts, strict=True):
            setattr(funnel, name, getattr(funnel, name) + n)

    link_views: dict[uuid.UUID, int] = {}
    for (_, link), n in views.items():
        link_views[link] = link_views.get(link, 0) + n
    names = await repo.campaign_link_names(session, params.edition_id)
    campaigns = [
        CampaignRow(
            id=link_id,
            name=name,
            views=link_views.get(link_id, 0),
            registrations=per_link.get(link_id, {}).get("CREATED", 0),
            valid=by_link.get(link_id, (0, 0, 0, 0, 0, 0))[3],
            checked_in=by_link.get(link_id, (0, 0, 0, 0, 0, 0))[5],
        )
        for link_id, name in names
        if params.campaign_link_id in (None, link_id)
    ]

    async def utm(field: str) -> list[Count]:
        return [
            Count(key=k, count=n) for k, n in await repo.campaign_utm(session, w, visible, field)
        ]

    return CampaignDashboardOut(
        timezone=edition.timezone,
        totals=totals,
        days=sorted(days.values(), key=lambda d: d.day),
        funnel=funnel,
        utm_source=await utm("utm_source"),
        utm_medium=await utm("utm_medium"),
        utm_campaign=await utm("utm_campaign"),
        campaigns=campaigns,
    )
