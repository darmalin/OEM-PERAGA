# 00 Foundation

Bootstrap the repo so every later feature has the same base. See `TECH_STACK.md`.

## Tasks

### Repo and tooling
- [ ] Create layout from `TECH_STACK.md` (`backend/`, `frontend/apps/web`, `frontend/apps/scanner`, `frontend/packages/ui`, `frontend/packages/api`).
- [ ] Backend: `uv` project, Ruff, mypy strict, pytest, pre-commit.
- [ ] Frontend: pnpm workspace, Vite + React + TS strict, Tailwind v4, shadcn init in `packages/ui`, ESLint, Vitest, Playwright.
- [ ] `.editorconfig`, `.gitignore`, `.env.example`.

### Docker
- [ ] `backend/Dockerfile` (multi-stage, non-root user, `uv sync --frozen`).
- [ ] `compose.yaml`: nginx, api, worker, beat, migrate, postgres, redis, minio, with healthchecks and named volumes.
- [ ] `compose.override.yaml`: bind mounts, `uvicorn --reload`, Vite dev servers, mailpit, exposed ports.
- [ ] Nginx config: `/api` to `api`, `/` to web, `/scan` to scanner, `client_max_body_size` for Excel uploads.
- [ ] `make` or `just` targets: `up`, `down`, `migrate`, `test`, `lint`, `gen-api`.

### Backend platform (`app/core`)
- [ ] Settings via `pydantic-settings`, read from env only.
- [ ] Async SQLAlchemy engine, session dependency, one transaction per request.
- [ ] Alembic wired to the model metadata; naming convention for constraints.
- [ ] Structured JSON logging with request/correlation ID middleware.
- [ ] Error handler producing the error envelope in `BACKEND_RULES/api.md`.
- [ ] Health endpoints: `/api/v1/health/live`, `/api/v1/health/ready` (checks DB and Redis).
- [ ] Celery app with Redis broker, JSON serializer, `acks_late`, task base class that sets correlation ID.
- [ ] Storage client (S3/MinIO) and email client interfaces.

### Frontend platform
- [ ] OpenAPI generation script: FastAPI `openapi.json` to `packages/api`.
- [ ] Fetch wrapper: cookie credentials, CSRF header, error envelope parsing.
- [ ] App shell from `DESIGN/DESIGN.md` (top bar, sidebar, page head) with real routes only.
- [ ] Light/dark/system theme toggle.

### CI
- [ ] Lint, type check, unit tests, integration tests against Postgres + Redis services, frontend build.

## Acceptance criteria
- `docker compose up` on a clean machine brings up a working login page and a ready health check.
- `alembic upgrade head` on an empty DB succeeds; `alembic downgrade -1` works for the latest migration.
- CI fails on lint, type, or test errors.
