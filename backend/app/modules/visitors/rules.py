"""Pure visitor rules: normalization (spec 5.2), custom field validation (spec 4.5)."""

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

import phonenumbers
from email_validator import EmailNotValidError, validate_email


class LeadSource(StrEnum):
    EXCEL = "EXCEL"
    API = "API"
    MANUAL = "MANUAL"
    WEBSITE = "WEBSITE"
    TELEMARKETING = "TELEMARKETING"


class Gender(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


class TelemarketingStatus(StrEnum):
    NEW = "NEW"
    ANSWER = "ANSWER"
    NO_ANSWER = "NO_ANSWER"
    RECONTACTED = "RECONTACTED"
    RETRY_NO_ANSWER = "RETRY_NO_ANSWER"


class RegistrationStatus(StrEnum):
    NOT_REGISTERED = "NOT_REGISTERED"
    REGISTERED = "REGISTERED"
    CANCELLED = "CANCELLED"


class QrStatus(StrEnum):
    NONE = "NONE"
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


class Attend(StrEnum):
    """spec 4.2: fixed options. Labels: Attend, Attend Sourcing, Under Consideration,
    Not Attend, Hang Up Immediately."""

    ATTEND = "ATTEND"
    ATTEND_SOURCING = "ATTEND_SOURCING"
    UNDER_CONSIDERATION = "UNDER_CONSIDERATION"
    NOT_ATTEND = "NOT_ATTEND"
    HANG_UP_IMMEDIATELY = "HANG_UP_IMMEDIATELY"


class BuyerType(StrEnum):
    """spec 4.3: B-Side / C-Side."""

    B_SIDE = "B_SIDE"
    C_SIDE = "C_SIDE"


class OptionField(StrEnum):
    """Configurable selects, defined per edition."""

    BUSINESS_TYPE = "BUSINESS_TYPE"
    BRANCH = "BRANCH"
    EXHIBITION_TYPE = "EXHIBITION_TYPE"
    PRODUCT_CATEGORY = "PRODUCT_CATEGORY"


class CustomFieldType(StrEnum):
    TEXT = "text"
    TEXTAREA = "textarea"
    NUMBER = "number"
    DATE = "date"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    CHECKBOX = "checkbox"


FIELD_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,49}$")


class NormalizationError(ValueError):
    pass


def clean_text(value: Any) -> str | None:
    """spec 5.2: empty values are stored as NULL, never as empty strings."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_email(value: Any) -> str | None:
    """Trim + lowercase; None when empty; NormalizationError when malformed."""
    text = clean_text(value)
    if text is None:
        return None
    try:
        validate_email(text, check_deliverability=False, test_environment=True)
    except EmailNotValidError as e:
        raise NormalizationError("Not a valid email address.") from e
    return text.lower()


def normalize_phone(value: Any, country: str | None) -> str | None:
    """E.164 when the number can be parsed (with the country as default region),
    otherwise digits with an optional leading + (D8 default)."""
    text = clean_text(value)
    if text is None:
        return None
    try:
        parsed = phonenumbers.parse(text, country.upper() if country else None)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        pass
    digits = re.sub(r"\D", "", text)
    if len(digits) < 6 or len(digits) > 15:
        raise NormalizationError("Not a valid phone number.")
    return f"+{digits}" if text.startswith("+") else digits


@dataclass(frozen=True)
class CustomFieldDef:
    field_key: str
    label: str
    field_type: CustomFieldType
    required: bool
    options: tuple[str, ...]
    validation: dict[str, Any]


def _check_one(d: CustomFieldDef, value: Any) -> Any:
    rules = d.validation
    match d.field_type:
        case CustomFieldType.TEXT | CustomFieldType.TEXTAREA:
            if not isinstance(value, str):
                raise NormalizationError("Must be text.")
            text = value.strip()
            max_len = int(
                rules.get("max_length", 2000 if d.field_type == CustomFieldType.TEXTAREA else 255)
            )
            if len(text) > max_len:
                raise NormalizationError(f"At most {max_len} characters.")
            return text or None
        case CustomFieldType.NUMBER:
            if isinstance(value, bool):
                raise NormalizationError("Must be a number.")
            try:
                num = Decimal(str(value).strip())
            except InvalidOperation as e:
                raise NormalizationError("Must be a number.") from e
            if "min" in rules and num < Decimal(str(rules["min"])):
                raise NormalizationError(f"Must be at least {rules['min']}.")
            if "max" in rules and num > Decimal(str(rules["max"])):
                raise NormalizationError(f"Must be at most {rules['max']}.")
            return int(num) if num == num.to_integral_value() else float(num)
        case CustomFieldType.DATE:
            try:
                return date.fromisoformat(str(value).strip()[:10]).isoformat()
            except ValueError as e:
                raise NormalizationError("Must be a date (YYYY-MM-DD).") from e
        case CustomFieldType.SELECT:
            if str(value) not in d.options:
                raise NormalizationError("Not one of the allowed options.")
            return str(value)
        case CustomFieldType.MULTI_SELECT:
            items = value if isinstance(value, list) else [value]
            bad = [str(v) for v in items if str(v) not in d.options]
            if bad:
                raise NormalizationError("Not one of the allowed options.")
            return sorted({str(v) for v in items}, key=d.options.index)
        case CustomFieldType.CHECKBOX:
            if isinstance(value, bool):
                return value
            if str(value).strip().lower() in ("true", "yes", "1", "y"):
                return True
            if str(value).strip().lower() in ("false", "no", "0", "n"):
                return False
            raise NormalizationError("Must be true or false.")


def validate_custom_fields(
    defs: list[CustomFieldDef], values: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, str]]:
    """Validate against active definitions. Returns (clean values, errors by field key).

    Unknown keys are rejected (spec 4.5). Empty values are dropped.
    """
    by_key = {d.field_key: d for d in defs}
    clean: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for key, value in values.items():
        d = by_key.get(key)
        if d is None:
            errors[key] = "Unknown custom field."
            continue
        if value is None or value == "" or value == []:
            continue
        try:
            checked = _check_one(d, value)
        except NormalizationError as e:
            errors[key] = str(e)
            continue
        if checked is not None and checked != []:
            clean[key] = checked
    for d in defs:
        if d.required and d.field_key not in clean and d.field_key not in errors:
            errors[d.field_key] = "Required."
    return clean, errors
