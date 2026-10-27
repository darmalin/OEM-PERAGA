# Known Gaps (Frontend)

State of the web app as of 2026-10-21. Read before frontend work; update in the same PR that
closes or adds a gap. Backend gaps are in `BACKEND_RULES/known-gaps.md`.

| # | Pri | Gap | Fix |
|---|---|---|---|
| W1 | P1 | Exhibitor panel not built: outside spec phase 1 and no backend. | Decisions E1 to E6 in `FEATURES/11-exhibitor-portal.md`, then backend, then the panel. |
| W2 | P1 | Scanner PWA is built and served at `/scanner/`, but in production the camera is blocked: nginx sends `camera=()` for every location (backend gap S5). Manual code entry works meanwhile. | nginx: `camera=(self)` on `/scanner/` only. |
| W9 | P2 | Scanner FIRST/REPEAT with a real QR on a phone camera is not run end to end; the offline E2E uses unknown codes, and FIRST/REPEAT is covered by unit tests against a fake server. | Run on a phone over HTTPS with a registration's QR email once S5 is fixed. |
| W11 | P2 | The board loads 50 cards per column; more are reached through the "more in the list" link, not by scrolling the column. | Infinite scroll per column if teams work the board instead of the list. |
| W12 | P3 | The Excel import template and mapping still offer the old "Exhibition Type" column, which fills the retired `exhibition_type` field (hidden in the UI). | Drop it from `importexport/rules.py` mapping targets and the template. |
| W13 | P2 | Edition remarks and exhibitor dates (price periods, Order Expired, Catalog Expired) are stored and shown only; nothing uses them yet. | Exhibitor Portal phase, FEATURES/02 "Remarks and exhibitor dates". |
| W14 | P3 | Excel import and the visitor export do not carry the new Source (master data) yet; imported leads get none. | Map a "Source" column by name to `lead_sources` in `importexport`; add it to the export columns. |
| W10 | P3 | Scanner PWA has no manifest icons (W3), so browsers do not offer "Install app". It still works from the browser and offline after the first load. | Add icons with the logo. |
| W3 | P2 | No logo or favicon: the header shows "EMS" as text (antislop R-23). | Owner supplies the logo; replace the text and the empty `<link rel="icon">`. |
| W4 | P2 | Campaign links have their API and admin screens (FEATURES/12) but no public form page yet: shared links lead nowhere. | Phase 3 of FEATURES/12. |
| W5 | P2 | Tests are a smoke run and a click-through script (`e2e/*.mjs`, local Chromium) plus a few unit tests. No component tests with mocked API yet, no axe accessibility run. | Add Vitest + Testing Library + MSW for forms and list states; add axe to the smoke run. |
| W6 | P2 | Native date and time inputs follow the browser locale (e.g. mm/dd/yyyy in en-US), while the rest of the app shows dd-mm-yyyy. | Accept, or replace with a date picker that uses the app format. |
| W7 | P3 | Lists fetch one page at a time with a total count; for very large editions the backend count (backend gap P3) may need keyset paging. | Follow the backend change. |
| W8 | P3 | Visual check is manual from screenshots; no screenshot diffing. | Add Playwright screenshot comparisons if the design stabilises. |
