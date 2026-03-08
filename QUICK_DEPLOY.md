#!/bin/bash
# AIseek 阿里云快速部署指南
# 按顺序执行以下命令即可完成部署

set -e

echo "=========================================="
echo "🚀 AIseek 阿里云快速部署指南"
echo "=========================================="
echo ""
echo "本指南分为两部分："
echo "1. 本地准备（在 MacBook 上执行）"
echo "2. 服务器部署（在阿里云 ECS 上执行）"
echo ""
echo "=========================================="
echo ""

# ==================== 第一部分：本地准备 ====================
echo "📍 第一部分：本地准备（MacBook）"
echo "=========================================="
echo ""

# 1.1 确认项目目录
PROJECT_DIR="/Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1"
cd "${PROJECT_DIR}"

echo "✅ 项目目录：${PROJECT_DIR}"
echo "✅ 当前版本：$(git rev-parse --short HEAD)"
echo ""

# 1.2 确认配置已就绪
if [ -f "deploy/aliyun/.env.prod" ]; then
    echo "✅ 生产环境配置已就绪：deploy/aliyun/.env.prod"
    echo ""
    echo "⚠️  请确认以下配置已修改："
    echo "   - POSTGRES_PASSWORD"
    echo "   - REDIS_PASSWORD"
    echo "   - WORKER_SECRET"
    echo ""
else
    echo "❌ 生产环境配置不存在"
    echo "请先运行：./deploy-aliyun.sh"
    exit 1
fi

# 1.3 打包项目
echo "📦 正在打包项目..."
BACKUP_NAME="aiseek-deploy-$(date +%Y%m%d-%H%M%S).tgz"

tar --exclude='.git' \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.DS_Store' \
    --exclude='backups/*' \
    --exclude='logs/*' \
    --exclude='*.db' \
    --exclude='*.db-shm' \
    --exclude='*.db-wal' \
    -czf "${BACKUP_NAME}" .

echo "✅ 打包完成：${BACKUP_NAME}"
echo "   大小：$(du -h "${BACKUP_NAME}" | cut -f1)"
echo ""

# 1.4 提供上传指令
echo "=========================================="
echo "📤 请执行以下命令上传到服务器："
echo "=========================================="
echo ""
echo "  # 上传项目包"
echo "  scp ${BACKUP_NAME} root@<ALIYUN_ECS_IP>:/root/"
echo ""
echo "  # 上传部署脚本"
echo "  scp scripts/deploy-on-aliyun.sh root@<ALIYUN_ECS_IP>:/root/"
echo ""
echo "  # 登录服务器"
echo "  ssh root@<ALIYUN_ECS_IP>"
echo ""

read -p "按回车键继续查看服务器部署步骤..."

# ==================== 第二部分：服务器部署 ====================
cat << 'SERVER_STEPS'

==========================================
📍 第二部分：服务器部署（阿里云 ECS）
==========================================

登录服务器后，执行以下命令：

# 1. 确认文件已上传
ls -lh /root/aiseek-deploy-*.tgz
ls -lh /root/deploy-on-aliyun.sh

# 2. 执行部署脚本
cd /root
chmod +x deploy-on-aliyun.sh
bash deploy-on-aliyun.sh aiseek-deploy-*.tgz

# 3. 等待部署完成（约 2-3 分钟）
# 脚本会自动完成：
# - 解压到 /opt/aiseek
# - 启动 Docker 服务
# - 执行数据库迁移
# - 构建静态资源
# - 健康检查

# 4. 验证部署
curl -I https://aiseek.cool/
curl -I https://aiseek.cool/studio
curl -I https://aiseek.cool/admin

# 5. 查看服务状态
cd /opt/aiseek/deploy/aliyun
docker compose -f docker-compose.prod.yml ps

# 6. 查看日志（如有问题）
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f worker

==========================================
✅ 部署完成后，访问 https://aiseek.cool
==========================================

SERVER_STEPS

echo ""
echo "=========================================="
echo "📋 部署后检查清单"
echo "=========================================="
echo ""
echo "1. [ ] GitHub Secrets 配置（备份功能）"
echo "   - BACKUP_S3_BUCKET"
echo "   - AWS_ACCESS_KEY_ID"
echo "   - AWS_SECRET_ACCESS_KEY"
echo "   - AWS_DEFAULT_REGION"
echo ""
echo "2. [ ] 验证备份工作流"
echo "   gh workflow run backup_daily.yml"
echo ""
echo "3. [ ] 监控首小时运行状态"
echo "   - 5xx 错误率"
echo "   - 队列积压"
echo "   - CPU/内存使用"
echo ""
echo "=========================================="
echo "🎉 部署准备完成！"
echo "=========================================="
