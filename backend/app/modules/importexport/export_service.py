"""Excel exports (spec 11): requested by API, built by the worker, downloaded by signed URL.

The worker re-resolves the requester's scope when it runs, so an export never contains
more than the requester may see at that moment.
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import structlog
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core import audit, outbox
from app.core.authorization import AuthContext, Scope
from app.core.config import get_settings
from app.core.context import Source, actor_id_var, source_var
from app.core.errors import NotFound
from app.core.excel import WorkbookWriter
from app.core.pagination import Page
from app.core.storage import get_storage, new_object_key
from app.modules.campaigns import service as campaigns_service
from app.modules.identity import service as identity_service
from app.modules.importexport.models import ExportJob
from app.modules.importexport.rules import EXPORT_COLUMNS, ExportKind, ExportStatus, display_value
from app.modules.importexport.schemas import (
    ExportJobOut,
    ExportListParams,
    ReportExportIn,
    VisitorExportIn,
)
from app.modules.reporting import service as reporting_service
from app.modules.visitors import service as visitors_service
from app.modules.visitors.schemas import LeadFilters

logger = structlog.get_logger("exports")

ENTITY = "export_job"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
BATCH = 1000
PERMISSION = {ExportKind.VISITORS: "visitor.export", ExportKind.REPORT: "report.export"}
# A RUNNING job older than this is treated as a crashed worker and failed by cleanup.
STALE_RUNNING = timedelta(hours=1)


# --- API -------------------------------------------------------------------------------------


async def _queue(
    session: AsyncSession,
    ctx: AuthContext,
    kind: ExportKind,
    edition_id: uuid.UUID,
    params: dict[str, Any],
) -> ExportJobOut:
    job = ExportJob(
        edition_id=edition_id,
        kind=kind,
        params=params,
        status=ExportStatus.QUEUED,
        requested_by=ctx.user.id,
    )
    session.add(job)
    await session.flush()
    await session.refresh(job)
    await outbox.enqueue(
        session, "export.requested", "importexport.run_export", {"job_id": str(job.id)}, "export"
    )
    await audit.record(
        session,
        entity_type=ENTITY,
        entity_id=job.id,
        action="requested",
        after={"kind": kind, "params": params},
        edition_id=edition_id,
    )
    return ExportJobOut.model_validate(job)


async def request_visitor_export(
    session: AsyncSession, ctx: AuthContext, data: VisitorExportIn
) -> ExportJobOut:
    """POST /exports/visitors (visitor.export)."""
    ctx.scope_for(data.edition_id, PERMISSION[ExportKind.VISITORS])
    params = data.model_dump(mode="json", exclude_unset=True, exclude={"edition_id"})
    return await _queue(session, ctx, ExportKind.VISITORS, data.edition_id, params)


async def request_report_export(
    session: AsyncSession, ctx: AuthContext, data: ReportExportIn
) -> ExportJobOut:
    """POST /exports/reports (report.export)."""
    reporting_service.scope_for_report(ctx, data, PERMISSION[ExportKind.REPORT])
    params = data.model_dump(mode="json", exclude_unset=True, exclude={"edition_id"})
    params["report"] = data.report.value
    return await _queue(session, ctx, ExportKind.REPORT, data.edition_id, params)


async def list_exports(
    session: AsyncSession, ctx: AuthContext, params: ExportListParams
) -> Page[ExportJobOut]:
    """GET /exports: own jobs, or every job of the edition with edition-wide export rights."""
    kinds = [k for k, perm in PERMISSION.items() if ctx.has(perm, params.edition_id)]
    scopes = [ctx.scope_for(params.edition_id, PERMISSION[k]) for k in kinds]
    if not scopes:
        raise NotFound("Edition not found.", code="EDITION_NOT_FOUND")
    stmt = select(ExportJob).where(
        ExportJob.edition_id == params.edition_id, ExportJob.kind.in_(kinds)
    )
    if not any(s.full_access for s in scopes):
        stmt = stmt.where(ExportJob.requested_by == ctx.user.id)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = await session.scalars(
        stmt.order_by(ExportJob.created_at.desc()).offset(params.offset).limit(params.page_size)
    )
    return Page(
        items=[ExportJobOut.model_validate(j) for j in rows],
        total=int(total or 0),
        page=params.page,
        page_size=params.page_size,
    )


async def _scoped_export(session: AsyncSession, ctx: AuthContext, job_id: uuid.UUID) -> ExportJob:
    """The requester, or anyone with edition-wide export rights; 404 for everyone else."""
    job = await session.get(ExportJob, job_id)
    if job is None:
        raise NotFound("Export not found.")
    try:
        scope = ctx.scope_for(job.edition_id, PERMISSION[ExportKind(job.kind)])
    except NotFound as e:
        raise NotFound("Export not found.") from e
    if job.requested_by != ctx.user.id and not scope.full_access:
        raise NotFound("Export not found.")
    return job


async def get_export(session: AsyncSession, ctx: AuthContext, job_id: uuid.UUID) -> ExportJobOut:
    """GET /exports/{id}. The download link points at the API, which streams the file."""
    job = await _scoped_export(session, ctx, job_id)
    out = ExportJobOut.model_validate(job)
    if job.status == ExportStatus.COMPLETED and job.object_key and job.file_name:
        out.download_url = f"/api/v1/exports/{job.id}/file"
    return out


async def export_file(
    session: AsyncSession, ctx: AuthContext, job_id: uuid.UUID
) -> tuple[Iterator[bytes], str]:
    """(chunks, file name) of a finished export. spec 11: every download is audited."""
    job = await _scoped_export(session, ctx, job_id)
    if job.status != ExportStatus.COMPLETED or not job.object_key or not job.file_name:
        raise NotFound("This export has no file.")
    try:
        chunks = await run_in_threadpool(
            get_storage().stream, get_settings().s3_bucket_exports, job.object_key
        )
    except FileNotFoundError as e:
        raise NotFound("The export file is no longer available. Request it again.") from e
    await audit.record(
        session,
        entity_type=ENTITY,
        entity_id=job.id,
        action="download",
        after={"file_name": job.file_name},
        edition_id=job.edition_id,
    )
    return chunks, job.file_name


# --- worker ----------------------------------------------------------------------------------


async def _claim(session: AsyncSession, job_id: uuid.UUID) -> ExportJob | None:
    """QUEUED -> RUNNING in one statement, so two workers never build the same file."""
    claimed = await session.scalar(
        update(ExportJob)
        .where(ExportJob.id == job_id, ExportJob.status == ExportStatus.QUEUED)
        .values(status=ExportStatus.RUNNING, started_at=datetime.now(UTC))
        .returning(ExportJob.id)
    )
    await session.commit()
    return await session.get(ExportJob, job_id) if claimed else None


async def _requester_scope(session: AsyncSession, job: ExportJob) -> Scope:
    user, grants = await identity_service.load_principal(session, job.requested_by)
    if user is None:
        raise PermissionError("The requester is no longer active.")
    permission = PERMISSION[ExportKind(job.kind)]
    ctx = AuthContext(user=user, permission=permission, grants=tuple(grants))
    try:
        return ctx.scope_for(job.edition_id, permission)
    except NotFound as e:
        raise PermissionError("The requester no longer has export access.") from e


def _local(value: Any, tz: ZoneInfo) -> Any:
    # Excel has no time zones: write event-local wall time.
    if isinstance(value, datetime):
        return value.astimezone(tz).replace(tzinfo=None)
    return value


async def _visitor_sheet(
    session: AsyncSession, job: ExportJob, scope: Scope, writer: WorkbookWriter, tz: ZoneInfo
) -> int:
    filters = LeadFilters.model_validate(job.params)
    custom = [
        d
        for d in await visitors_service.custom_field_definitions(session, job.edition_id)
        if d.in_export
    ]
    writer.sheet(
        "Visitor Leads", [label for _, label in EXPORT_COLUMNS] + [d.label for d in custom]
    )
    campaigns = await campaigns_service.link_names(session, job.edition_id)
    after: tuple[datetime, uuid.UUID] | None = None
    count = 0
    while batch := await visitors_service.export_batch(session, scope, filters, after, BATCH):
        for lead, owner in batch:
            computed = {
                "lead_owner": owner,
                "campaign": campaigns.get(lead.campaign_link_id) if lead.campaign_link_id else None,
            }
            row = [
                _local(
                    display_value(
                        field, computed[field] if field in computed else getattr(lead, field)
                    ),
                    tz,
                )
                for field, _ in EXPORT_COLUMNS
            ]
            row += [display_value(d.field_key, lead.custom_fields.get(d.field_key)) for d in custom]
            writer.append(row)
        count += len(batch)
        last = batch[-1][0]
        after = (last.created_at, last.id)
    return count


def _report_sheets(report: BaseModel, writer: WorkbookWriter) -> int:
    """Summary sheet of scalar numbers, then one sheet per breakdown list."""
    data = report.model_dump(mode="json")
    writer.sheet("Summary", ["Metric", "Value"])
    lists: dict[str, list[dict[str, Any]]] = {}
    for key, value in data.items():
        if isinstance(value, list):
            lists[key] = value
        else:
            writer.append([key.replace("_", " ").capitalize(), value])
    rows = 0
    for key, items in lists.items():
        headers = list(items[0]) if items else ["(no rows)"]
        writer.sheet(
            key.replace("_", " ").capitalize(), [h.replace("_", " ").capitalize() for h in headers]
        )
        for item in items:
            writer.append([item[h] for h in headers])
        rows += len(items)
    return rows


async def run_export(session: AsyncSession, job_id: uuid.UUID) -> ExportStatus | None:
    """Build the workbook, store it, and mark the job. Safe to call twice."""
    job = await _claim(session, job_id)
    if job is None:
        return None
    source_var.set(Source.WORKER)
    actor_id_var.set(job.requested_by)
    try:
        scope = await _requester_scope(session, job)
        timezone = await reporting_service.edition_timezone(session, job.edition_id)
        tz = ZoneInfo(timezone)
        writer = WorkbookWriter()
        if job.kind == ExportKind.VISITORS:
            rows = await _visitor_sheet(session, job, scope, writer, tz)
            stem = "visitor-leads"
        else:
            params = ReportExportIn.model_validate({**job.params, "edition_id": job.edition_id})
            report = await reporting_service.build(session, scope, params, timezone)
            rows = _report_sheets(report, writer)
            stem = f"report-{params.report.value.lower()}"
        data = writer.to_bytes()
        key = new_object_key(".xlsx")
        get_storage().put(get_settings().s3_bucket_exports, key, data, XLSX)
    except (PermissionError, ValidationError) as e:
        return await _finish(session, job_id, ExportStatus.FAILED, error=str(e)[:500])
    except Exception:
        logger.exception("export_failed", job_id=str(job_id))
        return await _finish(session, job_id, ExportStatus.FAILED, error="Export failed.")
    now = datetime.now(UTC)
    return await _finish(
        session,
        job_id,
        ExportStatus.COMPLETED,
        values={
            "row_count": rows,
            "file_name": f"{stem}-{now.astimezone(tz):%Y%m%d-%H%M}.xlsx",
            "file_size": len(data),
            "object_key": key,
            "expires_at": now + timedelta(seconds=get_settings().export_ttl_seconds),
        },
    )


async def _finish(
    session: AsyncSession,
    job_id: uuid.UUID,
    status: ExportStatus,
    *,
    error: str | None = None,
    values: dict[str, Any] | None = None,
) -> ExportStatus:
    await session.rollback()
    job = await session.get(ExportJob, job_id, populate_existing=True)
    assert job is not None  # noqa: S101 - claimed above
    job.status = status
    job.finished_at = datetime.now(UTC)
    job.error_summary = error
    for key, value in (values or {}).items():
        setattr(job, key, value)
    await audit.record(
        session,
        entity_type=ENTITY,
        entity_id=job.id,
        action="completed" if status == ExportStatus.COMPLETED else "failed",
        after={"status": status, "row_count": job.row_count, "error": error},
        edition_id=job.edition_id,
    )
    await session.commit()
    return status


async def cleanup(session: AsyncSession) -> int:
    """Delete expired files and fail jobs stuck in RUNNING. Returns jobs changed."""
    now = datetime.now(UTC)
    expired = list(
        await session.scalars(
            select(ExportJob)
            .where(ExportJob.status == ExportStatus.COMPLETED, ExportJob.expires_at < now)
            .with_for_update(skip_locked=True)
        )
    )
    for job in expired:
        if job.object_key:
            get_storage().delete(get_settings().s3_bucket_exports, job.object_key)
        job.status = ExportStatus.EXPIRED
        job.object_key = None
    stale = await session.execute(
        update(ExportJob)
        .where(ExportJob.status == ExportStatus.RUNNING, ExportJob.started_at < now - STALE_RUNNING)
        .values(status=ExportStatus.FAILED, finished_at=now, error_summary="Worker stopped.")
    )
    await session.commit()
    return len(expired) + int(stale.rowcount or 0)  # type: ignore[attr-defined]
