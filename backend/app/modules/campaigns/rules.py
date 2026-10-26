"""Pure campaign-link rules: link tokens, open/closed state, form tickets, IP hashing."""

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta
from enum import StrEnum

# 12 URL-safe characters (72 random bits): links cannot be guessed or enumerated.
TOKEN_BYTES = 9
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{12}$")
GTM_RE = re.compile(r"^GTM-[A-Z0-9]{4,12}$")

# A person needs a few seconds to fill the form; a bot posts at once. Old tickets expire.
MIN_FILL = timedelta(seconds=3)
MAX_FORM_AGE = timedelta(hours=2)

# Bump when the consent text on the form changes; stored with every submission.
CONSENT_VERSION = "2026-10-26"


class LinkState(StrEnum):
    OPEN = "OPEN"
    INACTIVE = "INACTIVE"
    NOT_STARTED = "NOT_STARTED"
    ENDED = "ENDED"
    FULL = "FULL"
    EDITION_CLOSED = "EDITION_CLOSED"


class SubmissionOutcome(StrEnum):
    CREATED = "CREATED"
    DUPLICATE = "DUPLICATE"  # same email/phone in the edition; answered like CREATED
    BOT = "BOT"  # honeypot filled, too fast, or a bad ticket; answered like CREATED


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def link_state(
    *,
    is_active: bool,
    starts_at: datetime | None,
    ends_at: datetime | None,
    max_submissions: int | None,
    submission_count: int,
    edition_active: bool,
    now: datetime,
) -> LinkState:
    if not edition_active:
        return LinkState.EDITION_CLOSED
    if not is_active:
        return LinkState.INACTIVE
    if starts_at is not None and now < starts_at:
        return LinkState.NOT_STARTED
    if ends_at is not None and now >= ends_at:
        return LinkState.ENDED
    if max_submissions is not None and submission_count >= max_submissions:
        return LinkState.FULL
    return LinkState.OPEN


def _sign(key: bytes, message: str) -> str:
    return hmac.new(key, message.encode(), hashlib.sha256).hexdigest()[:32]


def form_ticket(key: bytes, token: str, issued_at: datetime) -> str:
    """Issued with the form; proves the form was loaded, and when."""
    ts = str(int(issued_at.timestamp()))
    return f"{ts}.{_sign(key, f'{token}.{ts}')}"


def ticket_ok(key: bytes, token: str, ticket: str | None, now: datetime) -> bool:
    """False for a missing, forged, too quick, or too old ticket."""
    if not ticket or "." not in ticket:
        return False
    ts, sig = ticket.split(".", 1)
    if not ts.isdigit() or not hmac.compare_digest(sig, _sign(key, f"{token}.{ts}")):
        return False
    age = now - datetime.fromtimestamp(int(ts), tz=now.tzinfo)
    return MIN_FILL <= age <= MAX_FORM_AGE


def ip_hash(key: bytes, ip: str) -> str:
    """Keyed hash: the same visitor IP links submissions, the IP itself is never stored."""
    return _sign(key, f"ip:{ip}")
