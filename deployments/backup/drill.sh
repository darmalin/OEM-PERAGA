#!/usr/bin/env bash
# Backup/restore drill (spec 15, M6): back up, restore into a scratch database, compare
# row counts of every table, drop the scratch database. Exit code 1 on any mismatch.
# Usage: deployments/backup/drill.sh [output_dir]
set -euo pipefail

HERE="$(dirname "$0")"
OUT="${1:-backups}"
SCRATCH=ems_restore_drill

"$HERE/backup.sh" "$OUT"
DUMP="$(ls -t "$OUT"/ems-db-*.dump | head -1)"
"$HERE/restore.sh" "$DUMP" "$SCRATCH"

counts() {
  docker compose exec -T postgres sh -c "psql -U \"\$POSTGRES_USER\" -d \"$1\" -AtF' ' -c \"
    SELECT format('SELECT %L, count(*) FROM %I UNION ALL', tablename, tablename)
    FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename\" \
    | sed '\$ s/ UNION ALL\$//' | psql -U \"\$POSTGRES_USER\" -d \"$1\" -AtF' '"
}
LIVE_DB="$(docker compose exec -T postgres sh -c 'echo $POSTGRES_DB')"
diff <(counts "$LIVE_DB") <(counts "$SCRATCH") > /tmp/ems-drill.diff && RESULT=PASS || RESULT=FAIL
TABLES="$(counts "$SCRATCH" | wc -l)"
ROWS="$(counts "$SCRATCH" | awk '{s+=$2} END {print s}')"
docker compose exec -T postgres sh -c "dropdb -U \"\$POSTGRES_USER\" $SCRATCH"

echo "drill: $RESULT ($TABLES tables, $ROWS rows compared, dump $DUMP)"
[ "$RESULT" = PASS ] || { cat /tmp/ems-drill.diff; exit 1; }
