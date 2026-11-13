"""Quotation rules: stand types, statuses, numbering, and the price calculation of the sales team's
Excel quotation (docs/EXHIBITOR_QUOTATIONS.md "Calculation")."""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum


class StandType(StrEnum):
    RAW = "RAW"  # raw space: floor only
    SHELL = "SHELL"  # shell scheme: partition, chair, fascia name, desk, power


class QuotationStatus(StrEnum):
    ISSUED = "ISSUED"
    SUPERSEDED = "SUPERSEDED"  # replaced by a revision
    ACCEPTED = "ACCEPTED"
    CANCELLED = "CANCELLED"


STAND_LABELS = {StandType.RAW: "RAW SPACE", StandType.SHELL: "SHELL SCHEME"}
DEFAULT_SHELL_INCLUDES = (
    "Partition, folding chair, company name, reception desk, 2 amp / 220 V, single phase."
)
DEFAULT_TERMS: list[dict[str, object]] = [
    {"label": "Booking Fee", "percent": Decimal(30), "due_on": None},
    {"label": "First Payment", "percent": Decimal(50), "due_on": None},
    {"label": "Last Payment", "percent": Decimal(20), "due_on": None},
]
CENT = Decimal("0.01")
HUNDRED = Decimal(100)
ROMAN_MONTHS = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def quotation_number(seq: int, company_code: str, code: str, issued_on: date) -> str:
    """`112/PNJS/IIT/VII/2026`: running number / company / code / month in Roman / year."""
    return f"{seq}/{company_code}/{code}/{ROMAN_MONTHS[issued_on.month - 1]}/{issued_on.year}"


@dataclass(frozen=True)
class Term:
    label: str
    percent: Decimal
    due_on: date | None


@dataclass(frozen=True)
class Amounts:
    area_sqm: Decimal
    charged_sqm: Decimal
    gross_amount: Decimal  # charged sqm x stand rate
    discount_amount: Decimal  # charged sqm x raw rate x discount %
    cost_amount: Decimal  # gross - discount, the tax base before the 11/12 factor
    vat_amount: Decimal
    total_amount: Decimal
    term_amounts: tuple[Decimal, ...]


def compute(
    *,
    width_m: Decimal | None,
    length_m: Decimal | None,
    area_sqm: Decimal | None,
    complimentary_sqm: Decimal,
    stand_rate: Decimal,
    raw_rate: Decimal,
    discount_percent: Decimal,
    vat_rate: Decimal,
    vat_base_num: int,
    vat_base_den: int,
    terms: list[Term],
) -> Amounts:
    """The Excel sheet's arithmetic. The area is width x length unless given; the discount is a
    share of the raw space cost even for shell scheme; VAT is vat_rate % of cost x num/den (12% of
    11/12 for IDR); each term is a share of the total, the last one taking the rounding remainder.
    """
    area = money(
        area_sqm if area_sqm is not None else (width_m or Decimal(0)) * (length_m or Decimal(0))
    )
    charged = money(area - complimentary_sqm)
    gross = money(charged * stand_rate)
    discount = money(charged * raw_rate * discount_percent / HUNDRED)
    cost = gross - discount
    vat = money(cost * Decimal(vat_base_num) / Decimal(vat_base_den) * vat_rate / HUNDRED)
    total = cost + vat
    shares = [money(total * t.percent / HUNDRED) for t in terms[:-1]]
    shares.append(total - sum(shares, Decimal(0)))
    return Amounts(
        area_sqm=area,
        charged_sqm=charged,
        gross_amount=gross,
        discount_amount=discount,
        cost_amount=cost,
        vat_amount=vat,
        total_amount=total,
        term_amounts=tuple(shares),
    )
