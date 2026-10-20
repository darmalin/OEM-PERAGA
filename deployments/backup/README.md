# Backup and restore

Run from the repository root, against the running Compose stack.

| Script | What it does |
|---|---|
| `backup.sh [dir]` | `pg_dump -Fc` of the database and a tarball of the object storage volume into `dir` (default `backups/`). |
| `restore.sh <dump> [db]` | Restores a dump into `db` (default `ems_restored`, a new database). To replace the live database, stop `api`, `worker`, and `beat` first and pass the live name. |
| `drill.sh [dir]` | Backup, restore into `ems_restore_drill`, compare the row count of every table, drop the scratch database. Exits 1 on any mismatch. |

Schedule `backup.sh` daily and copy its output off the host. Run `drill.sh` after every
schema change and at least monthly; a backup that was never restored is not a backup.

Restoring files: stop `storage`, then extract the tarball into the storage volume, e.g.
`docker run --rm --volumes-from <storage container> -v "$PWD/backups:/in" --entrypoint tar postgres:17 xzf /in/<file>.tar.gz -C /data`.

Last drill: 2026-10-20 on the dev stack, PASS (40 tables, 2,603 rows).
