# AIseek 阿里云部署清单

**域名**: aiseek.cool  
**版本**: 26ad570  
**部署日期**: 2026-03-08  
**部署目标**: 阿里云 ECS

---

## 📋 部署前检查清单

### 1. 仓库与版本 ✅

- [x] 远端仓库：`https://github.com/AIseek2025/AIseek.git`
- [x] 当前提交：`26ad570`
- [x] main 分支已推送
- [x] 本地工作区干净

**验证命令**:
```bash
cd /Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1
git fetch origin
git checkout main
git status
git rev-parse --short HEAD
```

---

### 2. 服务器与域名 ⏳

- [ ] ECS 安全组配置：
  - [x] 开放 80 端口 (HTTP)
  - [x] 开放 443 端口 (HTTPS)
  - [ ] 关闭 5432 端口 (PostgreSQL) 公网访问
  - [ ] 关闭 6379 端口 (Redis) 公网访问
  - [ ] 22 端口 (SSH) 按需开放

- [ ] 域名 DNS 配置：
  - [ ] A 记录：`aiseek.cool` → ECS 公网 IP
  - [ ] A 记录：`www.aiseek.cool` → ECS 公网 IP (可选)

- [ ] 服务器时间同步：
  ```bash
  timedatectl status
  ntpdate -q pool.ntp.org
  ```

---

### 3. 生产环境变量 ⏳

**文件位置**: `deploy/aliyun/.env.prod`

**必须修改的配置**:
- [ ] `POSTGRES_PASSWORD` - 生成强密码
- [ ] `REDIS_PASSWORD` - 生成强密码
- [ ] `WORKER_SECRET` - 生成强密码 (openssl rand -hex 32)
- [ ] `WEB_URL=https://aiseek.cool`
- [ ] `CALLBACK_URL=https://aiseek.cool/callback`

**可选配置**:
- [ ] `DEEPSEEK_API_KEY` - 如需启用 AI 功能
- [ ] `R2_*` - 如需启用对象存储

**生成强密码**:
```bash
# PostgreSQL 密码
openssl rand -base64 32

# Redis 密码
openssl rand -base64 32

# Worker 密钥
openssl rand -hex 32
```

---

### 4. SSL 证书 ⏳

**方案 A: 使用已有证书**
- [ ] 证书文件放在 `deploy/aliyun/certs/`
- [ ] `fullchain.pem` (证书链)
- [ ] `privkey.pem` (私钥)
- [ ] Nginx 配置路径匹配

**方案 B: 使用 Let's Encrypt (推荐)**
```bash
# 在服务器上安装 certbot
apt update && apt install -y certbot

# 获取证书
certbot certonly --standalone -d aiseek.cool -d www.aiseek.cool

# 证书位置
# /etc/letsencrypt/live/aiseek.cool/fullchain.pem
# /etc/letsencrypt/live/aiseek.cool/privkey.pem

# 创建符号链接到部署目录
ln -s /etc/letsencrypt/live/aiseek.cool/fullchain.pem /opt/aiseek/deploy/aliyun/certs/fullchain.pem
ln -s /etc/letsencrypt/live/aiseek.cool/privkey.pem /opt/aiseek/deploy/aliyun/certs/privkey.pem
```

**验证 Nginx 配置**:
```bash
nginx -t
```

---

### 5. 数据迁移 ⏳

**首次上线前执行**:
```bash
cd /opt/aiseek
PYTHONPATH=backend ./.venv/bin/python backend/scripts/deploy_bootstrap.py --migrate
```

**构建静态资源指针** (可选但建议):
```bash
PYTHONPATH=backend ./.venv/bin/python backend/scripts/build_static_assets.py
```

---

### 6. 容器启动 ⏳

**启动命令**:
```bash
cd /opt/aiseek/deploy/aliyun
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

**检查服务状态**:
```bash
docker compose -f docker-compose.prod.yml ps
```

**预期状态**:
- [ ] db: healthy
- [ ] redis: healthy
- [ ] backend: running
- [ ] worker: running
- [ ] nginx: running

**查看日志**:
```bash
# 查看所有服务日志
docker compose -f docker-compose.prod.yml logs -f

# 查看特定服务
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f worker
```

---

### 7. 业务冒烟测试 ✅

**必须验证的功能**:

- [ ] **首页**: `https://aiseek.cool/`
  - [ ] 页面可打开 (HTTP 200)
  - [ ] 视频正常播放
  - [ ] 分类导航正常

- [ ] **创作台**: `https://aiseek.cool/studio`
  - [ ] 页面可打开
  - [ ] 能提交任务
  - [ ] 生成状态正常

- [ ] **管理后台**: `https://aiseek.cool/admin`
  - [ ] 可登录
  - [ ] 任务列表显示
  - [ ] 筛选功能可用

- [ ] **播放功能**:
  - [ ] 浮窗视频可全屏
  - [ ] 精选播放量会刷新
  - [ ] 点击播放正常

**自动化检查**:
```bash
curl -I https://aiseek.cool/
curl -I https://aiseek.cool/studio
curl -I https://aiseek.cool/admin
curl -I https://aiseek.cool/health
```

---

### 8. 发布流程专项 ✅

- [ ] 生成后状态应为"待发布（preview）"
- [ ] 点击"发布"后变为"已发布（done）"
- [ ] 无标题时可自动命名（DeepSeek 可用时走 AI，不可用走本地兜底）

---

### 9. 备份与恢复 ⏳

**本地备份** ✅:
- [x] 备份前缀：`AIseek-Trae-v1-backup-20260308-072530`
- [x] 产物齐全：tar/sha256/manifest/filelist/changes/README

**GitHub Actions 备份** ⏳:
- [ ] 在 GitHub 仓库添加 Secrets：
  - [ ] `BACKUP_S3_BUCKET`
  - [ ] `AWS_ACCESS_KEY_ID`
  - [ ] `AWS_SECRET_ACCESS_KEY`
  - [ ] `AWS_DEFAULT_REGION`
  - [ ] `BACKUP_S3_PREFIX` (可选)
  - [ ] `BACKUP_S3_ENDPOINT_URL` (可选，如使用 OSS)

**验证备份工作流**:
```bash
# 手动触发备份
gh workflow run backup_daily.yml

# 查看运行状态
gh run list --workflow backup_daily.yml -L 3
```

---

### 10. 上线后监控 ⏳

**首小时重点关注**:
- [ ] 5xx 错误率 (< 1%)
- [ ] 接口超时 (< 5s)
- [ ] 队列积压 (< 100)
- [ ] CPU 使用率 (< 80%)
- [ ] 内存使用率 (< 80%)
- [ ] 磁盘增长 (正常)

**监控命令**:
```bash
# 查看服务资源使用
docker stats

# 查看后端日志
docker compose -f docker-compose.prod.yml logs --tail=100 backend

# 查看 worker 日志
docker compose -f docker-compose.prod.yml logs --tail=100 worker

# 查看 Nginx 访问日志
tail -f /var/log/nginx/access.log

# 查看 Nginx 错误日志
tail -f /var/log/nginx/error.log
```

**Admin 仪表盘**:
- [ ] AI 队列状态正常
- [ ] 失败率 < 5%
- [ ] 任务处理速度正常

---

## 🔄 回滚预案

**若新版本异常，快速回滚**:

```bash
# 1. 停止新服务
cd /opt/aiseek/deploy/aliyun
docker compose -f docker-compose.prod.yml down

# 2. 备份当前状态
cd /opt/aiseek
tar -czf /root/aiseek-backup-$(date +%Y%m%d-%H%M%S).tgz .

# 3. 恢复旧版本代码
# (从备份目录解压或 git checkout 到上一个可用提交)

# 4. 重启旧版本
cd /opt/aiseek/deploy/aliyun
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d

# 5. 验证服务
curl -I https://aiseek.cool/
```

**保留上一个可用镜像/提交**:
- 记录当前可用提交 hash
- 保留上一个 Docker 镜像 tag
- 备份数据库：`docker compose exec db pg_dump -U aiseek aiseek_prod > backup.sql`

---

## 📞 应急联系

**问题排查顺序**:
1. 查看服务状态：`docker compose ps`
2. 查看错误日志：`docker compose logs --tail=100`
3. 检查资源使用：`docker stats`
4. 验证网络连接：`curl -I https://aiseek.cool/`
5. 检查数据库连接：`docker compose exec db psql -U aiseek -d aiseek_prod -c "SELECT 1"`

**常见故障**:
- **服务无法启动**: 检查端口占用、配置文件、证书路径
- **数据库连接失败**: 检查密码、网络、健康状态
- **HTTPS 无法访问**: 检查证书、Nginx 配置、防火墙
- **Worker 不处理任务**: 检查 Redis 连接、队列状态、日志

---

## ✅ 部署完成确认

部署完成后，确认以下事项：

- [ ] 首页可正常访问
- [ ] 所有核心功能正常
- [ ] 监控告警已配置
- [ ] 备份机制已验证
- [ ] 回滚预案已测试
- [ ] 文档已更新

**部署完成时间**: _______________  
**部署执行人**: _______________  
**验证人**: _______________

---

## 📚 相关文档

- [部署指南](./deploy/aliyun/README.md)
- [Docker Compose 配置](./deploy/aliyun/docker-compose.prod.yml)
- [环境变量示例](./deploy/aliyun/.env.prod.example)
- [Nginx 配置](./deploy/nginx/nginx.conf)
- [GitHub Actions 备份](./.github/workflows/backup_daily.yml)

---

**最后更新**: 2026-03-08  
**版本**: 26ad570
