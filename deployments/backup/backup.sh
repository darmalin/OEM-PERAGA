#!/usr/bin/env bash
# Backup PostgreSQL (custom-format dump) and the object storage volume.
# Usage: deployments/backup/backup.sh [output_dir]     (run from the repo root)
# Schedule it daily (cron/systemd timer) and copy the output off this host.
set -euo pipefail

OUT="$(realpath -m "${1:-backups}")"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT"

DB_FILE="$OUT/ems-db-$STAMP.dump"
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$DB_FILE"
echo "database: $DB_FILE ($(du -h "$DB_FILE" | cut -f1))"

# Files are copied from the running storage container's volume. Exports are short-lived;
# import uploads and error reports are the files worth keeping.
STORAGE_CID="$(docker compose ps -q storage)"
FILES="$OUT/ems-storage-$STAMP.tar.gz"
docker run --rm --volumes-from "$STORAGE_CID:ro" -v "$OUT:/out" --entrypoint tar postgres:17 \
  czf "/out/$(basename "$FILES")" -C /data .
echo "storage:  $FILES ($(du -h "$FILES" | cut -f1))"
