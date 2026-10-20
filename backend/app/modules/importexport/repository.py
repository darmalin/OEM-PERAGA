import uuid
from collections.abc import Sequence

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.importexport.models import ImportJob, ImportMappingPreset, ImportRowError


async def get_job(
    session: AsyncSession, edition_id: uuid.UUID | None, job_id: uuid.UUID
) -> ImportJob | None:
    """edition_id None only for workers; API callers always pass the scoped edition."""
    stmt = select(ImportJob).where(ImportJob.id == job_id)
    if edition_id is not None:
        stmt = stmt.where(ImportJob.edition_id == edition_id)
    return await session.scalar(stmt)


async def edition_of_job(session: AsyncSession, job_id: uuid.UUID) -> uuid.UUID | None:
    return await session.scalar(select(ImportJob.edition_id).where(ImportJob.id == job_id))


async def list_jobs(
    session: AsyncSession, edition_id: uuid.UUID, offset: int, limit: int
) -> tuple[Sequence[ImportJob], int]:
    stmt = select(ImportJob).where(ImportJob.edition_id == edition_id)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = await session.scalars(
        stmt.order_by(ImportJob.created_at.desc()).offset(offset).limit(limit)
    )
    return rows.all(), total


async def list_errors(
    session: AsyncSession,
    edition_id: uuid.UUID,
    job_id: uuid.UUID,
    reason: str | None,
    offset: int,
    limit: int | None,
) -> tuple[Sequence[ImportRowError], int]:
    stmt = select(ImportRowError).where(
        ImportRowError.edition_id == edition_id, ImportRowError.import_job_id == job_id
    )
    if reason:
        stmt = stmt.where(ImportRowError.reason_code == reason)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.order_by(ImportRowError.row_number).offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    return (await session.scalars(stmt)).all(), total


async def get_preset(session: AsyncSession, edition_id: uuid.UUID) -> ImportMappingPreset | None:
    return await session.scalar(
        select(ImportMappingPreset).where(ImportMappingPreset.edition_id == edition_id)
    )


async def try_job_lock(session: AsyncSession, job_id: uuid.UUID) -> bool:
    """Session-level advisory lock so a job never runs in two workers at once."""
    got = await session.scalar(
        text("SELECT pg_try_advisory_lock(hashtextextended(:k, 0))"), {"k": f"import:{job_id}"}
    )
    return bool(got)


async def release_job_lock(session: AsyncSession, job_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT pg_advisory_unlock(hashtextextended(:k, 0))"), {"k": f"import:{job_id}"}
    )
