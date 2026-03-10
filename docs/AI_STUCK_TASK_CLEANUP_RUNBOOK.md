# AI 历史卡任务清理标准流程（详细版）

## 1. 适用范围
当出现以下任一现象时，使用本流程：
- `ai_jobs` 长时间停留在 `queued/processing` 且不前进
- `worker` 日志显示任务 `succeeded`，但 `posts.video_url` 仍为空
- `media_assets` 无新增记录，前端显示“处理中/0秒”
- 后端回调返回 `ignored`（如 `post_status_regress`）

---

## 2. 执行前原则
- 全程使用绝对路径，不依赖 shell 变量
- 不执行 `down -v`
- 先保可用（恢复新任务），再处理历史坏数据
- 每一步都做可观测验证，禁止盲重试

---

## 2.1 一键脚本（推荐）
```bash
bash scripts/ai_task_recover.sh /opt/aiseek/AIseek-Trae-v1/deploy/aliyun all
```

仅处理单个任务：
```bash
bash scripts/ai_task_recover.sh /opt/aiseek/AIseek-Trae-v1/deploy/aliyun <ai_job_id>
```

只读诊断（不改数据，不重启，不派发）：
```bash
bash scripts/ai_task_recover.sh /opt/aiseek/AIseek-Trae-v1/deploy/aliyun all readonly
```

---

## 3. 基础健康检查
```bash
docker compose --env-file /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/.env.prod -f /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/docker-compose.prod.yml ps
docker compose --env-file /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/.env.prod -f /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/docker-compose.prod.yml exec -T db pg_isready -U aiseek -d aiseek_prod
docker compose --env-file /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/.env.prod -f /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/docker-compose.prod.yml exec -T backend sh -lc 'getent hosts db || true'
```

判定：
- 任一失败先修基础设施（DB/网络/磁盘）后再继续

---

## 4. 卡任务识别（筛选目标）
```bash
docker compose --env-file /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/.env.prod -f /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/docker-compose.prod.yml exec -T db \
psql -U aiseek -d aiseek_prod -P pager=off -c "
select id,status,stage,worker_task_id,dispatch_attempts,left(coalesce(error,''),120) err_short,updated_at
from ai_jobs
where kind='generate_video'
order by created_at desc
limit 30;"
```

```bash
docker compose --env-file /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/.env.prod -f /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/docker-compose.prod.yml exec -T db \
psql -U aiseek -d aiseek_prod -P pager=off -c "
select id,status,duration,video_url,ai_job_id,created_at
from posts
where ai_job_id is not null
order by id desc
limit 30;"
```

---

## 5. 队列与worker状态诊断
```bash
docker compose --env-file /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/.env.prod -f /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/docker-compose.prod.yml exec -T worker celery -A app.worker.celery_app inspect active
docker compose --env-file /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/.env.prod -f /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/docker-compose.prod.yml exec -T worker celery -A app.worker.celery_app inspect reserved
```

```bash
REDIS_PASS=$(grep '^REDIS_PASSWORD=' /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/.env.prod | cut -d= -f2-)
docker compose --env-file /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/.env.prod -f /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/docker-compose.prod.yml exec -T redis \
sh -lc "redis-cli -a '$REDIS_PASS' -n 1 LLEN ai"
```

判定：
- `active/reserved` 空且 `LLEN ai=0`：大概率是历史任务状态僵死
- `active` 有任务但 `posts/media_assets` 不更新：大概率回调被忽略或落库条件不满足

---

## 6. 标准解卡动作（推荐）

### 6.1 批量重置卡住任务
```bash
docker compose --env-file /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/.env.prod -f /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/docker-compose.prod.yml exec -T db \
psql -U aiseek -d aiseek_prod -c "
update ai_jobs
set status='queued',
    stage='dispatch_pending',
    next_dispatch_at=now(),
    dispatch_attempts=0,
    worker_task_id=null,
    error=null,
    stage_message='等待派发'
where kind='generate_video'
  and status in ('queued','processing','failed');"
```

### 6.2 重启 worker 并触发派发
```bash
docker compose --env-file /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/.env.prod -f /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/docker-compose.prod.yml restart worker
docker compose --env-file /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/.env.prod -f /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/docker-compose.prod.yml exec -T backend python - <<'PY'
from app.services.dispatch_retry_service import dispatch_once
print({'dispatched': dispatch_once(100)})
PY
```

---

## 7. 回调被 ignored 的专门处理
现象：回调 200 但返回 `{"ignored":true,...}`，常见是 `post_status_regress`。

处理策略：
- 先保证 worker done 回调不推进 post 状态（`no_post_status=True`）
- 再通过后端落库结果驱动 post 状态

运行后验证：
```bash
docker compose --env-file /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/.env.prod -f /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/docker-compose.prod.yml logs --since=5m worker | grep -E "callback|ignored|succeeded|failed" -n -C 2
```

---

## 8. 历史任务收口（有产物但状态未更新）
当已出现 `media_assets` 但 `posts.status` 仍 `processing` 时，执行：

```bash
docker compose --env-file /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/.env.prod -f /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/docker-compose.prod.yml exec -T db \
psql -U aiseek -d aiseek_prod -c "
update posts p
set status='done'
where p.ai_job_id is not null
  and exists (select 1 from media_assets m where m.post_id=p.id)
  and coalesce(p.status,'') <> 'done';

update ai_jobs j
set status='done', stage='done', error=null
where exists (select 1 from posts p join media_assets m on m.post_id=p.id where p.ai_job_id=j.id)
  and coalesce(j.status,'') <> 'done';"
```

---

## 9. 验收标准（必须全部满足）
- `ai_jobs` 新任务不再长期卡 `queued/processing`
- `media_assets` 出现新记录
- 对应 `posts.video_url` 非空
- 对应 `posts.duration > 0`

验收 SQL：
```bash
docker compose --env-file /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/.env.prod -f /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/docker-compose.prod.yml exec -T db \
psql -U aiseek -d aiseek_prod -P pager=off -c "select id,status,stage,left(coalesce(error,''),120) err_short,updated_at from ai_jobs order by created_at desc limit 20;"

docker compose --env-file /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/.env.prod -f /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/docker-compose.prod.yml exec -T db \
psql -U aiseek -d aiseek_prod -P pager=off -c "select id,post_id,duration,mp4_url,hls_url,created_at from media_assets order by id desc limit 20;"

docker compose --env-file /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/.env.prod -f /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/docker-compose.prod.yml exec -T db \
psql -U aiseek -d aiseek_prod -P pager=off -c "select id,status,duration,video_url,ai_job_id,created_at from posts where ai_job_id is not null order by id desc limit 20;"
```

---

## 10. 防复发建议
- 每日巡检新增“僵尸 processing 数量”指标
- 回调接口落库失败时记录结构化 reason
- 发布后强制执行一次 AI 端到端冒烟（产物 + 时长 + 状态）
- 避免 shell 变量丢失：生产命令优先使用绝对路径
