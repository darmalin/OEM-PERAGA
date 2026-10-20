"""Pure edition rules: status lifecycle and reference validation."""

import re
from enum import StrEnum
from functools import lru_cache
from zoneinfo import available_timezones

import phonenumbers


class EditionStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


# Lifecycle to confirm with business (FEATURES/02). CLOSED can reopen for late corrections.
_TRANSITIONS: dict[EditionStatus, set[EditionStatus]] = {
    EditionStatus.DRAFT: {EditionStatus.ACTIVE, EditionStatus.ARCHIVED},
    EditionStatus.ACTIVE: {EditionStatus.CLOSED},
    EditionStatus.CLOSED: {EditionStatus.ACTIVE, EditionStatus.ARCHIVED},
    EditionStatus.ARCHIVED: set(),
}

CODE_RE = re.compile(r"^[A-Z0-9]{2,20}$")
CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


def can_transition(current: EditionStatus, target: EditionStatus) -> bool:
    return current == target or target in _TRANSITIONS[current]


@lru_cache
def _timezones() -> frozenset[str]:
    return frozenset(available_timezones())


def is_valid_timezone(name: str) -> bool:
    return name in _timezones()


def is_valid_country(code: str) -> bool:
    """ISO 3166-1 alpha-2 (D8 default), using the region list shipped with phonenumbers."""
    return code in phonenumbers.SUPPORTED_REGIONS


def default_edition_code(exhibition_code: str, year: int) -> str:
    return f"{exhibition_code}{year}"
