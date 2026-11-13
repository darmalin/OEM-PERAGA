"""Quotations: settings per edition, numbering, preview, create, history, cancel
(docs/EXHIBITOR_QUOTATIONS.md, Phase 2)."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core import audit
from app.core.authorization import AuthContext, Scope
from app.core.config import get_settings as app_settings
from app.core.context import current_actor_id
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed, check_version
from app.core.storage import get_storage, new_object_key
from app.modules.exhibitions import service as exhibitions_service
from app.modules.exhibitions.models import Edition
from app.modules.exhibitors import repository as exhibitors_repo
from app.modules.exhibitors import service as exhibitors_service
from app.modules.exhibitors.models import ExhibitorLead
from app.modules.exhibitors.rules import SalesStage
from app.modules.identity.models import User
from app.modules.quotations import pdf
from app.modules.quotations.models import ExhibitorQuotation, QuotationCounter, QuotationSettings
from app.modules.quotations.rules import (
    DEFAULT_SHELL_INCLUDES,
    DEFAULT_TERMS,
    QuotationStatus,
    StandType,
    Term,
    compute,
    quotation_number,
)
from app.modules.quotations.schemas import (
    QuotationAcceptIn,
    QuotationCancelIn,
    QuotationIn,
    QuotationOut,
    QuotationPreviewOut,
    SettingsIn,
    SettingsOut,
    TermIn,
    TermOut,
)
from app.modules.visitors.rules import clean_text

READ = "exhibitor_lead.read"
WRITE = "exhibitor_lead.update"
SETTINGS = "booth.manage"  # rates are booth prices; the same people keep both
ENTITY = "exhibitor_quotation"
SETTINGS_ENTITY = "quotation_settings"
AUDIT_FIELDS = ("number", "status", "total_amount", "currency", "replaces_id", "cancel_reason")
SETTINGS_AUDIT_FIELDS = (
    "code", "company_code", "start_number", "place", "letter_name", "event_text", "rates",
    "shell_includes", "discount_label", "vat_rate", "vat_base_num", "vat_base_den", "terms",
    "signer_name", "signer_title",
)  # fmt: skip


# --- settings ----------------------------------------------------------------------------


def _scope(ctx: AuthContext, edition_id: uuid.UUID, permission: str) -> Scope:
    return ctx.scope_for(edition_id, permission)


async def _settings_row(
    session: AsyncSession, edition_id: uuid.UUID, *, for_update: bool = False
) -> QuotationSettings | None:
    stmt = select(QuotationSettings).where(QuotationSettings.edition_id == edition_id)
    if for_update:
        stmt = stmt.with_for_update()
    return await session.scalar(stmt)


def _default_terms() -> list[dict[str, Any]]:
    return [dict(t) for t in DEFAULT_TERMS]


async def _next_number(session: AsyncSession, code: str, year: int, start: int) -> int:
    last = await session.scalar(
        select(QuotationCounter.last_value).where(
            QuotationCounter.code == code, QuotationCounter.year == year
        )
    )
    return max((last or 0) + 1, start)


async def _settings_out(
    session: AsyncSession, edition: Edition, row: QuotationSettings | None
) -> SettingsOut:
    if row is None:
        return SettingsOut(
            exists=False,
            edition_id=edition.id,
            code=None,
            company_code="PNJS",
            start_number=1,
            place="Jakarta",
            letter_name=edition.name,
            event_text=None,
            rates=[],
            shell_includes=DEFAULT_SHELL_INCLUDES,
            discount_label="Special Discount",
            vat_rate=Decimal(12),
            vat_base_num=11,
            vat_base_den=12,
            terms=[TermIn.model_validate(t) for t in _default_terms()],
            signer_name=None,
            signer_title=None,
        )
    out = SettingsOut.model_validate(row)
    out.has_signature = row.signature_key is not None
    today = _today(edition)
    out.next_number = await _next_number(session, row.code, today.year, row.start_number)
    return out


async def get_settings(
    session: AsyncSession, ctx: AuthContext, edition_id: uuid.UUID
) -> SettingsOut:
    """Readable by everyone who sees the edition's exhibitor leads: the form starts from it."""
    _scope(ctx, edition_id, READ)
    edition = await exhibitions_service.get_edition_by_id(session, edition_id)
    if edition is None:
        raise NotFound("Edition not found.", code="EDITION_NOT_FOUND")
    return await _settings_out(session, edition, await _settings_row(session, edition_id))


def _require_settings_manager(ctx: AuthContext, edition_id: uuid.UUID) -> None:
    try:
        if not _scope(ctx, edition_id, SETTINGS).full_access:
            raise PermissionDenied()
    except NotFound as e:
        _scope(ctx, edition_id, READ)  # 404 for an edition the caller cannot see at all
        raise PermissionDenied() from e


def _jsonable_terms(terms: list[TermIn]) -> list[dict[str, Any]]:
    return [
        {
            "label": t.label.strip(),
            "percent": str(t.percent),
            "due_on": t.due_on and t.due_on.isoformat(),
        }
        for t in terms
    ]


async def save_settings(
    session: AsyncSession, ctx: AuthContext, edition_id: uuid.UUID, data: SettingsIn
) -> SettingsOut:
    _require_settings_manager(ctx, edition_id)
    edition = await exhibitions_service.ensure_writable(session, edition_id)
    row = await _settings_row(session, edition_id, for_update=True)
    values: dict[str, Any] = {
        "code": data.code.upper(),
        "company_code": data.company_code.upper(),
        "start_number": data.start_number,
        "place": data.place.strip(),
        "letter_name": clean_text(data.letter_name),
        "event_text": clean_text(data.event_text),
        "rates": [
            {"currency": r.currency, "stand_type": str(r.stand_type), "rate": str(r.rate)}
            for r in data.rates
        ],
        "shell_includes": clean_text(data.shell_includes),
        "discount_label": data.discount_label.strip(),
        "vat_rate": data.vat_rate,
        "vat_base_num": data.vat_base_num,
        "vat_base_den": data.vat_base_den,
        "terms": _jsonable_terms(data.terms),
        "signer_name": clean_text(data.signer_name),
        "signer_title": clean_text(data.signer_title),
    }
    actor = current_actor_id()
    before = None
    if row is None:
        if data.version is not None:
            raise Conflict("The settings were removed meanwhile.", code="VERSION_CONFLICT")
        row = QuotationSettings(edition_id=edition_id, created_by=actor, updated_by=actor, **values)
        session.add(row)
    else:
        check_version(row.version, data.version if data.version is not None else -1)
        before = audit.snapshot(row, SETTINGS_AUDIT_FIELDS)
        for key, value in values.items():
            setattr(row, key, value)
        row.updated_by = actor
    await session.flush()
    await session.refresh(row)
    await audit.record(
        session,
        entity_type=SETTINGS_ENTITY,
        entity_id=row.id,
        action="create" if before is None else "update",
        before=before,
        after=audit.snapshot(row, SETTINGS_AUDIT_FIELDS),
        edition_id=edition_id,
    )
    return await _settings_out(session, edition, row)


# --- quotations --------------------------------------------------------------------------


def _today(edition: Edition) -> date:
    return datetime.now(ZoneInfo(edition.timezone)).date()


async def _lead(
    session: AsyncSession,
    ctx: AuthContext,
    lead_id: uuid.UUID,
    permission: str,
    *,
    for_update: bool = False,
) -> ExhibitorLead:
    edition_id = await exhibitors_repo.edition_of(session, lead_id)
    if edition_id is None:
        raise NotFound("Exhibitor lead not found.")
    try:
        scope = _scope(ctx, edition_id, permission)
    except NotFound as e:
        raise NotFound("Exhibitor lead not found.") from e
    lead = await exhibitors_repo.get_lead(session, scope, lead_id, for_update=for_update)
    if lead is None:
        raise NotFound("Exhibitor lead not found.")
    return lead


def _rate(settings: QuotationSettings, currency: str, stand_type: StandType) -> Decimal | None:
    for r in settings.rates:
        if r["currency"] == currency and r["stand_type"] == stand_type:
            return Decimal(r["rate"])
    return None


async def _build(
    session: AsyncSession, lead: ExhibitorLead, data: QuotationIn
) -> tuple[dict[str, Any], QuotationSettings, Edition]:
    """Every value of the quotation, filled from the input, the settings, and the lead."""
    edition = await exhibitions_service.get_edition_by_id(session, lead.edition_id)
    assert edition is not None  # noqa: S101 - FK
    settings = await _settings_row(session, lead.edition_id)
    if settings is None:
        raise ValidationFailed(
            "Set up the quotation settings of this edition first.",
            code="QUOTATION_SETTINGS_MISSING",
        )
    currency = data.currency or edition.default_currency
    errors: dict[str, str] = {}

    booth_code = clean_text(data.booth_code)
    area = data.area_sqm
    if data.booth_id is not None:
        booth = await exhibitors_repo.get_booth(session, data.booth_id)
        if booth is None or booth.edition_id != lead.edition_id:
            raise NotFound("Booth not found.")
        booth_code = booth.code
        if area is None and (data.width_m is None or data.length_m is None):
            area = booth.area_sqm
    elif area is None and (data.width_m is None or data.length_m is None):
        errors["area_sqm"] = "Enter the width and length, or the area."

    stand_rate = data.stand_rate
    if stand_rate is None:
        stand_rate = _rate(settings, currency, data.stand_type)
    if stand_rate is None:
        errors["stand_rate"] = f"No {data.stand_type.lower()} rate in {currency} in the settings."
    raw_rate = data.raw_rate
    if raw_rate is None:
        raw_rate = (
            stand_rate
            if data.stand_type == StandType.RAW
            else _rate(settings, currency, StandType.RAW)
        )
    if raw_rate is None and data.discount_percent > 0:
        errors["raw_rate"] = f"No raw space rate in {currency} for the discount."
    if errors:
        raise ValidationFailed(fields=errors)
    assert stand_rate is not None  # noqa: S101 - checked above

    vat_on = data.vat if data.vat is not None else currency == "IDR"
    vat_rate = settings.vat_rate if vat_on else Decimal(0)
    term_rows = (
        _jsonable_terms(data.terms)
        if data.terms is not None
        else (
            settings.terms
            or [
                {"label": t["label"], "percent": str(t["percent"]), "due_on": None}
                for t in DEFAULT_TERMS
            ]
        )
    )
    terms = [
        Term(
            t["label"],
            Decimal(str(t["percent"])),
            date.fromisoformat(t["due_on"]) if t["due_on"] else None,
        )
        for t in term_rows
    ]
    amounts = compute(
        width_m=data.width_m,
        length_m=data.length_m,
        area_sqm=area,
        complimentary_sqm=data.complimentary_sqm,
        stand_rate=stand_rate,
        raw_rate=raw_rate or Decimal(0),
        discount_percent=data.discount_percent,
        vat_rate=vat_rate,
        vat_base_num=settings.vat_base_num,
        vat_base_den=settings.vat_base_den,
        terms=terms,
    )
    if amounts.charged_sqm <= 0 or data.complimentary_sqm >= amounts.area_sqm:
        raise ValidationFailed(
            fields={"complimentary_sqm": "The complimentary space must be less than the total."}
        )

    contract = await exhibitors_repo.get_contract(session, lead.id)
    includes = data.includes
    if includes is None and data.stand_type == StandType.SHELL:
        includes = settings.shell_includes or DEFAULT_SHELL_INCLUDES
    values: dict[str, Any] = {
        "issued_on": data.issued_on or _today(edition),
        "recipient_company": clean_text(data.recipient_company) or lead.company_name,
        "recipient_address": clean_text(data.recipient_address)
        or (contract.company_address if contract else None),
        "attention": clean_text(data.attention) or lead.contact_name,
        "stand_type": str(data.stand_type),
        "currency": currency,
        "booth_id": data.booth_id,
        "booth_code": booth_code,
        "width_m": data.width_m,
        "length_m": data.length_m,
        "area_sqm": amounts.area_sqm,
        "complimentary_sqm": data.complimentary_sqm,
        "charged_sqm": amounts.charged_sqm,
        "stand_rate": stand_rate,
        "raw_rate": raw_rate or Decimal(0),
        "discount_label": (clean_text(data.discount_label) or settings.discount_label)
        if data.discount_percent > 0
        else None,
        "discount_percent": data.discount_percent,
        "vat_rate": vat_rate,
        "vat_base_num": settings.vat_base_num,
        "vat_base_den": settings.vat_base_den,
        "gross_amount": amounts.gross_amount,
        "discount_amount": amounts.discount_amount,
        "cost_amount": amounts.cost_amount,
        "vat_amount": amounts.vat_amount,
        "total_amount": amounts.total_amount,
        "terms": [
            t | {"amount": str(a)} for t, a in zip(term_rows, amounts.term_amounts, strict=True)
        ],
        "includes": clean_text(includes),
        "notes": clean_text(data.notes),
    }
    return values, settings, edition


def _preview(values: dict[str, Any], number: str) -> QuotationPreviewOut:
    return QuotationPreviewOut(
        number=number,
        **{
            k: v
            for k, v in values.items()
            if k in QuotationPreviewOut.model_fields and k != "terms"
        },
        terms=[TermOut.model_validate(t) for t in values["terms"]],
    )


def _check_stage(lead: ExhibitorLead) -> None:
    if lead.stage == SalesStage.LOST:
        raise ValidationFailed("Reopen the lead before making a quotation.", code="LEAD_LOST")


async def preview(
    session: AsyncSession, ctx: AuthContext, lead_id: uuid.UUID, data: QuotationIn
) -> QuotationPreviewOut:
    """The summary before Create. Nothing is saved and no number is taken."""
    lead = await _lead(session, ctx, lead_id, WRITE)
    _check_stage(lead)
    values, settings, _edition = await _build(session, lead, data)
    issued_on: date = values["issued_on"]
    seq = await _next_number(session, settings.code, issued_on.year, settings.start_number)
    return _preview(values, quotation_number(seq, settings.company_code, settings.code, issued_on))


async def _allocate(session: AsyncSession, code: str, year: int, start: int) -> int:
    """Next running number for (code, year), never below the starting number. The upsert holds
    the counter row until commit, so two quotations never get the same number."""
    stmt = (
        insert(QuotationCounter)
        .values(code=code, year=year, last_value=start)
        .on_conflict_do_update(
            index_elements=[QuotationCounter.code, QuotationCounter.year],
            set_={"last_value": func.greatest(QuotationCounter.last_value + 1, start)},
        )
        .returning(QuotationCounter.last_value)
    )
    return int((await session.execute(stmt)).scalar_one())


async def _record(
    session: AsyncSession, q: ExhibitorQuotation, action: str, before: dict[str, Any] | None
) -> None:
    await audit.record(
        session,
        entity_type=ENTITY,
        entity_id=q.id,
        action=action,
        before=before,
        after=audit.snapshot(q, AUDIT_FIELDS) | {"exhibitor_lead_id": q.exhibitor_lead_id},
        edition_id=q.edition_id,
    )


async def create(
    session: AsyncSession, ctx: AuthContext, lead_id: uuid.UUID, data: QuotationIn
) -> QuotationOut:
    lead = await _lead(session, ctx, lead_id, WRITE, for_update=True)
    _check_stage(lead)
    await exhibitions_service.ensure_writable(session, lead.edition_id)
    values, settings, _edition = await _build(session, lead, data)
    replaced: ExhibitorQuotation | None = None
    if data.replaces_id is not None:
        replaced = await _quotation_row(session, data.replaces_id, for_update=True)
        if replaced is None or replaced.exhibitor_lead_id != lead.id:
            raise NotFound("Quotation not found.")
        if replaced.status != QuotationStatus.ISSUED:
            raise Conflict("Only an issued quotation can be revised.", code="QUOTATION_NOT_ISSUED")
    issued_on: date = values["issued_on"]
    seq = await _allocate(session, settings.code, issued_on.year, settings.start_number)
    actor = current_actor_id()
    q = ExhibitorQuotation(
        edition_id=lead.edition_id,
        exhibitor_lead_id=lead.id,
        number=quotation_number(seq, settings.company_code, settings.code, issued_on),
        status=QuotationStatus.ISSUED,
        replaces_id=data.replaces_id,
        letter={
            "company_code": settings.company_code,
            "place": settings.place,
            "letter_name": settings.letter_name,
            "event_text": settings.event_text,
            "signer_name": settings.signer_name,
            "signer_title": settings.signer_title,
            "signature_key": settings.signature_key,
        },
        created_by=actor,
        updated_by=actor,
        **values,
    )
    session.add(q)
    await session.flush()
    if replaced is not None:
        before = audit.snapshot(replaced, AUDIT_FIELDS)
        replaced.status = QuotationStatus.SUPERSEDED
        replaced.updated_by = actor
        await session.flush()
        await _record(session, replaced, "supersede", before)
    await session.refresh(q)
    await _record(session, q, "create", None)
    return await _out(session, q)


async def _quotation_row(
    session: AsyncSession, quotation_id: uuid.UUID, *, for_update: bool = False
) -> ExhibitorQuotation | None:
    stmt = select(ExhibitorQuotation).where(ExhibitorQuotation.id == quotation_id)
    if for_update:
        stmt = stmt.with_for_update()
    return await session.scalar(stmt)


async def _out(session: AsyncSession, q: ExhibitorQuotation) -> QuotationOut:
    out = QuotationOut.model_validate(
        {
            **{
                k: getattr(q, k)
                for k in QuotationOut.model_fields
                if hasattr(q, k) and k != "terms"
            },
            "terms": [TermOut.model_validate(t) for t in q.terms],
        }
    )
    out.created_by_name = (
        await session.scalar(select(User.full_name).where(User.id == q.created_by))
        if q.created_by
        else None
    )
    out.replaced_by_number = await session.scalar(
        select(ExhibitorQuotation.number).where(ExhibitorQuotation.replaces_id == q.id)
    )
    return out


async def list_for_lead(
    session: AsyncSession, ctx: AuthContext, lead_id: uuid.UUID
) -> list[QuotationOut]:
    """Every quotation of the lead, newest first: the history."""
    lead = await _lead(session, ctx, lead_id, READ)
    rows = await session.scalars(
        select(ExhibitorQuotation)
        .where(ExhibitorQuotation.exhibitor_lead_id == lead.id)
        .order_by(ExhibitorQuotation.created_at.desc(), ExhibitorQuotation.id.desc())
    )
    return [await _out(session, q) for q in rows]


async def _visible(
    session: AsyncSession,
    ctx: AuthContext,
    quotation_id: uuid.UUID,
    permission: str,
    *,
    for_update: bool = False,
) -> ExhibitorQuotation:
    q = await _quotation_row(session, quotation_id, for_update=for_update)
    if q is None:
        raise NotFound("Quotation not found.")
    try:
        await _lead(session, ctx, q.exhibitor_lead_id, permission)
    except NotFound as e:
        raise NotFound("Quotation not found.") from e
    return q


async def get(session: AsyncSession, ctx: AuthContext, quotation_id: uuid.UUID) -> QuotationOut:
    return await _out(session, await _visible(session, ctx, quotation_id, READ))


async def cancel(
    session: AsyncSession, ctx: AuthContext, quotation_id: uuid.UUID, data: QuotationCancelIn
) -> QuotationOut:
    """Withdraw an issued quotation; it stays in the history with the reason."""
    q = await _visible(session, ctx, quotation_id, WRITE, for_update=True)
    check_version(q.version, data.version)
    await exhibitions_service.ensure_writable(session, q.edition_id)
    if q.status != QuotationStatus.ISSUED:
        raise Conflict("Only an issued quotation can be cancelled.", code="QUOTATION_NOT_ISSUED")
    before = audit.snapshot(q, AUDIT_FIELDS)
    q.status = QuotationStatus.CANCELLED
    q.cancelled_at = datetime.now(UTC)
    q.cancel_reason = data.reason.strip()
    q.updated_by = current_actor_id()
    await session.flush()
    await session.refresh(q)
    await _record(session, q, "cancel", before)
    return await _out(session, q)


async def accept(
    session: AsyncSession, ctx: AuthContext, quotation_id: uuid.UUID, data: QuotationAcceptIn
) -> QuotationOut:
    """The company agreed. The lead takes the quotation's booth and price; the contract (now, if
    Draft, or at Convert) takes its price, discount, VAT, and terms. One accepted per lead."""
    q = await _visible(session, ctx, quotation_id, WRITE, for_update=True)
    check_version(q.version, data.version)
    await exhibitions_service.ensure_writable(session, q.edition_id)
    if q.status != QuotationStatus.ISSUED:
        raise Conflict("Only an issued quotation can be accepted.", code="QUOTATION_NOT_ISSUED")
    lead = await _lead(session, ctx, q.exhibitor_lead_id, WRITE, for_update=True)
    _check_stage(lead)
    previous = await exhibitors_service.accepted_quotation(session, lead.id)
    actor = current_actor_id()
    if previous is not None:
        before = audit.snapshot(previous, AUDIT_FIELDS)
        previous.status = QuotationStatus.SUPERSEDED
        previous.updated_by = actor
        await session.flush()
        await _record(session, previous, "supersede", before)
    before = audit.snapshot(q, AUDIT_FIELDS)
    q.status = QuotationStatus.ACCEPTED
    q.accepted_at = datetime.now(UTC)
    q.updated_by = actor
    await session.flush()
    await exhibitors_service.apply_accepted_quotation(session, lead, q)
    await session.refresh(q)
    await _record(session, q, "accept", before)
    return await _out(session, q)


# --- signature and PDF (Phase 3) ---------------------------------------------------------

_IMAGES = {"image/png": b"\x89PNG\r\n\x1a\n", "image/jpeg": b"\xff\xd8\xff"}
SIGNATURE_MAX_BYTES = 2 * 1024 * 1024


async def set_signature(
    session: AsyncSession,
    ctx: AuthContext,
    edition_id: uuid.UUID,
    *,
    content_type: str | None,
    data: bytes,
    version: int,
) -> SettingsOut:
    """The signer's signature, a PNG or JPEG. New quotations print it; made ones keep theirs."""
    _require_settings_manager(ctx, edition_id)
    edition = await exhibitions_service.ensure_writable(session, edition_id)
    row = await _settings_row(session, edition_id, for_update=True)
    if row is None:
        raise ValidationFailed("Save the settings first.", code="QUOTATION_SETTINGS_MISSING")
    check_version(row.version, version)
    magic = _IMAGES.get(content_type or "")
    if magic is None or not data.startswith(magic):
        raise ValidationFailed(fields={"file": "Only PNG or JPEG images are accepted."})
    if len(data) > SIGNATURE_MAX_BYTES:
        raise ValidationFailed(fields={"file": "File is too large."}, code="FILE_TOO_LARGE")
    if not pdf.readable_image(data):
        raise ValidationFailed(fields={"file": "The image cannot be read."})
    key = new_object_key(".png" if content_type == "image/png" else ".jpg")
    assert content_type is not None  # noqa: S101 - checked above
    await run_in_threadpool(
        get_storage().put, app_settings().s3_bucket_quotations, key, data, content_type
    )
    # The old image stays: quotations made with it still point at it.
    row.signature_key = key
    row.updated_by = current_actor_id()
    await session.flush()
    await session.refresh(row)
    await audit.record(
        session,
        entity_type=SETTINGS_ENTITY,
        entity_id=row.id,
        action="signature",
        after={"signature_key": key},
        edition_id=edition_id,
    )
    return await _settings_out(session, edition, row)


async def _image(key: str | None) -> bytes | None:
    if key is None:
        return None
    try:
        return await run_in_threadpool(get_storage().get, app_settings().s3_bucket_quotations, key)
    except FileNotFoundError:
        return None


async def signature(session: AsyncSession, ctx: AuthContext, edition_id: uuid.UUID) -> bytes:
    _scope(ctx, edition_id, READ)
    row = await _settings_row(session, edition_id)
    data = await _image(row.signature_key if row else None)
    if data is None:
        raise NotFound("No signature image.")
    return data


async def quotation_pdf(
    session: AsyncSession, ctx: AuthContext, quotation_id: uuid.UUID
) -> tuple[bytes, str]:
    """(PDF bytes, download name). Rendered from what the quotation stored, so it never changes."""
    q = await _visible(session, ctx, quotation_id, READ)
    edition = await exhibitions_service.get_edition_by_id(session, q.edition_id)
    assert edition is not None  # noqa: S101 - FK
    sign = await _image((q.letter or {}).get("signature_key"))
    data = await run_in_threadpool(pdf.render, q, edition.name, sign)
    name = "Quotation " + q.number.replace("/", "-") + ".pdf"
    return data, name
