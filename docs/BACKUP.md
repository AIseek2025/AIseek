# AIseek 备份系统文档

**最后更新**: 2026-03-09  
**状态**: ✅ 运行正常

---

## 📋 概述

AIseek 备份系统包含三个部分：

1. **本地备份** - 创建备份文件 (`tools/backup_run.py`)
2. **远程备份** - 上传到阿里云 OSS (`tools/backup_upload_s3.py`)
3. **备份清理** - 清理旧备份 (`tools/backup_prune.py`)

---

## 🚀 快速开始

### 手动执行备份

```bash
cd /Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1

# 执行完整备份（本地 + 远程）
BACKUP_REQUIRE_REMOTE=1 python tools/backup_daily.py
```

### 自动备份（GitHub Actions）

每天 UTC 2:30（北京时间 10:30）自动执行：

```yaml
# .github/workflows/backup_daily.yml
on:
  workflow_dispatch:
  schedule:
    - cron: "30 2 * * *"
```

---

## ☁️ 阿里云 OSS 配置

### 前置条件

1. **开通阿里云 OSS 服务**
   - 访问：https://www.aliyun.com/product/oss
   - 点击"立即开通"

2. **创建存储桶**
   - 访问：https://oss.console.aliyun.com
   - 创建 Bucket，名称：`aiseek-backups`
   - 地域：选择离服务器最近的（如香港、深圳）

3. **配置 AccessKey**
   - 访问：https://ram.console.aliyun.com
   - 创建 AccessKey 或使用现有的
   - 确保有 `AliyunOSSFullAccess` 权限

4. **配置 GitHub Secrets**
   ```bash
   gh secret set BACKUP_S3_BUCKET -b "aiseek-backups"
   gh secret set BACKUP_S3_PREFIX -b "aiseek-backups"
   gh secret set BACKUP_S3_ENDPOINT_URL -b "https://oss-cn-hongkong.aliyuncs.com"
   gh secret set AWS_ACCESS_KEY_ID -b "你的 AccessKeyID"
   gh secret set AWS_SECRET_ACCESS_KEY -b "你的 AccessKeySecret"
   ```

---

## ⚠️ 重要：OSS 场景必须使用 oss2 SDK

### 为什么不用 boto3？

**boto3 默认使用 `aws-chunked` 编码进行分片上传，阿里云 OSS 不支持这种编码方式。**

错误信息：
```
boto3.exceptions.S3UploadFailedError: 
An error occurred (InvalidArgument) when calling the UploadPart operation: 
aws-chunked encoding is not supported with the specified x-amz-content-sha256 value.
```

### 正确做法

**✅ 使用阿里云官方 oss2 SDK**

```python
# tools/backup_upload_s3.py
import oss2

auth = oss2.Auth(access_key_id, access_key_secret)
bucket = oss2.Bucket(auth, endpoint_url, bucket_name)
bucket.put_object_from_file(key, file_path)
```

**❌ 不要使用 boto3**

```python
# 会失败！
import boto3

s3 = boto3.client("s3", endpoint_url=endpoint_url, ...)
s3.upload_file(file_path, bucket_name, key)  # aws-chunked 编码不支持
```

### 依赖配置

```yaml
# .github/workflows/backup_daily.yml
- name: Install deps
  run: |
    pip install oss2  # ✅ 正确
    # pip install boto3  # ❌ 错误
```

---

## 📦 备份文件结构

```
backups/
├── AIseek-Trae-v1-backup-20260309-020000.tar.gz    # 备份文件
├── AIseek-Trae-v1-backup-20260309-020000.tar.gz.sha256  # SHA256 校验和
├── AIseek-Trae-v1-backup-20260309-020000.manifest.txt   # 清单
├── AIseek-Trae-v1-backup-20260309-020000.filelist.txt   # 文件列表
├── AIseek-Trae-v1-backup-20260309-020000.changes.txt    # 变更日志
└── AIseek-Trae-v1-backup-20260309-020000.READM E.md      # 备份说明
```

### OSS 存储结构

```
aiseek-backups/
└── aiseek-backups/
    ├── AIseek-Trae-v1-backup-20260309-020000.tar.gz
    ├── AIseek-Trae-v1-backup-20260309-020000.tar.gz.sha256
    └── ...
```

---

## ✅ 上传后校验

备份上传完成后，自动执行校验：

```yaml
- name: Verify backup upload
  run: |
    python tools/backup_verify.py
```

### 校验内容

1. **对象存在** - 确认备份文件已上传
2. **大小 > 0** - 确认文件不是空的
3. **metadata 可读** - 确认文件可访问

### 手动校验

```bash
python tools/backup_verify.py
```

---

## 🔧 故障排查

### 问题 1: 备份上传失败

**错误**: `aws-chunked encoding is not supported`

**原因**: 使用了 boto3 SDK

**解决**: 使用 oss2 SDK（见上文）

---

### 问题 2: AccessKey 无效

**错误**: `InvalidAccessKeyId: The OSS Access Key Id you provided does not exist`

**原因**: AccessKey 配置错误

**解决**:
1. 检查 GitHub Secrets 是否正确
2. 检查 AccessKey 是否已启用
3. 检查 RAM 用户是否有 OSS 权限

---

### 问题 3: 存储桶不存在

**错误**: `NoSuchBucket`

**原因**: OSS 存储桶未创建或名称错误

**解决**:
1. 登录阿里云 OSS 控制台
2. 确认存储桶名称：`aiseek-backups`
3. 确认地域配置正确

---

### 问题 4: 备份文件过大

**现象**: 上传时间过长或失败

**解决**:
1. 检查备份内容，排除不必要的大文件
2. 配置 `.gitignore` 排除大文件
3. 考虑分卷压缩

---

## 📊 备份策略

### 保留策略

| 类型 | 保留数量 | 说明 |
|------|---------|------|
| 本地备份 | 30 个 | 最近 30 天的备份 |
| 远程备份 | 30 个 | OSS 上保留 30 个 |

### 备份时间

- **GitHub Actions**: 每天 UTC 2:30（北京时间 10:30）
- **本地手动**: 随时执行

---

## 🔐 安全建议

1. **AccessKey 安全**
   - 不要将 AccessKey 提交到代码仓库
   - 使用 GitHub Secrets 存储
   - 定期轮换 AccessKey

2. **备份加密**（可选）
   - 备份前加密敏感数据
   - 使用 OSS 服务端加密

3. **访问控制**
   - 设置存储桶为私有
   - 使用 RAM 用户限制权限

---

## 📝 相关文档

- [部署复盘报告](./DEPLOY_INCIDENT_README_20260309.md)
- [备份上传脚本](../tools/backup_upload_s3.py)
- [备份工作流](../.github/workflows/backup_daily.yml)

---

**最后更新**: 2026-03-09  
**状态**: ✅ 运行正常
