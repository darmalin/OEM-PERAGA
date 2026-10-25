import uuid
from datetime import datetime
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
from app.modules.visitors import repository as repo
from app.modules.visitors.models import (
    EditionFieldOption,
    LeadSourceOption,
    VisitorCustomFieldDefinition,
    VisitorLead,
)
from app.modules.visitors.rules import (
    CustomFieldDef,
    CustomFieldType,
    LeadSource,
    NormalizationError,
    OptionField,
    clean_text,
    normalize_email,
    normalize_phone,
    validate_custom_fields,
)
from app.modules.visitors.schemas import (
    CustomFieldIn,
    CustomFieldOut,
    CustomFieldUpdateIn,
    FieldOptionIn,
    FieldOptionOut,
    FieldOptionUpdateIn,
    FilterChoice,
    LeadCreateIn,
    LeadFilterOptions,
    LeadFilterOptionsParams,
    LeadFilters,
    LeadListItem,
    LeadListParams,
    LeadOut,
    LeadSourceIn,
    LeadSourceOut,
    LeadSourceUpdateIn,
    LeadUpdateIn,
)

ENTITY = "visitor_lead"
AUDIT_FIELDS = (
    "registration_code",
    "lead_date",
    "first_name",
    "email",
    "phone",
    "gender",
    "company_name",
    "job_title",
    "country",
    "city",
    "website",
    "business_type",
    "branch",
    "exhibition_type",
    "source",
    "lead_source_id",
    "lead_owner_id",
    "product_categories",
    "comment",
    "custom_fields",
    "is_valid_lead",
    "is_invalid",
    "attend",
    "b2b_matching",
    "buyer_type",
    "telemarketing_status",
    "registration_status",
    "qr_status",
)
_TEXT_FIELDS = (
    "first_name",
    "company_name",
    "job_title",
    "city",
    "website",
    "product_categories",
    "comment",
)
_OPTION_FIELDS = {
    "business_type": OptionField.BUSINESS_TYPE,
    "branch": OptionField.BRANCH,
    "exhibition_type": OptionField.EXHIBITION_TYPE,
}
_UNIQUE_FIELDS = {
    "uq_visitor_leads_edition_email": "email",
    "uq_visitor_leads_edition_phone": "phone",
    "uq_visitor_leads_edition_external": "external_id",
}


class DuplicateVisitor(Conflict):
    code = "DUPLICATE_VISITOR"

    def __init__(
        self,
        message: str | None = None,
        *,
        fields: dict[str, str] | None = None,
        import_job_ids: set[uuid.UUID] | None = None,
    ) -> None:
        super().__init__(message, fields=fields)
        # Import jobs that created the conflicting leads (in-file duplicate detection).
        self.import_job_ids = import_job_ids or set()


# --- scope -------------------------------------------------------------------------------


async def scope_for_lead(
    session: AsyncSession, ctx: AuthContext, lead_id: uuid.UUID, permission: str | None = None
) -> Scope:
    """Resolve the caller's scope in the lead's edition; 404 if the lead is unknown/hidden."""
    edition_id = await repo.edition_of(session, lead_id)
    if edition_id is None:
        raise NotFound("Visitor lead not found.")
    try:
        return ctx.scope_for(edition_id, permission)
    except NotFound as e:
        raise NotFound("Visitor lead not found.") from e


async def get_lead_entity(
    session: AsyncSession, scope: Scope, lead_id: uuid.UUID, *, for_update: bool = False
) -> VisitorLead:
    """Load a lead inside the scope (404 otherwise). Used by other modules."""
    lead = await repo.get_lead(session, scope, lead_id, for_update=for_update)
    if lead is None:
        raise NotFound("Visitor lead not found.")
    return lead


async def scoped_lead_ids(
    session: AsyncSession,
    scope: Scope,
    lead_ids: list[uuid.UUID] | None,
    filters: LeadFilters | None,
    limit: int,
) -> list[uuid.UUID]:
    """Lead IDs visible in the scope, by explicit IDs or by list filter."""
    return await repo.scoped_lead_ids(session, scope, lead_ids, filters, limit)


async def lock_leads(
    session: AsyncSession, scope: Scope, lead_ids: list[uuid.UUID]
) -> list[VisitorLead]:
    return await repo.lock_leads(session, scope, lead_ids)


async def get_lead_internal(
    session: AsyncSession, edition_id: uuid.UUID, lead_id: uuid.UUID, *, for_update: bool = False
) -> VisitorLead:
    """Unscoped lookup for callers that already authorized access another way
    (e.g. the assignee of a follow-up). Never expose its result without that check."""
    full = Scope(edition_id=edition_id, user_id=uuid.UUID(int=0), full_access=True)
    return await get_lead_entity(session, full, lead_id, for_update=for_update)


async def unregistered_leads(
    session: AsyncSession, edition_ids: list[uuid.UUID], limit: int
) -> list[VisitorLead]:
    """No user scope: for the backfill command only."""
    return await repo.unregistered_leads(session, edition_ids, limit)


def visible_lead_ids(scope: Scope) -> Any:
    """Subquery of lead IDs visible in the scope (for filters in other modules)."""
    return repo.visible_ids(scope)


async def lead_labels(
    session: AsyncSession, scope: Scope, lead_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[str, str]]:
    """lead id -> (first name, Registration ID)."""
    return await repo.labels(session, scope, lead_ids) if lead_ids else {}


async def owner_queue(
    session: AsyncSession, scope: Scope, owner_id: uuid.UUID, page: int, page_size: int
) -> Page[LeadListItem]:
    """Leads owned by one agent in call order."""
    rows, total = await repo.owner_queue(
        session, scope, owner_id, (page - 1) * page_size, page_size
    )
    items = []
    for lead, owner in rows:
        item = LeadListItem.model_validate(lead)
        item.lead_owner_name = owner
        items.append(item)
    return Page(items=items, total=total, page=page, page_size=page_size)


async def lead_out(session: AsyncSession, lead: VisitorLead) -> LeadOut:
    out = LeadOut.model_validate(lead)
    out.lead_owner_name = await repo.owner_name(session, lead.lead_owner_id)
    return out


# --- normalization and validation --------------------------------------------------------


async def _custom_defs(session: AsyncSession, edition_id: uuid.UUID) -> list[CustomFieldDef]:
    return [
        CustomFieldDef(
            field_key=d.field_key,
            label=d.label,
            field_type=CustomFieldType(d.field_type),
            required=d.required,
            options=tuple(d.options),
            validation=dict(d.validation),
        )
        for d in await repo.active_custom_fields(session, edition_id)
    ]


async def normalize_fields(
    session: AsyncSession,
    edition_id: uuid.UUID,
    values: dict[str, Any],
    *,
    current: VisitorLead | None = None,
) -> dict[str, Any]:
    """Clean and validate submitted Person fields. Raises ValidationFailed with field errors.

    Only keys present in `values` are processed (PATCH semantics).
    """
    out: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for key in _TEXT_FIELDS:
        if key in values:
            out[key] = clean_text(values[key])
    if "first_name" in values and out.get("first_name") is None:
        errors["first_name"] = "First Name is required."
    for key in ("lead_date", "gender", "country"):
        if key in values:
            out[key] = values[key]

    if "email" in values:
        try:
            out["email_normalized"] = normalize_email(values["email"])
            out["email"] = clean_text(values["email"])
        except NormalizationError as e:
            errors["email"] = str(e)
    if "phone" in values or ("country" in values and current is not None and current.phone):
        raw_phone = values.get("phone", current.phone if current else None)
        country = values.get("country", current.country if current else None)
        try:
            out["phone_normalized"] = normalize_phone(raw_phone, country)
            out["phone"] = clean_text(raw_phone)
        except NormalizationError as e:
            errors["phone"] = str(e)

    options = await repo.active_option_values(session, edition_id)
    for key, field in _OPTION_FIELDS.items():
        if key in values:
            value = clean_text(values[key])
            if value is not None and value not in options.get(field, set()):
                errors[key] = "Not one of the allowed options."
            out[key] = value
    if "lead_source_id" in values:
        source_id = values["lead_source_id"]
        if source_id is not None:
            found = await repo.get_lead_source(session, source_id)
            # An inactive source stays valid on a lead that already has it.
            keeps = current is not None and current.lead_source_id == source_id
            if found is None or not (found.is_active or keeps):
                errors["lead_source_id"] = "Not one of the allowed options."
        out["lead_source_id"] = source_id
    if "custom_fields" in values:
        sent = dict(values["custom_fields"] or {})
        existing = dict(current.custom_fields) if current else {}
        defs = await _custom_defs(session, edition_id)
        active = {d.field_key for d in defs}
        merged = {k: v for k, v in {**existing, **sent}.items() if v is not None}
        to_check = {k: v for k, v in merged.items() if k in active or k in sent}
        clean, cf_errors = validate_custom_fields(defs, to_check)
        errors.update({f"custom_fields.{k}": v for k, v in cf_errors.items()})
        kept_inactive = {k: v for k, v in merged.items() if k not in active and k not in sent}
        out["custom_fields"] = {**kept_inactive, **clean}
    elif current is None:
        defs = await _custom_defs(session, edition_id)
        _, cf_errors = validate_custom_fields(defs, {})
        errors.update({f"custom_fields.{k}": v for k, v in cf_errors.items()})
        out["custom_fields"] = {}

    email_n = out.get("email_normalized", current.email_normalized if current else None)
    phone_n = out.get("phone_normalized", current.phone_normalized if current else None)
    if email_n is None and phone_n is None and "email" not in errors and "phone" not in errors:
        # spec 5.2: email and phone both empty is rejected.
        errors["email"] = errors["phone"] = "Email or Phone is required."
    if errors:
        raise ValidationFailed(fields=errors)
    return out


async def _raise_if_duplicate(
    session: AsyncSession,
    edition_id: uuid.UUID,
    email_n: str | None,
    phone_n: str | None,
    exclude_id: uuid.UUID | None = None,
) -> None:
    rows = await repo.find_conflicts(session, edition_id, email_n, phone_n, exclude_id)
    if not rows:
        return
    fields: dict[str, str] = {}
    codes: list[str] = []
    job_ids: set[uuid.UUID] = set()
    for code, other_email, other_phone, job_id in rows:
        if job_id is not None:
            job_ids.add(job_id)
        if email_n and other_email == email_n:
            fields["email"] = "Already used in this edition."
        if phone_n and other_phone == phone_n:
            fields["phone"] = "Already used in this edition."
        codes.append(code)
    label = " and ".join(k.capitalize() for k in ("email", "phone") if k in fields)
    raise DuplicateVisitor(
        f"{label} already used by {', '.join(sorted(set(codes)))} in this edition.",
        fields=fields,
        import_job_ids=job_ids,
    )


def _integrity_to_conflict(e: IntegrityError) -> Exception:
    """Race-safe mapping of DB constraint violations (two requests passing the pre-check)."""
    msg = str(e.orig)
    for constraint, field in _UNIQUE_FIELDS.items():
        if constraint in msg:
            return DuplicateVisitor(
                f"{field.replace('_', ' ').capitalize()} already used in this edition.",
                fields={field: "Already used in this edition."},
            )
    if "ck_visitor_leads_email_or_phone" in msg:
        return ValidationFailed(fields={"email": "Email or Phone is required."})
    return e


async def _flush_in_savepoint(session: AsyncSession, lead: VisitorLead) -> None:
    """Savepoint so a violation leaves the outer transaction usable (imports continue)."""
    try:
        async with session.begin_nested():
            session.add(lead)
            await session.flush()
    except IntegrityError as e:
        raise _integrity_to_conflict(e) from e


# --- create / update ---------------------------------------------------------------------


async def insert_lead(
    session: AsyncSession,
    edition_id: uuid.UUID,
    values: dict[str, Any],
    *,
    source: LeadSource,
    external_source: str | None = None,
    external_id: str | None = None,
    import_job_id: uuid.UUID | None = None,
) -> VisitorLead:
    """Create a lead after normalization and duplicate checks. Used by API, import, website."""
    await exhibitions_service.ensure_writable(session, edition_id)
    clean = await normalize_fields(session, edition_id, values)
    await _raise_if_duplicate(
        session, edition_id, clean.get("email_normalized"), clean.get("phone_normalized")
    )
    actor = current_actor_id()
    lead = VisitorLead(
        edition_id=edition_id,
        registration_code=await exhibitions_service.next_registration_id(session, edition_id),
        source=source,
        external_source=clean_text(external_source),
        external_id=clean_text(external_id),
        import_job_id=import_job_id,
        created_by=actor,
        updated_by=actor,
        **{k: v for k, v in clean.items() if v is not None or k == "custom_fields"},
    )
    await _flush_in_savepoint(session, lead)
    await session.refresh(lead)
    await audit.record(
        session,
        entity_type=ENTITY,
        entity_id=lead.id,
        action="create",
        after=audit.snapshot(lead, AUDIT_FIELDS),
        edition_id=edition_id,
    )
    return lead


async def create_lead(session: AsyncSession, ctx: AuthContext, data: LeadCreateIn) -> VisitorLead:
    """Create a lead from POST /visitor-leads; registrations.create_lead registers it."""
    scope = ctx.scope_for(data.edition_id)
    if not scope.full_access:
        # Creating unowned leads needs edition-wide access; otherwise the caller could not see it.
        raise PermissionDenied()
    values = data.model_dump(
        exclude_unset=True, exclude={"edition_id", "source", "external_source", "external_id"}
    )
    values.setdefault("first_name", data.first_name)
    lead = await insert_lead(
        session,
        data.edition_id,
        values,
        source=data.source,
        external_source=data.external_source,
        external_id=data.external_id,
    )
    return lead


async def apply_changes(
    session: AsyncSession, lead: VisitorLead, changes: dict[str, Any], action: str = "update"
) -> VisitorLead:
    """Write already-validated changes with an audit entry. Used by other modules too."""
    before = audit.snapshot(lead, AUDIT_FIELDS)
    for key, value in changes.items():
        setattr(lead, key, value)
    lead.updated_by = current_actor_id()
    try:
        async with session.begin_nested():
            await session.flush()
    except IntegrityError as e:
        raise _integrity_to_conflict(e) from e
    await session.refresh(lead)
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


async def update_lead(
    session: AsyncSession, ctx: AuthContext, lead_id: uuid.UUID, data: LeadUpdateIn
) -> LeadOut:
    """PATCH /visitor-leads/{id}: Person fields only (verification and owner have their own)."""
    scope = await scope_for_lead(session, ctx, lead_id)
    lead = await get_lead_entity(session, scope, lead_id, for_update=True)
    check_version(lead.version, data.version)
    await exhibitions_service.ensure_writable(session, lead.edition_id)
    values = data.model_dump(exclude_unset=True, exclude={"version"})
    clean = await normalize_fields(session, lead.edition_id, values, current=lead)
    if "email_normalized" in clean or "phone_normalized" in clean:
        await _raise_if_duplicate(
            session,
            lead.edition_id,
            clean.get("email_normalized", lead.email_normalized),
            clean.get("phone_normalized", lead.phone_normalized),
            exclude_id=lead.id,
        )
    lead = await apply_changes(session, lead, clean)
    return await lead_out(session, lead)


async def get_lead(session: AsyncSession, ctx: AuthContext, lead_id: uuid.UUID) -> LeadOut:
    scope = await scope_for_lead(session, ctx, lead_id)
    return await lead_out(session, await get_lead_entity(session, scope, lead_id))


async def readable_scopes(
    session: AsyncSession, ctx: AuthContext, permission: str | None = None
) -> list[Scope]:
    """The caller's scope in every edition the permission (default: the route's) applies to."""
    ids = ctx.edition_ids(permission)
    if ids is None:
        ids = {e.id for e in await exhibitions_service.edition_summaries(session, None)}
    scopes = []
    for edition_id in sorted(ids):
        try:
            scopes.append(ctx.scope_for(edition_id, permission))
        except NotFound:
            continue
    return scopes


def lead_visibility(scopes: list[Scope]) -> Any:
    """SQL condition on visitor_leads: visible in any of the scopes (reports across editions)."""
    return repo.any_scope_clause(scopes)


async def list_leads(
    session: AsyncSession, ctx: AuthContext, params: LeadListParams
) -> Page[LeadListItem]:
    """Lead list with filters, search, sort, and pagination, inside the caller's scope."""
    if params.edition_id is not None:
        scopes = [ctx.scope_for(params.edition_id)]
    else:
        scopes = await readable_scopes(session, ctx)
    rows, total = await repo.list_leads(
        session, scopes, params, params.sort, params.offset, params.page_size
    )
    items = []
    for lead, owner in rows:
        item = LeadListItem.model_validate(lead)
        item.lead_owner_name = owner
        items.append(item)
    return Page(items=items, total=total, page=params.page, page_size=params.page_size)


async def filter_options(
    session: AsyncSession, ctx: AuthContext, params: LeadFilterOptionsParams
) -> LeadFilterOptions:
    if params.edition_id is not None:
        scopes = [ctx.scope_for(params.edition_id)]
    else:
        scopes = await readable_scopes(session, ctx)
    countries, owners, teams = await repo.filter_options(session, scopes)
    return LeadFilterOptions(
        countries=countries,
        owners=[FilterChoice(id=i, name=n) for i, n in owners],
        teams=[FilterChoice(id=i, name=n) for i, n in teams],
    )


async def activity(
    session: AsyncSession, ctx: AuthContext, lead_id: uuid.UUID
) -> list[AuditLogOut]:
    """Activity timeline of a lead (visible to anyone who can read the lead)."""
    scope = await scope_for_lead(session, ctx, lead_id)
    lead = await get_lead_entity(session, scope, lead_id)
    return await audit_service.entity_timeline(session, lead.edition_id, ENTITY, lead.id)


# --- custom field definitions ------------------------------------------------------------

_CF_FIELDS = (
    "field_key", "label", "field_type", "required", "options", "validation",
    "sort_order", "is_active", "in_import", "in_export",
)  # fmt: skip


def _require_edition_admin(ctx: AuthContext, edition_id: uuid.UUID) -> None:
    if not ctx.scope_for(edition_id, "edition.manage").full_access:
        raise PermissionDenied()


def _check_options(field_type: str, options: list[str]) -> None:
    if field_type in (CustomFieldType.SELECT, CustomFieldType.MULTI_SELECT):
        if not options:
            raise ValidationFailed(fields={"options": "Select fields need at least one option."})
        if len(set(options)) != len(options):
            raise ValidationFailed(fields={"options": "Options must be unique."})
    elif options:
        raise ValidationFailed(fields={"options": "Only select fields have options."})


async def list_custom_fields(
    session: AsyncSession, ctx: AuthContext, edition_id: uuid.UUID, include_inactive: bool
) -> list[CustomFieldOut]:
    ctx.scope_for(edition_id)
    defs = await repo.active_custom_fields(session, edition_id, include_inactive)
    return [CustomFieldOut.model_validate(d) for d in defs]


async def create_custom_field(
    session: AsyncSession, ctx: AuthContext, data: CustomFieldIn
) -> CustomFieldOut:
    """Define a custom field for an edition."""
    _require_edition_admin(ctx, data.edition_id)
    _check_options(data.field_type, data.options)
    d = VisitorCustomFieldDefinition(
        **data.model_dump(), created_by=ctx.user.id, updated_by=ctx.user.id
    )
    session.add(d)
    try:
        async with session.begin_nested():
            await session.flush()
    except IntegrityError as e:
        raise Conflict(fields={"field_key": "Already exists in this edition."}) from e
    await audit.record(
        session,
        entity_type="custom_field",
        entity_id=d.id,
        action="create",
        after=audit.snapshot(d, _CF_FIELDS),
        edition_id=d.edition_id,
    )
    await session.refresh(d)
    return CustomFieldOut.model_validate(d)


async def update_custom_field(
    session: AsyncSession, ctx: AuthContext, field_id: uuid.UUID, data: CustomFieldUpdateIn
) -> CustomFieldOut:
    """Edit a custom field. Key and type are fixed once created."""
    d = await repo.get_custom_field(session, field_id)
    if d is None:
        raise NotFound("Custom field not found.")
    _require_edition_admin(ctx, d.edition_id)
    check_version(d.version, data.version)
    changes = data.model_dump(exclude_unset=True, exclude={"version"})
    if "options" in changes:
        _check_options(d.field_type, changes["options"])
    before = audit.snapshot(d, _CF_FIELDS)
    for key, value in changes.items():
        setattr(d, key, value)
    d.updated_by = ctx.user.id
    await session.flush()
    await audit.record(
        session,
        entity_type="custom_field",
        entity_id=d.id,
        action="update",
        before=before,
        after=audit.snapshot(d, _CF_FIELDS),
        edition_id=d.edition_id,
    )
    await session.refresh(d)
    return CustomFieldOut.model_validate(d)


async def custom_field_definitions(
    session: AsyncSession, edition_id: uuid.UUID
) -> list[VisitorCustomFieldDefinition]:
    """Active definitions, for import templates and exports."""
    return list(await repo.active_custom_fields(session, edition_id))


# --- configurable select options ---------------------------------------------------------


async def list_field_options(
    session: AsyncSession,
    ctx: AuthContext,
    edition_id: uuid.UUID,
    field: OptionField | None,
    include_inactive: bool,
) -> list[FieldOptionOut]:
    ctx.scope_for(edition_id)
    rows = await repo.field_options(session, edition_id, field, include_inactive)
    return [FieldOptionOut.model_validate(r) for r in rows]


async def create_field_option(
    session: AsyncSession, ctx: AuthContext, data: FieldOptionIn
) -> FieldOptionOut:
    """Add an option to a configurable select."""
    _require_edition_admin(ctx, data.edition_id)
    option = EditionFieldOption(**data.model_dump())
    session.add(option)
    try:
        async with session.begin_nested():
            await session.flush()
    except IntegrityError as e:
        raise Conflict(fields={"value": "Already exists for this field."}) from e
    await audit.record(
        session,
        entity_type="field_option",
        entity_id=option.id,
        action="create",
        after=data.model_dump(exclude={"edition_id"}),
        edition_id=option.edition_id,
    )
    await session.refresh(option)
    return FieldOptionOut.model_validate(option)


async def update_field_option(
    session: AsyncSession, ctx: AuthContext, option_id: uuid.UUID, data: FieldOptionUpdateIn
) -> FieldOptionOut:
    """Rename, reorder, or deactivate an option. The stored value never changes."""
    option = await repo.get_field_option(session, option_id)
    if option is None:
        raise NotFound("Option not found.")
    _require_edition_admin(ctx, option.edition_id)
    check_version(option.version, data.version)
    fields = ("label", "sort_order", "is_active")
    before = audit.snapshot(option, fields)
    for key, value in data.model_dump(exclude_unset=True, exclude={"version"}).items():
        setattr(option, key, value)
    await session.flush()
    await audit.record(
        session,
        entity_type="field_option",
        entity_id=option.id,
        action="update",
        before=before,
        after=audit.snapshot(option, fields),
        edition_id=option.edition_id,
    )
    await session.refresh(option)
    return FieldOptionOut.model_validate(option)


# --- reports and exports -------------------------------------------------------------------


def filtered_lead_ids(scope: Scope, filters: LeadFilters) -> Any:
    """Subquery of lead IDs in scope matching the list filters (reports)."""
    return repo.filtered_ids(scope, filters)


async def export_batch(
    session: AsyncSession,
    scope: Scope,
    filters: LeadFilters,
    after: tuple[datetime, uuid.UUID] | None,
    limit: int,
) -> list[tuple[VisitorLead, str | None]]:
    """(lead, owner name) pages in creation order for the Excel export worker."""
    return [(r[0], r[1]) for r in await repo.export_batch(session, scope, filters, after, limit)]


# --- lead sources (global master data) --------------------------------------------------------

_SOURCE_FIELDS = ("name", "sort_order", "is_active")


def _require_master_data(ctx: AuthContext) -> None:
    """Global master data, like venues: needs a cross-edition exhibition.manage grant."""
    if not ctx.has_global("exhibition.manage"):
        raise PermissionDenied()


async def list_lead_sources(session: AsyncSession, include_inactive: bool) -> list[LeadSourceOut]:
    rows = await repo.list_lead_sources(session, include_inactive)
    return [LeadSourceOut.model_validate(r) for r in rows]


async def _save_source(session: AsyncSession, source: LeadSourceOption) -> None:
    try:
        async with session.begin_nested():
            await session.flush()
    except IntegrityError as e:
        raise Conflict(
            "A source with this name already exists.",
            code="DUPLICATE_LEAD_SOURCE",
            fields={"name": "Already exists."},
        ) from e
    await session.refresh(source)


async def create_lead_source(
    session: AsyncSession, ctx: AuthContext, data: LeadSourceIn
) -> LeadSourceOut:
    _require_master_data(ctx)
    source = LeadSourceOption(
        name=data.name.strip(),
        sort_order=data.sort_order,
        is_active=data.is_active,
        created_by=ctx.user.id,
        updated_by=ctx.user.id,
    )
    session.add(source)
    await _save_source(session, source)
    await audit.record(
        session,
        entity_type="lead_source",
        entity_id=source.id,
        action="create",
        after=audit.snapshot(source, _SOURCE_FIELDS),
    )
    return LeadSourceOut.model_validate(source)


async def update_lead_source(
    session: AsyncSession, ctx: AuthContext, source_id: uuid.UUID, data: LeadSourceUpdateIn
) -> LeadSourceOut:
    """Rename, reorder, or deactivate. Leads keep the source; inactive ones are hidden in forms."""
    _require_master_data(ctx)
    source = await repo.get_lead_source(session, source_id)
    if source is None:
        raise NotFound("Source not found.")
    check_version(source.version, data.version)
    before = audit.snapshot(source, _SOURCE_FIELDS)
    changes = data.model_dump(exclude_unset=True, exclude={"version"})
    if changes.get("name") is not None:
        changes["name"] = changes["name"].strip()
    for key, value in changes.items():
        if value is not None:
            setattr(source, key, value)
    source.updated_by = ctx.user.id
    await _save_source(session, source)
    await audit.record(
        session,
        entity_type="lead_source",
        entity_id=source.id,
        action="update",
        before=before,
        after=audit.snapshot(source, _SOURCE_FIELDS),
    )
    return LeadSourceOut.model_validate(source)
