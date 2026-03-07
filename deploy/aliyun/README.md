# 阿里云生产部署（单机 Docker）

## 1. 准备
- ECS：建议 4C8G 起步，系统盘 >= 80G
- 域名已解析到 ECS 公网 IP
- 已安装 Docker / Docker Compose

## 2. 配置环境变量
```bash
cd deploy/aliyun
cp .env.prod.example .env.prod
```

必须修改：
- `POSTGRES_PASSWORD`
- `REDIS_PASSWORD`
- `WORKER_SECRET`
- `WEB_URL`
- `CALLBACK_URL`

## 3. 证书
把证书文件放到 `deploy/aliyun/certs/`（与 `nginx.conf` 的路径一致）。

## 4. 启动
```bash
cd deploy/aliyun
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

## 5. 发布前初始化（建议）
```bash
cd /path/to/repo
PYTHONPATH=backend ./.venv/bin/python backend/scripts/deploy_bootstrap.py --migrate
PYTHONPATH=backend ./.venv/bin/python backend/scripts/build_static_assets.py
```

## 6. 健康检查
- `curl -I https://your-domain.com/`
- 打开：
  - `/`
  - `/studio`
  - `/admin`

## 7. 安全建议
- ECS 安全组只放行 `80/443`，关闭 `5432/6379` 公网访问
- 定期轮换 `WORKER_SECRET`、数据库/Redis 密码
- 备份任务建议开启远端存储（S3/R2/OSS 兼容）
