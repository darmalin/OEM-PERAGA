"""Campaign links: public lead forms per edition (owner request 2026-10-26).

Admins manage links per edition. Anyone with the link can register; the form never says
whether someone already exists. New leads are registered (QR active) but no email is sent
and nobody is assigned: both stay manual.
"""

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit, ratelimit
from app.core.authorization import AuthContext
from app.core.config import get_settings
from app.core.context import current_actor_id
from app.core.errors import Conflict, NotFound, ValidationFailed, check_version
from app.modules.campaigns import repository as repo
from app.modules.campaigns.models import CampaignLink, CampaignSubmission
from app.modules.campaigns.rules import (
    CONSENT_VERSION,
    TOKEN_RE,
    LinkState,
    SubmissionOutcome,
    form_ticket,
    ip_hash,
    link_state,
    new_token,
    poster_qr_png,
    ticket_ok,
)
from app.modules.campaigns.schemas import (
    CampaignLinkIn,
    CampaignLinkOut,
    CampaignLinkUpdateIn,
    PublicCampaignOut,
    PublicEdition,
    PublicField,
    PublicSubmissionIn,
    PublicSubmissionOut,
)
from app.modules.exhibitions import service as exhibitions_service
from app.modules.registrations import service as registrations_service
from app.modules.visitors import service as visitors_service
from app.modules.visitors.rules import UTM_FIELDS, LeadSource

ENTITY = "campaign_link"
MANAGE = "edition.manage"
AUDIT_FIELDS = (
    "name",
    "lead_source_id",
    "is_active",
    "starts_at",
    "ends_at",
    "max_submissions",
    "gtm_container_id",
)
FORM_FIELDS = ("first_name", "email", "phone", "company_name", "job_title", "country", "city")


def _key() -> bytes:
    """Signing key for form tickets and IP hashes, derived from the app secret."""
    secret = get_settings().app_encryption_key.get_secret_value()
    return hashlib.sha256(f"campaign-forms:{secret}".encode()).digest()


async def _state(session: AsyncSession, link: CampaignLink, now: datetime) -> LinkState:
    edition = await exhibitions_service.public_edition_info(session, link.edition_id)
    return link_state(
        is_active=link.is_active,
        starts_at=link.starts_at,
        ends_at=link.ends_at,
        max_submissions=link.max_submissions,
        submission_count=link.submission_count,
        edition_active=edition.active,
        now=now,
    )


async def _out(session: AsyncSession, link: CampaignLink) -> CampaignLinkOut:
    out = CampaignLinkOut.model_validate(link)
    out.url = f"{get_settings().public_base_url.rstrip('/')}/r/{link.token}"
    out.state = await _state(session, link, datetime.now(UTC))
    return out


# --- admin -----------------------------------------------------------------------------------


async def list_links(
    session: AsyncSession, ctx: AuthContext, edition_id: uuid.UUID | None
) -> list[CampaignLinkOut]:
    """Links of one edition, or of every edition the caller can read (filter choices)."""
    if edition_id is not None:
        ctx.scope_for(edition_id)
        editions: set[uuid.UUID] | None = {edition_id}
    else:
        editions = ctx.edition_ids()
    return [await _out(session, link) for link in await repo.list_links(session, editions)]


async def link_names(session: AsyncSession, edition_id: uuid.UUID) -> dict[uuid.UUID, str]:
    """System use (exports): campaign names of an edition by id."""
    return {link.id: link.name for link in await repo.list_links(session, {edition_id})}


async def poster_qr(
    session: AsyncSession, ctx: AuthContext, link_id: uuid.UUID
) -> tuple[bytes, str]:
    """(PNG, file name) of the link's QR, for anyone who may see the edition's links."""
    link = await repo.get_link(session, link_id)
    if link is None:
        raise NotFound("Campaign link not found.")
    try:
        ctx.scope_for(link.edition_id)
    except NotFound as e:
        raise NotFound("Campaign link not found.") from e
    out = await _out(session, link)
    safe = "".join(ch if ch.isalnum() else "-" for ch in link.name).strip("-").lower() or "campaign"
    return poster_qr_png(out.url), f"qr-{safe[:60]}.png"


async def _check_source(session: AsyncSession, source_id: uuid.UUID | None) -> None:
    if source_id is not None and not await visitors_service.lead_source_active(session, source_id):
        raise ValidationFailed(fields={"lead_source_id": "Not one of the allowed options."})


async def create_link(
    session: AsyncSession, ctx: AuthContext, data: CampaignLinkIn
) -> CampaignLinkOut:
    ctx.scope_for(data.edition_id, MANAGE)
    await exhibitions_service.ensure_writable(session, data.edition_id)
    await _check_source(session, data.lead_source_id)
    name = data.name.strip()
    if await repo.name_taken(session, data.edition_id, name):
        raise Conflict("This edition already has a link with that name.", fields={"name": "Taken."})
    link = CampaignLink(
        **data.model_dump(exclude={"name"}),
        name=name,
        token=new_token(),
        created_by=current_actor_id(),
        updated_by=current_actor_id(),
    )
    session.add(link)
    await session.flush()
    await session.refresh(link)
    await audit.record(
        session,
        entity_type=ENTITY,
        entity_id=link.id,
        action="create",
        after=audit.snapshot(link, AUDIT_FIELDS),
        edition_id=link.edition_id,
    )
    return await _out(session, link)


async def _managed_link(
    session: AsyncSession, ctx: AuthContext, link_id: uuid.UUID
) -> CampaignLink:
    link = await repo.get_link(session, link_id)
    if link is None:
        raise NotFound("Campaign link not found.")
    try:
        ctx.scope_for(link.edition_id, MANAGE)
    except NotFound as e:
        raise NotFound("Campaign link not found.") from e
    await exhibitions_service.ensure_writable(session, link.edition_id)
    return link


async def update_link(
    session: AsyncSession, ctx: AuthContext, link_id: uuid.UUID, data: CampaignLinkUpdateIn
) -> CampaignLinkOut:
    """Edit a link. The GTM container loads third-party scripts on the form: every change of
    it is in the audit log with the user who made it."""
    link = await _managed_link(session, ctx, link_id)
    check_version(link.version, data.version)
    changes: dict[str, Any] = data.model_dump(exclude_unset=True, exclude={"version"})
    if "name" in changes:
        if changes["name"] is None:
            raise ValidationFailed(fields={"name": "Enter a name."})
        changes["name"] = changes["name"].strip()
        if await repo.name_taken(session, link.edition_id, changes["name"], exclude=link.id):
            raise Conflict(
                "This edition already has a link with that name.", fields={"name": "Taken."}
            )
    if changes.get("is_active", True) is None:
        raise ValidationFailed(fields={"is_active": "Choose active or not."})
    if "lead_source_id" in changes and changes["lead_source_id"] != link.lead_source_id:
        await _check_source(session, changes["lead_source_id"])
    starts = changes.get("starts_at", link.starts_at)
    ends = changes.get("ends_at", link.ends_at)
    if starts is not None and ends is not None and ends <= starts:
        raise ValidationFailed(fields={"ends_at": "The end is before the start."})
    before = audit.snapshot(link, AUDIT_FIELDS)
    for key, value in changes.items():
        setattr(link, key, value)
    link.updated_by = current_actor_id()
    await session.flush()
    await session.refresh(link)
    after = audit.snapshot(link, AUDIT_FIELDS)
    if after != before:
        await audit.record(
            session,
            entity_type=ENTITY,
            entity_id=link.id,
            action="update",
            before=before,
            after=after,
            edition_id=link.edition_id,
        )
    return await _out(session, link)


async def new_link_token(
    session: AsyncSession, ctx: AuthContext, link_id: uuid.UUID
) -> CampaignLinkOut:
    """Replace the URL (e.g. it was shared where it should not be); the old one stops at once."""
    link = await _managed_link(session, ctx, link_id)
    link.token = new_token()
    link.updated_by = current_actor_id()
    await session.flush()
    await session.refresh(link)
    await audit.record(
        session,
        entity_type=ENTITY,
        entity_id=link.id,
        action="new_url",
        edition_id=link.edition_id,
    )
    return await _out(session, link)


# --- public form -----------------------------------------------------------------------------

CLOSED = "CAMPAIGN_CLOSED"


async def _open_link(
    session: AsyncSession, token: str, now: datetime, *, for_update: bool = False
) -> CampaignLink:
    """The link if it takes registrations. Unknown and closed links answer the same."""
    link = (
        await repo.link_by_token(session, token, for_update=for_update)
        if TOKEN_RE.match(token)
        else None
    )
    if link is None or await _state(session, link, now) != LinkState.OPEN:
        raise NotFound("This registration form is closed.", code=CLOSED)
    return link


async def public_form(session: AsyncSession, token: str) -> PublicCampaignOut:
    now = datetime.now(UTC)
    link = await _open_link(session, token, now)
    edition = await exhibitions_service.public_edition_info(session, link.edition_id)
    fields = await visitors_service.custom_field_definitions(session, link.edition_id)
    return PublicCampaignOut(
        edition=PublicEdition(
            name=edition.name,
            start_date=edition.start_date,
            end_date=edition.end_date,
            venue_name=edition.venue_name,
            city=edition.city,
            country=edition.country,
        ),
        custom_fields=[
            PublicField(
                key=f.field_key,
                label=f.label,
                type=f.field_type,
                required=f.required,
                options=list(f.options),
            )
            for f in fields
        ],
        gtm_container_id=link.gtm_container_id,
        consent_version=CONSENT_VERSION,
        ticket=form_ticket(_key(), link.token, now),
    )


async def public_submit(
    session: AsyncSession, token: str, data: PublicSubmissionIn, client_ip: str
) -> PublicSubmissionOut:
    """Register a visitor from a campaign form. New, duplicate, and bot posts get one answer."""
    s = get_settings()
    key = _key()
    hashed_ip = ip_hash(key, client_ip)
    await ratelimit.hit(f"campaign:ip:{hashed_ip}", s.campaign_submissions_per_ip_per_hour, 3600)
    now = datetime.now(UTC)
    # Row lock: the submission count and its limit stay exact under parallel posts.
    link = await _open_link(session, token, now, for_update=True)
    await ratelimit.hit(f"campaign:link:{link.id}", s.campaign_submissions_per_link_per_hour, 3600)
    accepted = PublicSubmissionOut()

    def log(outcome: SubmissionOutcome, lead_id: uuid.UUID | None = None) -> None:
        session.add(
            CampaignSubmission(
                campaign_link_id=link.id,
                ip_hash=hashed_ip,
                outcome=outcome,
                consent_version=CONSENT_VERSION,
                visitor_lead_id=lead_id,
            )
        )

    if data.contact_fax or not ticket_ok(key, link.token, data.ticket, now):
        log(SubmissionOutcome.BOT)
        return accepted

    values: dict[str, Any] = {k: getattr(data, k) for k in FORM_FIELDS}
    values["custom_fields"] = data.custom_fields or {}
    # A source switched off after the link was made is left out rather than failing the form.
    if link.lead_source_id and await visitors_service.lead_source_active(
        session, link.lead_source_id
    ):
        values["lead_source_id"] = link.lead_source_id
    try:
        lead = await visitors_service.insert_lead(
            session,
            link.edition_id,
            values,
            source=LeadSource.CAMPAIGN,
            campaign_link_id=link.id,
            utm={k: v for k in UTM_FIELDS if (v := getattr(data, k))},
        )
    except visitors_service.DuplicateVisitor:
        log(SubmissionOutcome.DUPLICATE)
        return accepted
    await registrations_service.register_new_lead(session, lead)  # QR active, no email
    link.submission_count += 1
    log(SubmissionOutcome.CREATED, lead.id)
    return accepted
