# Changelog

Releases are git tags. Production runs a tag; staging runs `main`. Deploy steps: `deployments/PRODUCTION.md`.
Add an entry here in the same commit as the change, so a tag never ships something nobody wrote down.

## Unreleased

- Campaign forms can live on their own address (`EMS_CAMPAIGN_BASE_URL`, e.g. `https://events.example.com/k7Qm2xPa9Lw4`). That address opens only the forms; old `/r/` links redirect there with their UTM. Without the setting nothing changes. Setup: PRODUCTION.md 4b.
- Docs: this changelog; the 2026-10-28 changes below recorded in FEATURES 01, 03, 07, 08, 12, DESIGN, and FRONTEND_RULES.

## v1.2.2 (2026-10-28)

Commit `a70acfa`. No migration.

**Design and branding**
- Forest green and red theme for the desk: green sidebar, pale green active item with a red accent, green buttons, titles, and panels (`frontend/apps/web/src/styles/app.css`). Scanner and campaign form unchanged.
- PERAGA Expo logo replaces the "EMS" text in the header.
- Table headers are bold.
- Fix: Overview stayed highlighted in the sidebar on other pages.

**Menu**
- Marketing: Campaigns is now **Form**, Campaign Dashboard is now **Form Dashboard** (same URLs).
- Removed from the menu: **Registrations**, **My Calls**, **Follow-ups**. Their old URLs redirect to Visitor Leads, so bookmarks still work.
- Visitor Leads opens straight on the leads list, without the Leads/Registrations tabs.
- Registering, logging a call, and adding a follow-up stay on the lead detail.

**Visitor Lead detail**
- New **Email** tab: sent, pending, failed, cancelled, and total counts, then each email with subject, recipient, From, time, status, and attempts. API `GET /visitor-leads/{id}/emails`.
- Removed the Registration status column and the repeated Registered/Registration badges; Registration ID stays.

**Board and status**
- Dragging a card or using its menu opens Log Call in a popup over the board; Save and Cancel return to the same board and filters.
- Next Follow-up removed from the call form. Follow-ups are added from the lead detail.
- Status rules: **Answer + missed call now goes to Retry No Answer** (was: stays Answer). Full table in FEATURES/07.
- Menu labels show current to target status, e.g. "Answer to Retry No Answer".

**Users**
- Change Password (typed twice) and Disable / Enable User on the user page.
- Changing the password or disabling a user ends that user's sessions. You cannot disable yourself.

**Known effects** (BACKEND_RULES/known-gaps.md B2, FRONTEND_RULES/known-gaps.md W15)
- Leads that already had Answer then a missed call still show Answer until their next call.
- There is no longer one page listing follow-ups due today or overdue; use the Next Follow-up filter.

## v1.2.1 (2026-10-27)

- Kanban cards in a CRM layout: name, company, email, phone, Lead Owner, Registration ID with last update, and a footer with calls, next follow-up (red when overdue), QR status, and a + menu (Move to, Log Call). The lead list API returns `call_attempts`.

## v1.2.0 (2026-10-27)

- Marketing menu with Campaigns and the Campaign Dashboard (form opens, registrations, conversion, funnel to gate check-in, UTM). Permission `campaign.view` (migration 0023).
- Dev nginx serves `/r/` from the campaign form dev server.

## v1.1.0 (2026-10-27)

- Campaign links per edition with a public bilingual form at `/r/{token}`, GTM per link, campaign and UTM stored on the lead (migration 0022).
- Roles ordered by number, highest access first (migration 0021). Minimum password length 8.

## v1.0.0 (2026-10-25)

- First production release: leads, import and round-robin assignment, telemarketing, registration and QR email, gate scanner, reports and exports, admin boundaries, staging and production setup.
