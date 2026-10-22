# 02 Exhibitions and Editions

Spec §3.

## Data
- `exhibitions`: master (code like `IBTE`, name, active).
- `exhibition_editions`: `exhibition_id`, `year`, `code` (`IBTE2027`), start/end date, `venue_id`, country, city, timezone (IANA), default currency, registration ID prefix, status, email config, registration config, gate settings.
- `venues`.
- Edition access: which teams/users can access (via scoped role assignments in 01).

Constraints: `UNIQUE (exhibition_id, year)`, `UNIQUE (code)`, `end_date >= start_date`.

The old system's "Exhibition" form is our **Edition** (one event per year); its Code (`IIT`) is our Exhibition code.

## Remarks and exhibitor dates (display only, added 2026-10-22)

Owner request: keep the old Exhibition form's fields on the edition now, for display, so the next phase starts from known data. Migration `0013`. Nothing reads them yet.

| Old form | Edition field | Checked now | For the Exhibitor Portal phase (FEATURES/11) |
|---|---|---|---|
| Remarks | `remarks` (text, 2000) | length | Shown on the exhibitor home page? |
| Price Regular, To | `price_regular_from`, `price_regular_to` | to ≥ from | Price list per period: which period applies on an order date |
| Price Surcharge, To | `price_surcharge_from`, `price_surcharge_to` | to ≥ from | Same; in the old data the periods are back to back |
| Price Onsite, To | `price_onsite_from`, `price_onsite_to` | to ≥ from | Same; onsite ended on the edition end date in the old data |
| Order Expired | `order_expired_on` | none | Last day an exhibitor can order (old data: start of onsite) |
| Catalog Expired | `catalog_expired_on` | none | Last day to submit catalog content |

Decide in that phase: whether periods must be back to back and inside the edition dates, which timezone the day boundaries use (the edition's), whether these move to their own exhibitor settings table, and who may edit them. The old form's lower tabs (Home Content, General Information, Rules & Regulations, Site Operations & Services, Publicity Services, Order Forms, Order Forms Detail) are portal content and are not modelled yet.

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
