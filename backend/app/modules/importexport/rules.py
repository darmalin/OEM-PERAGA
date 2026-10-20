"""Pure import rules: header matching and cell conversion."""

import re
from datetime import date, datetime
from enum import StrEnum
from typing import Any


class ImportStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"


class ImportType(StrEnum):
    """D2: whether an import also registers visitors (and sends QR). Default LEADS_ONLY."""

    LEADS_ONLY = "LEADS_ONLY"
    LEADS_AND_REGISTER = "LEADS_AND_REGISTER"


class ImportErrorReason(StrEnum):
    DUPLICATE_IN_FILE = "DUPLICATE_IN_FILE"
    DUPLICATE_EXISTING = "DUPLICATE_EXISTING"
    INVALID = "INVALID"


# Import target -> template header (labels from the screenshot).
CORE_COLUMNS: dict[str, str] = {
    "first_name": "First Name",
    "email": "Email",
    "phone": "Phone",
    "gender": "Gender",
    "company_name": "Company Name",
    "job_title": "Job Title",
    "country": "Country",
    "city": "City",
    "website": "Website",
    "business_type": "Business Type",
    "branch": "Branch",
    "exhibition_type": "Exhibition Type",
    "product_categories": "Product Categories Interested In",
    "comment": "Comment",
    "lead_date": "Date",
    "external_id": "External ID",
}
CUSTOM_PREFIX = "custom_fields."
_ALIASES = {"name": "first_name", "firstname": "first_name", "mobile": "phone",
            "phonenumber": "phone", "emailaddress": "email", "company": "company_name",
            "productcategories": "product_categories", "registrationdate": "lead_date"}  # fmt: skip


def header_key(text: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text or "").lower())


def suggest_mapping(headers: list[str], custom: dict[str, str]) -> dict[str, str]:
    """Map file headers to targets by key or label. custom: field_key -> label."""
    lookup: dict[str, str] = {}
    for target, label in CORE_COLUMNS.items():
        lookup[header_key(target)] = target
        lookup[header_key(label)] = target
    lookup.update(_ALIASES)
    for key, label in custom.items():
        lookup.setdefault(header_key(key), CUSTOM_PREFIX + key)
        lookup.setdefault(header_key(label), CUSTOM_PREFIX + key)
    mapping: dict[str, str] = {}
    used: set[str] = set()
    for h in headers:
        found = lookup.get(header_key(h))
        if found and found not in used:
            mapping[h] = found
            used.add(found)
    return mapping


def cell_to_text(value: Any) -> str | None:
    """Excel gives floats for numeric phones (8.4971764E7); keep them as digits."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def split_multi(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in re.split(r"[;,\n]", value) if part.strip()]
