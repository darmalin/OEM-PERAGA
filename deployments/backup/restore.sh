#!/usr/bin/env bash
# Restore a database dump made by backup.sh.
# Usage: deployments/backup/restore.sh <dump-file> [target-db]
#
# Default target is a NEW database (safe to try). To replace the live database, stop
# api/worker/beat first, then pass the live database name; it is dropped and recreated.
set -euo pipefail

DUMP="${1:?dump file required}"
TARGET="${2:-ems_restored}"

docker compose exec -T postgres sh -c "dropdb -U \"\$POSTGRES_USER\" --if-exists \"$TARGET\" && createdb -U \"\$POSTGRES_USER\" \"$TARGET\""
docker compose exec -T postgres sh -c "pg_restore -U \"\$POSTGRES_USER\" -d \"$TARGET\" --no-owner --exit-on-error" < "$DUMP"
echo "restored into $TARGET"
