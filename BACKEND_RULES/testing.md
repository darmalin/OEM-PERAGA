# Testing Rules

Spec §16. A feature is not done until its tests are merged.

## Layers

| Layer | Tool | Runs against | Required for |
|---|---|---|---|
| Unit | pytest | Pure functions (`rules.py`) | Normalization, duplicate table, telemarketing status, round robin, first/repeat entry, redaction |
| Integration | pytest + pytest-asyncio + httpx `AsyncClient` | Real PostgreSQL + Redis (compose services in CI) | Every endpoint, every constraint, every migration |
| Permission matrix | pytest parametrized | API | Every endpoint x every baseline role x scope (in / out) |
| Concurrency | pytest + `asyncio.gather` | Real PostgreSQL | Duplicate leads, Registration ID, attempt numbers, check-in, round robin |
| Idempotency | pytest | API + worker in eager mode and real mode | Registration, email job, scan sync, assignment |
| E2E | Playwright | Full compose stack | Telemarketing flow: import, assign, call, verify, register, QR email in Mailpit |
| Load | k6 or Locust | Staging | Lead list/filter, scan API |

## Rules
- No SQLite stand-in. Integration tests run on the same Postgres major version as production.
- Each test gets a clean state (transaction rollback per test, or truncate between tests).
- Factories (`factory_boy` or plain builders) for test data. Fixture names and emails are clearly fake (`lead-001@example.test`), never real people.
- Every migration is tested by `alembic upgrade head` then `alembic downgrade base` then `upgrade head` in CI.
- Spec tables become parametrized tests: the §5.2 duplicate table and the §6.2 status table are copied row for row.
- Coverage target: services and rules 90%+. Coverage is a signal, not the goal; missing a spec rule is a failure even at 100%.
- A bug fix comes with a test that fails before the fix.

## CI pipeline
1. `ruff check`, `ruff format --check`, `mypy`.
2. Unit tests.
3. Integration + permission + concurrency tests with Postgres and Redis services.
4. Migration up/down/up.
5. OpenAPI export and diff against the committed client (frontend types must be regenerated when the API changes).
