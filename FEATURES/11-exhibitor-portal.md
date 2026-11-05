# 11 Exhibitor Sales and Exhibitor Portal (built 2026-11-03)

Owner request 2026-11-03, built in phases 1 to 8 of
[docs/EXHIBITOR_LEADS_SALES_PIPELINE.md](../docs/EXHIBITOR_LEADS_SALES_PIPELINE.md), which holds the
decisions, the data model, and the task list. This file is the short version.

Spec §1.2 and §18 put the exhibitor CRM, booths, contracts, the exhibitor portal, and payments
outside phase 1. The owner moved a narrow slice of them in scope (below). Everything else in §1.2
stays out: proposals, the twelve exhibitor forms, invoices, refunds, credit notes, payment gateway.

## Flow

Exhibitor lead → Opportunity → booth held → Convert (portal account + numbered Draft contract)
→ exhibitor fills the contract and uploads the signed PDF in the portal → staff record payments
(installments) and verify them → Paid.

Exhibitor leads are separate from visitor leads (own table, own permissions). Opportunity is a
stage of the lead, not another table or menu.

## Decisions (2026-11-03)

| # | Decision |
|---|---|
| E1 | Portal jobs: fill the contract, upload the signed PDF, follow payments. No B2B matching or lead retrieval yet. |
| E2 | Accounts come from an invitation **link** made by staff at Convert (sent by any channel, no email needed); the exhibitor sets the password there. |
| E3 | One login per exhibitor, by email. The same account is reused when the exhibitor returns in another edition. |
| E4 | This slice is in scope now (owner request); the rest of §1.2 is not. |
| E5 | Exhibitors see no visitor data. |
| E6 | Production: own subdomain (`EMS_PORTAL_BASE_URL`). Staging and dev: `/exhibitor/` on the same domain. |
| P1 | Payments can be installments; each is recorded and verified on its own. Tagging only, no gateway. |
| P2 | Stage `LOST` with a reason; can be reopened to `LEAD`. |
| P3 | Contract = fields (number, PIC, address, NPWP, price, discount, total) + signed PDF. |
| C1 | Contract numbers are automatic per edition: `<edition code>-C-0001`. |

## What is built

**Desk (Admin panel, menu "Exhibitors")**
- Exhibitor Leads: list (search, stage and owner filters), board by stage (drag a card or use its
  Move to menu; Lost and Convert open their pages, as does leaving Opportunity with a booth), new lead, detail with Details,
  Contract, Payments, and Activity tabs. Actions are pages: move stage, choose booth, Convert
  (shows the one-time invitation link), new invitation link, record payment, payment proof and
  Verify / Reject.
- Lead Owner: users with edition-wide access assign or reassign a lead (or leave it unassigned)
  to an active user who can edit exhibitor leads in that edition (`GET /exhibitor-leads/owners`);
  the list filters by owner. Sales with Own Leads access own what they create.
- Booths per edition: list (Available / Held / Not for Sale), add, edit.
- Overview: "How are exhibitor sales going?" panel with leads per stage, booths held, and signed
  value, paid, waiting, and outstanding per currency (`GET /exhibitor-leads/pipeline`), counted
  inside the user's lead scope.

**Exhibitor portal** (`frontend/apps/exhibitor`)
- Set Your Password (invitation link), Sign In, My Exhibitions, and one page per exhibition:
  contract details form, signed PDF upload, signed PDF download, payment status.
- Own cookie (`ems_portal_session`) and Redis session namespace; staff and portal sessions never
  open each other's API.
- Forgotten password: staff make a **password reset link** from the lead (same page as a new
  invitation, valid 24 hours). Using it sets a new password and ends the exhibitor's other
  sessions. Staff can also **disable** the account (ends its sessions, closes the portal for every
  edition, cancels open links) and enable it again.

**Permissions** (Super Admin and Exhibition Admin by default): `exhibitor_lead.read`,
`exhibitor_lead.create`, `exhibitor_lead.update`, `booth.manage`, `exhibitor.invite`,
`exhibitor_payment.record`, `exhibitor_payment.verify`. A sales person gets a custom role with the
`exhibitor_lead.*` permissions, scoped to the edition, a team, or own leads.

## Rules worth knowing

- A booth is held only by an Opportunity or an Exhibitor, one lead per booth (database index).
  Leaving Opportunity releases it. A signed contract freezes the booth.
- A Draft contract follows its booth's price when the booth changes. Signed contracts are read-only.
  An Exhibition Admin (`exhibitor.invite`) can reopen a signed contract to Draft with a reason (for
  a wrong PDF), unless it has pending or verified payments; the old PDF is kept, its key in the
  audit entry.
- Payments are recorded only against a signed contract. Pending plus verified never exceeds the
  contract total; the contract row is locked while recording or verifying.
- Uploads (signed PDF; proof as PDF, JPG, PNG) are checked by extension, type, and content, up to
  10 MB, stored with random keys, and downloaded through the API only.

## Known gaps

- Edition remarks and exhibitor dates (price periods, Order Expired, Catalog Expired) are still
  display only (FEATURES/02, W13).
