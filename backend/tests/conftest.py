import os
import subprocess
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

os.environ.setdefault("EMS_ENVIRONMENT", "test")
os.environ.setdefault("EMS_EMAIL_BACKEND", "memory")
os.environ.setdefault("EMS_SESSION_COOKIE_SECURE", "false")
os.environ.setdefault("EMS_APP_ENCRYPTION_KEY", "dGVzdC1vbmx5LWtleS1kby1ub3QtdXNlLWFueXdoZXJlIQ==")

from app.core.db import get_engine
from app.core.email import MemorySender, set_email_sender
from app.core.redis import get_redis
from app.core.storage import MemoryStorage, set_storage
from app.main import app
from app.modules.identity.rules import BASELINE_ROLES

# Seeded by migrations; never truncated between tests.
SEED_TABLES = {"alembic_version", "permissions", "roles", "role_permissions"}


@pytest.fixture(scope="session", autouse=True)
def _migrate() -> None:
    subprocess.run(["alembic", "upgrade", "head"], check=True)  # noqa: S607


@pytest.fixture(autouse=True)
async def _clean_state() -> AsyncIterator[None]:
    async with get_engine().begin() as conn:
        rows = await conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        tables = [r[0] for r in rows if r[0] not in SEED_TABLES]
        if tables:
            await conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
        # Restore the role seed in case a test edited roles.
        await conn.execute(text("DELETE FROM roles WHERE NOT is_system"))
        for code, (_name, perms) in BASELINE_ROLES.items():
            await conn.execute(
                text(
                    "DELETE FROM role_permissions WHERE role_id = "
                    "(SELECT id FROM roles WHERE code = :code)"
                ),
                {"code": code},
            )
            await conn.execute(
                text(
                    "INSERT INTO role_permissions (role_id, permission_id) "
                    "SELECT r.id, p.id FROM roles r JOIN permissions p ON p.code = ANY(:perms) "
                    "WHERE r.code = :code"
                ),
                {"code": code, "perms": perms},
            )
    await get_redis().flushdb()
    yield


@pytest.fixture
def storage() -> MemoryStorage:
    s = MemoryStorage()
    set_storage(s)
    return s


@pytest.fixture
def mailbox() -> MemorySender:
    sender = MemorySender()
    set_email_sender(sender)
    return sender


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
