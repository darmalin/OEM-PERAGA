COMPOSE ?= docker compose
TEST_DB_URL = postgresql+asyncpg://ems:ems@postgres:5432/ems_test
RUN_BACKEND = $(COMPOSE) run --rm --no-deps -T
TEST_ENV = -e EMS_ENVIRONMENT=test -e EMS_DATABASE_URL=$(TEST_DB_URL) -e EMS_REDIS_URL=redis://redis:6379/15 -e EMS_EMAIL_BACKEND=memory

.PHONY: up down logs migrate superuser test lint fmt typecheck gen-api shell web scanner campaign web-check e2e e2e-scanner e2e-campaign

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f api worker beat

migrate:
	$(COMPOSE) run --rm migrate

superuser:
	$(COMPOSE) run --rm api python -m app.cli create-superuser

test:
	$(COMPOSE) up -d postgres redis
	$(RUN_BACKEND) $(TEST_ENV) api pytest $(ARGS)

lint:
	$(RUN_BACKEND) api sh -c "ruff check . && ruff format --check ."

fmt:
	$(RUN_BACKEND) api sh -c "ruff format . && ruff check --fix ."

typecheck:
	$(RUN_BACKEND) api mypy

gen-api:
	$(RUN_BACKEND) api python -c "import json; from app.main import app; print(json.dumps(app.openapi()))" > openapi.json
	cd frontend && pnpm gen:api

# Frontend on the host (needs Node 24 + pnpm); the API stays in Docker behind :8080.
web:
	cd frontend && pnpm install && pnpm dev

# Scanner PWA dev server at http://localhost:5174/scanner/ (camera needs localhost or HTTPS).
scanner:
	cd frontend && pnpm install && pnpm dev:scanner

# Public campaign form dev server at http://localhost:5175/r/{token}.
campaign:
	cd frontend && pnpm install && pnpm dev:campaign

web-check:
	cd frontend && pnpm typecheck && pnpm lint && pnpm test && pnpm build

# Click-through and page sweep with a local Chromium; credentials from .env (EMS_DEV_ADMIN_*).
e2e:
	cd frontend/apps/web && set -a && . ../../../.env && set +a && \
	EMS_EMAIL=$$EMS_DEV_ADMIN_EMAIL EMS_PASSWORD=$$EMS_DEV_ADMIN_PASSWORD node e2e/flows.mjs && \
	EMS_EMAIL=$$EMS_DEV_ADMIN_EMAIL EMS_PASSWORD=$$EMS_DEV_ADMIN_PASSWORD node e2e/smoke.mjs

# Scanner offline flow (activate, scan offline, sync, replay, revoke); needs `make scanner` running.
e2e-scanner:
	cd frontend/apps/scanner && set -a && . ../../../.env && set +a && \
	EMS_EMAIL=$$EMS_DEV_ADMIN_EMAIL EMS_PASSWORD=$$EMS_DEV_ADMIN_PASSWORD node e2e/offline.mjs

# Public campaign form flow; needs `make campaign` running and an Active edition.
e2e-campaign:
	cd frontend/apps/campaign && set -a && . ../../../.env && set +a && \
	EMS_EMAIL=$$EMS_DEV_ADMIN_EMAIL EMS_PASSWORD=$$EMS_DEV_ADMIN_PASSWORD node e2e/form.mjs

shell:
	$(COMPOSE) exec api sh
