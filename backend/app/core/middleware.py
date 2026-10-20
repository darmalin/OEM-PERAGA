import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import FastAPI, Request, Response

from app.core.context import Source, actor_id_var, request_id_var, source_var

logger = structlog.get_logger("http")

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
# The API only returns JSON, so nothing in a response may load or run. Swagger UI (dev
# only, /docs) needs its scripts, so it is left out.
_API_CSP = "default-src 'none'; frame-ancestors 'none'"


def install_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get("X-Request-ID", "")
        rid = incoming if 0 < len(incoming) <= 64 and incoming.isprintable() else uuid.uuid4().hex
        request_id_var.set(rid)
        actor_id_var.set(None)
        source_var.set(Source.UI)
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        for k, v in _SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        if not request.url.path.endswith("/docs"):
            response.headers.setdefault("Content-Security-Policy", _API_CSP)
        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        return response
