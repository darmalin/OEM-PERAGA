"""gate_scanner

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gates",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_gates_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["exhibition_editions.id"],
            name=op.f("fk_gates_edition_id_exhibition_editions"),
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], name=op.f("fk_gates_updated_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gates")),
        sa.UniqueConstraint("edition_id", "code", name=op.f("uq_gates_edition_id_code")),
    )
    op.create_index(op.f("ix_gates_edition_id"), "gates", ["edition_id"], unique=False)
    op.create_table(
        "scanner_devices",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("gate_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("activation_code_hash", sa.String(length=64), nullable=True),
        sa.Column("activation_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("secret_hash", sa.String(length=64), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.Uuid(), nullable=True),
        sa.Column("revoke_reason", sa.String(length=500), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "status <> 'ACTIVE' OR secret_hash IS NOT NULL",
            name=op.f("ck_scanner_devices_active_has_secret"),
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'ACTIVE', 'REVOKED')",
            name=op.f("ck_scanner_devices_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_scanner_devices_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["exhibition_editions.id"],
            name=op.f("fk_scanner_devices_edition_id_exhibition_editions"),
        ),
        sa.ForeignKeyConstraint(
            ["gate_id"], ["gates.id"], name=op.f("fk_scanner_devices_gate_id_gates")
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by"], ["users.id"], name=op.f("fk_scanner_devices_revoked_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], name=op.f("fk_scanner_devices_updated_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scanner_devices")),
        sa.UniqueConstraint(
            "activation_code_hash", name=op.f("uq_scanner_devices_activation_code_hash")
        ),
    )
    op.create_index(
        op.f("ix_scanner_devices_edition_id"), "scanner_devices", ["edition_id"], unique=False
    )
    op.create_index(
        op.f("ix_scanner_devices_gate_id"), "scanner_devices", ["gate_id"], unique=False
    )
    op.create_table(
        "scan_attempts",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("gate_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=True),
        sa.Column("scan_event_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=True),
        sa.Column("credential_id", sa.Uuid(), nullable=True),
        sa.Column("registration_id", sa.Uuid(), nullable=True),
        sa.Column("mode", sa.String(length=10), nullable=False),
        sa.Column("outcome", sa.String(length=30), nullable=False),
        sa.Column("provisional_result", sa.String(length=30), nullable=True),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("recorded_by", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "mode <> 'OVERRIDE' OR (recorded_by IS NOT NULL AND reason IS NOT NULL)",
            name=op.f("ck_scan_attempts_override_attributed"),
        ),
        sa.CheckConstraint(
            "mode IN ('ONLINE', 'OFFLINE', 'OVERRIDE')", name=op.f("ck_scan_attempts_mode_valid")
        ),
        sa.CheckConstraint(
            "outcome IN ('ACCEPTED', 'REJECTED_UNKNOWN', 'REJECTED_REVOKED', 'REJECTED_WRONG_EDITION', 'REJECTED_CANCELLED')",
            name=op.f("ck_scan_attempts_outcome_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["credential_id"],
            ["qr_credentials.id"],
            name=op.f("fk_scan_attempts_credential_id_qr_credentials"),
        ),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["scanner_devices.id"],
            name=op.f("fk_scan_attempts_device_id_scanner_devices"),
        ),
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["exhibition_editions.id"],
            name=op.f("fk_scan_attempts_edition_id_exhibition_editions"),
        ),
        sa.ForeignKeyConstraint(
            ["gate_id"], ["gates.id"], name=op.f("fk_scan_attempts_gate_id_gates")
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by"], ["users.id"], name=op.f("fk_scan_attempts_recorded_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["registration_id"],
            ["visitor_registrations.id"],
            name=op.f("fk_scan_attempts_registration_id_visitor_registrations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scan_attempts")),
        sa.UniqueConstraint("scan_event_id", name=op.f("uq_scan_attempts_scan_event_id")),
    )
    op.create_index(
        "ix_scan_attempts_edition_date", "scan_attempts", ["edition_id", "local_date"], unique=False
    )
    op.create_index(
        "ix_scan_attempts_gate_scanned", "scan_attempts", ["gate_id", "scanned_at"], unique=False
    )
    op.create_index(
        "ix_scan_attempts_registration_date",
        "scan_attempts",
        ["registration_id", "local_date"],
        unique=False,
    )
    op.create_table(
        "visitor_checkins",
        sa.Column("edition_id", sa.Uuid(), nullable=False),
        sa.Column("registration_id", sa.Uuid(), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("first_scan_attempt_id", sa.Uuid(), nullable=False),
        sa.Column("first_scanned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("gate_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["edition_id"],
            ["exhibition_editions.id"],
            name=op.f("fk_visitor_checkins_edition_id_exhibition_editions"),
        ),
        sa.ForeignKeyConstraint(
            ["first_scan_attempt_id"],
            ["scan_attempts.id"],
            name=op.f("fk_visitor_checkins_first_scan_attempt_id_scan_attempts"),
        ),
        sa.ForeignKeyConstraint(
            ["gate_id"], ["gates.id"], name=op.f("fk_visitor_checkins_gate_id_gates")
        ),
        sa.ForeignKeyConstraint(
            ["registration_id"],
            ["visitor_registrations.id"],
            name=op.f("fk_visitor_checkins_registration_id_visitor_registrations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_visitor_checkins")),
        sa.UniqueConstraint(
            "first_scan_attempt_id", name=op.f("uq_visitor_checkins_first_scan_attempt_id")
        ),
        sa.UniqueConstraint(
            "registration_id",
            "local_date",
            name=op.f("uq_visitor_checkins_registration_id_local_date"),
        ),
    )
    op.create_index(
        "ix_visitor_checkins_edition_date",
        "visitor_checkins",
        ["edition_id", "local_date"],
        unique=False,
    )
    op.add_column("user_role_assignments", sa.Column("gate_id", sa.Uuid(), nullable=True))
    op.create_index(
        op.f("ix_user_role_assignments_gate_id"), "user_role_assignments", ["gate_id"], unique=False
    )
    op.create_foreign_key(
        op.f("fk_user_role_assignments_gate_id_gates"),
        "user_role_assignments",
        "gates",
        ["gate_id"],
        ["id"],
    )
    op.create_check_constraint(
        op.f("ck_user_role_assignments_gate_scope_has_gate"),
        "user_role_assignments",
        "scope_type <> 'GATE' OR (gate_id IS NOT NULL AND edition_id IS NOT NULL)",
    )
    op.execute(
        "CREATE TRIGGER scan_attempts_append_only BEFORE UPDATE OR DELETE ON scan_attempts "
        "FOR EACH ROW EXECUTE FUNCTION ems_forbid_mutation()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER scan_attempts_append_only ON scan_attempts")
    op.drop_constraint(
        op.f("ck_user_role_assignments_gate_scope_has_gate"), "user_role_assignments", type_="check"
    )
    op.drop_constraint(
        op.f("fk_user_role_assignments_gate_id_gates"), "user_role_assignments", type_="foreignkey"
    )
    op.drop_index(op.f("ix_user_role_assignments_gate_id"), table_name="user_role_assignments")
    op.drop_column("user_role_assignments", "gate_id")
    op.drop_index("ix_visitor_checkins_edition_date", table_name="visitor_checkins")
    op.drop_table("visitor_checkins")
    op.drop_index("ix_scan_attempts_registration_date", table_name="scan_attempts")
    op.drop_index("ix_scan_attempts_gate_scanned", table_name="scan_attempts")
    op.drop_index("ix_scan_attempts_edition_date", table_name="scan_attempts")
    op.drop_table("scan_attempts")
    op.drop_index(op.f("ix_scanner_devices_gate_id"), table_name="scanner_devices")
    op.drop_index(op.f("ix_scanner_devices_edition_id"), table_name="scanner_devices")
    op.drop_table("scanner_devices")
    op.drop_index(op.f("ix_gates_edition_id"), table_name="gates")
    op.drop_table("gates")
