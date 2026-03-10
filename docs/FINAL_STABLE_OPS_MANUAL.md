# 最终稳定版操作手册 (Final Stable Version Operation Manual)

本手册汇总了 AIseek 项目在生产环境（100万-1亿量级架构）下的核心运维操作，特别是针对 AI 任务卡顿、数据库故障及前端显示问题的标准处理流程。

---

## 1. 历史卡任务清理标准流程

当出现 AI 任务长时间停留在 `queued/processing` 状态，或者任务已完成但前端显示“0秒”/无播放地址时，请按以下流程处理。

### 1.1 核心原则
- **先保可用**：优先恢复新任务的派发与执行。
- **后清理历史**：在确认系统恢复后，再批量重置或标记历史卡顿任务。
- **全链路验证**：操作后必须验证数据库状态、文件存储与前端表现。

### 1.2 一键清理命令 (推荐)

我们提供了一个自动化脚本 `scripts/ai_task_recover.sh`，可一键完成：
1. 重置卡住的 `processing/queued` 任务状态。
2. 重启 worker 容器以清除僵尸进程。
3. 触发后端重新派发任务。

**执行命令：**

```bash
# 进入项目根目录
cd /opt/aiseek/AIseek-Trae-v1

# 执行全量恢复（需指定部署目录，例如 /opt/aiseek/AIseek-Trae-v1/deploy/aliyun）
bash scripts/ai_task_recover.sh /opt/aiseek/AIseek-Trae-v1/deploy/aliyun all
```

**仅诊断不执行（Dry Run）：**

```bash
bash scripts/ai_task_recover.sh /opt/aiseek/AIseek-Trae-v1/deploy/aliyun all readonly
```

### 1.3 判定标准 (Acceptance Criteria)

执行完清理操作后，必须满足以下所有条件才算“清理成功”：

1.  **任务状态流转正常**：
    -   `ai_jobs` 表中不再有创建时间超过 30 分钟仍处于 `queued` 或 `processing` 的任务。
    -   新提交的任务能正常从 `queued` -> `processing` -> `done`。

2.  **产物落库完整**：
    -   `media_assets` 表中有新增记录。
    -   `posts` 表中的 `video_url` 字段非空。
    -   `posts` 表中的 `duration` 字段大于 0（通常为 40s-60s）。

3.  **前端播放正常**：
    -   在浏览器中访问视频详情页，视频能正常播放。
    -   **时长显示正常**（非 `00:00` 或 `NaN`）。

### 1.4 手动验证 SQL

如果脚本执行后仍有疑虑，可运行以下 SQL 进行二次确认：

```bash
# 检查最近 10 条 AI 任务状态
docker compose --env-file /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/.env.prod -f /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/docker-compose.prod.yml exec -T db \
psql -U aiseek -d aiseek_prod -P pager=off -c "
select id, status, stage, left(coalesce(error,''), 50) as err, updated_at 
from ai_jobs 
order by created_at desc 
limit 10;"

# 检查最近 10 条媒体产物时长
docker compose --env-file /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/.env.prod -f /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/docker-compose.prod.yml exec -T db \
psql -U aiseek -d aiseek_prod -P pager=off -c "
select id, post_id, duration, mp4_url 
from media_assets 
order by id desc 
limit 10;"
```

---

## 2. 数据库故障恢复流程 (Disk Full)

当服务器磁盘满（`No space left on device`）导致 PostgreSQL 崩溃并进入死循环（`recovery mode` / `standby.signal`）时：

### 2.1 紧急恢复步骤

1.  **清理磁盘空间**：
    ```bash
    # 清理 Docker 构建缓存
    docker builder prune -f
    
    # 清理旧的容器与镜像
    docker system prune -f
    
    # 清理大日志文件 (例如 worker 或 db 日志)
    truncate -s 0 /var/lib/docker/containers/*/*-json.log
    ```

2.  **解除数据库锁定**：
    如果数据库因为崩溃残留了锁定文件，需手动删除：
    ```bash
    docker compose ... exec -T db sh -c 'rm -f /var/lib/postgresql/data/standby.signal /var/lib/postgresql/data/recovery.signal'
    ```

3.  **重启数据库**：
    ```bash
    docker compose ... restart db
    ```

---

## 3. 前端 HLS 时长显示修复 (0秒问题)

### 3.1 问题现象
HLS (`.m3u8`) 视频在部分浏览器（如 Chrome）中加载时，`video.duration` 可能为 `Infinity` 或 `0`，导致播放器显示 `00:00`。

### 3.2 解决方案
前端代码已打补丁（`player.js`, `search.js`, `floating_player.js`），逻辑如下：
1.  后端在 API 返回中提供准确的 `duration` 字段（从 `media_assets` 表获取）。
2.  前端渲染时将 `duration` 写入 DOM 的 `data-duration` 属性。
3.  播放器初始化时，优先读取 `data-duration` 作为视频总时长，不再完全依赖 `video.duration` 事件。

### 3.3 验证方法
- 强制刷新浏览器（Cmd+Shift+R）。
- 检查视频右下角时长是否显示为具体数值（如 `00:44`）。

---

**文档维护者**: AIseek Ops Team
**最后更新**: 2026-03-09
