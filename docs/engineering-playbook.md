# AIseek 研发协作手册

## 1. 文档目的

这份手册用于统一 AIseek 的研发协作方式，帮助团队在以下场景快速落地：

- 新同学上手与代码定位
- 功能迭代联调
- 线上问题排障
- 发布前检查与上线验证

---

## 2. 系统整体与代码入口

### 2.1 架构形态

- 单体后端（FastAPI）+ 模板化前端（Jinja2 + 原生 JS 模块）
- 双 Celery 体系（backend 调度 + worker 执行）
- Redis（缓存/限流/stream）+ PostgreSQL（事务数据）+ Elasticsearch（搜索）
- Nginx 网关（反代、限流、静态缓存策略、SSE 优化）

### 2.2 关键入口文件

- 后端应用入口：`backend/app/main.py`
- API 路由聚合：`backend/app/api/v1/api.py`
- 后端 Celery 装配：`backend/app/core/celery_app.py`
- Worker Celery 装配：`worker/app/worker/celery_app.py`
- 网关配置：`deploy/nginx/nginx.conf`
- 前端启动器：`backend/static/js/main.js`

---

## 3. 功能模块地图（前端 -> API -> 服务 -> 数据 -> 异步）

### 3.1 推荐流

- 前端：`backend/static/js/app/player.js`, `backend/static/js/app/router.js`
- API：`backend/app/api/v1/endpoints/feed.py`
- 服务：`backend/app/services/feed_service.py`, `backend/app/services/feed_recall.py`
- 数据：`posts`, `interactions`, `user_personas`, `ab_assignments`
- 异步：`backend/app/tasks/client_events.py`, `backend/app/tasks/counters.py`

### 3.2 创作台（AI 生成）

- 前端：`backend/static/js/app/creator.js`, `backend/static/js/app/studio.js`, `backend/templates/studio.html`
- API：`backend/app/api/v1/endpoints/ai_jobs.py`, `backend/app/api/v1/endpoints/posts.py`, `backend/app/api/v1/endpoints/upload.py`
- 服务：`backend/app/services/queue_service.py`, `backend/app/services/ai_pipeline.py`, `backend/app/services/storage.py`
- 数据：`ai_jobs`, `ai_job_messages`, `ai_job_draft_versions`, `ai_moderation_checks`, `posts`, `media_assets`
- 异步：backend Celery 发任务，worker 执行 `generate_video/transcode`

### 3.3 个人页与关系链

- 前端：`backend/static/js/app/profile.js`
- API：`backend/app/api/v1/endpoints/users.py`, `backend/app/api/v1/endpoints/interaction.py`, `backend/app/api/v1/endpoints/ai_jobs.py`
- 服务：`backend/app/services/notification_service.py`, `backend/app/services/post_presenter.py`
- 数据：`users`, `follows`, `friend_requests`, `notification_events`, `notification_reads`
- 异步：`backend/app/tasks/notification_backfill.py`, `backend/app/tasks/reco_profile.py`

### 3.4 搜索

- 前端：`backend/static/js/app/search.js`
- API：`backend/app/api/v1/endpoints/search.py`, `backend/app/api/v1/endpoints/users.py`（search-user）
- 服务：`backend/app/services/search_service.py`, `backend/app/services/search_hot_service.py`
- 数据：`posts`, `client_events`, `es_reindex_jobs`
- 异步：`backend/app/tasks/search_index.py`

### 3.5 互动（点赞/评论/弹幕/私信/通知）

- 前端：`backend/static/js/app/comments.js`, `backend/static/js/app/notifications.js`, `backend/static/js/app/interaction_store.js`
- API：`backend/app/api/v1/endpoints/interaction.py`, `backend/app/api/v1/endpoints/messages.py`
- 服务：`backend/app/services/counter_service.py`, `backend/app/services/notification_service.py`
- 数据：`interactions`, `comments`, `comment_reactions`, `danmaku`, `messages`
- 异步：`backend/app/tasks/counters.py`, `backend/app/tasks/dirty_flush.py`

### 3.6 观测与运维

- 前端：`backend/static/js/modules/telemetry.js`, `backend/static/js/modules/observability.js`, `backend/templates/admin.html`
- API：`backend/app/api/v1/endpoints/observability.py`, `backend/app/api/v1/endpoints/ops.py`
- 服务：`backend/app/services/job_event_service.py`
- 数据：`client_events`, `es_reindex_jobs`, `ai_jobs`
- 异步：`backend/app/tasks/client_events.py`, `backend/app/tasks/search_index.py`

---

## 4. 研发协作流程（建议）

### 4.1 改需求前

- 明确改动属于哪个业务模块（参考第 3 节）
- 确定最小改动入口文件（前端/API/服务/模型）
- 先确认是否已有同类开关、策略或 runtime 配置

### 4.2 开发中

- 优先在服务层做业务逻辑，不在 endpoint 堆复杂逻辑
- 写接口必须遵守鉴权与 user_id 防越权规则
- 涉及高频行为优先考虑异步化（Celery）和 Redis 缓冲

### 4.3 联调时

- 先看实例与构建头：`x-aiseek-instance`, `x-aiseek-build`, `x-chain-*`
- 再看业务探针：`/api/v1/debug/chain-status`
- 再看任务链路：AIJob 状态、worker 消费、回调更新

---

## 5. 常见问题排障手册

### 5.1 改了代码页面无变化

- 检查是否命中正确实例（instance/build）
- 检查 `x-chain-main-js`、`x-chain-actions-js` 是否是预期版本
- 检查静态缓存头是否符合 no-store/no-cache 预期

### 5.2 AI 任务有 job 但无结果

- 看 `ai_jobs.status/stage`
- 看 worker 队列消费情况
- 看回调接口是否成功写回 `posts.ai_job_id` 和结果字段

### 5.3 搜索结果异常

- 检查 ES 是否可用
- 检查重建任务状态（`es_reindex_jobs`）
- 检查 pg fallback 路径是否触发

### 5.4 前端交互“偶发”异常

- 检查事件分发器 `modules/actions.js`
- 检查是否存在额外事件拦截逻辑
- 用 debug client probe 看浏览器真实探针数据

---

## 6. 上线前检查清单（Release Checklist）

### 6.1 配置与安全

- SECRET_KEY / WORKER_SECRET / JWT 配置正确
- 写接口鉴权中间件生效
- 应用限流与网关限流已开启并符合策略

### 6.2 数据与迁移

- Alembic 迁移已执行
- 关键表字段与索引完整
- 读写分离连接配置正确

### 6.3 异步与外部依赖

- backend Celery 与 worker 进程在线
- Redis、Postgres、Elasticsearch 可达
- 媒体存储配置（S3/R2）可用

### 6.4 前端与网关

- 构建标识可见且脚本链路头正确
- 静态资源缓存策略符合预期
- 关键页面诊断框可显示探针数据

### 6.5 观测与告警

- `/metrics` 正常
- `/observability/events` 入流正常
- 管理台核心指标可见

---

## 7. 建议团队约定

- 新功能必须提供“最小定位说明”：改了哪些前端/API/服务/表/任务
- 每次线上问题复盘必须留下“探针证据”（build/instance/chain-status）
- 高风险链路优先加“可观测字段”，避免口头描述驱动排障

---

## 8. 附：最常用定位路径

- 路由入口：`backend/app/api/v1/api.py`
- 数据模型：`backend/app/models/all_models.py`
- 中间件：`backend/app/middleware/*.py`
- 服务层：`backend/app/services/*.py`
- 任务层：`backend/app/tasks/*.py` 与 `worker/app/worker/tasks.py`
- 前端模块：`backend/static/js/app/*.js`, `backend/static/js/modules/*.js`
- 页面模板：`backend/templates/*.html`

