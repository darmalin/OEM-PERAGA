# Architecture

## Modular monolith

One FastAPI app (`api`) and one Celery app (`worker`, `beat`) built from the same codebase and image. Modules are separated by domain, not by technical layer.

```text
backend/app/
├── main.py                 # create_app(): routers, middleware, exception handlers
├── worker.py               # Celery app, task autodiscovery
├── core/
│   ├── config.py           # Settings (pydantic-settings)
│   ├── db.py               # engine, async session, Base, naming convention
│   ├── auth.py             # session load, current_user dependency, CSRF
│   ├── authorization.py    # require(permission), Scope, scope filters
│   ├── audit.py            # audit.record()
│   ├── errors.py           # AppError hierarchy + handlers
│   ├── idempotency.py
│   ├── outbox.py
│   ├── email.py            # EmailSender protocol + SMTP/provider impls
│   ├── storage.py          # S3 client
│   └── logging.py
└── modules/
    └── visitors/
        ├── models.py       # SQLAlchemy models
        ├── schemas.py      # Pydantic request/response models
        ├── repository.py   # queries; every function takes a Scope
        ├── service.py      # business rules, transactions, audit calls
        ├── router.py       # HTTP layer only
        ├── tasks.py        # Celery tasks for this module
        └── rules.py        # pure functions (normalization, status derivation)
```

Modules: `identity`, `exhibitions`, `visitors`, `telemarketing`, `registrations`, `checkin`, `importexport`, `reporting`, `mail`.

`mail` owns email accounts and the email queue/log (`email_jobs`). Every module that sends email queues it with `mail.service.queue_email` and delivers it in its task through `mail.tasks.deliver`, so every email is logged and goes through the right account.

## Layer rules

| Layer | May do | Must not do |
|---|---|---|
| `router.py` | Parse request, call one service function, return schema | Query the DB, contain business rules, commit |
| `service.py` | Business rules, orchestrate repositories, call `audit.record`, enqueue outbox events | Know about HTTP (`Request`, status codes) |
| `repository.py` | SQLAlchemy queries, always with `Scope` | Commit, call other modules' repositories |
| `rules.py` | Pure functions, no I/O | Import SQLAlchemy or FastAPI |
| `tasks.py` | Thin wrapper that opens a session and calls a service | Hold business logic |

## Cross-module calls

- A module calls another module only through that module's `service.py` public functions. Never import another module's `models.py` to query it directly (exception: foreign keys and relationships in models).
- Exception: `reporting` is read-only and may query other modules' tables directly for aggregate reports. It never writes, and it still applies scope through `visitors.filtered_lead_ids(scope, filters)` and the gate scope clause.
- No circular imports between modules. If two modules need each other, the shared piece moves to `core/` or a new module.
- Cross-module side effects (send QR email after registration) go through the outbox, not direct calls.

## Transactions

- One unit of work per request: the session dependency opens a transaction and commits at the end if no exception.
- Services do not call `commit()`. Use `session.flush()` when an ID is needed mid-transaction.
- Worker tasks open their own session per task (or per batch for imports).

## Configuration

- All config from environment variables via `Settings`. No config in code, no `.env` committed (only `.env.example`).
- Secrets (DB password, SMTP, S3 keys, app encryption key) never logged, never returned by any endpoint.

## Time

- Store all timestamps as `timestamptz` in UTC.
- Edition-local dates (daily unique visitors, first/repeat entry) are computed with the edition's IANA timezone, in SQL (`AT TIME ZONE`) or `zoneinfo`.
