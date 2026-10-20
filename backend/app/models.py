"""Imports every model so Alembic sees the full metadata."""

from app.core.db import Base
from app.core.outbox import OutboxEvent

__all__ = ["Base", "OutboxEvent"]
