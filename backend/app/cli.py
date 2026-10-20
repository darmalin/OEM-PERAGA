"""Operational commands: python -m app.cli <command>."""

import argparse

from app.core.config import get_settings
from app.core.storage import get_storage


def ensure_buckets() -> None:
    s = get_settings()
    storage = get_storage()
    for bucket in (s.s3_bucket_imports, s.s3_bucket_exports):
        storage.ensure_bucket(bucket)
    print("buckets ready")


COMMANDS = {"ensure-buckets": ensure_buckets}


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    parser.add_argument("command", choices=sorted(COMMANDS))
    args = parser.parse_args()
    COMMANDS[args.command]()


if __name__ == "__main__":
    main()
