# AIseek 阿里云部署完整指南

**部署日期**: 2026-03-08  
**服务器**: 阿里云轻量应用服务器 (2 vCPU / 2GB / 40GB)  
**域名**: aiseek.cool  
**状态**: ✅ 生产就绪

---

## 📋 目录

1. [服务器配置](#服务器配置)
2. [部署前准备](#部署前准备)
3. [遇到的问题与解决方案](#遇到的问题与解决方案)
4. [最终正确部署流程](#最终正确部署流程)
5. [Nginx 多域名配置](#nginx 多域名配置)
6. [健康检查与监控](#健康检查与监控)
7. [日常维护](#日常维护)
8. [故障排查清单](#故障排查清单)

---

## 服务器配置

| 配置项 | 值 |
|--------|-----|
| 实例类型 | 阿里云轻量应用服务器 |
| CPU | 2 vCPU |
| 内存 | 2GB |
| 磁盘 | 40GB ESSD |
| 公网 IP | 47.239.7.62 |
| 内网 IP | 172.19.43.195 |
| 操作系统 | Alibaba Cloud Linux |

---

## 部署前准备

### 1. 检查磁盘空间

```bash
df -h
```

**预期**: 至少 10GB 可用空间

### 2. 清理 Docker 垃圾（如需要）

```bash
docker system prune -a -f --volumes
docker builder prune -a -f
```

### 3. 上传部署包

```bash
# 在本地 Mac 上执行
cd /Users/surferboy/.openclaw/workspace/AIseek-integrated
scp aiseek-release-*.tgz root@47.239.7.62:/root/
scp AIseek-Trae-v1/scripts/deploy-on-aliyun.sh root@47.239.7.62:/root/
```

### 4. 登录服务器

```bash
ssh root@47.239.7.62
```

---

## 遇到的问题与解决方案

### 问题 1: 磁盘空间不足 ❌

**症状**:
```
PANIC: could not write to file "pg_logical/replorigin_checkpoint.tmp": No space left on device
```

**原因**: Docker 积累了太多镜像和容器垃圾

**解决方案**:
```bash
docker system prune -a -f --volumes
docker builder prune -a -f
df -h  # 确认有足够空间
```

**结果**: 回收了 16.45GB 空间

---

### 问题 2: PostgreSQL 卡在 Recovery 模式 ❌

**症状**:
```
FATAL: the database system is not yet accepting connections
DETAIL: Consistent recovery state has not been yet reached.
```

**原因**: 
- 数据库异常关机后 WAL 无法完成
- 可能存在 `standby.signal` 或 `recovery.signal` 文件

**解决方案**:
```bash
# 检查 signal 文件
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T db sh -lc 'ls -l /var/lib/postgresql/data/*.signal 2>/dev/null || true'

# 如果存在，删除它们
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T db sh -lc 'rm -f /var/lib/postgresql/data/standby.signal /var/lib/postgresql/data/recovery.signal'

# 重启数据库
docker compose --env-file .env.prod -f docker-compose.prod.yml restart db

# 等待数据库就绪
until docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T db pg_isready; do sleep 2; done
```

---

### 问题 3: Alembic 迁移路径配置错误 ❌

**症状**:
```
alembic.util.exc.CommandError: Path doesn't exist: backend/alembic
KeyError: 'formatters'
```

**原因**: 
- 容器内路径是 `/app/alembic`，但配置写的是 `backend/alembic`
- `alembic.ini` 配置文件缺少 `formatters` 部分

**解决方案**:
```bash
# 方法 1: 手动跑迁移（指定正确的路径）
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm \
  -e ALEMBIC_DATABASE_URL="postgresql://aiseek:Test123456@db:5432/aiseek_prod" \
  backend sh -lc '
    sed -i "s#script_location = backend/alembic#script_location = /app/alembic#" /app/alembic.ini &&
    sed -i "s#prepend_sys_path = backend#prepend_sys_path = /app#" /app/alembic.ini &&
    alembic -c /app/alembic.ini upgrade head
  '

# 方法 2: 创建正确的 alembic.ini
cat > /opt/aiseek/AIseek-Trae-v1/backend/alembic.ini << 'EOF'
[alembic]
script_location = alembic
prepend_sys_path = .

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN

[logger_alembic]
level = INFO

[handler_console]
class = StreamHandler
formatter = generic

[formatter_generic]
format = %(message)s
EOF
```

---

### 问题 4: 环境变量解析失败 ❌

**症状**:
```
error while interpolating services.db.environment.POSTGRES_USER: required variable POSTGRES_USER is missing a value
-bash: aiseek: command not found
```

**原因**: 
- `docker compose` 命令有些带了 `--env-file .env.prod`，有些没带
- 环境变量 `$POSTGRES_USER` 没有被正确解析

**解决方案**:
```bash
# 所有 docker compose 命令都必须带 --env-file
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
docker compose --env-file .env.prod -f docker-compose.prod.yml logs backend

# 或者先 export 环境变量
set -a; source .env.prod; set +a
```

**关键**: 每条命令都要带 `--env-file .env.prod`！

---

### 问题 5: 并发竞态条件 ❌

**症状**:
```
psycopg2.errors.InFailedSqlTransaction: current transaction is aborted
sqlalchemy.exc.InternalError: (2j85)
```

**原因**: 
- gunicorn 多 worker 启动
- `startup` 里有"先 count=0 再批量插入 categories"逻辑
- 两个 worker 同时跑 startup，容易出现一个事务先失败，另一个继续

**解决方案**:
```bash
# 减少并发数为 1（单 worker）
cd /opt/aiseek/AIseek-Trae-v1/deploy/aliyun
sed -i 's/WEB_CONCURRENCY=2/WEB_CONCURRENCY=1/' .env.prod
sed -i 's/WORKER_CONCURRENCY=2/WORKER_CONCURRENCY=1/' .env.prod

# 重启服务
docker compose --env-file .env.prod -f docker-compose.prod.yml down
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
```

**注意**: 生产环境稳定 24 小时后再考虑升到 2

---

### 问题 6: Nginx 端口配置 ❌

**症状**:
- `curl -I http://localhost:8888/` 返回 200
- `curl -I http://47.239.7.62/` 无法访问

**原因**: Nginx 运行在 8888 端口，但域名访问默认是 80 端口

**解决方案**:
```bash
# 方案 A: 修改 docker-compose 为 80 端口（推荐）
cd /opt/aiseek/AIseek-Trae-v1/deploy/aliyun
sed -i 's/"8888:80"/"80:80"/' docker-compose.prod.yml
sed -i 's/"8443:443"/"443:443"/' docker-compose.prod.yml
docker compose --env-file .env.prod -f docker-compose.prod.yml down
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d

# 方案 B: 配置 Nginx 反向代理（多域名场景）
cat > /etc/nginx/conf.d/aiseek.conf << 'EOF'
server {
    listen 80;
    server_name aiseek.cool www.aiseek.cool;
    location / {
        proxy_pass http://localhost:8888;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF
nginx -t && nginx -s reload
```

---

### 问题 7: DNS 解析未配置 ❌

**症状**:
```
curl: (6) Could not resolve host: aiseek.cool
```

**原因**: 域名没有配置 DNS A 记录

**解决方案**:

1. 登录阿里云 DNS 控制台：https://dns.console.aliyun.com
2. 添加 A 记录：
   - 主机记录：`@` → 记录值：`47.239.7.62`
   - 主机记录：`www` → 记录值：`47.239.7.62`
3. 等待 5-10 分钟生效

**验证**:
```bash
ping aiseek.cool
# 应该解析到 47.239.7.62
```

---

### 问题 8: Nginx 多域名冲突 ❌

**症状**:
- `http://aiseek.cool/` 显示 BestGoods 的内容
- `http://www.bestgoods.vip/` 正常

**原因**: BestGoods 的 Nginx 配置用了 `default_server`，覆盖了 aiseek 的配置

**解决方案**:
```bash
# 创建 AIseek 的 Nginx 配置（用 echo 逐行添加，避免 heredoc 问题）
echo 'server {' > /etc/nginx/conf.d/aiseek.conf
echo '    listen 80;' >> /etc/nginx/conf.d/aiseek.conf
echo '    server_name aiseek.cool www.aiseek.cool;' >> /etc/nginx/conf.d/aiseek.conf
echo '    location / {' >> /etc/nginx/conf.d/aiseek.conf
echo '        proxy_pass http://localhost:8888;' >> /etc/nginx/conf.d/aiseek.conf
echo '        proxy_set_header Host $host;' >> /etc/nginx/conf.d/aiseek.conf
echo '        proxy_set_header X-Real-IP $remote_addr;' >> /etc/nginx/conf.d/aiseek.conf
echo '    }' >> /etc/nginx/conf.d/aiseek.conf
echo '}' >> /etc/nginx/conf.d/aiseek.conf

# 验证并重载
nginx -t
nginx -s reload

# 验证
curl http://aiseek.cool/ | grep -i "title"
# 应该显示 AIseek 的标题
```

---

## 最终正确部署流程

### 第 1 步：解压部署包

```bash
cd /root
mkdir -p /opt/aiseek
cd /opt/aiseek
tar -xzf /root/aiseek-release-*.tgz
```

### 第 2 步：创建配置文件

```bash
cd /opt/aiseek/AIseek-Trae-v1/deploy/aliyun

# 用 echo 逐行创建（避免 heredoc 问题）
echo 'POSTGRES_USER=aiseek' > .env.prod
echo 'POSTGRES_PASSWORD=Test123456' >> .env.prod
echo 'POSTGRES_DB=aiseek_prod' >> .env.prod
echo 'REDIS_PASSWORD=Test123456' >> .env.prod
echo 'WORKER_SECRET=shortsecret123' >> .env.prod
echo 'WEB_URL=http://47.239.7.62' >> .env.prod
echo 'CALLBACK_URL=http://47.239.7.62/callback' >> .env.prod
echo 'WEB_CONCURRENCY=1' >> .env.prod
echo 'WORKER_CONCURRENCY=1' >> .env.prod
echo 'AUTO_MIGRATE=0' >> .env.prod

cat .env.prod  # 验证
```

### 第 3 步：修复 alembic.ini

```bash
cat > /opt/aiseek/AIseek-Trae-v1/backend/alembic.ini << 'EOF'
[alembic]
script_location = alembic
prepend_sys_path = .

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN

[logger_alembic]
level = INFO

[handler_console]
class = StreamHandler
formatter = generic

[formatter_generic]
format = %(message)s
EOF
```

### 第 4 步：启动服务

```bash
cd /opt/aiseek/AIseek-Trae-v1/deploy/aliyun

# 清理旧容器
docker compose --env-file .env.prod -f docker-compose.prod.yml down

# 启动数据库
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d db redis

# 等待数据库就绪
sleep 20
docker compose --env-file .env.prod -f docker-compose.prod.yml exec db pg_isready

# 手动跑迁移
docker compose --env-file .env.prod -f docker-compose.prod.yml run --rm \
  -e ALEMBIC_DATABASE_URL="postgresql://aiseek:Test123456@db:5432/aiseek_prod" \
  backend sh -lc '
    sed -i "s#script_location = backend/alembic#script_location = /app/alembic#" /app/alembic.ini &&
    sed -i "s#prepend_sys_path = backend#prepend_sys_path = /app#" /app/alembic.ini &&
    alembic -c /app/alembic.ini upgrade head
  '

# 初始化分类数据
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T db psql -U aiseek -d aiseek_prod -c "
INSERT INTO categories(name,sort_order,is_active) VALUES 
('大模型',0,true),('Agent',1,true),('机器人',2,true),('AIGC',3,true),
('多模态',4,true),('编程',5,true),('提示词',6,true),('资讯',7,true),
('Tools',8,true),('办公',9,true),('变现',10,true),('电商',11,true),
('游戏',12,true),('金融',13,true),('影视',14,true),('教育',15,true),
('少儿',16,true) ON CONFLICT (name) DO NOTHING;"

# 启动所有服务
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d

# 等待启动
sleep 30

# 检查状态
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
```

### 第 5 步：配置 Nginx 反向代理

```bash
# 创建 AIseek 配置
echo 'server {' > /etc/nginx/conf.d/aiseek.conf
echo '    listen 80;' >> /etc/nginx/conf.d/aiseek.conf
echo '    server_name aiseek.cool www.aiseek.cool;' >> /etc/nginx/conf.d/aiseek.conf
echo '    location / {' >> /etc/nginx/conf.d/aiseek.conf
echo '        proxy_pass http://localhost:8888;' >> /etc/nginx/conf.d/aiseek.conf
echo '        proxy_set_header Host $host;' >> /etc/nginx/conf.d/aiseek.conf
echo '        proxy_set_header X-Real-IP $remote_addr;' >> /etc/nginx/conf.d/aiseek.conf
echo '    }' >> /etc/nginx/conf.d/aiseek.conf
echo '}' >> /etc/nginx/conf.d/aiseek.conf

# 验证并重载
nginx -t
nginx -s reload
```

### 第 6 步：验证部署

```bash
# 本地访问
curl -I http://localhost:8888/

# 域名访问
curl -I http://aiseek.cool/
curl -I http://www.aiseek.cool/

# 验证内容
curl http://aiseek.cool/ | grep -i "title"
# 应该显示：<title>AIseek</title>

curl http://www.bestgoods.vip/ | grep -i "title"
# 应该显示 BestGoods 的标题
```

---

## Nginx 多域名配置

### 场景说明

- `bestgoods.vip` → `localhost:3100` (BestGoods)
- `aiseek.cool` → `localhost:8888` (AIseek)

### 配置文件

**BestGoods 配置** (`/etc/nginx/conf.d/bestgoods.conf`):
```nginx
server {
    listen 80;
    server_name bestgoods.vip www.bestgoods.vip;
    
    location / {
        proxy_pass http://localhost:3100;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /health {
        proxy_pass http://localhost:3100/health;
        access_log off;
    }
}
```

**AIseek 配置** (`/etc/nginx/conf.d/aiseek.conf`):
```nginx
server {
    listen 80;
    server_name aiseek.cool www.aiseek.cool;
    
    location / {
        proxy_pass http://localhost:8888;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 验证命令

```bash
# 列出所有配置
ls -la /etc/nginx/conf.d/

# 验证语法
nginx -t

# 重载配置
nginx -s reload

# 测试访问
curl http://aiseek.cool/ | grep -i "title"
curl http://bestgoods.vip/ | grep -i "title"
```

---

## 健康检查与监控

### 简化健康检查脚本

```bash
cat > /tmp/check.sh << 'END' && chmod +x /tmp/check.sh
#!/bin/bash
cd /opt/aiseek/AIseek-Trae-v1/deploy/aliyun
echo "=== AIseek 健康检查 ==="
date
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
curl -s -o /dev/null -w "网站状态：%{http_code}\n" http://aiseek.cool/
curl -s -o /dev/null -w "Studio 状态：%{http_code}\n" http://aiseek.cool/studio
curl -s -o /dev/null -w "Admin 状态：%{http_code}\n" http://aiseek.cool/admin
df -h / | awk 'NR==2{print "磁盘使用："$5}'
echo "=== 完成 ==="
END
```

### 配置自动巡检（每 15 分钟）

```bash
# 创建日志目录
mkdir -p /var/log/aiseek

# 复制脚本
cp /tmp/check.sh /usr/local/bin/aiseek-health-check.sh
chmod +x /usr/local/bin/aiseek-health-check.sh

# 配置 cron
(crontab -l 2>/dev/null; echo '*/15 * * * * /usr/local/bin/aiseek-health-check.sh >> /var/log/aiseek/health.log 2>&1') | crontab -

# 验证
crontab -l
```

### 监控阈值

| 指标 | 阈值 | 动作 |
|------|------|------|
| HTTP 5xx | > 2% (5 分钟窗口) | 告警 |
| HTTP 5xx | > 5% (10 分钟) | 回滚评估 |
| P95 延迟 | > 1500ms | 告警 |
| Backend 重启 | ≥ 2 次 (30 分钟) | 告警 |
| Backend 重启 | ≥ 4 次 | 回滚评估 |
| 磁盘使用率 | > 80% | 告警 |
| 磁盘使用率 | > 90% | 立即清理 |
| DB 未就绪 | 连续 5 次 | 回滚评估 |

### 查看监控日志

```bash
tail -n 50 /var/log/aiseek/health.log
```

---

## 日常维护

### 1. 定期清理 Docker（每周）

```bash
docker system prune -f
docker builder prune -f
```

### 2. 检查磁盘空间（每天）

```bash
df -h
```

### 3. 查看服务状态（每天）

```bash
cd /opt/aiseek/AIseek-Trae-v1/deploy/aliyun
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
```

### 4. 查看错误日志（每天）

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml logs backend --tail=100
docker compose --env-file .env.prod -f docker-compose.prod.yml logs nginx --tail=100
```

### 5. 数据库备份（每天）

```bash
cd /opt/aiseek/AIseek-Trae-v1/deploy/aliyun
docker compose --env-file .env.prod -f docker-compose.prod.yml exec db pg_dump -U aiseek -d aiseek_prod > /root/db-backup-$(date +%Y%m%d).sql
```

### 6. 配置 GitHub Actions 备份

在 GitHub 仓库添加 Secrets：
- `BACKUP_S3_BUCKET`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_DEFAULT_REGION`

然后手动触发一次 `backup_daily.yml` 工作流。

---

## 故障排查清单

### 网站无法访问

```bash
# 1. 检查 DNS 解析
ping aiseek.cool

# 2. 检查服务状态
docker compose --env-file .env.prod -f docker-compose.prod.yml ps

# 3. 检查 Nginx 配置
nginx -t
nginx -s reload

# 4. 检查端口监听
netstat -tlnp | grep -E "80|8888"

# 5. 本地测试
curl -I http://localhost:8888/
curl -I http://localhost/
```

### Backend 不断重启

```bash
# 1. 查看日志
docker compose --env-file .env.prod -f docker-compose.prod.yml logs backend --tail=200

# 2. 检查数据库连接
docker compose --env-file .env.prod -f docker-compose.prod.yml exec db pg_isready

# 3. 检查环境变量
cat /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/.env.prod

# 4. 检查并发数
grep CONCURRENCY /opt/aiseek/AIseek-Trae-v1/deploy/aliyun/.env.prod
# 应该是 WEB_CONCURRENCY=1
```

### 数据库无法连接

```bash
# 1. 检查数据库状态
docker compose --env-file .env.prod -f docker-compose.prod.yml ps db

# 2. 查看数据库日志
docker compose --env-file .env.prod -f docker-compose.prod.yml logs db

# 3. 检查 signal 文件
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T db sh -lc 'ls -l /var/lib/postgresql/data/*.signal 2>/dev/null || true'

# 4. 如果有 signal 文件，删除并重启
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T db sh -lc 'rm -f /var/lib/postgresql/data/standby.signal /var/lib/postgresql/data/recovery.signal'
docker compose --env-file .env.prod -f docker-compose.prod.yml restart db
```

### 磁盘空间不足

```bash
# 1. 检查磁盘使用
df -h

# 2. 清理 Docker
docker system prune -a -f --volumes
docker builder prune -a -f

# 3. 清理日志
> /var/log/nginx/error.log
> /var/log/nginx/access.log

# 4. 再次检查
df -h
```

---

## 快速回滚步骤

如果新版本有问题，快速回滚：

```bash
cd /opt/aiseek/AIseek-Trae-v1/deploy/aliyun

# 1. 停止当前服务
docker compose --env-file .env.prod -f docker-compose.prod.yml down

# 2. 备份当前状态
cd /opt/aiseek
tar -czf /root/aiseek-backup-$(date +%Y%m%d-%H%M%S).tgz .

# 3. 恢复旧版本代码
# (从备份解压或 git checkout)

# 4. 重启服务
cd /opt/aiseek/AIseek-Trae-v1/deploy/aliyun
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d

# 5. 验证
curl -I http://aiseek.cool/
```

---

## 重要命令速查

```bash
# 服务管理
cd /opt/aiseek/AIseek-Trae-v1/deploy/aliyun
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
docker compose --env-file .env.prod -f docker-compose.prod.yml restart
docker compose --env-file .env.prod -f docker-compose.prod.yml down
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d

# 查看日志
docker compose --env-file .env.prod -f docker-compose.prod.yml logs backend --tail=100
docker compose --env-file .env.prod -f docker-compose.prod.yml logs nginx --tail=100
docker compose --env-file .env.prod -f docker-compose.prod.yml logs db --tail=100

# 健康检查
/usr/local/bin/aiseek-health-check.sh
curl -I http://aiseek.cool/
curl -I http://aiseek.cool/studio
curl -I http://aiseek.cool/admin

# 数据库操作
docker compose --env-file .env.prod -f docker-compose.prod.yml exec db pg_isready
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T db psql -U aiseek -d aiseek_prod -c "SELECT 1"
docker compose --env-file .env.prod -f docker-compose.prod.yml exec db pg_dump -U aiseek -d aiseek_prod > backup.sql

# 磁盘清理
docker system prune -a -f --volumes
df -h
```

---

## 联系与支持

- **部署日期**: 2026-03-08
- **最后更新**: 2026-03-08
- **版本**: 26ad570
- **域名**: https://aiseek.cool

---

**文档结束**
