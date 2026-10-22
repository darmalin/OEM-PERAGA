"""Pure edition rules: status lifecycle and reference validation."""

import re
from collections.abc import Mapping
from enum import StrEnum
from functools import lru_cache
from typing import Any
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


# Exhibitor dates (owner request 2026-10-22, from the old system's Exhibition form). Stored and
# shown only; the Exhibitor Portal phase (FEATURES/11) will give them meaning and fuller rules.
PRICE_PERIODS = (
    ("price_regular_from", "price_regular_to"),
    ("price_surcharge_from", "price_surcharge_to"),
    ("price_onsite_from", "price_onsite_to"),
)
EXHIBITOR_DATE_FIELDS = (
    *(f for pair in PRICE_PERIODS for f in pair),
    "order_expired_on",
    "catalog_expired_on",
)


def period_errors(values: Mapping[str, Any]) -> dict[str, str]:
    """Only checked now: a price period does not end before it starts."""
    errors: dict[str, str] = {}
    for start, end in PRICE_PERIODS:
        a, b = values.get(start), values.get(end)
        if a is not None and b is not None and b < a:
            errors[end] = "Must not be before the start of the period."
    return errors


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
