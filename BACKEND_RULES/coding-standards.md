# Coding Standards (Python)

## Tooling
- `ruff format` + `ruff check` (rules: E, F, I, B, UP, SIM, ASYNC, S, N, RUF). CI fails on any finding.
- `mypy --strict` on `app/`. No `Any` in public function signatures. `# type: ignore` needs an error code and a reason.
- Python 3.13 syntax: `X | None`, `list[str]`, `match` where it helps.

## Naming
- English only. `snake_case` functions and variables, `PascalCase` classes, `UPPER_SNAKE` constants and enum members.
- Domain words match the spec: `visitor_lead`, `edition`, `call_activity`, `followup`, `registration`, `qr_credential`, `scan_attempt`, `checkin`.
- Enums are `StrEnum` with values equal to the spec strings (`TelemarketingStatus.RETRY_NO_ANSWER = "RETRY_NO_ANSWER"`). Display labels are a frontend concern.

## Async
- Route handlers, services, and repositories are `async def`.
- No blocking calls in async code (`requests`, `time.sleep`, sync file I/O, `openpyxl` on large files). Those run in Celery or `run_in_threadpool`.
- Never share an `AsyncSession` across concurrent tasks.

## Errors
- Raise domain errors from `core/errors.py`: `NotFound`, `PermissionDenied`, `Conflict`, `ValidationFailed`, `IdempotencyMismatch`, `RateLimited`. Handlers map them to HTTP.
- Never return raw exception messages or stack traces to clients.
- Catch `IntegrityError` at the repository/service boundary and convert unique violations into `Conflict` with the field name.
- Do not use bare `except:` or `except Exception: pass`.

## Functions and modules
- Business rules that can be pure (normalization, status derivation, round robin ordering, first/repeat decision) live in `rules.py` and get table-driven unit tests.
- Keep functions small enough to test. A service function does one use case.
- No global mutable state. Dependencies come through FastAPI `Depends` or function arguments.

## Comments and docs
- Comment the why, not the what. Reference the spec section when a rule comes from it (`# spec 5.2: empty values stored as NULL`).
- Every public service function has a one-line docstring.

## Logging
- `structlog` (or stdlib `logging` with JSON formatter), one event per line, with `request_id`, `user_id`, `edition_id` when known.
- Never log: passwords, session IDs, CSRF tokens, QR tokens, device secrets, full email bodies, full Excel rows. Mask emails and phones in logs (`q***@gmail.com`).

## Dependencies
- Add a dependency only with a reason in the PR. Pin through `uv.lock`. Run `pip-audit` (or `uv` equivalent) in CI.
