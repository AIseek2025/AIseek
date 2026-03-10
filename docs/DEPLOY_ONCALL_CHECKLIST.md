# AIseek 上线值班应急 Checklist（极简版）

## 0) 先做三件事（30秒）
- 固定目录变量：`BASE=/opt/aiseek/AIseek-Trae-v1/deploy/aliyun`
- 所有命令使用绝对路径：`--env-file "$BASE/.env.prod" -f "$BASE/docker-compose.prod.yml"`
- 不做破坏性操作：不执行 `down -v`、不删数据库卷

## 1) 快速判断服务是否存活（2分钟）
```bash
docker compose --env-file "$BASE/.env.prod" -f "$BASE/docker-compose.prod.yml" ps
```
- 预期：`db/redis/backend/worker` 均为 `Up/Healthy`

## 2) AI任务卡住（queued不动）时
```bash
docker compose --env-file "$BASE/.env.prod" -f "$BASE/docker-compose.prod.yml" exec -T db \
psql -U aiseek -d aiseek_prod -P pager=off -c \
"select id,status,stage,dispatch_attempts,worker_task_id,error,updated_at from ai_jobs order by created_at desc limit 20;"
```
- 若长期 `queued`：
```bash
docker compose --env-file "$BASE/.env.prod" -f "$BASE/docker-compose.prod.yml" exec -T db \
psql -U aiseek -d aiseek_prod -c \
"update ai_jobs set stage='dispatch_pending', next_dispatch_at=now(), stage_message='等待派发' where status='queued';"

docker compose --env-file "$BASE/.env.prod" -f "$BASE/docker-compose.prod.yml" exec -T backend python - <<'PY'
from app.services.dispatch_retry_service import dispatch_once
print({"dispatched": dispatch_once(200)})
PY
```

## 3) AI回调是否通（必查）
```bash
docker compose --env-file "$BASE/.env.prod" -f "$BASE/docker-compose.prod.yml" exec -T worker python - <<'PY'
import os
print("WEB_URL=", os.getenv("WEB_URL"))
print("WORKER_SECRET set=", bool(os.getenv("WORKER_SECRET")))
PY
```
- 预期：`WEB_URL` 必须是 `http://backend:5000`
- 禁止：反引号 URL、指向公网首页域名

## 4) 编码器错误（Encoder not found）时
```bash
grep -q '^FFMPEG_HW_ACCEL=' "$BASE/.env.prod" \
  && sed -i 's/^FFMPEG_HW_ACCEL=.*/FFMPEG_HW_ACCEL=libx264/' "$BASE/.env.prod" \
  || echo 'FFMPEG_HW_ACCEL=libx264' >> "$BASE/.env.prod"

docker compose --env-file "$BASE/.env.prod" -f "$BASE/docker-compose.prod.yml" up -d --build --force-recreate worker

docker compose --env-file "$BASE/.env.prod" -f "$BASE/docker-compose.prod.yml" exec -T worker python - <<'PY'
import os
from app.core.config import settings
print("ENV=", os.getenv("FFMPEG_HW_ACCEL"))
print("SETTINGS=", settings.ffmpeg_hw_accel)
PY
```
- 预期：`ENV=libx264` 且 `SETTINGS=libx264`

## 5) 上传失败（413/404）时
- 413：检查宿主机 Nginx `client_max_body_size`
- 404 `/api/v1/upload/local`：检查宿主机 Nginx `/api/v1/upload/` 转发配置

## 6) 数据库异常（recovery / 事务失败）时
- 确保 DB healthy 后再拉 backend/worker
- 执行迁移：
```bash
docker compose --env-file "$BASE/.env.prod" -f "$BASE/docker-compose.prod.yml" exec -T backend alembic upgrade head
```

## 7) 备份失败（GitHub Actions）时
- 必填 secrets：
  - `BACKUP_S3_BUCKET`
  - `BACKUP_S3_PREFIX`
  - `BACKUP_S3_ENDPOINT_URL`
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`
  - `AWS_DEFAULT_REGION`

## 8) 最终验收（必须执行）
```bash
docker compose --env-file "$BASE/.env.prod" -f "$BASE/docker-compose.prod.yml" exec -T db \
psql -U aiseek -d aiseek_prod -P pager=off -c \
"select id,status,stage,dispatch_attempts,error,updated_at from ai_jobs order by created_at desc limit 20;"

docker compose --env-file "$BASE/.env.prod" -f "$BASE/docker-compose.prod.yml" exec -T db \
psql -U aiseek -d aiseek_prod -P pager=off -c \
"select id,post_id,duration,mp4_url,hls_url,created_at from media_assets order by id desc limit 20;"
```
- 验收标准：
  - `ai_jobs` 不长期卡 `queued`
  - `media_assets` 出现新记录
  - 新生成视频 `duration > 0`

## 9) 升级版文档
- 详版复盘：`docs/DEPLOY_INCIDENT_README_20260309.md`
- 部署总文档：`docs/DEPLOY.md`
- 备份文档：`docs/BACKUP.md`
- 历史卡任务清理：`docs/AI_STUCK_TASK_CLEANUP_RUNBOOK.md`
