"""Pure exhibitor sales rules (docs/EXHIBITOR_LEADS_SALES_PIPELINE.md)."""

from decimal import Decimal
from enum import StrEnum


class SalesStage(StrEnum):
    LEAD = "LEAD"
    OPPORTUNITY = "OPPORTUNITY"
    EXHIBITOR = "EXHIBITOR"  # converted: has a booth and a portal account
    LOST = "LOST"


class ContractStatus(StrEnum):
    DRAFT = "DRAFT"
    SIGNED = "SIGNED"


class PaymentStatus(StrEnum):
    """A recorded payment (one installment); no payment gateway, staff verify it by hand."""

    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class PaymentMethod(StrEnum):
    BANK_TRANSFER = "BANK_TRANSFER"
    CASH = "CASH"
    OTHER = "OTHER"


class PaymentState(StrEnum):
    """Derived per contract from its verified payments, never stored."""

    UNPAID = "UNPAID"
    PARTIAL = "PARTIAL"
    PAID = "PAID"


STAGE_TRANSITIONS: dict[SalesStage, frozenset[SalesStage]] = {
    SalesStage.LEAD: frozenset({SalesStage.OPPORTUNITY, SalesStage.LOST}),
    SalesStage.OPPORTUNITY: frozenset({SalesStage.LEAD, SalesStage.EXHIBITOR, SalesStage.LOST}),
    SalesStage.EXHIBITOR: frozenset(),
    SalesStage.LOST: frozenset({SalesStage.LEAD}),  # reopen
}

# A booth is held only while the lead is being sold to or has converted.
BOOTH_STAGES = frozenset({SalesStage.OPPORTUNITY, SalesStage.EXHIBITOR})


def can_move(current: SalesStage, target: SalesStage) -> bool:
    return target in STAGE_TRANSITIONS[current]


def payment_state(total_amount: Decimal, verified_sum: Decimal) -> PaymentState:
    if verified_sum >= total_amount:
        return PaymentState.PAID
    if verified_sum > 0:
        return PaymentState.PARTIAL
    return PaymentState.UNPAID
