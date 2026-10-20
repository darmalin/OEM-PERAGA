import asyncio
import uuid
from collections.abc import Coroutine
from typing import Any

import structlog
from celery import Celery, Task
from celery.signals import before_task_publish, task_prerun, worker_process_init
from kombu import Queue

from app.core.config import get_settings
from app.core.context import Source, request_id_var, source_var
from app.core.logging import configure_logging

logger = structlog.get_logger("worker")

celery_app = Celery("ems", broker=get_settings().celery_broker_url)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_ignore_result=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
    task_queues=[Queue(q) for q in ("default", "email", "import", "export", "reports")],
    timezone="UTC",
    beat_schedule={
        "dispatch-outbox": {"task": "core.dispatch_outbox", "schedule": 5.0},
    },
)


@before_task_publish.connect
def _propagate_request_id(headers: dict[str, Any] | None = None, **_: Any) -> None:
    if headers is not None and (rid := request_id_var.get()):
        headers.setdefault("request_id", rid)


@task_prerun.connect
def _set_task_context(task: "Task[Any, Any] | None" = None, **_: Any) -> None:
    rid = getattr(task.request, "request_id", None) if task else None
    request_id_var.set(rid or uuid.uuid4().hex)
    source_var.set(Source.WORKER)


@worker_process_init.connect
def _init_logging(**_: Any) -> None:
    configure_logging(get_settings().log_level)


def run_async[T](coro: Coroutine[Any, Any, T]) -> T:
    """Celery tasks are sync; each runs its coroutine in a fresh event loop."""
    return asyncio.run(coro)


# Every module with Celery tasks is listed here.
celery_app.conf.include = [
    "app.core.tasks",
    "app.modules.identity.tasks",
    "app.modules.importexport.tasks",
]
