import uuid

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from app.core import audit
from app.core.audit import REDACTED, AuditLog
from app.core.db import get_sessionmaker
from tests.factories import PASSWORD, RoleGrant, actor, make_edition


def test_redaction_at_any_depth() -> None:
    data = {
        "password": "p",
        "Token": "t",
        "nested": {"qr_token": "q", "ok": 1, "items": [{"device_secret": "s"}]},
        "name": "Ann",
    }
    assert audit.redact(data) == {
        "password": REDACTED,
        "Token": REDACTED,
        "nested": {"qr_token": REDACTED, "ok": 1, "items": [{"device_secret": REDACTED}]},
        "name": "Ann",
    }


def test_diff_keeps_only_changed_fields() -> None:
    uid = uuid.uuid4()
    before, after = audit.diff({"a": 1, "b": uid, "c": "x"}, {"a": 2, "b": uid, "c": "x"})
    assert before == {"a": 1} and after == {"a": 2}
    assert audit.diff(None, {"a": 1}) == (None, {"a": 1})


async def test_rollback_also_drops_audit_row() -> None:
    with pytest.raises(RuntimeError):
        async with get_sessionmaker()() as session, session.begin():
            await audit.record(session, entity_type="x", entity_id=uuid.uuid4(), action="create")
            raise RuntimeError("boom")
    async with get_sessionmaker()() as session:
        assert await session.scalar(select(func.count()).select_from(AuditLog)) == 0


async def test_unchanged_update_writes_nothing() -> None:
    async with get_sessionmaker()() as session, session.begin():
        entry = await audit.record(
            session,
            entity_type="x",
            entity_id=uuid.uuid4(),
            action="update",
            before={"a": 1},
            after={"a": 1},
        )
    assert entry is None


async def test_audit_rows_are_append_only() -> None:
    async with get_sessionmaker()() as session, session.begin():
        await audit.record(session, entity_type="x", entity_id=uuid.uuid4(), action="create")
    for stmt in ("UPDATE audit_logs SET action = 'tampered'", "DELETE FROM audit_logs"):
        with pytest.raises(DBAPIError, match="append-only"):
            async with get_sessionmaker()() as session, session.begin():
                await session.execute(text(stmt))


async def test_identity_actions_are_audited_without_secrets() -> None:
    admin, client = await actor(RoleGrant("SUPER_ADMIN"))
    r = await client.post(
        "/api/v1/users",
        json={"email": "audited@example.test", "full_name": "Audited", "password": PASSWORD},
    )
    user_id = r.json()["id"]
    await client.patch(f"/api/v1/users/{user_id}", json={"version": 1, "full_name": "Renamed"})
    bad = await client.post(
        "/api/v1/auth/login", json={"email": "audited@example.test", "password": "wrong-password!"}
    )
    assert bad.status_code == 401

    logs = (await client.get("/api/v1/audit-logs", params={"entity_id": user_id})).json()
    actions = [i["action"] for i in logs["items"]]
    assert actions == ["login_failed", "update", "create"]
    update = logs["items"][1]
    assert update["before"] == {"full_name": "Audited"}
    assert update["after"] == {"full_name": "Renamed"}
    assert update["actor_user_id"] == str(admin.id)
    assert update["request_id"]

    async with get_sessionmaker()() as session:
        dump = await session.scalar(
            text("SELECT string_agg(before::text || after::text, '') FROM audit_logs")
        )
    assert PASSWORD not in (dump or "")
    assert "password_hash" not in (dump or "")
    failed = logs["items"][0]["after"]
    assert failed["email"] == "a***@example.test"


async def test_login_success_audited() -> None:
    user, _ = await actor()
    async with get_sessionmaker()() as session:
        rows = (await session.scalars(select(AuditLog).where(AuditLog.entity_id == user.id))).all()
    assert [r.action for r in rows] == ["login"]
    assert rows[0].actor_user_id == user.id


async def test_audit_read_requires_permission_and_scope() -> None:
    mine, other = (await make_edition()).id, (await make_edition()).id
    async with get_sessionmaker()() as session, session.begin():
        await audit.record(
            session, entity_type="x", entity_id=uuid.uuid4(), action="a", edition_id=mine
        )
        await audit.record(
            session, entity_type="x", entity_id=uuid.uuid4(), action="b", edition_id=other
        )
        await audit.record(session, entity_type="x", entity_id=uuid.uuid4(), action="c")

    _, agent = await actor(RoleGrant("TELEMARKETING_AGENT", "OWNED", mine))
    assert (await agent.get("/api/v1/audit-logs")).status_code == 403

    _, edition_admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", mine))
    items = (await edition_admin.get("/api/v1/audit-logs", params={"entity_type": "x"})).json()[
        "items"
    ]
    assert [i["action"] for i in items] == ["a"]
    r = await edition_admin.get("/api/v1/audit-logs", params={"edition_id": str(other)})
    assert r.status_code == 404

    _, root = await actor(RoleGrant("SUPER_ADMIN"))
    items = (await root.get("/api/v1/audit-logs", params={"entity_type": "x"})).json()["items"]
    assert sorted(i["action"] for i in items) == ["a", "b", "c"]
    r = await root.get("/api/v1/audit-logs", params={"bogus": "1"})
    assert r.status_code == 422
