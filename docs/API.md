# API Documentation

本项目已合并为单 FastAPI 后端（API + UI），worker 通过回调接口回写状态与媒体信息。回调协议与观测/告警使用说明见 [WORKER_CALLBACK.md](WORKER_CALLBACK.md)。

## Worker API (Port 8000)

### POST /trigger
Submit a job.
- Body: `{"content": "...", "user_id": "...", "job_id": "..."}`
- Auth: Bearer Token (if configured)

### GET /status/{job_id}
Get job status.

### GET /health
System health check.

## Web API (Port 5001)

### POST /api/submit
Submit job from frontend (proxies to worker).

### GET /api/jobs
Get user job history.
