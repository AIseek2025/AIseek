# Backup & Restore

本项目提供“本地快照 + 远端对象存储 + 每日定时任务”的标准化备份体系：

- 本地快照：生成 `backups/AIseek-Trae-v1-backup-YYYYMMDD-HHMMSS.*` 一组文件
- 远端同步：上传到 S3 兼容对象存储（AWS S3 / Cloudflare R2 / MinIO）
- 定时备份：GitHub Actions 每日触发，每次生成新文件，不覆盖历史

## 生成本地备份

```bash
python tools/backup_run.py
```

产物：

- `backups/AIseek-Trae-v1-backup-YYYYMMDD-HHMMSS.tar.gz`
- `backups/AIseek-Trae-v1-backup-YYYYMMDD-HHMMSS.tar.gz.sha256`
- `backups/AIseek-Trae-v1-backup-YYYYMMDD-HHMMSS.manifest.txt`
- `backups/AIseek-Trae-v1-backup-YYYYMMDD-HHMMSS.filelist.txt`
- `backups/AIseek-Trae-v1-backup-YYYYMMDD-HHMMSS.changes.txt`
- `backups/AIseek-Trae-v1-backup-YYYYMMDD-HHMMSS.README.md`

默认排除（避免递归与缓存/临时文件膨胀）：`.git/`、`backups/`、`.venv/`、`__pycache__`、`*.pyc`、`.DS_Store`、`backend/gunicorn.ctl`。

## 恢复备份

```bash
python tools/restore_run.py --archive backups/AIseek-Trae-v1-backup-YYYYMMDD-HHMMSS.tar.gz --dest ./restore-YYYYMMDD-HHMMSS
```

默认会校验同名 `*.tar.gz.sha256`（存在时）；并对 tar 成员路径做安全校验，避免目录穿越。

## 上传到对象存储（S3 兼容）

```bash
export BACKUP_S3_BUCKET="your-bucket"
export BACKUP_S3_PREFIX="aiseek-backups"
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_DEFAULT_REGION="auto"
export BACKUP_S3_ENDPOINT_URL="https://<account-id>.r2.cloudflarestorage.com"

python tools/backup_upload_s3.py --dir backups --keep_last_n 30
```

上传内容为同一备份前缀的整组文件（tar/sha256/manifest/filelist/changes/README）。

## 每日定时备份（GitHub Actions）

仓库包含每日定时任务工作流：

- `.github/workflows/backup_daily.yml`

需要在仓库 Secrets 配置：

- `BACKUP_S3_BUCKET`
- `BACKUP_S3_PREFIX`（可选）
- `BACKUP_S3_ENDPOINT_URL`（可选；R2/MinIO 需要）
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_DEFAULT_REGION`（可选；R2 可设 `auto`）

可选 Secrets（保留策略）：

- `BACKUP_REMOTE_KEEP_LAST_N`（默认 30）

每次任务会生成新的时间戳备份文件，不会覆盖前一日备份；超出保留数量时会按时间从旧到新删除远端最旧的一批。

