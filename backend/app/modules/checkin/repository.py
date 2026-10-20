import uuid
from collections.abc import Sequence
from datetime import date, datetime
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, func, select, true, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.authorization import Scope
from app.core.db import new_id
from app.modules.checkin.models import Gate, ScanAttempt, ScannerDevice, VisitorCheckin
from app.modules.checkin.rules import ScanOutcome
from app.modules.checkin.schemas import ScanListParams

# --- gates / devices -------------------------------------------------------------------------


def gate_scope_clause(
    column: InstrumentedAttribute[uuid.UUID], scope: Scope
) -> ColumnElement[bool]:
    """Gate-scoped users (spec 9.2 GATE) only see their own gates."""
    if scope.full_access:
        return true()
    return column.in_(scope.gate_ids or [uuid.UUID(int=0)])


async def get_gate(session: AsyncSession, gate_id: uuid.UUID) -> Gate | None:
    return await session.get(Gate, gate_id)


async def list_gates(session: AsyncSession, scope: Scope) -> list[Gate]:
    rows = await session.scalars(
        select(Gate)
        .where(Gate.edition_id == scope.edition_id, gate_scope_clause(Gate.id, scope))
        .order_by(Gate.code)
    )
    return list(rows)


async def get_device(
    session: AsyncSession, device_id: uuid.UUID, *, for_update: bool = False
) -> ScannerDevice | None:
    return await session.get(ScannerDevice, device_id, with_for_update=for_update)


async def device_by_activation(session: AsyncSession, code_hash: str) -> ScannerDevice | None:
    return await session.scalar(
        select(ScannerDevice)
        .where(ScannerDevice.activation_code_hash == code_hash)
        .with_for_update()
    )


async def list_devices(
    session: AsyncSession,
    scope: Scope,
    gate_id: uuid.UUID | None,
    status: str | None,
    offset: int,
    limit: int,
) -> tuple[Sequence[ScannerDevice], int]:
    stmt = select(ScannerDevice).where(
        ScannerDevice.edition_id == scope.edition_id,
        gate_scope_clause(ScannerDevice.gate_id, scope),
    )
    if gate_id:
        stmt = stmt.where(ScannerDevice.gate_id == gate_id)
    if status:
        stmt = stmt.where(ScannerDevice.status == status)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = await session.scalars(
        stmt.order_by(ScannerDevice.created_at.desc()).offset(offset).limit(limit)
    )
    return rows.all(), int(total or 0)


async def touch_device(session: AsyncSession, device_id: uuid.UUID) -> None:
    """Bulk UPDATE on purpose: last_seen_at must not bump the optimistic-lock version."""
    await session.execute(
        update(ScannerDevice)
        .where(ScannerDevice.id == device_id)
        .values(last_seen_at=func.now())
        .execution_options(synchronize_session=False)
    )


# --- scans -----------------------------------------------------------------------------------


async def get_attempt_by_event(
    session: AsyncSession, scan_event_id: uuid.UUID
) -> ScanAttempt | None:
    return await session.scalar(
        select(ScanAttempt).where(ScanAttempt.scan_event_id == scan_event_id)
    )


async def insert_attempt(session: AsyncSession, values: dict[str, Any]) -> uuid.UUID | None:
    """None when the scan_event_id already exists (a retry racing the first request)."""
    return await session.scalar(
        insert(ScanAttempt)
        .values(id=new_id(), **values)
        .on_conflict_do_nothing(index_elements=["scan_event_id"])
        .returning(ScanAttempt.id)
    )


async def claim_first_entry(
    session: AsyncSession,
    *,
    edition_id: uuid.UUID,
    registration_id: uuid.UUID,
    local_date: date,
    attempt_id: uuid.UUID,
    scanned_at: datetime,
    gate_id: uuid.UUID,
) -> bool:
    """Atomic: True when this attempt is now the first entry of the day.

    An earlier scan time takes over the first entry (late offline sync); ties keep the
    existing one. The row lock of ON CONFLICT serialises concurrent devices.
    """
    base = insert(VisitorCheckin).values(
        id=new_id(),
        edition_id=edition_id,
        registration_id=registration_id,
        local_date=local_date,
        first_scan_attempt_id=attempt_id,
        first_scanned_at=scanned_at,
        gate_id=gate_id,
    )
    stmt = base.on_conflict_do_update(
        index_elements=["registration_id", "local_date"],
        set_={
            "first_scan_attempt_id": base.excluded.first_scan_attempt_id,
            "first_scanned_at": base.excluded.first_scanned_at,
            "gate_id": base.excluded.gate_id,
            "updated_at": func.now(),
        },
        where=base.excluded.first_scanned_at < VisitorCheckin.first_scanned_at,
    ).returning(VisitorCheckin.first_scan_attempt_id)
    first: uuid.UUID | None = await session.scalar(stmt)
    return first == attempt_id


async def is_first(session: AsyncSession, attempt_id: uuid.UUID) -> bool:
    found = await session.scalar(
        select(VisitorCheckin.id).where(VisitorCheckin.first_scan_attempt_id == attempt_id)
    )
    return found is not None


async def entered_on(
    session: AsyncSession, edition_id: uuid.UUID, local_date: date
) -> list[uuid.UUID]:
    rows = await session.scalars(
        select(VisitorCheckin.registration_id).where(
            VisitorCheckin.edition_id == edition_id, VisitorCheckin.local_date == local_date
        )
    )
    return list(rows)


def _attempts(scope: Scope) -> Select[ScanAttempt, bool]:
    """Attempts in scope with is_first derived from visitor_checkins."""
    return (
        select(ScanAttempt, VisitorCheckin.id.is_not(None).label("is_first"))
        .outerjoin(VisitorCheckin, VisitorCheckin.first_scan_attempt_id == ScanAttempt.id)
        .where(
            ScanAttempt.edition_id == scope.edition_id,
            gate_scope_clause(ScanAttempt.gate_id, scope),
        )
    )


async def get_attempt_row(session: AsyncSession, attempt_id: uuid.UUID) -> Any:
    """(attempt, is_first) for one attempt."""
    row = await session.execute(
        select(ScanAttempt, VisitorCheckin.id.is_not(None).label("is_first"))
        .outerjoin(VisitorCheckin, VisitorCheckin.first_scan_attempt_id == ScanAttempt.id)
        .where(ScanAttempt.id == attempt_id)
    )
    return row.one()


def _result_clause(result: str) -> ColumnElement[bool]:
    if result == "FIRST_ENTRY":
        return VisitorCheckin.id.is_not(None)
    if result == "REPEAT_ENTRY":
        return and_(ScanAttempt.outcome == ScanOutcome.ACCEPTED, VisitorCheckin.id.is_(None))
    return ScanAttempt.outcome == result


async def list_attempts(
    session: AsyncSession, scope: Scope, params: ScanListParams
) -> tuple[Sequence[Any], int]:
    stmt = _attempts(scope)
    if params.gate_id:
        stmt = stmt.where(ScanAttempt.gate_id == params.gate_id)
    if params.device_id:
        stmt = stmt.where(ScanAttempt.device_id == params.device_id)
    if params.local_date:
        stmt = stmt.where(ScanAttempt.local_date == params.local_date)
    if params.mode:
        stmt = stmt.where(ScanAttempt.mode == params.mode)
    if params.result:
        stmt = stmt.where(_result_clause(params.result))
    return await _page(session, stmt, params.offset, params.page_size)


async def reconciliation(
    session: AsyncSession, scope: Scope, offset: int, limit: int
) -> tuple[Sequence[Any], int]:
    """Offline scans whose final result differs from what the device showed."""
    stmt = (
        _attempts(scope)
        .where(ScanAttempt.provisional_result.is_not(None))
        .where(
            (ScanAttempt.outcome != ScanOutcome.ACCEPTED)
            & (ScanAttempt.provisional_result != ScanAttempt.outcome)
            | (
                (ScanAttempt.outcome == ScanOutcome.ACCEPTED)
                & VisitorCheckin.id.is_not(None)
                & (ScanAttempt.provisional_result != "FIRST_ENTRY")
            )
            | (
                (ScanAttempt.outcome == ScanOutcome.ACCEPTED)
                & VisitorCheckin.id.is_(None)
                & (ScanAttempt.provisional_result != "REPEAT_ENTRY")
            )
        )
    )
    return await _page(session, stmt, offset, limit)


async def _page(
    session: AsyncSession, stmt: Select[ScanAttempt, bool], offset: int, limit: int
) -> tuple[Sequence[Any], int]:
    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = await session.execute(
        stmt.order_by(ScanAttempt.scanned_at.desc(), ScanAttempt.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return rows.all(), int(total or 0)
