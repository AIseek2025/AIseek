# GitHub Actions 备份配置指南

**仓库**: https://github.com/AIseek2025/AIseek  
**工作流**: `.github/workflows/backup_daily.yml`  
**配置时间**: 2026-03-08

---

## 📋 配置步骤

### 1. 打开 GitHub 仓库设置

1. 访问：https://github.com/AIseek2025/AIseek
2. 点击 **Settings** (设置)
3. 左侧菜单选择 **Secrets and variables** → **Actions**
4. 点击 **New repository secret** (新建仓库密钥)

---

### 2. 添加必需的 Secrets

按顺序添加以下密钥：

#### 2.1 存储桶名称
- **Name**: `BACKUP_S3_BUCKET`
- **Value**: 你的 OSS 存储桶名称 (例如：`aiseek-backups`)

#### 2.2 AWS 访问密钥 ID
- **Name**: `AWS_ACCESS_KEY_ID`
- **Value**: 你的阿里云访问密钥 ID (例如：`LTAI5t...`)

#### 2.3 AWS 访问密钥 Secret
- **Name**: `AWS_SECRET_ACCESS_KEY`
- **Value**: 你的阿里云访问密钥 Secret

#### 2.4 默认区域
- **Name**: `AWS_DEFAULT_REGION`
- **Value**: OSS 区域 (例如：`oss-cn-hangzhou` 或 `us-east-1`)

---

### 3. 可选 Secrets

#### 3.1 存储桶前缀
- **Name**: `BACKUP_S3_PREFIX`
- **Value**: 备份文件前缀路径 (例如：`aiseek/daily` 或留空)

#### 3.2 端点 URL (如使用阿里云 OSS)
- **Name**: `BACKUP_S3_ENDPOINT_URL`
- **Value**: OSS 端点 (例如：`https://oss-cn-hangzhou.aliyuncs.com`)

---

## 🔑 获取阿里云 OSS 凭证

### 步骤 1: 创建 RAM 用户

1. 登录阿里云控制台：https://ram.console.aliyun.com
2. 左侧菜单：**身份管理** → **用户**
3. 点击 **创建用户**
4. 填写用户名 (例如：`aiseek-github-actions`)
5. 访问方式：勾选 **OpenAPI 调用访问**
6. 点击 **确定**
7. **重要**: 保存 AccessKey ID 和 AccessKey Secret

### 步骤 2: 授权权限

1. 在用户列表中找到刚创建的用户
2. 点击 **添加权限**
3. 选择权限：
   - `AliyunOSSFullAccess` (OSS 完全访问权限)
   - 或自定义权限 (仅允许特定存储桶)
4. 点击 **确定**

### 步骤 3: 创建 OSS 存储桶

1. 访问 OSS 控制台：https://oss.console.aliyun.com
2. 点击 **创建 Bucket**
3. 填写信息：
   - **Bucket 名称**: `aiseek-backups` (全局唯一)
   - **地域**: 选择离你最近的地域
   - **读写权限**: 私有 (推荐)
4. 点击 **确定**

---

## ✅ 验证配置

### 1. 手动触发备份工作流

```bash
# 确保已安装 GitHub CLI
gh auth login

# 触发备份工作流
cd /Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1
gh workflow run backup_daily.yml

# 查看运行状态
gh run list --workflow backup_daily.yml -L 5
```

### 2. 在 GitHub 上查看

1. 访问：https://github.com/AIseek2025/AIseek/actions
2. 找到 **Backup Daily** 工作流
3. 确认状态为 **Success** ✅

### 3. 检查 OSS 存储桶

1. 登录阿里云 OSS 控制台
2. 进入你的存储桶
3. 确认备份文件已上传

---

## 🔧 故障排查

### 问题 1: 工作流失败 - 缺少密钥

**错误信息**: `Error: Input required and not supplied: BACKUP_S3_BUCKET`

**解决方案**:
- 确认所有必需的 Secrets 已添加
- 检查密钥名称是否完全匹配 (区分大小写)
- 等待 1-2 分钟后重试

### 问题 2: 认证失败

**错误信息**: `AccessDenied` 或 `InvalidAccessKeyId`

**解决方案**:
- 检查 `AWS_ACCESS_KEY_ID` 和 `AWS_SECRET_ACCESS_KEY` 是否正确
- 确认 RAM 用户有 OSS 权限
- 检查密钥是否已激活

### 问题 3: 存储桶不存在

**错误信息**: `NoSuchBucket`

**解决方案**:
- 确认 `BACKUP_S3_BUCKET` 名称正确
- 检查存储桶是否已创建
- 确认区域设置正确

### 问题 4: 端点错误

**错误信息**: 连接超时或端点错误

**解决方案**:
- 添加 `BACKUP_S3_ENDPOINT_URL` Secret
- 使用正确的 OSS 端点格式：`https://oss-{region}.aliyuncs.com`
- 例如：`https://oss-cn-hangzhou.aliyuncs.com`

---

## 📅 备份计划

**默认计划**: 每天 UTC 时间 00:00 (北京时间 08:00)

**修改计划** (可选):
1. 编辑 `.github/workflows/backup_daily.yml`
2. 修改 `schedule` 部分的 cron 表达式
3. 提交更改

**Cron 表达式参考**:
```yaml
# 每天北京时间 08:00
- cron: '0 0 * * *'

# 每天北京时间 02:00
- cron: '0 18 * * *'

# 每 6 小时
- cron: '0 */6 * * *'
```

---

## 📊 备份保留策略

**默认保留**: 最近 30 天的备份

**修改保留策略** (可选):
1. 编辑 `.github/workflows/backup_daily.yml`
2. 修改 `retention_days` 参数
3. 提交更改

---

## 🔐 安全建议

1. **最小权限原则**: RAM 用户只授予必要的权限
2. **定期轮换密钥**: 每 90 天更新一次 AccessKey
3. **监控访问日志**: 定期检查 OSS 访问日志
4. **加密敏感数据**: 备份文件可启用服务器端加密
5. **多区域备份**: 重要数据建议跨区域备份

---

## 📞 支持

**遇到问题？**

1. 查看工作流日志：https://github.com/AIseek2025/AIseek/actions
2. 检查 OSS 控制台：https://oss.console.aliyun.com
3. 查看阿里云文档：https://help.aliyun.com/product/31815.html

---

**配置完成日期**: _______________  
**配置人**: _______________  
**验证状态**: ☐ 成功 ☐ 失败

---

**最后更新**: 2026-03-08  
**版本**: 26ad570
