"""Pure exhibitor order form rules (docs/EXHIBITOR_ORDER_FORMS.md)."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

# "01", "02a": the numbering of the order forms in the old portal, kept for the exhibitors.
FORM_CODE_PATTERN = re.compile(r"^[0-9]{2}[a-z]?$")


class OrderStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    RETURNED = "RETURNED"  # sent back by staff with a reason; the exhibitor edits and resubmits
    APPROVED = "APPROVED"
    CANCELLED = "CANCELLED"


class PricePeriod(StrEnum):
    """Which catalog price applies; chosen from the submit date (edition `price_*` dates)."""

    REGULAR = "REGULAR"
    SURCHARGE = "SURCHARGE"
    ONSITE = "ONSITE"


class FormProgress(StrEnum):
    """Derived per exhibitor and form, never stored."""

    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    NOT_REQUIRED = "NOT_REQUIRED"


class AttachmentPurpose(StrEnum):
    LOGO = "LOGO"
    PRODUCT_IMAGE = "PRODUCT_IMAGE"
    FITTING_LOCATION = "FITTING_LOCATION"
    VISA_LIST = "VISA_LIST"
    OTHER = "OTHER"


class DetailsType(StrEnum):
    """Code-defined answer schema of a form (decision O10); the schemas come in Phase 5."""

    DIRECTORY_LISTING = "directory_listing"
    ADVERTISING = "advertising"
    SOCIAL_MEDIA = "social_media"
    STAND_SERVICE = "stand_service"
    EXHIBIT_DETAILS = "exhibit_details"
    FREIGHT = "freight"
    BADGES_VISA = "badges_visa"
    SEMINAR = "seminar"
    PARKING = "parking"


ORDER_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.DRAFT: frozenset({OrderStatus.SUBMITTED}),  # a draft can also be deleted
    OrderStatus.SUBMITTED: frozenset(
        {OrderStatus.APPROVED, OrderStatus.RETURNED, OrderStatus.CANCELLED}
    ),
    OrderStatus.RETURNED: frozenset({OrderStatus.SUBMITTED, OrderStatus.CANCELLED}),
    OrderStatus.APPROVED: frozenset({OrderStatus.CANCELLED}),
    OrderStatus.CANCELLED: frozenset(),
}

# The exhibitor can edit these; at most one per exhibitor and form (partial unique index).
OPEN_STATUSES = frozenset({OrderStatus.DRAFT, OrderStatus.RETURNED})
# A form with such an order cannot be marked "I don't require this form".
COMMITTED_STATUSES = frozenset({OrderStatus.SUBMITTED, OrderStatus.APPROVED})


def can_move(current: OrderStatus, target: OrderStatus) -> bool:
    return target in ORDER_TRANSITIONS[current]


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date

    def __contains__(self, day: object) -> bool:
        return isinstance(day, date) and self.start <= day <= self.end


@dataclass(frozen=True)
class PricePeriods:
    """The edition's price periods; any of them may be missing."""

    regular: DateRange | None = None
    surcharge: DateRange | None = None
    onsite: DateRange | None = None


def price_period(day: date, periods: PricePeriods) -> PricePeriod | None:
    """Period on `day` (in the edition's timezone), or None when ordering is not open.

    Checked in time order, so a day shared by two back-to-back periods gets the earlier one.
    """
    for period, window in (
        (PricePeriod.REGULAR, periods.regular),
        (PricePeriod.SURCHARGE, periods.surcharge),
        (PricePeriod.ONSITE, periods.onsite),
    ):
        if window is not None and day in window:
            return period
    return None


def unit_price(
    period: PricePeriod,
    regular: Decimal,
    surcharge: Decimal | None = None,
    onsite: Decimal | None = None,
) -> Decimal:
    """Catalog price for the period; a missing surcharge or onsite price means the regular one."""
    if period is PricePeriod.SURCHARGE and surcharge is not None:
        return surcharge
    if period is PricePeriod.ONSITE and onsite is not None:
        return onsite
    return regular


def line_amount(quantity: int, free_quantity: int, price: Decimal | None) -> Decimal | None:
    """Charged amount of a line; None while an extra item has no price from staff yet (O6)."""
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if not 0 <= free_quantity <= quantity:
        raise ValueError("free_quantity must be between 0 and quantity")
    if price is None:
        return None
    return (quantity - free_quantity) * price


def order_total(amounts: Iterable[Decimal | None]) -> Decimal:
    """Sum of the priced lines; unpriced extra items count once staff price them."""
    return sum((a for a in amounts if a is not None), Decimal(0))


def all_priced(amounts: Iterable[Decimal | None]) -> bool:
    """Approve needs a price on every line."""
    return all(a is not None for a in amounts)


def approval_needs_signed_contract(total: Decimal) -> bool:
    """Decision O2: orders that cost money are approved only once the booth contract is signed."""
    return total > 0


def form_progress(statuses: Iterable[OrderStatus], waived: bool) -> FormProgress:
    """One status per exhibitor and form for lists and counters.

    Waiting for staff wins, then work for the exhibitor, then done.
    """
    present = set(statuses)
    if OrderStatus.SUBMITTED in present:
        return FormProgress.SUBMITTED
    if present & OPEN_STATUSES:
        return FormProgress.IN_PROGRESS
    if OrderStatus.APPROVED in present:
        return FormProgress.APPROVED
    if waived:
        return FormProgress.NOT_REQUIRED
    return FormProgress.NOT_STARTED


def can_waive(statuses: Iterable[OrderStatus]) -> bool:
    return not set(statuses) & COMMITTED_STATUSES
