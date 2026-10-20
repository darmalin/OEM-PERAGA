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
| Person | Exhibition Type | configurable select | Per edition config |
| Person | Source | select | Excel, API, Manual, Website, Telemarketing |
| Person | Lead Owner | user | Optional until assigned |
| Person | Product Categories Interested In | multi-select | Optional |
| Person | Comment | textarea | Optional |
| Verification | Valid Lead / Invalid | mutually exclusive | Neither = undecided |
| Verification | Attend | select | `Attend`, `Attend Sourcing`, `Under Consideration`, `Not Attend`, `Hang Up Immediately` |
| Verification | B2B Matching | checkbox | |
| Verification | Type of Buyers | select | `B-Side`, `C-Side` |
| Verification | Updated At | datetime, read-only | |

Note: the screenshot marks Email and Phone both with `*`. The spec rule is "at least one". The form must show this as a group rule, not two required fields. Confirm with business (D11).

System fields: `id` (UUID), `edition_id`, `telemarketing_status`, `registration_status`, `qr_status`, `last_call_at`, `next_followup_at`, `external_source`, `external_id`, `custom_fields` (JSONB), `created_by`, `updated_by`, `created_at`, `updated_at`, `version` (optimistic lock).

## Registration ID
- Format: edition code + 6-digit counter, e.g. `IBTE2027000001`.
- Generated from a per-edition counter row: `UPDATE edition_counters SET last_value = last_value + 1 WHERE edition_id = :id RETURNING last_value` inside the same transaction. Never `COUNT(*)`.
- Not the primary key.

## Duplicate rules (§5.2)
- Normalize: email trimmed + lowercased; phone trimmed + E.164 when country known; empty = `NULL`.
- Partial unique indexes: `(edition_id, email_normalized) WHERE email_normalized IS NOT NULL`, same for phone.
- Same email or phone in the same edition: reject with `409` and the conflicting field(s). Other editions: allow. Both empty: `422`.
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
