import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.authorization import AuthContext, Scope
from app.core.config import get_settings
from app.core.context import current_actor_id
from app.core.crypto import new_token, sha256_hex
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed, check_version
from app.core.pagination import Page
from app.modules.audit import service as audit_service
from app.modules.audit.schemas import AuditLogOut
from app.modules.exhibitions import service as exhibitions_service
from app.modules.exhibitors import repository as repo
from app.modules.exhibitors.models import (
    Booth,
    ExhibitorAccount,
    ExhibitorContract,
    ExhibitorLead,
)
from app.modules.exhibitors.rules import BOOTH_STAGES, ContractStatus, SalesStage, can_move
from app.modules.exhibitors.schemas import (
    BoothAssignIn,
    BoothCreateIn,
    BoothListParams,
    BoothOut,
    BoothUpdateIn,
    ConvertIn,
    ConvertOut,
    ExhibitorLeadCreateIn,
    ExhibitorLeadListParams,
    ExhibitorLeadOut,
    ExhibitorLeadUpdateIn,
    InvitationOut,
    StageChangeIn,
)
from app.modules.visitors.rules import (
    NormalizationError,
    clean_text,
    normalize_email,
    normalize_phone,
)

ENTITY = "exhibitor_lead"
AUDIT_FIELDS = (
    "company_name", "contact_name", "email", "phone", "product_categories", "booth_preference",
    "budget_estimate", "notes", "stage", "lost_reason", "booth_id", "lead_owner_id",
)  # fmt: skip
_TEXT_FIELDS = (
    "company_name", "contact_name", "product_categories", "booth_preference", "notes",
)  # fmt: skip
_REQUIRED = ("company_name", "contact_name", "email")


class BoothTaken(Conflict):
    code = "BOOTH_TAKEN"
    default_message = "This booth is already held by another exhibitor lead."


class DuplicateExhibitorLead(Conflict):
    code = "DUPLICATE_EXHIBITOR_LEAD"
    default_message = "Email already used by another exhibitor lead in this edition."


def _normalize(values: dict[str, Any]) -> dict[str, Any]:
    """Trim text, empty to NULL (spec 5.2), normalize email and phone."""
    out: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for key, value in values.items():
        if key in _TEXT_FIELDS:
            out[key] = clean_text(value)
        elif key == "email":
            try:
                normalized = normalize_email(value)
            except NormalizationError as e:
                errors["email"] = str(e)
                continue
            out["email"] = clean_text(value)
            out["email_normalized"] = normalized
        elif key == "phone":
            try:
                out["phone_normalized"] = normalize_phone(value, None)
            except NormalizationError as e:
                errors["phone"] = str(e)
                continue
            out["phone"] = clean_text(value)
        else:
            out[key] = value
    for key in _REQUIRED:
        if key in out and out[key] is None and key not in errors:
            errors[key] = "Required."
    if errors:
        raise ValidationFailed(fields=errors)
    return out


def _integrity_error(e: IntegrityError) -> Exception:
    msg = str(e.orig)
    if "uq_exhibitor_leads_edition_email" in msg:
        return DuplicateExhibitorLead(fields={"email": "Already used in this edition."})
    if "uq_exhibitor_leads_booth" in msg:
        return BoothTaken()
    if "uq_booths_edition_id_code" in msg:
        return Conflict(
            "Booth code already used in this edition.",
            code="DUPLICATE_BOOTH_CODE",
            fields={"code": "Already used in this edition."},
        )
    if "fk_exhibitor_leads_lead_owner_id_users" in msg:
        return ValidationFailed(fields={"lead_owner_id": "Unknown user."})
    return e


async def _flush(session: AsyncSession, row: ExhibitorLead | Booth) -> None:
    try:
        async with session.begin_nested():
            session.add(row)
            await session.flush()
    except IntegrityError as e:
        raise _integrity_error(e) from e
    await session.refresh(row)


async def _raise_if_duplicate(
    session: AsyncSession, edition_id: uuid.UUID, email_n: str, exclude_id: uuid.UUID | None
) -> None:
    if await repo.email_taken(session, edition_id, email_n, exclude_id):
        raise DuplicateExhibitorLead(fields={"email": "Already used in this edition."})


async def _out(session: AsyncSession, lead: ExhibitorLead) -> ExhibitorLeadOut:
    out = ExhibitorLeadOut.model_validate(lead)
    out.lead_owner_name = await repo.owner_name(session, lead.lead_owner_id)
    out.booth_code = await repo.booth_code(session, lead.booth_id)
    return out


async def _scope_for_lead(session: AsyncSession, ctx: AuthContext, lead_id: uuid.UUID) -> Scope:
    edition_id = await repo.edition_of(session, lead_id)
    if edition_id is None:
        raise NotFound("Exhibitor lead not found.")
    try:
        return ctx.scope_for(edition_id)
    except NotFound as e:
        raise NotFound("Exhibitor lead not found.") from e


async def _get(
    session: AsyncSession, scope: Scope, lead_id: uuid.UUID, *, for_update: bool = False
) -> ExhibitorLead:
    lead = await repo.get_lead(session, scope, lead_id, for_update=for_update)
    if lead is None:
        raise NotFound("Exhibitor lead not found.")
    return lead


async def _save(
    session: AsyncSession, lead: ExhibitorLead, changes: dict[str, Any], action: str
) -> ExhibitorLead:
    before = audit.snapshot(lead, AUDIT_FIELDS)
    for key, value in changes.items():
        setattr(lead, key, value)
    lead.updated_by = current_actor_id()
    await _flush(session, lead)
    await audit.record(
        session,
        entity_type=ENTITY,
        entity_id=lead.id,
        action=action,
        before=before,
        after=audit.snapshot(lead, AUDIT_FIELDS),
        edition_id=lead.edition_id,
    )
    return lead


async def create_lead(
    session: AsyncSession, ctx: AuthContext, data: ExhibitorLeadCreateIn
) -> ExhibitorLeadOut:
    """Create an exhibitor lead in stage LEAD; callers without edition-wide access own it."""
    scope = ctx.scope_for(data.edition_id)
    await exhibitions_service.ensure_writable(session, data.edition_id)
    values = _normalize(data.model_dump(exclude={"edition_id"}))
    if not scope.full_access:
        # Otherwise the creator could not see the lead they just made.
        if values["lead_owner_id"] not in (None, ctx.user.id):
            raise PermissionDenied("Only edition-wide access may assign another owner.")
        values["lead_owner_id"] = ctx.user.id
    await _raise_if_duplicate(session, data.edition_id, values["email_normalized"], None)
    actor = current_actor_id()
    lead = ExhibitorLead(
        edition_id=data.edition_id,
        stage=SalesStage.LEAD,
        created_by=actor,
        updated_by=actor,
        **values,
    )
    await _flush(session, lead)
    await audit.record(
        session,
        entity_type=ENTITY,
        entity_id=lead.id,
        action="create",
        after=audit.snapshot(lead, AUDIT_FIELDS),
        edition_id=lead.edition_id,
    )
    return await _out(session, lead)


async def list_leads(
    session: AsyncSession, ctx: AuthContext, params: ExhibitorLeadListParams
) -> Page[ExhibitorLeadOut]:
    """Exhibitor leads of one edition inside the caller's scope, filtered and paginated."""
    scope = ctx.scope_for(params.edition_id)
    rows, total = await repo.list_leads(session, scope, params)
    items = []
    for lead, owner, booth_code in rows:
        item = ExhibitorLeadOut.model_validate(lead)
        item.lead_owner_name = owner
        item.booth_code = booth_code
        items.append(item)
    return Page(items=items, total=total, page=params.page, page_size=params.page_size)


async def get_lead(session: AsyncSession, ctx: AuthContext, lead_id: uuid.UUID) -> ExhibitorLeadOut:
    """One exhibitor lead inside the caller's scope."""
    scope = await _scope_for_lead(session, ctx, lead_id)
    return await _out(session, await _get(session, scope, lead_id))


async def update_lead(
    session: AsyncSession, ctx: AuthContext, lead_id: uuid.UUID, data: ExhibitorLeadUpdateIn
) -> ExhibitorLeadOut:
    """Edit lead fields (not the stage) with optimistic locking."""
    scope = await _scope_for_lead(session, ctx, lead_id)
    lead = await _get(session, scope, lead_id, for_update=True)
    check_version(lead.version, data.version)
    await exhibitions_service.ensure_writable(session, lead.edition_id)
    changes = _normalize(data.model_dump(exclude_unset=True, exclude={"version"}))
    if (
        "lead_owner_id" in changes
        and changes["lead_owner_id"] != lead.lead_owner_id
        and not scope.full_access
    ):
        raise PermissionDenied("Only edition-wide access may change the owner.")
    if "email_normalized" in changes:
        await _raise_if_duplicate(session, lead.edition_id, changes["email_normalized"], lead.id)
    return await _out(session, await _save(session, lead, changes, "update"))


def _stage_changes(lead: ExhibitorLead, data: StageChangeIn) -> dict[str, Any]:
    target = SalesStage(data.stage)
    if not can_move(SalesStage(lead.stage), target):
        raise ValidationFailed(
            f"Cannot move from {lead.stage} to {target}.", code="INVALID_STAGE_TRANSITION"
        )
    changes: dict[str, Any] = {"stage": target, "lost_reason": None}
    if target is SalesStage.OPPORTUNITY:
        changes["qualified_at"] = lead.qualified_at or datetime.now(UTC)
    else:
        # A booth is held only by an opportunity; leaving that stage releases it.
        changes |= {"booth_id": None, "booth_assigned_at": None}
    if target is SalesStage.LOST:
        reason = clean_text(data.lost_reason)
        if reason is None:
            raise ValidationFailed(fields={"lost_reason": "Required when the lead is lost."})
        changes["lost_reason"] = reason
    return changes


async def change_stage(
    session: AsyncSession, ctx: AuthContext, lead_id: uuid.UUID, data: StageChangeIn
) -> ExhibitorLeadOut:
    """Move a lead between LEAD, OPPORTUNITY and LOST (rules.STAGE_TRANSITIONS)."""
    scope = await _scope_for_lead(session, ctx, lead_id)
    lead = await _get(session, scope, lead_id, for_update=True)
    check_version(lead.version, data.version)
    await exhibitions_service.ensure_writable(session, lead.edition_id)
    lead = await _save(session, lead, _stage_changes(lead, data), "stage_change")
    return await _out(session, lead)


async def activity(
    session: AsyncSession, ctx: AuthContext, lead_id: uuid.UUID
) -> list[AuditLogOut]:
    """Audit timeline of a lead, for anyone who can read the lead."""
    scope = await _scope_for_lead(session, ctx, lead_id)
    lead = await _get(session, scope, lead_id)
    return await audit_service.entity_timeline(session, lead.edition_id, ENTITY, lead.id)


async def assign_booth(
    session: AsyncSession, ctx: AuthContext, lead_id: uuid.UUID, data: BoothAssignIn
) -> ExhibitorLeadOut:
    """Assign, move, or release the booth of an opportunity (or of an exhibitor, moves only)."""
    scope = await _scope_for_lead(session, ctx, lead_id)
    lead = await _get(session, scope, lead_id, for_update=True)
    check_version(lead.version, data.version)
    await exhibitions_service.ensure_writable(session, lead.edition_id)
    if data.booth_id == lead.booth_id:
        return await _out(session, lead)
    if SalesStage(lead.stage) not in BOOTH_STAGES:
        raise ValidationFailed(
            "Only an opportunity can hold a booth.", code="BOOTH_NEEDS_OPPORTUNITY"
        )
    if data.booth_id is None and lead.stage == SalesStage.EXHIBITOR:
        raise ValidationFailed("An exhibitor keeps a booth; move it instead.")
    contract = await repo.get_contract(session, lead.id, for_update=True)
    if contract is not None and contract.status == ContractStatus.SIGNED:
        raise Conflict("The contract is signed; the booth cannot change.", code="CONTRACT_SIGNED")
    booth: Booth | None = None
    if data.booth_id is not None:
        # Locking the booth row makes two assignments of one booth wait for each other.
        booth = await repo.get_booth(session, data.booth_id, for_update=True)
        if booth is None or booth.edition_id != lead.edition_id:
            raise NotFound("Booth not found.")
        if not booth.is_active:
            raise ValidationFailed("This booth is inactive.", code="BOOTH_INACTIVE")
        holder = await repo.booth_holder(session, booth.id)
        if holder is not None and holder[0] != lead.id:
            raise BoothTaken()
    changes = {
        "booth_id": data.booth_id,
        "booth_assigned_at": datetime.now(UTC) if data.booth_id else None,
    }
    lead = await _save(session, lead, changes, "booth_change")
    if contract is not None and booth is not None:
        await _reprice_contract(session, contract, booth)
    return await _out(session, lead)


async def _reprice_contract(
    session: AsyncSession, contract: ExhibitorContract, booth: Booth
) -> None:
    """A DRAFT contract follows its exhibitor's booth; the discount is kept where it fits."""
    before = audit.snapshot(contract, CONTRACT_AUDIT_FIELDS)
    contract.booth_price = booth.price
    contract.discount_amount = min(contract.discount_amount, booth.price)
    contract.total_amount = booth.price - contract.discount_amount
    contract.currency = booth.currency
    contract.updated_by = current_actor_id()
    await session.flush()
    await audit.record(
        session,
        entity_type=CONTRACT_ENTITY,
        entity_id=contract.id,
        action="reprice",
        before=before,
        after=audit.snapshot(contract, CONTRACT_AUDIT_FIELDS),
        edition_id=contract.edition_id,
    )


# --- booths ------------------------------------------------------------------------------

BOOTH_ENTITY = "booth"
BOOTH_AUDIT_FIELDS = ("code", "hall", "area_sqm", "price", "currency", "is_active", "notes")
_BOOTH_REQUIRED = ("code", "area_sqm", "price", "currency", "is_active")


def _booth_out(booth: Booth, holder: tuple[uuid.UUID, str] | None, show_holder: bool) -> BoothOut:
    out = BoothOut.model_validate(booth)
    out.is_available = holder is None
    if holder is not None and show_holder:
        out.exhibitor_lead_id, out.exhibitor_company_name = holder
    return out


def _require_booth_manager(ctx: AuthContext, edition_id: uuid.UUID) -> None:
    if not ctx.scope_for(edition_id, "booth.manage").full_access:
        raise PermissionDenied()


def _clean_booth(values: dict[str, Any]) -> dict[str, Any]:
    out = {k: clean_text(v) if k in ("code", "hall", "notes") else v for k, v in values.items()}
    missing = {k: "Required." for k in _BOOTH_REQUIRED if k in out and out[k] is None}
    if missing:
        raise ValidationFailed(fields=missing)
    return out


async def _save_booth(session: AsyncSession, booth: Booth, before: dict[str, Any] | None) -> None:
    await _flush(session, booth)
    await audit.record(
        session,
        entity_type=BOOTH_ENTITY,
        entity_id=booth.id,
        action="create" if before is None else "update",
        before=before,
        after=audit.snapshot(booth, BOOTH_AUDIT_FIELDS),
        edition_id=booth.edition_id,
    )


async def list_booths(
    session: AsyncSession, ctx: AuthContext, params: BoothListParams
) -> Page[BoothOut]:
    """Booths of an edition with availability; holders only for edition-wide access."""
    scopes = []
    for permission in ("booth.manage", "exhibitor_lead.read"):
        try:
            scopes.append(ctx.scope_for(params.edition_id, permission))
        except NotFound:
            continue
    if not scopes:
        raise NotFound("Edition not found.", code="EDITION_NOT_FOUND")
    show_holder = any(s.full_access for s in scopes)
    rows, total = await repo.list_booths(session, params.edition_id, params)
    items = [
        _booth_out(booth, (lead_id, company) if lead_id and company else None, show_holder)
        for booth, lead_id, company in rows
    ]
    return Page(items=items, total=total, page=params.page, page_size=params.page_size)


async def create_booth(session: AsyncSession, ctx: AuthContext, data: BoothCreateIn) -> BoothOut:
    """Add a booth to an edition; currency defaults to the edition's."""
    _require_booth_manager(ctx, data.edition_id)
    edition = await exhibitions_service.ensure_writable(session, data.edition_id)
    values = data.model_dump(exclude={"edition_id"})
    values["currency"] = values["currency"] or edition.default_currency
    values["is_active"] = True if values["is_active"] is None else values["is_active"]
    actor = current_actor_id()
    booth = Booth(
        edition_id=data.edition_id, created_by=actor, updated_by=actor, **_clean_booth(values)
    )
    await _save_booth(session, booth, None)
    return _booth_out(booth, None, True)


async def update_booth(
    session: AsyncSession, ctx: AuthContext, booth_id: uuid.UUID, data: BoothUpdateIn
) -> BoothOut:
    """Edit a booth; a booth held by a lead cannot be deactivated."""
    booth = await repo.get_booth(session, booth_id, for_update=True)
    if booth is None:
        raise NotFound("Booth not found.")
    try:
        _require_booth_manager(ctx, booth.edition_id)
    except NotFound as e:
        raise NotFound("Booth not found.") from e
    check_version(booth.version, data.version)
    await exhibitions_service.ensure_writable(session, booth.edition_id)
    changes = _clean_booth(data.model_dump(exclude_unset=True, exclude={"version"}))
    holder = await repo.booth_holder(session, booth.id)
    if changes.get("is_active") is False and holder is not None:
        raise Conflict("Release the booth before deactivating it.", code="BOOTH_IN_USE")
    before = audit.snapshot(booth, BOOTH_AUDIT_FIELDS)
    for key, value in changes.items():
        setattr(booth, key, value)
    booth.updated_by = current_actor_id()
    await _save_booth(session, booth, before)
    return _booth_out(booth, holder, True)


# --- convert and portal invitations ----------------------------------------------------

CONTRACT_ENTITY = "exhibitor_contract"
CONTRACT_AUDIT_FIELDS = (
    "contract_number", "pic_name", "company_address", "tax_id", "booth_price",
    "discount_amount", "total_amount", "currency", "status", "signed_at", "signed_file_name",
)  # fmt: skip
ACCOUNT_ENTITY = "exhibitor_account"
ACCOUNT_AUDIT_FIELDS = ("email", "is_active", "activated_at")


def portal_url(path: str) -> str:
    """Portal on its own host in production, under /exhibitor on the desk host otherwise."""
    s = get_settings()
    base = s.portal_base_url.rstrip("/") or f"{s.public_base_url.rstrip('/')}/exhibitor"
    return f"{base}/{path.lstrip('/')}"


def _issue_invitation(account: ExhibitorAccount) -> InvitationOut:
    """New single-use link; any earlier link of the account stops working."""
    token = new_token()
    expires_at = datetime.now(UTC) + timedelta(seconds=get_settings().portal_invite_ttl_seconds)
    account.invite_token_hash = sha256_hex(token)
    account.invite_expires_at = expires_at
    return InvitationOut(url=portal_url(f"accept-invite?token={token}"), expires_at=expires_at)


async def _account_for(
    session: AsyncSession, lead: ExhibitorLead
) -> tuple[ExhibitorAccount, InvitationOut | None]:
    """The lead's portal account by email: reused across editions, created on first convert."""
    account = await repo.account_by_email(session, lead.email_normalized, for_update=True)
    if account is not None and not account.is_active:
        raise Conflict("The portal account of this email is deactivated.", code="ACCOUNT_INACTIVE")
    if account is not None and account.password_hash is not None:
        return account, None
    created = account is None
    if account is None:
        actor = current_actor_id()
        account = ExhibitorAccount(
            email=lead.email,
            email_normalized=lead.email_normalized,
            is_active=True,
            created_by=actor,
            updated_by=actor,
        )
    invitation = _issue_invitation(account)
    try:
        async with session.begin_nested():
            session.add(account)
            await session.flush()
    except IntegrityError as e:
        # Two editions converting the same email at once; the retry finds the account.
        raise Conflict("Try again.", code="ACCOUNT_CREATED_CONCURRENTLY") from e
    await audit.record(
        session,
        entity_type=ACCOUNT_ENTITY,
        entity_id=account.id,
        action="create" if created else "invite",
        after=audit.snapshot(account, ACCOUNT_AUDIT_FIELDS)
        | {"invite_expires_at": invitation.expires_at},
    )
    return account, invitation


async def convert(
    session: AsyncSession, ctx: AuthContext, lead_id: uuid.UUID, data: ConvertIn
) -> ConvertOut:
    """Opportunity with a booth becomes an exhibitor: portal account, DRAFT contract."""
    scope = await _scope_for_lead(session, ctx, lead_id)
    lead = await _get(session, scope, lead_id, for_update=True)
    check_version(lead.version, data.version)
    edition = await exhibitions_service.ensure_writable(session, lead.edition_id)
    if not can_move(SalesStage(lead.stage), SalesStage.EXHIBITOR):
        raise ValidationFailed(
            f"Cannot convert a lead in stage {lead.stage}.", code="INVALID_STAGE_TRANSITION"
        )
    if lead.booth_id is None:
        raise ValidationFailed("Assign a booth before converting.", code="BOOTH_REQUIRED")
    booth = await repo.get_booth(session, lead.booth_id)
    assert booth is not None  # noqa: S101 - FK
    account, invitation = await _account_for(session, lead)
    now = datetime.now(UTC)
    lead = await _save(
        session,
        lead,
        {"stage": SalesStage.EXHIBITOR, "converted_at": now, "exhibitor_account_id": account.id},
        "convert",
    )
    number = await repo.next_contract_number(session, lead.edition_id)
    actor = current_actor_id()
    contract = ExhibitorContract(
        edition_id=lead.edition_id,
        exhibitor_lead_id=lead.id,
        contract_number=f"{edition.code}-C-{number:04d}",
        booth_price=booth.price,
        discount_amount=0,
        total_amount=booth.price,
        currency=booth.currency,
        status=ContractStatus.DRAFT,
        created_by=actor,
        updated_by=actor,
    )
    session.add(contract)
    await session.flush()
    await audit.record(
        session,
        entity_type=CONTRACT_ENTITY,
        entity_id=contract.id,
        action="create",
        after=audit.snapshot(contract, CONTRACT_AUDIT_FIELDS),
        edition_id=contract.edition_id,
    )
    assert contract.contract_number is not None  # noqa: S101 - set above
    return ConvertOut(
        lead=await _out(session, lead),
        contract_number=contract.contract_number,
        invitation=invitation,
    )


async def reissue_invitation(
    session: AsyncSession, ctx: AuthContext, lead_id: uuid.UUID
) -> InvitationOut:
    """New invitation link for an exhibitor whose account has no password yet."""
    scope = await _scope_for_lead(session, ctx, lead_id)
    lead = await _get(session, scope, lead_id)
    if lead.exhibitor_account_id is None:
        raise ValidationFailed("Convert the lead first.", code="NOT_AN_EXHIBITOR")
    account = await repo.get_account(session, lead.exhibitor_account_id, for_update=True)
    assert account is not None  # noqa: S101 - FK
    if account.password_hash is not None:
        raise Conflict("The account is already active.", code="ACCOUNT_ALREADY_ACTIVE")
    if not account.is_active:
        raise Conflict("The portal account is deactivated.", code="ACCOUNT_INACTIVE")
    invitation = _issue_invitation(account)
    account.updated_by = current_actor_id()
    await session.flush()
    await audit.record(
        session,
        entity_type=ACCOUNT_ENTITY,
        entity_id=account.id,
        action="invite",
        after={"invite_expires_at": invitation.expires_at},
        edition_id=lead.edition_id,
    )
    return invitation
