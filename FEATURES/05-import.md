# 05 Excel Import

Spec §5.2, §15 M2. Open decision D2 (does import create registrations).

## Flow
1. User uploads `.xlsx` (needs `visitor.import`). File goes to S3/MinIO; `import_jobs` row created with status `QUEUED`. Request returns immediately with the job ID.
2. Worker streams rows (`openpyxl` read-only), maps columns, normalizes, validates, inserts in batches. Each row is its own savepoint so one bad row never fails the batch.
3. Failed rows go to `import_errors` (row number, reason code, message, safe subset of the row).
4. Job ends `COMPLETED` / `COMPLETED_WITH_ERRORS` / `FAILED`, with counts: processed, created, duplicate, invalid.

## Tasks
- [ ] `import_jobs`, `import_errors` tables.
- [ ] Downloadable template per edition (core + active custom fields with `in_import`).
- [ ] Column mapping step (header matching, manual override, saved per edition).
- [ ] `POST /visitor-leads/imports`, `GET /visitor-leads/imports/{id}`, `GET /visitor-leads/imports/{id}/errors` (and as `.xlsx`).
- [ ] Import type setting: `LEADS_ONLY` vs `LEADS_AND_REGISTER` (behind D2; default `LEADS_ONLY`).
- [ ] Max file size + row limit enforced in nginx and API.
- [ ] Import wizard UI: upload, map, confirm, progress (polling), result with error table.
- [ ] Audit: job start and finish.

## Acceptance criteria
- A 50k-row file does not block any API request.
- Duplicate inside the same file and duplicate against existing data are both reported per row.
- Re-running the same file creates no new leads (all rows become duplicates).
