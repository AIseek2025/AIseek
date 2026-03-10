# AIseek 部署复盘报告 - 2026-03-09

**事件**: GitHub Actions 备份上传失败修复  
**日期**: 2026-03-09  
**状态**: ✅ 已解决  
**耗时**: 约 1 小时

---

## 📋 事件概述

GitHub Actions 自动备份任务持续失败，无法将备份文件上传到阿里云 OSS。

---

## 🔍 问题诊断

### 错误现象

```
boto3.exceptions.S3UploadFailedError: Failed to upload /home/runner/work/AIseek/AIseek/backups/AIseek-Trae-v1-backup-20260308-174137.tar.gz to ***/***/AIseek-Trae-v1-backup-20260308-174137.tar.gz: An error occurred (InvalidArgument) when calling the UploadPart operation: aws-chunked encoding is not supported with the specified x-amz-content-sha256 value.
```

### 根本原因

**boto3 SDK 默认使用 `aws-chunked` 编码进行分片上传，但阿里云 OSS 不支持这种编码方式。**

### 尝试的失败方案

1. **修改 S3 客户端配置** - 尝试设置 `addressing_style: 'virtual'` 和 `payload_signing_enabled: False`
   - ❌ 无效，boto3 内部仍然使用 aws-chunked 编码

2. **切换 addressing_style** - 尝试 `path` 样式和 `virtual` 样式
   - ❌ 无效，问题不在寻址方式，而在编码方式

3. **禁用各种高级特性** - 尝试 `use_accelerate_endpoint: False` 等
   - ❌ 无效，boto3 的 S3 Transfer 自动启用分片上传和 chunked 编码

---

## ✅ 最终解决方案

**使用阿里云官方 oss2 SDK 替代 boto3**

### 修改内容

#### 1. 重写备份上传脚本 (`tools/backup_upload_s3.py`)

```python
# 之前 (boto3)
import boto3
s3 = boto3.client("s3", ...)
s3.upload_file(str(p), args.bucket, key)

# 之后 (oss2)
import oss2
auth = oss2.Auth(access_key, secret_key)
bucket = oss2.Bucket(auth, endpoint, bucket_name)
bucket.put_object_from_file(key, str(p))
```

#### 2. 更新依赖安装 (`.github/workflows/backup_daily.yml`)

```yaml
# 之前
pip install boto3

# 之后
pip install oss2
```

#### 3. 更新参数传递 (`tools/backup_daily.py`)

```python
# 之前
"--region", os.getenv("AWS_REGION", ...)

# 之后
"--access_key_id", os.getenv("AWS_ACCESS_KEY_ID", ""),
"--access_key_secret", os.getenv("AWS_SECRET_ACCESS_KEY", ""),
```

---

## 📚 备份上传兼容性章节

### OSS 场景最佳实践

**核心原则**: **阿里云 OSS 场景必须使用 oss2 SDK，不要使用 boto3**

#### 为什么？

| 特性 | boto3 | oss2 |
|------|-------|------|
| 分片上传编码 | aws-chunked (OSS 不支持) | 标准编码 (OSS 支持) |
| 寻址方式 | path/virtual 配置复杂 | 自动适配 |
| 错误处理 | S3 兼容层可能有差异 | 原生 OSS API |
| 性能 | 需要额外配置 | 针对 OSS 优化 |

#### 正确示例

```python
# ✅ 正确：使用 oss2
import oss2

auth = oss2.Auth(access_key_id, access_key_secret)
bucket = oss2.Bucket(auth, endpoint_url, bucket_name)
bucket.put_object_from_file(key, file_path)
```

```python
# ❌ 错误：使用 boto3 (会触发 aws-chunked 编码)
import boto3

s3 = boto3.client("s3", endpoint_url=endpoint_url, ...)
s3.upload_file(file_path, bucket_name, key)  # 会失败！
```

#### 依赖配置

```yaml
# .github/workflows/backup.yml
- name: Install deps
  run: |
    pip install oss2
```

---

## 🔧 上传后校验（新增）

在 workflow 中增加上传后校验步骤，防止"任务成功但文件无效"：

```yaml
- name: Verify backup upload
  run: |
    python -c "
    import oss2
    import os
    import sys
    
    auth = oss2.Auth(
        os.getenv('AWS_ACCESS_KEY_ID'),
        os.getenv('AWS_SECRET_ACCESS_KEY')
    )
    bucket = oss2.Bucket(
        auth,
        os.getenv('BACKUP_S3_ENDPOINT_URL'),
        os.getenv('BACKUP_S3_BUCKET')
    )
    
    # 获取最新备份文件名
    prefix = os.getenv('BACKUP_S3_PREFIX', 'aiseek-backups')
    result = bucket.list_objects(prefix=prefix + '/', max_keys=1)
    
    if not result.object_list:
        print('❌ No backup objects found')
        sys.exit(1)
    
    latest = result.object_list[0]
    print(f'✅ Found backup: {latest.key}')
    print(f'   Size: {latest.size} bytes')
    print(f'   Last Modified: {latest.last_modified}')
    
    # 校验大小 > 0
    if latest.size <= 0:
        print('❌ Backup file size is 0 or negative')
        sys.exit(1)
    
    # 校验可读性 (获取 metadata)
    meta = bucket.get_object_meta(latest.key)
    print(f'   Content-Type: {meta.content_type}')
    print(f'   ETag: {meta.etag}')
    
    print('✅ Backup verification passed')
    "
```

---

## 📊 修复效果

### 修复前
- ❌ 备份任务持续失败
- ❌ 无法上传到 OSS
- ❌ 错误信息不明确

### 修复后
- ✅ 备份任务成功
- ✅ 文件正常上传到 OSS
- ✅ 可以在阿里云 OSS 控制台查看备份文件

---

## ✅ 附录：AI 创作“0秒”问题最终验收（生产）

### 验收结论
- AI 链路已恢复，`media_assets` 已落库，且时长为正常值（非 0 秒）
- 关键样本时长：`43s / 44s / 63s`
- 新任务已可从 `processing` 推进到 `done`

### 验收 SQL 结果摘要（节选）

`media_assets`（节选）：

| id | post_id | duration | mp4_url | hls_url |
|---:|---:|---:|---|---|
| 6 | 22 | 63 | `/static/worker_media/videos/b60a...bbb5.mp4` | `/static/worker_media/hls/b60a...5c93/master.m3u8` |
| 5 | 1 | 44 | `/static/worker_media/videos/15ce...ad9f.mp4` | `/static/worker_media/hls/15ce...71fd/master.m3u8` |
| 4 | 23 | 43 | `/static/worker_media/videos/afb3...6737.mp4` | `/static/worker_media/hls/afb3...9b9f/master.m3u8` |
| 3 | 16 | 44 | `/static/worker_media/videos/9d5c...e398.mp4` | `/static/worker_media/hls/9d5c...cc44/master.m3u8` |

`ai_jobs`（节选）：

| job_id | status | stage |
|---|---|---|
| afb314cd-8129-448b-bb88-74c4d57b3214 | done | done |
| b60a252c-65aa-4855-8ae1-f91b1acf9562 | done | done |
| 9d5cbfe5-d11d-4a32-af6d-ebf6cb0a3b4c | done | done |
| 15ce20c4-d794-4bd2-ba2d-2a415ff5b01f | done | done |

### 说明
- 历史“卡 processing”任务已按标准流程收口
- 当前生产以发布包目录运行（非 git 工作副本），后续更新按发布包流程执行

---

## 🎯 经验教训

### 1. SDK 选择很重要
- **S3 兼容存储 ≠ 完全兼容 S3**
- 阿里云 OSS 虽然支持 S3 API，但有自己的一些限制
- 优先使用云厂商官方 SDK

### 2. 错误信息要仔细分析
- `aws-chunked encoding is not supported` 明确指向编码问题
- 不应该反复尝试修改配置，而应该更换 SDK

### 3. 上传后校验很重要
- 任务成功 ≠ 文件有效
- 需要校验：对象存在、大小>0、metadata 可读

---

## 📝 相关文档

- [备份上传脚本](../tools/backup_upload_s3.py)
- [备份工作流](../.github/workflows/backup_daily.yml)
- [备份文档](./BACKUP.md)
- [卡任务清理 Runbook](./AI_STUCK_TASK_CLEANUP_RUNBOOK.md)

---

**最后更新**: 2026-03-09（含 AI 0秒验收附录）  
**状态**: ✅ 已解决
