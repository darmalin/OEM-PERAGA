# Known Gaps (Frontend)

State of the web app as of 2026-10-21. Read before frontend work; update in the same PR that
closes or adds a gap. Backend gaps are in `BACKEND_RULES/known-gaps.md`.

| # | Pri | Gap | Fix |
|---|---|---|---|
| W15 | P2 | Since the Follow-ups list and My Calls were removed (2026-10-28), there is no page of follow-ups due today or overdue across leads. Agents find them with the Next Follow-up filter on Visitor Leads or on board cards. | Ask the owner whether a saved filter ("Due today", "Overdue") on Visitor Leads is enough. |
| W18 | P3 | The desk order and order payment pages show times in the browser's timezone: the order API does not return the edition, so its timezone is not used. | Add `edition_id` to `StaffOrderOut` and pass the edition timezone like the lead pages. |
| W19 | P3 | Portal deadline countdowns ("In 5 days") count from the device's date, not the edition's timezone; the server's closing check uses the edition's date. | Return the edition's today with the form list, or count in the edition timezone. |
| W20 | P3 | The portal exhibition page shows the contract and its payments, but not a total of service orders; payment status shows per order on each form. | A "Service orders" summary on the exhibition page from the order payments. |
| W21 | P3 | The booth search lists free booths only. A quotation for a booth another lead holds needs its code typed in (it then prints without being linked to the booth). | Search all booths in the quotation form and mark the held ones. |
| W22 | P3 | The New Quotation summary refreshes after a 400 ms pause through the preview API; offline or on a slow link it shows "Computing" until the server answers. | Accept, or compute a client-side estimate while waiting. |
| W2 | P1 | Scanner PWA is built and served at `/scanner/`, but in production the camera is blocked: nginx sends `camera=()` for every location (backend gap S5). Manual code entry works meanwhile. | nginx: `camera=(self)` on `/scanner/` only. |
| W9 | P2 | Scanner FIRST/REPEAT with a real QR on a phone camera is not run end to end; the offline E2E uses unknown codes, and FIRST/REPEAT is covered by unit tests against a fake server. | Run on a phone over HTTPS with a registration's QR email once S5 is fixed. |
| W11 | P2 | The board loads 50 cards per column; more are reached through the "more in the list" link, not by scrolling the column. | Infinite scroll per column if teams work the board instead of the list. |
| W12 | P3 | The Excel import template and mapping still offer the old "Exhibition Type" column, which fills the retired `exhibition_type` field (hidden in the UI). | Drop it from `importexport/rules.py` mapping targets and the template. |
| W13 | P2 | Edition remarks and exhibitor dates (price periods, Order Expired, Catalog Expired) are stored and shown only; nothing uses them yet. | Exhibitor Portal phase, FEATURES/02 "Remarks and exhibitor dates". |
| W14 | P3 | Excel import and the visitor export do not carry the new Source (master data) yet; imported leads get none. | Map a "Source" column by name to `lead_sources` in `importexport`; add it to the export columns. |
| W10 | P3 | Scanner PWA has no manifest icons (W3), so browsers do not offer "Install app". It still works from the browser and offline after the first load. | Add icons with the logo. |
| W3 | P2 | No favicon yet. Desk header now uses the owner-requested PERAGA Expo logo (official website asset), with a white backing for both themes. | Supply a favicon asset and replace the empty `<link rel="icon">`. |
| W5 | P2 | Tests are a smoke run and a click-through script (`e2e/*.mjs`, local Chromium) plus a few unit tests. No component tests with mocked API yet, no axe accessibility run. | Add Vitest + Testing Library + MSW for forms and list states; add axe to the smoke run. |
| W6 | P2 | Native date and time inputs follow the browser locale (e.g. mm/dd/yyyy in en-US), while the rest of the app shows dd-mm-yyyy. | Accept, or replace with a date picker that uses the app format. |
| W7 | P3 | Lists fetch one page at a time with a total count; for very large editions the backend count (backend gap P3) may need keyset paging. | Follow the backend change. |
| W8 | P3 | Visual check is manual from screenshots; no screenshot diffing. | Add Playwright screenshot comparisons if the design stabilises. |
