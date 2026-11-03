"""Database constraints of the exhibitor sales tables (migration 0025)."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.db import get_sessionmaker, new_id
from app.modules.exhibitors.models import (
    Booth,
    ExhibitorAccount,
    ExhibitorContract,
    ExhibitorLead,
    ExhibitorPayment,
)
from tests.factories import make_edition


async def _add(*rows: Any) -> None:
    async with get_sessionmaker()() as session, session.begin():
        for row in rows:
            session.add(row)
            await session.flush()


def _booth(edition_id: uuid.UUID, code: str = "A01") -> Booth:
    return Booth(
        id=new_id(),
        edition_id=edition_id,
        code=code,
        area_sqm=Decimal("9.00"),
        price=Decimal("15000000.00"),
        currency="IDR",
    )


def _lead(edition_id: uuid.UUID, email: str = "sales-001@example.test", **kw: Any) -> ExhibitorLead:
    return ExhibitorLead(
        id=new_id(),
        edition_id=edition_id,
        company_name="Example Corp",
        contact_name="Test Contact",
        email=email,
        email_normalized=email.lower(),
        **kw,
    )


def _account() -> ExhibitorAccount:
    return ExhibitorAccount(
        id=new_id(), email="portal@example.test", email_normalized="portal@example.test"
    )


async def _exhibitor(edition_id: uuid.UUID) -> tuple[ExhibitorLead, ExhibitorContract]:
    booth, account = _booth(edition_id), _account()
    await _add(booth, account)
    lead = _lead(edition_id, stage="EXHIBITOR", booth_id=booth.id, exhibitor_account_id=account.id)
    contract = ExhibitorContract(
        edition_id=edition_id,
        exhibitor_lead_id=lead.id,
        booth_price=booth.price,
        currency="IDR",
    )
    await _add(lead, contract)
    return lead, contract


async def test_email_unique_per_edition_only() -> None:
    e1, e2 = await make_edition(), await make_edition()
    await _add(_lead(e1.id), _lead(e2.id))
    with pytest.raises(IntegrityError, match="uq_exhibitor_leads_edition_email"):
        await _add(_lead(e1.id))


async def test_booth_sold_once() -> None:
    edition = await make_edition()
    booth = _booth(edition.id)
    await _add(booth, _lead(edition.id, stage="OPPORTUNITY", booth_id=booth.id))
    with pytest.raises(IntegrityError, match="uq_exhibitor_leads_booth"):
        await _add(
            _lead(edition.id, "sales-002@example.test", stage="OPPORTUNITY", booth_id=booth.id)
        )


async def test_booth_from_another_edition_rejected() -> None:
    e1, e2 = await make_edition(), await make_edition()
    booth = _booth(e2.id)
    await _add(booth)
    with pytest.raises(IntegrityError, match="fk_exhibitor_leads_booth_id_booths"):
        await _add(_lead(e1.id, stage="OPPORTUNITY", booth_id=booth.id))


@pytest.mark.parametrize(
    ("stage", "with_booth", "with_account", "constraint"),
    [
        ("LEAD", True, False, "booth_only_when_selling"),
        ("LOST", True, False, "booth_only_when_selling"),
        ("EXHIBITOR", False, True, "exhibitor_has_booth"),
        ("EXHIBITOR", True, False, "exhibitor_has_account"),
        ("WON", False, False, "stage_valid"),
    ],
)
async def test_stage_and_booth_consistency(
    stage: str, with_booth: bool, with_account: bool, constraint: str
) -> None:
    edition = await make_edition()
    booth, account = _booth(edition.id), _account()
    await _add(booth, account)
    lead = _lead(
        edition.id,
        stage=stage,
        booth_id=booth.id if with_booth else None,
        exhibitor_account_id=account.id if with_account else None,
    )
    with pytest.raises(IntegrityError, match=constraint):
        await _add(lead)


async def test_signed_contract_needs_its_fields_and_pdf() -> None:
    edition = await make_edition()
    _lead_row, contract = await _exhibitor(edition.id)
    async with get_sessionmaker()() as session, session.begin():
        row = await session.get(ExhibitorContract, contract.id)
        assert row is not None
        row.status = "SIGNED"
        row.signed_at = datetime.now(UTC)
        with pytest.raises(IntegrityError, match="signed_complete"):
            await session.flush()


async def test_discount_cannot_exceed_price() -> None:
    edition = await make_edition()
    lead = _lead(edition.id)
    await _add(lead)
    contract = ExhibitorContract(
        edition_id=edition.id,
        exhibitor_lead_id=lead.id,
        booth_price=Decimal(100),
        discount_amount=Decimal(101),
        currency="IDR",
    )
    with pytest.raises(IntegrityError, match="discount_valid"):
        await _add(contract)


@pytest.mark.parametrize(
    ("kw", "constraint"),
    [
        ({"amount": Decimal(0)}, "amount_positive"),
        ({"method": "CARD"}, "method_valid"),
        ({"status": "VERIFIED"}, "reviewed_unless_pending"),
        ({"reviewed_at": datetime.now(UTC)}, "reviewed_unless_pending"),
    ],
)
async def test_payment_constraints(kw: dict[str, Any], constraint: str) -> None:
    edition = await make_edition()
    _lead_row, contract = await _exhibitor(edition.id)
    values: dict[str, Any] = {
        "amount": Decimal("5000000"),
        "method": "BANK_TRANSFER",
        "paid_on": date(2027, 1, 15),
    } | kw
    with pytest.raises(IntegrityError, match=constraint):
        await _add(ExhibitorPayment(edition_id=edition.id, contract_id=contract.id, **values))


async def test_installments_recorded_against_one_contract() -> None:
    edition = await make_edition()
    _lead_row, contract = await _exhibitor(edition.id)
    await _add(
        *(
            ExhibitorPayment(
                edition_id=edition.id,
                contract_id=contract.id,
                amount=Decimal("5000000"),
                method="BANK_TRANSFER",
                paid_on=date(2027, 1, day),
            )
            for day in (5, 20)
        )
    )
