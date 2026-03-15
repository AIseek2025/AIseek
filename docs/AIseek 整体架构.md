**AIseek整体架构**

AIseek
项目整体技术栈、系统架构、模块划分、运行方式（后端/前端/任务/存储/网关/监控/安全）相关文档与代码入口

我已做过较完整的仓库级排查（入口、部署、配置、中间件、任务与前端链路），下面按你要的维度给出技术栈/架构/模块/数据流，并附代码依据。

\*\*总体结论\*\*

\- 形态是"单体后端 + 模板化前端 + 双 Celery（backend/worker）+ Redis +
Postgres + ES + Nginx
网关"的分层架构，\[README.md:L3-L30\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/README.md#L3-L30)。

\- 后端主入口是 FastAPI（同时承载
API、模板和静态资源），\[main.py:L33-L88\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/main.py#L33-L88)。

\- 前端不是 React/Vue，而是 Jinja2 + 原生 JS
模块化加载，\[README.md:L3\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/README.md#L3)
\[main.js:L153-L189\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/main.js#L153-L189)。

\*\*技术栈\*\*

\-
后端依赖：FastAPI/Uvicorn/SQLAlchemy/Alembic/Redis/Celery/Elasticsearch/Prometheus/OpenTelemetry/JWT，\[requirements.txt\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/requirements.txt)。

\- Worker 依赖：Celery/Redis/SQLAlchemy +
openai/ffmpeg/httpx/boto3，\[worker
requirements.txt\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/worker/requirements.txt)。

\- 运行编排：docker-compose 包含
db/redis/elasticsearch/backend/backend_celery/worker，\[docker-compose.yml:L3-L118\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/docker-compose.yml#L3-L118)。

\- K8s 也有部署清单（backend 3 副本 +
worker），\[backend-deployment.yaml\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/deploy/k8s/backend-deployment.yaml)
\[worker-deployment.yaml\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/deploy/k8s/worker-deployment.yaml)。

\*\*运行架构与核心模块\*\*

\- API 网关层：Nginx 做反代、限流、SSE
优化、静态分层缓存，\[nginx.conf:L23-L213\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/deploy/nginx/nginx.conf#L23-L213)。

\- 应用层：FastAPI 挂载 \`/api/v1\`、模板、静态、健康检查与
metrics，\[main.py:L84-L125\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/main.py#L84-L125)。

\-
业务路由分区：auth/users/posts/feed/search/interaction/upload/observability/ai/ops，\[api.py:L7-L23\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/api.py#L7-L23)。

\-
数据模型核心：Post、MediaAsset、AIJob、ClientEvent、ESReindexJob，\[all_models.py:L65-L330\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L65-L330)。

\*\*后端\*\*

\- FastAPI
中间件链：请求日志、灰度、鉴权、限流、写保护、gzip、metrics，\[main.py:L55-L82\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/main.py#L55-L82)。

\- 配置中心集中在
Settings（DB/Redis/Celery/ES/限流/事件/安全等），\[config.py:L9-L253\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/core/config.py#L9-L253)。

\- DB
支持读写分离与连接池参数化，\[session.py:L9-L67\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/db/session.py#L9-L67)。

\*\*前端\*\*

\- 首页模板由后端渲染并注入
build/flags，\[index.html:L6-L8\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/templates/index.html#L6-L8)。

\- 前端入口 main.js
按模块顺序动态加载（events/telemetry/api/router/player/search/auth\...），\[main.js:L153-L189\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/main.js#L153-L189)。

\- 前端观测埋点批量上报 \`/api/v1/observability/events\`，并先取
token，\[telemetry.js:L61-L176\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/modules/telemetry.js#L61-L176)。

\*\*异步任务\*\*

\- Backend Celery
负责调度与上下文透传（request-id/session-id/trace），\[celery_app.py:L33-L105\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/core/celery_app.py#L33-L105)。

\- 任务包含 ai_creation/search_index/counters/transcode/client_events
等，\[celery_app.py:L72-L81\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/core/celery_app.py#L72-L81)。

\- AI 真实执行在 worker Celery，按队列路由到 \`ai/transcode\`，\[worker
celery_app.py:L32-L37\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/worker/app/worker/celery_app.py#L32-L37)。

\- 后端通过 \`send_worker_task\` 把 generate_video 等发往 worker
队列，\[queue_service.py:L15-L27\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/queue_service.py#L15-L27)。

\*\*存储\*\*

\- 关系型：Postgres（compose
默认），\[docker-compose.yml:L4-L19\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/docker-compose.yml#L4-L19)。

\-
缓存与流：Redis（缓存/限流/幂等/stream），\[cache.py:L33-L67\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/core/cache.py#L33-L67)
\[observability.py:L495-L520\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/observability.py#L495-L520)。

\- 搜索：Elasticsearch（compose 服务 +
配置项），\[docker-compose.yml:L30-L43\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/docker-compose.yml#L30-L43)
\[config.py:L225-L240\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/core/config.py#L225-L240)。

\- 媒体对象存储：S3/R2
接口封装（预签名上传/下载），\[storage.py:L8-L52\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/storage.py#L8-L52)。

\*\*网关\*\*

\- Nginx upstream 指向 backend，统一透传 request-id/session-id/canary
头，\[nginx.conf:L27-L29\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/deploy/nginx/nginx.conf#L27-L29)
\[nginx.conf:L126-L142\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/deploy/nginx/nginx.conf#L126-L142)。

\- API/auth/search
分别限流，静态资源分层缓存策略，\[nginx.conf:L23-L26\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/deploy/nginx/nginx.conf#L23-L26)
\[nginx.conf:L49-L102\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/deploy/nginx/nginx.conf#L49-L102)。

\*\*观测\*\*

\- Prometheus 指标：HTTP 请求、延迟、构建信息、ES
重建、客户端事件流等，\[metrics.py:L7-L41\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/middleware/metrics.py#L7-L41)
\[main.py:L105-L125\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/main.py#L105-L125)。

\- OpenTelemetry 可选启用并导出
OTLP，\[tracing.py:L4-L33\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/core/tracing.py#L4-L33)。

\- 前后端事件观测闭环：前端 telemetry -\> \`/observability/events\` -\>
Redis Stream/DB fallback -\> 异步
drain，\[telemetry.js:L137-L188\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/modules/telemetry.js#L137-L188)
\[observability.py:L363-L606\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/observability.py#L363-L606)。

\*\*安全设计\*\*

\- JWT 与密码哈希：jose + passlib（token
签发/解析），\[security.py:L11-L52\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/core/security.py#L11-L52)。

\- 写接口强制鉴权并校验 body.user_id
防越权，\[auth_required.py:L20-L75\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/middleware/auth_required.py#L20-L75)。

\- 多级限流：全局中间件（feed/auth/write/search + token
bucket），\[rate_limit.py:L125-L251\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/middleware/rate_limit.py#L125-L251)。

\- Worker 回调验签/密钥校验 +
防重放去重，\[worker_auth.py:L15-L59\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/core/worker_auth.py#L15-L59)
\[posts.py:L1010-L1062\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/posts.py#L1010-L1062)。

\- 观测事件接口有
token、签名、速率控制，\[observability.py:L334-L412\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/observability.py#L334-L412)。

\*\*核心数据流（端到端）\*\*

\- AI 生成链路：前端/客户端请求 \`POST /api/v1/ai/create\` -\> 创建
Post+AIJob -\> \`send_worker_task(generate_video)\` -\> worker 执行 -\>
回调 posts
更新状态，\[routes.py:L19-L129\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/ai_creation/routes.py#L19-L129)
\[queue_service.py:L15-L27\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/queue_service.py#L15-L27)
\[worker
celery_app.py:L68-L99\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/worker/app/worker/celery_app.py#L68-L99)
\[posts.py:L1075-L1137\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/posts.py#L1075-L1137)。

\- 前端事件链路：前端 emit -\> telemetry 批量上报 -\> 后端鉴权/采样/限流
-\> Redis Stream 分 topic -\> Celery drain 或 DB
fallback，\[telemetry.js:L190-L211\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/modules/telemetry.js#L190-L211)
\[observability.py:L413-L552\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/observability.py#L413-L552)。

太好了，这个问题很关键。我给你一个"架构总览版"，把 \*\*技术选型 /
底层架构 / 模块设计 / 数据流\*\* 一次讲全。

\*\*总体架构\*\*

\- AIseek 是"\*\*单体后端 + 模板化前端 + 双 Celery 异步体系 + Redis +
Postgres + ES + Nginx 网关\*\*"架构。

\- 不是 SPA 框架（React/Vue）主导，而是 FastAPI + Jinja2 + 原生 JS
模块化加载。

\- 代码入口可看
\[README.md\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/README.md#L3-L30)
与
\[main.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/main.py#L33-L88)。

\*\*技术选型\*\*

\- 后端：FastAPI / Uvicorn / SQLAlchemy / Alembic / Redis / Celery /
Elasticsearch / Prometheus / OpenTelemetry / JWT

\- 见
\[backend/requirements.txt\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/requirements.txt)

\- Worker：Celery + Redis + SQLAlchemy + openai + ffmpeg + boto3 等

\- 见
\[worker/requirements.txt\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/worker/requirements.txt)

\- 运行编排：docker-compose（db/redis/es/backend/backend_celery/worker）

\- 见
\[docker-compose.yml\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/docker-compose.yml#L3-L118)

\*\*分层设计\*\*

\- 网关层（Nginx）：反代、限流、SSE 优化、静态缓存策略

\-
\[nginx.conf\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/deploy/nginx/nginx.conf#L23-L213)

\- 应用层（FastAPI）：API 路由 + 模板页 + 静态资源 + 诊断与健康检查

\-
\[main.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/main.py#L84-L125)

\-
业务路由层：auth/users/posts/feed/search/interaction/upload/observability/ai/ops

\-
\[api.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/api.py#L7-L23)

\- 数据模型层：Post / MediaAsset / AIJob / ClientEvent / ESReindexJob

\-
\[all_models.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L65-L330)

\*\*前端模块设计\*\*

\- 首页由模板渲染并注入 build 标识与资源 URL。

\- \`main.js\`
负责按顺序加载前端模块（events/telemetry/actions/core/api/router/player/\...）。

\-
\[main.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/main.js#L153-L189)

\- 观测模块 telemetry 会把前端行为批量上报到后端
\`/observability/events\`。

\-
\[telemetry.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/modules/telemetry.js#L61-L176)

\*\*异步任务与 AI 生成链路\*\*

\- Backend Celery 负责业务调度与上下文透传（request/session/trace）。

\- \[backend
celery_app.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/core/celery_app.py#L33-L105)

\- 真正 AI 执行在 worker 队列（\`ai/transcode\`）。

\- \[worker
celery_app.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/worker/app/worker/celery_app.py#L32-L37)

\- 关键流：\`/api/v1/ai/create\` -\> 建 Post+AIJob -\> 发 worker task
-\> 回调更新帖子状态。

\- \[ai_creation
routes\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/ai_creation/routes.py#L19-L129)

\-
\[queue_service.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/queue_service.py#L15-L27)

\- \[posts
callback\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/posts.py#L1075-L1137)

\*\*数据与基础设施\*\*

\- 事务数据：PostgreSQL

\- 缓存与流：Redis（缓存/限流/幂等/Stream）

\-
\[cache.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/core/cache.py#L33-L67)

\- 搜索：Elasticsearch

\- \[docker-compose
ES\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/docker-compose.yml#L30-L43)

\- 媒体存储：S3/R2 兼容封装（预签名上传/下载）

\-
\[storage.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/storage.py#L8-L52)

\*\*观测与可运维性\*\*

\- Prometheus metrics（请求数、时延、构建信息、事件流指标等）

\- \[metrics
middleware\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/middleware/metrics.py#L7-L41)

\- OpenTelemetry 可接 OTLP 导出

\-
\[tracing.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/core/tracing.py#L4-L33)

\- 前后端事件观测闭环：前端 telemetry -\> API -\> Redis Stream / DB
fallback -\> 异步 drain

\-
\[observability.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/observability.py#L363-L606)

\*\*安全设计\*\*

\- JWT + 密码哈希（passlib + jose）

\-
\[security.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/core/security.py#L11-L52)

\- 写接口鉴权与 user_id 防越权校验

\- \[auth_required
middleware\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/middleware/auth_required.py#L20-L75)

\- 多级限流（Nginx + 应用层 token bucket）

\-
\[rate_limit.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/middleware/rate_limit.py#L125-L251)

\- Worker 回调签名/密钥/防重放

\-
\[worker_auth.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/core/worker_auth.py#L15-L59)

**如果你愿意，我下一步可以给你出一版"\*\*模块地图图谱\*\*"：按"用户可见功能（推荐流/创作台/个人页/搜索/互动）-\>
对应 API -\> 表结构 -\> 异步任务 -\>
前端文件"的一对一索引表，方便你后续快速定位代码。**

query:
整体架构与业务模块划分：推荐流、创作台、个人页、搜索、互动、观测、运维相关的前端、后端API、服务层、数据访问、异步任务在哪里定义

已完成全仓检索并交叉核对（前端调用、FastAPI路由、服务层、模型表、Celery/Worker任务），下面给出可直接落库的映射。

\*\*功能映射\*\*

\- \*\*推荐流\*\*：前端
\[player.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/app/player.js#L207-L260)、\[router.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/app/router.js#L75-L89)；API
\[feed.py:/feed\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/feed.py#L14-L31)（挂载于
\[api.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/api.py#L10-L20)
\`/posts/feed\`）；核心服务
\[feed_service.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/feed_service.py#L262-L434)、\[feed_recall.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/feed_recall.py#L30-L220)、\[ab_service.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/ab_service.py)；数据表
\[posts\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L65-L121)、\[interactions\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L175-L183)、\[user_personas\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L45-L64)、\[ab_assignments\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L278-L286)；异步任务
\[client_events.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/tasks/client_events.py#L155-L524)、\[dirty_flush.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/tasks/dirty_flush.py#L41-L160)、\[counters.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/tasks/counters.py#L9-L59)、\[reco_profile.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/tasks/reco_profile.py#L8-L62)。

\- \*\*创作台\*\*：前端
\[creator.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/app/creator.js#L97-L275)、\[studio.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/app/studio.js#L135-L1275)、\[studio.html\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/templates/studio.html)；API
\[ai_jobs.py:/submit等\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/ai_jobs.py#L1467-L1916)、\[posts.py:/create
/publish
/media\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/posts.py#L708-L2448)、\[upload.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/upload.py#L70-L140)；核心服务
\[queue_service.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/queue_service.py#L15-L30)、\[ai_pipeline.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/ai_pipeline.py)、\[ai_moderation.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/ai_moderation.py)、\[storage.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/storage.py)；数据表
\[ai_jobs\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L309-L330)、\[ai_job_messages\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L361-L370)、\[ai_job_draft_versions\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L372-L380)、\[ai_moderation_checks\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L333-L347)、\[posts/media_assets\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L65-L142)；异步任务
\[backend
ai_creation.py(占位转发)\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/tasks/ai_creation.py#L4-L24)、\[worker
celery_app.py
任务路由\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/worker/app/worker/celery_app.py#L32-L132)、\[worker
tasks.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/worker/app/worker/tasks.py#L30-L113)。

\- \*\*个人页\*\*：前端
\[profile.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/app/profile.js)；API
\[users.py:profile/followers/following/friends\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/users.py#L302-L969)、\[posts.py:user
posts\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/posts.py#L498-L538)、\[interaction.py:likes/favorites/history\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/interaction.py#L783-L1028)、\[ai_jobs.py:by_post/job详情草稿聊天\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/ai_jobs.py#L836-L1384)；核心服务
\[notification_service.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/notification_service.py#L12-L220)、\[post_presenter.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/post_presenter.py)；数据表
\[users\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L6-L44)、\[follows\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L184-L190)、\[friend_requests\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L218-L226)、\[notification_events/reads\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L228-L246)；异步任务
\[notification_backfill.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/tasks/notification_backfill.py#L6-L25)、\[reco_profile.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/tasks/reco_profile.py#L8-L62)。

\- \*\*搜索\*\*：前端
\[search.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/app/search.js)；API
\[search.py:/hot /posts
/share-views\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/search.py#L170-L300)、\[users.py:/search-user\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/users.py#L339-L568)；核心服务
\[search_service.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/search_service.py#L82-L954)、\[search_hot_service.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/search_hot_service.py#L36-L134)、\[engagement_service.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/engagement_service.py#L15-L108)；数据表
\[posts\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L65-L121)、\[client_events\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L248-L260)、\[es_reindex_jobs\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L263-L275)；异步任务
\[search_index.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/tasks/search_index.py#L10-L180)、\[client_events.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/tasks/client_events.py#L380-L449)。

\- \*\*互动\*\*：前端
\[notifications.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/app/notifications.js)、\[comments.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/app/comments.js)、\[interaction_store.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/app/interaction_store.js)、\[player.js(历史/观看上报)\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/app/player.js#L1419-L1469)；API
\[interaction.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/interaction.py#L74-L1313)、\[messages.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/messages.py#L28-L104)、\[users.py:follow/friend-request\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/users.py#L742-L861)；核心服务
\[counter_service.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/counter_service.py)、\[hot_counter_service.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/hot_counter_service.py)、\[notification_service.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/notification_service.py#L12-L220)；数据表
\[interactions\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L175-L183)、\[comments/comment_reactions/danmaku\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L143-L217)、\[messages\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L191-L199)、\[post_counter_events/post_counters\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L288-L307)；异步任务
\[counters.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/tasks/counters.py#L9-L59)、\[dirty_flush.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/tasks/dirty_flush.py#L41-L160)、\[notification_backfill.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/tasks/notification_backfill.py#L6-L25)。

\- \*\*观测与运维\*\*：前端
\[modules/observability.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/modules/observability.js#L1-L98)、\[modules/telemetry.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/modules/telemetry.js#L61-L210)、\[admin.html\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/templates/admin.html#L836-L2690)；API
\[observability.py:/token
/events\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/observability.py#L334-L363)、\[ops.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/ops.py#L26-L2271)、\[posts.py
admin
metrics\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/posts.py#L1567-L1974)；核心服务
\[job_event_service.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/job_event_service.py)、\[search_service.py(ES重建)\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/search_service.py#L683-L893)、运行时配置
\[runtime_client_events.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/observability/runtime_client_events.py)、\[runtime_ai_production.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/observability/runtime_ai_production.py)；数据表
\[client_events\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L248-L260)、\[es_reindex_jobs\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L263-L275)、\[ai_jobs/ai_moderation_checks\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L309-L347)、\[notification_events\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L228-L239)；异步任务
\[client_events.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/tasks/client_events.py#L155-L524)、\[search_index.py:rebuild_posts_index_job\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/tasks/search_index.py#L44-L180)、Celery装载
\[celery_app.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/core/celery_app.py#L67-L82)。

\*\*总入口\*\*

\- 后端路由聚合：
\[api.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/api.py#L7-L23)

\- 后端任务装配：
\[celery_app.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/core/celery_app.py#L67-L82)

\- Worker任务路由： \[worker
celery_app.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/worker/app/worker/celery_app.py#L32-L37)

**太好了，我给你做一版"\*\*AIseek
模块地图（可落地开发索引）\*\*"。你可以直接拿它当"功能→代码定位"手册。**

\*\*一图总览\*\*

\- 业务主链路：\`前端页面模块 -\> /api/v1 路由 -\> services 业务层 -\>
models 数据表 -\> Celery/Worker 异步任务\`

\- 网关入口：Nginx -\> FastAPI（模板+API+静态）-\>
Redis/Postgres/ES/Worker

\-
路由聚合入口：\[api.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/api.py#L7-L23)

\-\--

\*\*1) 推荐流（首页刷视频）\*\*

\- 前端模块：

\-
\[player.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/app/player.js#L207-L260)

\-
\[router.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/app/router.js#L75-L89)

\- API：

\- \[feed.py
\`/feed\`\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/feed.py#L14-L31)

\- 核心服务：

\-
\[feed_service.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/feed_service.py#L262-L434)

\-
\[feed_recall.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/feed_recall.py#L30-L220)

\- 核心表：

\-
\[posts\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L65-L121)

\-
\[interactions\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L175-L183)

\- 异步：

\-
\[client_events.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/tasks/client_events.py#L155-L524)

\-
\[counters.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/tasks/counters.py#L9-L59)

\-\--

\*\*2) 创作台（AI 生成）\*\*

\- 前端模块：

\-
\[creator.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/app/creator.js#L97-L275)

\-
\[studio.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/app/studio.js#L135-L1275)

\-
\[studio.html\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/templates/studio.html)

\- API：

\-
\[ai_jobs.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/ai_jobs.py#L1467-L1916)

\-
\[posts.py（create/publish/media）\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/posts.py#L708-L2448)

\-
\[upload.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/upload.py#L70-L140)

\- 核心服务：

\-
\[queue_service.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/queue_service.py#L15-L30)

\-
\[ai_pipeline.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/ai_pipeline.py)

\-
\[storage.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/storage.py)

\- 核心表：

\-
\[ai_jobs\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L309-L330)

\-
\[ai_job_messages\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L361-L370)

\-
\[ai_job_draft_versions\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L372-L380)

\- 异步：

\- 后端调度：\[backend
celery_app.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/core/celery_app.py#L67-L82)

\- Worker执行：\[worker
celery_app.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/worker/app/worker/celery_app.py#L32-L37)

\- Worker任务：\[worker
tasks.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/worker/app/worker/tasks.py#L30-L113)

\-\--

\*\*3) 个人页（作品/关注/草稿编辑）\*\*

\-
前端模块：\[profile.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/app/profile.js)

\- API：

\-
\[users.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/users.py#L302-L969)

\-
\[posts.py（用户作品）\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/posts.py#L498-L538)

\-
\[interaction.py（likes/favorites/history）\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/interaction.py#L783-L1028)

\- 核心表：

\-
\[users\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L6-L44)

\-
\[follows\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L184-L190)

\-
\[friend_requests\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L218-L226)

\-\--

\*\*4) 搜索（视频/用户/热词）\*\*

\-
前端模块：\[search.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/app/search.js)

\- API：

\-
\[search.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/search.py#L170-L300)

\- \[users.py
\`/search-user\`\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/users.py#L339-L568)

\- 核心服务：

\-
\[search_service.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/search_service.py#L82-L954)

\-
\[search_hot_service.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/search_hot_service.py#L36-L134)

\- 异步索引：

\-
\[search_index.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/tasks/search_index.py#L10-L180)

\-\--

\*\*5) 互动（点赞/评论/弹幕/私信/通知）\*\*

\- 前端模块：

\-
\[comments.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/app/comments.js)

\-
\[notifications.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/app/notifications.js)

\-
\[interaction_store.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/app/interaction_store.js)

\- API：

\-
\[interaction.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/interaction.py#L74-L1313)

\-
\[messages.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/messages.py#L28-L104)

\- 核心表：

\- \[comments / comment_reactions /
danmaku\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L143-L217)

\-
\[messages\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L191-L199)

\- \[notification_events /
notification_reads\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L228-L246)

\-\--

\*\*6) 观测与运维（埋点/管理台/诊断）\*\*

\- 前端：

\-
\[telemetry.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/modules/telemetry.js#L61-L210)

\-
\[observability.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/modules/observability.js#L1-L98)

\-
\[admin.html\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/templates/admin.html#L836-L2690)

\- API：

\-
\[observability.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/observability.py#L334-L363)

\-
\[ops.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/ops.py#L26-L2271)

\- 异步：

\-
\[client_events.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/tasks/client_events.py#L155-L524)

\-\--

\*\*底层与安全关键点\*\*

\-
中间件链（日志/灰度/鉴权/限流/写保护/metrics）：\[main.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/main.py#L55-L82)

\-
JWT/密码安全：\[security.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/core/security.py#L11-L52)

\-
写接口鉴权中间件：\[auth_required.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/middleware/auth_required.py#L20-L75)

\-
应用限流：\[rate_limit.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/middleware/rate_limit.py#L125-L251)

\-
网关限流与静态缓存策略：\[nginx.conf\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/deploy/nginx/nginx.conf#L23-L213)

\-\--

**如果你愿意，我下一步可以给你一版"\*\*研发协作手册版\*\*"：**

**- 每个功能模块的\*\*改动最小入口文件\*\***

**- \*\*联调时必看 API\*\***

**- \*\*最容易踩坑点\*\***

**- \*\*上线前检查清单\*\*（数据库/缓存/异步/搜索/观测）**

**这样你团队新同学上手会非常快。**

太好了，下面给你一版可以直接发团队使用的 \*\*AIseek
研发协作手册（精简实战版）\*\*。

\*\*1) 快速上手\*\*

\- \*\*后端主入口\*\*：\`FastAPI app + 中间件 + 路由挂载\` 在
\[main.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/main.py#L33-L125)。

\- \*\*API 总路由图\*\*：所有 v1 模块聚合在
\[api.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/api.py#L7-L23)。

\- \*\*前端真实入口\*\*：模板注入后，模块化加载在
\[main.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/main.js#L153-L189)。

\- \*\*异步总入口\*\*：后端 Celery 任务装配在
\[celery_app.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/core/celery_app.py#L67-L82)，Worker
路由在 \[worker
celery_app.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/worker/app/worker/celery_app.py#L32-L37)。

\- \*\*网关与限流\*\*：Nginx 反代、静态缓存和限流规则在
\[nginx.conf\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/deploy/nginx/nginx.conf#L23-L213)。

\*\*2) 功能改动最小入口（按业务）\*\*

\- \*\*推荐流\*\*：先看
\[feed.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/feed.py#L14-L31)
→
\[feed_service.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/feed_service.py#L262-L434)
→ 前端
\[player.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/app/player.js#L207-L260)。

\- \*\*AI 创作台\*\*：先看
\[ai_jobs.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/ai_jobs.py#L1467-L1916)
与
\[posts.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/posts.py#L708-L2448)，前端在
\[studio.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/app/studio.js#L135-L1275)。

\- \*\*个人页/作品管理\*\*：先看
\[users.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/users.py#L302-L969) +
\[profile.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/app/profile.js)。

\- \*\*搜索\*\*：先看
\[search.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/search.py#L170-L300) +
\[search_service.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/search_service.py#L82-L954) +
\[search.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/app/search.js)。

\- \*\*互动（赞评私信通知）\*\*：先看
\[interaction.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/interaction.py#L74-L1313)、\[messages.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/messages.py#L28-L104)、前端
\[comments.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/app/comments.js)
/
\[notifications.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/app/notifications.js)。

\*\*3) 联调时必看 API\*\*

\-
\*\*登录与用户态\*\*：\`/api/v1/auth/\*\`、\`/api/v1/users/\*\`（入口见
\[api.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/api.py#L7-L23)）。

\-
\*\*内容链路\*\*：\`/api/v1/posts/\*\`、\`/api/v1/ai/\*\`、\`/api/v1/ai/jobs/\*\`（见
\[posts.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/posts.py#L708-L2448)、\[ai_jobs.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/ai_jobs.py#L836-L1916)）。

\-
\*\*搜索链路\*\*：\`/api/v1/posts/search\`、\`/api/v1/users/search-user\`（见
\[search.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/search.py#L170-L300)、\[users.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/users.py#L339-L568)）。

\- \*\*观测链路\*\*：\`/api/v1/observability/\*\` + 调试接口（见
\[observability.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/observability.py#L334-L606)、\[main.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/main.py#L774-L960)）。

\*\*4) 常见坑（你团队最该避开的）\*\*

\- \*\*改了 JS 但页面不生效\*\*：先看响应头里的 \`x-aiseek-build /
x-chain-main-js / x-chain-actions-js\`，确认命中实例和脚本版本一致（由
\[main.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/main.py#L573-L589)
注入）。

\- \*\*有数据但前端看不到\*\*：优先查 \`post_id -\> ai_job_id -\>
draft/result\` 三段链路（见
\[ai_jobs.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/ai_jobs.py#L836-L1384)）。

\- \*\*交互偶发失效\*\*：先检查动作分发层
\[actions.js\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/static/js/modules/actions.js)
与页面局部拦截是否冲突。

\- \*\*异步任务"提交成功但不产出"\*\*：看 backend Celery
是否发出、worker
是否消费（\[queue_service.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/queue_service.py#L15-L30)、\[worker
tasks.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/worker/app/worker/tasks.py#L30-L113)）。

\- \*\*搜索结果异常\*\*：检查 ES
索引/重建任务状态（\[search_index.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/tasks/search_index.py#L10-L180)、\[search_service.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/services/search_service.py#L683-L893)）。

\*\*5) 上线前检查清单（建议直接变成 SOP）\*\*

\-
\*\*配置与安全\*\*：\`SECRET_KEY/WORKER_SECRET\`、鉴权中间件、限流开关是否符合环境（\[config.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/core/config.py#L9-L253)、\[auth_required.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/middleware/auth_required.py#L20-L75)）。

\- \*\*数据库\*\*：迁移是否执行、核心表字段齐全（模型见
\[all_models.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/models/all_models.py#L6-L380)）。

\- \*\*缓存与队列\*\*：Redis 可达、Celery worker
在线、任务路由正确（\[celery_app.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/core/celery_app.py#L67-L82)、\[worker
celery_app.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/worker/app/worker/celery_app.py#L32-L37)）。

\- \*\*前端资源\*\*：build
与脚本路径一致，静态缓存策略符合预期（\[main.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/main.py#L535-L560)、\[nginx.conf\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/deploy/nginx/nginx.conf#L49-L102)）。

\-
\*\*观测可用\*\*：\`/metrics\`、\`/observability/events\`、管理台关键指标正常（\[metrics.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/middleware/metrics.py#L7-L41)、\[observability.py\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/observability.py#L334-L606)）。

\*\*6) 你可以直接用的"排障路径"\*\*

\- \*\*先定位实例\*\*：看 \`x-aiseek-instance + x-aiseek-build\`。

\- \*\*再看脚本链路\*\*：看 \`x-chain-\*\` 是否命中预期文件。

\- \*\*再看业务探针\*\*：\`/api/v1/debug/chain-status?post_id=\...\` 的
\`probe/client_probe\`。

\- \*\*最后看异步与存储\*\*：任务状态、DB 行、ES 索引是否一致。

**如果你要，我下一步可以直接给你产出一份
\`docs/engineering-playbook.md\`（可提交仓库），把这版手册固化为团队规范文档。**

已帮你出好一份，并落库到：

\-
\[engineering-playbook.md\](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/docs/engineering-playbook.md)

\*\*这份文档包含\*\*

\- AIseek 整体架构与关键入口

\- 功能模块地图（前端→API→服务→数据→异步）

\- 研发协作流程（改需求前/开发中/联调时）

\- 常见问题排障手册

\- 上线前检查清单（安全/数据/异步/网关/观测）

\- 团队协作约定与常用定位路径

如果你愿意，我下一步可以再给你补一份"\*\*TL;DR
一页版\*\*"（给产品/测试/新同学快速看），从这份手册自动提炼出 10
条最关键规则。
