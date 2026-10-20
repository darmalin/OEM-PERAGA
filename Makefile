COMPOSE ?= docker compose
TEST_DB_URL = postgresql+asyncpg://ems:ems@postgres:5432/ems_test
RUN_BACKEND = $(COMPOSE) run --rm --no-deps -T
TEST_ENV = -e EMS_ENVIRONMENT=test -e EMS_DATABASE_URL=$(TEST_DB_URL) -e EMS_REDIS_URL=redis://redis:6379/15 -e EMS_EMAIL_BACKEND=memory

.PHONY: up down logs migrate test lint fmt typecheck gen-api shell

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f api worker beat

migrate:
	$(COMPOSE) run --rm migrate

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

shell:
	$(COMPOSE) exec api sh
