# Worker Callback & Observability

本文件描述 worker → backend 的回调协议（状态/进度/脚本写入）、幂等与防重放机制，以及管理员侧的指标/样例/告警接口与后台页面使用方式。

## 回调入口

### POST /api/v1/posts/callback

用途：worker 上报 job/post 的状态推进、媒体地址、进度、阶段信息，以及（在允许阶段）写入 draft_json / assistant_message。

请求 Body（关键字段）：
- job_id: string（必填）
- post_id: int（可选；不填时后端会从 job 关联或用 job_id 推断）
- status: queued | processing | done | failed | cancelled
- progress: 0-100（可选；后端会做单调性保护）
- stage: string（可选；后端会做单调性保护）
- stage_message: string（可选）
- draft_json: any（可选；仅允许特定 stage 写入）
- assistant_message: string（可选；仅允许特定 stage 写入）
- no_post_status: bool（可选；true 时仅更新 job，不改 post.status）
- video_url / hls_url / mp4_url / cover_url / duration / video_width / video_height / media_version（可选）
- error: string（可选；failed 时可写入）

返回值：
- {"status":"ok"} 或 {"status":"ok","dup":true} 或 {"status":"ok","ignored":true,"reason":...}

## 认证与防重放

后端支持两种模式（二选一）：

### 1) 签名模式（推荐）
请求头：
- x-worker-ts: unix timestamp（秒）
- x-worker-sig: hex sha256 hmac

签名计算：
- raw = 原始 HTTP body（bytes）
- msg = f"{ts}.{raw}"
- sig = HMAC-SHA256(WORKER_SECRET, msg)

校验：
- ts 必须在 WORKER_SIG_WINDOW_SEC 窗口内
- sig 必须匹配

### 2) 共享密钥模式（兼容）
请求头：
- x-worker-secret: WORKER_SECRET

可通过 WORKER_SIGNED_CALLBACK_REQUIRED 强制要求签名模式。

### 幂等去重（dedupe）
后端会对同一个 job 的回调进行去重：
- 优先用 (x-worker-ts, x-worker-sig) 作为 dedupe key
- 否则退化为 body 的 sha256
- TTL = WORKER_SIG_WINDOW_SEC + 120

命中去重时返回 {"dup": true}。

## 状态机与单调性策略

### 状态推进（避免回退）
后端会阻止状态回退覆盖（例如 done 被旧回调改回 processing）。
同时允许一种重要的“纠错路径”：
- 当 create_post 的任务派发失败导致 post/job 先进入 failed，后续仍允许通过回调推进到 processing/done（便于重试与人工补偿）。

被阻止的回调会返回 ignored + reason（并进入指标统计/样例采集）。

### progress 单调性
- progress 只允许不下降；乱序回调不会覆盖更大的进度值。

### stage 单调性
- stage 会基于 stage_rank 进行比较；低 rank 的回调不会覆盖高 rank。
- 当 progress/顺序信息足够时，允许同 rank 或更高 rank 推进。

## 写入白名单（安全收口）

### draft_json 写入
仅在以下 stage 才会写入 job.draft_json 并记录草稿版本：
- deepseek
- draft_loaded
- chat_ai_done

### assistant_message 写入
仅在以下 stage 才会入库（AIJobMessage）：
- chat_ai_done

worker 侧在发送前也会按同一白名单剔除不合规字段，降低异常写入面。

## Stage 常量（双端一致）

stage rank 与写入白名单在双端保持一致：
- backend: backend/app/core/ai_stages.py
- worker: worker/app/core/ai_stages.py

## 指标 / 样例 / 告警（管理员）

这些接口需要管理员（is_superuser）鉴权。

### GET /api/v1/posts/admin/metrics/worker-callback
返回近 N 天的指标汇总与时序：
- totals: 汇总计数
- series: 每日计数
- storage: redis | local（当前指标存储模式）

主要字段：
- dup
- ignored_job_status_regress
- ignored_post_status_regress
- progress_regress

### GET /api/v1/posts/admin/metrics/worker-callback/samples
返回回调样例（仅记录 dup/ignored/progress_regress 等异常路径）：
- items: [{ts, kind, payload, ...}]
- storage: redis | local

### GET /api/v1/posts/admin/metrics/worker-callback/alerts
返回阈值告警（当日首次跨越黄/红阈值会记录）：
- items: [{id, day, ts, level, key, value, threshold, payload, ack}]
- storage: redis | local

筛选：
- include_acked=false 仅返回未确认告警

### POST /api/v1/posts/admin/metrics/worker-callback/alerts/{day}/{alert_id}/ack
确认单条告警。

### POST /api/v1/posts/admin/metrics/worker-callback/alerts/{day}/ack_all
确认某天所有告警。

### POST /api/v1/posts/admin/metrics/worker-callback/alerts/ack_batch
批量确认（用于“确认当前筛选结果”）。

### GET /api/v1/posts/admin/metrics/worker-callback/thresholds
读取服务端阈值（多管理员一致）：
- thresholds: {dup/ij/ip/pr: {y,r}}
- storage: redis | local

### POST /api/v1/posts/admin/metrics/worker-callback/thresholds
保存服务端阈值（带 clamp 与 r>=y 校验）。

## 后台页面（/admin）

系统设置 → Worker 回调健康度：
- 指标存储模式展示：Redis / 本地降级
- 阈值设置：本地阈值（浏览器）与“保存阈值到服务器”
- 告警列表：支持只看未确认、单条确认、确认今日全部、确认当前筛选、导出告警 JSON
- 样例列表：支持导出样例 JSON
