"""Order forms in the exhibitor portal (Phase 3 of docs/EXHIBITOR_ORDER_FORMS.md).

Callers resolve the exhibitor with exhibitors.portal.own_exhibitor first, so every function here
works on the account's own lead. Prices, totals, statuses, and the price period always come from
the server; the portal sends item ids and quantities only.
"""

import uuid
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import PurePosixPath
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from starlette.concurrency import run_in_threadpool

from app.core import audit
from app.core.config import get_settings
from app.core.errors import Conflict, NotFound, ValidationFailed, check_version
from app.core.storage import get_storage, new_object_key
from app.modules.exhibitions import service as exhibitions_service
from app.modules.exhibitions.models import Edition
from app.modules.exhibitors import repository as exhibitors_repo
from app.modules.exhibitors.models import ExhibitorLead
from app.modules.exhibitors.rules import ContractStatus
from app.modules.orders import repository as repo
from app.modules.orders.models import (
    ExhibitorFormWaiver,
    ExhibitorOrder,
    ExhibitorOrderFile,
    ExhibitorOrderLine,
    OrderForm,
    OrderFormItem,
)
from app.modules.orders.rules import (
    OPEN_STATUSES,
    AttachmentPurpose,
    DateRange,
    OrderStatus,
    PricePeriod,
    PricePeriods,
    can_move,
    can_waive,
    form_progress,
    line_amount,
    order_total,
    price_period,
    unit_price,
)
from app.modules.orders.schemas import (
    OrderDraftIn,
    PortalCatalogItemOut,
    PortalOrderFileOut,
    PortalOrderFormDetailOut,
    PortalOrderFormOut,
    PortalOrderFormsOut,
    PortalOrderLineOut,
    PortalOrderOut,
)
from app.modules.visitors.rules import clean_text

ENTITY = "exhibitor_order"
AUDIT_FIELDS = ("order_number", "status", "price_period", "remarks", "total", "submitted_at")
FILE_MAX_BYTES = 10 * 1024 * 1024
IMAGE_MAX_BYTES = 5 * 1024 * 1024
MAX_FILES_PER_ORDER = 20

PDF = ("application/pdf", b"%PDF-")
JPG = ("image/jpeg", b"\xff\xd8\xff")
PNG = ("image/png", b"\x89PNG\r\n\x1a\n")
XLSX = ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", b"PK\x03\x04")
_KINDS = {".pdf": PDF, ".jpg": JPG, ".jpeg": JPG, ".png": PNG, ".xlsx": XLSX}
_IMAGES = (".jpg", ".jpeg", ".png")
# What each attachment may be.
_PURPOSE_KINDS: dict[str, tuple[str, ...]] = {
    AttachmentPurpose.LOGO: _IMAGES,
    AttachmentPurpose.PRODUCT_IMAGE: _IMAGES,
    AttachmentPurpose.FITTING_LOCATION: (".pdf", *_IMAGES),
    AttachmentPurpose.VISA_LIST: (".xlsx", ".pdf"),
    AttachmentPurpose.OTHER: (".pdf", ".xlsx", *_IMAGES),
}
_SENT = frozenset({OrderStatus.SUBMITTED, OrderStatus.RETURNED, OrderStatus.APPROVED})


# --- context -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Clock:
    """The edition's calendar today: deadlines and price periods are edition days."""

    edition: Edition
    today: date

    @property
    def period(self) -> PricePeriod | None:
        e = self.edition

        def window(start: date | None, end: date | None) -> DateRange | None:
            return DateRange(start, end) if start and end else None

        periods = PricePeriods(
            regular=window(e.price_regular_from, e.price_regular_to),
            surcharge=window(e.price_surcharge_from, e.price_surcharge_to),
            onsite=window(e.price_onsite_from, e.price_onsite_to),
        )
        return price_period(self.today, periods)

    def closes_on(self, form: OrderForm) -> date | None:
        return form.closes_on or self.edition.order_expired_on

    def is_closed(self, form: OrderForm) -> bool:
        closes = self.closes_on(form)
        return closes is not None and self.today > closes


async def _clock(session: AsyncSession, lead: ExhibitorLead) -> Clock:
    edition = await exhibitions_service.get_edition_by_id(session, lead.edition_id)
    if edition is None:  # FK makes this impossible; kept for the type checker
        raise NotFound("Edition not found.")
    return Clock(edition, datetime.now(ZoneInfo(edition.timezone)).date())


async def _form(session: AsyncSession, lead: ExhibitorLead, code: str) -> OrderForm:
    form = await repo.published_form(session, lead.edition_id, code)
    if form is None:
        raise NotFound("Order form not found.")
    return form


async def _own_order(
    session: AsyncSession, lead: ExhibitorLead, order_id: uuid.UUID, *, for_update: bool = False
) -> tuple[ExhibitorOrder, OrderForm]:
    """The exhibitor's own order on a published form; anything else is a 404."""
    order = await repo.get_order(session, order_id, for_update=for_update)
    if order is None or order.exhibitor_lead_id != lead.id:
        raise NotFound("Order not found.")
    form = await repo.get_form(session, order.form_id)
    if form is None or not form.is_published:
        raise NotFound("Order not found.")
    return order, form


def _require_open(order: ExhibitorOrder) -> None:
    if order.status not in OPEN_STATUSES:
        raise Conflict("This order was sent and can no longer change.", code="ORDER_SENT")


async def _writable(session: AsyncSession, lead: ExhibitorLead) -> None:
    await exhibitions_service.ensure_writable(session, lead.edition_id)


# --- output ------------------------------------------------------------------------------


def _item_price(item: OrderFormItem, period: PricePeriod | None) -> Decimal:
    # Before ordering opens the catalog shows the regular price.
    return unit_price(
        period or PricePeriod.REGULAR, item.price_regular, item.price_surcharge, item.price_onsite
    )


def _line_out(line: ExhibitorOrderLine) -> PortalOrderLineOut:
    return PortalOrderLineOut(
        id=line.id,
        item_id=line.item_id,
        section=line.section,
        code=line.code,
        name=line.name,
        size=line.size,
        quantity=line.quantity,
        free_quantity=line.free_quantity,
        unit_price=line.unit_price,
        amount=line.amount,
        has_image=line.image_key is not None,
        notes=line.notes,
    )


def _file_out(f: ExhibitorOrderFile) -> PortalOrderFileOut:
    return PortalOrderFileOut(
        id=f.id,
        purpose=AttachmentPurpose(f.purpose),
        file_name=f.file_name,
        size_bytes=f.size_bytes,
        created_at=f.created_at,
    )


def _order_out(
    order: ExhibitorOrder,
    form: OrderForm,
    lines: Sequence[ExhibitorOrderLine],
    files: Sequence[ExhibitorOrderFile],
    contract_signed: bool,
) -> PortalOrderOut:
    unpriced = sum(1 for line in lines if line.unit_price is None)
    status = OrderStatus(order.status)
    costs_money = order.total > 0 or unpriced > 0
    return PortalOrderOut(
        id=order.id,
        form_code=form.code,
        order_number=order.order_number,
        status=status,
        price_period=PricePeriod(order.price_period) if order.price_period else None,
        remarks=order.remarks,
        total=order.total,
        currency=order.currency,
        submitted_at=order.submitted_at,
        review_notes=order.review_notes if status == OrderStatus.RETURNED else None,
        cancel_reason=order.cancel_reason,
        unpriced_lines=unpriced,
        waiting_for_contract=status == OrderStatus.SUBMITTED
        and costs_money
        and not contract_signed,
        lines=[_line_out(line) for line in lines],
        files=[_file_out(f) for f in files],
        version=order.version,
    )


async def _contract_signed(session: AsyncSession, lead: ExhibitorLead) -> bool:
    contract = await exhibitors_repo.get_contract(session, lead.id)
    return contract is not None and contract.status == ContractStatus.SIGNED


async def _orders_out(
    session: AsyncSession, lead: ExhibitorLead, form: OrderForm, orders: Sequence[ExhibitorOrder]
) -> list[PortalOrderOut]:
    ids = [o.id for o in orders]
    lines = await repo.order_lines(session, ids)
    files = await repo.order_files(session, ids)
    signed = await _contract_signed(session, lead)
    return [
        _order_out(
            o,
            form,
            [line for line in lines if line.order_id == o.id],
            [f for f in files if f.order_id == o.id],
            signed,
        )
        for o in orders
    ]


async def _one_order_out(
    session: AsyncSession, lead: ExhibitorLead, form: OrderForm, order: ExhibitorOrder
) -> PortalOrderOut:
    return (await _orders_out(session, lead, form, [order]))[0]


# --- reading -----------------------------------------------------------------------------


async def list_forms(session: AsyncSession, lead: ExhibitorLead) -> PortalOrderFormsOut:
    clock = await _clock(session, lead)
    forms = await repo.published_forms(session, lead.edition_id)
    orders = await repo.lead_orders(session, lead.id)
    waived = await repo.waived_form_ids(session, lead.id)
    rows = []
    for form in forms:
        mine = [o for o in orders if o.form_id == form.id]
        statuses = [OrderStatus(o.status) for o in mine]
        rows.append(
            PortalOrderFormOut(
                code=form.code,
                title=form.title,
                has_catalog=form.has_catalog,
                details_type=form.details_type,
                deadline_on=form.deadline_on,
                closes_on=clock.closes_on(form),
                secondary_deadline_label=form.secondary_deadline_label,
                secondary_deadline_on=form.secondary_deadline_on,
                is_closed=clock.is_closed(form),
                progress=form_progress(statuses, form.id in waived),
                open_order_id=next((o.id for o in mine if o.status in OPEN_STATUSES), None),
                sent_orders=sum(1 for s in statuses if s in _SENT),
            )
        )
    return PortalOrderFormsOut(forms=rows, price_period=clock.period)


async def form_detail(
    session: AsyncSession, lead: ExhibitorLead, code: str
) -> PortalOrderFormDetailOut:
    clock = await _clock(session, lead)
    form = await _form(session, lead, code)
    period = clock.period
    items = await repo.active_items(session, form.id) if form.has_catalog else []
    orders = await repo.lead_orders(session, lead.id, form.id)
    outs = await _orders_out(session, lead, form, orders)
    waiver = await repo.get_waiver(session, lead.id, form.id)
    return PortalOrderFormDetailOut(
        code=form.code,
        title=form.title,
        instructions=form.instructions,
        currency=form.currency,
        has_catalog=form.has_catalog,
        allow_custom_items=form.allow_custom_items,
        details_type=form.details_type,
        attachment_purposes=[AttachmentPurpose(p) for p in form.attachment_purposes],
        deadline_on=form.deadline_on,
        closes_on=clock.closes_on(form),
        secondary_deadline_label=form.secondary_deadline_label,
        secondary_deadline_on=form.secondary_deadline_on,
        is_closed=clock.is_closed(form),
        price_period=period,
        progress=form_progress([OrderStatus(o.status) for o in orders], waiver is not None),
        not_required=waiver is not None,
        company_name=lead.company_name,
        booth_code=await exhibitors_repo.booth_code(session, lead.booth_id),
        items=[
            PortalCatalogItemOut(
                id=i.id,
                section=i.section,
                code=i.code,
                name=i.name,
                description=i.description,
                size=i.size,
                unit=i.unit,
                unit_price=_item_price(i, period),
                max_quantity=i.max_quantity,
                has_image=i.image_key is not None,
            )
            for i in items
        ],
        open_order=next((o for o in outs if o.status in OPEN_STATUSES), None),
        sent_orders=[o for o in outs if o.status not in OPEN_STATUSES],
    )


# --- audit -------------------------------------------------------------------------------


def _lines_summary(lines: Sequence[ExhibitorOrderLine]) -> list[dict[str, Any]]:
    return [
        {
            "code": line.code,
            "name": line.name,
            "quantity": line.quantity,
            "unit_price": line.unit_price,
        }
        for line in lines
    ]


async def _record(
    session: AsyncSession,
    order: ExhibitorOrder,
    action: str,
    account_id: uuid.UUID,
    before: dict[str, Any] | None = None,
    **extra: Any,
) -> None:
    after = audit.snapshot(order, AUDIT_FIELDS)
    # Portal actors are not users; the account goes into the entry instead.
    await audit.record(
        session,
        entity_type=ENTITY,
        entity_id=order.id,
        action=action,
        before=before,
        after=after | {"portal_account_id": account_id} | extra,
        edition_id=order.edition_id,
    )


# --- drafts ------------------------------------------------------------------------------


async def create_order(
    session: AsyncSession, account_id: uuid.UUID, lead: ExhibitorLead, code: str
) -> PortalOrderOut:
    """Start a draft on a form; one open order per form (decision O7)."""
    await _writable(session, lead)
    clock = await _clock(session, lead)
    form = await _form(session, lead, code)
    if clock.is_closed(form):
        raise ValidationFailed("This form is closed.", code="FORM_CLOSED")
    if any(o.status in OPEN_STATUSES for o in await repo.lead_orders(session, lead.id, form.id)):
        raise Conflict("You already have an order in progress on this form.", code="ORDER_OPEN")
    order = ExhibitorOrder(
        edition_id=lead.edition_id,
        exhibitor_lead_id=lead.id,
        form_id=form.id,
        currency=form.currency,
    )
    session.add(order)
    await session.flush()
    await session.refresh(order)
    await _record(session, order, "create", account_id, form_code=form.code)
    return await _one_order_out(session, lead, form, order)


def _clean_custom(
    name: str, size: str | None, notes: str | None
) -> tuple[str, str | None, str | None]:
    clean_name = clean_text(name)
    if clean_name is None:
        raise ValidationFailed(fields={"custom_lines": "Each extra item needs a name."})
    return clean_name, clean_text(size), clean_text(notes)


async def update_order(
    session: AsyncSession,
    account_id: uuid.UUID,
    lead: ExhibitorLead,
    order_id: uuid.UUID,
    data: OrderDraftIn,
) -> PortalOrderOut:
    """Save the draft: catalog quantities, extra items, remarks. Lines left out are removed.

    Prices on a draft are today's prices, an estimate; submit fixes them.
    """
    await _writable(session, lead)
    order, form = await _own_order(session, lead, order_id, for_update=True)
    check_version(order.version, data.version)
    _require_open(order)
    if data.lines and not form.has_catalog:
        raise ValidationFailed(fields={"lines": "This form has no catalog."})
    if data.custom_lines and not form.allow_custom_items:
        raise ValidationFailed(fields={"custom_lines": "This form takes catalog items only."})
    period = (await _clock(session, lead)).period
    catalog = {i.id: i for i in await repo.active_items(session, form.id)}
    errors: dict[str, str] = {}
    seen: set[uuid.UUID] = set()
    for row in data.lines:
        item = catalog.get(row.item_id)
        if item is None:
            errors[f"lines.{row.item_id}"] = "This item is no longer available."
        elif row.item_id in seen:
            errors[f"lines.{row.item_id}"] = "Listed twice."
        elif item.max_quantity is not None and row.quantity > item.max_quantity:
            errors[f"lines.{row.item_id}"] = f"At most {item.max_quantity} per order."
        seen.add(row.item_id)
    if errors:
        raise ValidationFailed(fields=errors)

    existing = list(await repo.order_lines(session, [order.id]))
    kept_images = {line.id: line.image_key for line in existing if line.item_id is None}
    for line in existing:
        await session.delete(line)
    await session.flush()
    lines: list[ExhibitorOrderLine] = []
    for n, row in enumerate(data.lines):
        item = catalog[row.item_id]
        price = _item_price(item, period)
        lines.append(
            ExhibitorOrderLine(
                edition_id=order.edition_id,
                order_id=order.id,
                item_id=item.id,
                section=item.section,
                code=item.code,
                name=item.name,
                size=item.size,
                quantity=row.quantity,
                free_quantity=0,
                unit_price=price,
                amount=line_amount(row.quantity, 0, price),
                sort_order=n,
            )
        )
    for n, custom in enumerate(data.custom_lines):
        name, size, notes = _clean_custom(custom.name, custom.size, custom.notes)
        lines.append(
            ExhibitorOrderLine(
                edition_id=order.edition_id,
                order_id=order.id,
                name=name,
                size=size,
                notes=notes,
                quantity=custom.quantity,
                free_quantity=0,
                image_key=kept_images.get(custom.id) if custom.id else None,
                sort_order=len(data.lines) + n,
            )
        )
    session.add_all(lines)
    order.remarks = clean_text(data.remarks)
    order.total = order_total(line.amount for line in lines)
    flag_modified(order, "details")  # line edits bump the order's version too
    await session.flush()
    await session.refresh(order)
    await _record(session, order, "update", account_id, lines=_lines_summary(lines))
    return await _one_order_out(session, lead, form, order)


async def delete_order(
    session: AsyncSession, account_id: uuid.UUID, lead: ExhibitorLead, order_id: uuid.UUID
) -> None:
    """Throw away a draft that was never sent; its lines and files go with it."""
    await _writable(session, lead)
    order, _form = await _own_order(session, lead, order_id, for_update=True)
    if order.status != OrderStatus.DRAFT:
        raise Conflict("Only a draft that was never sent can be deleted.", code="ORDER_SENT")
    before = audit.snapshot(order, AUDIT_FIELDS)
    await _record(session, order, "delete", account_id, before)
    await session.delete(order)
    await session.flush()


async def quote_order(
    session: AsyncSession, lead: ExhibitorLead, order_id: uuid.UUID
) -> PortalOrderOut:
    """The order at today's prices, as it would be sent; nothing is saved."""
    order, form = await _own_order(session, lead, order_id)
    period = (await _clock(session, lead)).period
    out = await _one_order_out(session, lead, form, order)
    if order.status not in OPEN_STATUSES:
        return out
    catalog = {i.id: i for i in await repo.active_items(session, form.id)}
    for line in out.lines:
        item = catalog.get(line.item_id) if line.item_id else None
        if item is not None:
            line.unit_price = _item_price(item, period)
            line.amount = line_amount(line.quantity, line.free_quantity, line.unit_price)
    out.total = order_total(line.amount for line in out.lines)
    out.price_period = period
    return out


async def submit_order(
    session: AsyncSession,
    account_id: uuid.UUID,
    lead: ExhibitorLead,
    order_id: uuid.UUID,
    version: int,
) -> PortalOrderOut:
    """Send the order to staff. Prices are fixed here, from the period of today."""
    await _writable(session, lead)
    order, form = await _own_order(session, lead, order_id, for_update=True)
    check_version(order.version, version)
    if not can_move(OrderStatus(order.status), OrderStatus.SUBMITTED):
        raise Conflict("This order was already sent.", code="ORDER_SENT")
    clock = await _clock(session, lead)
    if clock.is_closed(form):
        raise ValidationFailed("This form is closed.", code="FORM_CLOSED")
    period = clock.period
    if period is None:
        raise ValidationFailed(
            "Ordering is not open: today is outside the price periods of this edition.",
            code="ORDERING_NOT_OPEN",
        )
    lines = list(await repo.order_lines(session, [order.id]))
    files = await repo.order_files(session, [order.id])
    if not lines and not files and not order.details:
        raise ValidationFailed("Add at least one item before sending.", code="ORDER_EMPTY")
    catalog = {i.id: i for i in await repo.active_items(session, form.id)}
    errors: dict[str, str] = {}
    for line in lines:
        if line.item_id is None:
            continue
        item = catalog.get(line.item_id)
        if item is None:
            errors[f"lines.{line.item_id}"] = f"{line.name} is no longer available. Remove it."
        elif item.max_quantity is not None and line.quantity > item.max_quantity:
            errors[f"lines.{line.item_id}"] = f"At most {item.max_quantity} per order."
        else:
            line.unit_price = _item_price(item, period)
            line.amount = line_amount(line.quantity, line.free_quantity, line.unit_price)
    if errors:
        raise ValidationFailed("Some items changed since you saved.", fields=errors)
    booth = await exhibitors_repo.get_booth(session, lead.booth_id) if lead.booth_id else None
    if booth is None:  # an exhibitor always holds a booth (database check)
        raise Conflict("Your booth is not set. Contact the organizer.", code="NO_BOOTH")
    before = audit.snapshot(order, AUDIT_FIELDS)
    if order.order_number is None:
        number = await repo.next_order_number(session, order.edition_id)
        order.order_number = f"{clock.edition.code}-O-{number:04d}"
    order.status = OrderStatus.SUBMITTED
    order.price_period = period
    order.total = order_total(line.amount for line in lines)
    order.submitted_at = datetime.now(UTC)
    order.submitted_by_account_id = account_id
    order.booth_id_at_submit = booth.id
    order.area_sqm_at_submit = booth.area_sqm
    flag_modified(order, "details")
    await session.flush()
    await session.refresh(order)
    # Sending an order answers "I don't require this form".
    waiver = await repo.get_waiver(session, lead.id, form.id)
    if waiver is not None:
        await session.delete(waiver)
        await session.flush()
    await _record(session, order, "submit", account_id, before, lines=_lines_summary(lines))
    return await _one_order_out(session, lead, form, order)


# --- extra item pictures and attachments -------------------------------------------------


def _check_file(
    file_name: str, content_type: str | None, data: bytes, allowed: tuple[str, ...], limit: int
) -> str:
    """Extension, MIME, magic bytes, size (BACKEND_RULES/security-permissions.md "Uploads")."""
    ext = PurePosixPath(file_name.lower()).suffix
    kind = _KINDS.get(ext) if ext in allowed else None
    # Some browsers send xlsx as octet-stream; the magic bytes still have to match.
    sent_ok = (
        not content_type
        or content_type == (kind or ("", b""))[0]
        or (ext == ".xlsx" and content_type == "application/octet-stream")
    )
    if kind is None or not sent_ok:
        names = "/".join(sorted({e.lstrip(".").upper() for e in allowed} - {"JPEG"}))
        raise ValidationFailed(fields={"file": f"Only {names} files are accepted."})
    if len(data) > limit:
        raise ValidationFailed(fields={"file": "File is too large."}, code="FILE_TOO_LARGE")
    if not data.startswith(kind[1]):
        raise ValidationFailed(fields={"file": "File content does not match its type."})
    return ext


def _display_name(file_name: str, fallback: str) -> str:
    """The uploader's file name, for display only; never used as a key or a header."""
    name = PurePosixPath(file_name.replace("\\", "/")).name
    return "".join(c for c in name if c.isprintable())[-255:] or fallback


async def _put(key: str, data: bytes, mime: str) -> None:
    await run_in_threadpool(get_storage().put, get_settings().s3_bucket_orders, key, data, mime)


async def _stream(key: str) -> Iterator[bytes]:
    return await run_in_threadpool(get_storage().stream, get_settings().s3_bucket_orders, key)


async def set_line_image(
    session: AsyncSession,
    account_id: uuid.UUID,
    lead: ExhibitorLead,
    order_id: uuid.UUID,
    line_id: uuid.UUID,
    *,
    file_name: str,
    content_type: str | None,
    data: bytes,
    version: int,
) -> PortalOrderOut:
    """Picture of an extra item, so staff can see what to price."""
    await _writable(session, lead)
    order, form = await _own_order(session, lead, order_id, for_update=True)
    check_version(order.version, version)
    _require_open(order)
    line = await repo.get_line(session, line_id)
    if line is None or line.order_id != order.id or line.item_id is not None:
        raise NotFound("Extra item not found.")
    ext = _check_file(file_name, content_type, data, _IMAGES, IMAGE_MAX_BYTES)
    key = new_object_key(ext)
    await _put(key, data, _KINDS[ext][0])
    line.image_key = key
    flag_modified(order, "details")
    await session.flush()
    await session.refresh(order)
    await _record(session, order, "line_image", account_id, line=line.name)
    return await _one_order_out(session, lead, form, order)


async def line_image(
    session: AsyncSession, lead: ExhibitorLead, order_id: uuid.UUID, line_id: uuid.UUID
) -> tuple[Iterator[bytes], str, str]:
    order, _form = await _own_order(session, lead, order_id)
    line = await repo.get_line(session, line_id)
    if line is None or line.order_id != order.id or line.image_key is None:
        raise NotFound("Picture not found.")
    ext = PurePosixPath(line.image_key).suffix
    return await _stream(line.image_key), f"item-{line.id}{ext}", _KINDS[ext][0]


async def add_file(
    session: AsyncSession,
    account_id: uuid.UUID,
    lead: ExhibitorLead,
    order_id: uuid.UUID,
    *,
    purpose: AttachmentPurpose,
    file_name: str,
    content_type: str | None,
    data: bytes,
    version: int,
) -> PortalOrderOut:
    """Attach a file the form asks for (logo, fitting location, visa list, ...)."""
    await _writable(session, lead)
    order, form = await _own_order(session, lead, order_id, for_update=True)
    check_version(order.version, version)
    _require_open(order)
    if purpose not in form.attachment_purposes:
        raise ValidationFailed(fields={"purpose": "This form does not take this attachment."})
    if len(await repo.order_files(session, [order.id])) >= MAX_FILES_PER_ORDER:
        raise ValidationFailed(
            fields={"file": f"At most {MAX_FILES_PER_ORDER} files per order."},
            code="TOO_MANY_FILES",
        )
    ext = _check_file(file_name, content_type, data, _PURPOSE_KINDS[purpose], FILE_MAX_BYTES)
    key = new_object_key(ext)
    await _put(key, data, _KINDS[ext][0])
    row = ExhibitorOrderFile(
        edition_id=order.edition_id,
        order_id=order.id,
        purpose=purpose,
        file_key=key,
        file_name=_display_name(file_name, f"attachment{ext}"),
        content_type=_KINDS[ext][0],
        size_bytes=len(data),
        uploaded_by_account_id=account_id,
    )
    session.add(row)
    flag_modified(order, "details")
    await session.flush()
    await session.refresh(order)
    await _record(session, order, "attach_file", account_id, purpose=purpose, file=row.file_name)
    return await _one_order_out(session, lead, form, order)


async def remove_file(
    session: AsyncSession,
    account_id: uuid.UUID,
    lead: ExhibitorLead,
    order_id: uuid.UUID,
    file_id: uuid.UUID,
    version: int,
) -> PortalOrderOut:
    await _writable(session, lead)
    order, form = await _own_order(session, lead, order_id, for_update=True)
    check_version(order.version, version)
    _require_open(order)
    row = await repo.get_file(session, file_id)
    if row is None or row.order_id != order.id:
        raise NotFound("File not found.")
    # The object stays in storage; its key is in the audit entry.
    await session.delete(row)
    flag_modified(order, "details")
    await session.flush()
    await session.refresh(order)
    await _record(
        session, order, "remove_file", account_id, file=row.file_name, file_key=row.file_key
    )
    return await _one_order_out(session, lead, form, order)


async def file_download(
    session: AsyncSession, lead: ExhibitorLead, order_id: uuid.UUID, file_id: uuid.UUID
) -> tuple[Iterator[bytes], str, str]:
    order, _form = await _own_order(session, lead, order_id)
    row = await repo.get_file(session, file_id)
    if row is None or row.order_id != order.id:
        raise NotFound("File not found.")
    ext = PurePosixPath(row.file_key).suffix
    return (
        await _stream(row.file_key),
        f"{order.order_number or 'order'}-{row.id}{ext}",
        row.content_type,
    )


async def item_image(
    session: AsyncSession, lead: ExhibitorLead, code: str, item_id: uuid.UUID
) -> tuple[Iterator[bytes], str, str]:
    """Catalog picture of a published form in the exhibitor's edition."""
    form = await _form(session, lead, code)
    item = await repo.get_item(session, item_id)
    if item is None or item.form_id != form.id or not item.is_active or item.image_key is None:
        raise NotFound("Picture not found.")
    ext = PurePosixPath(item.image_key).suffix
    return await _stream(item.image_key), f"item-{item.id}{ext}", _KINDS[ext][0]


# --- "I don't require this form" ---------------------------------------------------------


async def set_not_required(
    session: AsyncSession, account_id: uuid.UUID, lead: ExhibitorLead, code: str, value: bool
) -> PortalOrderFormDetailOut:
    await _writable(session, lead)
    form = await _form(session, lead, code)
    waiver = await repo.get_waiver(session, lead.id, form.id)
    if value and waiver is None:
        orders = await repo.lead_orders(session, lead.id, form.id)
        if not can_waive([OrderStatus(o.status) for o in orders]):
            raise Conflict("You already sent an order on this form.", code="FORM_HAS_ORDERS")
        session.add(
            ExhibitorFormWaiver(
                edition_id=lead.edition_id,
                exhibitor_lead_id=lead.id,
                form_id=form.id,
                waived_by_account_id=account_id,
            )
        )
        await session.flush()
    elif not value and waiver is not None:
        await session.delete(waiver)
        await session.flush()
    else:
        return await form_detail(session, lead, code)
    await audit.record(
        session,
        entity_type="exhibitor_form_waiver",
        entity_id=None,
        action="waive" if value else "unwaive",
        after={
            "form_code": form.code,
            "exhibitor_lead_id": lead.id,
            "portal_account_id": account_id,
        },
        edition_id=lead.edition_id,
    )
    return await form_detail(session, lead, code)
