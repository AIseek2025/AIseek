# AIseek-Trae-v1 全量技术与资料说明（2026-03-15）

本文档用于对 `AIseek-Trae-v1` 项目做一次完整的工程说明，覆盖：
- 代码与文档资料清单（含关键文件逐项说明）
- 技术选型与架构设计
- 功能模块
- GitHub 工作流
- 阿里云与 Docker 部署
- 备份、维护、巡检与故障处理

---

## 1. 项目概览

AIseek-Trae-v1 是一个“抖音风桌面端 + AI 创作工作台”的一体化项目，核心目标是：
- 前台提供短视频信息流浏览、互动、搜索、用户页等能力
- 后台提供 AI 文案/音频/视频生成、转码、封面生成、任务调度、回调处理与运营运维能力

运行形态为：
- `backend`：FastAPI 提供 API + 页面渲染 + 静态资源入口
- `worker`：Celery 异步执行 AI 任务与转码流水线
- `redis`：消息队列、缓存、限流与计数中间层
- `postgres`：主数据存储（帖子、用户、任务、事件、搜索辅助等）
- `nginx`：反向代理与静态资源直出

---

## 2. 技术选型与理由

## 2.1 后端
- FastAPI + Uvicorn/Gunicorn
  - 高性能 API 服务，便于异步 IO 与接口拆分
- SQLAlchemy + Alembic
  - 模型与迁移体系稳定，支持持续演进
- PostgreSQL
  - 关系数据强一致，适合社交数据与任务数据
- Redis
  - 作为 Celery Broker/Result，同时承载缓存与限流
- Celery
  - 将 AI 与转码等重任务异步化，提升前台响应
- Elasticsearch（可选增强）
  - 用于搜索能力强化（索引重建、别名切换、降级策略）
- OpenTelemetry + Prometheus
  - 链路与指标可观测

## 2.2 前端
- Jinja2 模板 + 原生 JS/CSS
  - 开销低、控制力强、适合逐步演进
- 前端模块化脚本（`backend/static/js/app/*.js`）
  - `player.js`、`studio.js`、`search.js` 等按业务分治

## 2.3 AI 与媒体处理
- Edge-TTS、OpenAI/DeepSeek、外部图像/封面 API
- ffmpeg/ffmpeg-python
  - 音视频合成、转码、封面抽帧、HLS 产物生成

## 2.4 部署与交付
- Docker / Docker Compose（生产单机）
- GitHub Actions（CI、部署、备份）
- 阿里云 ECS + OSS（对象存储备份）

---

## 3. 底层系统架构（数据流）

1) 用户请求进入 Nginx  
2) 静态资源由 Nginx 直出；动态请求转发 FastAPI  
3) FastAPI 写入 PostgreSQL / Redis，并将重任务投递 Celery  
4) Worker 消费任务，调用 AI 能力与 ffmpeg 生成媒体  
5) 产物回写到静态目录或对象存储映射路径  
6) 前端通过 feed/post/media API 拉取最新视频、封面、字幕轨道并播放  

关键工程策略：
- 写后读粘主（减少主从延迟可见性问题）
- 搜索降级与限流预算（防风暴）
- 静态资源版本化与缓存控制
- 备份 + 远端校验 + 清理保留策略

---

## 4. 功能模块说明

## 4.1 信息流与互动
- 帖子 feed、播放、点赞、评论、收藏、转发、关注
- 主要入口：
  - `backend/app/api/v1/endpoints/feed.py`
  - `backend/app/api/v1/endpoints/interaction.py`
  - `backend/static/js/app/player.js`

## 4.2 创作工作台（Studio）
- 任务草稿、预览、重跑、发布、媒体版本切换
- 主要入口：
  - `backend/app/api/v1/endpoints/ai_jobs.py`
  - `backend/app/api/v1/endpoints/ai_creation/routes.py`
  - `backend/static/js/app/studio.js`

## 4.3 搜索
- 帖子搜索、用户搜索、ES/PG 降级兜底、分页游标
- 主要入口：
  - `backend/app/services/search_service.py`
  - `backend/app/api/v1/endpoints/search.py`
  - `backend/app/api/v1/endpoints/posts.py`
  - `backend/app/api/v1/endpoints/users.py`

## 4.4 运营与可观测
- `/metrics`、运维接口、索引重建、资产发布
- 主要入口：
  - `backend/app/main.py`
  - `backend/app/api/v1/endpoints/ops.py`
  - `backend/app/api/v1/endpoints/observability.py`

## 4.5 备份恢复
- 本地打包、OSS 上传、远端校验、保留清理
- 主要入口：
  - `tools/backup_run.py`
  - `tools/backup_daily.py`
  - `tools/backup_upload_s3.py`
  - `tools/backup_verify.py`
  - `tools/backup_prune.py`
  - `tools/restore_run.py`

---

## 5. 代码与文件清单（关键文件逐项说明）

说明：仓库文件体量较大，以下按“生产运行相关”逐项列出。历史归档、构建产物快照、第三方依赖目录不做逐行说明。

## 5.1 根目录关键文件
- `README.md`：项目总览与快速启动
- `DEPLOYMENT_GUIDE.md`：部署详细指南
- `DEPLOYMENT_SUMMARY.md`：部署总结
- `DEPLOYMENT_CHECKLIST.md`：上线检查清单
- `QUICK_DEPLOY.md`：快速部署命令
- `RESTART_GUIDE.md`：重启与恢复指引
- `WANX_API_KEY_CONFIG.md`：万相 API Key 配置
- `CODE_QUALITY_*.md / BUG_FIX_REPORT.md / FIXES_COMPLETE.md`：质量与修复报告
- `.env.example`：环境变量示例

## 5.2 GitHub 工作流
- `.github/workflows/ci.yml`：CI 检查流程
- `.github/workflows/deploy.yml`：推送 main 后通过 SSH 到阿里云更新部署
- `.github/workflows/backup_daily.yml`：每日备份 + 远端上传 + 校验

## 5.3 backend（服务核心）

### 5.3.1 入口与配置
- `backend/app/main.py`：FastAPI 主入口，路由挂载、中间件、指标、静态与模板
- `backend/app/recall_main.py`：召回/辅助服务入口
- `backend/app/core/config.py`：核心配置项（数据库、缓存、限流、搜索等）
- `backend/app/core/cache.py`：缓存工具
- `backend/app/core/celery_app.py`：Celery 配置
- `backend/app/core/security.py`：鉴权相关
- `backend/app/core/logging_config.py`：日志配置
- `backend/app/core/tracing.py`：链路追踪配置

### 5.3.2 API 层
- `backend/app/api/v1/api.py`：v1 路由汇总
- `backend/app/api/deps.py`：依赖注入（DB 会话、鉴权等）
- `backend/app/api/v1/endpoints/auth.py`：登录认证
- `backend/app/api/v1/endpoints/users.py`：用户接口
- `backend/app/api/v1/endpoints/posts.py`：帖子主接口（创建、发布、媒体、下载、管理）
- `backend/app/api/v1/endpoints/feed.py`：信息流
- `backend/app/api/v1/endpoints/interaction.py`：点赞/收藏/评论等互动
- `backend/app/api/v1/endpoints/search.py`：搜索接口
- `backend/app/api/v1/endpoints/social.py`：社交关系
- `backend/app/api/v1/endpoints/upload.py`：本地上传与转码相关接口
- `backend/app/api/v1/endpoints/media.py`：媒体相关接口
- `backend/app/api/v1/endpoints/ai_jobs.py`：AI 任务生命周期与状态
- `backend/app/api/v1/endpoints/ops.py`：运维接口
- `backend/app/api/v1/endpoints/observability.py`：可观测接口
- `backend/app/api/v1/endpoints/messages.py`：消息接口

### 5.3.3 服务层
- `backend/app/services/feed_service.py`：信息流聚合
- `backend/app/services/post_presenter.py`：帖子展示字段组装（含前端所需媒体字段）
- `backend/app/services/search_service.py`：搜索实现（ES/PG）
- `backend/app/services/ai_pipeline.py`：AI 任务编排
- `backend/app/services/storage.py`：存储抽象
- `backend/app/services/*counter*`：计数器体系
- `backend/app/services/notification_service.py`：通知服务
- `backend/app/services/reputation_service.py`：信誉/评分

### 5.3.4 中间件
- `backend/app/middleware/auth_required.py`：写接口鉴权防护
- `backend/app/middleware/rate_limit.py`：限流与预算
- `backend/app/middleware/metrics.py`：指标采集
- `backend/app/middleware/request_logging.py`：请求日志
- `backend/app/middleware/canary.py`：灰度相关
- `backend/app/middleware/write_guard.py`：写保护

### 5.3.5 任务层
- `backend/app/tasks/ai_creation.py`：AI 创作异步任务
- `backend/app/tasks/transcode.py`：转码任务
- `backend/app/tasks/search_index.py`：搜索索引任务
- `backend/app/tasks/counters.py`：计数器异步任务

### 5.3.6 数据层
- `backend/app/db/session.py`：数据库会话
- `backend/app/models/all_models.py`：核心模型汇总
- `backend/alembic/versions/*.py`：迁移脚本（索引、媒体字段、任务字段等）

### 5.3.7 前端静态（业务核心）
- `backend/static/js/app/core.js`：基础能力
- `backend/static/js/app/api.js`：前端 API 封装
- `backend/static/js/app/player.js`：播放页核心逻辑（视频源、字幕、封面、互动）
- `backend/static/js/app/studio.js`：Studio 页核心逻辑
- `backend/static/js/app/search.js`：搜索页逻辑
- `backend/static/css/style.css`：主样式
- `backend/templates/*.html`：Jinja 页面模板

## 5.4 worker（异步执行核心）
- `worker/app/worker/celery_app.py`：Worker Celery 入口
- `worker/app/worker/tasks/*.py`：任务执行（AI 生成、媒体合成、转码、回调）
- `worker/app/services/*.py`：AI 与媒体处理服务
- `worker/assets/bgm/README.md`：背景音乐资源说明
- `worker/requirements.txt`：Worker 依赖

## 5.5 deploy（部署相关）
- `deploy/aliyun/docker-compose.prod.yml`：阿里云单机生产编排
- `deploy/aliyun/README.md`：阿里云部署步骤
- `deploy/nginx/nginx.conf`：Nginx 主配置
- `deploy/nginx/simple.conf`：简化版 Nginx 配置
- `docker-compose.ops-simple.yml`：运维/简化部署组合

## 5.6 docs（运维与架构文档）
- `docs/README.md`：文档入口
- `docs/DEPLOY.md`：部署流程
- `docs/BACKUP.md`：备份与恢复体系
- `docs/SCALE.md`：扩容策略
- `docs/BLUEPRINT.md`：架构蓝图
- `docs/K8S.md`：Kubernetes 方案
- `docs/FINAL_STABLE_OPS_MANUAL.md`：稳定运维手册
- `docs/GITHUB_SECRETS_SETUP.md`：GitHub Secrets 配置
- `docs/DEPLOYMENT_PROCEDURE.md`：标准发布流程

## 5.7 tools（运维工具脚本）
- `tools/backup_run.py`：创建备份
- `tools/restore_run.py`：恢复备份
- `tools/backup_daily.py`：本地+远端+清理编排
- `tools/backup_upload_s3.py`：OSS/S3 兼容上传
- `tools/backup_verify.py`：上传结果验证
- `tools/backup_prune.py`：旧备份清理

---

## 6. GitHub 与仓库信息

- 部署工作流中使用的仓库地址：
  - `https://github.com/AIseek2025/AIseek.git`
- 典型流程：
  - 代码推送 `main` -> GitHub Actions `deploy.yml`
  - SSH 到阿里云 ECS 拉取最新代码并执行 `deploy/aliyun/update.sh`
- 备份流程：
  - `backup_daily.yml` 每日定时 + 手动触发
  - 执行 `tools/backup_daily.py` 并校验 OSS 备份对象

---

## 7. 阿里云、Docker 与部署说明

## 7.1 阿里云 ECS
- 推荐基础：4C8G 起步，系统盘 >= 80G
- 安全组建议：仅放行 80/443，禁止 5432/6379 公网暴露
- 域名解析到 ECS 公网 IP

## 7.2 Docker 生产编排
- 使用 `deploy/aliyun/docker-compose.prod.yml`
- 核心容器：
  - `db`（Postgres）
  - `redis`
  - `backend`（gunicorn + uvicorn worker）
  - `worker`（celery）
  - `nginx`

## 7.3 Nginx
- 静态资源直出路径：`/static/**`
- 反向代理 FastAPI 动态接口
- 证书目录：`deploy/aliyun/certs/`

---

## 8. 维护与巡检清单

日常维护建议：
- 应用健康检查：
  - 首页 `/`
  - Studio `/studio`
  - 管理页 `/admin`
  - 指标 `/metrics`
- 数据健康：
  - Postgres 连接数与慢查询
  - Redis 内存与 key 增长
- 媒体健康：
  - 视频 URL 可达
  - cover URL 200
  - subtitle_tracks 可读且 WEBVTT 有效
- 异步队列：
  - Celery 积压长度与失败重试
- 备份检查：
  - 本地备份产物存在
  - OSS 远端对象可读
  - 定期执行恢复演练

---

## 9. 备份、恢复、清理（执行建议）

- 创建备份：
  - `python tools/backup_run.py`
- 每日备份编排：
  - `BACKUP_REQUIRE_REMOTE=1 python tools/backup_daily.py`
- 恢复备份：
  - `python tools/restore_run.py --archive <archive.tar.gz> --dest <dir>`
- 清理旧备份：
  - `python tools/backup_prune.py --dir backups --keep 1 --name AIseek-Trae-v1`

---

## 10. 本次文档目标与边界

本文件已覆盖项目生产相关目录与关键文件的“逐项说明”。  
对于历史构建快照、依赖目录、缓存文件、运行时产物等非核心生产文件，采用“目录级说明 + 运行机制说明”的方式归档，不建议逐个文件人工维护说明。

---

## 11. 附：关键入口速查

- 主后端入口：`backend/app/main.py`
- Worker 入口：`worker/app/worker/celery_app.py`
- 播放核心：`backend/static/js/app/player.js`
- Studio 核心：`backend/static/js/app/studio.js`
- 部署编排：`deploy/aliyun/docker-compose.prod.yml`
- 部署工作流：`.github/workflows/deploy.yml`
- 每日备份工作流：`.github/workflows/backup_daily.yml`
- 备份主脚本：`tools/backup_daily.py`

