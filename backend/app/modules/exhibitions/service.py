import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.authorization import AuthContext
from app.core.context import current_actor_id
from app.core.errors import (
    Conflict,
    NotFound,
    PermissionDenied,
    ValidationFailed,
    check_version,
)
from app.core.pagination import Page
from app.modules.exhibitions import repository as repo
from app.modules.exhibitions.models import Edition, EditionCounter, Exhibition, Venue
from app.modules.exhibitions.rules import (
    EXHIBITOR_DATE_FIELDS,
    EditionStatus,
    can_transition,
    default_edition_code,
    period_errors,
)
from app.modules.exhibitions.schemas import (
    EditionIn,
    EditionListParams,
    EditionOut,
    EditionUpdateIn,
    ExhibitionIn,
    ExhibitionListParams,
    ExhibitionOut,
    ExhibitionUpdateIn,
    VenueIn,
    VenueOut,
    VenueUpdateIn,
)

_EXHIBITION_FIELDS = ("code", "name", "is_active")
_VENUE_FIELDS = ("name", "address", "city", "country")
_EDITION_FIELDS = (
    "exhibition_id",
    "year",
    "code",
    "name",
    "start_date",
    "end_date",
    "venue_id",
    "country",
    "city",
    "timezone",
    "default_currency",
    "registration_id_prefix",
    "status",
    "email_sender_name",
    "email_reply_to",
    "email_account_id",
    "scanner_cache_ttl_minutes",
    "remarks",
    *EXHIBITOR_DATE_FIELDS,
)


def _require_global(ctx: AuthContext, permission: str) -> None:
    """Master data (exhibitions, venues, new editions) needs a cross-edition grant."""
    if not ctx.has_global(permission):
        raise PermissionDenied()


def _apply(obj: Any, changes: dict[str, Any]) -> None:
    for key, value in changes.items():
        setattr(obj, key, value)


# --- venues --------------------------------------------------------------------------------


async def list_venues(session: AsyncSession) -> list[VenueOut]:
    return [VenueOut.model_validate(v) for v in await repo.list_venues(session)]


async def create_venue(session: AsyncSession, ctx: AuthContext, data: VenueIn) -> VenueOut:
    """Create a venue."""
    _require_global(ctx, "exhibition.manage")
    venue = Venue(**data.model_dump(), created_by=ctx.user.id, updated_by=ctx.user.id)
    session.add(venue)
    await session.flush()
    await audit.record(
        session,
        entity_type="venue",
        entity_id=venue.id,
        action="create",
        after=audit.snapshot(venue, _VENUE_FIELDS),
    )
    await session.refresh(venue)
    return VenueOut.model_validate(venue)


async def update_venue(
    session: AsyncSession, ctx: AuthContext, venue_id: uuid.UUID, data: VenueUpdateIn
) -> VenueOut:
    """Edit a venue."""
    _require_global(ctx, "exhibition.manage")
    venue = await repo.get_venue(session, venue_id)
    if venue is None:
        raise NotFound("Venue not found.")
    check_version(venue.version, data.version)
    before = audit.snapshot(venue, _VENUE_FIELDS)
    _apply(venue, data.model_dump(exclude_unset=True, exclude={"version"}))
    venue.updated_by = ctx.user.id
    await session.flush()
    await audit.record(
        session,
        entity_type="venue",
        entity_id=venue.id,
        action="update",
        before=before,
        after=audit.snapshot(venue, _VENUE_FIELDS),
    )
    await session.refresh(venue)
    return VenueOut.model_validate(venue)


# --- exhibitions ---------------------------------------------------------------------------


async def list_exhibitions(
    session: AsyncSession, ctx: AuthContext, params: ExhibitionListParams
) -> Page[ExhibitionOut]:
    """Exhibitions the caller can see through at least one edition (or all, if global)."""
    rows, total = await repo.list_exhibitions(
        session, ctx.edition_ids(), params.q, params.is_active, params.offset, params.page_size
    )
    return Page(
        items=[ExhibitionOut.model_validate(r) for r in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def get_exhibition(
    session: AsyncSession, ctx: AuthContext, exhibition_id: uuid.UUID
) -> ExhibitionOut:
    ex = await repo.get_exhibition(session, exhibition_id, ctx.edition_ids())
    if ex is None:
        raise NotFound("Exhibition not found.")
    return ExhibitionOut.model_validate(ex)


async def create_exhibition(
    session: AsyncSession, ctx: AuthContext, data: ExhibitionIn
) -> ExhibitionOut:
    """Create an exhibition master record."""
    _require_global(ctx, "exhibition.manage")
    ex = Exhibition(**data.model_dump(), created_by=ctx.user.id, updated_by=ctx.user.id)
    session.add(ex)
    try:
        await session.flush()
    except IntegrityError as e:
        raise Conflict(
            "Exhibition code already exists.",
            code="DUPLICATE_EXHIBITION",
            fields={"code": "Already exists."},
        ) from e
    await audit.record(
        session,
        entity_type="exhibition",
        entity_id=ex.id,
        action="create",
        after=audit.snapshot(ex, _EXHIBITION_FIELDS),
    )
    await session.refresh(ex)
    return ExhibitionOut.model_validate(ex)


async def update_exhibition(
    session: AsyncSession, ctx: AuthContext, exhibition_id: uuid.UUID, data: ExhibitionUpdateIn
) -> ExhibitionOut:
    """Edit an exhibition (code is immutable: edition codes derive from it)."""
    ex = await repo.get_exhibition(session, exhibition_id, ctx.edition_ids())
    if ex is None:
        raise NotFound("Exhibition not found.")
    _require_global(ctx, "exhibition.manage")
    check_version(ex.version, data.version)
    before = audit.snapshot(ex, _EXHIBITION_FIELDS)
    _apply(ex, data.model_dump(exclude_unset=True, exclude={"version"}))
    ex.updated_by = ctx.user.id
    await session.flush()
    await audit.record(
        session,
        entity_type="exhibition",
        entity_id=ex.id,
        action="update",
        before=before,
        after=audit.snapshot(ex, _EXHIBITION_FIELDS),
    )
    await session.refresh(ex)
    return ExhibitionOut.model_validate(ex)


# --- editions ------------------------------------------------------------------------------


def _edition_out(edition: Edition, exhibition_code: str | None) -> EditionOut:
    out = EditionOut.model_validate(edition)
    out.exhibition_code = exhibition_code
    return out


async def list_editions(
    session: AsyncSession, ctx: AuthContext, params: EditionListParams
) -> Page[EditionOut]:
    """Editions in the caller's scope."""
    rows, total = await repo.list_editions(
        session,
        ctx.edition_ids(),
        params.exhibition_id,
        params.status,
        params.year,
        params.offset,
        params.page_size,
    )
    return Page(
        items=[_edition_out(e, code) for e, code in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def get_edition_entity(
    session: AsyncSession, ctx: AuthContext, edition_id: uuid.UUID
) -> Edition:
    """Load an edition after the scope check (404 when out of scope)."""
    ctx.scope_for(edition_id)
    edition = await repo.get_edition(session, edition_id)
    if edition is None:
        raise NotFound("Edition not found.", code="EDITION_NOT_FOUND")
    return edition


async def get_edition(session: AsyncSession, ctx: AuthContext, edition_id: uuid.UUID) -> EditionOut:
    edition = await get_edition_entity(session, ctx, edition_id)
    return _edition_out(edition, await repo.exhibition_code(session, edition.exhibition_id))


async def _check_venue(session: AsyncSession, venue_id: uuid.UUID | None) -> None:
    if venue_id is not None and await repo.get_venue(session, venue_id) is None:
        raise ValidationFailed(fields={"venue_id": "Unknown venue."})


async def create_edition(session: AsyncSession, ctx: AuthContext, data: EditionIn) -> EditionOut:
    """Create an edition and its Registration ID counter row."""
    _require_global(ctx, "edition.manage")
    ex_code = await repo.exhibition_code(session, data.exhibition_id)
    if ex_code is None:
        raise ValidationFailed(fields={"exhibition_id": "Unknown exhibition."})
    await _check_venue(session, data.venue_id)
    if errors := period_errors(data.model_dump()):
        raise ValidationFailed(fields=errors)
    code = data.code or default_edition_code(ex_code, data.year)
    values = data.model_dump(exclude={"code", "name", "registration_id_prefix"})
    edition = Edition(
        **values,
        code=code,
        name=data.name or code,
        registration_id_prefix=data.registration_id_prefix or code,
        status=EditionStatus.DRAFT,
        created_by=ctx.user.id,
        updated_by=ctx.user.id,
    )
    session.add(edition)
    try:
        await session.flush()
    except IntegrityError as e:
        msg = str(e.orig)
        if "email_account" in msg:
            raise ValidationFailed(fields={"email_account_id": "Unknown email account."}) from e
        if "exhibition_id_year" in msg:
            raise Conflict(
                "This exhibition already has an edition for that year.",
                code="DUPLICATE_EDITION",
                fields={"year": "Already has an edition."},
            ) from e
        raise Conflict(
            "Edition code already exists.",
            code="DUPLICATE_EDITION",
            fields={"code": "Already exists."},
        ) from e
    session.add(EditionCounter(edition_id=edition.id, last_value=0))
    await session.flush()
    await audit.record(
        session,
        entity_type="edition",
        entity_id=edition.id,
        action="create",
        after=audit.snapshot(edition, _EDITION_FIELDS),
        edition_id=edition.id,
    )
    await session.refresh(edition)
    return _edition_out(edition, ex_code)


async def update_edition(
    session: AsyncSession, ctx: AuthContext, edition_id: uuid.UUID, data: EditionUpdateIn
) -> EditionOut:
    """Edit an edition; status changes follow the lifecycle."""
    scope = ctx.scope_for(edition_id)
    if not scope.full_access:
        raise PermissionDenied()
    edition = await repo.get_edition(session, edition_id)
    if edition is None:
        raise NotFound("Edition not found.", code="EDITION_NOT_FOUND")
    check_version(edition.version, data.version)
    changes = data.model_dump(exclude_unset=True, exclude={"version"})
    if "status" in changes and not can_transition(edition.status, changes["status"]):
        raise ValidationFailed(
            f"Cannot move from {edition.status} to {changes['status']}.",
            code="INVALID_STATUS_TRANSITION",
            fields={"status": "Transition not allowed."},
        )
    if "venue_id" in changes:
        await _check_venue(session, changes["venue_id"])
    start = changes.get("start_date", edition.start_date)
    end = changes.get("end_date", edition.end_date)
    if end < start:
        raise ValidationFailed(fields={"end_date": "Must not be before start date."})
    merged = {f: changes.get(f, getattr(edition, f)) for f in EXHIBITOR_DATE_FIELDS}
    if errors := period_errors(merged):
        raise ValidationFailed(fields=errors)
    before = audit.snapshot(edition, _EDITION_FIELDS)
    _apply(edition, changes)
    edition.updated_by = current_actor_id()
    try:
        async with session.begin_nested():
            await session.flush()
    except IntegrityError as e:
        # The only foreign keys a PATCH can break: venue (checked above) and email account.
        raise ValidationFailed(fields={"email_account_id": "Unknown email account."}) from e
    await audit.record(
        session,
        entity_type="edition",
        entity_id=edition.id,
        action="update",
        before=before,
        after=audit.snapshot(edition, _EDITION_FIELDS),
        edition_id=edition.id,
    )
    await session.refresh(edition)
    return _edition_out(edition, await repo.exhibition_code(session, edition.exhibition_id))


async def ensure_writable(session: AsyncSession, edition_id: uuid.UUID) -> Edition:
    """Event data of an ARCHIVED edition is read-only."""
    edition = await repo.get_edition(session, edition_id)
    if edition is None:
        raise NotFound("Edition not found.", code="EDITION_NOT_FOUND")
    if edition.status == EditionStatus.ARCHIVED:
        raise ValidationFailed("This edition is archived.", code="EDITION_ARCHIVED")
    return edition


async def get_edition_by_id(session: AsyncSession, edition_id: uuid.UUID) -> Edition | None:
    """Internal lookup for other modules; callers have already checked scope."""
    return await repo.get_edition(session, edition_id)


async def get_edition_by_code(session: AsyncSession, code: str) -> Edition | None:
    """Internal lookup by edition code (public registration URL)."""
    return await repo.get_edition_by_code(session, code)


async def next_registration_id(session: AsyncSession, edition_id: uuid.UUID) -> str:
    """Next Registration ID for the edition: prefix + 6-digit counter (spec 5.1)."""
    edition = await repo.get_edition(session, edition_id)
    if edition is None:
        raise NotFound("Edition not found.", code="EDITION_NOT_FOUND")
    value = await repo.increment_counter(session, edition_id)
    return f"{edition.registration_id_prefix}{value:06d}"


async def edition_summaries(
    session: AsyncSession, edition_ids: set[uuid.UUID] | None
) -> list[EditionOut]:
    """Editions for /auth/me (edition switcher)."""
    rows, _ = await repo.list_editions(session, edition_ids, None, None, None, 0, 500)
    return [_edition_out(e, code) for e, code in rows]


@dataclass(frozen=True)
class PublicEditionInfo:
    """What a public campaign form may show about its edition (no internal settings)."""

    code: str
    name: str
    start_date: date
    end_date: date
    venue_name: str | None
    city: str | None
    country: str | None
    timezone: str
    active: bool


async def public_edition_info(session: AsyncSession, edition_id: uuid.UUID) -> PublicEditionInfo:
    """System use (campaign forms): the edition behind a valid campaign link."""
    edition = await repo.get_edition(session, edition_id)
    if edition is None:
        raise NotFound("Edition not found.")
    venue = await session.get(Venue, edition.venue_id) if edition.venue_id else None
    return PublicEditionInfo(
        code=edition.code,
        name=edition.name,
        start_date=edition.start_date,
        end_date=edition.end_date,
        venue_name=venue.name if venue else None,
        city=edition.city,
        country=edition.country,
        timezone=edition.timezone,
        active=edition.status == EditionStatus.ACTIVE,
    )
