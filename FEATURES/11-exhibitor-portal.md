# 11 Exhibitor Portal (draft, not built)

Requested by the owner on 2026-10-21 as the third panel ("panel customer" = exhibitors).
Spec §1.2 puts the exhibitor CRM and the exhibitor customer portal **outside phase 1**, and
there is no backend for exhibitors yet: no exhibitor table, no exhibitor login, no link
between exhibitors and visitors. Nothing here is built until the decisions below are made.

The web app reserves the URL prefix `/exhibitor` for this panel. No navigation points to it
until it exists (antislop R-24).

## Already stored (2026-10-22)

The edition already holds the old Exhibition form's remarks, price periods (Regular, Surcharge, Onsite), Order Expired, and Catalog Expired, display only. See FEATURES/02 "Remarks and exhibitor dates" for the field list and the open rules.

## Decisions needed (owner / business)

| # | Question | Why it matters |
|---|---|---|
| E1 | What should an exhibitor do in the portal? Candidate jobs below; pick the ones for the first release. | Decides every screen and table. |
| E2 | Who creates exhibitor accounts: the organiser, or self sign-up with approval? | Account model, invitations, and abuse risk. |
| E3 | One login per company, or several staff per exhibitor company? | Data model (company + members) and permissions. |
| E4 | Is the exhibitor portal part of phase 1 after all, or phase 2? | The spec says out of scope; the plan and milestones change. |
| E5 | Which visitor data may an exhibitor see (B2B matching), and with what consent? | PII and the visitor's consent; probably needs a consent field at registration. |
| E6 | Same domain as the staff app, or a separate subdomain? | Cookie scope, CSP, and session separation from staff. |

## Candidate jobs (for E1, none confirmed)

- See their own booth and edition details.
- See visitors matched to them (B2B Matching) and request meetings.
- Scan visitor badges at their booth to collect leads (lead retrieval).
- Download their own collected leads.

Anything involving booths, contracts, invoices, payments, or the twelve exhibitor forms is
explicitly out of scope in spec §1.2 and §18.

## Backend work once E1 to E6 are answered

- `exhibitors` (company per edition), `exhibitor_users` (separate from staff `users`, or a
  user type), invitations, and sessions kept apart from staff sessions.
- New permission set and scope (`EXHIBITOR`), checked on every endpoint like the rest.
- Audit and retention rules for any visitor data shared with exhibitors.

## Frontend work

- Third panel at `/exhibitor` with its own sign-in, built on the same design system
  (DESIGN.md), pages instead of popups, toasts.
