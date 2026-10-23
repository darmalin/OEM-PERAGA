"""Pure rules for registration, QR credentials, and QR emails (spec 7)."""

import io
from enum import StrEnum

import segno

from app.core.crypto import new_token, sha256_hex


class RegistrationChannel(StrEnum):
    WEBSITE = "WEBSITE"
    ADMIN = "ADMIN"
    TELEMARKETING = "TELEMARKETING"
    API = "API"
    IMPORT = "IMPORT"


# Channels a logged-in user may pick; WEBSITE and IMPORT are set by their own flows.
STAFF_CHANNELS = (
    RegistrationChannel.ADMIN,
    RegistrationChannel.TELEMARKETING,
    RegistrationChannel.API,
)


class RegistrationState(StrEnum):
    REGISTERED = "REGISTERED"
    CANCELLED = "CANCELLED"


class CredentialStatus(StrEnum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


def new_qr_token() -> tuple[str, str]:
    """(token, sha256 hex). spec 7.2: random, hard to guess, no PII."""
    token = new_token(32)
    return token, sha256_hex(token)


def qr_png(token: str) -> bytes:
    """The QR encodes the token only, never the visitor's name, email, or phone."""
    buf = io.BytesIO()
    segno.make(token, error="m").save(buf, kind="png", scale=8, border=4)
    return buf.getvalue()
