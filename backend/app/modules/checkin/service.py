"""Gates, scanner devices, scans, and attendance (spec 8, FEATURES/09)."""

import hmac
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit, ratelimit
from app.core.authorization import AuthContext, Scope
from app.core.config import get_settings
from app.core.context import Source, source_var
from app.core.crypto import sha256_hex
from app.core.db import get_session
from app.core.errors import (
    AppError,
    Conflict,
    NotFound,
    PermissionDenied,
    ValidationFailed,
    check_version,
)
from app.core.pagination import Page
from app.modules.checkin import repository as repo
from app.modules.checkin.models import Gate, ScanAttempt, ScannerDevice
from app.modules.checkin.rules import (
    DeviceStatus,
    ScanMode,
    ScanOutcome,
    ScanResult,
    activation_code_hash,
    local_date,
    new_activation_code,
    new_device_secret,
    result_for,
    trusted_scan_time,
)
from app.modules.checkin.schemas import (
    ActivatedOut,
    ActivateIn,
    CacheEntry,
    CacheOut,
    DeviceContext,
    DeviceCreatedOut,
    DeviceIn,
    DeviceListParams,
    DeviceOut,
    DeviceRevokeIn,
    GateIn,
    GateOut,
    GateUpdateIn,
    OverrideIn,
    ReconciliationParams,
    ScanIn,
    ScanListParams,
    ScanOut,
    ScanResultOut,
    SyncIn,
    SyncOut,
)
from app.modules.exhibitions import service as exhibitions_service
from app.modules.exhibitions.models import Edition
from app.modules.registrations import service as registrations_service

GATE_ENTITY = "gate"
DEVICE_ENTITY = "scanner_device"
DEVICE_AUDIT_FIELDS = ("name", "gate_id", "status", "activated_at", "revoked_at", "revoke_reason")
DEVICE_TOKEN_HEADER = "X-Device-Token"  # noqa: S105 - header name, not a secret


class DeviceNotAuthenticated(AppError):
    status_code = 401
    code = "DEVICE_NOT_AUTHENTICATED"
    default_message = "Scanner device is not activated. Enter a new activation code."


# --- device authentication -------------------------------------------------------------------


@dataclass(frozen=True)
class DeviceAuth:
    device_id: uuid.UUID
    device_name: str
    edition_id: uuid.UUID
    edition_code: str
    timezone: str
    gate_id: uuid.UUID
    gate_code: str
    gate_name: str
    edition: Edition

    def context(self) -> DeviceContext:
        return DeviceContext(
            device_id=self.device_id,
            device_name=self.device_name,
            status=DeviceStatus.ACTIVE,
            edition_id=self.edition_id,
            edition_code=self.edition_code,
            edition_timezone=self.timezone,
            gate_id=self.gate_id,
            gate_code=self.gate_code,
            gate_name=self.gate_name,
        )


def _parse_device_token(raw: str | None) -> tuple[uuid.UUID, str] | None:
    if not raw or "." not in raw:
        return None
    device_part, _, secret = raw.partition(".")
    try:
        return uuid.UUID(device_part), secret
    except ValueError:
        return None


async def require_device(
    request: Request, session: AsyncSession = Depends(get_session)
) -> DeviceAuth:
    """Dependency for /gate/device/* routes: an ACTIVE device on an active gate."""
    parsed = _parse_device_token(request.headers.get(DEVICE_TOKEN_HEADER))
    if parsed is None:
        raise DeviceNotAuthenticated()
    device_id, secret = parsed
    device = await repo.get_device(session, device_id)
    if (
        device is None
        or device.secret_hash is None
        or not hmac.compare_digest(device.secret_hash, sha256_hex(secret))
    ):
        raise DeviceNotAuthenticated()
    if device.status == DeviceStatus.REVOKED:
        raise PermissionDenied(
            "This device was revoked. Ask a gate supervisor.", code="DEVICE_REVOKED"
        )
    gate = await repo.get_gate(session, device.gate_id)
    edition = await exhibitions_service.get_edition_by_id(session, device.edition_id)
    assert gate is not None and edition is not None  # noqa: S101 - FKs
    if not gate.is_active:
        raise PermissionDenied("This gate is closed.", code="GATE_INACTIVE")
    source_var.set(Source.SCANNER)
    await repo.touch_device(session, device.id)
    return DeviceAuth(
        device_id=device.id,
        device_name=device.name,
        edition_id=edition.id,
        edition_code=edition.code,
        timezone=edition.timezone,
        gate_id=gate.id,
        gate_code=gate.code,
        gate_name=gate.name,
        edition=edition,
    )


require_device.__ems_device__ = True  # type: ignore[attr-defined]


def is_device_guard(dependency: Any) -> bool:
    return getattr(dependency, "__ems_device__", False) is True


async def activate_device(session: AsyncSession, data: ActivateIn, client_ip: str) -> ActivatedOut:
    """POST /gate/device/activate: exchange the one-time code for a device token."""
    await ratelimit.hit(f"device_activate:ip:{client_ip}", 10, 15 * 60)
    source_var.set(Source.SCANNER)
    device = await repo.device_by_activation(session, activation_code_hash(data.activation_code))
    now = datetime.now(UTC)
    if (
        device is None
        or device.status != DeviceStatus.PENDING
        or device.activation_expires_at is None
        or device.activation_expires_at < now
    ):
        raise ValidationFailed(
            "Activation code is invalid or expired.",
            code="ACTIVATION_CODE_INVALID",
            fields={"activation_code": "Invalid or expired."},
        )
    before = audit.snapshot(device, DEVICE_AUDIT_FIELDS)
    secret, secret_hash = new_device_secret()
    device.secret_hash = secret_hash
    device.status = DeviceStatus.ACTIVE
    device.activated_at = now
    device.activation_code_hash = None
    device.activation_expires_at = None
    await session.flush()
    await audit.record(
        session,
        entity_type=DEVICE_ENTITY,
        entity_id=device.id,
        action="activate",
        before=before,
        after=audit.snapshot(device, DEVICE_AUDIT_FIELDS),
        edition_id=device.edition_id,
    )
    gate = await repo.get_gate(session, device.gate_id)
    edition = await exhibitions_service.get_edition_by_id(session, device.edition_id)
    assert gate is not None and edition is not None  # noqa: S101 - FKs
    return ActivatedOut(
        device_id=device.id,
        device_name=device.name,
        status=DeviceStatus.ACTIVE,
        edition_id=edition.id,
        edition_code=edition.code,
        edition_timezone=edition.timezone,
        gate_id=gate.id,
        gate_code=gate.code,
        gate_name=gate.name,
        device_token=f"{device.id}.{secret}",
    )


# --- scanning --------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Scan:
    scan_event_id: uuid.UUID
    token_hash: str
    scanned_at: datetime
    mode: ScanMode
    provisional: ScanResult | None = None


def _out(
    attempt_event: uuid.UUID,
    result: ScanResult,
    scanned_at: datetime,
    day: Any,
    label: tuple[str, str] | None,
    provisional: str | None,
) -> ScanResultOut:
    show = label if result != ScanResult.REJECTED_WRONG_EDITION else None
    return ScanResultOut(
        scan_event_id=attempt_event,
        result=result,
        registration_code=show[0] if show else None,
        first_name=show[1] if show else None,
        scanned_at=scanned_at,
        local_date=day,
        changed_from_provisional=provisional is not None and provisional != result,
    )


async def _replay(session: AsyncSession, device: DeviceAuth, attempt: ScanAttempt) -> ScanResultOut:
    """Same scan_event_id again: answer from the stored attempt, never count it twice."""
    if attempt.device_id != device.device_id:
        raise Conflict("scan_event_id belongs to another device.", code="SCAN_EVENT_CONFLICT")
    result = result_for(ScanOutcome(attempt.outcome), await repo.is_first(session, attempt.id))
    labels = await registrations_service.registration_labels(
        session, [attempt.registration_id] if attempt.registration_id else []
    )
    return _out(
        attempt.scan_event_id,
        result,
        attempt.scanned_at,
        attempt.local_date,
        labels.get(attempt.registration_id) if attempt.registration_id else None,
        attempt.provisional_result,
    )


async def _process(session: AsyncSession, device: DeviceAuth, scan: _Scan) -> ScanResultOut:
    existing = await repo.get_attempt_by_event(session, scan.scan_event_id)
    if existing is not None:
        return await _replay(session, device, existing)
    received = datetime.now(UTC)
    scanned_at = (
        received if scan.mode == ScanMode.ONLINE else trusted_scan_time(scan.scanned_at, received)
    )
    day = local_date(scanned_at, device.timezone)
    match = await registrations_service.match_credential(session, scan.token_hash)
    if match is None:
        outcome = ScanOutcome.REJECTED_UNKNOWN
    elif match.edition_id != device.edition_id:
        outcome = ScanOutcome.REJECTED_WRONG_EDITION
    elif not match.credential_active:
        outcome = ScanOutcome.REJECTED_REVOKED
    elif not match.registered:
        outcome = ScanOutcome.REJECTED_CANCELLED
    else:
        outcome = ScanOutcome.ACCEPTED
    same_edition = match is not None and match.edition_id == device.edition_id
    attempt_id = await repo.insert_attempt(
        session,
        {
            "edition_id": device.edition_id,
            "gate_id": device.gate_id,
            "device_id": device.device_id,
            "scan_event_id": scan.scan_event_id,
            "token_hash": scan.token_hash,
            "credential_id": match.credential_id if same_edition and match else None,
            "registration_id": match.registration_id if same_edition and match else None,
            "mode": scan.mode,
            "outcome": outcome,
            "provisional_result": scan.provisional,
            "scanned_at": scanned_at,
            "received_at": received,
            "local_date": day,
        },
    )
    if attempt_id is None:
        existing = await repo.get_attempt_by_event(session, scan.scan_event_id)
        assert existing is not None  # noqa: S101 - conflict means it exists
        return await _replay(session, device, existing)
    first = False
    if outcome == ScanOutcome.ACCEPTED and match is not None:
        first = await repo.claim_first_entry(
            session,
            edition_id=device.edition_id,
            registration_id=match.registration_id,
            local_date=day,
            attempt_id=attempt_id,
            scanned_at=scanned_at,
            gate_id=device.gate_id,
        )
    label = (match.registration_code, match.first_name) if match else None
    return _out(
        scan.scan_event_id, result_for(outcome, first), scanned_at, day, label, scan.provisional
    )


async def scan_online(session: AsyncSession, device: DeviceAuth, data: ScanIn) -> ScanResultOut:
    """POST /gate/device/scans."""
    await exhibitions_service.ensure_writable(session, device.edition_id)
    return await _process(
        session,
        device,
        _Scan(data.scan_event_id, data.token_hash, datetime.now(UTC), ScanMode.ONLINE),
    )


async def sync_scans(session: AsyncSession, device: DeviceAuth, data: SyncIn) -> SyncOut:
    """POST /gate/device/scans/sync. Oldest first, so the earliest scan wins the first entry."""
    await exhibitions_service.ensure_writable(session, device.edition_id)
    if len({i.scan_event_id for i in data.items}) != len(data.items):
        raise ValidationFailed(fields={"items": "Duplicate scan_event_id in one batch."})
    order = sorted(range(len(data.items)), key=lambda i: data.items[i].scanned_at)
    results: dict[int, ScanResultOut] = {}
    for i in order:
        item = data.items[i]
        results[i] = await _process(
            session,
            device,
            _Scan(
                item.scan_event_id,
                item.token_hash,
                item.scanned_at,
                ScanMode.OFFLINE,
                item.provisional_result,
            ),
        )
    out = [results[i] for i in range(len(data.items))]
    rejected = [r.scan_event_id for r in out if r.result.startswith("REJECTED_")]
    changed = [r.scan_event_id for r in out if r.changed_from_provisional]
    if rejected or changed:
        # spec 10: scanner sync rejections are audited; one entry per batch.
        await audit.record(
            session,
            entity_type=DEVICE_ENTITY,
            entity_id=device.device_id,
            action="sync_reconciled",
            after={
                "items": len(out),
                "rejected": len(rejected),
                "changed_from_provisional": len(changed),
                "scan_event_ids": [str(x) for x in (rejected + changed)[:50]],
            },
            edition_id=device.edition_id,
        )
    return SyncOut(results=out)


async def device_cache(session: AsyncSession, device: DeviceAuth) -> CacheOut:
    """GET /gate/device/cache: credentials of the device's edition only (spec 8.1)."""
    s = get_settings()
    now = datetime.now(UTC)
    ttl = (
        timedelta(minutes=device.edition.scanner_cache_ttl_minutes)
        if device.edition.scanner_cache_ttl_minutes
        else timedelta(seconds=s.scanner_cache_ttl_seconds)
    )
    today = local_date(now, device.timezone)
    entered = await repo.entered_on(session, device.edition_id, today)
    rows = await registrations_service.gate_cache_rows(session, device.edition_id)
    return CacheOut(
        edition_id=device.edition_id,
        gate_id=device.gate_id,
        generated_at=now,
        expires_at=now + ttl,
        local_date=today,
        credentials=[
            CacheEntry(token_hash=h, status=st, registration_code=code, first_name=name)
            for h, st, code, name in rows
        ],
        entered_today=await registrations_service.active_token_hashes(session, entered),
    )


# --- gates (desk) ----------------------------------------------------------------------------


def _check_gate_scope(scope: Scope, gate_id: uuid.UUID) -> None:
    if not scope.full_access and gate_id not in scope.gate_ids:
        raise NotFound("Gate not found.")


async def _gate_in_scope(
    session: AsyncSession, ctx: AuthContext, gate_id: uuid.UUID, *, full: bool = False
) -> tuple[Gate, Scope]:
    gate = await repo.get_gate(session, gate_id)
    if gate is None:
        raise NotFound("Gate not found.")
    try:
        scope = ctx.scope_for(gate.edition_id)
    except NotFound as e:
        raise NotFound("Gate not found.") from e
    _check_gate_scope(scope, gate.id)
    if full and not scope.full_access:
        raise PermissionDenied()
    return gate, scope


async def list_gates(
    session: AsyncSession, ctx: AuthContext, edition_id: uuid.UUID
) -> list[GateOut]:
    scope = ctx.scope_for(edition_id)
    return [GateOut.model_validate(g) for g in await repo.list_gates(session, scope)]


async def create_gate(session: AsyncSession, ctx: AuthContext, data: GateIn) -> GateOut:
    if not ctx.scope_for(data.edition_id).full_access:
        raise PermissionDenied()
    await exhibitions_service.ensure_writable(session, data.edition_id)
    gate = Gate(
        edition_id=data.edition_id,
        code=data.code,
        name=data.name,
        created_by=ctx.user.id,
        updated_by=ctx.user.id,
    )
    try:
        async with session.begin_nested():
            session.add(gate)
            await session.flush()
    except IntegrityError as e:
        raise Conflict(
            f"Gate {data.code} already exists in this edition.", fields={"code": "Already used."}
        ) from e
    await session.refresh(gate)
    await audit.record(
        session,
        entity_type=GATE_ENTITY,
        entity_id=gate.id,
        action="create",
        after=audit.snapshot(gate, ("code", "name", "is_active")),
        edition_id=gate.edition_id,
    )
    return GateOut.model_validate(gate)


async def update_gate(
    session: AsyncSession, ctx: AuthContext, gate_id: uuid.UUID, data: GateUpdateIn
) -> GateOut:
    gate, _ = await _gate_in_scope(session, ctx, gate_id, full=True)
    check_version(gate.version, data.version)
    before = audit.snapshot(gate, ("name", "is_active"))
    for key, value in data.model_dump(exclude_unset=True, exclude={"version"}).items():
        setattr(gate, key, value)
    gate.updated_by = ctx.user.id
    await session.flush()
    await session.refresh(gate)
    await audit.record(
        session,
        entity_type=GATE_ENTITY,
        entity_id=gate.id,
        action="update",
        before=before,
        after=audit.snapshot(gate, ("name", "is_active")),
        edition_id=gate.edition_id,
    )
    return GateOut.model_validate(gate)


async def gate_edition(session: AsyncSession, gate_id: uuid.UUID) -> uuid.UUID | None:
    """For identity: GATE-scoped role assignments must name a gate of the same edition."""
    gate = await repo.get_gate(session, gate_id)
    return gate.edition_id if gate else None


# --- devices (desk) --------------------------------------------------------------------------


def _with_code(device: ScannerDevice) -> str:
    code, code_hash = new_activation_code()
    device.activation_code_hash = code_hash
    device.activation_expires_at = datetime.now(UTC) + timedelta(
        seconds=get_settings().scanner_activation_code_ttl_seconds
    )
    return code


async def create_device(
    session: AsyncSession, ctx: AuthContext, data: DeviceIn
) -> DeviceCreatedOut:
    gate, _ = await _gate_in_scope(session, ctx, data.gate_id)
    await exhibitions_service.ensure_writable(session, gate.edition_id)
    device = ScannerDevice(
        edition_id=gate.edition_id,
        gate_id=gate.id,
        name=data.name,
        status=DeviceStatus.PENDING,
        created_by=ctx.user.id,
        updated_by=ctx.user.id,
    )
    code = _with_code(device)
    session.add(device)
    await session.flush()
    await session.refresh(device)
    await audit.record(
        session,
        entity_type=DEVICE_ENTITY,
        entity_id=device.id,
        action="create",
        after=audit.snapshot(device, DEVICE_AUDIT_FIELDS),
        edition_id=device.edition_id,
    )
    return DeviceCreatedOut(**DeviceOut.model_validate(device).model_dump(), activation_code=code)


async def _device_in_scope(
    session: AsyncSession, ctx: AuthContext, device_id: uuid.UUID
) -> ScannerDevice:
    device = await repo.get_device(session, device_id, for_update=True)
    if device is None:
        raise NotFound("Device not found.")
    try:
        await _gate_in_scope(session, ctx, device.gate_id)
    except NotFound as e:
        raise NotFound("Device not found.") from e
    return device


async def new_activation(
    session: AsyncSession, ctx: AuthContext, device_id: uuid.UUID
) -> DeviceCreatedOut:
    """A fresh code for a device that has not been activated yet (old code expired)."""
    device = await _device_in_scope(session, ctx, device_id)
    if device.status != DeviceStatus.PENDING:
        raise Conflict(
            "Only a pending device gets a new activation code.", code="DEVICE_NOT_PENDING"
        )
    code = _with_code(device)
    await session.flush()
    await session.refresh(device)
    await audit.record(
        session,
        entity_type=DEVICE_ENTITY,
        entity_id=device.id,
        action="new_activation_code",
        after={"activation_expires_at": device.activation_expires_at},
        edition_id=device.edition_id,
    )
    return DeviceCreatedOut(**DeviceOut.model_validate(device).model_dump(), activation_code=code)


async def revoke_device(
    session: AsyncSession, ctx: AuthContext, device_id: uuid.UUID, data: DeviceRevokeIn
) -> DeviceOut:
    device = await _device_in_scope(session, ctx, device_id)
    if device.status == DeviceStatus.REVOKED:
        raise Conflict("Device is already revoked.", code="DEVICE_REVOKED")
    before = audit.snapshot(device, DEVICE_AUDIT_FIELDS)
    device.status = DeviceStatus.REVOKED
    device.revoked_at = datetime.now(UTC)
    device.revoked_by = ctx.user.id
    device.revoke_reason = data.reason
    device.activation_code_hash = None
    device.activation_expires_at = None
    device.updated_by = ctx.user.id
    await session.flush()
    await session.refresh(device)
    await audit.record(
        session,
        entity_type=DEVICE_ENTITY,
        entity_id=device.id,
        action="revoke",
        before=before,
        after=audit.snapshot(device, DEVICE_AUDIT_FIELDS),
        edition_id=device.edition_id,
    )
    return DeviceOut.model_validate(device)


async def list_devices(
    session: AsyncSession, ctx: AuthContext, params: DeviceListParams
) -> Page[DeviceOut]:
    scope = ctx.scope_for(params.edition_id)
    rows, total = await repo.list_devices(
        session, scope, params.gate_id, params.status, params.offset, params.page_size
    )
    return Page(
        items=[DeviceOut.model_validate(d) for d in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


# --- history, reconciliation, override (desk) ------------------------------------------------


async def _scan_page(
    session: AsyncSession, rows: Any, total: int, page: int, page_size: int
) -> Page[ScanOut]:
    labels = await registrations_service.registration_labels(
        session, [a.registration_id for a, _ in rows if a.registration_id]
    )
    items = []
    for attempt, first in rows:
        label = labels.get(attempt.registration_id) if attempt.registration_id else None
        items.append(
            ScanOut(
                id=attempt.id,
                scan_event_id=attempt.scan_event_id,
                gate_id=attempt.gate_id,
                device_id=attempt.device_id,
                registration_id=attempt.registration_id,
                registration_code=label[0] if label else None,
                first_name=label[1] if label else None,
                mode=attempt.mode,
                result=result_for(ScanOutcome(attempt.outcome), bool(first)),
                provisional_result=attempt.provisional_result,
                scanned_at=attempt.scanned_at,
                received_at=attempt.received_at,
                local_date=attempt.local_date,
                recorded_by=attempt.recorded_by,
                reason=attempt.reason,
            )
        )
    return Page(items=items, total=total, page=page, page_size=page_size)


async def list_scans(
    session: AsyncSession, ctx: AuthContext, params: ScanListParams
) -> Page[ScanOut]:
    scope = ctx.scope_for(params.edition_id)
    rows, total = await repo.list_attempts(session, scope, params)
    return await _scan_page(session, rows, total, params.page, params.page_size)


async def reconciliation(
    session: AsyncSession, ctx: AuthContext, params: ReconciliationParams
) -> Page[ScanOut]:
    scope = ctx.scope_for(params.edition_id)
    rows, total = await repo.reconciliation(session, scope, params.offset, params.page_size)
    return await _scan_page(session, rows, total, params.page, params.page_size)


async def override(session: AsyncSession, ctx: AuthContext, data: OverrideIn) -> ScanOut:
    """POST /gate/overrides: admit a registered visitor by hand; audited."""
    gate, _ = await _gate_in_scope(session, ctx, data.gate_id)
    await exhibitions_service.ensure_writable(session, gate.edition_id)
    found = await registrations_service.registration_for_override(session, data.registration_id)
    if found is None or found[0].edition_id != gate.edition_id:
        raise NotFound("Registration not found.")
    reg, credential_id = found
    if reg.status != "REGISTERED":
        raise Conflict("This registration is cancelled.", code="REGISTRATION_CANCELLED")
    if await repo.get_attempt_by_event(session, data.scan_event_id) is not None:
        raise Conflict("This override was already recorded.", code="SCAN_EVENT_CONFLICT")
    now = datetime.now(UTC)
    edition = await exhibitions_service.get_edition_by_id(session, gate.edition_id)
    assert edition is not None  # noqa: S101 - FK
    day = local_date(now, edition.timezone)
    attempt_id = await repo.insert_attempt(
        session,
        {
            "edition_id": gate.edition_id,
            "gate_id": gate.id,
            "device_id": None,
            "scan_event_id": data.scan_event_id,
            "token_hash": None,
            "credential_id": credential_id,
            "registration_id": reg.id,
            "mode": ScanMode.OVERRIDE,
            "outcome": ScanOutcome.ACCEPTED,
            "scanned_at": now,
            "received_at": now,
            "local_date": day,
            "recorded_by": ctx.user.id,
            "reason": data.reason,
        },
    )
    if attempt_id is None:
        raise Conflict("This override was already recorded.", code="SCAN_EVENT_CONFLICT")
    await repo.claim_first_entry(
        session,
        edition_id=gate.edition_id,
        registration_id=reg.id,
        local_date=day,
        attempt_id=attempt_id,
        scanned_at=now,
        gate_id=gate.id,
    )
    await audit.record(
        session,
        entity_type="scan_attempt",
        entity_id=attempt_id,
        action="override",
        after={"gate_id": gate.id, "registration_id": reg.id, "reason": data.reason},
        edition_id=gate.edition_id,
    )
    row = await repo.get_attempt_row(session, attempt_id)
    return (await _scan_page(session, [row], 1, 1, 1)).items[0]
