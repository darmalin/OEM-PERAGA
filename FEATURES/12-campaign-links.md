# 12 — Campaign links (public lead forms)

Owner request 2026-10-26. Each edition has any number of campaign links ("IG October", "WA blast", "Poster Hall A"). Anyone with a link fills a public form; the visitor becomes a lead of that edition.

## Decisions
- Many links per edition; the lead keeps its **campaign** (`campaign_link_id`) and the **UTM** tags of the URL opened (`utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content`). Both filterable on Visitor Leads and exported.
- New leads are **registered with an active QR, but no email is sent** and **nobody is assigned**: Resend QR Email and Assign To stay manual.
- The edition's custom fields appear on the form; their rules apply.
- The old website endpoint `/public/editions/{code}/registrations` and the edition's "Website registration" flag are removed (unused, guessable by edition code, sent email at once).
- Per link: Google Tag Manager container ID only (`GTM-XXXX`, no free script field). Same domain as the app (option B): the form page gets its own strict CSP (phase 3). Test campaign links in a private window, not one logged in to EMS.
- Form in English and Indonesian, switchable by the visitor (phase 3); standard consent text, versioned (`CONSENT_VERSION`).

## Link
`name` (unique per edition), `token` (12 random URL-safe characters; **New URL** replaces it and the old one stops), `lead_source_id` (master Source given to its leads), `is_active`, `starts_at`/`ends_at`, `max_submissions`, `submission_count`, `gtm_container_id`. State: OPEN, INACTIVE, NOT_STARTED, ENDED, FULL, EDITION_CLOSED (edition not Active).

## API
- Admin (`edition.manage`; list also `visitor.read`): `GET/POST /campaign-links`, `PATCH /campaign-links/{id}`, `POST /campaign-links/{id}/new-url`. Every change is audited (GTM included).
- Public, no login: `GET /public/campaigns/{token}` (edition name, dates, venue; custom fields; GTM ID; a signed `ticket`), `POST /public/campaigns/{token}/registrations`.

## Public form safety
| Risk | Rule |
|---|---|
| Guessing links | Random token; unknown and closed links both answer `404 CAMPAIGN_CLOSED`. |
| Bots | Honeypot field; the signed ticket must be 3 s to 2 h old; per IP and per link hourly limits (`EMS_CAMPAIGN_SUBMISSIONS_PER_IP_PER_HOUR`, `..._PER_LINK_PER_HOUR`). |
| Probing who exists | New, duplicate, and bot posts all get `202 {"status":"RECEIVED"}`. |
| Setting internal fields | Body allows only the form fields (`extra="forbid"`); owner, status, source are refused. |
| Consent | `consent: true` required; its version is stored with the submission. |
| Abuse review | `campaign_submissions`: time, outcome (CREATED / DUPLICATE / BOT), keyed hash of the IP (never the address). |
| Faked IPs | The host nginx must **set** `X-Forwarded-For $remote_addr` (deployments/nginx/host-site.conf.example). |

## Phases
1. Backend (this file's API and rules, migration 0022, tests `tests/test_campaigns.py`).
2. Admin UI (done): Campaign Links panel on the edition page (Copy Link, QR Code PNG from `GET /campaign-links/{id}/qr.png`, Edit, New URL with a second click); new/edit pages under `/app/campaign-links`; Campaign column, Campaign and UTM fields in the Filter button, and a Campaign panel on the lead detail.
3. Public form (done): `frontend/apps/campaign`, built into `/r/` of the web image.
   - English and Indonesian, switched by the visitor (kept in the browser); country names in that language.
   - GTM loads only when the link has a container ID. Data layer events `campaign_form_view`, `campaign_form_start`, `campaign_form_submit` carry the edition name and form language, never personal data.
   - UTM tags are read from the URL (only the five `utm_*`, 200 characters each). Requests use `credentials: "omit"`.
   - Pages: form, thank you, closed (unknown, inactive, ended, full, or edition not Active).
   - `deployments/nginx/default.conf` gives `/r/` its own CSP: GTM, Google, Meta, and TikTok script and beacon hosts allowed; `connect-src` is only `<host>/api/v1/public/` plus those hosts (no `'self'`), so a tag cannot call the admin API with a signed-in user's cookie; no framing of this origin (`frame-src` without `'self'`). Checked against the production image: `/api/v1/auth/me` from the form page is blocked by the browser, the public API works. A tag that needs another host is blocked until that host is added to the policy.
   - Dev: `make campaign` runs the form's dev server on the host (port 5175); the dev nginx sends `/r/` there, so the admin's links (http://localhost:8080/r/{token}) open as they are. Without `make campaign` running they answer 502. `make e2e-campaign` runs the flow.

## Marketing menu and dashboard (owner decision 2026-10-27)
- Sidebar group **Marketing**: **Campaigns** (links of the chosen Exhibition Type, same actions as the edition page) and **Campaign Dashboard**. Permission `campaign.view`: Super Admin, Exhibition Admin, Telemarketing Manager (migration 0023). Managing links still needs `edition.manage`.
- Form opens are counted per link and edition-local day, once per visitor (keyed IP hash in Redis, 26 h) in `campaign_views`.
- `GET /reports/campaigns?edition_id=&campaign_link_id=&date_from=&date_to=`: opens, registrations, duplicates, bots, conversion (registrations ÷ opens; over 100% when one device registers several people), per day, the funnel, UTM source/medium/campaign (top 10), and every campaign of the edition side by side.
- Funnel of the campaign leads the caller can see: Registered → Called (a call logged) → Answered (status Answer or Recontacted) → Valid lead → Plans to attend (Attend or Attend Sourcing) → Checked in at the gate (scanned in at least once, any day, Manual Entry included).

### How a campaign lead reaches "Checked in"
1. The visitor fills the form: the lead is Registered with an active QR (no email yet).
2. Telemarketing assigns and calls the lead, logging the result and verification (Lead Quality, Attend).
3. Staff send the QR: Registrations → the visitor → Resend QR Email.
4. On the event day the visitor shows the QR at a gate; the scanner records a First Entry. If the QR cannot be read, a Gate Supervisor uses Manual Entry.
5. The dashboard counts the lead as Checked in from then on.
