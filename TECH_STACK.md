# EMS Visitor CRM: Tech Stack

Locked on 2026-10-20. Source spec: `DEV_DOCS/EMS-Visitor-CRM-Specification.md`.

The spec recommended Go. The team switched to **Python + FastAPI** because the team are Frappe engineers: same language, faster delivery, and the business rules (duplicates, scope, idempotency, offline sync) are safer in a language the team already knows. Every other principle of the spec stays: modular monolith, PostgreSQL as source of truth, edition scoping, backend-enforced permissions, audit log, background workers, idempotency.

**System language is English.** Every UI label, API field, error message, email template, log line, database identifier, and code comment is in English. User-entered data (names, cities, comments) can be in any language and must render correctly (UTF-8 end to end, Vietnamese diacritics included).

## Stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.13 | Team background (Frappe). |
| API framework | FastAPI | Async, typed, OpenAPI generated from code, which feeds the frontend client. |
| Validation | Pydantic v2 | Request and response schemas, custom field validation. |
| ORM / DB access | SQLAlchemy 2.0 (async) + asyncpg | Explicit queries, transactions, `SELECT ... FOR UPDATE`, partial unique indexes. |
| Migrations | Alembic | Versioned, reviewed migrations. No auto-sync like `bench migrate`. |
| Database | PostgreSQL 17 | Partial unique indexes, JSONB for custom fields, sequences. |
| Queue / cache | Redis 7.4 (or Valkey 8) | Celery broker, session store, rate limiting. |
| Background jobs | Celery 5 + Celery Beat | Email, import, export, follow-up reminders, outbox dispatch. Retries and scheduling built in. |
| Auth | Server-side sessions in Redis, `HttpOnly` + `Secure` + `SameSite=Lax` cookie, CSRF token | Matches spec section 2. No JWT in browser storage. |
| Password hashing | Argon2id (`pwdlib[argon2]`) | Current recommended default. |
| Excel | `openpyxl` (read-only / write-only modes) | Streams large files in the worker. |
| Phone normalization | `phonenumbers` | E.164 normalization (spec 5.2). |
| QR | `segno` | Generates QR images for email; token only, no PII. |
| Email | SMTP or provider API behind one interface; Mailpit in dev | Spec 7.3. |
| File storage | S3-compatible: MinIO (dev/self-host), any S3 in prod; `boto3` | Import uploads, export files. |
| Frontend | React 19 + Vite + TypeScript (strict) | Spec section 2. |
| UI kit | Tailwind CSS v4 + shadcn/ui (Radix) | Restyled to the Frappe Desk look in `DESIGN/DESIGN.md`. |
| Routing | TanStack Router | Type-safe URL search params, so list filters live in the URL like Frappe list views. |
| Server state | TanStack Query | Caching, refetch, optimistic updates. |
| Tables | TanStack Table | Lead list with selection, sorting, column config. |
| Forms | React Hook Form + Zod | Field-level errors mapped from API 422. |
| API client | `openapi-typescript` + `openapi-fetch` | Types generated from FastAPI's OpenAPI. No hand-written DTOs. |
| Scanner | Separate React PWA (`vite-plugin-pwa`), IndexedDB via Dexie, camera via `qr-scanner` | Offline cache and scan queue (spec 8.3). |
| Package managers | `uv` (Python), `pnpm` (Node 24 LTS) | Lockfiles committed. |
| Lint / type check | Ruff + mypy (strict) / ESLint + `tsc --noEmit` | CI gate. |
| Tests | pytest + pytest-asyncio + httpx; Vitest + Testing Library; Playwright for E2E | Spec section 16. |
| Reverse proxy | Nginx | TLS, static files, `/api` proxy, upload size limits. |
| Deployment | Docker Compose | Spec section 2. |

Pin exact versions in `pyproject.toml` / `uv.lock` and `package.json` / `pnpm-lock.yaml` at bootstrap. Do not upgrade a major version without a ticket.

## Docker Compose services

| Service | Image / build | Purpose | Dev only |
|---|---|---|---|
| `nginx` | `nginx:1.27-alpine` | Entry point. Serves built `web` and `scanner`, proxies `/api` to `api`. | |
| `api` | `backend/Dockerfile` | FastAPI via `uvicorn` (dev) or `gunicorn -k uvicorn.workers.UvicornWorker` (prod). | |
| `worker` | same image as `api` | `celery -A app.worker worker`. | |
| `beat` | same image as `api` | `celery -A app.worker beat`. Exactly one replica. | |
| `migrate` | same image as `api` | `alembic upgrade head`, runs once before `api` starts. | |
| `web` | `frontend/apps/web` | Vite dev server in dev; static build copied into `nginx` in prod. | dev server only |
| `scanner` | `frontend/apps/scanner` | Same pattern as `web`. Must be served over HTTPS for camera and service worker. | dev server only |
| `postgres` | `postgres:17` | Named volume, healthcheck. | |
| `redis` | `redis:7.4-alpine` | Broker, sessions. | |
| `minio` | `minio/minio` | S3-compatible storage. | |
| `mailpit` | `axllent/mailpit` | Catches all outgoing email in dev. | yes |

Files:

```text
compose.yaml            # base services, production-like
compose.override.yaml   # dev: bind mounts, hot reload, mailpit, exposed ports
.env.example            # every variable documented, no real secrets
```

## Repository layout

```text
ems/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── worker.py
│   │   ├── core/          # config, db, auth, authorization, audit, email, storage, logging
│   │   └── modules/
│   │       ├── identity/
│   │       ├── exhibitions/
│   │       ├── visitors/
│   │       ├── telemarketing/
│   │       ├── registrations/
│   │       ├── checkin/
│   │       ├── importexport/
│   │       └── reporting/
│   ├── migrations/        # alembic
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── apps/
│   │   ├── web/           # desk app (CRM)
│   │   └── scanner/       # gate scanner PWA
│   ├── packages/
│   │   ├── ui/            # shadcn components + design tokens, shared by both apps
│   │   └── api/           # generated OpenAPI client
│   └── pnpm-workspace.yaml
├── deployments/nginx/
├── FEATURES/  DESIGN/  BACKEND_RULES/  FRONTEND_RULES/
├── compose.yaml
└── compose.override.yaml
```
