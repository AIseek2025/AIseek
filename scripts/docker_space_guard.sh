#!/usr/bin/env bash
set -euo pipefail

export PATH="/usr/local/bin:/opt/homebrew/bin:/Applications/Docker.app/Contents/Resources/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

ROOT="${1:-/}"
THRESHOLD="${2:-85}"
DOCKER_BIN="${DOCKER_BIN:-$(command -v docker || true)}"

usage_pct="$(df -P "$ROOT" | awk 'NR==2 {gsub(/%/,"",$5); print $5}')"
docker_dir="$HOME/Library/Containers/com.docker.docker"
docker_size="$(du -sh "$docker_dir" 2>/dev/null | awk '{print $1}')"

echo "root_usage=${usage_pct}%"
echo "docker_size=${docker_size:-unknown}"

if [ -z "${DOCKER_BIN}" ]; then
  echo "docker binary not found, skip docker operations"
  echo "root_df:"
  df -h "$ROOT"
  exit 0
fi

if [ "${usage_pct:-0}" -ge "${THRESHOLD}" ]; then
  echo "disk usage above threshold ${THRESHOLD}%: running docker builder prune"
  "$DOCKER_BIN" builder prune -af || true
  "$DOCKER_BIN" image prune -f || true
  "$DOCKER_BIN" container prune -f || true
fi

echo "docker_df:"
"$DOCKER_BIN" system df || true
echo "root_df:"
df -h "$ROOT"
