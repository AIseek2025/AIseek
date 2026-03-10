# 上线验收截图模板（交付留档）

## 1) 基本信息
- 项目：
- 环境：生产 / 预发
- 验收人：
- 验收时间：
- 版本标识（包名/镜像Tag）：

## 2) 必传截图清单

### A. 服务健康
- [ ] `docker compose ps` 全服务 `Up/Healthy`
- 截图文件：`01-services-health.png`

### B. AI 任务状态
- [ ] `ai_jobs` 最近 10 条（`status/stage/error`）
- 截图文件：`02-ai-jobs-status.png`

### C. 媒体资产落库
- [ ] `media_assets` 最近 10 条（`duration/mp4_url/hls_url`）
- 截图文件：`03-media-assets.png`

### D. 帖子时长与视频地址
- [ ] `posts` 最近 10 条（`status/duration/video_url/ai_job_id`）
- 截图文件：`04-posts-duration.png`

### E. 前端页面效果
- [ ] AI 视频卡片显示非 0 秒
- [ ] 视频可播放、封面可展示
- 截图文件：`05-frontend-feed.png`

## 3) 推荐验收 SQL（直接复制）
```bash
docker compose --env-file /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/.env.prod -f /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/docker-compose.prod.yml exec -T db psql -U aiseek -d aiseek_prod -P pager=off -c "select id,status,stage,left(coalesce(error,''),120) err_short,updated_at from ai_jobs order by created_at desc limit 10;"

docker compose --env-file /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/.env.prod -f /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/docker-compose.prod.yml exec -T db psql -U aiseek -d aiseek_prod -P pager=off -c "select id,post_id,duration,mp4_url,hls_url,created_at from media_assets order by id desc limit 10;"

docker compose --env-file /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/.env.prod -f /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/docker-compose.prod.yml exec -T db psql -U aiseek -d aiseek_prod -P pager=off -c "select id,status,duration,video_url,ai_job_id,created_at from posts where ai_job_id is not null order by id desc limit 10;"
```

## 4) 验收结论
- [ ] 通过
- [ ] 不通过

不通过原因：
- 

处理人：
- 

计划完成时间：
- 

## 5) 附件索引
- 01-services-health.png
- 02-ai-jobs-status.png
- 03-media-assets.png
- 04-posts-duration.png
- 05-frontend-feed.png
