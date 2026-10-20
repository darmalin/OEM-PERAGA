from httpx import AsyncClient
from sqlalchemy import text

from app.core import outbox
from app.core.db import get_sessionmaker
from app.core.logging import mask_email, mask_phone


async def test_health_live(client: AsyncClient) -> None:
    r = await client.get("/api/v1/health/live")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_health_ready_checks_db_and_redis(client: AsyncClient) -> None:
    r = await client.get("/api/v1/health/ready")
    assert r.status_code == 200
    assert r.json()["checks"] == {"database": "ok", "redis": "ok"}


async def test_unknown_route_uses_error_envelope(client: AsyncClient) -> None:
    r = await client.get("/api/v1/does-not-exist", headers={"X-Request-ID": "abc123"})
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["request_id"] == "abc123"
    assert r.headers["X-Request-ID"] == "abc123"


async def test_security_headers(client: AsyncClient) -> None:
    r = await client.get("/api/v1/health/live")
    assert r.headers["X-Content-Type-Options"] == "nosniff"


async def test_outbox_claim_skips_dispatched() -> None:
    async with get_sessionmaker()() as session, session.begin():
        await outbox.enqueue(session, "test.event", "core.noop", {"a": 1})
    async with get_sessionmaker()() as session, session.begin():
        events = await outbox.claim_pending(session)
        assert len(events) == 1
        await session.execute(text("UPDATE outbox_events SET dispatched_at = now()"))
    async with get_sessionmaker()() as session, session.begin():
        assert await outbox.claim_pending(session) == []


def test_masking() -> None:
    assert mask_email("quinn@gmail.com") == "q***@gmail.com"
    assert mask_phone("+6281234567") == "********567"
