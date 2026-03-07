# Deployment Guide

## Prerequisites
- Python 3.10+
- FFmpeg (with `h264_videotoolbox` for Mac, or `libx264` for Linux)
- Cloudflare R2 Account (Optional but recommended)

## Installation

1. Run the setup script:
   ```bash
   ./scripts/setup.sh
   ```

2. Configure Environment:
   ```bash
   cp .env.example .env
   # Edit .env with your keys
   ```

3. Prepare Assets:
   ```bash
   cd worker/assets
   ./create_placeholder.sh
   # (Optional) Add mp3 files to worker/assets/bgm/
   ```

## Running (Local)

推荐使用 Docker 编排（见下方）。如果需要本地方式运行：

1. Start Backend (Terminal 1):
   ```bash
   PYTHONPATH=backend ./.venv/bin/python backend/app/main.py --port 5002
   ```

2. Start Redis (Terminal 2, optional but recommended for async jobs):
   ```bash
   docker run --rm -p 6379:6379 redis:7-alpine
   ```

3. Start Workers (Terminal 3/4):
   ```bash
   cd worker
   celery -A app.worker.celery_app worker --loglevel=info -Q ai
   celery -A app.worker.celery_app worker --loglevel=info -Q transcode
   ```

4. Access:
   - Web/UI + API: http://localhost:5002

## 启动前自检（迁移/索引）（生产建议）

当启用 Postgres 与 Elasticsearch 时，推荐在应用进程启动前执行一次“迁移 + ES alias/重建”的自检脚本，避免多实例并发启动时出现迁移竞态、或 ES alias 未就绪导致的搜索异常。

```bash
PYTHONPATH=backend python backend/scripts/deploy_bootstrap.py --migrate
```

如需确保 ES alias 存在（不做重建）：

```bash
PYTHONPATH=backend python backend/scripts/deploy_bootstrap.py --migrate --es
```

如需执行一次 ES 重建（离线/发布窗口执行，避免与线上写入竞争）：

```bash
PYTHONPATH=backend python backend/scripts/deploy_bootstrap.py --migrate --es --reindex --reindex-limit 5000
```

## 静态资源发布与回滚（生产建议）
系统支持“内容哈希文件名 + manifest 指针”的静态资源交付方式，用于避免浏览器/CDN 缓存导致的脚本错配与前端静默卡死。

- 构建静态资源（生成 dist/r/<release> 与 manifest.<release>.json，并切换 manifest.current.json）：

```bash
python backend/scripts/build_static_assets.py
```

- 回滚到某个 release（仅切换 manifest.current.json 指针，静态资源可强缓存不变）：

```bash
python backend/scripts/activate_static_assets.py <release_id>
```

- 缓存头策略：
  - HTML（/、/studio、/admin）：no-store
  - /static/dist/r/**：immutable
  - /static/dist/manifest*.json：no-store

## Running (Docker)
单机最简（推荐，无需运维专家）：
- `docker-compose.ops-simple.yml`：Postgres(单实例) + Redis(单节点) + backend + Nginx
  - Nginx 直出 /static（需要挂载 ./backend/static → /srv/aiseek/static）
  - /static/dist/r/**：immutable；/static/dist/manifest*：no-store；/static/uploads 与 /static/worker_media：短缓存
- 阿里云生产模板：`deploy/aliyun/docker-compose.prod.yml`（配套 `deploy/aliyun/.env.prod.example` 与 `deploy/aliyun/README.md`）

单机开发编排（可选，组件更多）：
- `docker-compose-simple.yml`：Postgres + Redis + ES + backend + worker

多实例+负载均衡演示：
- `docker-compose.scale.yml`：3 个 backend 实例 + Nginx 负载均衡
- 入口：http://localhost:5001

100万-1亿阶段（最小运维、队列隔离）：
- `docker-compose.stage2.yml`：backend + backend_celery + worker_ai + worker_transcode + Postgres + Redis + ES
- [OPS_STAGE2.md](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/docs/OPS_STAGE2.md)
- [BLUEPRINT.md](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/docs/BLUEPRINT.md)

更多规模化设计与参数说明（按瓶颈演进，避免过度工程化）：
- [SCALE.md](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/docs/SCALE.md)

## 网关与流量治理（生产建议）

推荐采用“边缘（Nginx）+应用（Middleware）”的双层保护：

- 边缘层（Nginx）：
  - 统一生成/透传 `X-Request-Id`，并透传 `X-Session-Id`、`X-Canary`、`X-Real-IP`
  - 对高风险接口（搜索）配置专用限流，避免请求风暴打穿应用层与 ES/DB
  - 配置位置：`deploy/nginx/nginx.conf`、`deploy/nginx/simple.conf`
- 应用层：
  - 写鉴权、搜索限流与成本预算（令牌桶）、ES 熔断降级、外呼统一超时/重试/熔断
  - `/metrics` 输出外呼熔断状态（open/fail/open_until）与关键业务指标
