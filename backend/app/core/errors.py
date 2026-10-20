import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.context import current_request_id

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code = 400
    code = "BAD_REQUEST"
    default_message = "Bad request."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        fields: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.default_message
        if code:
            self.code = code
        self.fields = fields or {}
        super().__init__(self.message)


class NotAuthenticated(AppError):
    status_code = 401
    code = "NOT_AUTHENTICATED"
    default_message = "Login required."


class PermissionDenied(AppError):
    status_code = 403
    code = "PERMISSION_DENIED"
    default_message = "You do not have permission to perform this action."


class NotFound(AppError):
    status_code = 404
    code = "NOT_FOUND"
    default_message = "Not found."


class Conflict(AppError):
    status_code = 409
    code = "CONFLICT"
    default_message = "Conflict."


class VersionConflict(Conflict):
    code = "VERSION_CONFLICT"
    default_message = "The record was changed by someone else. Reload and try again."


class IdempotencyMismatch(Conflict):
    code = "IDEMPOTENCY_KEY_REUSED"
    default_message = "Idempotency key was already used with a different request."


class ValidationFailed(AppError):
    status_code = 422
    code = "VALIDATION_FAILED"
    default_message = "Validation failed."


class RateLimited(AppError):
    status_code = 429
    code = "RATE_LIMITED"
    default_message = "Too many requests. Try again later."


def error_body(code: str, message: str, fields: dict[str, str] | None = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "fields": fields or {},
            "request_id": current_request_id(),
        }
    }


async def _app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AppError):
        raise exc
    return JSONResponse(error_body(exc.code, exc.message, exc.fields), status_code=exc.status_code)


def _loc_to_field(loc: tuple[Any, ...]) -> str:
    parts = [str(p) for p in loc if p not in ("body", "query", "path", "header", "cookie")]
    return ".".join(parts) or "request"


async def _validation_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    fields: dict[str, str] = {}
    for err in exc.errors():
        fields.setdefault(_loc_to_field(tuple(err.get("loc", ()))), str(err.get("msg", "Invalid")))
    return JSONResponse(
        error_body("VALIDATION_FAILED", "Validation failed.", fields), status_code=422
    )


async def _http_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        raise exc
    code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 401: "NOT_AUTHENTICATED"}.get(
        exc.status_code, "HTTP_ERROR"
    )
    message = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return JSONResponse(error_body(code, message), status_code=exc.status_code)


async def _unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_error", exc_info=exc)
    return JSONResponse(error_body("INTERNAL_ERROR", "Internal server error."), status_code=500)


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(StarletteHTTPException, _http_handler)
    app.add_exception_handler(Exception, _unhandled_handler)
