# Backend Rules

Rules for the FastAPI backend. Stack in `TECH_STACK.md`. Every rule here is a review gate: a PR that breaks one is not merged.

| File | Covers |
|---|---|
| [architecture.md](architecture.md) | Modular monolith, module layout, dependencies between modules |
| [coding-standards.md](coding-standards.md) | Python style, typing, naming, errors |
| [database.md](database.md) | PostgreSQL, SQLAlchemy, Alembic, constraints, scoping, IDs |
| [api.md](api.md) | Routes, schemas, error envelope, pagination, idempotency |
| [security-permissions.md](security-permissions.md) | Auth, sessions, permission + scope checks, audit, PII |
| [jobs-integrations.md](jobs-integrations.md) | Celery, outbox, email, storage, Excel |
| [testing.md](testing.md) | Test layers and what must be covered |

## The ten non-negotiables (spec §1.3, §18)

1. English everywhere: identifiers, messages, logs, comments.
2. Every query on event data filters by `edition_id` and the caller's scope.
3. Permissions are checked in the backend on every endpoint. The frontend hiding a button is not security.
4. Uniqueness and integrity rules live in the database (constraints, partial unique indexes), and the API also handles their violations.
5. Every important change writes an audit entry in the same transaction.
6. Email, import, export, and anything slow runs in the worker, never in the request.
7. Retriable operations (registration, QR email, scan sync, assignment batches) are idempotent.
8. History is append-only: call attempts, assignments, verification history, audit log, scan attempts are never updated or deleted.
9. No single generic `status` that mixes telemarketing, registration, verification, and attendance.
10. Every migration, endpoint, and permission comes with tests.
