from decimal import Decimal

import pytest

from app.modules.exhibitors.rules import (
    PaymentState,
    SalesStage,
    can_move,
    payment_state,
)

LEAD, OPP, EXH, LOST = (
    SalesStage.LEAD,
    SalesStage.OPPORTUNITY,
    SalesStage.EXHIBITOR,
    SalesStage.LOST,
)


@pytest.mark.parametrize(
    ("current", "target", "allowed"),
    [
        (LEAD, OPP, True),
        (LEAD, LOST, True),
        (LEAD, EXH, False),
        (OPP, LEAD, True),
        (OPP, EXH, True),
        (OPP, LOST, True),
        (EXH, LEAD, False),
        (EXH, OPP, False),
        (EXH, LOST, False),
        (LOST, LEAD, True),
        (LOST, OPP, False),
        (LOST, EXH, False),
    ],
)
def test_stage_transitions(current: SalesStage, target: SalesStage, allowed: bool) -> None:
    assert can_move(current, target) is allowed


@pytest.mark.parametrize(
    ("total", "verified", "state"),
    [
        ("10000000", "0", PaymentState.UNPAID),
        ("10000000", "3000000", PaymentState.PARTIAL),
        ("10000000", "10000000", PaymentState.PAID),
        ("10000000", "12000000", PaymentState.PAID),
        ("0", "0", PaymentState.PAID),  # fully discounted booth
    ],
)
def test_payment_state(total: str, verified: str, state: PaymentState) -> None:
    assert payment_state(Decimal(total), Decimal(verified)) is state
