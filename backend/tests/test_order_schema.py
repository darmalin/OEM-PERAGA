"""Database constraints of the exhibitor order form tables (migration 0030)."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.core.db import get_sessionmaker, new_id
from app.modules.exhibitors.models import Booth, ExhibitorAccount, ExhibitorLead
from app.modules.orders.models import (
    ExhibitorFormWaiver,
    ExhibitorOrder,
    ExhibitorOrderFile,
    ExhibitorOrderLine,
    OrderForm,
    OrderFormItem,
)
from tests.factories import make_edition, make_user

NOW = datetime(2027, 1, 10, 9, 0, tzinfo=UTC)


async def _add(*rows: Any) -> None:
    async with get_sessionmaker()() as session, session.begin():
        for row in rows:
            session.add(row)
            await session.flush()


def _form(edition_id: uuid.UUID, code: str = "04", **kw: Any) -> OrderForm:
    values: dict[str, Any] = {
        "title": "Electrical Fittings & Supplies",
        "has_catalog": True,
        "currency": "IDR",
    }
    values.update(kw)
    return OrderForm(id=new_id(), edition_id=edition_id, code=code, **values)


def _item(form: OrderForm, code: str = "E-001", **kw: Any) -> OrderFormItem:
    return OrderFormItem(
        id=new_id(),
        edition_id=form.edition_id,
        form_id=form.id,
        code=code,
        name="Fluorescent lamp 40 W",
        price_regular=Decimal("740600.00"),
        **kw,
    )


async def _exhibitor(edition_id: uuid.UUID, n: int = 1) -> tuple[ExhibitorLead, Booth]:
    booth = Booth(
        id=new_id(),
        edition_id=edition_id,
        code=f"A{n:02d}",
        area_sqm=Decimal("18.00"),
        price=Decimal("30000000.00"),
        currency="IDR",
    )
    email = f"exhibitor-{n:03d}@example.test"
    account = ExhibitorAccount(id=new_id(), email=email, email_normalized=email)
    await _add(booth, account)
    lead = ExhibitorLead(
        id=new_id(),
        edition_id=edition_id,
        company_name="Example Corp",
        contact_name="Test Contact",
        email=email,
        email_normalized=email,
        stage="EXHIBITOR",
        booth_id=booth.id,
        exhibitor_account_id=account.id,
    )
    await _add(lead)
    return lead, booth


def _order(lead: ExhibitorLead, form: OrderForm, **kw: Any) -> ExhibitorOrder:
    return ExhibitorOrder(
        id=new_id(),
        edition_id=lead.edition_id,
        exhibitor_lead_id=lead.id,
        form_id=form.id,
        currency="IDR",
        **kw,
    )


def _submitted(booth: Booth, number: str = "E1-O-0001", **kw: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "status": "SUBMITTED",
        "order_number": number,
        "submitted_at": NOW,
        "price_period": "REGULAR",
        "booth_id_at_submit": booth.id,
        "area_sqm_at_submit": booth.area_sqm,
    }
    values.update(kw)
    return values


async def _setup() -> tuple[ExhibitorLead, Booth, OrderForm]:
    edition = await make_edition()
    lead, booth = await _exhibitor(edition.id)
    form = _form(edition.id)
    await _add(form)
    return lead, booth, form


# Forms and catalog


async def test_form_code_unique_per_edition_only() -> None:
    e1, e2 = await make_edition(), await make_edition()
    await _add(_form(e1.id), _form(e2.id))
    with pytest.raises(IntegrityError, match="uq_order_forms_edition_id_code"):
        await _add(_form(e1.id))


@pytest.mark.parametrize(
    ("kw", "constraint"),
    [
        ({"code": "4"}, "code_format"),
        ({"code": "04A"}, "code_format"),
        ({"details_type": "survey"}, "details_type_valid"),
        ({"attachment_purposes": ["LOGO", "SELFIE"]}, "attachment_purposes_valid"),
        ({"has_catalog": False, "allow_custom_items": True}, "custom_items_need_catalog"),
        (
            {"deadline_on": NOW.date(), "closes_on": NOW.date().replace(day=9)},
            "closes_after_deadline",
        ),
        ({"secondary_deadline_label": "Material Deadline"}, "secondary_deadline_complete"),
    ],
)
async def test_form_checks(kw: dict[str, Any], constraint: str) -> None:
    edition = await make_edition()
    with pytest.raises(IntegrityError, match=constraint):
        await _add(_form(edition.id, **kw))


async def test_form_accepts_known_purposes_and_types() -> None:
    edition = await make_edition()
    await _add(
        _form(
            edition.id,
            code="02a",
            has_catalog=False,
            details_type="social_media",
            attachment_purposes=["LOGO", "PRODUCT_IMAGE"],
        )
    )


async def test_item_code_unique_per_form() -> None:
    edition = await make_edition()
    f04, f07 = _form(edition.id, "04"), _form(edition.id, "07")
    await _add(f04, f07, _item(f04), _item(f07))
    with pytest.raises(IntegrityError, match="uq_order_form_items_form_id_code"):
        await _add(_item(f04))


async def test_item_of_a_form_from_another_edition_rejected() -> None:
    e1, e2 = await make_edition(), await make_edition()
    form = _form(e2.id)
    await _add(form)
    item = _item(form)
    item.edition_id = e1.id
    with pytest.raises(IntegrityError, match="fk_order_form_items_form_id_order_forms"):
        await _add(item)


@pytest.mark.parametrize(
    ("kw", "constraint"),
    [
        ({"price_regular": Decimal("-1")}, "price_regular_not_negative"),
        ({"price_surcharge": Decimal("-1")}, "price_surcharge_not_negative"),
        ({"price_onsite": Decimal("-1")}, "price_onsite_not_negative"),
        ({"max_quantity": 0}, "max_quantity_positive"),
    ],
)
async def test_item_checks(kw: dict[str, Any], constraint: str) -> None:
    edition = await make_edition()
    form = _form(edition.id)
    await _add(form)
    item = _item(form)
    for key, value in kw.items():
        setattr(item, key, value)
    with pytest.raises(IntegrityError, match=constraint):
        await _add(item)


# Orders


async def test_one_open_order_per_form() -> None:
    lead, _booth, form = await _setup()
    await _add(_order(lead, form))
    with pytest.raises(IntegrityError, match="uq_exhibitor_orders_open_per_form"):
        await _add(_order(lead, form))


async def test_returned_order_also_counts_as_open() -> None:
    lead, booth, form = await _setup()
    reviewer = await make_user()
    returned = _submitted(
        booth, status="RETURNED", reviewed_by=reviewer.id, reviewed_at=NOW, review_notes="Fix"
    )
    await _add(_order(lead, form, **returned))
    with pytest.raises(IntegrityError, match="uq_exhibitor_orders_open_per_form"):
        await _add(_order(lead, form))


async def test_new_draft_next_to_sent_orders() -> None:
    lead, booth, form = await _setup()
    reviewer = await make_user()
    await _add(
        _order(lead, form, **_submitted(booth, "E1-O-0001")),
        _order(
            lead,
            form,
            **_submitted(
                booth, "E1-O-0002", status="APPROVED", reviewed_by=reviewer.id, reviewed_at=NOW
            ),
        ),
        _order(lead, form),
    )


async def test_order_number_unique_per_edition() -> None:
    lead, booth, form = await _setup()
    other_form = _form(lead.edition_id, "07")
    await _add(other_form, _order(lead, form, **_submitted(booth, "E1-O-0001")))
    with pytest.raises(IntegrityError, match="uq_exhibitor_orders_edition_number"):
        await _add(_order(lead, other_form, **_submitted(booth, "E1-O-0001")))


async def test_order_lead_from_another_edition_rejected() -> None:
    e1, e2 = await make_edition(), await make_edition()
    lead, _booth = await _exhibitor(e2.id)
    form = _form(e1.id)
    await _add(form)
    order = _order(lead, form)
    order.edition_id = e1.id
    with pytest.raises(
        IntegrityError, match="fk_exhibitor_orders_exhibitor_lead_id_exhibitor_leads"
    ):
        await _add(order)


async def test_order_form_from_another_edition_rejected() -> None:
    e1, e2 = await make_edition(), await make_edition()
    lead, _booth = await _exhibitor(e1.id)
    form = _form(e2.id)
    await _add(form)
    with pytest.raises(IntegrityError, match="fk_exhibitor_orders_form_id_order_forms"):
        await _add(_order(lead, form))


@pytest.mark.parametrize(
    "missing", ["order_number", "submitted_at", "price_period", "booth_id_at_submit"]
)
async def test_submitted_order_is_complete(missing: str) -> None:
    lead, booth, form = await _setup()
    values = _submitted(booth)
    values[missing] = None
    if missing == "booth_id_at_submit":
        values["area_sqm_at_submit"] = None
    with pytest.raises(IntegrityError, match="submitted_complete"):
        await _add(_order(lead, form, **values))


async def test_draft_has_no_submit_data() -> None:
    lead, booth, form = await _setup()
    with pytest.raises(IntegrityError, match="submitted_complete"):
        await _add(_order(lead, form, order_number="E1-O-0001"))
    with pytest.raises(IntegrityError, match="submitted_complete"):
        await _add(_order(lead, form, **{**_submitted(booth), "status": "DRAFT"}))


async def test_booth_and_area_go_together() -> None:
    lead, booth, form = await _setup()
    with pytest.raises(IntegrityError, match="submitted_complete"):
        await _add(_order(lead, form, **_submitted(booth, area_sqm_at_submit=None)))


@pytest.mark.parametrize(
    ("kw", "constraint"),
    [
        ({"status": "APPROVED"}, "reviewed_complete"),
        ({"status": "RETURNED", "review_notes": "Fix"}, "reviewed_complete"),
        ({"status": "RETURNED", "reviewed_at": NOW, "with_reviewer": True}, "returned_has_reason"),
        ({"status": "CANCELLED"}, "cancelled_has_reason"),
        ({"cancel_reason": "Duplicate"}, "cancelled_has_reason"),
        ({"status": "PAID"}, "status_valid"),
        ({"price_period": "EARLY_BIRD"}, "price_period_valid"),
        ({"total": Decimal("-1")}, "total_not_negative"),
    ],
)
async def test_order_review_and_status_checks(kw: dict[str, Any], constraint: str) -> None:
    lead, booth, form = await _setup()
    if kw.pop("with_reviewer", False):
        kw["reviewed_by"] = (await make_user()).id
    with pytest.raises(IntegrityError, match=constraint):
        await _add(_order(lead, form, **_submitted(booth, **kw)))


async def test_approved_and_cancelled_orders_accepted() -> None:
    lead, booth, form = await _setup()
    reviewer = await make_user()
    await _add(
        _order(
            lead,
            form,
            **_submitted(
                booth,
                "E1-O-0001",
                status="APPROVED",
                reviewed_by=reviewer.id,
                reviewed_at=NOW,
                total=Decimal("1481200.00"),
            ),
        ),
        _order(
            lead,
            form,
            **_submitted(booth, "E1-O-0002", status="CANCELLED", cancel_reason="Ordered twice"),
        ),
    )


# Lines


def _line(
    order: ExhibitorOrder, item: OrderFormItem | None = None, **kw: Any
) -> ExhibitorOrderLine:
    values: dict[str, Any] = {"name": "Line", "quantity": 2}
    if item is not None:
        values.update(
            item_id=item.id,
            code=item.code,
            name=item.name,
            unit_price=item.price_regular,
            amount=2 * item.price_regular,
        )
    values.update(kw)
    return ExhibitorOrderLine(id=new_id(), edition_id=order.edition_id, order_id=order.id, **values)


async def test_catalog_and_extra_lines_accepted() -> None:
    lead, _booth, form = await _setup()
    item, order = _item(form), _order(lead, form)
    await _add(item, order)
    await _add(
        _line(order, item),
        _line(order, name="Custom spotlight", image_key="orders/abc.jpg"),  # waits for a price
        _line(order, name="Custom stand", unit_price=Decimal("50000"), amount=Decimal("100000")),
    )


async def test_one_line_per_catalog_item() -> None:
    lead, _booth, form = await _setup()
    item, order = _item(form), _order(lead, form)
    await _add(item, order, _line(order, item))
    with pytest.raises(IntegrityError, match="uq_exhibitor_order_lines_order_item"):
        await _add(_line(order, item))


@pytest.mark.parametrize(
    ("kw", "constraint"),
    [
        ({"quantity": 0, "amount": Decimal("0")}, "quantity_positive"),
        ({"free_quantity": 3}, "free_quantity_valid"),
        ({"free_quantity": -1}, "free_quantity_valid"),
        ({"unit_price": None, "amount": None}, "catalog_line_priced"),
        ({"amount": None}, "amount_with_price"),
        ({"unit_price": Decimal("-1"), "amount": Decimal("0")}, "unit_price_not_negative"),
        ({"amount": Decimal("-1")}, "amount_not_negative"),
        ({"image_key": "orders/abc.jpg"}, "image_only_on_extra_items"),
    ],
)
async def test_line_checks(kw: dict[str, Any], constraint: str) -> None:
    lead, _booth, form = await _setup()
    item, order = _item(form), _order(lead, form)
    await _add(item, order)
    with pytest.raises(IntegrityError, match=constraint):
        await _add(_line(order, item, **kw))


async def test_line_item_from_another_edition_rejected() -> None:
    e1, e2 = await make_edition(), await make_edition()
    lead, _booth = await _exhibitor(e1.id)
    form, foreign_form = _form(e1.id), _form(e2.id)
    foreign_item = _item(foreign_form)
    order = _order(lead, form)
    await _add(form, foreign_form, foreign_item, order)
    with pytest.raises(IntegrityError, match="fk_exhibitor_order_lines_item_id_order_form_items"):
        await _add(_line(order, foreign_item))


async def test_deleting_a_draft_removes_its_lines_and_files() -> None:
    lead, _booth, form = await _setup()
    item, order = _item(form), _order(lead, form)
    attachment = ExhibitorOrderFile(
        edition_id=order.edition_id,
        order_id=order.id,
        purpose="FITTING_LOCATION",
        file_key="orders/fitting.pdf",
        file_name="fitting.pdf",
        content_type="application/pdf",
        size_bytes=1024,
    )
    await _add(item, order, _line(order, item), attachment)
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(delete(ExhibitorOrder).where(ExhibitorOrder.id == order.id))
    async with get_sessionmaker()() as session:
        lines = await session.scalar(select(func.count()).select_from(ExhibitorOrderLine))
        files = await session.scalar(select(func.count()).select_from(ExhibitorOrderFile))
    assert (lines, files) == (0, 0)


# Files and waivers


@pytest.mark.parametrize(
    ("kw", "constraint"),
    [
        ({"purpose": "SELFIE"}, "purpose_valid"),
        ({"size_bytes": 0}, "size_positive"),
    ],
)
async def test_file_checks(kw: dict[str, Any], constraint: str) -> None:
    lead, _booth, form = await _setup()
    order = _order(lead, form)
    await _add(order)
    values: dict[str, Any] = {
        "purpose": "LOGO",
        "file_key": f"orders/{uuid.uuid4()}.png",
        "file_name": "logo.png",
        "content_type": "image/png",
        "size_bytes": 2048,
    }
    values.update(kw)
    with pytest.raises(IntegrityError, match=constraint):
        await _add(ExhibitorOrderFile(edition_id=order.edition_id, order_id=order.id, **values))


async def test_waiver_once_per_form() -> None:
    lead, _booth, form = await _setup()

    def waiver() -> ExhibitorFormWaiver:
        return ExhibitorFormWaiver(
            edition_id=lead.edition_id, exhibitor_lead_id=lead.id, form_id=form.id
        )

    await _add(waiver())
    with pytest.raises(IntegrityError, match="uq_exhibitor_form_waivers_exhibitor_lead_id_form_id"):
        await _add(waiver())
