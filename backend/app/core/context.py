"""Per-request (or per-task) context propagated through contextvars."""

import uuid
from contextvars import ContextVar
from enum import StrEnum


class Source(StrEnum):
    UI = "UI"
    API = "API"
    IMPORT = "IMPORT"
    WORKER = "WORKER"
    SCANNER = "SCANNER"
    PUBLIC = "PUBLIC"  # campaign forms: no login


request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
actor_id_var: ContextVar[uuid.UUID | None] = ContextVar("actor_id", default=None)
source_var: ContextVar[Source] = ContextVar("source", default=Source.UI)


def current_request_id() -> str | None:
    return request_id_var.get()


def current_actor_id() -> uuid.UUID | None:
    return actor_id_var.get()


def current_source() -> Source:
    return source_var.get()
