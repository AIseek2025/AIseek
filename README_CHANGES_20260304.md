# 近期修改说明（相对 20260302-003150 备份）

本文档用于在 “AIseek-Trae-v1-backup-20260302-003150” 的基础上，汇总最近新增/修改的功能点，并列出主要改动文件与作用说明，便于审计、回滚与二次开发。

## 总览

最近改动聚焦在把项目从“原型可用”推进到“可扩展基础能力完整”的形态，核心目标：

- 高并发可用性：写鉴权全覆盖、搜索降级与熔断、搜索限流预算
- 高性能：静态直出与缓存分层、搜索分页、热点缓存、Postgres 搜索索引
- 高可用/可运维：ES alias 重建与回滚、OPS 接口、指标暴露
- 一致性与体验：写后短期粘主、搜索页加载更多与请求整形
- 交付与治理：标准化备份产物与备份/恢复脚本

## 功能改动与文件清单

### 1) Nginx 静态直出 + 分层缓存头 + volume 挂载

- `deploy/nginx/nginx.conf`：增加 `/static/**` 直出、按路径细分 Cache-Control（immutable/no-store/短缓存），并保持对 API 的反代。
- `deploy/nginx/simple.conf`：简化版同样策略，用于单机/演示环境。
- `docker-compose.ops-simple.yml`：补齐静态目录只读挂载，确保 Nginx `try_files` 命中。
- `docs/DEPLOY.md`：更新部署说明与静态交付策略要点。

### 2) 写请求鉴权全覆盖 + user_id 越权收口

- `backend/app/middleware/auth_required.py`
  - `/api/v1/**` 的 `POST/PUT/DELETE` 强制 Bearer
  - 对 JSON body 的 `user_id` 做强一致校验（与 token user_id 必须一致）
- `backend/app/api/v1/endpoints/posts.py`
  - `/posts/create` 以 token 用户为准创建，兼容旧入参但不再信任客户端 user_id

### 3) 读写一致性（写后短期粘主）

- `backend/app/main.py`：对写请求成功响应写入短 TTL cookie（`aiseek_rw`），用于提示后续读走主库。
- `backend/app/api/deps.py`：`get_read_db` 读取 cookie，短期选择主库（否则读库），缓解主从延迟造成的写后读不一致。

### 4) Elasticsearch 工程化（alias/bulk/重建/回滚/保留）

- `backend/app/services/search_service.py`
  - `ensure_posts_alias`：保障 alias 存在
  - `rebuild_posts_index`：新建物理索引 + streaming_bulk 写入 + alias 原子切换 + 切换校验 + 回滚逻辑 + 清理旧索引
  - ES 熔断降级（cooldown）+ ES 调用指标（op_total/latency）
- `backend/app/tasks/search_index.py`
  - `rebuild_posts_index_job`：Redis 分布式锁防并发重建；进度写入缓存；支持取消；状态落库
- `backend/app/api/v1/endpoints/ops.py`
  - `/ops/es/reindex` 触发重建
  - `/ops/es/reindex/status` 查询进度
  - `/ops/es/reindex/cancel` 取消重建
  - `/ops/es/reindex/jobs` 查看历史任务
- `backend/app/models/all_models.py`：新增 `ESReindexJob` 模型用于审计与追溯。
- `backend/alembic/versions/0021_es_reindex_jobs.py`：新增 `es_reindex_jobs` 表迁移。
- `backend/app/core/config.py`：新增 ES 重建参数（分片/副本/bulk/保留数量/熔断窗口等）。

### 5) 搜索接口升级（分页游标 + 缓存 + ES/DB 统一）

- `backend/app/services/search_service.py`
  - `search_post_ids`：统一 ES/DB 取 id 列表并返回 next_cursor
  - DB 回退支持 cursor（created_at,id）；ES 使用 search_after 游标
  - 首屏热点 query 短 TTL 缓存（避免击穿）
- `backend/app/api/v1/endpoints/posts.py`
  - `/posts/search` 支持 `limit/cursor` 并返回 `x-next-cursor`
  - 首屏结果层缓存（items + next_cursor）
- `backend/app/api/v1/endpoints/users.py`
  - `/users/search-user` 支持 `limit/cursor` 并返回 `x-next-cursor`
  - 首屏结果层缓存（items + next_cursor）
- `backend/static/js/app/search.js`
  - 搜索触发去抖
  - 请求去重/取消/短 TTL 复用
  - “加载更多”基于 `x-next-cursor` 的渐进追加渲染（避免一次性渲染与一次性大返回）

### 6) Postgres 搜索索引（避免 contains 全表扫）

- `backend/alembic/versions/0022_search_pg_indexes.py`
  - `pg_trgm` 扩展
  - `posts` 全文检索 `to_tsvector` GIN 索引
  - `users.nickname/username`、`posts.category` trgm GIN 索引
- `backend/app/services/search_service.py`
  - Postgres 下 DB 回退优先全文检索（tsvector/tsquery）+ ILIKE（命中 trgm）
  - 非 Postgres 环境保持 SQLite contains 逻辑兼容
- `backend/app/api/v1/endpoints/users.py`
  - Postgres 下用户模糊匹配使用 ILIKE（命中 trgm）

### 7) 搜索抗请求风暴（限流 + 成本预算）

- `backend/app/middleware/rate_limit.py`
  - 将 `/posts/search`、`/users/search-user` 纳入限流
  - 固定窗口限流（匿名/登录用户不同阈值）
  - Redis 可用时启用令牌桶成本预算（按 query/limit 估算 cost）
  - 无 `x-forwarded-for` 时回落 `request.client.host`，防止直连绕过
- `backend/app/core/config.py`：新增搜索限流/预算配置项默认值。
- `docs/SCALE.md`：补齐搜索限流/预算策略与配置项说明。

### 8) 标准化备份与恢复脚本

- `tools/backup_run.py`
  - 在 `backups/` 下生成带时间戳的备份包与辅助文件：sha256、manifest、filelist、changes、README
  - 默认排除 `.git/`、`backups/`、`.venv/`、`__pycache__`、`*.pyc`、`.DS_Store`、`backend/gunicorn.ctl`
- `tools/restore_run.py`
  - 支持 sha256 校验与安全解压（防目录穿越），推荐恢复到新目录
- `tools/backup_upload_s3.py`
  - 上传备份到 S3 兼容对象存储（AWS S3 / R2 / MinIO），并支持远端保留最近 N 个备份
- `tools/backup_prune.py`
  - 本地保留最近 N 个备份（超出即删除最旧的一批，不会覆盖前一日备份）
- `tools/backup_daily.py`
  - 组合执行：生成备份 → 上传对象存储（可选）→ 本地保留
- `.github/workflows/backup_daily.yml`
  - GitHub Actions 每日定时任务：每次生成新的时间戳备份文件并上传对象存储（不覆盖历史）
- `docs/BACKUP.md`
  - 备份/恢复/对象存储/CI 凭据注入说明

## 备注：完整变更文件列表

 备份产物按时间戳生成，位于 `backups/`：
  - `backups/AIseek-Trae-v1-backup-YYYYMMDD-HHMMSS.tar.gz`
  - `backups/AIseek-Trae-v1-backup-YYYYMMDD-HHMMSS.manifest.txt`
  - `backups/AIseek-Trae-v1-backup-YYYYMMDD-HHMMSS.changes.txt`
  - `backups/AIseek-Trae-v1-backup-YYYYMMDD-HHMMSS.filelist.txt`
