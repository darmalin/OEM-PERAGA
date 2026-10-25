import json
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import structlog
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core import audit, outbox
from app.core.authorization import AuthContext
from app.core.config import get_settings
from app.core.context import Source, actor_id_var, source_var
from app.core.db import new_id
from app.core.errors import AppError, NotFound, PermissionDenied, ValidationFailed
from app.core.excel import is_xlsx, iter_rows, write_workbook
from app.core.logging import mask_email, mask_phone
from app.core.pagination import Page
from app.core.storage import get_storage, new_object_key
from app.modules.exhibitions import service as exhibitions_service
from app.modules.importexport import repository as repo
from app.modules.importexport.models import ImportJob, ImportMappingPreset, ImportRowError
from app.modules.importexport.rules import (
    CORE_COLUMNS,
    CUSTOM_PREFIX,
    ImportErrorReason,
    ImportStatus,
    ImportType,
    cell_to_text,
    suggest_mapping,
)
from app.modules.importexport.schemas import (
    AssignedCount,
    ImportErrorOut,
    ImportErrorParams,
    ImportJobOut,
    ImportListParams,
    ImportRecipient,
    JobAccepted,
    MappingTarget,
    PreviewOut,
)
from app.modules.registrations import service as registrations_service
from app.modules.telemarketing import service as telemarketing_service
from app.modules.visitors import service as visitors_service
from app.modules.visitors.rules import LeadSource, OptionField
from app.modules.visitors.schemas import LeadFields

logger = structlog.get_logger("import")

XLSX_MIME = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream",
}
_OPTION_TARGETS = {
    "business_type": OptionField.BUSINESS_TYPE,
    "branch": OptionField.BRANCH,
    "exhibition_type": OptionField.EXHIBITION_TYPE,
}
_GENDERS = {"m": "MALE", "male": "MALE", "f": "FEMALE", "female": "FEMALE", "other": "OTHER"}


def _check_scope(ctx: AuthContext, edition_id: uuid.UUID) -> None:
    """Imports create unowned leads, so they need edition-wide scope."""
    if not ctx.scope_for(edition_id).full_access:
        raise PermissionDenied()


async def _targets(session: AsyncSession, edition_id: uuid.UUID) -> list[MappingTarget]:
    targets = [
        MappingTarget(target=k, label=v, required=k == "first_name")
        for k, v in CORE_COLUMNS.items()
    ]
    for d in await visitors_service.custom_field_definitions(session, edition_id):
        if d.in_import:
            targets.append(
                MappingTarget(
                    target=CUSTOM_PREFIX + d.field_key, label=d.label, required=d.required
                )
            )
    return targets


def _check_file(file_name: str, content_type: str | None, data: bytes) -> None:
    """Only .xlsx (BACKEND_RULES/security-permissions.md): extension, MIME, magic bytes, size."""
    if not file_name.lower().endswith(".xlsx"):
        raise ValidationFailed(fields={"file": "Only .xlsx files are accepted."})
    if content_type and content_type not in XLSX_MIME:
        raise ValidationFailed(fields={"file": "Only .xlsx files are accepted."})
    if len(data) > get_settings().import_max_bytes:
        raise ValidationFailed(fields={"file": "File is too large."}, code="FILE_TOO_LARGE")
    if not data or not is_xlsx(data):
        raise ValidationFailed(fields={"file": "File is not a valid .xlsx workbook."})


def _parse_mapping(raw: str | None, targets: list[MappingTarget]) -> dict[str, str]:
    if not raw:
        return {}
    try:
        mapping = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValidationFailed(fields={"column_mapping": "Must be a JSON object."}) from e
    if not isinstance(mapping, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in mapping.items()
    ):
        raise ValidationFailed(fields={"column_mapping": "Must map header text to a target."})
    known = {t.target for t in targets}
    unknown = sorted({v for v in mapping.values() if v not in known})
    if unknown:
        raise ValidationFailed(fields={"column_mapping": f"Unknown targets: {', '.join(unknown)}"})
    if len(set(mapping.values())) != len(mapping):
        raise ValidationFailed(fields={"column_mapping": "Each target can be mapped once."})
    return mapping


async def start_import(
    session: AsyncSession,
    ctx: AuthContext,
    *,
    edition_id: uuid.UUID,
    file_name: str,
    content_type: str | None,
    data: bytes,
    import_type: ImportType,
    column_mapping: str | None,
    save_mapping: bool,
    auto_assign: bool = False,
) -> JobAccepted:
    """Store the upload and queue the job. Rows are never read in the request."""
    _check_scope(ctx, edition_id)
    await exhibitions_service.ensure_writable(session, edition_id)
    _check_file(file_name, content_type, data)
    if import_type == ImportType.LEADS_AND_REGISTER:
        raise ValidationFailed(
            "Registering visitors from an import is not enabled (open decision D2).",
            fields={"import_type": "Not available."},
        )
    if auto_assign and not await telemarketing_service.import_recipients(session, edition_id):
        raise ValidationFailed(
            "No one in this edition's team can receive leads.",
            fields={"auto_assign": "Set a team with callers on the edition first."},
        )
    mapping = _parse_mapping(column_mapping, await _targets(session, edition_id))
    if not mapping and (preset := await repo.get_preset(session, edition_id)):
        mapping = dict(preset.mapping)
    if mapping and save_mapping:
        await _save_preset(session, edition_id, mapping, ctx.user.id)

    key = new_object_key(".xlsx")
    await run_in_threadpool(
        get_storage().put, get_settings().s3_bucket_imports, key, data, next(iter(XLSX_MIME))
    )
    job = ImportJob(
        edition_id=edition_id,
        status=ImportStatus.QUEUED,
        import_type=import_type,
        file_name=file_name[-255:],
        file_size=len(data),
        object_key=key,
        column_mapping=mapping,
        auto_assign=auto_assign,
        created_by=ctx.user.id,
    )
    session.add(job)
    await session.flush()
    await outbox.enqueue(
        session, "import.requested", "importexport.run_import", {"job_id": str(job.id)}, "import"
    )
    await audit.record(
        session,
        entity_type="import_job",
        entity_id=job.id,
        action="start",
        after={
            "file_name": job.file_name,
            "file_size": job.file_size,
            "import_type": import_type,
            "auto_assign": auto_assign,
        },
        edition_id=edition_id,
    )
    return JobAccepted(job_id=job.id, status=job.status)


async def _save_preset(
    session: AsyncSession, edition_id: uuid.UUID, mapping: dict[str, str], user_id: uuid.UUID
) -> None:
    preset = await repo.get_preset(session, edition_id)
    if preset is None:
        session.add(ImportMappingPreset(edition_id=edition_id, mapping=mapping, updated_by=user_id))
    else:
        preset.mapping = mapping
        preset.updated_by = user_id
    await session.flush()


def _read_headers(data: bytes, limit: int) -> tuple[list[str], int]:
    headers: list[str] = []
    count = 0
    for number, values in iter_rows(data):
        if number == 1:
            headers = [cell_to_text(v) or "" for v in values]
            continue
        if any(v is not None for v in values):
            count += 1
        if count >= limit:
            break
    return headers, count


async def preview(
    session: AsyncSession,
    ctx: AuthContext,
    edition_id: uuid.UUID,
    file_name: str,
    content_type: str | None,
    data: bytes,
) -> PreviewOut:
    """Header row + suggested mapping for the mapping step."""
    _check_scope(ctx, edition_id)
    _check_file(file_name, content_type, data)
    try:
        headers, count = await run_in_threadpool(_read_headers, data, 1000)
    except Exception as e:  # openpyxl raises many types for corrupt files
        raise ValidationFailed(fields={"file": "File is not a valid .xlsx workbook."}) from e
    targets = await _targets(session, edition_id)
    custom = {
        t.target.removeprefix(CUSTOM_PREFIX): t.label
        for t in targets
        if t.target.startswith(CUSTOM_PREFIX)
    }
    suggested = suggest_mapping([h for h in headers if h], custom)
    if preset := await repo.get_preset(session, edition_id):
        suggested.update({h: t for h, t in preset.mapping.items() if h in headers})
    return PreviewOut(
        headers=headers, suggested_mapping=suggested, targets=targets, sample_rows=count
    )


async def template(session: AsyncSession, ctx: AuthContext, edition_id: uuid.UUID) -> bytes:
    """Per-edition template: core columns + active custom fields marked for import."""
    ctx.scope_for(edition_id)
    targets = await _targets(session, edition_id)
    options = await visitors_service.list_field_options(session, ctx, edition_id, None, False)
    option_rows = [[o.field.value, o.value, o.label] for o in options]
    return await run_in_threadpool(
        write_workbook,
        [
            ("Leads", [t.label for t in targets], []),
            ("Options", ["Field", "Value", "Label"], option_rows),
        ],
    )


def _job_out(job: ImportJob) -> ImportJobOut:
    out = ImportJobOut.model_validate(job)
    out.has_error_report = job.errors_object_key is not None
    out.assigned_to = sorted(
        (
            AssignedCount(user_id=uuid.UUID(k), full_name=v["name"], count=v["count"])
            for k, v in job.assign_summary.items()
        ),
        key=lambda a: a.full_name,
    )
    return out


async def recipients(
    session: AsyncSession, ctx: AuthContext, edition_id: uuid.UUID
) -> list[ImportRecipient]:
    _check_scope(ctx, edition_id)
    return [
        ImportRecipient(id=a.id, full_name=a.full_name)
        for a in await telemarketing_service.import_recipients(session, edition_id)
    ]


async def _auto_assign(session: AsyncSession, job: ImportJob) -> None:
    """Share the import's unowned new leads round robin among the edition team's callers.

    Batches commit with the job's running totals, so a resumed job carries on where it
    stopped. Callers are read now, when rows are done: someone added meanwhile counts."""
    agents = await telemarketing_service.import_recipients(session, job.edition_id)
    if not agents:
        job.error_summary = "Leads were not assigned: no one in the edition's team can call."
        return
    names = {a.id: a.full_name for a in agents}
    agent_ids = sorted(names)
    batch_id = new_id()
    while lead_ids := await visitors_service.unassigned_import_lead_ids(
        session, job.edition_id, job.id, get_settings().import_batch_size
    ):
        counts = await telemarketing_service.assign_import_batch(
            session, job.edition_id, lead_ids, agent_ids, job.created_by, batch_id
        )
        summary = dict(job.assign_summary)
        for user_id, n in counts.items():
            prev = summary.get(str(user_id), {"name": names[user_id], "count": 0})
            summary[str(user_id)] = {"name": names[user_id], "count": prev["count"] + n}
        job.assign_summary = summary
        job.assigned_count += sum(counts.values())
        await session.commit()


async def _scoped_job(session: AsyncSession, ctx: AuthContext, job_id: uuid.UUID) -> ImportJob:
    edition_id = await repo.edition_of_job(session, job_id)
    if edition_id is None:
        raise NotFound("Import not found.")
    try:
        _check_scope(ctx, edition_id)
    except (NotFound, PermissionDenied) as e:
        raise NotFound("Import not found.") from e
    job = await repo.get_job(session, edition_id, job_id)
    if job is None:
        raise NotFound("Import not found.")
    return job


async def get_job(session: AsyncSession, ctx: AuthContext, job_id: uuid.UUID) -> ImportJobOut:
    return _job_out(await _scoped_job(session, ctx, job_id))


async def list_jobs(
    session: AsyncSession, ctx: AuthContext, params: ImportListParams
) -> Page[ImportJobOut]:
    _check_scope(ctx, params.edition_id)
    rows, total = await repo.list_jobs(session, params.edition_id, params.offset, params.page_size)
    return Page(
        items=[_job_out(j) for j in rows], total=total, page=params.page, page_size=params.page_size
    )


async def list_errors(
    session: AsyncSession, ctx: AuthContext, job_id: uuid.UUID, params: ImportErrorParams
) -> Page[ImportErrorOut]:
    job = await _scoped_job(session, ctx, job_id)
    rows, total = await repo.list_errors(
        session, job.edition_id, job.id, params.reason_code, params.offset, params.page_size
    )
    return Page(
        items=[ImportErrorOut.model_validate(r) for r in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def error_report_url(session: AsyncSession, ctx: AuthContext, job_id: uuid.UUID) -> str:
    """Where the browser downloads the error report: through the API, never from storage."""
    job = await _scoped_job(session, ctx, job_id)
    if job.errors_object_key is None:
        raise NotFound("This import has no error report.")
    return f"/api/v1/visitor-leads/imports/{job.id}/errors/file"


async def error_report_file(
    session: AsyncSession, ctx: AuthContext, job_id: uuid.UUID
) -> tuple[Iterator[bytes], str]:
    """(chunks, file name) of the error report, for the caller's scope only."""
    job = await _scoped_job(session, ctx, job_id)
    if job.errors_object_key is None:
        raise NotFound("This import has no error report.")
    try:
        chunks = await run_in_threadpool(
            get_storage().stream, get_settings().s3_bucket_imports, job.errors_object_key
        )
    except FileNotFoundError as e:
        raise NotFound("The error report is no longer available.") from e
    return chunks, f"import-errors-{job.id}.xlsx"


# --- worker --------------------------------------------------------------------------------


def _row_values(
    raw: dict[str, Any], option_lookup: dict[str, dict[str, str]]
) -> tuple[dict[str, Any], dict[str, str]]:
    """Convert a mapped spreadsheet row into lead values; collect field errors."""
    values: dict[str, Any] = {}
    custom: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for target, cell in raw.items():
        text = cell_to_text(cell)
        if target.startswith(CUSTOM_PREFIX):
            custom[target.removeprefix(CUSTOM_PREFIX)] = text
        elif target == "gender":
            if text is not None and text.lower() not in _GENDERS:
                errors["gender"] = "Unknown gender."
            values["gender"] = _GENDERS.get(text.lower()) if text else None
        elif target in _OPTION_TARGETS:
            lookup = option_lookup.get(_OPTION_TARGETS[target], {})
            values[target] = lookup.get(text.lower(), text) if text else None
        elif target == "country":
            values[target] = text.upper() if text else None
        elif target == "lead_date":
            values[target] = cell if isinstance(cell, datetime) else text
        elif target != "external_id":
            values[target] = text
    if custom:
        values["custom_fields"] = custom
    try:
        parsed = LeadFields.model_validate(values)
    except ValidationError as e:
        for err in e.errors():
            errors.setdefault(".".join(str(p) for p in err["loc"]), "Invalid value.")
        return values, errors
    return parsed.model_dump(exclude_unset=True), errors


def _preview(raw: dict[str, Any]) -> dict[str, Any]:
    """Safe subset of a row for the error report (no full PII)."""
    email = cell_to_text(raw.get("email"))
    phone = cell_to_text(raw.get("phone"))
    return {
        "first_name": cell_to_text(raw.get("first_name")),
        "company_name": cell_to_text(raw.get("company_name")),
        "email": mask_email(email),
        "phone": mask_phone(phone),
    }


async def _option_lookup(session: AsyncSession, edition_id: uuid.UUID) -> dict[str, dict[str, str]]:
    """Accept option values or labels (case-insensitive) in the file."""
    from app.modules.visitors import repository as visitors_repo

    lookup: dict[str, dict[str, str]] = {}
    for opt in await visitors_repo.field_options(session, edition_id, None, False):
        bucket = lookup.setdefault(opt.field, {})
        bucket[opt.value.lower()] = opt.value
        bucket[opt.label.lower()] = opt.value
    return lookup


def _mapped_rows(
    data: bytes, mapping: dict[str, str], start_after: int
) -> Iterator[tuple[int, dict[str, Any]]]:
    headers: list[str] = []
    for number, values in iter_rows(data):
        if number == 1:
            headers = [cell_to_text(v) or "" for v in values]
            continue
        if number <= start_after or not any(v is not None for v in values):
            continue
        yield (
            number,
            {
                mapping[h]: values[i]
                for i, h in enumerate(headers)
                if h in mapping and i < len(values)
            },
        )


async def _finish(session: AsyncSession, job: ImportJob, status: ImportStatus) -> None:
    job.status = status
    job.finished_at = datetime.now(UTC)
    await audit.record(
        session,
        entity_type="import_job",
        entity_id=job.id,
        action="finish",
        after={
            "status": status,
            "processed": job.processed_count,
            "created": job.created_count,
            "duplicate": job.duplicate_count,
            "invalid": job.invalid_count,
        },
        edition_id=job.edition_id,
    )
    await session.commit()


async def _write_error_report(session: AsyncSession, job: ImportJob) -> None:
    rows, _ = await repo.list_errors(session, job.edition_id, job.id, None, 0, None)
    if not rows:
        return
    content = write_workbook(
        [
            (
                "Errors",
                ["Row", "Reason", "Message", "Fields", "First Name", "Company", "Email", "Phone"],
                (
                    [
                        r.row_number,
                        r.reason_code,
                        r.message,
                        "; ".join(f"{k}: {v}" for k, v in r.fields.items()),
                        r.row_preview.get("first_name"),
                        r.row_preview.get("company_name"),
                        r.row_preview.get("email"),
                        r.row_preview.get("phone"),
                    ]
                    for r in rows
                ),
            )
        ]
    )
    key = new_object_key(".xlsx")
    get_storage().put(get_settings().s3_bucket_imports, key, content, next(iter(XLSX_MIME)))
    job.errors_object_key = key


async def process_import(session: AsyncSession, job_id: uuid.UUID) -> ImportStatus | None:
    """Run (or resume) an import. Safe to call twice: a lock and a row checkpoint make
    each row count once. Returns the final status, or None if skipped."""
    if not await repo.try_job_lock(session, job_id):
        return None
    await session.commit()
    try:
        return await _process_locked(session, job_id)
    finally:
        await session.rollback()
        await repo.release_job_lock(session, job_id)
        await session.commit()


async def _process_locked(session: AsyncSession, job_id: uuid.UUID) -> ImportStatus | None:
    s = get_settings()
    job = await repo.get_job(session, None, job_id)
    if job is None or job.status not in (ImportStatus.QUEUED, ImportStatus.RUNNING):
        return None
    source_var.set(Source.IMPORT)
    actor_id_var.set(job.created_by)
    if job.status == ImportStatus.QUEUED:
        job.status = ImportStatus.RUNNING
        job.started_at = datetime.now(UTC)
    await session.commit()

    try:
        data = get_storage().get(s.s3_bucket_imports, job.object_key)
        mapping = dict(job.column_mapping)
        if not mapping:
            headers = next((v for n, v in iter_rows(data) if n == 1), ())
            custom = {
                d.field_key: d.label
                for d in await visitors_service.custom_field_definitions(session, job.edition_id)
                if d.in_import
            }
            mapping = suggest_mapping([cell_to_text(h) or "" for h in headers], custom)
            job.column_mapping = mapping
        if "first_name" not in mapping.values():
            job.error_summary = "No column is mapped to First Name."
            await _finish(session, job, ImportStatus.FAILED)
            return ImportStatus.FAILED
        if job.total_rows is None:
            job.total_rows = sum(1 for _ in _mapped_rows(data, mapping, 1))
            if job.total_rows > s.import_max_rows:
                job.error_summary = f"File has more than {s.import_max_rows} rows."
                await _finish(session, job, ImportStatus.FAILED)
                return ImportStatus.FAILED
        await session.commit()

        options = await _option_lookup(session, job.edition_id)
        in_batch = 0
        for number, raw in _mapped_rows(data, mapping, job.checkpoint_row):
            await _import_row(session, job, number, raw, options)
            job.processed_count += 1
            job.checkpoint_row = number
            in_batch += 1
            if in_batch >= s.import_batch_size:
                await session.commit()
                in_batch = 0
        await session.commit()

        if job.auto_assign:
            await _auto_assign(session, job)

        await _write_error_report(session, job)
        has_errors = job.duplicate_count or job.invalid_count
        status = ImportStatus.COMPLETED_WITH_ERRORS if has_errors else ImportStatus.COMPLETED
        await _finish(session, job, status)
        logger.info("import_finished", job_id=str(job.id), status=status)
        return status
    except Exception as e:
        logger.exception("import_failed", job_id=str(job_id))
        await session.rollback()
        job = await repo.get_job(session, None, job_id)
        if job is None:
            raise
        job.error_summary = f"Import failed ({type(e).__name__})."
        await _finish(session, job, ImportStatus.FAILED)
        return ImportStatus.FAILED


async def _import_row(
    session: AsyncSession,
    job: ImportJob,
    number: int,
    raw: dict[str, Any],
    options: dict[str, dict[str, str]],
) -> None:
    values, errors = _row_values(raw, options)
    reason: ImportErrorReason | None = None
    message = ""
    if errors:
        reason, message = ImportErrorReason.INVALID, "Invalid values."
    else:
        try:
            lead = await visitors_service.insert_lead(
                session,
                job.edition_id,
                values,
                source=LeadSource.EXCEL,
                external_source="EXCEL" if raw.get("external_id") is not None else None,
                external_id=cell_to_text(raw.get("external_id")),
                import_job_id=job.id,
            )
            await registrations_service.register_new_lead(session, lead)
            job.created_count += 1
            return
        except visitors_service.DuplicateVisitor as e:
            in_file = job.id in e.import_job_ids
            reason = (
                ImportErrorReason.DUPLICATE_IN_FILE
                if in_file
                else ImportErrorReason.DUPLICATE_EXISTING
            )
            message, errors = e.message, e.fields
        except AppError as e:
            reason, message, errors = ImportErrorReason.INVALID, e.message, e.fields
    if reason in (ImportErrorReason.DUPLICATE_IN_FILE, ImportErrorReason.DUPLICATE_EXISTING):
        job.duplicate_count += 1
    else:
        job.invalid_count += 1
    session.add(
        ImportRowError(
            import_job_id=job.id,
            edition_id=job.edition_id,
            row_number=number,
            reason_code=reason,
            message=message[:1000],
            fields=errors,
            row_preview=_preview(raw),
        )
    )
    await session.flush()
