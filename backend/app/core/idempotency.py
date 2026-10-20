"""Idempotency-Key store (BACKEND_RULES/api.md).

`claim()` inserts the key with ON CONFLICT DO NOTHING inside the request transaction. A
concurrent request with the same key blocks on the unique index until the first commits,
then reads the stored response. A rolled-back first attempt leaves no row, so a retry runs.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, delete, func, select
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import get_settings
from app.core.db import Base, UUIDPk
from app.core.errors import IdempotencyMismatch, ValidationFailed


class IdempotencyKey(UUIDPk, Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("scope", "key"),)

    # Endpoint + caller, so two users can never collide on the same key.
    scope: Mapped[str] = mapped_column(String(200), nullable=False)
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer)
    response: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


@dataclass(frozen=True)
class Stored:
    status_code: int
    response: dict[str, Any]


def request_hash(body: Any) -> str:
    raw = json.dumps(body, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def validate_key(key: str | None, *, required: bool) -> str | None:
    if key is None:
        if required:
            raise ValidationFailed(
                "Idempotency-Key header is required.", fields={"Idempotency-Key": "Required."}
            )
        return None
    key = key.strip()
    if not 8 <= len(key) <= 200 or not key.isprintable():
        raise ValidationFailed(fields={"Idempotency-Key": "Use 8-200 printable characters."})
    return key


async def claim(
    session: AsyncSession, scope: str, key: str, body: Any
) -> tuple[uuid.UUID | None, Stored | None]:
    """Returns (claim id, None) when this request should run, or (None, stored response)."""
    digest = request_hash(body)
    ttl = timedelta(seconds=get_settings().idempotency_ttl_seconds)
    claimed = await session.scalar(
        insert(IdempotencyKey)
        .values(scope=scope, key=key, request_hash=digest, expires_at=datetime.now(UTC) + ttl)
        .on_conflict_do_nothing(index_elements=["scope", "key"])
        .returning(IdempotencyKey.id)
    )
    if claimed is not None:
        return claimed, None
    row = await session.scalar(
        select(IdempotencyKey).where(IdempotencyKey.scope == scope, IdempotencyKey.key == key)
    )
    if row is None or row.response is None or row.status_code is None:
        # Expired and purged between statements, or an earlier attempt crashed mid-way.
        raise IdempotencyMismatch("Request with this key is still being processed.")
    if row.request_hash != digest:
        raise IdempotencyMismatch()
    return None, Stored(row.status_code, row.response)


async def store(
    session: AsyncSession, claim_id: uuid.UUID, status_code: int, response: dict[str, Any]
) -> None:
    row = await session.get(IdempotencyKey, claim_id)
    if row is not None:
        row.status_code = status_code
        row.response = json.loads(json.dumps(response, default=str))
        await session.flush()


async def purge_expired(session: AsyncSession) -> int:
    result = await session.execute(
        delete(IdempotencyKey).where(IdempotencyKey.expires_at < datetime.now(UTC))
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]
