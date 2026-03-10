#!/usr/bin/env bash
set -euo pipefail

BASE="${1:-/opt/aiseek/AIseek-Trae-v1/deploy/aliyun}"
ENV_FILE="${BASE}/.env.prod"
COMPOSE_FILE="${BASE}/docker-compose.prod.yml"
TARGET="${2:-all}"
MODE="${3:-recover}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "missing env file: ${ENV_FILE}"
  exit 1
fi
if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "missing compose file: ${COMPOSE_FILE}"
  exit 1
fi

DC=(docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}")

if [[ "${TARGET}" == "all" ]]; then
  TARGET_SQL="where kind='generate_video' and status in ('queued','processing','failed')"
else
  TARGET_SQL="where id='${TARGET}'"
fi

if [[ "${MODE}" != "recover" && "${MODE}" != "readonly" ]]; then
  echo "invalid mode: ${MODE} (allowed: recover|readonly)"
  exit 1
fi

echo "== services =="
"${DC[@]}" ps

echo "== db ready check =="
"${DC[@]}" exec -T db pg_isready -U aiseek -d aiseek_prod

if [[ "${MODE}" == "recover" ]]; then
  echo "== reset stuck jobs =="
  "${DC[@]}" exec -T db psql -U aiseek -d aiseek_prod -c "
  update ai_jobs
  set status='queued',
      stage='dispatch_pending',
      next_dispatch_at=now(),
      dispatch_attempts=0,
      worker_task_id=null,
      error=null,
      stage_message='等待派发'
  ${TARGET_SQL};
  "

  echo "== restart worker =="
  "${DC[@]}" restart worker

  echo "== dispatch jobs =="
  "${DC[@]}" exec -T backend python - <<'PY'
from app.services.dispatch_retry_service import dispatch_once
print({'dispatched': dispatch_once(100)})
PY
else
  echo "== readonly mode: skip reset/restart/dispatch =="
fi

echo "== ai_jobs =="
"${DC[@]}" exec -T db psql -U aiseek -d aiseek_prod -P pager=off -c "
select id,status,stage,worker_task_id,left(coalesce(error,''),120) err_short,updated_at
from ai_jobs
where kind='generate_video'
order by created_at desc
limit 20;
"

echo "== posts(ai) =="
"${DC[@]}" exec -T db psql -U aiseek -d aiseek_prod -P pager=off -c "
select id,status,duration,video_url,ai_job_id,created_at
from posts
where ai_job_id is not null
order by id desc
limit 20;
"

echo "== media_assets =="
"${DC[@]}" exec -T db psql -U aiseek -d aiseek_prod -P pager=off -c "
select id,post_id,duration,mp4_url,hls_url,created_at
from media_assets
order by id desc
limit 20;
"

echo "== worker logs(3m) =="
"${DC[@]}" logs --since=3m worker | tail -n 200 || true
