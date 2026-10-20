"""Append-only audit log (spec 10, FEATURES/04-audit-log.md).

`record()` runs inside the caller's transaction, so a rollback also drops the audit row.
Only changed fields are stored, and secret keys are redacted before anything is written.
"""

import enum
import uuid
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, func, inspect
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.context import Source, current_actor_id, current_request_id, current_source
from app.core.db import Base, UUIDPk, get_sessionmaker

REDACTED = "[REDACTED]"
REDACT_KEYS = frozenset(
    {
        "password",
        "password_hash",
        "new_password",
        "session_id",
        "csrf_token",
        "token",
        "token_hash",
        "token_enc",
        "qr_token",
        "device_secret",
        "secret_hash",
        "activation_code",
        "smtp_password",
        "api_key",
    }
)


class AuditLog(UUIDPk, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_entity", "entity_type", "entity_id", "occurred_at"),
        Index("ix_audit_logs_edition_occurred", "edition_id", "occurred_at"),
        Index("ix_audit_logs_actor_occurred", "actor_user_id", "occurred_at"),
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    edition_id: Mapped[uuid.UUID | None] = mapped_column()
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column()
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    request_id: Mapped[str | None] = mapped_column(String(64))


def to_json(value: Any) -> Any:
    """Make a value JSONB-safe."""
    match value:
        case None | bool() | int() | float() | str():
            return value
        case enum.Enum():
            return value.value
        case uuid.UUID() | Decimal():
            return str(value)
        case datetime() | date():
            return value.isoformat()
        case Mapping():
            return {str(k): to_json(v) for k, v in value.items()}
        case list() | tuple() | set() | frozenset():
            return [to_json(v) for v in value]
        case _:
            return str(value)


def redact(data: Any) -> Any:
    """Replace values of secret keys at any depth."""
    if isinstance(data, Mapping):
        return {
            k: (REDACTED if str(k).lower() in REDACT_KEYS else redact(v)) for k, v in data.items()
        }
    if isinstance(data, list):
        return [redact(v) for v in data]
    return data


def diff(
    before: Mapping[str, Any] | None, after: Mapping[str, Any] | None
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Keep only keys whose values differ. Create/delete keep the full side."""
    b = to_json(dict(before)) if before is not None else None
    a = to_json(dict(after)) if after is not None else None
    if b is None or a is None:
        return b, a
    keys = [k for k in {*b, *a} if b.get(k) != a.get(k)]
    return {k: b.get(k) for k in keys}, {k: a.get(k) for k in keys}


def snapshot(obj: Any, fields: Iterable[str] | None = None) -> dict[str, Any]:
    """Column values of an ORM instance (all columns unless fields are given)."""
    mapper = inspect(obj).mapper
    names = list(fields) if fields is not None else [c.key for c in mapper.column_attrs]
    return {name: getattr(obj, name) for name in names}


def _build(
    *,
    entity_type: str,
    entity_id: uuid.UUID | None,
    action: str,
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any] | None,
    edition_id: uuid.UUID | None,
    actor_id: uuid.UUID | None,
    source: Source | None,
) -> AuditLog | None:
    b, a = diff(before, after)
    if before is not None and after is not None and not b and not a:
        return None  # nothing changed
    return AuditLog(
        actor_user_id=actor_id if actor_id is not None else current_actor_id(),
        source=(source or current_source()).value,
        edition_id=edition_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        before=redact(b),
        after=redact(a),
        request_id=current_request_id(),
    )


async def record(
    session: AsyncSession,
    *,
    entity_type: str,
    entity_id: uuid.UUID | None,
    action: str,
    before: Mapping[str, Any] | None = None,
    after: Mapping[str, Any] | None = None,
    edition_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    source: Source | None = None,
) -> AuditLog | None:
    """Write an audit row in the caller's transaction. Returns None if nothing changed."""
    entry = _build(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        before=before,
        after=after,
        edition_id=edition_id,
        actor_id=actor_id,
        source=source,
    )
    if entry is not None:
        session.add(entry)
        await session.flush()
    return entry


async def record_independent(**kwargs: Any) -> None:
    """Commit an audit row on its own, for events whose request fails (failed login)."""
    async with get_sessionmaker()() as session, session.begin():
        await record(session, **kwargs)
