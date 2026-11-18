"""passport copies, the NPWP or KTP card, and order emails

Revision ID: 0040
Revises: 0039
Create Date: 2026-11-18

Customer feedback on the exhibitor guide (2026-11-18): a visa letter needs a passport copy per
person (new attachment purpose PASSPORT), and a company without an NPWP gives the signer's KTP,
with a photo of the card either way. Contracts that already have a tax ID had an NPWP. A
submitted order emails the exhibitor and the lead's owner (email kinds ORDER_RECEIVED and
ORDER_ALERT).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0040"
down_revision: str | None = "0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD = ["FITTING_LOCATION", "LOGO", "OTHER", "PRODUCT_IMAGE", "VISA_LIST"]
NEW = sorted([*OLD, "PASSPORT"])


def _quoted(values: list[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def _purposes(values: list[str]) -> None:
    op.drop_constraint(
        op.f("ck_order_forms_attachment_purposes_valid"), "order_forms", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_order_forms_attachment_purposes_valid"),
        "order_forms",
        f"attachment_purposes <@ ARRAY[{_quoted(values)}]::varchar[]",
    )
    op.drop_constraint(
        op.f("ck_exhibitor_order_files_purpose_valid"), "exhibitor_order_files", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_exhibitor_order_files_purpose_valid"),
        "exhibitor_order_files",
        f"purpose IN ({_quoted(values)})",
    )


KINDS = ["QR_CONFIRMATION", "PASSWORD_RESET", "FOLLOWUP_REMINDER", "TEST"]
ORDER_KINDS = ["ORDER_RECEIVED", "ORDER_ALERT"]


def _kinds(values: list[str]) -> None:
    op.drop_constraint(op.f("ck_email_jobs_kind_valid"), "email_jobs", type_="check")
    op.create_check_constraint(
        op.f("ck_email_jobs_kind_valid"), "email_jobs", f"kind IN ({_quoted(values)})"
    )


def upgrade() -> None:
    _kinds(KINDS + ORDER_KINDS)
    _purposes(NEW)
    op.add_column("exhibitor_contracts", sa.Column("tax_id_type", sa.String(4), nullable=True))
    op.add_column(
        "exhibitor_contracts", sa.Column("tax_id_file_key", sa.String(500), nullable=True)
    )
    op.add_column(
        "exhibitor_contracts", sa.Column("tax_id_file_name", sa.String(255), nullable=True)
    )
    op.create_check_constraint(
        op.f("ck_exhibitor_contracts_tax_id_type_valid"),
        "exhibitor_contracts",
        "tax_id_type IS NULL OR tax_id_type IN ('KTP', 'NPWP')",
    )
    op.execute("UPDATE exhibitor_contracts SET tax_id_type = 'NPWP' WHERE tax_id IS NOT NULL")


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_exhibitor_contracts_tax_id_type_valid"), "exhibitor_contracts", type_="check"
    )
    op.drop_column("exhibitor_contracts", "tax_id_file_name")
    op.drop_column("exhibitor_contracts", "tax_id_file_key")
    op.drop_column("exhibitor_contracts", "tax_id_type")
    op.execute("DELETE FROM exhibitor_order_files WHERE purpose = 'PASSPORT'")
    op.execute(
        "UPDATE order_forms SET attachment_purposes = array_remove(attachment_purposes, 'PASSPORT')"
    )
    _purposes(OLD)
    # The email log is append-only; paused for this one cleanup, as in migration 0018.
    op.execute("ALTER TABLE email_logs DISABLE TRIGGER email_logs_append_only")
    op.execute(
        "DELETE FROM email_logs WHERE email_job_id IN"
        " (SELECT id FROM email_jobs WHERE kind IN ('ORDER_RECEIVED', 'ORDER_ALERT'))"
    )
    op.execute("ALTER TABLE email_logs ENABLE TRIGGER email_logs_append_only")
    op.execute("DELETE FROM email_jobs WHERE kind IN ('ORDER_RECEIVED', 'ORDER_ALERT')")
    _kinds(KINDS)
