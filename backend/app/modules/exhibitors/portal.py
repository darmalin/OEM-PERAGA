"""Exhibitor portal auth: invitation links, login, sessions. Kept apart from staff auth:
own cookie, own Redis session namespace, own accounts table (BACKEND_RULES/security-permissions.md).
"""

import contextlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit, ratelimit, sessions
from app.core.config import get_settings
from app.core.context import Source, source_var
from app.core.crypto import sha256_hex
from app.core.db import get_session
from app.core.errors import NotAuthenticated, PermissionDenied, RateLimited, ValidationFailed
from app.core.logging import mask_email
from app.modules.exhibitions import service as exhibitions_service
from app.modules.exhibitors import repository as repo
from app.modules.exhibitors.models import ExhibitorAccount
from app.modules.exhibitors.schemas import PortalExhibitorOut, PortalMeOut
from app.modules.identity import service as identity_service
from app.modules.visitors.rules import NormalizationError, normalize_email

ENTITY = "exhibitor_account"
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
INVITE_LIMIT_PER_IP = 30


@dataclass(frozen=True)
class PortalContext:
    account_id: uuid.UUID
    email: str
    session: sessions.SessionData


async def portal_account(
    request: Request, session: AsyncSession = Depends(get_session)
) -> PortalContext:
    """Dependency for portal routes: a live portal session of an active account."""
    cookie = request.cookies.get(get_settings().portal_session_cookie_name)
    sess = await sessions.load(cookie, sessions.PORTAL) if cookie else None
    if sess is None:
        raise NotAuthenticated()
    if request.method in UNSAFE_METHODS and not sessions.csrf_matches(
        sess, request.headers.get("X-CSRF-Token")
    ):
        raise PermissionDenied("CSRF token missing or invalid.", code="CSRF_FAILED")
    account = await repo.get_account(session, sess.user_id)
    if account is None or not account.is_active or account.password_hash is None:
        await sessions.destroy(sess.session_id, sessions.PORTAL)
        raise NotAuthenticated()
    source_var.set(Source.PORTAL)
    return PortalContext(account.id, account.email, sess)


# Marks the dependency as a guard for the every-route-is-guarded test.
portal_account.__ems_require__ = ("exhibitor_portal",)  # type: ignore[attr-defined]


async def _invited_account(session: AsyncSession, token: str, client_ip: str) -> ExhibitorAccount:
    await ratelimit.hit(f"portal_invite:ip:{client_ip}", INVITE_LIMIT_PER_IP, 15 * 60)
    account = await repo.account_by_invite(session, sha256_hex(token), for_update=True)
    if (
        account is None
        or not account.is_active
        or account.password_hash is not None
        or account.invite_expires_at is None
        or account.invite_expires_at < datetime.now(UTC)
    ):
        raise ValidationFailed("Invitation link is invalid or expired.", code="INVITATION_INVALID")
    return account


async def invitation_email(session: AsyncSession, token: str, client_ip: str) -> str:
    """Email the invitation is for, shown on the set-password page."""
    return (await _invited_account(session, token, client_ip)).email


async def accept_invitation(
    session: AsyncSession, token: str, password: str, client_ip: str
) -> tuple[ExhibitorAccount, sessions.SessionData]:
    """Set the password, consume the link, and log in."""
    account = await _invited_account(session, token, client_ip)
    now = datetime.now(UTC)
    account.password_hash = identity_service.hash_password(password)
    account.activated_at = now
    account.last_login_at = now
    account.invite_token_hash = None
    account.invite_expires_at = None
    await session.flush()
    await audit.record(
        session,
        entity_type=ENTITY,
        entity_id=account.id,
        action="activate",
        after={"activated_at": now, "ip": client_ip},
        source=Source.PORTAL,
    )
    return account, await sessions.create(account.id, sessions.PORTAL)


async def login(
    session: AsyncSession, email: str, password: str, client_ip: str
) -> tuple[ExhibitorAccount, sessions.SessionData]:
    """Same limits and lockout as staff login, on separate counters."""
    s = get_settings()
    try:
        email_n = normalize_email(email) or ""
    except NormalizationError:
        email_n = email.strip().lower()
    account_key = f"portal_login:acct:{sha256_hex(email_n)}"
    await ratelimit.hit(
        f"portal_login:ip:{client_ip}", s.login_max_attempts_per_ip, s.login_window_seconds
    )
    if await ratelimit.count(account_key) >= s.login_max_failures_per_account:
        raise RateLimited("Account temporarily locked. Try again later.", code="ACCOUNT_LOCKED")

    account = await repo.account_by_email(session, email_n) if email_n else None
    valid = identity_service.verify_password(password, account.password_hash if account else None)
    if not (account and account.is_active and valid):
        with contextlib.suppress(RateLimited):
            await ratelimit.hit(
                account_key, s.login_max_failures_per_account, s.login_window_seconds
            )
        await audit.record_independent(
            entity_type=ENTITY,
            entity_id=account.id if account else None,
            action="login_failed",
            after={"email": mask_email(email_n), "ip": client_ip},
            source=Source.PORTAL,
        )
        raise NotAuthenticated("Invalid email or password.", code="INVALID_CREDENTIALS")

    await ratelimit.reset(account_key)
    account.last_login_at = datetime.now(UTC)
    await session.flush()
    await audit.record(
        session,
        entity_type=ENTITY,
        entity_id=account.id,
        action="login",
        after={"ip": client_ip},
        source=Source.PORTAL,
    )
    # A fresh session ID on every login prevents session fixation.
    return account, await sessions.create(account.id, sessions.PORTAL)


async def logout(ctx: PortalContext) -> None:
    await sessions.destroy(ctx.session.session_id, sessions.PORTAL)


async def me(session: AsyncSession, account_id: uuid.UUID, csrf_token: str) -> PortalMeOut:
    """The account and its own exhibitor records, nothing else of the edition."""
    account = await repo.get_account(session, account_id)
    assert account is not None  # noqa: S101 - checked by portal_account or just created
    exhibitors = []
    for lead, booth_code, contract in await repo.account_exhibitors(session, account_id):
        edition = await exhibitions_service.public_edition_info(session, lead.edition_id)
        exhibitors.append(
            PortalExhibitorOut(
                exhibitor_lead_id=lead.id,
                edition_id=lead.edition_id,
                edition_name=edition.name,
                edition_start_date=edition.start_date,
                edition_end_date=edition.end_date,
                company_name=lead.company_name,
                booth_code=booth_code,
                contract_number=contract.contract_number if contract else None,
                contract_status=contract.status if contract else None,
            )
        )
    return PortalMeOut(
        account_id=account.id, email=account.email, csrf_token=csrf_token, exhibitors=exhibitors
    )
