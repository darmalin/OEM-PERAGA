import asyncio
import json
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.core.crypto import decrypt, sha256_hex
from app.core.db import get_sessionmaker
from app.core.email import (
    MemorySender,
    OutgoingEmail,
    SmtpAccount,
    TransientEmailError,
    set_email_sender,
)
from app.core.outbox import OutboxEvent
from app.modules.exhibitions.models import Edition
from app.modules.mail.models import EmailJob
from app.modules.registrations import templates
from app.modules.registrations.models import QrCredential, VisitorRegistration
from app.modules.registrations.tasks import send_qr_email_event
from app.modules.visitors.models import VisitorLead
from tests.factories import RoleGrant, actor, login_client, make_edition, make_user

REGISTER = "/api/v1/visitor-registrations"


async def make_lead(
    edition: Edition,
    *,
    email: str | None = "visitor-001@example.test",
    owner: uuid.UUID | None = None,
) -> str:
    async with get_sessionmaker()() as session, session.begin():
        lead = VisitorLead(
            edition_id=edition.id,
            registration_code=f"{edition.registration_id_prefix}{uuid.uuid4().int % 10**6:06d}",
            first_name="Visitor",
            email=email,
            email_normalized=email,
            phone_normalized=None if email else f"+6281{uuid.uuid4().int % 10**8:08d}",
            source="MANUAL",
            lead_owner_id=owner,
            custom_fields={},
        )
        session.add(lead)
    return str(lead.id)


async def admin_setup() -> tuple[Edition, AsyncClient, str]:
    edition = await make_edition()
    _, client = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))
    return edition, client, await make_lead(edition)


async def register(client: AsyncClient, lead_id: str, key: str | None = None, **body: Any) -> Any:
    headers = {"Idempotency-Key": key or uuid.uuid4().hex}
    return await client.post(REGISTER, json={"visitor_lead_id": lead_id, **body}, headers=headers)


async def run_email_events() -> list[str | None]:
    """Run every QR email outbox event, oldest first, like the worker would."""
    async with get_sessionmaker()() as session:
        ids = list(
            await session.scalars(
                select(OutboxEvent.id)
                .where(OutboxEvent.event_type == "mail.qr_confirmation")
                .order_by(OutboxEvent.created_at)
            )
        )
    return [await send_qr_email_event(i) for i in ids]


async def scalar(sql: str, **params: Any) -> Any:
    async with get_sessionmaker()() as session:
        return await session.scalar(text(sql), params)


# --- registration ----------------------------------------------------------------------------


async def test_register_issues_qr_and_emails_it(mailbox: MemorySender) -> None:
    edition, client, lead_id = await admin_setup()
    r = await register(client, lead_id)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "REGISTERED"
    assert body["qr_status"] == "ACTIVE"
    assert body["email_status"] == "QUEUED"

    lead = (await client.get(f"/api/v1/visitor-leads/{lead_id}")).json()
    assert lead["registration_status"] == "REGISTERED"
    assert lead["qr_status"] == "ACTIVE"

    assert await run_email_events() == ["SENT"]
    assert len(mailbox.outbox) == 1
    email = mailbox.outbox[0]
    assert email.to == "visitor-001@example.test"
    assert edition.name in email.subject
    assert body["registration_code"] in email.text
    assert email.attachments[0].mime_type == "image/png"
    assert email.attachments[0].content_id == templates.QR_IMAGE_CID

    detail = (await client.get(f"{REGISTER}/{body['id']}")).json()
    job = detail["email_jobs"][0]
    assert job["status"] == "SENT"
    assert [log["event"] for log in job["logs"]] == ["QUEUED", "ATTEMPT", "SENT"]
    assert "token" not in json.dumps(detail["credentials"])


async def test_qr_token_is_random_hashed_and_has_no_pii() -> None:
    _, client, lead_id = await admin_setup()
    r = await register(client, lead_id)
    async with get_sessionmaker()() as session:
        cred = await session.scalar(select(QrCredential))
    assert cred is not None
    token = decrypt(cred.token_enc)
    assert sha256_hex(token) == cred.token_hash
    assert len(token) >= 43
    for pii in ("Visitor", "visitor-001", "example.test", r.json()["registration_code"]):
        assert pii not in token


async def test_same_idempotency_key_returns_same_registration() -> None:
    _, client, lead_id = await admin_setup()
    first = await register(client, lead_id, key="reg-key-0001")
    second = await register(client, lead_id, key="reg-key-0001")
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert await scalar("SELECT count(*) FROM visitor_registrations") == 1
    assert await scalar("SELECT count(*) FROM email_jobs") == 1
    assert await scalar("SELECT count(*) FROM qr_credentials") == 1


async def test_idempotency_key_reused_with_other_body_is_409() -> None:
    edition, client, lead_id = await admin_setup()
    other = await make_lead(edition, email="visitor-002@example.test")
    await register(client, lead_id, key="reg-key-0002")
    r = await register(client, other, key="reg-key-0002")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


async def test_idempotency_key_required() -> None:
    _, client, lead_id = await admin_setup()
    r = await client.post(REGISTER, json={"visitor_lead_id": lead_id})
    assert r.status_code == 422
    assert "Idempotency-Key" in r.json()["error"]["fields"]


async def test_second_registration_with_new_key_is_409() -> None:
    _, client, lead_id = await admin_setup()
    assert (await register(client, lead_id)).status_code == 201
    r = await register(client, lead_id)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ALREADY_REGISTERED"


async def test_parallel_registrations_create_one() -> None:
    _, client, lead_id = await admin_setup()
    results = await asyncio.gather(*(register(client, lead_id) for _ in range(5)))
    codes = sorted(r.status_code for r in results)
    assert codes == [201, 409, 409, 409, 409]
    assert await scalar("SELECT count(*) FROM qr_credentials") == 1


async def test_lead_without_email_registers_without_email_job() -> None:
    edition, client, _ = await admin_setup()
    lead_id = await make_lead(edition, email=None)
    r = await register(client, lead_id)
    assert r.status_code == 201
    assert r.json()["qr_status"] == "ACTIVE"
    assert r.json()["email_status"] is None
    assert await scalar("SELECT count(*) FROM email_jobs") == 0


async def test_send_email_false_skips_email() -> None:
    _, client, lead_id = await admin_setup()
    r = await register(client, lead_id, send_email=False)
    assert r.status_code == 201
    assert await scalar("SELECT count(*) FROM email_jobs") == 0


async def test_scope_and_permissions() -> None:
    edition = await make_edition()
    agent = await make_user(RoleGrant("TELEMARKETING_AGENT", "OWNED", edition.id))
    agent_client = await login_client(agent.email)
    own = await make_lead(edition, owner=agent.id)
    other = await make_lead(edition, email="visitor-002@example.test")
    r = await register(agent_client, own, channel="TELEMARKETING")
    assert r.status_code == 201
    assert r.json()["channel"] == "TELEMARKETING"
    assert (await register(agent_client, other)).status_code == 404

    _, gate_client = await actor(RoleGrant("GATE_STAFF", "EDITION", edition.id))
    assert (await register(gate_client, other)).status_code == 403

    # Agents can read their own registration but cannot resend (no registration.resend_qr).
    reg_id = r.json()["id"]
    assert (await agent_client.get(f"{REGISTER}/{reg_id}")).status_code == 200
    resend = await agent_client.post(
        f"{REGISTER}/{reg_id}/resend-qr", headers={"Idempotency-Key": uuid.uuid4().hex}
    )
    assert resend.status_code == 403


async def test_other_edition_registration_is_hidden() -> None:
    _, client, lead_id = await admin_setup()
    reg_id = (await register(client, lead_id)).json()["id"]
    other_edition = await make_edition()
    _, other_admin = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", other_edition.id))
    assert (await other_admin.get(f"{REGISTER}/{reg_id}")).status_code == 404


async def test_list_registrations_filters() -> None:
    edition, client, lead_id = await admin_setup()
    other = await make_lead(edition, email="visitor-002@example.test")
    await register(client, lead_id)
    await register(client, other, send_email=False)
    r = await client.get(REGISTER, params={"edition_id": str(edition.id)})
    assert r.json()["total"] == 2
    r = await client.get(REGISTER, params={"edition_id": str(edition.id), "email_status": "QUEUED"})
    assert [i["visitor_lead_id"] for i in r.json()["items"]] == [lead_id]


# --- resend / revoke ---------------------------------------------------------------------------


async def test_resend_reuses_credential(mailbox: MemorySender) -> None:
    _, client, lead_id = await admin_setup()
    reg_id = (await register(client, lead_id)).json()["id"]
    r = await client.post(
        f"{REGISTER}/{reg_id}/resend-qr", headers={"Idempotency-Key": "resend-0001"}
    )
    assert r.status_code == 202, r.text
    again = await client.post(
        f"{REGISTER}/{reg_id}/resend-qr", headers={"Idempotency-Key": "resend-0001"}
    )
    assert again.json()["id"] == r.json()["id"]
    assert await run_email_events() == ["SENT", "SENT"]
    assert len(mailbox.outbox) == 2
    assert mailbox.outbox[0].attachments[0].content == mailbox.outbox[1].attachments[0].content
    assert await scalar("SELECT count(*) FROM qr_credentials") == 1
    actions = await scalar(
        "SELECT string_agg(action, ',' ORDER BY occurred_at) FROM audit_logs "
        "WHERE entity_type = 'visitor_registration'"
    )
    assert actions == "create,resend_qr"


async def test_revoke_cancels_pending_email(mailbox: MemorySender) -> None:
    _, client, lead_id = await admin_setup()
    reg_id = (await register(client, lead_id)).json()["id"]
    r = await client.post(f"{REGISTER}/{reg_id}/revoke-qr", json={"reason": "Lost phone"})
    assert r.status_code == 200, r.text
    assert r.json()["qr_status"] == "REVOKED"
    assert r.json()["credentials"][0]["status"] == "REVOKED"
    assert await run_email_events() == [None]
    assert mailbox.outbox == []
    assert await scalar("SELECT status FROM email_jobs") == "CANCELLED"

    again = await client.post(f"{REGISTER}/{reg_id}/revoke-qr", json={"reason": "Twice"})
    assert again.status_code == 409
    resend = await client.post(
        f"{REGISTER}/{reg_id}/resend-qr", headers={"Idempotency-Key": uuid.uuid4().hex}
    )
    assert resend.json()["error"]["code"] == "QR_NOT_ACTIVE"


async def test_revoke_with_reissue_sends_new_code(mailbox: MemorySender) -> None:
    _, client, lead_id = await admin_setup()
    reg_id = (await register(client, lead_id)).json()["id"]
    await run_email_events()
    r = await client.post(
        f"{REGISTER}/{reg_id}/revoke-qr", json={"reason": "Shared on social media", "reissue": True}
    )
    assert r.status_code == 200
    statuses = sorted(c["status"] for c in r.json()["credentials"])
    assert statuses == ["ACTIVE", "REVOKED"]
    assert r.json()["qr_status"] == "ACTIVE"
    await run_email_events()
    assert len(mailbox.outbox) == 2
    assert mailbox.outbox[0].attachments[0].content != mailbox.outbox[1].attachments[0].content


# --- delivery failures --------------------------------------------------------------------------


class FlakySender:
    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.sent: list[OutgoingEmail] = []

    def send(self, email: OutgoingEmail, account: SmtpAccount | None = None) -> str:
        if self.failures:
            self.failures -= 1
            raise TransientEmailError("SMTPServerDisconnected")
        self.sent.append(email)
        return "<flaky@ems.test>"


async def test_transient_failure_retries_without_duplicate_registration() -> None:
    sender = FlakySender(failures=1)
    set_email_sender(sender)
    _, client, lead_id = await admin_setup()
    await register(client, lead_id)
    async with get_sessionmaker()() as session:
        event_id = await session.scalar(select(OutboxEvent.id))
    assert event_id is not None
    with pytest.raises(TransientEmailError):
        await send_qr_email_event(event_id)
    async with get_sessionmaker()() as session:
        job = await session.scalar(select(EmailJob))
    assert job is not None and job.status == "QUEUED" and job.attempts == 1
    assert await send_qr_email_event(event_id) == "SENT"
    assert await send_qr_email_event(event_id) is None  # finished jobs are never resent
    assert len(sender.sent) == 1
    assert await scalar("SELECT count(*) FROM visitor_registrations") == 1


async def test_final_attempt_marks_failed() -> None:
    set_email_sender(FlakySender(failures=10))
    _, client, lead_id = await admin_setup()
    await register(client, lead_id)
    async with get_sessionmaker()() as session:
        event_id = await session.scalar(select(OutboxEvent.id))
    assert event_id is not None
    assert await send_qr_email_event(event_id, final_attempt=True) == "FAILED"
    r = await client.get(REGISTER, params={"edition_id": str(await _edition_id())})
    assert r.json()["items"][0]["email_status"] == "FAILED"


async def _edition_id() -> uuid.UUID:
    async with get_sessionmaker()() as session:
        reg = await session.scalar(select(VisitorRegistration))
    assert reg is not None
    return reg.edition_id


# --- audit -------------------------------------------------------------------------------------


async def test_audit_never_contains_qr_token() -> None:
    _, client, lead_id = await admin_setup()
    reg_id = (await register(client, lead_id)).json()["id"]
    await client.post(f"{REGISTER}/{reg_id}/revoke-qr", json={"reason": "Test", "reissue": True})
    async with get_sessionmaker()() as session:
        creds = list(await session.scalars(select(QrCredential)))
        dump = await session.scalar(
            text("SELECT string_agg(before::text || after::text, '') FROM audit_logs")
        )
    assert creds
    for cred in creds:
        assert decrypt(cred.token_enc) not in dump
        assert cred.token_hash not in dump
        assert cred.token_enc not in dump


# --- templates ---------------------------------------------------------------------------------


async def test_edition_template_version_is_used(mailbox: MemorySender) -> None:
    edition, client, lead_id = await admin_setup()
    bad = await client.post(
        "/api/v1/email-templates",
        json={
            "edition_id": str(edition.id),
            "subject": "Hi {{ unknown_var }}",
            "body_text": "x",
            "body_html": "<p>{% if %}</p>",
        },
    )
    assert bad.status_code == 422
    assert set(bad.json()["error"]["fields"]) == {"subject", "body_html"}

    good = await client.post(
        "/api/v1/email-templates",
        json={
            "edition_id": str(edition.id),
            "subject": "Welcome {{ first_name }} to {{ edition_code }}",
            "body_text": "Code {{ registration_code }}",
            "body_html": '<p><img src="cid:{{ qr_cid }}"></p>',
        },
    )
    assert good.status_code == 201, good.text
    assert good.json()["version"] == 1
    await register(client, lead_id)
    await run_email_events()
    assert mailbox.outbox[0].subject == f"Welcome Visitor to {edition.code}"

    system = await client.post(
        "/api/v1/email-templates",
        json={"subject": "x", "body_text": "x", "body_html": '<img src="cid:{{ qr_cid }}">'},
    )
    assert system.status_code == 403


async def test_template_html_is_escaped(mailbox: MemorySender) -> None:
    edition = await make_edition()
    _, client = await actor(RoleGrant("EXHIBITION_ADMIN", "EDITION", edition.id))
    async with get_sessionmaker()() as session, session.begin():
        lead = VisitorLead(
            edition_id=edition.id,
            registration_code=f"{edition.registration_id_prefix}000777",
            first_name="<script>alert(1)</script>",
            email="visitor-003@example.test",
            email_normalized="visitor-003@example.test",
            source="MANUAL",
            custom_fields={},
        )
        session.add(lead)
    await register(client, str(lead.id))
    await run_email_events()
    assert "<script>" not in mailbox.outbox[0].html
    assert "&lt;script&gt;" in mailbox.outbox[0].html
