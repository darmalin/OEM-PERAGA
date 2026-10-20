import uuid
from datetime import UTC, datetime

import structlog

from app.core import outbox
from app.core.config import get_settings
from app.core.crypto import decrypt
from app.core.db import task_session
from app.core.email import OutgoingEmail, TransientEmailError, get_email_sender
from app.core.redis import new_redis
from app.modules.identity import repository as repo
from app.modules.identity.models import PasswordResetToken
from app.worker import celery_app, run_async

logger = structlog.get_logger("identity.tasks")


async def send_password_reset_email(event_id: uuid.UUID) -> bool:
    """Send the reset link once per outbox event. Returns True when an email went out."""
    done_key = f"task_done:{event_id}"
    async with new_redis() as redis:
        if await redis.exists(done_key):
            return False
    async with task_session() as session:
        event = await outbox.get_event(session, event_id)
        if event is None:
            return False
        reset = await session.get(PasswordResetToken, uuid.UUID(event.payload["reset_id"]))
        if reset is None or reset.used_at or reset.expires_at < datetime.now(UTC):
            return False
        user = await repo.get_user(session, reset.user_id)
        if user is None or not user.is_active:
            return False
        token = decrypt(event.payload["token_enc"])
    link = f"{get_settings().public_base_url}/reset-password?token={token}"
    get_email_sender().send(
        OutgoingEmail(
            to=user.email,
            subject="Reset your EMS password",
            text=f"Use this link to set a new password. It expires soon.\n\n{link}\n",
            html=(
                "<p>Use this link to set a new password. It expires soon.</p>"
                f'<p><a href="{link}">Reset password</a></p>'
            ),
        )
    )
    async with new_redis() as redis:
        await redis.set(done_key, "1", ex=7 * 24 * 3600)
    logger.info("password_reset_sent", event_id=str(event_id))
    return True


@celery_app.task(
    name="identity.send_password_reset",
    autoretry_for=(TransientEmailError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def send_password_reset(event_id: str) -> bool:
    return run_async(send_password_reset_email(uuid.UUID(event_id)))
