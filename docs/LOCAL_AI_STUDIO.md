# 本地跑通 AI 创作全流程（含视频产物）

目标：在本机不依赖 Cloudflare R2、不依赖外部大模型 Key 的情况下，完整跑通：
提交文稿 → 派发 → worker 生成 MP4/HLS/封面 → 回调落库 → 工作台预览。

## 1. 必要进程

### 1) Redis（broker + 事件/锁）
本地启动 redis-server，监听 6379。

### 2) 后端（FastAPI）
运行后端并监听 5002：
- 工作台入口：`http://localhost:5002/studio`

### 3) Worker（Celery）
启动 Celery worker，订阅 `ai,transcode` 队列。

## 2. 本地覆盖配置（.env.local）

仓库根目录的 `.env.local` 用于覆盖 `.env`（不会破坏 docker 配置）。最小需要：
- `REDIS_URL=redis://localhost:6379/0`
- `CELERY_BROKER_URL=redis://localhost:6379/1`
- `CELERY_RESULT_BACKEND=redis://localhost:6379/1`
- `WEB_URL=http://127.0.0.1:5002`

本地跑通推荐：
- `DEEPSEEK_API_KEY=` 留空（自动走本地脚本降级，仍能生成视频）
- `R2_*` 清空（让 worker 走本地静态目录输出模式）

## 3. 本地静态产物输出（无 R2）

当 R2 未配置时：
- worker 会把 MP4/HLS/封面复制到 `backend/static/worker_media/...`
- 回调给后端的 URL 形如：`/static/worker_media/...`

## 4. 占位视频

首次本地运行前，确保占位视频存在：
- `worker/assets/bg_placeholder.mp4`

若没有，可执行 `worker/assets/create_placeholder.sh` 生成（不依赖 drawtext）。

