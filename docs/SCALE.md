# Scale Blueprint

## 目标
将系统从单机开发形态，演进为可水平扩展、可观测、可容灾的生产形态，为极高并发场景奠定“可扩展基础能力”。

## 原则（避免过度工程化）
- 优先把系统做成“可观测、可测、可部署、可回滚”，再谈复杂分布式。
- 默认不引入 K8s/Redis Cluster/分库分表，除非监控数据证明“必须”。
- 通过预留接口与参数开关保证未来能演进，而不是现在就把复杂度拉满。

## 分阶段演进（参考）
- 阶段 1（<100 万用户/早期迭代）：单体 + Postgres 单实例 + Redis 单节点 + Nginx + 对象存储/CDN
- 阶段 2（100 万~1000 万）：少量服务拆分（2~5）+ Postgres 读写分离 + Redis 高可用（哨兵/托管）+ 队列按需
- 阶段 3（1000 万~1 亿）：容器化多实例（Compose/简单编排）+ 更严格的限流/降级 + Postgres 分区（按数据规模）+ 只读副本扩展
- 阶段 4（>1 亿）：多活/跨地域 + Redis Cluster（按 QPS/内存瓶颈）+ 分域拆库拆表（最后手段）

## 分层架构
- 边缘层：CDN 缓存静态资源与视频文件，边缘做基础防护与限流。
- 接入层：反向代理/Ingress 负责 TLS、路由、连接复用与负载均衡。
- 应用层：FastAPI Web 实例无状态化，按 CPU/延迟/HPA 水平扩展。
- 异步层：Celery Worker 承接耗时任务（AI 生成、转码、索引、计数器合并），与 Web 解耦。
- 缓存层：Redis（集群/哨兵/托管）用于会话、限流、幂等、热点计数器与缓存版本。
- 数据层：Postgres 主从（读写分离）/分区/索引；极限规模时按业务域拆库拆表。
- 存储层：对象存储（R2/S3）承载媒体文件，应用只存 URL 与元数据。

## 关键代码能力
### 读写分离与连接池
- 写库：`DATABASE_URL`
- 读库：`READ_DATABASE_URL`（未设置时会回落到写库）
- 连接池参数（非 sqlite 生效）：
  - `DB_POOL_SIZE`
  - `DB_MAX_OVERFLOW`
  - `DB_POOL_TIMEOUT_SEC`
  - `DB_POOL_RECYCLE_SEC`

实现位置：
- [session.py](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/db/session.py)
- [deps.py](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/deps.py)

### 高基数列表分页
以下接口支持 `limit/cursor` 并返回 `x-total-count/x-next-cursor`：
- 点赞/收藏/观看历史：[interaction.py](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/interaction.py)
- 关注/粉丝：[users.py](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend/app/api/v1/endpoints/users.py)

### Redis 与 ES 韧性参数
Redis：
- `REDIS_SOCKET_TIMEOUT_SEC`
- `REDIS_CONNECT_TIMEOUT_SEC`
- `REDIS_MAX_CONNECTIONS`

Elasticsearch：
- `ES_REQUEST_TIMEOUT_SEC`
- `ES_MAX_RETRIES`
- `ES_RETRY_ON_TIMEOUT`

### 搜索限流与预算（抗请求风暴）
搜索类 GET 接口（`/api/v1/posts/search`、`/api/v1/users/search-user`）采用“两层保护”：
- 固定窗口限流：按用户/会话/IP，按路由维度计数（防止持续刷接口）。
- 成本预算（令牌桶）：按请求成本扣减 tokens（query 长度、limit 越大成本越高），可平滑限制突发并保护 DB/ES 尾延迟。

可配置项：
- 固定窗口：
  - `RATE_LIMIT_SEARCH_PER_MIN_ANON`
  - `RATE_LIMIT_SEARCH_PER_MIN_AUTH`
- 预算（令牌桶）：
  - `SEARCH_BUDGET_RATE_PER_SEC_ANON` / `SEARCH_BUDGET_BURST_ANON`
  - `SEARCH_BUDGET_RATE_PER_SEC_AUTH` / `SEARCH_BUDGET_BURST_AUTH`

调参建议（生产落地）：
- 先以“429 比例 + 搜索 P95/P99 延迟 + ES/DB CPU/连接数”作为核心观测指标，目标是把尾延迟压住且 429 可解释（主要来自异常刷接口与极端突发）。
- 匿名用户优先控紧（窗口限流与预算都低一些），登录用户适当放宽；必要时对“新注册/低信誉用户”再单独收紧（可后续演进）。
- cost 估算与预算上限要与接口形态匹配：`limit` 越大、query 越长成本越高；上线后根据 DB/ES 实际压力调整成本函数与 rate/burst。

### 前端交付与缓存策略（避免“静默卡死”）
- HTML 页面（`/`、`/studio`、`/admin`）：`Cache-Control: no-store`，确保发布后首屏总能拿到最新入口。
- 静态资源（`/static/**`）：`Cache-Control: public, max-age=31536000, immutable`，配合版本参数实现强缓存与低延迟。
- 版本参数：模板下发 `build_id` 并注入到脚本 URL（例如 `main.js?v={{ build_id }}`），避免浏览器/代理缓存导致的脚本错配。
- 启动自检：前端启动脚本在关键模块加载后进行函数存在性检查，缺失时直接展示“初始化失败”遮罩而不是无限“加载中...”，便于快速定位与回滚。

## 本地模拟“多实例+负载均衡”
使用 Nginx 反代到 3 个 Web 实例（演示水平扩展基本形态）：
- [docker-compose.scale.yml](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/docker-compose.scale.yml)
- [nginx.conf](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/deploy/nginx/nginx.conf)

入口：
- http://localhost:5001

## 生产落地清单（摘要）
- 数据库：读写分离 + 分区（按时间/用户/内容域），热点表与索引策略，在线迁移方案。
- 缓存：多级缓存（CDN/边缘/Redis/本地），缓存键规范与版本化失效。
- 队列：Broker 高可用与积压告警，任务幂等与可重试策略，Worker 水平扩展。
- 限流：边缘+接入+应用三层限流，按用户/会话/接口分级阈值，熔断与降级策略。
- 可观测：指标（Prometheus）、链路（OTLP）、日志（结构化 + request_id/session_id）。
