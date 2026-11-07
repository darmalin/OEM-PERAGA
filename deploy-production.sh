#!/usr/bin/env bash
# Release this staging checkout to its sibling production checkout.
set -Eeuo pipefail
umask 077

STAGING_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
PROD_DIR=${EMS_DEPLOY_PROD_DIR:-"$(dirname "$STAGING_DIR")/ems-prod"}
BACKUP_ROOT=${EMS_DEPLOY_BACKUP_DIR:-"$(dirname "$STAGING_DIR")/backups/ems-prod"}
AUTO_COMMIT=1
CHECK_ONLY=0
usage() {
  cat <<'EOF'
Usage: ./deploy-production.sh [--no-commit] [--check]
  Default   Commit all application changes in staging before releasing.
  --no-commit  Require staging changes to have been committed already.
  --check   Read-only preflight; do not commit, push, build, or deploy.
Existing production .env, database, and uploads are preserved.
EOF
}
for arg in "$@"; do
  case "$arg" in
    --commit) AUTO_COMMIT=1 ;;
    --no-commit) AUTO_COMMIT=0 ;;
    --check) CHECK_ONLY=1 ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; exit 1 ;;
  esac
done
die() { echo "ERROR: $*" >&2; exit 1; }
log() { printf '\n[%s] %s\n' "$(date +%T)" "$*"; }
for tool in git docker python3 curl flock; do
  command -v "$tool" >/dev/null || die "Missing command: $tool"
done
[[ -d "$PROD_DIR" && -f "$PROD_DIR/.env" ]] || die "Production folder/.env not found: $PROD_DIR"
PROD_DIR=$(cd -- "$PROD_DIR" && pwd -P)
[[ "$PROD_DIR" != "$STAGING_DIR" ]] || die "Staging and production must be different folders."
dc() { docker compose --project-directory "$PROD_DIR" --env-file "$PROD_DIR/.env" -f "$PROD_DIR/compose.yaml" -p ems-prod "$@"; }
dirty() { git -C "$1" status --porcelain --untracked-files=normal -- . ':(exclude)backups/'; }
[[ -z "$(dirty "$PROD_DIR")" ]] || die "Production has local changes. Resolve them first; nothing was overwritten."
git -C "$STAGING_DIR" rev-parse --show-toplevel >/dev/null
[[ -z "$(git -C "$STAGING_DIR" ls-files -u)" ]] || die "Resolve staging merge conflicts first."
BRANCH=$(git -C "$STAGING_DIR" symbolic-ref --short HEAD) || die "Staging must be on a branch."
git -C "$STAGING_DIR" remote get-url origin >/dev/null
git -C "$STAGING_DIR" diff --check
dc config --format json | python3 -c '
import json,sys
c=json.load(sys.stdin)
assert c["name"]=="ems-prod", "Wrong Compose project"
assert c["services"]["api"]["environment"]["EMS_ENVIRONMENT"]=="production", "Wrong application environment"
assert c["services"]["api"]["environment"]["EMS_PUBLIC_BASE_URL"].startswith("https://"), "Production URL must use HTTPS"
'
API_CONTAINER=$(dc ps -q api)
[[ -n "$API_CONTAINER" ]] || die "Existing production API container not found. This script updates an existing installation."
ACTUAL_DIR=$(docker inspect --format '{{ index .Config.Labels "com.docker.compose.project.working_dir" }}' "$API_CONTAINER")
[[ "$ACTUAL_DIR" == "$PROD_DIR" ]] || die "ems-prod belongs to another directory: $ACTUAL_DIR"
PUBLIC_URL=$(dc config --format json | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"]["api"]["environment"]["EMS_PUBLIC_BASE_URL"].rstrip("/"))')
if (( CHECK_ONLY )); then
  log "Preflight OK. Staging: $STAGING_DIR; production: $PROD_DIR; URL: $PUBLIC_URL"
  if [[ -n "$(dirty "$STAGING_DIR")" ]]; then
    echo "Staging has uncommitted changes; a normal run will commit and release them."
  fi
  exit 0
fi
exec 9>"$(dirname "$PROD_DIR")/.ems-production-deploy.lock"
flock -n 9 || die "Another production deployment is running."
if [[ -n "$(dirty "$STAGING_DIR")" ]]; then
  (( AUTO_COMMIT )) || die "Commit staging changes first, or run with --commit."
  log "Committing staging application changes (excluding backups)."
  git -C "$STAGING_DIR" add -A -- . ':(exclude)backups/'
  git -C "$STAGING_DIR" diff --cached --check
  git -C "$STAGING_DIR" commit -m "release: staging changes $(date -u +%Y-%m-%dT%H:%M:%SZ)"
fi
TARGET=$(git -C "$STAGING_DIR" rev-parse HEAD)
PREVIOUS=$(git -C "$PROD_DIR" rev-parse HEAD)
if [[ "$TARGET" == "$PREVIOUS" ]]; then
  for service in api worker beat nginx; do
    [[ "$(dc ps --status running -q "$service")" ]] || die "Commit is already checked out, but $service is stopped. Inspect the last deployment log before recovery."
  done
  curl --fail --silent --show-error --max-time 10 "$PUBLIC_URL/api/v1/health/ready" | python3 -c 'import json,sys; assert json.load(sys.stdin)["status"]=="ok"'
  log "Production already uses this commit ($TARGET). Nothing to deploy."
  exit 0
fi
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
TAG="v$(date -u +%Y.%m.%d.%H%M%S)"
RELEASE_DIR="$BACKUP_ROOT/release-$STAMP"
mkdir -p "$RELEASE_DIR"
chmod 700 "$RELEASE_DIR"
exec > >(tee -a "$RELEASE_DIR/deploy.log") 2>&1
STOPPED=0
MIGRATION_STARTED=0
CHECKED_OUT=0
FAILED=0
failure() {
  local code=$1
  (( code != 0 )) || return 0
  (( FAILED == 0 )) || exit "$code"
  FAILED=1
  trap - EXIT INT TERM
  set +e
  echo "ERROR: Release stopped. See $RELEASE_DIR/deploy.log"
  if (( MIGRATION_STARTED )); then
    dc stop -t 30 api worker beat
    echo "Migration may have changed the schema. Writers are stopped; no database restore was attempted."
    echo "Inspect migration.log and backups before recovery. Previous commit: $PREVIOUS"
  else
    if (( CHECKED_OUT )); then git -C "$PROD_DIR" checkout --detach "$PREVIOUS"; fi
    if (( STOPPED )); then
      dc -f "$RELEASE_DIR/rollback.compose.json" up -d --no-deps --no-build api worker beat nginx
    fi
    echo "Production kept/recovered its previous code and data."
  fi
  exit "$code"
}
trap 'failure $?' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
printf '%s\n' "$PREVIOUS" > "$RELEASE_DIR/previous-commit.txt"
printf '%s\n' "$TARGET" > "$RELEASE_DIR/release-commit.txt"
cp "$PROD_DIR/.env" "$RELEASE_DIR/production.env"
log "Publishing release $TAG to GitHub."
git -C "$STAGING_DIR" tag -a "$TAG" "$TARGET" -m "Production release $TAG"
git -C "$STAGING_DIR" push --atomic origin "HEAD:refs/heads/$BRANCH" "refs/tags/$TAG"
git -C "$STAGING_DIR" bundle create "$RELEASE_DIR/release.bundle" --all
log "Preserving previous application images."
python3 - "$PROD_DIR" "$RELEASE_DIR" "$STAMP" <<'PY'
import json,subprocess,sys
prod,release,stamp=sys.argv[1:]
services={}
for name in ("api","worker","beat","nginx"):
    container=json.loads(subprocess.check_output(["docker","inspect",f"ems-prod-{name}-1"]))[0]
    tag=f"ems-prod-{name}:rollback-{stamp.lower()}"
    if subprocess.run(["docker","image","inspect",container["Image"]],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:
        subprocess.run(["docker","image","tag",container["Image"],tag],check=True)
    else:
        subprocess.run(["docker","commit","--pause=false",container["Id"],tag],check=True,stdout=subprocess.DEVNULL)
    services[name]={"image":tag,"pull_policy":"never"}
with open(release+"/rollback.compose.json","w") as f:
    json.dump({"services":services},f,indent=2)
PY
log "Checking out the exact release and building images while production remains online."
git -C "$PROD_DIR" fetch "$STAGING_DIR" "refs/tags/$TAG:refs/tags/$TAG"
git -C "$PROD_DIR" checkout --detach "$TAG"
CHECKED_OUT=1
dc build api worker beat migrate nginx
log "Stopping application writers and making the final production backup."
STOPPED=1
dc stop -t 60 beat worker api
(cd "$PROD_DIR"; COMPOSE_FILE=compose.yaml COMPOSE_PROJECT_NAME=ems-prod bash deployments/backup/backup.sh "$RELEASE_DIR")
shopt -s nullglob
dumps=("$RELEASE_DIR"/*.dump)
archives=("$RELEASE_DIR"/*.tar.gz)
[[ ${#dumps[@]} == 1 && -s "${dumps[0]}" && ${#archives[@]} == 1 ]] || die "Backup files are missing/empty."
dc exec -T postgres pg_restore --list < "${dumps[0]}" > /dev/null
tar tzf "${archives[0]}" > /dev/null
log "Running database migration."
MIGRATION_STARTED=1
dc run --rm --no-deps -T migrate | tee "$RELEASE_DIR/migration.log"
log "Starting API and waiting for readiness."
dc up -d --no-deps --no-build api
ready=0
for (( attempt=0; attempt<60; attempt++ )); do
  if dc exec -T api python -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8000/api/v1/health/ready", timeout=3)' >/dev/null 2>&1; then ready=1; break; fi
  sleep 2
done
(( ready )) || die "New API did not become ready."
dc up -d --no-deps --no-build nginx
for (( attempt=0; attempt<15; attempt++ )); do
  if curl --fail --silent --show-error --max-time 10 "$PUBLIC_URL/api/v1/health/ready" > "$RELEASE_DIR/readiness.json" 2>/dev/null; then break; fi
  sleep 2
done
python3 - "$RELEASE_DIR/readiness.json" <<'PY'
import json,sys
with open(sys.argv[1]) as f:
    assert json.load(f)["status"]=="ok", "Public readiness check failed"
PY
dc up -d --no-deps --no-build worker beat
for service in api worker beat nginx; do
  [[ "$(dc ps --status running -q "$service")" ]] || die "$service is not running."
done
dc exec -T api alembic current
dc ps
printf '%s\n' "$TAG" > "$RELEASE_DIR/SUCCESS"
STOPPED=0
trap - ERR EXIT INT TERM
log "SUCCESS: $TAG is live at $PUBLIC_URL"
echo "Backup and deployment log: $RELEASE_DIR"
