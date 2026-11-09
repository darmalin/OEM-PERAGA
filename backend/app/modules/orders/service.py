"""Order form setup: forms, catalog items, item images, copy, Excel import (Phase 2 of
docs/EXHIBITOR_ORDER_FORMS.md)."""

import uuid
from collections.abc import Iterator
from decimal import Decimal, InvalidOperation
from pathlib import PurePosixPath
from typing import Any

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core import audit
from app.core.authorization import AuthContext
from app.core.config import get_settings
from app.core.context import current_actor_id
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed, check_version
from app.core.excel import is_xlsx, iter_rows, write_workbook
from app.core.pagination import Page
from app.core.storage import get_storage, new_object_key
from app.modules.exhibitions import service as exhibitions_service
from app.modules.orders import repository as repo
from app.modules.orders.models import OrderForm, OrderFormItem, OrderFormOption
from app.modules.orders.rules import DETAILS_OPTION_KINDS, DetailsType, OptionKind
from app.modules.orders.schemas import (
    CopyFormsIn,
    CopyFormsOut,
    FormOptionsIn,
    FormOptionsOut,
    ItemImportOut,
    ItemImportRowError,
    OrderFormCreateIn,
    OrderFormItemCreateIn,
    OrderFormItemListParams,
    OrderFormItemOut,
    OrderFormItemUpdateIn,
    OrderFormListParams,
    OrderFormOut,
    OrderFormUpdateIn,
)
from app.modules.visitors.rules import clean_text

MANAGE = "order_form.manage"
# Desk pages that show forms next to an exhibitor (lead page, review) read with this.
READ_PERMISSIONS = (MANAGE, "exhibitor_lead.read")

FORM_ENTITY = "order_form"
FORM_AUDIT_FIELDS = (
    "code", "title", "details_type", "has_catalog", "allow_custom_items", "attachment_purposes",
    "deadline_on", "closes_on", "secondary_deadline_label", "secondary_deadline_on",
    "instructions", "currency", "sort_order", "is_published",
)  # fmt: skip
ITEM_ENTITY = "order_form_item"
ITEM_AUDIT_FIELDS = (
    "section", "code", "name", "description", "size", "unit", "price_regular",
    "price_surcharge", "price_onsite", "max_quantity", "is_active", "sort_order", "image_key",
)  # fmt: skip
_FORM_TEXT = ("title", "secondary_deadline_label", "instructions")
_ITEM_TEXT = ("section", "code", "name", "description", "size", "unit")

IMAGE_MAX_BYTES = 5 * 1024 * 1024
IMPORT_MAX_BYTES = 2 * 1024 * 1024
IMPORT_MAX_ROWS = 1000
# Extension -> (MIME, leading magic bytes).
_IMAGE_KINDS = {
    ".jpg": ("image/jpeg", b"\xff\xd8\xff"),
    ".jpeg": ("image/jpeg", b"\xff\xd8\xff"),
    ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
}

# Spreadsheet header -> item field; the template uses these headers in this order.
IMPORT_COLUMNS = {
    "Section": "section",
    "Code": "code",
    "Name": "name",
    "Description": "description",
    "Size": "size",
    "Unit": "unit",
    "Price Regular": "price_regular",
    "Price Surcharge": "price_surcharge",
    "Price Onsite": "price_onsite",
    "Max Quantity": "max_quantity",
    "Active": "is_active",
    "Sort Order": "sort_order",
}
_KEEP_WHEN_BLANK = ("is_active", "sort_order")


# --- access ------------------------------------------------------------------------------


def _require_manager(ctx: AuthContext, edition_id: uuid.UUID) -> None:
    """Setup is edition master data: edition-wide order_form.manage only."""
    if not ctx.scope_for(edition_id, MANAGE).full_access:
        raise PermissionDenied()


def _require_reader(ctx: AuthContext, edition_id: uuid.UUID) -> None:
    for permission in READ_PERMISSIONS:
        try:
            ctx.scope_for(edition_id, permission)
        except NotFound:
            continue
        return
    raise NotFound("Edition not found.", code="EDITION_NOT_FOUND")


async def _form_for(
    session: AsyncSession,
    ctx: AuthContext,
    form_id: uuid.UUID,
    *,
    manage: bool,
    for_update: bool = False,
) -> OrderForm:
    """The form, or 404 when it does not exist or its edition is hidden from the caller."""
    form = await repo.get_form(session, form_id, for_update=for_update)
    if form is None:
        raise NotFound("Order form not found.")
    try:
        (_require_manager if manage else _require_reader)(ctx, form.edition_id)
    except NotFound as e:
        raise NotFound("Order form not found.") from e
    return form


async def _item_for(
    session: AsyncSession,
    ctx: AuthContext,
    form_id: uuid.UUID,
    item_id: uuid.UUID,
    *,
    manage: bool,
    for_update: bool = False,
) -> tuple[OrderForm, OrderFormItem]:
    form = await _form_for(session, ctx, form_id, manage=manage)
    item = await repo.get_item(session, item_id, for_update=for_update)
    if item is None or item.form_id != form.id:
        raise NotFound("Catalog item not found.")
    return form, item


# --- integrity ---------------------------------------------------------------------------


def _integrity_error(e: IntegrityError) -> Exception:
    msg = str(e.orig)
    if "uq_order_forms_edition_id_code" in msg:
        return Conflict(
            "Form number already used in this edition.",
            code="DUPLICATE_FORM_CODE",
            fields={"code": "Already used in this edition."},
        )
    if "uq_order_form_items_form_id_code" in msg:
        return Conflict(
            "Item code already used in this form.",
            code="DUPLICATE_ITEM_CODE",
            fields={"code": "Already used in this form."},
        )
    return e


async def _flush(session: AsyncSession, *rows: OrderForm | OrderFormItem) -> None:
    try:
        async with session.begin_nested():
            session.add_all(rows)
            await session.flush()
    except IntegrityError as e:
        raise _integrity_error(e) from e


# --- forms -------------------------------------------------------------------------------


def _form_out(form: OrderForm, active_items: int) -> OrderFormOut:
    out = OrderFormOut.model_validate(form)
    out.active_item_count = active_items
    return out


def _clean_form(values: dict[str, Any]) -> dict[str, Any]:
    out = {k: clean_text(v) if k in _FORM_TEXT else v for k, v in values.items()}
    for key in ("title", "has_catalog", "allow_custom_items", "currency", "sort_order"):
        if key in out and out[key] is None:
            raise ValidationFailed(fields={key: "Required."})
    if "attachment_purposes" in out and out["attachment_purposes"] is None:
        out["attachment_purposes"] = []
    return out


def _check_form(form: OrderForm, active_items: int) -> None:
    """Rules across fields, checked on the merged result of an edit."""
    errors: dict[str, str] = {}
    if form.allow_custom_items and not form.has_catalog:
        errors["allow_custom_items"] = "Extra items need a catalog form."
    if form.deadline_on and form.closes_on and form.closes_on < form.deadline_on:
        errors["closes_on"] = "Must be on or after the deadline."
    if (form.secondary_deadline_label is None) != (form.secondary_deadline_on is None):
        field = (
            "secondary_deadline_on"
            if form.secondary_deadline_label
            else ("secondary_deadline_label")
        )
        errors[field] = "Give both the label and the date, or neither."
    if errors:
        raise ValidationFailed(fields=errors)
    fillable = (
        (form.has_catalog and (active_items > 0 or form.allow_custom_items))
        or form.details_type is not None
        or bool(form.attachment_purposes)
    )
    if form.is_published and not fillable:
        raise ValidationFailed(
            "Add catalog items, questions, or attachments before publishing.",
            code="FORM_EMPTY",
        )


async def _save_form(
    session: AsyncSession, form: OrderForm, before: dict[str, Any] | None, action: str
) -> None:
    await _flush(session, form)
    await session.refresh(form)  # updated_at and version come back from the database
    await audit.record(
        session,
        entity_type=FORM_ENTITY,
        entity_id=form.id,
        action=action,
        before=before,
        after=audit.snapshot(form, FORM_AUDIT_FIELDS),
        edition_id=form.edition_id,
    )


async def list_forms(
    session: AsyncSession, ctx: AuthContext, params: OrderFormListParams
) -> Page[OrderFormOut]:
    _require_reader(ctx, params.edition_id)
    rows, total = await repo.list_forms(session, params.edition_id, params)
    return Page(
        items=[_form_out(form, count) for form, count in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def get_form(session: AsyncSession, ctx: AuthContext, form_id: uuid.UUID) -> OrderFormOut:
    form = await _form_for(session, ctx, form_id, manage=False)
    return _form_out(form, await repo.active_item_count(session, form.id))


async def create_form(
    session: AsyncSession, ctx: AuthContext, data: OrderFormCreateIn
) -> OrderFormOut:
    """New form, unpublished unless asked; currency defaults to the edition's."""
    _require_manager(ctx, data.edition_id)
    edition = await exhibitions_service.ensure_writable(session, data.edition_id)
    values = data.model_dump(exclude={"edition_id"})
    defaults = {
        "currency": edition.default_currency,
        "has_catalog": False,
        "allow_custom_items": False,
        "attachment_purposes": [],
        "sort_order": 0,
        "is_published": False,
    }
    values = {k: (defaults[k] if v is None and k in defaults else v) for k, v in values.items()}
    actor = current_actor_id()
    form = OrderForm(
        edition_id=data.edition_id, created_by=actor, updated_by=actor, **_clean_form(values)
    )
    _check_form(form, 0)
    await _save_form(session, form, None, "create")
    return _form_out(form, 0)


async def update_form(
    session: AsyncSession, ctx: AuthContext, form_id: uuid.UUID, data: OrderFormUpdateIn
) -> OrderFormOut:
    form = await _form_for(session, ctx, form_id, manage=True, for_update=True)
    check_version(form.version, data.version)
    await exhibitions_service.ensure_writable(session, form.edition_id)
    changes = _clean_form(data.model_dump(exclude_unset=True, exclude={"version"}))
    if changes.get("currency", form.currency) != form.currency and (
        await repo.sent_order_count(session, form.id)
    ):
        raise Conflict(
            "Orders were already sent in this currency.",
            code="FORM_HAS_ORDERS",
            fields={"currency": "Orders were already sent in this currency."},
        )
    before = audit.snapshot(form, FORM_AUDIT_FIELDS)
    for key, value in changes.items():
        setattr(form, key, value)
    active_items = await repo.active_item_count(session, form.id)
    _check_form(form, active_items)
    form.updated_by = current_actor_id()
    await _save_form(session, form, before, "update")
    return _form_out(form, active_items)


async def copy_forms(session: AsyncSession, ctx: AuthContext, data: CopyFormsIn) -> CopyFormsOut:
    """Copy forms and their catalog from another edition, so staff do not type them again.

    Forms whose number exists in the target are skipped. Copies start unpublished and without
    dates, which belong to the new edition. Item images are shared: objects are never edited.
    """
    if data.from_edition_id == data.to_edition_id:
        raise ValidationFailed(fields={"from_edition_id": "Choose another edition."})
    _require_manager(ctx, data.from_edition_id)
    _require_manager(ctx, data.to_edition_id)
    target = await exhibitions_service.ensure_writable(session, data.to_edition_id)
    existing = {f.code for f in await repo.edition_forms(session, target.id)}
    actor = current_actor_id()
    skipped: list[str] = []
    forms_copied = items_copied = 0
    for source in await repo.edition_forms(session, data.from_edition_id):
        if source.code in existing:
            skipped.append(source.code)
            continue
        values = audit.snapshot(source, FORM_AUDIT_FIELDS)
        values.update(
            deadline_on=None,
            closes_on=None,
            secondary_deadline_on=None,
            secondary_deadline_label=None,
            is_published=False,
        )
        form = OrderForm(edition_id=target.id, created_by=actor, updated_by=actor, **values)
        items = [
            OrderFormItem(
                edition_id=target.id,
                form_id=form.id,
                created_by=actor,
                updated_by=actor,
                **audit.snapshot(item, ITEM_AUDIT_FIELDS),
            )
            for item in await repo.form_items(session, source.id)
        ]
        await _flush(session, form)
        for item in items:
            item.form_id = form.id
        if items:
            await _flush(session, *items)
        for kind, choices in (await repo.form_options(session, source.id)).items():
            session.add_all(
                OrderFormOption(
                    edition_id=target.id, form_id=form.id, kind=kind, value=v, sort_order=n
                )
                for n, v in enumerate(choices)
            )
        await session.flush()
        forms_copied += 1
        items_copied += len(items)
    await audit.record(
        session,
        entity_type=FORM_ENTITY,
        entity_id=None,
        action="copy",
        after={
            "from_edition_id": str(data.from_edition_id),
            "forms_copied": forms_copied,
            "items_copied": items_copied,
            "skipped_codes": skipped,
        },
        edition_id=target.id,
    )
    return CopyFormsOut(forms_copied=forms_copied, items_copied=items_copied, skipped_codes=skipped)


# --- question choices --------------------------------------------------------------------


def _options_out(options: dict[str, list[str]]) -> FormOptionsOut:
    return FormOptionsOut(options={OptionKind(k): v for k, v in options.items()})


async def get_options(
    session: AsyncSession, ctx: AuthContext, form_id: uuid.UUID
) -> FormOptionsOut:
    form = await _form_for(session, ctx, form_id, manage=False)
    return _options_out(await repo.form_options(session, form.id))


async def set_options(
    session: AsyncSession, ctx: AuthContext, form_id: uuid.UUID, data: FormOptionsIn
) -> FormOptionsOut:
    """Replace the choices of one kind, in the order given. Sent answers keep their text."""
    form = await _form_for(session, ctx, form_id, manage=True, for_update=True)
    await exhibitions_service.ensure_writable(session, form.edition_id)
    used = DETAILS_OPTION_KINDS[DetailsType(form.details_type)] if form.details_type else ()
    if data.kind not in used:
        raise ValidationFailed(fields={"kind": "This form's questions do not use these choices."})
    values = list(dict.fromkeys(data.values))
    before = (await repo.form_options(session, form.id)).get(data.kind, [])
    await repo.delete_options(session, form.id, data.kind)
    session.add_all(
        OrderFormOption(
            edition_id=form.edition_id, form_id=form.id, kind=data.kind, value=v, sort_order=n
        )
        for n, v in enumerate(values)
    )
    await session.flush()
    await audit.record(
        session,
        entity_type=FORM_ENTITY,
        entity_id=form.id,
        action="set_options",
        before={"kind": data.kind, "values": before},
        after={"kind": data.kind, "values": values},
        edition_id=form.edition_id,
    )
    return _options_out(await repo.form_options(session, form.id))


# --- catalog items -----------------------------------------------------------------------


def _item_out(item: OrderFormItem) -> OrderFormItemOut:
    out = OrderFormItemOut.model_validate(item)
    out.has_image = item.image_key is not None
    return out


def _clean_item(values: dict[str, Any]) -> dict[str, Any]:
    out = {k: clean_text(v) if k in _ITEM_TEXT else v for k, v in values.items()}
    for key in ("code", "name", "price_regular", "is_active", "sort_order"):
        if key in out and out[key] is None:
            raise ValidationFailed(fields={key: "Required."})
    return out


async def _save_item(
    session: AsyncSession, item: OrderFormItem, before: dict[str, Any] | None, action: str
) -> None:
    await _flush(session, item)
    await session.refresh(item)
    await audit.record(
        session,
        entity_type=ITEM_ENTITY,
        entity_id=item.id,
        action=action,
        before=before,
        after=audit.snapshot(item, ITEM_AUDIT_FIELDS),
        edition_id=item.edition_id,
    )


async def list_items(
    session: AsyncSession, ctx: AuthContext, form_id: uuid.UUID, params: OrderFormItemListParams
) -> Page[OrderFormItemOut]:
    form = await _form_for(session, ctx, form_id, manage=False)
    items, total = await repo.list_items(session, form.id, params)
    return Page(
        items=[_item_out(i) for i in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def create_item(
    session: AsyncSession, ctx: AuthContext, form_id: uuid.UUID, data: OrderFormItemCreateIn
) -> OrderFormItemOut:
    form = await _form_for(session, ctx, form_id, manage=True)
    await exhibitions_service.ensure_writable(session, form.edition_id)
    values = data.model_dump()
    values["is_active"] = True if values["is_active"] is None else values["is_active"]
    values["sort_order"] = values["sort_order"] or 0
    actor = current_actor_id()
    item = OrderFormItem(
        edition_id=form.edition_id,
        form_id=form.id,
        created_by=actor,
        updated_by=actor,
        **_clean_item(values),
    )
    await _save_item(session, item, None, "create")
    return _item_out(item)


async def _check_still_publishable(session: AsyncSession, form: OrderForm) -> None:
    """Deactivating the last item would leave a published catalog form empty."""
    if form.is_published:
        _check_form(form, await repo.active_item_count(session, form.id))


async def update_item(
    session: AsyncSession,
    ctx: AuthContext,
    form_id: uuid.UUID,
    item_id: uuid.UUID,
    data: OrderFormItemUpdateIn,
) -> OrderFormItemOut:
    """Edit or deactivate an item. Sent orders keep the price they were sent with."""
    form, item = await _item_for(session, ctx, form_id, item_id, manage=True, for_update=True)
    check_version(item.version, data.version)
    await exhibitions_service.ensure_writable(session, form.edition_id)
    changes = _clean_item(data.model_dump(exclude_unset=True, exclude={"version"}))
    before = audit.snapshot(item, ITEM_AUDIT_FIELDS)
    for key, value in changes.items():
        setattr(item, key, value)
    item.updated_by = current_actor_id()
    await _save_item(session, item, before, "update")
    if changes.get("is_active") is False:
        await _check_still_publishable(session, form)
    return _item_out(item)


def _check_image(file_name: str, content_type: str | None, data: bytes) -> str:
    """Extension, MIME, magic bytes, size (BACKEND_RULES/security-permissions.md "Uploads")."""
    ext = PurePosixPath(file_name.lower()).suffix
    kind = _IMAGE_KINDS.get(ext)
    if kind is None or (content_type and content_type != kind[0]):
        raise ValidationFailed(fields={"file": "Only JPG and PNG files are accepted."})
    if len(data) > IMAGE_MAX_BYTES:
        raise ValidationFailed(fields={"file": "File is too large."}, code="FILE_TOO_LARGE")
    if not data.startswith(kind[1]):
        raise ValidationFailed(fields={"file": "File content does not match its type."})
    return ext


async def set_item_image(
    session: AsyncSession,
    ctx: AuthContext,
    form_id: uuid.UUID,
    item_id: uuid.UUID,
    *,
    file_name: str,
    content_type: str | None,
    data: bytes,
    version: int,
) -> OrderFormItemOut:
    """Upload or replace the picture shown next to the item in the portal."""
    form, item = await _item_for(session, ctx, form_id, item_id, manage=True, for_update=True)
    check_version(item.version, version)
    await exhibitions_service.ensure_writable(session, form.edition_id)
    ext = _check_image(file_name, content_type, data)
    key = new_object_key(ext)
    await run_in_threadpool(
        get_storage().put, get_settings().s3_bucket_orders, key, data, _IMAGE_KINDS[ext][0]
    )
    before = audit.snapshot(item, ITEM_AUDIT_FIELDS)
    item.image_key = key
    item.updated_by = current_actor_id()
    await _save_item(session, item, before, "set_image")
    return _item_out(item)


async def item_image(
    session: AsyncSession, ctx: AuthContext, form_id: uuid.UUID, item_id: uuid.UUID
) -> tuple[Iterator[bytes], str, str]:
    """(chunks, file name, media type) of the item picture."""
    _form, item = await _item_for(session, ctx, form_id, item_id, manage=False)
    if item.image_key is None:
        raise NotFound("This item has no picture.")
    ext = PurePosixPath(item.image_key).suffix
    chunks = await run_in_threadpool(
        get_storage().stream, get_settings().s3_bucket_orders, item.image_key
    )
    return chunks, f"item-{item.id}{ext}", _IMAGE_KINDS[ext][0]


# --- catalog import ----------------------------------------------------------------------


def import_template() -> bytes:
    example = [
        "A. Lighting & Equipment", "E-001", "Fluorescent lamp", "Lamp with fitting", "40 W",
        "unit", 740600, None, None, None, "yes", 10,
    ]  # fmt: skip
    return write_workbook([("Catalog", list(IMPORT_COLUMNS), [example])])


def _cell(value: Any, field: str) -> Any:
    """Spreadsheet value to the type the item schema expects; errors surface as row errors."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if field.startswith("price_"):
        try:
            return Decimal(str(value).replace(",", "").strip())
        except InvalidOperation:
            return str(value)
    if field in ("max_quantity", "sort_order") and isinstance(value, float):
        return int(value) if value.is_integer() else value
    if field == "is_active":
        text = str(value).strip().lower()
        return {"yes": True, "y": True, "true": True, "1": True, "no": False, "n": False,
                "false": False, "0": False}.get(text, text)  # fmt: skip
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value) if field in _ITEM_TEXT else value


def _parse_import(
    data: bytes,
) -> tuple[list[tuple[int, OrderFormItemCreateIn]], list[ItemImportRowError]]:
    rows = iter_rows(data)
    try:
        _, header = next(rows)
    except StopIteration as e:
        raise ValidationFailed(fields={"file": "The sheet is empty."}) from e
    columns: dict[int, str] = {}
    known = {name.lower(): field for name, field in IMPORT_COLUMNS.items()}
    for index, name in enumerate(header):
        field = known.get(str(name).strip().lower()) if name is not None else None
        if field is not None:
            columns[index] = field
    missing = [
        n for n in ("Code", "Name", "Price Regular") if IMPORT_COLUMNS[n] not in columns.values()
    ]
    if missing:
        raise ValidationFailed(fields={"file": f"Missing columns: {', '.join(missing)}."})
    parsed: list[tuple[int, OrderFormItemCreateIn]] = []
    errors: list[ItemImportRowError] = []
    seen: dict[str, int] = {}
    for number, values in rows:
        if all(v is None or (isinstance(v, str) and not v.strip()) for v in values):
            continue
        if len(parsed) + len(errors) >= IMPORT_MAX_ROWS:
            raise ValidationFailed(
                fields={"file": f"At most {IMPORT_MAX_ROWS} rows per import."}, code="TOO_MANY_ROWS"
            )
        raw = {
            field: _cell(values[i] if i < len(values) else None, field)
            for i, field in columns.items()
        }
        # A blank cell clears the field, except Active and Sort Order, which keep their value.
        raw = {k: v for k, v in raw.items() if v is not None or k not in _KEEP_WHEN_BLANK}
        try:
            row = OrderFormItemCreateIn.model_validate(raw)
        except ValidationError as e:
            errors.append(
                ItemImportRowError(
                    row=number,
                    errors={str(err["loc"][0]): err["msg"] for err in e.errors()},
                )
            )
            continue
        code = (clean_text(row.code) or "").upper()
        if code in seen:
            errors.append(
                ItemImportRowError(row=number, errors={"code": f"Same code as row {seen[code]}."})
            )
            continue
        seen[code] = number
        parsed.append((number, row))
    return parsed, errors


async def import_items(
    session: AsyncSession, ctx: AuthContext, form_id: uuid.UUID, *, data: bytes
) -> ItemImportOut:
    """Create or update catalog items by code from an Excel sheet; all rows or none.

    Small and synchronous (a catalog has hundreds of rows, not thousands), parsed in a
    threadpool. Items missing from the sheet are left as they are.
    """
    form = await _form_for(session, ctx, form_id, manage=True)
    await exhibitions_service.ensure_writable(session, form.edition_id)
    if len(data) > IMPORT_MAX_BYTES:
        raise ValidationFailed(fields={"file": "File is too large."}, code="FILE_TOO_LARGE")
    if not is_xlsx(data):
        raise ValidationFailed(fields={"file": "Only Excel (.xlsx) files are accepted."})
    try:
        parsed, errors = await run_in_threadpool(_parse_import, data)
    except ValidationFailed:
        raise
    except Exception as e:  # a corrupt workbook raises from deep inside openpyxl
        raise ValidationFailed(fields={"file": "The file could not be read."}) from e
    if errors:
        return ItemImportOut(created=0, updated=0, errors=errors)
    by_code = {item.code.upper(): item for item in await repo.form_items(session, form.id)}
    actor = current_actor_id()
    created = updated = 0
    for _number, row in parsed:
        values = _clean_item(row.model_dump(exclude_unset=True))
        existing = by_code.get(values["code"].upper())
        if existing is None:
            values.setdefault("is_active", True)
            values.setdefault("sort_order", 0)
            item = OrderFormItem(
                edition_id=form.edition_id,
                form_id=form.id,
                created_by=actor,
                updated_by=actor,
                **values,
            )
            await _save_item(session, item, None, "import")
            created += 1
            continue
        values.pop("code")  # matched case-insensitively; keep the stored spelling
        before = audit.snapshot(existing, ITEM_AUDIT_FIELDS)
        if all(getattr(existing, k) == v for k, v in values.items()):
            continue
        for key, value in values.items():
            setattr(existing, key, value)
        existing.updated_by = actor
        await _save_item(session, existing, before, "import")
        updated += 1
    await _check_still_publishable(session, form)
    return ItemImportOut(created=created, updated=updated, errors=[])
