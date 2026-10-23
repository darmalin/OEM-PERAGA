# Known Gaps (Backend)

What is missing, unverified, or knowingly simplified in the backend as of 2026-10-20
(commit `623974e`). Read this before starting backend work, and update it in the same PR
that closes or adds a gap.

Priority: **P1** must be closed before production, **P2** before the first event at scale,
**P3** improvement.

## Bugs

| # | Pri | Gap | Where | Fix |
|---|---|---|---|---|
| B1 | P2 | `create-superuser` for an existing email does not change the password, and adds a second SUPER_ADMIN assignment on every run. | `app/modules/identity/service.py` `create_superuser` | Skip the assignment when it exists; decide whether re-running should reset the password (explicit flag), and test both. |

## Security

| # | Pri | Gap | Where | Fix |
|---|---|---|---|---|
| S1 | P1 | No dependency vulnerability scan has been run. `pip-audit` is not in the image. | CI, `pyproject.toml` | Add `pip-audit` (or equivalent) to the dev group and CI; fix or document findings. |
| S2 | P1 | No HSTS / TLS config. nginx listens on plain port 80. | `deployments/nginx/default.conf` | Configure TLS at the terminator in front of nginx (or in nginx) with HSTS. |
| S3 | P1 | Public website registration has no CORS allowance for the website origin, so a browser form on another domain cannot call it. | `app/main.py`, `/api/v1/public/*` | CORS only for the configured website origin, only on `/public/*` (BACKEND_RULES/security-permissions.md). |
| S4 | P2 | Public registration has rate limit + honeypot but no captcha. | `app/modules/registrations/service.py` `public_register` | Optional captcha check behind a setting, verified server-side. |
| S5 | P2 | nginx sends `Permissions-Policy: camera=()`, which will block the scanner PWA camera once it is served from nginx. | `deployments/nginx/default.conf` | `camera=(self)` on the scanner location only. |
| S6 | P2 | No penetration test or external security review yet. | | Schedule before go-live. |

## Open business decisions still on defaults

Defaults are in code; changing them later may need a migration. Full list in `FEATURES/README.md`.

| # | Decision | Current default in code |
|---|---|---|
| D2 | Import creates registration + QR? | `LEADS_AND_REGISTER` rejected; imports create leads only (`importexport/service.py`). |
| D4 | Follow-up reminder interval / send time | Off: `EMS_FOLLOWUP_REMINDERS_ENABLED=false`. |
| D6 | Offline cache lifetime, lost-device policy | 12 h (`EMS_SCANNER_CACHE_TTL_SECONDS`, per-edition override); manual revoke. |
| D7 | Extra call results | `ANSWER` / `NO_ANSWER` + `EMS_CALL_RESULTS_EXTRA`. |
| D9 | Retention of PII, audit log, scan data | Keep everything; no purge job exists. |
| D10 | API upsert of existing visitors | Not supported; create or update by ID only. |
| D11 | Email and Phone both marked `*` in the screenshot | Rule implemented as "at least one of the two" (spec 5.2). |

## Features not built

| # | Pri | Gap | Fix |
|---|---|---|---|
| F1 | P2 | Registration cancel: `CANCELLED` exists in the schema and the gate rejects it, but no endpoint sets it. | `POST /visitor-registrations/{id}/cancel` that revokes the QR, updates the lead, audits. |
| F2 | P2 | Email delivery status from the provider (bounces, deferrals) is not tracked; `SENT` means the SMTP server accepted it. | Provider webhook or bounce mailbox into `email_logs`. |
| F3 | P2 | Gate scans are attributed to the device, not to the gate staff member using it. | Optional staff session on device calls, stored as `recorded_by`. |
| F4 | P3 | QR email delivery is at-least-once: a worker crash after the SMTP call and before `SENT` is committed sends the email again. | Accept, or use a provider idempotency key if the provider supports one. |
| F5 | P3 | Retention purge job (depends on D9). | Celery Beat task per retention rule. |

## Performance and scale

Measured baselines are in `FEATURES/10-reporting-export.md`. Targets are not set yet.

| # | Pri | Gap | Fix |
|---|---|---|---|
| P1 | P1 | No performance targets. The load test ran only on the dev stack (one `uvicorn --reload` process). | Get expected volume from the business; rerun `scripts/loadtest.py` on staging with gunicorn and production settings. |
| P2 | P2 | Lead search uses `LIKE '%term%'` without a trigram index, so it scans the edition. | `pg_trgm` GIN indexes on the searched columns (`CREATE INDEX CONCURRENTLY`), checked with `EXPLAIN ANALYZE`. |
| P3 | P2 | Lead list runs `count(*)` on every request. | Keep for now; switch to keyset pagination without totals for very large editions (BACKEND_RULES/api.md allows it). |
| P4 | P2 | The offline cache is sent in full on every refresh (all credentials of the edition). | Incremental `?since=` cache updates. |
| P5 | P3 | Excel export builds the whole file in memory before upload. | Fine at 100k rows; stream to a temp file if exports grow past that. |

## Operations

| # | Pri | Gap | Fix |
|---|---|---|---|
| E1 | P2 | Email account passwords are encrypted with `EMS_APP_ENCRYPTION_KEY`; there is no key rotation, and a lost key means re-entering every account password (QR tokens: revoke and reissue). | Keep the key in a password manager; add a rotation command if the key must ever change. |
| E2 | P3 | Email accounts support SMTP with a password only; no OAuth (Google, Microsoft 365). | Use app passwords; add OAuth if the providers require it. |
| O1 | P1 | Backups are scripts only; nothing schedules them or copies them off the host. | Cron/systemd timer for `deployments/backup/backup.sh` + off-host copy. |
| O2 | P2 | The drill restores the database only; restoring the storage tarball has not been tested. Storage is copied while running (not a consistent snapshot). | Add a file restore step to `drill.sh`; snapshot or `aws s3 sync` for production storage. |
| O3 | P3 | The dev database holds test data: edition `E2EQR2027`, `LOADTEST2027`/`2028`/`2029` (~100k leads), user `e2e-admin@example.test`. Append-only triggers block deleting their scans. | Reset the dev database (`docker compose down -v`, then migrate) when it gets in the way. |
| O4 | P3 | `scripts/loadtest.py` needs `httpx`, which is a dev dependency only. | Run it from the dev image, or install `httpx` where it runs. |
