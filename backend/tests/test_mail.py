"""Email accounts, which account an email goes through, test sends, and the email log."""

import uuid
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.core.email import (
    MemorySender,
    OutgoingEmail,
    PermanentEmailError,
    SmtpAccount,
    env_account,
    set_email_sender,
)
from app.core.outbox import OutboxEvent
from app.modules.identity.tasks import send_password_reset_email
from app.modules.mail.models import EmailAccount, EmailJob
from app.modules.mail.tasks import send_test_email_event
from app.modules.registrations.tasks import send_qr_email_event
from tests.factories import RoleGrant, actor, make_edition, make_user
from tests.test_registrations import make_lead, register

ACCOUNTS = "/api/v1/email-accounts"


def account_body(name: str, address: str, **over: Any) -> dict[str, Any]:
    return {
        "name": name,
        "from_name": f"{name} sender",
        "from_address": address,
        "host": "smtp.example.test",
        "port": 587,
        "security": "STARTTLS",
        "username": address,
        "password": "app-password-001",
        **over,
    }


async def events(event_type: str) -> list[uuid.UUID]:
    async with get_sessionmaker()() as session:
        return list(
            await session.scalars(
                select(OutboxEvent.id)
                .where(OutboxEvent.event_type == event_type)
                .order_by(OutboxEvent.created_at)
            )
        )


async def test_accounts_are_super_admin_only_and_hide_the_password() -> None:
    edition = await make_edition()
    _, root = await actor(RoleGrant("SUPER_ADMIN"))
    _, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))
    body = account_body("Marketing", "info@example.test")
    assert (await admin.post(ACCOUNTS, json=body)).status_code == 403
    assert (await admin.get(ACCOUNTS)).status_code == 403

    r = await root.post(ACCOUNTS, json=body)
    assert r.status_code == 201, r.text
    first = r.json()
    assert first["is_default"] is True  # the first account becomes the default
    assert first["has_password"] is True and "password" not in first
    async with get_sessionmaker()() as session:
        row = await session.get(EmailAccount, uuid.UUID(first["id"]))
    assert row is not None and row.password_enc and "app-password-001" not in row.password_enc
    assert (await root.post(ACCOUNTS, json=body)).status_code == 409

    second = (
        await root.post(ACCOUNTS, json=account_body("System", "no-reply@example.test"))
    ).json()
    assert second["is_default"] is False
    # Edition admins pick from active accounts, without SMTP details.
    choices = (await admin.get(f"{ACCOUNTS}/choices")).json()
    assert {c["name"] for c in choices} == {"Marketing", "System"}
    assert "host" not in choices[0]

    url = f"{ACCOUNTS}/{first['id']}"
    r = await root.patch(url, json={"version": first["version"], "is_active": False})
    assert r.status_code == 422  # the default cannot be turned off
    r = await root.post(f"{ACCOUNTS}/{second['id']}/default")
    assert r.status_code == 200 and r.json()["is_default"] is True
    listed = {a["name"]: a["is_default"] for a in (await root.get(ACCOUNTS)).json()}
    assert listed == {"Marketing": False, "System": True}
    # Omitting the password keeps it; the audit never holds it.
    r = await root.patch(url, json={"version": first["version"], "port": 465, "security": "SSL"})
    assert r.status_code == 200 and r.json()["has_password"] is True
    audit = (await root.get("/api/v1/audit-log", params={"entity_type": "email_account"})).json()
    assert "app-password-001" not in str(audit)


async def test_qr_email_uses_the_edition_account_then_default_then_env(
    mailbox: MemorySender,
) -> None:
    edition = await make_edition()
    _, root = await actor(RoleGrant("SUPER_ADMIN"))
    _, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))

    # No account configured yet: the .env settings.
    await register(admin, await make_lead(edition, email="visitor-201@example.test"))
    [first_event] = await events("mail.qr_confirmation")
    assert await send_qr_email_event(first_event) == "SENT"
    assert mailbox.accounts[-1] == env_account()

    default = (
        await root.post(ACCOUNTS, json=account_body("System", "no-reply@example.test"))
    ).json()
    iit = (await root.post(ACCOUNTS, json=account_body("IIT", "info@iit.example.test"))).json()
    ed = (await root.get(f"/api/v1/editions/{edition.id}")).json()
    r = await admin.patch(
        f"/api/v1/editions/{edition.id}",
        json={"version": ed["version"], "email_account_id": iit["id"]},
    )
    assert r.status_code == 200, r.text
    await register(admin, await make_lead(edition, email="visitor-202@example.test"))
    second_event = (await events("mail.qr_confirmation"))[-1]
    assert await send_qr_email_event(second_event) == "SENT"
    used = mailbox.accounts[-1]
    assert isinstance(used, SmtpAccount) and used.from_address == "info@iit.example.test"
    assert used.password == "app-password-001"  # decrypted only for the send

    # The edition's account turned off: the default takes over.
    r = await root.patch(
        f"{ACCOUNTS}/{iit['id']}", json={"version": iit["version"], "is_active": False}
    )
    assert r.status_code == 200
    await register(admin, await make_lead(edition, email="visitor-203@example.test"))
    assert await send_qr_email_event((await events("mail.qr_confirmation"))[-1]) == "SENT"
    assert mailbox.accounts[-1].from_address == "no-reply@example.test"  # type: ignore[union-attr]

    jobs = (await admin.get("/api/v1/email-jobs", params={"edition_id": str(edition.id)})).json()
    assert [j["account_name"] for j in jobs["items"]] == ["System", "IIT", None]
    assert {j["kind"] for j in jobs["items"]} == {"QR_CONFIRMATION"}
    assert default["is_default"] is True

    ed = (await root.get(f"/api/v1/editions/{edition.id}")).json()
    r = await admin.patch(
        f"/api/v1/editions/{edition.id}",
        json={"version": ed["version"], "email_account_id": str(uuid.uuid4())},
    )
    assert r.status_code == 422 and "email_account_id" in r.json()["error"]["fields"]


async def test_send_test_records_the_result_on_the_account(mailbox: MemorySender) -> None:
    _, root = await actor(RoleGrant("SUPER_ADMIN"))
    account = (
        await root.post(ACCOUNTS, json=account_body("System", "no-reply@example.test"))
    ).json()
    r = await root.post(f"{ACCOUNTS}/{account['id']}/test")
    assert r.status_code == 202 and r.json()["recipient"] == "no-reply@example.test"
    [event_id] = await events("mail.test")
    assert await send_test_email_event(event_id) == "SENT"
    assert mailbox.outbox[-1].to == "no-reply@example.test"
    fresh = (await root.get(f"{ACCOUNTS}/{account['id']}")).json()
    assert fresh["last_test_ok"] is True and fresh["last_test_at"] is not None

    class Refusing:
        def send(self, email: OutgoingEmail, account: SmtpAccount | None = None) -> str:
            raise PermanentEmailError("535 Authentication failed")

    set_email_sender(Refusing())
    await root.post(f"{ACCOUNTS}/{account['id']}/test")
    assert await send_test_email_event((await events("mail.test"))[-1]) == "FAILED"
    fresh = (await root.get(f"{ACCOUNTS}/{account['id']}")).json()
    assert fresh["last_test_ok"] is False
    assert fresh["last_test_detail"] == "535 Authentication failed"
    system = (await root.get("/api/v1/email-jobs", params={"scope": "system"})).json()
    assert [(j["kind"], j["status"]) for j in system["items"]] == [
        ("TEST", "FAILED"),
        ("TEST", "SENT"),
    ]
    assert system["items"][0]["error_summary"] == "535 Authentication failed"


async def test_password_reset_is_logged_and_uses_the_default(
    client: AsyncClient, mailbox: MemorySender
) -> None:
    user = await make_user()
    _, root = await actor(RoleGrant("SUPER_ADMIN"))
    await root.post(ACCOUNTS, json=account_body("System", "no-reply@example.test"))
    r = await client.post("/api/v1/auth/password-reset/request", json={"email": user.email})
    assert r.status_code == 202
    [event_id] = await events("mail.password_reset")
    assert await send_password_reset_email(event_id) is True
    assert mailbox.accounts[-1].from_address == "no-reply@example.test"  # type: ignore[union-attr]
    async with get_sessionmaker()() as session:
        job = await session.scalar(select(EmailJob).where(EmailJob.kind == "PASSWORD_RESET"))
    assert job is not None and job.status == "SENT" and job.edition_id is None
    assert job.recipient == user.email and job.user_id == user.id
    system = (await root.get("/api/v1/email-jobs", params={"scope": "system"})).json()
    assert [j["kind"] for j in system["items"]] == ["PASSWORD_RESET"]
    detail = (await root.get(f"/api/v1/email-jobs/{job.id}")).json()
    assert [log["event"] for log in detail["logs"]] == ["QUEUED", "ATTEMPT", "SENT"]
    assert "token" not in str(detail)


async def test_email_log_follows_edition_scope(mailbox: MemorySender) -> None:
    mine, other = await make_edition(), await make_edition()
    _, admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", mine.id))
    _, other_admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", other.id))
    await register(admin, await make_lead(mine, email="visitor-204@example.test"))
    await register(other_admin, await make_lead(other, email="visitor-205@example.test"))
    listed = (await admin.get("/api/v1/email-jobs")).json()
    assert [j["recipient"] for j in listed["items"]] == ["visitor-204@example.test"]
    assert (await admin.get("/api/v1/email-jobs", params={"scope": "system"})).status_code == 403
    r = await admin.get("/api/v1/email-jobs", params={"edition_id": str(other.id)})
    assert r.status_code == 404
    other_job = (await other_admin.get("/api/v1/email-jobs")).json()["items"][0]
    assert (await admin.get(f"/api/v1/email-jobs/{other_job['id']}")).status_code == 404
    _, agent = await actor(RoleGrant("TELEMARKETING_AGENT", "OWNED", mine.id))
    assert (await agent.get("/api/v1/email-jobs")).status_code == 403
