from datetime import date
from decimal import Decimal

import pytest

from app.modules.orders.rules import (
    FORM_CODE_PATTERN,
    DateRange,
    FormProgress,
    OrderStatus,
    PricePeriod,
    PricePeriods,
    all_priced,
    approval_needs_signed_contract,
    can_move,
    can_waive,
    form_progress,
    line_amount,
    order_total,
    price_period,
    unit_price,
)

DRAFT, SUBMITTED, RETURNED, APPROVED, CANCELLED = (
    OrderStatus.DRAFT,
    OrderStatus.SUBMITTED,
    OrderStatus.RETURNED,
    OrderStatus.APPROVED,
    OrderStatus.CANCELLED,
)


@pytest.mark.parametrize(
    ("current", "target", "allowed"),
    [
        (DRAFT, SUBMITTED, True),
        (DRAFT, APPROVED, False),
        (DRAFT, CANCELLED, False),
        (SUBMITTED, APPROVED, True),
        (SUBMITTED, RETURNED, True),
        (SUBMITTED, CANCELLED, True),
        (SUBMITTED, DRAFT, False),
        (RETURNED, SUBMITTED, True),
        (RETURNED, CANCELLED, True),
        (RETURNED, APPROVED, False),
        (APPROVED, CANCELLED, True),
        (APPROVED, RETURNED, False),
        (APPROVED, SUBMITTED, False),
        (CANCELLED, SUBMITTED, False),
        (CANCELLED, APPROVED, False),
    ],
)
def test_order_transitions(current: OrderStatus, target: OrderStatus, allowed: bool) -> None:
    assert can_move(current, target) is allowed


# Back to back, like the old data: regular, then surcharge, then onsite during the show.
PERIODS = PricePeriods(
    regular=DateRange(date(2027, 1, 1), date(2027, 2, 28)),
    surcharge=DateRange(date(2027, 2, 28), date(2027, 4, 13)),
    onsite=DateRange(date(2027, 4, 14), date(2027, 4, 17)),
)


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2027, 1, 1), PricePeriod.REGULAR),
        (date(2027, 2, 27), PricePeriod.REGULAR),
        (date(2027, 2, 28), PricePeriod.REGULAR),  # shared day: the earlier period
        (date(2027, 3, 1), PricePeriod.SURCHARGE),
        (date(2027, 4, 13), PricePeriod.SURCHARGE),
        (date(2027, 4, 14), PricePeriod.ONSITE),
        (date(2027, 4, 17), PricePeriod.ONSITE),
        (date(2026, 12, 31), None),  # before ordering opens
        (date(2027, 4, 18), None),  # after the show
    ],
)
def test_price_period(day: date, expected: PricePeriod | None) -> None:
    assert price_period(day, PERIODS) is expected


def test_price_period_without_periods_is_closed() -> None:
    assert price_period(date(2027, 1, 1), PricePeriods()) is None


def test_price_period_with_regular_only() -> None:
    periods = PricePeriods(regular=DateRange(date(2027, 1, 1), date(2027, 1, 31)))
    assert price_period(date(2027, 1, 15), periods) is PricePeriod.REGULAR
    assert price_period(date(2027, 2, 1), periods) is None


@pytest.mark.parametrize(
    ("period", "surcharge", "onsite", "expected"),
    [
        (PricePeriod.REGULAR, Decimal("120"), Decimal("150"), Decimal("100")),
        (PricePeriod.SURCHARGE, Decimal("120"), Decimal("150"), Decimal("120")),
        (PricePeriod.ONSITE, Decimal("120"), Decimal("150"), Decimal("150")),
        (PricePeriod.SURCHARGE, None, Decimal("150"), Decimal("100")),
        (PricePeriod.ONSITE, Decimal("120"), None, Decimal("100")),
    ],
)
def test_unit_price_falls_back_to_regular(
    period: PricePeriod, surcharge: Decimal | None, onsite: Decimal | None, expected: Decimal
) -> None:
    assert unit_price(period, Decimal("100"), surcharge, onsite) == expected


def test_line_amount_charges_only_above_the_free_quantity() -> None:
    assert line_amount(5, 0, Decimal("740600.00")) == Decimal("3703000.00")
    assert line_amount(5, 4, Decimal("50000")) == Decimal("50000")
    assert line_amount(4, 4, Decimal("50000")) == Decimal("0")


def test_line_amount_of_an_unpriced_extra_item() -> None:
    assert line_amount(2, 0, None) is None


@pytest.mark.parametrize(("quantity", "free"), [(0, 0), (-1, 0), (2, 3), (2, -1)])
def test_line_amount_rejects_bad_quantities(quantity: int, free: int) -> None:
    with pytest.raises(ValueError):
        line_amount(quantity, free, Decimal("1"))


def test_order_total_and_all_priced() -> None:
    amounts = [Decimal("100.50"), None, Decimal("0"), Decimal("20")]
    assert order_total(amounts) == Decimal("120.50")
    assert not all_priced(amounts)
    assert all_priced([Decimal("1"), Decimal("0")])
    assert order_total([]) == Decimal(0)
    assert all_priced([])


def test_approval_needs_signed_contract_only_for_paid_orders() -> None:
    assert approval_needs_signed_contract(Decimal("0.01"))
    assert not approval_needs_signed_contract(Decimal("0"))


@pytest.mark.parametrize(
    ("statuses", "waived", "expected"),
    [
        ([], False, FormProgress.NOT_STARTED),
        ([], True, FormProgress.NOT_REQUIRED),
        ([DRAFT], False, FormProgress.IN_PROGRESS),
        ([RETURNED], False, FormProgress.IN_PROGRESS),
        ([SUBMITTED], False, FormProgress.SUBMITTED),
        ([APPROVED], False, FormProgress.APPROVED),
        ([CANCELLED], False, FormProgress.NOT_STARTED),
        ([CANCELLED], True, FormProgress.NOT_REQUIRED),
        ([APPROVED, DRAFT], False, FormProgress.IN_PROGRESS),  # extra order being written
        ([APPROVED, SUBMITTED], False, FormProgress.SUBMITTED),  # extra order waits for staff
        ([SUBMITTED, RETURNED], False, FormProgress.SUBMITTED),
    ],
)
def test_form_progress(statuses: list[OrderStatus], waived: bool, expected: FormProgress) -> None:
    assert form_progress(statuses, waived) is expected


@pytest.mark.parametrize(
    ("statuses", "allowed"),
    [
        ([], True),
        ([DRAFT], True),
        ([RETURNED], True),
        ([CANCELLED], True),
        ([SUBMITTED], False),
        ([APPROVED, CANCELLED], False),
    ],
)
def test_can_waive(statuses: list[OrderStatus], allowed: bool) -> None:
    assert can_waive(statuses) is allowed


@pytest.mark.parametrize(
    ("code", "valid"),
    [("01", True), ("02a", True), ("12", True), ("1", False), ("02A", False), ("123", False)],
)
def test_form_code_pattern(code: str, valid: bool) -> None:
    assert bool(FORM_CODE_PATTERN.fullmatch(code)) is valid
