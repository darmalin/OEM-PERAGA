import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.core.db import get_sessionmaker
from app.main import app
from app.modules.checkin.models import ScannerDevice
from app.modules.checkin.rules import (
    activation_code_hash,
    local_date,
    new_activation_code,
    trusted_scan_time,
)
from app.modules.checkin.service import is_device_guard
from app.modules.exhibitions.models import Edition
from app.modules.registrations.models import QrCredential
from app.modules.visitors.models import VisitorLead
from tests.factories import RoleGrant, actor, make_edition
from tests.routes import api_routes

DEVICE = "/api/v1/gate/device"


# --- pure rules ------------------------------------------------------------------------------


def test_local_date_uses_edition_timezone() -> None:
    moment = datetime(2027, 3, 10, 17, 30, tzinfo=UTC)  # 00:30 on the 11th in Jakarta
    assert str(local_date(moment, "Asia/Jakarta")) == "2027-03-11"
    assert str(local_date(moment, "UTC")) == "2027-03-10"


def test_future_device_clock_is_not_trusted() -> None:
    now = datetime(2027, 3, 10, 8, 0, tzinfo=UTC)
    assert trusted_scan_time(now - timedelta(hours=2), now) == now - timedelta(hours=2)
    assert trusted_scan_time(now + timedelta(minutes=3), now) == now + timedelta(minutes=3)
    assert trusted_scan_time(now + timedelta(hours=1), now) == now


def test_activation_code_normalization() -> None:
    code, code_hash = new_activation_code()
    assert len(code) == 11 and code[5] == "-"
    assert activation_code_hash(code.lower().replace("-", " ")) == code_hash


def test_device_routes_use_the_device_guard() -> None:
    def guarded(route: APIRoute) -> bool:
        stack = list(route.dependant.dependencies)
        while stack:
            dep = stack.pop()
            if is_device_guard(dep.call):
                return True
            stack.extend(dep.dependencies)
        return False

    device_routes = [(p, r) for p, r in api_routes() if p.startswith(f"{DEVICE}/")]
    assert len(device_routes) == 5
    missing = [p for p, r in device_routes if p != f"{DEVICE}/activate" and not guarded(r)]
    assert missing == []


# --- helpers ---------------------------------------------------------------------------------


async def create_gate(admin: AsyncClient, edition: Edition, code: str = "A") -> str:
    r = await admin.post(
        "/api/v1/gates", json={"edition_id": str(edition.id), "code": code, "name": f"Gate {code}"}
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def activated_device(admin: AsyncClient, gate_id: str) -> tuple[str, AsyncClient]:
    r = await admin.post("/api/v1/gate/devices", json={"gate_id": gate_id, "name": "Phone 1"})
    assert r.status_code == 201, r.text
    code = r.json()["activation_code"]
    device = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    a = await device.post(f"{DEVICE}/activate", json={"activation_code": code})
    assert a.status_code == 200, a.text
    device.headers["X-Device-Token"] = a.json()["device_token"]
    return str(r.json()["id"]), device


async def registered_hash(admin: AsyncClient, edition: Edition, n: int) -> str:
    """Register a visitor through the API and return the QR token hash."""
    async with get_sessionmaker()() as session, session.begin():
        lead = VisitorLead(
            edition_id=edition.id,
            registration_code=f"{edition.registration_id_prefix}{n:06d}",
            first_name=f"Visitor {n:03d}",
            email=f"visitor-{n:03d}@example.test",
            email_normalized=f"visitor-{n:03d}@example.test",
            source="MANUAL",
            custom_fields={},
        )
        session.add(lead)
    r = await admin.post(
        "/api/v1/visitor-registrations",
        json={"visitor_lead_id": str(lead.id), "send_email": False},
        headers={"Idempotency-Key": uuid.uuid4().hex},
    )
    assert r.status_code == 201, r.text
    async with get_sessionmaker()() as session:
        token_hash = await session.scalar(
            select(QrCredential.token_hash).where(
                QrCredential.registration_id == uuid.UUID(r.json()["id"])
            )
        )
    assert token_hash is not None
    return token_hash


async def setup() -> tuple[Edition, AsyncClient, str, AsyncClient]:
    edition = await make_edition()
    _, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))
    gate_id = await create_gate(admin, edition)
    _, device = await activated_device(admin, gate_id)
    return edition, admin, gate_id, device


async def scan(device: AsyncClient, token_hash: str, event: uuid.UUID | None = None) -> Any:
    return await device.post(
        f"{DEVICE}/scans",
        json={"scan_event_id": str(event or uuid.uuid4()), "token_hash": token_hash},
    )


async def count(sql: str) -> Any:
    async with get_sessionmaker()() as session:
        return await session.scalar(text(sql))


# --- devices ---------------------------------------------------------------------------------


async def test_device_activation_lifecycle() -> None:
    edition = await make_edition()
    _, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))
    gate_id = await create_gate(admin, edition)
    r = await admin.post("/api/v1/gate/devices", json={"gate_id": gate_id, "name": "Phone 1"})
    assert r.headers["cache-control"] == "no-store"
    device_id, code = r.json()["id"], r.json()["activation_code"]
    anon = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    assert (
        await anon.post(f"{DEVICE}/activate", json={"activation_code": "AAAAA-BBBBB"})
    ).status_code == 422
    ok = await anon.post(f"{DEVICE}/activate", json={"activation_code": code.lower()})
    assert ok.status_code == 200
    token = ok.json()["device_token"]
    assert token.startswith(device_id)
    reused = await anon.post(f"{DEVICE}/activate", json={"activation_code": code})
    assert reused.status_code == 422

    me = await anon.get(f"{DEVICE}/me", headers={"X-Device-Token": token})
    assert me.json()["gate_code"] == "A"
    assert me.json()["edition_code"] == edition.code
    bad = await anon.get(f"{DEVICE}/me", headers={"X-Device-Token": f"{device_id}.wrong"})
    assert bad.status_code == 401
    assert (await anon.get(f"{DEVICE}/me")).status_code == 401

    again = await admin.post(f"/api/v1/gate/devices/{device_id}/activation-code")
    assert again.json()["error"]["code"] == "DEVICE_NOT_PENDING"

    rv = await admin.post(f"/api/v1/gate/devices/{device_id}/revoke", json={"reason": "Lost"})
    assert rv.json()["status"] == "REVOKED"
    gone = await anon.get(f"{DEVICE}/me", headers={"X-Device-Token": token})
    assert gone.status_code == 403
    assert gone.json()["error"]["code"] == "DEVICE_REVOKED"

    async with get_sessionmaker()() as session:
        device = await session.get(ScannerDevice, uuid.UUID(device_id))
    assert device is not None and device.secret_hash is not None
    assert device.secret_hash not in token


async def test_expired_activation_code() -> None:
    edition = await make_edition()
    _, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))
    gate_id = await create_gate(admin, edition)
    r = await admin.post("/api/v1/gate/devices", json={"gate_id": gate_id, "name": "Phone 1"})
    async with get_sessionmaker()() as session, session.begin():
        device = await session.get(ScannerDevice, uuid.UUID(r.json()["id"]))
        assert device is not None
        device.activation_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    anon = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    code = r.json()["activation_code"]
    assert (
        await anon.post(f"{DEVICE}/activate", json={"activation_code": code})
    ).status_code == 422
    fresh = await admin.post(f"/api/v1/gate/devices/{r.json()['id']}/activation-code")
    ok = await anon.post(
        f"{DEVICE}/activate", json={"activation_code": fresh.json()["activation_code"]}
    )
    assert ok.status_code == 200


async def test_closed_gate_blocks_scans() -> None:
    edition, admin, gate_id, device = await setup()
    gate = (await admin.get("/api/v1/gates", params={"edition_id": str(edition.id)})).json()[0]
    await admin.patch(
        f"/api/v1/gates/{gate_id}", json={"version": gate["version"], "is_active": False}
    )
    r = await scan(device, "0" * 64)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "GATE_INACTIVE"


async def test_duplicate_gate_code() -> None:
    edition = await make_edition()
    _, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))
    await create_gate(admin, edition, "MAIN")
    r = await admin.post(
        "/api/v1/gates", json={"edition_id": str(edition.id), "code": "main", "name": "Again"}
    )
    assert r.status_code == 409


# --- online scanning -------------------------------------------------------------------------


async def test_first_then_repeat_entry() -> None:
    edition, admin, _, device = await setup()
    token_hash = await registered_hash(admin, edition, 1)
    first = await scan(device, token_hash)
    assert first.status_code == 200, first.text
    assert first.json()["result"] == "FIRST_ENTRY"
    assert first.json()["first_name"] == "Visitor 001"
    second = await scan(device, token_hash)
    assert second.json()["result"] == "REPEAT_ENTRY"
    assert await count("SELECT count(*) FROM visitor_checkins") == 1
    assert await count("SELECT count(*) FROM scan_attempts") == 2


async def test_next_day_is_first_entry_again() -> None:
    edition, admin, _, device = await setup()
    token_hash = await registered_hash(admin, edition, 1)
    yesterday = datetime.now(UTC) - timedelta(days=1)
    r = await device.post(
        f"{DEVICE}/scans/sync",
        json={
            "items": [
                {
                    "scan_event_id": str(uuid.uuid4()),
                    "token_hash": token_hash,
                    "scanned_at": yesterday.isoformat(),
                }
            ]
        },
    )
    assert r.json()["results"][0]["result"] == "FIRST_ENTRY"
    assert (await scan(device, token_hash)).json()["result"] == "FIRST_ENTRY"


async def test_retried_scan_is_counted_once() -> None:
    edition, admin, _, device = await setup()
    token_hash = await registered_hash(admin, edition, 1)
    event = uuid.uuid4()
    results = [(await scan(device, token_hash, event)).json()["result"] for _ in range(5)]
    assert results == ["FIRST_ENTRY"] * 5
    assert await count("SELECT count(*) FROM scan_attempts") == 1


async def test_rejections() -> None:
    edition, admin, _, device = await setup()
    unknown = await scan(device, "f" * 64)
    assert unknown.json()["result"] == "REJECTED_UNKNOWN"

    revoked = await registered_hash(admin, edition, 2)
    async with get_sessionmaker()() as session:
        reg_id = await session.scalar(
            select(QrCredential.registration_id).where(QrCredential.token_hash == revoked)
        )
    await admin.post(f"/api/v1/visitor-registrations/{reg_id}/revoke-qr", json={"reason": "Test"})
    assert (await scan(device, revoked)).json()["result"] == "REJECTED_REVOKED"

    other = await make_edition()
    _, other_admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", other.id))
    foreign = await registered_hash(other_admin, other, 3)
    r = await scan(device, foreign)
    assert r.json()["result"] == "REJECTED_WRONG_EDITION"
    assert r.json()["first_name"] is None
    assert await count("SELECT count(*) FROM visitor_checkins") == 0


async def test_scan_body_rejects_raw_tokens() -> None:
    _, _, _, device = await setup()
    r = await device.post(
        f"{DEVICE}/scans", json={"scan_event_id": str(uuid.uuid4()), "token_hash": "raw-token"}
    )
    assert r.status_code == 422


# --- offline sync ----------------------------------------------------------------------------


async def test_two_offline_devices_one_first_entry() -> None:
    edition, admin, gate_id, device_a = await setup()
    _, device_b = await activated_device(admin, gate_id)
    token_hash = await registered_hash(admin, edition, 1)
    now = datetime.now(UTC)
    item_a = {
        "scan_event_id": str(uuid.uuid4()),
        "token_hash": token_hash,
        "scanned_at": (now - timedelta(minutes=5)).isoformat(),
        "provisional_result": "FIRST_ENTRY",
    }
    item_b = {
        "scan_event_id": str(uuid.uuid4()),
        "token_hash": token_hash,
        "scanned_at": (now - timedelta(minutes=10)).isoformat(),
        "provisional_result": "FIRST_ENTRY",
    }
    a = await device_a.post(f"{DEVICE}/scans/sync", json={"items": [item_a]})
    assert a.json()["results"][0]["result"] == "FIRST_ENTRY"
    b = await device_b.post(f"{DEVICE}/scans/sync", json={"items": [item_b]})
    assert b.json()["results"][0]["result"] == "FIRST_ENTRY"

    # B scanned earlier, so A's scan is now the repeat entry.
    replay = await device_a.post(f"{DEVICE}/scans/sync", json={"items": [item_a]})
    assert replay.json()["results"][0]["result"] == "REPEAT_ENTRY"
    assert replay.json()["results"][0]["changed_from_provisional"] is True
    assert await count("SELECT count(*) FROM visitor_checkins") == 1
    assert await count("SELECT count(*) FROM scan_attempts") == 2

    rec = await admin.get("/api/v1/gate/reconciliation", params={"edition_id": str(edition.id)})
    assert [i["scan_event_id"] for i in rec.json()["items"]] == [item_a["scan_event_id"]]
    assert rec.json()["items"][0]["result"] == "REPEAT_ENTRY"

    first = await admin.get(
        "/api/v1/gate/scans", params={"edition_id": str(edition.id), "result": "FIRST_ENTRY"}
    )
    assert [i["scan_event_id"] for i in first.json()["items"]] == [item_b["scan_event_id"]]


async def test_sync_batch_order_and_duplicates() -> None:
    edition, admin, _, device = await setup()
    token_hash = await registered_hash(admin, edition, 1)
    now = datetime.now(UTC)
    later = {
        "scan_event_id": str(uuid.uuid4()),
        "token_hash": token_hash,
        "scanned_at": (now - timedelta(minutes=1)).isoformat(),
        "provisional_result": "FIRST_ENTRY",
    }
    earlier = {
        "scan_event_id": str(uuid.uuid4()),
        "token_hash": token_hash,
        "scanned_at": (now - timedelta(minutes=2)).isoformat(),
        "provisional_result": "REPEAT_ENTRY",
    }
    unknown = {
        "scan_event_id": str(uuid.uuid4()),
        "token_hash": "e" * 64,
        "scanned_at": now.isoformat(),
    }
    r = await device.post(f"{DEVICE}/scans/sync", json={"items": [later, earlier, unknown]})
    results = r.json()["results"]
    assert [x["scan_event_id"] for x in results] == [
        later["scan_event_id"],
        earlier["scan_event_id"],
        unknown["scan_event_id"],
    ]
    assert [x["result"] for x in results] == ["REPEAT_ENTRY", "FIRST_ENTRY", "REJECTED_UNKNOWN"]
    assert await count("SELECT count(*) FROM audit_logs WHERE action = 'sync_reconciled'") == 1

    dup = await device.post(f"{DEVICE}/scans/sync", json={"items": [later, later]})
    assert dup.status_code == 422


async def test_scan_event_id_of_other_device_conflicts() -> None:
    edition, admin, gate_id, device_a = await setup()
    _, device_b = await activated_device(admin, gate_id)
    token_hash = await registered_hash(admin, edition, 1)
    event = uuid.uuid4()
    await scan(device_a, token_hash, event)
    assert (await scan(device_b, token_hash, event)).status_code == 409


# --- cache -----------------------------------------------------------------------------------


async def test_cache_has_only_own_edition() -> None:
    edition, admin, _, device = await setup()
    mine = await registered_hash(admin, edition, 1)
    other = await make_edition()
    _, other_admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", other.id))
    foreign = await registered_hash(other_admin, other, 2)
    await scan(device, mine)
    r = await device.get(f"{DEVICE}/cache")
    assert r.headers["cache-control"] == "no-store"
    body = r.json()
    assert [c["token_hash"] for c in body["credentials"]] == [mine]
    assert body["credentials"][0] == {
        "token_hash": mine,
        "status": "ACTIVE",
        "registration_code": f"{edition.registration_id_prefix}000001",
        "first_name": "Visitor 001",
    }
    assert foreign not in str(body)
    assert body["entered_today"] == [mine]
    ttl = datetime.fromisoformat(body["expires_at"]) - datetime.fromisoformat(body["generated_at"])
    assert ttl == timedelta(hours=12)


# --- desk: override, scope -------------------------------------------------------------------


async def test_override_admits_registered_visitor() -> None:
    edition, admin, gate_id, _ = await setup()
    token_hash = await registered_hash(admin, edition, 1)
    async with get_sessionmaker()() as session:
        reg_id = await session.scalar(
            select(QrCredential.registration_id).where(QrCredential.token_hash == token_hash)
        )
    body = {
        "scan_event_id": str(uuid.uuid4()),
        "gate_id": gate_id,
        "registration_id": str(reg_id),
        "reason": "QR screen cracked",
    }
    r = await admin.post("/api/v1/gate/overrides", json=body)
    assert r.status_code == 201, r.text
    assert r.json()["result"] == "FIRST_ENTRY"
    assert r.json()["mode"] == "OVERRIDE"
    assert (await admin.post("/api/v1/gate/overrides", json=body)).status_code == 409
    assert await count("SELECT count(*) FROM audit_logs WHERE action = 'override'") == 1

    _, staff = await actor(RoleGrant("GATE_STAFF", "EDITION", edition.id))
    assert (await staff.post("/api/v1/gate/overrides", json=body)).status_code == 403


async def test_gate_scope_limits_history() -> None:
    edition, admin, gate_a, device_a = await setup()
    gate_b = await create_gate(admin, edition, "B")
    _, device_b = await activated_device(admin, gate_b)
    token_hash = await registered_hash(admin, edition, 1)
    await scan(device_a, token_hash)
    await scan(device_b, token_hash)
    _, supervisor = await actor(
        RoleGrant("GATE_SUPERVISOR", "GATE", edition.id, gate_id=uuid.UUID(gate_a))
    )
    gates = await supervisor.get("/api/v1/gates", params={"edition_id": str(edition.id)})
    assert [g["code"] for g in gates.json()] == ["A"]
    scans = await supervisor.get("/api/v1/gate/scans", params={"edition_id": str(edition.id)})
    assert {s["gate_id"] for s in scans.json()["items"]} == {gate_a}
    devices = await supervisor.get("/api/v1/gate/devices", params={"edition_id": str(edition.id)})
    assert {d["gate_id"] for d in devices.json()["items"]} == {gate_a}
    other = await supervisor.post("/api/v1/gate/devices", json={"gate_id": gate_b, "name": "x"})
    assert other.status_code == 404
    patch = await supervisor.patch(f"/api/v1/gates/{gate_a}", json={"version": 1, "name": "x"})
    assert patch.status_code == 403


@pytest.mark.parametrize("same_edition", [True, False])
async def test_gate_role_assignment(same_edition: bool) -> None:
    edition = await make_edition()
    _, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))
    gate_edition = edition if same_edition else await make_edition()
    if same_edition:
        gate_id = await create_gate(admin, edition)
    else:
        _, other_admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", gate_edition.id))
        gate_id = await create_gate(other_admin, gate_edition)
    staff, _ = await actor()
    roles = (await admin.get("/api/v1/roles")).json()
    role_id = next(r["id"] for r in roles if r["code"] == "GATE_STAFF")
    r = await admin.post(
        f"/api/v1/users/{staff.id}/role-assignments",
        json={
            "role_id": role_id,
            "scope_type": "GATE",
            "edition_id": str(edition.id),
            "gate_id": gate_id,
        },
    )
    if same_edition:
        assert r.status_code == 201, r.text
        assert r.json()["gate_id"] == gate_id
    else:
        assert r.status_code == 422
        assert "gate_id" in r.json()["error"]["fields"]


async def test_last_seen_is_written_at_most_once_a_minute() -> None:
    edition, admin, _, device = await setup()

    async def last_seen() -> Any:
        r = await admin.get("/api/v1/gate/devices", params={"edition_id": str(edition.id)})
        return r.json()["items"][0]["last_seen_at"]

    await device.get(f"{DEVICE}/me")
    first = await last_seen()
    assert first is not None
    await device.get(f"{DEVICE}/me")
    assert await last_seen() == first
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(
            text("UPDATE scanner_devices SET last_seen_at = now() - interval '2 minutes'")
        )
    await device.get(f"{DEVICE}/me")
    assert await last_seen() > first
