# Database Rules (PostgreSQL + SQLAlchemy + Alembic)

## Identifiers and naming
- Tables: plural `snake_case` (`visitor_leads`). Columns: `snake_case`. English only.
- Primary key: `id UUID` (UUIDv7 generated in the app for index locality). Business identifiers (Registration ID, edition code) are separate unique columns.
- Foreign keys: `<entity>_id`. Always indexed.
- Constraint naming convention set on `MetaData` so Alembic produces stable names (`pk_`, `fk_`, `uq_`, `ix_`, `ck_`).

## Standard columns
Every mutable business table has `created_at`, `updated_at` (`timestamptz`, default `now()`), `created_by`, `updated_by`. Tables edited from forms also have `version INTEGER` for optimistic locking.

Append-only tables (`audit_logs`, `visitor_call_activities`, `lead_assignment_history`, `visitor_verifications` history, `scan_attempts`) have only `created_at`/`occurred_at`; the app's DB role has no `UPDATE`/`DELETE` on them.

## Edition scoping
- Every event-data table carries `edition_id NOT NULL` with an FK, even when it could be reached through a join. This keeps scope filters simple and indexes effective.
- Composite indexes start with `edition_id` (`(edition_id, telemarketing_status)`, `(edition_id, lead_owner_id)`, `(edition_id, updated_at DESC)`).
- Repositories take a `Scope` argument and apply it in one place (`apply_scope(stmt, scope)`). A repository function without a `Scope` parameter on event data fails review.
- Optional hardening later: Postgres Row Level Security as a second line. Not a replacement for app-level scope.

## Integrity in the database
- Duplicate rules: partial unique indexes
  `CREATE UNIQUE INDEX uq_visitor_leads_edition_email ON visitor_leads (edition_id, email_normalized) WHERE email_normalized IS NOT NULL;` and the same for phone.
- `CHECK (email_normalized IS NOT NULL OR phone_normalized IS NOT NULL)`.
- `CHECK (NOT (is_valid_lead AND is_invalid))`.
- Enums: `CHECK (col IN (...))` or Postgres enum types; prefer `CHECK` + text for easier migrations.
- `UNIQUE (exhibition_id, year)` on editions. `UNIQUE (scan_event_id)` on scan attempts. `UNIQUE (idempotency_key)` where used.
- Empty strings are converted to `NULL` before insert (normalization layer), never stored.

## Counters and sequences
- Registration ID: per-edition counter row, incremented with `UPDATE ... RETURNING` inside the transaction. Never `COUNT(*)` or `MAX()+1`.
- Attempt numbers: lock the lead row (`SELECT ... FOR UPDATE`) then compute.

## Concurrency
- Optimistic locking on form updates: `UPDATE ... WHERE id = :id AND version = :v`; 0 rows = `409 Conflict`.
- Pessimistic locks (`FOR UPDATE`) only for counters, attempt numbers, round-robin cursors. Keep those transactions short.
- Default isolation `READ COMMITTED`. Do not raise it globally.

## JSONB
- Only for `custom_fields`, audit `before`/`after`, and job payloads. Never store core fields in JSONB.
- Custom field values validated against active definitions before write. GIN index only when a filter on a custom field is actually needed.

## Migrations (Alembic)
- One migration per change, reviewed like code. Autogenerate is a draft; read and fix it.
- Every migration has a working `downgrade()` unless it is explicitly irreversible (data drop), which needs approval and a comment.
- No data backfill mixed into schema changes on large tables: separate migration or a worker task.
- Creating indexes on large tables: `CREATE INDEX CONCURRENTLY` (in its own non-transactional migration).
- Never edit a migration that has run in a shared environment.
- Seed data (roles, permissions, fixed options) via idempotent migration or a `seed` command, not by hand.

## Queries
- Use SQLAlchemy Core/ORM 2.0 `select()` style. Raw SQL only through `text()` with bound parameters, never f-strings.
- List endpoints always paginate; no unbounded `SELECT`.
- Avoid N+1: `selectinload`/`joinedload` or explicit joins. Check report queries with `EXPLAIN ANALYZE` on realistic data.

## Backup
- Daily `pg_dump` (or WAL archiving in prod), stored off the DB host. A restore drill is part of M6 and must be run, not just documented.
