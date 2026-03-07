# 100万-1亿量级：最小运维架构（AIseek）

## 目标
- 运维尽量简单：不要求 K8s/专职运维人员即可上线与扩容
- 性能优先：短视频播放快、媒体存储成本可控、AI 渲染计算可隔离扩展
- 可演进：当数据证明需要时再升级（读写分离、Redis HA、分区等）

## 推荐组件（阶段 2）
- Web：FastAPI（无状态，多进程/多实例扩展）
- DB：Postgres（单实例起步；压力上来再上只读副本）
- Cache：Redis 单节点（用于缓存/限流/幂等/队列 broker）
- 队列：Celery + Redis（按队列隔离 AI 与转码）
- 存储：对象存储（R2/S3）+ CDN（视频/图片走 CDN，源站只提供 API）
- 反代：Nginx（TLS/连接复用/限流可按需）

## 关键工程落地点（已实现）
- Worker 回调统一到 backend：`/api/v1/posts/callback`，并使用 `x-worker-secret` 鉴权
- 上传视频状态机：上传后保持 `processing`，转码完成回调后变为 `done`
- 转码产物升级为 HLS 多码率（VOD）：上传后生成 `master.m3u8 + 多档位分片` 并上传对象存储；同时保留 MP4 作为回退源
- 首帧体验增强：生成 `cover_url`（webp/jpg）与 `duration/video_width/video_height` 元信息，前端用 poster 与预热减少体感等待
- 封面策略更接近短视频平台：选帧时避开过暗/低对比/大面积纯色帧，并降低中心/底部高边缘密度（字幕/大字）帧权重；封面固定裁切为 720x1280 以提升 CDN 命中与解码效率
- AI 创建限流：按 user_id 的 token bucket（可调）
- 指标去高基数：Prometheus path 使用路由模板路径，避免 label 爆炸
- CI：无额外依赖的 smoke 测试与静态审计

## 一键编排（推荐）
使用：
- [docker-compose.stage2.yml](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/docker-compose.stage2.yml)

它做了两件关键事：
1) Web 与后台 Celery 分离（web 不跑重任务）
2) Worker 队列隔离：`ai` 与 `transcode` 分开，避免 AI 任务挤压影响上传转码

## 扩容方式（不需要复杂运维）
### Web 扩容
- 优先把 backend 的 gunicorn worker 数拉起来（单机）
- 再考虑多机横向扩容（Nginx upstream）

### AI 渲染扩容
- 直接增加 `worker_ai` 实例数或并发（独立扩，不影响 Web/转码）

### 转码扩容
- 直接增加 `worker_transcode` 实例数或并发（独立扩，不影响 AI）

## 什么时候升级哪些技术（用数据说话）
- Postgres 只读副本：读 QPS 持续高、主库 CPU > 70%
- Redis HA（哨兵/托管）：Redis 成为单点、或业务必须高可用
- Postgres 分区：单表行数过大、热点查询明显变慢且索引已优化
- Redis Cluster：单节点内存 > 80% 或 QPS 持续很高且无法拆分 key
- K8s：服务拆分到 10+ 且需要弹性伸缩/自动化运维时再上

## 最小监控清单
- API：QPS、p95/p99、5xx、慢查询
- DB：CPU、连接数、慢查询、索引命中率
- Redis：内存、QPS、keyspace hits/misses、阻塞时间
- 队列：积压长度、任务失败率、重试次数
- 存储/CDN：回源率、带宽、命中率

## 播放策略（秒开体验）
- 后端会同时返回 `hls_url`（m3u8）与 `mp4_url`（回退源）
- 前端默认优先 `hls_url`：
  - Safari/Apple 平台走原生 HLS
  - 其他浏览器尝试加载 hls.js（CDN），失败则自动回退 mp4
- 前端在内容“即将进入视口”时预取 poster 并预热 m3u8（master + v2）以降低首帧抖动

## CDN 建议（VOD）
- 由于产物 URL 带版本号目录（可视为不可变），上传时可设置 `Cache-Control: public, max-age=31536000, immutable`
- 建议在对象存储/CDN 侧开启 Range 支持（m4s/mp4 需要），并配置 CORS 允许前端域名 GET m3u8/m4s/mp4
