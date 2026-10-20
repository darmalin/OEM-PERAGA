# 04 Audit Log

Spec §10. Rules in `BACKEND_RULES/security-permissions.md`.

## Data
`audit_logs`: `id`, `occurred_at`, `actor_user_id` (nullable for system), `source` (`UI`, `API`, `IMPORT`, `WORKER`, `SCANNER`), `edition_id`, `entity_type`, `entity_id`, `action`, `before` (JSONB), `after` (JSONB), `request_id`.

Append-only: no update or delete from the application. The DB role used by the app has no `UPDATE`/`DELETE` grant on this table.

## Covered actions
Lead create/update, verification change, assignment, call attempt, follow-up create/reschedule/complete/cancel, registration, QR issue/resend/revoke, gate and device config, scanner sync rejections, import start/finish, export, user/role changes, login success/failure.

## Tasks
- [ ] Table + grants + index on `(entity_type, entity_id, occurred_at)` and `(edition_id, occurred_at)`.
- [ ] `audit.record(...)` helper called inside the same DB transaction as the change.
- [ ] Redaction list: password, session token, CSRF token, QR token, provider credentials never stored. Unit test that asserts this.
- [ ] Diff helper: store only changed fields in `before`/`after`.
- [ ] `GET /audit-logs` (needs `audit_log.read`), filter by entity, actor, date.
- [ ] Activity timeline on every form view (Frappe-style "Activity" at the bottom).

## Acceptance criteria
- Rolling back a transaction also rolls back its audit entry.
- No secret value appears in `audit_logs` (test with fixtures).
