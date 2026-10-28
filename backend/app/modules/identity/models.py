import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, UUIDPk, Versioned
from app.modules.identity.rules import ScopeType


class User(UUIDPk, Timestamps, Versioned, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class Permission(UUIDPk, Base):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")


class Role(UUIDPk, Timestamps, Base):
    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Lists show roles by this number, highest access first (1 = Super Admin).
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class Team(UUIDPk, Timestamps, Versioned, Base):
    __tablename__ = "teams"

    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class UserTeamMembership(Base):
    __tablename__ = "user_team_memberships"

    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EditionTeam(Base):
    """The team that works an edition's leads (one per edition); its members with
    telemarketing.call receive imported leads round robin."""

    __tablename__ = "edition_teams"

    edition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exhibition_editions.id", ondelete="CASCADE"), primary_key=True
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class UserRoleAssignment(UUIDPk, Base):
    """A role granted to a user, limited to a scope.

    edition_id NULL means every edition (cross-edition scope, spec 9.2).
    """

    __tablename__ = "user_role_assignments"
    __table_args__ = (
        CheckConstraint(
            "scope_type IN ('EDITION', 'TEAM', 'OWNED', 'GATE')", name="scope_type_valid"
        ),
        CheckConstraint("scope_type <> 'TEAM' OR team_id IS NOT NULL", name="team_scope_has_team"),
        CheckConstraint(
            "scope_type <> 'GATE' OR (gate_id IS NOT NULL AND edition_id IS NOT NULL)",
            name="gate_scope_has_gate",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id"), nullable=False, index=True)
    scope_type: Mapped[ScopeType] = mapped_column(String(20), nullable=False)
    edition_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("exhibition_editions.id"), index=True
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("teams.id"), index=True)
    gate_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("gates.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class PasswordResetToken(UUIDPk, Base):
    __tablename__ = "password_reset_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
