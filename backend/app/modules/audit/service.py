import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditLog
from app.core.authorization import AuthContext
from app.core.pagination import Page
from app.modules.audit import repository as repo
from app.modules.audit.schemas import AuditLogOut, AuditLogParams


def _out(log: AuditLog, actor_name: str | None) -> AuditLogOut:
    out = AuditLogOut.model_validate(log)
    out.actor_name = actor_name
    return out


async def list_logs(
    session: AsyncSession, ctx: AuthContext, params: AuditLogParams
) -> Page[AuditLogOut]:
    """Audit search. Edition-limited readers only see rows of their editions."""
    allowed = ctx.edition_ids()
    if allowed is not None:
        # Non-global readers must have full (EDITION) scope on the editions they read.
        allowed = {e for e in allowed if ctx.scope_for(e).full_access}
        if params.edition_id is not None:
            ctx.scope_for(params.edition_id)
    rows, total = await repo.list_logs(
        session,
        edition_ids=allowed,
        edition_id=params.edition_id,
        entity_type=params.entity_type,
        entity_id=params.entity_id,
        actor_user_id=params.actor_user_id,
        action=params.action,
        occurred_from=params.occurred_from,
        occurred_to=params.occurred_to,
        offset=params.offset,
        limit=params.page_size,
    )
    return Page(
        items=[_out(log, name) for log, name in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def entity_timeline(
    session: AsyncSession, edition_id: uuid.UUID, entity_type: str, entity_id: uuid.UUID
) -> list[AuditLogOut]:
    """Activity timeline for one record. Callers check access to the record first."""
    rows = await repo.entity_timeline(session, edition_id, entity_type, entity_id)
    return [_out(log, name) for log, name in rows]
