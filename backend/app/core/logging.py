import logging
import re
import sys
from typing import Any

import structlog

from app.core.context import actor_id_var, request_id_var

_EMAIL_RE = re.compile(r"^(.)[^@]*(@.*)$")


def mask_email(email: str | None) -> str | None:
    if not email:
        return email
    return _EMAIL_RE.sub(r"\1***\2", email)


def mask_phone(phone: str | None) -> str | None:
    if not phone or len(phone) < 4:
        return phone
    return "*" * (len(phone) - 3) + phone[-3:]


def _add_context(_: Any, __: str, event: dict[str, Any]) -> dict[str, Any]:
    if (rid := request_id_var.get()) is not None:
        event.setdefault("request_id", rid)
    if (uid := actor_id_var.get()) is not None:
        event.setdefault("user_id", str(uid))
    return event


def configure_logging(level: str = "INFO") -> None:
    """JSON logs, one event per line, with request_id and user_id when known."""
    shared: list[Any] = [
        structlog.contextvars.merge_contextvars,
        _add_context,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    structlog.configure(
        processors=[
            *shared,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
