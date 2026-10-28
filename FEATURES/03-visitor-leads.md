# 03 Visitor Leads

Spec §4, §5. Reference screen: `DEV_DOCS/WhatsApp Image 2026-10-20 at 14.40.58.jpeg` (Person form, Verification section).

## Fields (from the screenshot, keep labels)

| Section | Field | Type | Rule |
|---|---|---|---|
| Person | Date | datetime | System or registration date |
| Person | Registration ID | string, read-only | Generated, see below |
| Person | Status | select | See D3: split into telemarketing / registration / verification status |
| Person | First Name | text | Required |
| Person | Email | email | Email or phone required (at least one) |
| Person | Phone | string | Email or phone required (at least one) |
| Person | Gender | select | Optional |
| Person | Company Name | text | Optional |
| Person | Job Title | text | Optional |
| Person | Country | reference | Optional |
| Person | City | text | Optional |
| Person | Website | url | Optional |
| Person | Business Type | configurable select | Optional |
| Person | Branch | configurable select | Per edition config |
| Person | Exhibition Type | edition | The lead's edition, chosen when the lead is created, read-only after (owner decision 2026-10-22). The old `exhibition_type` option column is kept for existing data and no longer shown. |
| Person | Source | select | Global master data `lead_sources` (Setup > Sources), e.g. "2026 test". Optional. Inactive sources stay on leads that have them (owner decision 2026-10-22). |
| Record | Channel | system | How the lead came in: Excel, API, Manual, Website, Telemarketing. Column `source`, set by the system, drives the registration channel. Labelled "Source" until 2026-10-22. |
| Person | Lead Owner | user | Optional until assigned. Changed through Assign (keeps the assignment history), not in the Person form (owner decision 2026-10-22). |
| Person | Product Categories Interested In | text (2000) | Optional free text, like the old system (owner decision 2026-10-22). Was a per-edition multi-select until migration `0016`, which turned stored values into their option labels joined with ", ". Excel import copies the cell as is. |
| Person | Comment | textarea | Optional |
| Verification | Valid Lead / Invalid | mutually exclusive | Neither = undecided |
| Verification | Attend | select | `Attend`, `Attend Sourcing`, `Under Consideration`, `Not Attend`, `Hang Up Immediately` |
| Verification | B2B Matching | checkbox | |
| Verification | Type of Buyers | select | `B-Side`, `C-Side` |
| Verification | Updated At | datetime, read-only | |

Note: the screenshot marks Email and Phone both with `*`. The spec rule is "at least one". The form must show this as a group rule, not two required fields. Confirm with business (D11).

System fields: `id` (UUID), `edition_id`, `telemarketing_status`, `registration_status`, `qr_status`, `last_call_at`, `next_followup_at`, `external_source`, `external_id`, `custom_fields` (JSONB), `created_by`, `updated_by`, `created_at`, `updated_at`, `version` (optimistic lock).

## List across editions
`GET /visitor-leads` without `edition_id` lists every edition the caller may read, each with its own scope (the Exhibition Type filter set to All). Items carry `edition_id`.

## Search per field and stacked filters (owner request 2026-10-25)
Like Frappe: a row of per-field inputs above the list, plus a **Filter** button that stacks conditions (all must match).
- `filters` on `GET /visitor-leads` (and in export / assign-by-filter bodies) is a JSON list of `{"field", "op", "value"}`, at most 20.
- Fields and operators are a fixed list in `visitors/rules.py` (`CONDITION_FIELDS`, `CONDITION_OPS`); anything else is `422`. Values are checked and typed per field, never put into SQL as text.

| Kind | Fields | Operators |
|---|---|---|
| text | Name, Company, Email, Phone, Registration ID, Job Title, City | contains, equals, starts with, is set, not set |
| choice | Status, Registration, QR, Channel, Source, Country, Attend, Type of Buyers, Lead Owner, Team | is, is not, is set, not set |
| yes/no | Valid Lead, Invalid, B2B Matching | is |
| date | Lead Date, Last Call, Next Follow-up, Created | between, before, after, is set, not set |
| number | Call Attempts | equals, greater than, less than |

- Text matches ignore case; `%` and `_` are literal; phone compares digits only (at least 4). Dates are calendar days in `report_timezone`. Required fields (Name, Registration ID, statuses) do not offer is set / not set.
- The board uses the same row and Filter button (without Status: its columns are the statuses); a column's "more" link opens the list with the same filters plus that status. Lead Owner offers "Me" and "Unassigned". On a phone only Name, Exhibition Type, and filled fields stay in the row; the rest are in the Filter button.
- `GET /visitor-leads/filter-options` gives countries, lead owners, and their teams found in the leads the caller can see.
- `pg_trgm` GIN indexes (migration 0019) serve "contains" on name, company, email, phone, and Registration ID.

## Lead list, board, and detail (owner request 2026-10-28)
- Visitor Leads opens straight on the leads list; the Leads/Registrations tabs are gone. `/app/registrations` and `/app/visitor-leads/registrations` redirect to the list. Registered leads: filter Registration Status = Registered.
- The Registration status column and the repeated Registered/Registration badges were removed; Registration ID stays.
- Registering a visitor, logging a call, and adding a follow-up are done from the lead detail. Its tabs: Person, Verification, Calls, Registration, Email (FEATURES/08), Activity.
- Board cards (2026-10-27): name, company, email, phone, Lead Owner, Registration ID with last update, and a footer with call count, next follow-up (red when overdue), QR status, and a + menu. Moving a card opens Log Call in a modal (FEATURES/07).

## Registration ID
- Format: edition code + 6-digit counter, e.g. `IBTE2027000001`.
- Generated from a per-edition counter row: `UPDATE edition_counters SET last_value = last_value + 1 WHERE edition_id = :id RETURNING last_value` inside the same transaction. Never `COUNT(*)`.
- Not the primary key.

## Duplicate rules (§5.2)
- Normalize: email trimmed + lowercased; phone trimmed + E.164 when country known; empty = `NULL`.
- Partial unique indexes: `(edition_id, email_normalized) WHERE email_normalized IS NOT NULL`, same for phone.
- Same email or phone in the same edition: reject with `409` and the conflicting field(s). Other editions: allow. Both empty: `422`. (Confirmed by the owner 2026-10-22: unique per edition.)
- Update re-checks conflicts against other records.

## Custom fields (§4.5)
- `visitor_custom_field_definitions`: `field_key`, `label`, `field_type` (text, textarea, number, date, select, multi_select, checkbox), `required`, `options`, `sort_order`, `is_active`, validation rules, `in_import`, `in_export`.
- Backend validates `custom_fields` against active definitions for the edition. Unknown keys rejected.
- Admin screen to manage definitions; form renders them in a "Custom Fields" section.

## Tasks
- [ ] Models, migration, partial unique indexes, counter table.
- [ ] Normalization helpers + unit tests for every row of the §5.2 table.
- [ ] `GET /visitor-leads` with filters (§11 list), search (name, email, phone, company, registration ID), sort, cursor or page pagination.
- [ ] `POST /visitor-leads`, `GET /visitor-leads/{id}`, `PATCH /visitor-leads/{id}` with `version` check.
- [ ] Map DB unique violation to 409 (race-safe).
- [ ] Custom field definitions CRUD + validation.
- [ ] List view, form view (layout from the screenshot), activity timeline from audit log.
- [ ] Concurrency test: parallel creates with the same email produce exactly one row; parallel creates never share a Registration ID.

## Acceptance criteria
- Every row of the §5.2 duplicate table has a passing test.
- No query on `visitor_leads` without `edition_id` and scope filter.
- Every create/update writes an audit entry with before/after.
