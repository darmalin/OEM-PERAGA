"""Operational commands: python -m app.cli <command>."""

import argparse
import asyncio
import getpass
import os

from app.core.config import get_settings
from app.core.storage import get_storage


def ensure_buckets() -> None:
    s = get_settings()
    storage = get_storage()
    for bucket in (s.s3_bucket_imports, s.s3_bucket_exports):
        storage.ensure_bucket(bucket)
    print("buckets ready")


def create_superuser() -> None:
    """Interactive, or non-interactive with EMS_BOOTSTRAP_EMAIL/NAME/PASSWORD."""
    from app.core.db import task_session
    from app.modules.identity import service

    email = os.environ.get("EMS_BOOTSTRAP_EMAIL") or input("Email: ")
    name = os.environ.get("EMS_BOOTSTRAP_NAME") or input("Full name: ")
    password = os.environ.get("EMS_BOOTSTRAP_PASSWORD") or getpass.getpass("Password: ")

    async def run() -> None:
        async with task_session() as session, session.begin():
            user = await service.create_superuser(session, email, name, password)
            print(f"super admin ready: {user.id}")

    asyncio.run(run())


COMMANDS = {"ensure-buckets": ensure_buckets, "create-superuser": create_superuser}


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    parser.add_argument("command", choices=sorted(COMMANDS))
    args = parser.parse_args()
    COMMANDS[args.command]()


if __name__ == "__main__":
    main()
