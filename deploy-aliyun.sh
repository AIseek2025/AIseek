#!/bin/bash
# AIseek 阿里云部署脚本 - 首发当天执行
# 域名：aiseek.cool
# 版本：26ad570
# 生成时间：2026-03-08

set -e

echo "=========================================="
echo "🚀 AIseek 阿里云部署脚本"
echo "=========================================="
echo "域名：aiseek.cool"
echo "版本：$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
echo "时间：$(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "=========================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查是否在正确的目录
if [ ! -f "deploy/aliyun/docker-compose.prod.yml" ]; then
    echo -e "${RED}❌ 错误：请在 AIseek-Trae-v1 项目根目录执行此脚本${NC}"
    exit 1
fi

# 步骤 1: 检查配置文件
echo -e "\n${YELLOW}📋 步骤 1: 检查生产环境配置${NC}"
if [ ! -f "deploy/aliyun/.env.prod" ]; then
    echo -e "${RED}❌ 错误：deploy/aliyun/.env.prod 不存在${NC}"
    echo "请先复制并编辑配置文件："
    echo "  cp deploy/aliyun/.env.prod.example deploy/aliyun/.env.prod"
    echo "  vim deploy/aliyun/.env.prod"
    exit 1
fi

# 检查关键配置是否已修改
if grep -q "CHANGE_ME_STRONG_PASSWORD" deploy/aliyun/.env.prod; then
    echo -e "${YELLOW}⚠️  警告：密码仍为默认值，请修改 deploy/aliyun/.env.prod${NC}"
    echo "  - POSTGRES_PASSWORD"
    echo "  - REDIS_PASSWORD"
    echo "  - WORKER_SECRET"
    read -p "是否继续？(y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 步骤 2: 检查证书
echo -e "\n${YELLOW}📋 步骤 2: 检查 SSL 证书${NC}"
if [ ! -d "deploy/aliyun/certs" ]; then
    mkdir -p deploy/aliyun/certs
    echo -e "${GREEN}✅ 创建证书目录：deploy/aliyun/certs${NC}"
fi

CERT_COUNT=$(ls -1 deploy/aliyun/certs/*.pem 2>/dev/null | wc -l)
if [ "$CERT_COUNT" -lt 2 ]; then
    echo -e "${YELLOW}⚠️  警告：证书目录中少于 2 个.pem 文件${NC}"
    echo "请将证书文件放入 deploy/aliyun/certs/："
    echo "  - fullchain.pem (或 cert.pem)"
    echo "  - privkey.pem (或 key.pem)"
    read -p "是否继续？(y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo -e "${GREEN}✅ 证书文件已就绪 (${CERT_COUNT} 个文件)${NC}"
fi

# 步骤 3: 打包项目
echo -e "\n${YELLOW}📋 步骤 3: 打包项目文件${NC}"
BACKUP_NAME="aiseek-deploy-$(date +%Y%m%d-%H%M%S).tgz"
echo "创建打包文件：${BACKUP_NAME}"

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

echo -e "${GREEN}✅ 打包完成：${BACKUP_NAME} ($(du -h "${BACKUP_NAME}" | cut -f1))${NC}"

# 步骤 4: 提供上传指令
echo -e "\n${YELLOW}📋 步骤 4: 上传到阿里云 ECS${NC}"
echo "请执行以下命令上传到服务器（替换 <ALIYUN_ECS_IP> 为你的服务器 IP）："
echo ""
echo "  scp ${BACKUP_NAME} root@<ALIYUN_ECS_IP>:/root/"
echo ""
read -p "按回车键继续..."

# 步骤 5: 生成服务器执行脚本
echo -e "\n${YELLOW}📋 步骤 5: 生成服务器执行脚本${NC}"
cat > /tmp/aiseek-deploy-remote.sh << 'REMOTE_SCRIPT'
#!/bin/bash
# AIseek 阿里云服务器部署脚本
# 在 ECS 上执行

set -e

echo "=========================================="
echo "🚀 AIseek 阿里云服务器部署"
echo "=========================================="

RELEASE_FILE="${1:-aiseek-deploy.tgz}"
DEPLOY_DIR="/opt/aiseek"

# 检查文件
if [ ! -f "/root/${RELEASE_FILE}" ]; then
    echo "❌ 错误：找不到 /root/${RELEASE_FILE}"
    echo "请先从本地上传："
    echo "  scp aiseek-deploy-*.tgz root@<IP>:/root/"
    exit 1
fi

# 创建部署目录
echo "📁 创建部署目录：${DEPLOY_DIR}"
mkdir -p "${DEPLOY_DIR}"
cd "${DEPLOY_DIR}"

# 解压
echo "📦 解压发布包..."
tar -xzf "/root/${RELEASE_FILE}"

# 检查配置文件
if [ ! -f "deploy/aliyun/.env.prod" ]; then
    echo "❌ 错误：deploy/aliyun/.env.prod 不存在"
    exit 1
fi

# 提示修改配置
echo ""
echo "⚙️  请检查并修改配置："
echo "  cd ${DEPLOY_DIR}/deploy/aliyun"
echo "  vim .env.prod"
echo ""
echo "必须修改："
echo "  - POSTGRES_PASSWORD"
echo "  - REDIS_PASSWORD"
echo "  - WORKER_SECRET"
echo "  - WEB_URL=https://aiseek.cool"
echo "  - CALLBACK_URL=https://aiseek.cool/callback"
echo ""
read -p "配置已完成？(y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "请先修改配置文件"
    exit 1
fi

# 放置证书
echo ""
echo "🔐 请确保证书文件已放置："
echo "  ${DEPLOY_DIR}/deploy/aliyun/certs/"
echo "  - fullchain.pem"
echo "  - privkey.pem"
read -p "证书已就绪？(y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "请先放置证书文件"
    exit 1
fi

# 启动服务
echo ""
echo "🚀 启动 Docker 服务..."
cd "${DEPLOY_DIR}/deploy/aliyun"
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build

# 等待服务启动
echo ""
echo "⏳ 等待服务启动 (30 秒)..."
sleep 30

# 检查服务状态
echo ""
echo "📊 服务状态："
docker compose -f docker-compose.prod.yml ps

# 数据库迁移
echo ""
echo "🗄️  执行数据库迁移..."
cd "${DEPLOY_DIR}"
PYTHONPATH=backend ./.venv/bin/python backend/scripts/deploy_bootstrap.py --migrate

# 构建静态资源
echo ""
echo "📦 构建静态资源..."
PYTHONPATH=backend ./.venv/bin/python backend/scripts/build_static_assets.py

# 健康检查
echo ""
echo "🏥 健康检查..."
curl -I https://localhost/ || echo "⚠️  HTTPS 检查失败，请检查证书配置"
curl -I http://localhost/ || echo "⚠️  HTTP 检查失败"

echo ""
echo "=========================================="
echo "✅ 部署完成！"
echo "=========================================="
echo ""
echo "访问地址：https://aiseek.cool"
echo "管理后台：https://aiseek.cool/admin"
echo "创作台：https://aiseek.cool/studio"
echo ""
echo "查看日志："
echo "  docker compose -f docker-compose.prod.yml logs -f backend"
echo "  docker compose -f docker-compose.prod.yml logs -f worker"
echo ""
REMOTE_SCRIPT

chmod +x /tmp/aiseek-deploy-remote.sh
echo -e "${GREEN}✅ 服务器部署脚本已生成：/tmp/aiseek-deploy-remote.sh${NC}"

# 步骤 6: 提供完整指令
echo -e "\n${YELLOW}📋 完整部署流程${NC}"
cat << 'INSTRUCTIONS'

==========================================
📝 部署指令汇总
==========================================

【1. 本地执行】（已完成）
   ./deploy-aliyun.sh

【2. 上传到服务器】
   scp aiseek-deploy-*.tgz root@<ALIYUN_ECS_IP>:/root/
   scp /tmp/aiseek-deploy-remote.sh root@<ALIYUN_ECS_IP>:/root/

【3. 登录服务器执行】
   ssh root@<ALIYUN_ECS_IP>
   cd /root
   bash aiseek-deploy-remote.sh aiseek-deploy-*.tgz

【4. 验证部署】
   curl -I https://aiseek.cool/
   curl -I https://aiseek.cool/studio
   curl -I https://aiseek.cool/admin

【5. GitHub Actions 备份配置】
   在 GitHub 仓库设置中添加 Secrets：
   - BACKUP_S3_BUCKET
   - AWS_ACCESS_KEY_ID
   - AWS_SECRET_ACCESS_KEY
   - AWS_DEFAULT_REGION
   - BACKUP_S3_PREFIX (可选)
   - BACKUP_S3_ENDPOINT_URL (可选，如使用 OSS)

==========================================
INSTRUCTIONS

echo -e "\n${GREEN}✅ 部署准备完成！${NC}"
echo "下一步：上传文件到阿里云 ECS 并执行远程部署脚本"
