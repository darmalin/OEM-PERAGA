# 10 Reporting, Dashboard, Export

Spec §11, §15 M6.

## Reports (minimum)
| Report | Metrics |
|---|---|
| Lead overview | total, new, assigned, unassigned |
| Telemarketing | attempts, answer rate, follow-ups due / overdue |
| Verification | valid, invalid, attendance intention (by Attend value) |
| Registration | registered, QR issued, email status |
| Attendance | unique daily visitors, unique event visitors, first entry, repeat entry |
| Gate | scans per gate, per hour, per day |
| Agent performance | leads handled, attempts, follow-up completion |
| Import | processed, rejected, duplicate, error |
| Email | queued, sent, failed, provider status |

Filters: edition, date range, country, source, lead owner / team, telemarketing status, verification, registration / QR status, gate.

## Rules
- Every report query goes through the same scope filter as list endpoints.
- Dashboard refreshes by polling (e.g. 30 s), no websockets in phase 1.
- Numbers come from the database only. No placeholder values in the UI; empty data shows an empty state.
- Export (`report.export` / `visitor.export`) runs in the worker, writes `.xlsx` to storage, returns a short-lived signed URL, and writes an audit entry.

## Tasks
- [ ] Report queries (SQL views or explicit queries) with indexes checked by `EXPLAIN`.
- [ ] `GET /reports/visitors?type=...`, `POST /exports/visitors`, `GET /exports/{id}`.
- [ ] `export_jobs` table, expiry and cleanup task.
- [ ] Dashboard screen per `DESIGN/DESIGN.md` (built around the questions each role asks, not a generic stat grid).
- [ ] Report pages with filter bar and table, export button.

## Hardening (M6)
- [ ] Load test: lead list/filter and scan API (k6 or Locust), with targets set from expected volume.
- [ ] Security review: permission matrix, rate limits, headers, dependency audit.
- [ ] Backup (`pg_dump` schedule + MinIO bucket) and a documented restore drill that has actually been run.
