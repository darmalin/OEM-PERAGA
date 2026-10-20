# 02 Exhibitions and Editions

Spec §3.

## Data
- `exhibitions`: master (code like `IBTE`, name, active).
- `exhibition_editions`: `exhibition_id`, `year`, `code` (`IBTE2027`), start/end date, `venue_id`, country, city, timezone (IANA), default currency, registration ID prefix, status, email config, registration config, gate settings.
- `venues`.
- Edition access: which teams/users can access (via scoped role assignments in 01).

Constraints: `UNIQUE (exhibition_id, year)`, `UNIQUE (code)`, `end_date >= start_date`.

## Tasks
- [ ] Models, migration, constraints.
- [ ] `GET/POST /exhibitions`, `GET/PATCH /exhibitions/{id}`.
- [ ] `GET/POST /editions`, `GET/PATCH /editions/{id}`; list filtered by user scope.
- [ ] Edition status lifecycle (e.g. `DRAFT`, `ACTIVE`, `CLOSED`, `ARCHIVED`; confirm with business).
- [ ] Per-edition registration ID counter row created with the edition (see 03).
- [ ] Edition switcher in the top bar; the active edition is part of every list URL.
- [ ] Exhibition list + form, Edition list + form (tabs: Details, Registration, Email, Gates, Access).
- [ ] Audit every create/update.

## Acceptance criteria
- Second edition for the same exhibition and year is rejected by the DB (409).
- A user without scope on an edition gets it neither in lists nor by direct ID (404, not 403, to avoid leaking existence).
- All dates shown in the edition's timezone.
