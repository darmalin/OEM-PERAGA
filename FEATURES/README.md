# Features: Work Breakdown

Breakdown of `DEV_DOCS/EMS-Visitor-CRM-Specification.md` into buildable work. Each file lists scope, tasks, acceptance criteria, and open questions. Spec section numbers are cited as `§x.y`.

## Phase 1 scope

In: auth and permissions, exhibitions and editions, visitor lead CRUD, duplicate rules, Excel import, assignment, telemarketing calls, verification, follow-ups, registration and QR, QR email, gate scanner (online and offline), audit log, dashboard, export.

Out (do not build, §1.2 and §18): exhibitor CRM, booth inventory, proposals, contracts, exhibitor portal, the twelve exhibitor forms, invoices, payments, refunds, credit notes.

## Feature files

| # | File | Spec | Milestone |
|---|---|---|---|
| 00 | [00-foundation.md](00-foundation.md) | §2, §14, §16 | M1 |
| 01 | [01-identity-permissions.md](01-identity-permissions.md) | §9 | M1 |
| 02 | [02-exhibitions-editions.md](02-exhibitions-editions.md) | §3 | M1 |
| 03 | [03-visitor-leads.md](03-visitor-leads.md) | §4, §5 | M1 |
| 04 | [04-audit-log.md](04-audit-log.md) | §10 | M1 |
| 05 | [05-import.md](05-import.md) | §5.2 | M2 |
| 06 | [06-assignment.md](06-assignment.md) | §6.1 | M2 |
| 07 | [07-telemarketing.md](07-telemarketing.md) | §6.2 to §6.5 | M3 |
| 08 | [08-registration-qr-email.md](08-registration-qr-email.md) | §7 | M4 |
| 09 | [09-gate-scanner.md](09-gate-scanner.md) | §8 | M5 |
| 10 | [10-reporting-export.md](10-reporting-export.md) | §11 | M6 |
| 11 | [11-exhibitor-portal.md](11-exhibitor-portal.md) | outside §1.2 | not planned; decisions E1 to E6 first |

## Milestones (§15)

| Milestone | Contents | Exit criteria |
|---|---|---|
| M1 Foundation and Visitor CRUD | 00, 01, 02, 03, 04 | No read/write outside scope. Duplicate email/phone rejected by the database. Every update in audit log. |
| M2 Import and Assignment | 05, 06 | Large files never block a request. Import results traceable. Assignment history never lost. |
| M3 Telemarketing | 07 | Attempts stored as history. Status derived consistently. Partial verification allowed. Lead changes audited. |
| M4 Registration and QR | 08 | Registration idempotent. QR has no PII. Failed email retried without duplicate registration. |
| M5 Gate Scanner | 09 | Retried scan never counted twice. Scanner rejects other editions. Offline conflicts handled and auditable. |
| M6 Dashboard, Export, Hardening | 10 + load, security, backup/restore | All reports respect scope. Exports audited. Restore tested. |

## Open decisions (§17)

These block the related feature from being called production-ready. Owner: business / product. Record the answer in the feature file when decided.

| # | Question | Default until decided | Blocks |
|---|---|---|---|
| D1 | External API Registration ID: keep or store separately? | EMS issues its own ID; external ID in `external_source` + `external_id`. | 03, 08 |
| D2 | Does a lead import create a registration and send QR? | Separate processes; import type decides. | 05, 08 |
| D3 | What does `Status` in the screenshot mean? | Split into telemarketing, registration, verification status. | 03, 07 |
| D4 | Follow-up reminder interval, send time, escalation | No automatic reminder until defined; due/overdue lists only. | 07 |
| D5 | Custom field scope: exhibition master or edition? | Per edition (safer, copyable). | 03 |
| D6 | Offline cache lifetime, device activation, lost-device policy | Short lifetime, manual revoke. | 09 |
| D7 | Extra call results (Busy, Invalid Number) | Answer / No Answer only, configurable list. | 07 |
| D8 | Country reference and phone normalization policy | ISO 3166 list; E.164 when country known. | 03, 05 |
| D9 | Retention for PII, audit log, scanner data | Keep everything; no purge job yet. | 04, 09 |
| D10 | API upsert policy for existing visitors | No upsert. Create or explicit update by ID only. | 03 |
| D11 | Labels and options from the original screenshot source | Use labels as in the screenshot. | 03 |
