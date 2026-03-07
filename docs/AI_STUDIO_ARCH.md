# AI创作工作台：全链路流程与10亿并发架构升级

本文面向“AI创作工作台（/studio）”的端到端链路，给出：
- 业务流程点梳理（从用户文稿到成片）
- 当前代码落点与数据模型边界
- 面向10亿用户基本高并发的底层架构升级路线（可渐进落地）

## 一、端到端流程点（工作台视角）

### 1) 创建作品（用户文稿 → 创建 Post + AIJob）
入口：
- 工作台“开始生成” → `POST /api/v1/ai/submit`

后端效果：
- 创建 `Post(status=queued, post_type=video, content_text, user_id, ...)`
- 创建 `AIJob(kind=generate_video, status=queued, input_json, post_id, user_id, ...)`
- 触发“派发 generate_video 到 worker”
- 若触发预审：`AIJob.status=needs_review` + `AIModerationCheck(status=pending)`，不派发

核心目标：
- 提交接口必须“快返回”（写库即可），派发失败也不能把任务打死

### 2) 预审与人审（审查功能）
预审：
- `preflight_text(...)` 同步执行（敏感词/PII/重复/事实无来源等）
- 命中需要人审：工作台“审查”页展示原因

人审流转：
- 用户：`GET /ai/jobs/{job_id}/review` 查看原因；`POST /ai/jobs/{job_id}/appeal` 申诉
- 管理员：`GET /ai/admin/review/list` 获取待审；`POST /ai/admin/review/{check_id}/decision` 决策并继续派发

### 3) 生成执行（口播稿/脚本 → 配音/配乐/封面 → 成片）
执行方：worker
- 后端通过 Celery broker 派发 `generate_video(job_id, content, user_id, post_id, ...)`

worker 产物：
- 脚本/分镜：回调携带 `draft_json`（受写入白名单限制）
- AI对话：回调携带 `assistant_message`（受写入白名单限制）
- 媒体：回调携带 `hls_url/mp4_url/cover_url/duration/...`

### 4) 回调写入（状态、单调性、幂等、防重放）
回调入口：
- `POST /api/v1/posts/callback`

关键策略：
- 状态机：禁止回退覆盖；允许“派发失败后纠错推进”
- progress 单调性：只增不减
- stage 单调性：基于 `stage_rank` 只增不减
- 幂等/去重：dup 直接短路（并计入指标）
- 写入白名单：限制 `draft_json/assistant_message` 的写入 stage

### 5) 脚本编辑与回退（回退文稿功能）
入口：
- 工作台“脚本”页保存 → `POST /ai/jobs/{job_id}/draft`
- 工作台“回退”页：
  - 列表：`GET /ai/jobs/{job_id}/draft/history`
  - 取回：`GET /ai/jobs/{job_id}/draft/history/{version_id}`
  - 恢复：再次 `POST /ai/jobs/{job_id}/draft`（source=restore）

目标：
- 所有关键产出均版本化；允许回退到任意草稿并重跑

### 6) 重跑与版本管理（多版本作品）
重跑：
- `POST /ai/jobs/{job_id}/rerun`（基于当前 draft 生成新的 job）

媒体版本：
- worker 回调写入 `MediaAsset(version=...)` 并设置 `post.active_media_asset_id`
- `GET /posts/{post_id}/media` 列表
- `POST /posts/{post_id}/media/activate` 切换激活版本

### 7) 预览与发布（预览功能）
预览：
- 工作台视频播放器读取 `Post.mp4_url/video_url/cover_url`
- HLS 在浏览器端可通过后续引入 hls.js 进行增强（当前以 MP4 预览为主）

### 8) AI沟通（AI作品沟通功能）
对话：
- 发送：`POST /ai/jobs/{job_id}/chat`
- 拉取：`GET /ai/jobs/{job_id}/chat`
- AI建议：`POST /ai/jobs/{job_id}/chat/ai_suggest`
- 基于对话生成新版本：`POST /ai/jobs/{job_id}/revise_from_chat`

目标：
- 对话留痕、可追溯；对话驱动脚本改写与版本迭代

### 9) 运维观测（后台管理联动）
后台（/admin）系统设置 → Worker 回调健康度：
- 指标：dup/ignored/progress_regress 等
- 样例：异常回调样例
- 告警：阈值黄/红 + 确认闭环
- 存储模式：Redis / 本地降级

## 二、当前实现的关键边界（代码落点）

- 工作台 UI：`/studio` + `static/js/app/studio.js`
- 提交与作业：`/api/v1/ai/*`（ai_jobs）
- 回调与媒体资产：`/api/v1/posts/callback` + `MediaAsset`
- 审查：`ai_moderation.py` + `AIModerationCheck`
- 草稿：`AIJobDraftVersion` + draft history API
- 事件流：`/ai/jobs/{job_id}/events` + SSE `.../events/stream`
- 全局写限流/幂等：`WriteGuardMiddleware`（POST/PUT/DELETE）

## 三、10亿并发的“底层架构升级路线”（可渐进）

### A. 入口层（抗流量/抗抖动）
- CDN：静态资源与视频走 CDN；动态 API 走多 Region L7
- WAF/反爬：基于 IP/ASN/指纹/行为特征
- 全局限流：分层限流（IP、用户、接口、作品维度），超限返回可恢复错误
- 幂等：提交/重试派发/互动写接口必须幂等（写中间件 + 业务幂等键）

### B. API 层（无状态、可水平扩展）
- FastAPI 多进程/多实例：只做鉴权、写库、投递、回调校验
- 重请求拆分：提交“快返回”，重计算全部异步化
- 读写分离：读库只读 session（本项目已具备 get_read_db）

### C. 队列与异步计算（核心承载）
- Broker：Kafka / Redis Streams / RabbitMQ（按业务选择）
- Outbox：提交先落库，再由 dispatcher 扫描投递（保证“不丢任务”）
- 多队列分层：
  - 生成队列（长任务）
  - 轻任务（脚本改写/摘要/审核辅助）
  - 回调写入（快速落库）
- 限速与隔离：按用户/租户配额，避免大客户挤压

### D. 存储层（可扩展与可治理）
- DB：PostgreSQL + 分区/分片（按 user_id 或时间分区）
- 索引与归档：热数据索引齐全，冷数据归档到 OLAP/对象存储
- 对象存储：视频/封面/中间产物全部上 OSS/S3，DB 只存元数据

### E. 事件流与实时通知（SSE/WS）
- 事件持久化：Redis Streams / Kafka topic（按 job_id）
- SSE 服务器不做轮询：改为阻塞式读取（XREAD block）或订阅式推送
- 回放能力：最近 N 条事件可重放，断线续传

### F. 审查与风控（规模化必备）
- 多级审查：
  - preflight（同步快速）
  - async moderation（异步深度）
  - 人审（队列化、可追溯）
- 审计日志：所有关键写操作可追溯（job、draft、media、review）

### G. 观测与自愈（SLO 驱动）
- 指标：队列积压、派发失败率、回调 dup/ignored、耗时分布
- 日志：请求链路 ID、job_id 贯穿
- 告警：阈值 + 错误预算
- 自愈：派发失败自动重试、指数退避、熔断与降级

## 四、建议的“本仓库可落地”迭代顺序（从现在到可规模化）

1) 派发失败不打死 + 可重试 + 自动重试（自愈闭环）
2) 事件流从轮询升级为 Redis Streams 阻塞读取（降低CPU与DB压力）
3) AI 相关表加索引 + API 分页（读扩展）
4) 提交/聊天/建议接口细粒度限流与幂等（抗刷与成本控制）
5) 引入 Outbox Dispatcher（跨实例一致、不丢任务）

