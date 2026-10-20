import pytest

from app.modules.visitors.rules import (
    CustomFieldDef,
    CustomFieldType,
    NormalizationError,
    normalize_email,
    normalize_phone,
    validate_custom_fields,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Quinn@Example.TEST ", "quinn@example.test"),
        ("", None),
        ("   ", None),
        (None, None),
    ],
)
def test_normalize_email(raw: str | None, expected: str | None) -> None:
    assert normalize_email(raw) == expected


def test_normalize_email_rejects_garbage() -> None:
    with pytest.raises(NormalizationError):
        normalize_email("not-an-email")


@pytest.mark.parametrize(
    ("raw", "country", "expected"),
    [
        ("0812-3456-7890", "ID", "+6281234567890"),
        ("+62 812 3456 7890", None, "+6281234567890"),
        ("0912 345 678", "VN", "+84912345678"),
        ("84971764", None, "84971764"),
        ("  ", "ID", None),
        (None, None, None),
    ],
)
def test_normalize_phone(raw: str | None, country: str | None, expected: str | None) -> None:
    assert normalize_phone(raw, country) == expected


def test_normalize_phone_rejects_garbage() -> None:
    with pytest.raises(NormalizationError):
        normalize_phone("12", "ID")


DEFS = [
    CustomFieldDef("budget", "Budget", CustomFieldType.NUMBER, False, (), {"min": 0}),
    CustomFieldDef("size", "Size", CustomFieldType.SELECT, True, ("S", "M", "L"), {}),
    CustomFieldDef("tags", "Tags", CustomFieldType.MULTI_SELECT, False, ("a", "b"), {}),
    CustomFieldDef("visit", "Visit", CustomFieldType.DATE, False, (), {}),
    CustomFieldDef("vip", "VIP", CustomFieldType.CHECKBOX, False, (), {}),
    CustomFieldDef("note", "Note", CustomFieldType.TEXT, False, (), {"max_length": 5}),
]


def test_custom_fields_valid() -> None:
    clean, errors = validate_custom_fields(
        DEFS,
        {"budget": "12", "size": "M", "tags": ["b", "a", "b"], "visit": "2027-03-10",
         "vip": "yes", "note": " hi "},
    )  # fmt: skip
    assert errors == {}
    assert clean == {
        "budget": 12, "size": "M", "tags": ["a", "b"], "visit": "2027-03-10",
        "vip": True, "note": "hi",
    }  # fmt: skip


def test_custom_fields_errors() -> None:
    _, errors = validate_custom_fields(
        DEFS, {"budget": -1, "tags": ["z"], "visit": "soon", "note": "too long", "nope": 1}
    )
    assert set(errors) == {"budget", "tags", "visit", "note", "nope", "size"}
    assert errors["nope"] == "Unknown custom field."
    assert errors["size"] == "Required."
