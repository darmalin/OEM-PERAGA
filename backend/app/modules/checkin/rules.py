"""Pure gate rules (spec 8): entry types, local event dates, device codes."""

import secrets
from datetime import date, datetime, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from app.core.crypto import new_token, sha256_hex


class DeviceStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


class ScanMode(StrEnum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    OVERRIDE = "OVERRIDE"


class ScanOutcome(StrEnum):
    """Stored on the attempt. FIRST/REPEAT is derived from visitor_checkins, since a later
    offline sync with an earlier scan time can move the first entry (spec 8.3)."""

    ACCEPTED = "ACCEPTED"
    REJECTED_UNKNOWN = "REJECTED_UNKNOWN"
    REJECTED_REVOKED = "REJECTED_REVOKED"
    REJECTED_WRONG_EDITION = "REJECTED_WRONG_EDITION"
    REJECTED_CANCELLED = "REJECTED_CANCELLED"


class ScanResult(StrEnum):
    FIRST_ENTRY = "FIRST_ENTRY"
    REPEAT_ENTRY = "REPEAT_ENTRY"
    REJECTED_UNKNOWN = "REJECTED_UNKNOWN"
    REJECTED_REVOKED = "REJECTED_REVOKED"
    REJECTED_WRONG_EDITION = "REJECTED_WRONG_EDITION"
    REJECTED_CANCELLED = "REJECTED_CANCELLED"


# Offline results the device may report; the server's answer is final.
ProvisionalResult = ScanResult

# A device clock ahead by more than this is not trusted; the receive time is used instead.
MAX_CLOCK_SKEW = timedelta(minutes=5)

# No 0/O, 1/I/L: the code is read off a screen and typed on a phone.
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 10


def result_for(outcome: ScanOutcome, is_first: bool) -> ScanResult:
    if outcome != ScanOutcome.ACCEPTED:
        return ScanResult(outcome.value)
    return ScanResult.FIRST_ENTRY if is_first else ScanResult.REPEAT_ENTRY


def local_date(moment: datetime, timezone: str) -> date:
    """Event-local date: first entry resets each local day (spec 8.2)."""
    return moment.astimezone(ZoneInfo(timezone)).date()


def trusted_scan_time(scanned_at: datetime, received_at: datetime) -> datetime:
    return received_at if scanned_at > received_at + MAX_CLOCK_SKEW else scanned_at


def new_activation_code() -> tuple[str, str]:
    """(code shown once as XXXXX-XXXXX, hash stored)."""
    raw = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(CODE_LENGTH))
    return f"{raw[:5]}-{raw[5:]}", sha256_hex(raw)


def activation_code_hash(code: str) -> str:
    return sha256_hex("".join(c for c in code.upper() if c.isalnum()))


def new_device_secret() -> tuple[str, str]:
    secret = new_token(32)
    return secret, sha256_hex(secret)
