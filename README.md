# AIseek-Trae-v1

一个抖音风格（桌面端）的内容浏览/社交原型项目：后端使用 FastAPI（可切换 Postgres 读写分离）+ Redis（缓存/限流/幂等/计数器）+ Celery（异步任务），前端为 Jinja2 模板 + 原生 JS/CSS 单页交互。

当前默认运行入口为 `backend/app/main.py`（抖音风 UI）。

## 文档索引

- `docs/PROJECT_FULL_README_20260315.md`：项目全量技术说明（代码/架构/模块/GitHub/部署/阿里云/Docker/维护/备份）
- `docs/README.md`：文档总入口
- `docs/DEPLOY.md`：部署说明
- `docs/BACKUP.md`：备份与恢复
- `docs/SCALE.md`：扩容蓝图

## 快速开始（本地运行）

### 1) 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### 2) 启动后端（含模板/静态资源/API）

```bash
PYTHONPATH=backend python backend/app/main.py --port 5002
```

打开：`http://localhost:5002/`

## 目录结构

- `backend/`：FastAPI Web（模板渲染 + API + 静态资源）
- `worker/`：Celery worker（AI/转码/索引/计数器合并等异步任务）
- `deploy/`：Nginx 配置与部署样例
- `docs/`：部署与扩容、API 与运维文档
- `backups/`：标准化备份产物与备份/恢复脚本

## 核心能力（面向高并发可扩展）

### 鉴权与越权防护

- 写请求（`POST/PUT/DELETE` 且 `/api/v1/**`）强制 Bearer，并对 JSON body 中的 `user_id` 做强一致校验（防止“带 token 但伪造 user_id”越权）：
  - `backend/app/middleware/auth_required.py`
  - `backend/app/main.py`
- 典型写接口收口：`/api/v1/posts/create` 以 token 用户为准创建，不再信任客户端 `user_id`：
  - `backend/app/api/v1/endpoints/posts.py`

### 读写一致性（写后短期粘主）

- 写请求成功后短期下发 `aiseek_rw` cookie；读依赖 `get_read_db` 检测 cookie 后短时间走主库，缓解主从复制延迟导致的“写后读不一致”：
  - `backend/app/main.py`
  - `backend/app/api/deps.py`

### 搜索（ES 优先 + 降级 + 分页 + 缓存 + 抗风暴）

- 帖子搜索 `GET /api/v1/posts/search` 支持 `limit/cursor`，返回 `x-next-cursor`，并有首屏短 TTL 缓存：
  - `backend/app/api/v1/endpoints/posts.py`
  - `backend/app/services/search_service.py`
- 用户搜索 `GET /api/v1/users/search-user` 支持 `limit/cursor`，返回 `x-next-cursor`，并有首屏短 TTL 缓存：
  - `backend/app/api/v1/endpoints/users.py`
- ES 索引工程化：alias + streaming_bulk + 原子切换 + 校验回滚 + 保留历史索引：
  - `backend/app/services/search_service.py`
  - `backend/app/tasks/search_index.py`
- ES/DB 抖动保护：ES 熔断降级（cooldown），并有 ES 调用指标：
  - `backend/app/services/search_service.py`
- 搜索抗请求风暴：对 `/posts/search` 与 `/users/search-user` 增加固定窗口限流 + 成本预算（令牌桶）：
  - `backend/app/middleware/rate_limit.py`
  - `backend/app/core/config.py`
- Postgres 下搜索可扩展：全文检索 + trgm 索引，避免 `contains(%q%)` 全表扫描：
  - `backend/alembic/versions/0022_search_pg_indexes.py`
  - `backend/app/services/search_service.py`

### 运维与可观测

- `/metrics` 暴露构建信息、前端资源发布、ES 重建进度与计数等指标：
  - `backend/app/main.py`
- 资产发布/灰度/回滚与 ES 重建运维接口（管理员鉴权）：
  - `backend/app/api/v1/endpoints/ops.py`
- ES 重建状态落库（可审计可追溯）：
  - `backend/app/models/all_models.py`
  - `backend/alembic/versions/0021_es_reindex_jobs.py`

## 部署与交付

### Nginx 静态直出与缓存策略

- `/static/**` 由 Nginx 直出，按资源类型分层缓存（immutable/no-store/短缓存），降低后端压力并提升首屏体验：
  - `deploy/nginx/nginx.conf`
  - `deploy/nginx/simple.conf`
- 静态目录只读挂载示例：
  - `docker-compose.ops-simple.yml`
- 部署说明：
  - `docs/DEPLOY.md`

## 近期变更（基于 20260302-003150 备份的增量说明）

本仓库在最近两天完成了“可扩展基础能力”的一轮强化，覆盖：静态交付、写鉴权、读写一致性、ES 工程化、搜索分页/缓存/降级、PG 索引、搜索限流预算与备份体系。

完整变更文件清单：

- `README_CHANGES_20260304.md`
- `backups/*.changes.txt`（相对上一备份时间戳筛选的变更文件，取最新一份即可）

### 关键变更文件清单（按主题）

- 静态直出与缓存：`deploy/nginx/nginx.conf`、`deploy/nginx/simple.conf`、`docker-compose.ops-simple.yml`、`docs/DEPLOY.md`
- 写鉴权与越权防护：`backend/app/middleware/auth_required.py`、`backend/app/api/v1/endpoints/posts.py`
- 读写一致性粘主：`backend/app/main.py`、`backend/app/api/deps.py`
- ES 重建与可运维：`backend/app/services/search_service.py`、`backend/app/tasks/search_index.py`、`backend/app/api/v1/endpoints/ops.py`、`backend/app/models/all_models.py`、`backend/alembic/versions/0021_es_reindex_jobs.py`
- 搜索分页/缓存/体验：`backend/app/api/v1/endpoints/posts.py`、`backend/app/api/v1/endpoints/users.py`、`backend/static/js/app/search.js`
- Postgres 搜索索引：`backend/alembic/versions/0022_search_pg_indexes.py`
- 搜索抗风暴（限流+预算）：`backend/app/middleware/rate_limit.py`、`backend/app/core/config.py`、`docs/SCALE.md`
- 标准化备份脚本：`backups/backup_run.py`、`backups/restore_run.py`

## 备份与恢复（标准化）

### 1) 生成备份

```bash
python tools/backup_run.py
```

产物输出到 `backups/`，命名规则：

- `backups/AIseek-Trae-v1-backup-YYYYMMDD-HHMMSS.tar.gz`
- 同前缀的 `.sha256`、`.manifest.txt`、`.filelist.txt`、`.changes.txt`、`.README.md`

### 2) 恢复备份

```bash
python tools/restore_run.py --archive backups/AIseek-Trae-v1-backup-YYYYMMDD-HHMMSS.tar.gz --dest ./restore-YYYYMMDD-HHMMSS
```

### 3) 远端对象存储与每日定时备份

对象存储上传（S3/R2/MinIO）与 GitHub Actions 每日定时备份说明见：

- `docs/BACKUP.md`

## 扩容蓝图

更完整的扩容/高可用/可观测蓝图与参数说明见：

- `docs/SCALE.md`
