# AIseek 值班交接模板（3分钟版）

## 1) 基本信息
- 交班人：
- 接班人：
- 交接时间：
- 当前环境：生产 / 预发 / 本地

## 2) 服务状态快照
- `db`：
- `redis`：
- `backend`：
- `worker`：
- Nginx：

## 3) 当前风险等级
- 风险等级：低 / 中 / 高
- 主要风险点（最多3条）：
  1.
  2.
  3.

## 4) 未完成事项（按优先级）
- P0（必须立即处理）：
- P1（本班内处理）：
- P2（可排期）：

## 5) 今日变更与影响
- 已执行变更：
- 涉及文件/配置：
- 是否已回滚验证：是 / 否
- 影响范围：

## 6) 关键监控与阈值
- AI队列积压（ai）：
- `ai_jobs` 失败率：
- `media_assets` 新增量：
- 5xx 比例：
- 磁盘可用空间：

## 7) 当前故障与处置进度
- 故障标题：
- 首次发现时间：
- 当前状态：定位中 / 修复中 / 观察中 / 已恢复
- 已执行动作：
- 下一步动作：

## 8) 回滚条件（写清触发标准）
- 触发条件：
- 回滚目标版本：
- 回滚负责人：

## 9) 交接必跑命令（贴结果摘要）
```bash
BASE=/opt/aiseek/AIseek-Trae-v1/deploy/aliyun
docker compose --env-file "$BASE/.env.prod" -f "$BASE/docker-compose.prod.yml" ps
docker compose --env-file "$BASE/.env.prod" -f "$BASE/docker-compose.prod.yml" exec -T db psql -U aiseek -d aiseek_prod -P pager=off -c "select id,status,stage,dispatch_attempts,error,updated_at from ai_jobs order by created_at desc limit 10;"
docker compose --env-file "$BASE/.env.prod" -f "$BASE/docker-compose.prod.yml" exec -T db psql -U aiseek -d aiseek_prod -P pager=off -c "select id,post_id,duration,mp4_url,hls_url,created_at from media_assets order by id desc limit 10;"
```

结果摘要：
- ai_jobs：
- media_assets：

## 10) 凭据与配置变更确认
- 今日是否变更 `.env.prod`：是 / 否
- 今日是否变更 GitHub Secrets：是 / 否
- 变更项列表：

## 11) 接班确认
- 接班人已知风险：
- 接班人确认接收：是 / 否
- 备注：
