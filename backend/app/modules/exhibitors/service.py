import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.authorization import AuthContext, Scope
from app.core.context import current_actor_id
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed, check_version
from app.core.pagination import Page
from app.modules.audit import service as audit_service
from app.modules.audit.schemas import AuditLogOut
from app.modules.exhibitions import service as exhibitions_service
from app.modules.exhibitors import repository as repo
from app.modules.exhibitors.models import ExhibitorLead
from app.modules.exhibitors.rules import SalesStage, can_move
from app.modules.exhibitors.schemas import (
    ExhibitorLeadCreateIn,
    ExhibitorLeadListParams,
    ExhibitorLeadOut,
    ExhibitorLeadUpdateIn,
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
    if "fk_exhibitor_leads_lead_owner_id_users" in msg:
        return ValidationFailed(fields={"lead_owner_id": "Unknown user."})
    return e


async def _flush(session: AsyncSession, lead: ExhibitorLead) -> None:
    try:
        async with session.begin_nested():
            session.add(lead)
            await session.flush()
    except IntegrityError as e:
        raise _integrity_error(e) from e
    await session.refresh(lead)


async def _raise_if_duplicate(
    session: AsyncSession, edition_id: uuid.UUID, email_n: str, exclude_id: uuid.UUID | None
) -> None:
    if await repo.email_taken(session, edition_id, email_n, exclude_id):
        raise DuplicateExhibitorLead(fields={"email": "Already used in this edition."})


async def _out(session: AsyncSession, lead: ExhibitorLead) -> ExhibitorLeadOut:
    out = ExhibitorLeadOut.model_validate(lead)
    out.lead_owner_name = await repo.owner_name(session, lead.lead_owner_id)
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
    for lead, owner in rows:
        item = ExhibitorLeadOut.model_validate(lead)
        item.lead_owner_name = owner
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
