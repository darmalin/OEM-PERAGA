"""Pure exhibitor sales rules (docs/EXHIBITOR_LEADS_SALES_PIPELINE.md)."""

from decimal import Decimal
from enum import StrEnum


class SalesStage(StrEnum):
    LEAD = "LEAD"
    OPPORTUNITY = "OPPORTUNITY"
    EXHIBITOR = "EXHIBITOR"  # converted: has a booth and a portal account
    LOST = "LOST"


class TaxIdType(StrEnum):
    """The company's NPWP, or the signer's KTP when the company has none (owner request
    2026-11-18). Both are 15 or 16 digits; KTP (NIK) is always 16."""

    NPWP = "NPWP"
    KTP = "KTP"


def tax_id_problem(kind: str, number: str) -> str | None:
    """Why the number cannot be this kind of ID, or None. Dots, dashes and spaces are allowed."""
    digits = "".join(c for c in number if c.isdigit())
    if any(not (c.isdigit() or c in ".- ") for c in number):
        return "Use digits only (dots and dashes are fine)."
    if kind == TaxIdType.KTP and len(digits) != 16:
        return "A KTP number (NIK) has 16 digits."
    if kind == TaxIdType.NPWP and len(digits) not in (15, 16):
        return "An NPWP has 15 or 16 digits."
    return None


class ContractStatus(StrEnum):
    DRAFT = "DRAFT"
    SIGNED = "SIGNED"


class PaymentStatus(StrEnum):
    """A recorded payment (one installment); no payment gateway, staff verify it by hand."""

    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


# Transfer slips and receipts per payment: a payment paid in parts can have one slip per transfer.
PROOF_MAX_FILES = 5


def proof_name(file_name: str) -> str:
    """The uploaded name, without any folder the browser sent, as staff see it in the list."""
    return file_name.replace("\\", "/").rsplit("/", 1)[-1].strip()[:200] or "proof"


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
