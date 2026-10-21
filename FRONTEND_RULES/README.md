# Frontend Rules

Rules for `frontend/apps/web` (desk), `frontend/apps/scanner` (PWA), and the shared packages. Visual direction is `DESIGN/DESIGN.md`; these files cover how to build it.

| File | Covers |
|---|---|
| [architecture.md](architecture.md) | Workspace layout, feature folders, routing, data fetching |
| [coding-standards.md](coding-standards.md) | TypeScript, React, naming, forms |
| [ui-components.md](ui-components.md) | shadcn customization, tokens, Frappe patterns, states, accessibility |
| [scanner-pwa.md](scanner-pwa.md) | Offline cache, scan queue, sync |
| [testing.md](testing.md) | Unit, component, E2E |
| [known-gaps.md](known-gaps.md) | What is not built or not verified yet. Read before starting work |

## The non-negotiables

1. **English only** for every label, message, button, placeholder, and toast. No Indonesian strings in code or UI. User data renders as entered.
2. The frontend never decides permissions or duplicates. It hides what the user cannot do (using `/auth/me` permissions) for convenience; the backend enforces.
3. API types come from the generated OpenAPI client. No hand-written request/response types for API data.
4. Every data view has loading, empty, error, and no-permission states (`DESIGN/DESIGN.md` "States").
5. Every interactive element works with the keyboard and has a visible focus ring.
6. Only routes that exist and the user may open appear in the sidebar or command bar.
7. No invented data in the UI: no placeholder numbers, no fake names in screenshots or demos.
8. Both light and dark themes are checked before a screen is merged.
