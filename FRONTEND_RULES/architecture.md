# Frontend Architecture

## Workspace

```text
frontend/
├── apps/
│   ├── web/                    # desk app
│   │   └── src/
│   │       ├── main.tsx
│   │       ├── routes/         # TanStack Router file-based routes
│   │       ├── features/
│   │       │   ├── auth/
│   │       │   ├── exhibitions/
│   │       │   ├── visitors/
│   │       │   ├── telemarketing/
│   │       │   ├── registrations/
│   │       │   ├── gate/
│   │       │   ├── reports/
│   │       │   └── setup/      # users, roles, custom fields, audit log
│   │       ├── shell/          # top bar, sidebar, command bar, edition switcher
│   │       └── lib/
│   └── scanner/                # PWA, see scanner-pwa.md
└── packages/
    ├── ui/                     # shadcn components, tokens, Frappe patterns (ListView, FormSection, Indicator)
    └── api/                    # generated client + query helpers
```

- `apps/*` may import from `packages/*`. Packages never import from apps. Features never import from other features; shared code moves to `packages/ui` or `apps/web/src/lib`.
- Inside a feature: `api.ts` (query/mutation hooks), `components/`, `pages/` (route components), `schemas.ts` (Zod form schemas), `labels.ts` (English display labels for enums).

## Routing (TanStack Router)
- File-based routes. URL shape follows Frappe:
  - `/app/visitor-leads` list, `/app/visitor-leads/new`, `/app/visitor-leads/$id`
  - `/app/my-calls`, `/app/followups`, `/app/gates`, `/app/reports/$report`, `/app/setup/...`
- The active edition is a search param on every event-data route (`?edition=IBTE2027`) and is persisted per user. Switching edition updates the URL.
- List filters, sort, and page are typed search params (validated with Zod). Reloading or sharing a URL reproduces the same list.
- Route `beforeLoad` checks the permission from `/auth/me` and redirects to a no-access page; this is UX only.

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
