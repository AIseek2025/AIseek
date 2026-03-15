#!/bin/bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE=(docker compose --env-file "$SCRIPT_DIR/.env.prod" -f "$SCRIPT_DIR/docker-compose.prod.yml")
STAMP="$(date +%Y%m%d-%H%M%S)"
ROLLBACK_BACKEND=""
ROLLBACK_WORKER=""
BRANCH="main"
SERVICES=(backend worker nginx)
RUN_MIGRATE=1
RUN_HEALTH=1

log() { echo "[$(date '+%F %T')] $*"; }
die() { echo "[ERROR] $*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --branch)
      BRANCH="${2:-}"
      [ -n "$BRANCH" ] || die "missing value for --branch"
      shift 2
      ;;
    --services)
      IFS=',' read -r -a SERVICES <<< "${2:-}"
      [ "${#SERVICES[@]}" -gt 0 ] || die "missing value for --services"
      shift 2
      ;;
    --skip-migrate)
      RUN_MIGRATE=0
      shift
      ;;
    --skip-health-check)
      RUN_HEALTH=0
      shift
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
done

get_image_id() {
  local service="$1"
  local cid
  cid="$("${COMPOSE[@]}" ps -q "$service" 2>/dev/null || true)"
  if [ -z "$cid" ]; then
    echo ""
    return
  fi
  docker inspect -f '{{.Image}}' "$cid" 2>/dev/null || true
}

rollback() {
  log "Deployment failed, starting image rollback"
  if [ -n "$ROLLBACK_BACKEND" ] && docker image inspect "$ROLLBACK_BACKEND" >/dev/null 2>&1; then
    docker tag "$ROLLBACK_BACKEND" "aliyun-backend:latest" >/dev/null 2>&1 || true
  fi
  if [ -n "$ROLLBACK_WORKER" ] && docker image inspect "$ROLLBACK_WORKER" >/dev/null 2>&1; then
    docker tag "$ROLLBACK_WORKER" "aliyun-worker:latest" >/dev/null 2>&1 || true
  fi
  "${COMPOSE[@]}" up -d backend worker nginx || true
  log "Rollback finished"
}

trap 'rollback' ERR

log "Starting deployment update"
[ -f "$SCRIPT_DIR/.env.prod" ] || die ".env.prod not found"
grep -q '^REDIS_PASSWORD=.\+' "$SCRIPT_DIR/.env.prod" || die "REDIS_PASSWORD must be set"

ROLLBACK_BACKEND="$(get_image_id backend)"
ROLLBACK_WORKER="$(get_image_id worker)"
if [ -n "$ROLLBACK_BACKEND" ]; then docker tag "$ROLLBACK_BACKEND" "rollback-backend:${STAMP}" >/dev/null 2>&1 || true; fi
if [ -n "$ROLLBACK_WORKER" ]; then docker tag "$ROLLBACK_WORKER" "rollback-worker:${STAMP}" >/dev/null 2>&1 || true; fi

log "Updating repository to origin/${BRANCH} (ff-only)"
git -C "$REPO_ROOT" fetch origin "$BRANCH"
git -C "$REPO_ROOT" pull --ff-only origin "$BRANCH"

log "Writing deploy_version.json"
VERSION_JSON="$REPO_ROOT/backend/app/runtime/deploy_version.json"
mkdir -p "$(dirname "$VERSION_JSON")"
printf '{"sha":"%s","short":"%s","date":"%s"}\n' \
  "$(git -C "$REPO_ROOT" rev-parse HEAD)" \
  "$(git -C "$REPO_ROOT" rev-parse --short HEAD)" \
  "$(git -C "$REPO_ROOT" log -1 --format=%ci HEAD 2>/dev/null || echo "")" \
  > "$VERSION_JSON"

log "Rebuild and restart services: ${SERVICES[*]}"
"${COMPOSE[@]}" up -d --build --remove-orphans "${SERVICES[@]}"

if [ "$RUN_MIGRATE" -eq 1 ]; then
  log "Run migrations with retry"
  migrated=0
  for i in $(seq 1 20); do
    if "${COMPOSE[@]}" exec -T backend alembic upgrade head >/dev/null 2>&1; then
      migrated=1
      break
    fi
    sleep 2
  done
  [ "$migrated" -eq 1 ] || die "alembic upgrade failed"
fi

if [ "$RUN_HEALTH" -eq 1 ]; then
  log "Backend health check with retry"
  healthy=0
  for i in $(seq 1 30); do
    if "${COMPOSE[@]}" exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/', timeout=5)" >/dev/null 2>&1; then
      healthy=1
      break
    fi
    sleep 2
  done
  [ "$healthy" -eq 1 ] || die "backend health check failed"
fi

"${COMPOSE[@]}" ps --status running backend worker nginx >/dev/null

log "Cleaning old images"
docker image prune -f >/dev/null 2>&1 || true

trap - ERR
log "Deployment completed successfully"
