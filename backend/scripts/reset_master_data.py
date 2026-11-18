"""Clear all exhibition data and keep the system data (owner request 2026-11-18).

Cleared: exhibitions, editions, venues, booths, exhibitor leads, portal accounts, contracts,
payments, quotations, order forms and orders, visitor leads, registrations, QR codes, check-ins,
gates, telemarketing, campaigns, imports and exports, and every uploaded file (the five storage
buckets hold only that data).

Kept: users, roles, permissions, teams, email accounts, audit logs, and system emails (password
resets, tests). Removed from the kept tables only the rows that point at cleared data: emails
sent for an edition or a visitor, edition email templates, and role grants scoped to an edition
or a gate (the user and the role stay).

Every table must be listed in KEEP or CLEAR: a table added later stops the script until someone
decides which side it is on. The database part runs in one transaction; files are removed after
the commit, so a failed file step can be finished by running the script again.

    docker exec ems-api-preview python -m scripts.reset_master_data            # counts only
    docker exec ems-api-preview python -m scripts.reset_master_data --yes ems  # clears "ems"

The counts start with the database and buckets the run will touch; --yes must name that same
database, so a run pointed somewhere else by mistake stops.

Back up first on a shared server: pg_dump -Fc ems > before-reset.dump
"""

import argparse
import asyncio
import sys
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.config import get_settings
from app.core.db import get_engine
from app.core.storage import S3Storage, get_storage

if TYPE_CHECKING:
    from types_boto3_s3.type_defs import ObjectIdentifierTypeDef

KEEP = {
    "alembic_version",
    "users",
    "roles",
    "permissions",
    "role_permissions",
    "teams",
    "user_team_memberships",
    "user_role_assignments",  # minus edition and gate grants
    "password_reset_tokens",
    "email_accounts",
    "email_templates",  # minus edition templates
    "email_jobs",  # minus emails for cleared data
    "email_logs",
    "outbox_events",
    "audit_logs",
    "idempotency_keys",
}

CLEAR = {
    "exhibitions",
    "exhibition_editions",
    "edition_counters",
    "edition_teams",
    "venues",
    "booths",
    "exhibitor_accounts",
    "exhibitor_leads",
    "exhibitor_contracts",
    "exhibitor_contract_counters",
    "exhibitor_payments",
    "exhibitor_quotations",
    "quotation_counters",
    "quotation_settings",
    "order_forms",
    "order_form_items",
    "order_form_options",
    "order_form_allowances",
    "exhibitor_orders",
    "exhibitor_order_lines",
    "exhibitor_order_files",
    "exhibitor_order_counters",
    "exhibitor_form_waivers",
    "visitor_leads",
    "visitor_custom_field_definitions",
    "edition_field_options",
    "lead_sources",
    "visitor_registrations",
    "qr_credentials",
    "visitor_checkins",
    "scan_attempts",
    "scanner_devices",
    "gates",
    "visitor_call_activities",
    "visitor_followups",
    "visitor_followup_changes",
    "visitor_verifications",
    "followup_reminders",
    "lead_assignment_history",
    "assignment_jobs",
    "round_robin_cursors",
    "campaign_links",
    "campaign_submissions",
    "campaign_views",
    "import_jobs",
    "import_errors",
    "import_mapping_presets",
    "export_jobs",
}

# Emails tied to cleared data: sent for an edition, a visitor, or from an edition template.
DOOMED_JOBS = """
    CREATE TEMP TABLE doomed_jobs ON COMMIT DROP AS
    SELECT id FROM email_jobs
    WHERE edition_id IS NOT NULL OR registration_id IS NOT NULL OR qr_credential_id IS NOT NULL
       OR visitor_lead_id IS NOT NULL
       OR template_id IN (SELECT id FROM email_templates WHERE edition_id IS NOT NULL)
"""

PARTIAL = [
    (
        "email_logs",
        "DELETE FROM email_logs WHERE email_job_id IN (SELECT id FROM doomed_jobs)",
    ),
    # Email events of cleared emails, and every other event: those all concern cleared data.
    (
        "outbox_events",
        "DELETE FROM outbox_events WHERE NOT (payload ? 'email_job_id')"
        " OR (payload->>'email_job_id')::uuid IN (SELECT id FROM doomed_jobs)",
    ),
    ("email_jobs", "DELETE FROM email_jobs WHERE id IN (SELECT id FROM doomed_jobs)"),
    ("email_templates", "DELETE FROM email_templates WHERE edition_id IS NOT NULL"),
    (
        "user_role_assignments",
        "DELETE FROM user_role_assignments WHERE edition_id IS NOT NULL OR gate_id IS NOT NULL",
    ),
]

# Append-only tables that lose some rows here. TRUNCATE does not fire their row triggers.
APPEND_ONLY = {
    "email_logs": "email_logs_append_only",
    "email_templates": "email_templates_append_only",
}


def buckets() -> list[str]:
    s = get_settings()
    return [
        s.s3_bucket_imports,
        s.s3_bucket_exports,
        s.s3_bucket_contracts,
        s.s3_bucket_orders,
        s.s3_bucket_quotations,
    ]


async def tables(conn: AsyncConnection) -> set[str]:
    rows = await conn.execute(
        text("SELECT tablename FROM pg_tables WHERE schemaname = current_schema()")
    )
    return {name for (name,) in rows}


async def count(conn: AsyncConnection, table: str, where: str = "TRUE") -> int:
    # Table names and conditions come from the constants above, never from input.
    sql = f"SELECT count(*) FROM {table} WHERE {where}"  # noqa: S608
    return int((await conn.execute(text(sql))).scalar_one())


async def report(conn: AsyncConnection) -> None:
    database, host = (
        await conn.execute(text("SELECT current_database(), inet_server_addr()"))
    ).one()
    print(f"Database: {database} on {host or 'local socket'}")
    print(f"Buckets:  {', '.join(buckets())}\n")
    await conn.execute(text(DOOMED_JOBS))
    print("Cleared whole:")
    for table in sorted(CLEAR):
        print(f"  {table:36} {await count(conn, table):>8}")
    print("Cleared in part (rows tied to cleared data):")
    for table, delete in PARTIAL:
        condition = delete.split(" WHERE ", 1)[1]
        print(f"  {table:36} {await count(conn, table, condition):>8}")
    print("Kept:")
    for table in ("users", "roles", "teams", "email_accounts", "audit_logs"):
        print(f"  {table:36} {await count(conn, table):>8}")


async def clear(conn: AsyncConnection) -> None:
    for table, trigger in APPEND_ONLY.items():
        await conn.execute(text(f"ALTER TABLE {table} DISABLE TRIGGER {trigger}"))
    for _, delete in PARTIAL:
        await conn.execute(text(delete))
    for table, trigger in APPEND_ONLY.items():
        await conn.execute(text(f"ALTER TABLE {table} ENABLE TRIGGER {trigger}"))
    # Postgres refuses TRUNCATE while a kept table has a foreign key into a cleared one, even
    # with no rows left behind it. Those keys are dropped and added back by name; adding them
    # back checks every kept row, so one still pointing at cleared data fails the whole run.
    keys = (
        await conn.execute(
            text(
                "SELECT conrelid::regclass::text, conname, pg_get_constraintdef(oid)"
                " FROM pg_constraint WHERE contype = 'f'"
                " AND conrelid::regclass::text = ANY(:keep)"
                " AND confrelid::regclass::text = ANY(:clear)"
            ),
            {"keep": sorted(KEEP), "clear": sorted(CLEAR)},
        )
    ).all()
    for table, name, _ in keys:
        await conn.execute(text(f"ALTER TABLE {table} DROP CONSTRAINT {name}"))
    # No CASCADE: it would empty the kept tables that point here.
    await conn.execute(text(f"TRUNCATE {', '.join(sorted(CLEAR))} RESTART IDENTITY"))
    for table, name, definition in keys:
        await conn.execute(text(f"ALTER TABLE {table} ADD CONSTRAINT {name} {definition}"))


def clear_files() -> None:
    storage = get_storage()
    if not isinstance(storage, S3Storage):
        print("Files: no S3 storage configured, skipped.")
        return
    client = storage._client
    for bucket in buckets():
        removed = 0
        for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket):
            keys: list[ObjectIdentifierTypeDef] = [
                {"Key": o["Key"]} for o in page.get("Contents", [])
            ]
            if keys:
                client.delete_objects(Bucket=bucket, Delete={"Objects": keys, "Quiet": True})
                removed += len(keys)
        print(f"Files: {bucket:12} {removed} removed")


async def main(yes: str | None, production: bool) -> int:
    settings = get_settings()
    if settings.environment == "production" and not production:
        print("This is production. Add --production as well if you really mean it.")
        return 2
    engine = get_engine()
    async with engine.begin() as conn:
        found = await tables(conn)
        unknown = found - KEEP - CLEAR
        missing = (KEEP | CLEAR) - found
        if unknown or missing:
            for name in sorted(unknown):
                print(f"Table {name} is in neither KEEP nor CLEAR: decide its side first.")
            for name in sorted(missing):
                print(f"Table {name} is listed but not in the database (migrations behind?).")
            return 1
        await report(conn)
        database = (await conn.execute(text("SELECT current_database()"))).scalar_one()
        if yes != database:
            if yes is not None:
                print(f"\n--yes names {yes!r} but this is {database!r}: nothing changed.")
            else:
                print(f"\nNothing changed. Run again with --yes {database} to clear.")
            await conn.rollback()
            return 0 if yes is None else 1
        await clear(conn)
    print("\nDatabase cleared.")
    clear_files()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--yes", metavar="DATABASE", help="clear; must name the database (without it: counts only)"
    )
    parser.add_argument("--production", action="store_true", help="allow on production")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.yes, args.production)))
