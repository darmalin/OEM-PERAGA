# Frontend Architecture

## Workspace (as built, 2026-10-21)

```text
frontend/
├── apps/web/
│   ├── public/theme.js         # theme before first paint (a file, so CSP needs no inline script)
│   ├── e2e/                    # smoke.mjs (every page x light/dark/mobile), flows.mjs (click-through)
│   └── src/
│       ├── main.tsx            # router, query client, error and not-found boundaries
│       ├── routes/             # file-based: /login, /app/* (Admin panel), /system/* (System panel); leads list + board
│       ├── features/           # shared per-domain pieces: leads/, gate/, reports.ts, edition-form.tsx, ...
│       ├── shell/              # top bar, panel switcher, sidebar (nav.ts), command bar
│       ├── ui/                 # design-system components (tokens from DESIGN.md)
│       └── lib/                # auth, edition, format, labels, status colors, forms, toasts
├── apps/scanner/               # gate scanner PWA, served at /scanner/ (scanner-pwa.md)
│   ├── e2e/offline.mjs         # activate, scan offline, sync, replay the batch, revoke
│   └── src/
│       ├── lib/                # engine (scan, sync, cache), Dexie db, provisional decision, device API
│       └── ui/                 # activation, scan screen, full-screen result, recent scans
├── packages/api/               # generated OpenAPI types + typed client (call, upload, downloadFile)
└── packages/ui/                # shared design tokens (tokens.css) and cn()
```

Decisions that differ from the first plan, with the reason:

- `packages/ui` holds only the tokens and `cn()`. Components stay in `apps/web/src/ui`: the scanner shares no component with the desk (its controls are 56px, its screens full-bleed), so moving them would only add indirection.
- There is no edition switcher in the top bar (owner decision 2026-10-22). Pages that work in one edition show an "Exhibition Type" picker in their page head (`<PageHead edition>`); the choice is saved in localStorage and carried to the next page. Visitor Leads (list and board) instead filter by Exhibition Type in the URL (`?edition=`), with All as the default, and the new-lead form picks the edition in its Exhibition Type field.
- Insert, edit, and actions are pages with their own URL, never dialogs (owner decision, DESIGN.md). The only overlays are menus, native selects, and the command bar.
- Feedback is a toast (sonner) plus field errors; errors stay until dismissed and show the request ID.
- Helper files inside `routes/` start with `-` (e.g. `-form.tsx`) so the router does not treat them as routes.

## Panels

| Panel | Prefix | Guard |
|---|---|---|
| Admin | `/app` | signed in; nav items filtered by permission (`shell/nav.ts`) |
| System | `/system` | signed in; nav items filtered by permission |
| Exhibitor | `/exhibitor` (reserved) | not built; see FEATURES/11 |

## Routing (TanStack Router)
- File-based routes. URL shape follows Frappe:
  - `/app/visitor-leads` list, `/app/visitor-leads/new`, `/app/visitor-leads/$id`
  - `/app/gates`, `/app/campaigns`, `/app/campaign-dashboard`, `/app/reports/$report`, `/app/setup/...`
- Retired pages keep their URL as a redirect so bookmarks work: `/app/my-calls`, `/app/followups`, `/app/registrations`, `/app/visitor-leads/registrations` (2026-10-28).
- List filters, sort, and page are typed search params (validated with Zod). Reloading or sharing a URL reproduces the same list.
- Panel routes (`/app`, `/system`) load `/auth/me` in `beforeLoad` and send signed-out users to `/login?next=...`. Permission is not checked per route: the nav hides what the user cannot open, and a page the API refuses (403/404) shows the NoAccess state. The backend is the only real check.

## Server state (TanStack Query)
- All API reads go through query hooks in the feature's `api.ts`. Query keys are arrays starting with the resource and edition: `['visitor-leads', editionId, filters]`.
- Mutations invalidate the exact keys they affect. Use optimistic updates only for low-risk toggles; never for create, assignment, or verification.
- Polling (`refetchInterval`) for job status and dashboard. Stop polling when the job is finished or the tab is hidden.
- No server data in global client stores. Local UI state stays in components; cross-page UI state (sidebar collapsed, theme) in a small Zustand store or context.

## API client
- `openapi-typescript` generates types from `/api/v1/openapi.json` into `packages/api`. `openapi-fetch` client with:
  - `credentials: 'include'`
  - `X-CSRF-Token` header on unsafe methods
  - `Idempotency-Key` (UUID) on endpoints that require it, generated once per user action and reused on retry
  - error envelope parsed into a typed `ApiError` (`code`, `message`, `fields`, `request_id`)
- `pnpm gen:api` regenerates; CI fails if the committed client differs from the backend schema.
- 401 anywhere redirects to login and keeps the return URL.

## Time and formatting
- Dates from the API are UTC ISO strings. Display in the edition timezone using `@date-fns/tz`; show relative time ("2 h") in lists with the absolute value in a tooltip, like Frappe.
- Display format follows the screenshot: `DD-MM-YYYY HH:mm:ss` for datetimes. Keep one formatter in `lib/format.ts`.
- Numbers with `Intl.NumberFormat('en')`.

## Build
- Vite, TypeScript strict, path aliases (`@/`, `@ems/ui`, `@ems/api`).
- Environment via `import.meta.env.VITE_*`; no secrets in the frontend.
- Production build is static files served by nginx.
