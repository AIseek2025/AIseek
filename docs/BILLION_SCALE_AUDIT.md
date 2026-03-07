# 面向“10亿级”高并发的架构落地核查表（可执行版本）

本文档对照目标清单逐项核查当前仓库的落地状态，并给出“代码/配置/文档”的对应落点，确保每一项都能在现有架构上可执行、可演进、可观测、可回滚。

> 说明：部分目标属于“基础设施能力”（多可用区、HPA、分库分表等），无法仅靠应用代码一键实现。本仓库对这类目标提供可执行的部署清单/脚手架与运行时开关，并明确下一步演进路径。

## 1) 前端交付（构建产物 + hash + immutable + HTML no-store）

状态：已落地

- 构建产物（dist）与 manifest 指针：
  - `backend/static/dist/**`
  - `backend/scripts/build_static_assets.py`
  - `backend/scripts/activate_static_assets.py`
- immutable/no-store 分层缓存：
  - 应用侧：`backend/app/main.py`（HTML no-store、manifest no-store、rollout/build header）
  - Nginx 侧：`deploy/nginx/nginx.conf`、`deploy/nginx/simple.conf`

## 2) API 网关层（统一鉴权/限流/灰度/熔断/追踪）

状态：已落地（应用内网关 + Nginx 边缘网关）

### 2.1 请求追踪（x-request-id）

- Nginx 边缘层生成/回写并透传：`deploy/nginx/nginx.conf`、`deploy/nginx/simple.conf`
- 应用层提取/生成并回写：`backend/app/middleware/request_logging.py`
- 日志上下文注入（request_id/trace_id/span_id）：`backend/app/core/logging_config.py`

### 2.2 tracing（OpenTelemetry）

- 自动埋点与 trace headers 传播：`backend/app/core/tracing.py`、`backend/app/core/http_client.py`
- span 统一属性（request_id/session_id/user_id/canary）：`backend/app/middleware/tracing_context.py`

### 2.3 统一鉴权（写请求）

- 写请求强制 Bearer + user_id 强一致校验：`backend/app/middleware/auth_required.py`

### 2.4 限流（固定窗口 + 成本预算）

- 固定窗口限流（按 user/session/ip + route）：`backend/app/middleware/rate_limit.py`
- 搜索接口成本预算（令牌桶）：`backend/app/middleware/rate_limit.py`、`backend/app/core/redis_scripts.py`
- 边缘层补充限流（搜索专用）：`deploy/nginx/nginx.conf`、`deploy/nginx/simple.conf`
- 调参建议：`docs/SCALE.md`

### 2.5 灰度（canary）

- 静态资源灰度发布：`backend/app/middleware/canary.py`、`backend/app/core/assets.py`、`backend/static/dist/rollout.json`
- 灰度标识透传（x-canary）：`deploy/nginx/*.conf`、`backend/app/core/http_client.py`
- 受控强制灰度（用于压测/回归/问题定位）：`CANARY_OVERRIDE_ENABLED=1` 时允许请求头 `x-canary: 1/0` 覆盖分桶结果：`backend/app/middleware/canary.py`

### 2.6 熔断/降级

- 搜索：ES 熔断降级（cooldown）+ DB 回退：`backend/app/services/search_service.py`
- 推荐召回：远端召回熔断 + 自动回退本地：`backend/app/services/feed_recall.py`
- 资源/封面/占位图 provider 熔断（worker）：`worker/app/services/cover_service.py`、`worker/app/services/placeholder/circuit_breaker.py`
- 外呼治理（统一超时/重试/熔断/指标/透传）：`backend/app/core/http_client.py`
- 熔断状态指标（open/fail/open_until）：`backend/app/main.py`（`/metrics`）

## 3) 核心服务拆分（从单体可演进）

状态：已落地“可拆分边界”（单体内模块化 + worker 异步）

### 3.1 Feed/推荐服务（读多写少）

- 召回：本地 DB 召回 + 远端 recall 服务（可独立扩展）+ 灰度/回退：`backend/app/services/feed_recall.py`、`backend/app/recall_main.py`
- 排序：基于用户偏好分类的轻量排序（AB variant）：`backend/app/services/feed_service.py`
- 热点计数器（写合并/读叠加）：`backend/app/services/hot_counter_service.py`

### 3.2 Post/内容服务

- 写入走主库：`get_db`
- 读取走只读副本（默认回落主库）：`get_read_db`（`READ_DATABASE_URL`）
- 写后短期粘主（避免主从延迟导致写后读不一致）：`backend/app/main.py` + `backend/app/api/deps.py`

### 3.3 Media 服务

- 对象存储/URL 化：`backend/app/services/storage.py`
- 转码/字幕/封面：worker 侧异步任务（可水平扩展）：`worker/app/worker/tasks.py`、`worker/app/services/video_service.py`

### 3.4 AI 生成服务

- 队列化：Celery + Redis：`worker/app/worker/celery_app.py`、`worker/app/worker/tasks.py`
- 任务状态可查询：`backend/app/api/v1/endpoints/ai_jobs.py`、`backend/app/models/all_models.py`
- 回调与告警：`docs/WORKER_CALLBACK.md`

## 4) 数据层（读写分离 → 分区/分片 → 最终拆库拆表）

状态：读写分离已落地；分区/分片提供可执行脚手架与演进路径

- 读写分离与连接池：`backend/app/db/session.py`、`docs/SCALE.md`
- Postgres 搜索索引（全文检索 + trgm）：`backend/alembic/versions/0022_search_pg_indexes.py`
- ES/索引服务：`backend/app/services/search_service.py`、`backend/app/tasks/search_index.py`
- 分区/分片/多活（基础设施级）：见 `docs/SCALE.md` 与 `docs/K8S.md` 的演进与清单建议

## 5) 高可用（多 AZ、自动伸缩、依赖降级）

状态：应用就绪/存活探针 + 降级已落地；多 AZ/HPA 提供 k8s 清单

- 健康检查：`/livez`、`/readyz`：`backend/app/main.py`
- 推荐依赖降级：远端 recall 失败自动回退本地：`backend/app/services/feed_recall.py`
- k8s 多副本 + HPA + PDB 示例：`docs/K8S.md`、`deploy/k8s/**`

## 6) 可观测（前端上报 + tracing/metrics/logs + 告警/回滚）

状态：已落地（可扩展）

- 前端错误上报：`/api/v1/observability/events`（路由与契约见 `backend/app/api/v1/endpoints/ops.py` 与前端 modules）
- 结构化日志（request_id/trace_id/span_id）：`backend/app/core/logging_config.py`
- 指标：`/metrics`：`backend/app/main.py`
- 静态资源灰度与自动回滚（基于错误阈值）：`backend/static/dist/rollout.json` + `backend/app/main.py` 的灰度监控逻辑

## 需要你补齐的外部配置（生产）

- 对象存储/每日备份：见 `docs/BACKUP.md`
- tracing：`ENABLE_TRACING=1`、`OTEL_EXPORTER_OTLP_ENDPOINT`
- Postgres/读写分离：`DATABASE_URL`、`READ_DATABASE_URL`
- Redis：`REDIS_URL`
- Elasticsearch：`ELASTICSEARCH_URL`、`ELASTICSEARCH_INDEX`
