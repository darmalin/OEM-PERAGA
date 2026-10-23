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

## Dashboard (2026-10-23, like the old system)

Admin > Dashboard (`report.view`), `GET /reports/dashboard?group_by=total|day|day_edition|day_source|day_user`. Tabs: Dashboard (tiles, breakdowns, daily trend), Today, Daily Comparison, Recap By Exhibition Type, Recap By Source, Recap By User. Email Report follows in phase 3.

Counts are **per call** in the date range (as the old dashboard), with the verification sent with that call (`visitor_verifications.call_id`, migration 0018):

| Number | Meaning |
|---|---|
| Added Leads | leads created in the range |
| Pending | leads never called by the end of the day (of the range for the totals) |
| Total Calls | all calls |
| Answer / Non Answer | first call answered / not answered |
| Recontacted / Retry No Answer | later calls answered / not answered (the old "Follow-up Answered / No Answer") |
| Valid / No Valid | calls with Lead Quality Valid / Invalid |
| Attend ... Hang Up Immediately | answered calls by Attend value |
| B2B Matching, B-Side, C-Side | calls with that verification value |

- Filters: dates, Country (only countries present in the leads), User and Team (the call's agent; for Added and Pending the lead owner), Exhibition Type (edition), Source, Status (current), Lead Quality, Buyer Type, Attend, B2B Matching (on the call's verification; for Added and Pending the lead's current values).
- Across editions, only editions the user may view reports in, each with its own scope. Days use the edition's timezone when one edition is filtered, else `EMS_REPORT_TIMEZONE` (default Asia/Jakarta; Vietnam is the same offset).
- Recap By User lists users with `telemarketing.call` in those editions; Group = their teams, Exhibition Type = editions of that grant ("All" for a global one). Leads without an owner show as Unassigned.
- Tables download as CSV (opens in Excel). Ranges up to 366 days.

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

## Hardening results (2026-10-20, dev stack)

Load test (`backend/scripts/seed_loadtest.py` + `backend/scripts/loadtest.py`): 50,000 leads,
5,000 registrations, 20 concurrent clients, 30 s per scenario, against the dev API (one
`uvicorn --reload` process; production runs gunicorn with 4 workers). No 5xx in any run.

| Scenario | RPS | p50 | p95 | p99 |
|---|---|---|---|---|
| Lead list/filter (random page, source, country, search, status) | 96.6 | 174 ms | 386 ms | 478 ms |
| Gate scan, online, before the fix below | 72.1 | 201 ms | 763 ms | 1,222 ms |
| Gate scan, online, after the fix | 114.1 | 172 ms | 189 ms | 272 ms |

Fix found by the test: every scan updated `scanner_devices.last_seen_at` on the same row,
so concurrent scans queued on its row lock. It is now written at most once a minute.

These are baselines, not targets. Targets still need the expected volume (leads per
edition, scanners per gate, concurrent agents) from the business; rerun the same scripts
on staging with production settings.

Backup/restore drill (`deployments/backup/drill.sh`): PASS, 40 tables, 2,603 rows.

Security pass: route guard test fixed so it really checks all 89 routes (it checked none
under FastAPI 0.151); API responses carry CSP `default-src 'none'`, X-Frame-Options,
nosniff, Referrer-Policy, Permissions-Policy; nginx re-resolves the api container.
Not done here: dependency vulnerability scan (`pip-audit` is not in the image), HSTS
(belongs to the TLS terminator), penetration test.
