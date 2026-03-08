#!/bin/bash
# AIseek 阿里云服务器一键部署脚本
# 使用方法：bash deploy-on-aliyun.sh aiseek-deploy-*.tgz

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
RELEASE_FILE="${1:-aiseek-deploy-*.tgz}"
DEPLOY_DIR="/opt/aiseek"
DOMAIN="aiseek.cool"

echo -e "${BLUE}=========================================="
echo "🚀 AIseek 阿里云一键部署"
echo "==========================================${NC}"
echo "域名：${DOMAIN}"
echo "部署目录：${DEPLOY_DIR}"
echo "发布包：${RELEASE_FILE}"
echo "时间：$(date '+%Y-%m-%d %H:%M:%S %Z')"
echo -e "${BLUE}==========================================${NC}"
echo ""

# 检查是否在 root 目录
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ 请使用 root 用户执行此脚本${NC}"
    exit 1
fi

# 检查发布包
if [ ! -f "/root/${RELEASE_FILE}" ]; then
    # 尝试通配符匹配
    RELEASE_FILE=$(ls -t /root/aiseek-deploy-*.tgz 2>/dev/null | head -1)
    if [ -z "${RELEASE_FILE}" ]; then
        echo -e "${RED}❌ 错误：找不到发布包${NC}"
        echo "请先从本地上传："
        echo -e "  ${YELLOW}scp aiseek-deploy-*.tgz root@<IP>:/root/${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✅ 找到发布包：${RELEASE_FILE}${NC}"
echo ""

# 步骤 1: 创建部署目录
echo -e "${YELLOW}[1/8] 创建部署目录...${NC}"
mkdir -p "${DEPLOY_DIR}"
cd "${DEPLOY_DIR}"
echo -e "${GREEN}✅ 部署目录：${DEPLOY_DIR}${NC}"
echo ""

# 步骤 2: 解压发布包
echo -e "${YELLOW}[2/8] 解压发布包...${NC}"
tar -xzf "${RELEASE_FILE}"
echo -e "${GREEN}✅ 解压完成${NC}"
echo ""

# 步骤 3: 检查配置文件
echo -e "${YELLOW}[3/8] 检查生产环境配置...${NC}"
if [ ! -f "deploy/aliyun/.env.prod" ]; then
    echo -e "${RED}❌ 错误：deploy/aliyun/.env.prod 不存在${NC}"
    exit 1
fi

# 检查关键配置
if grep -q "CHANGE_ME_STRONG_PASSWORD" deploy/aliyun/.env.prod; then
    echo -e "${YELLOW}⚠️  警告：密码仍为默认值${NC}"
    echo ""
    echo "请立即编辑配置文件："
    echo -e "  ${YELLOW}vim ${DEPLOY_DIR}/deploy/aliyun/.env.prod${NC}"
    echo ""
    echo "必须修改："
    echo "  - POSTGRES_PASSWORD"
    echo "  - REDIS_PASSWORD"
    echo "  - WORKER_SECRET"
    echo ""
    read -p "配置已完成？(y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "请先修改配置文件"
        exit 1
    fi
fi
echo -e "${GREEN}✅ 配置文件检查通过${NC}"
echo ""

# 步骤 4: 检查证书
echo -e "${YELLOW}[4/8] 检查 SSL 证书...${NC}"
CERT_DIR="deploy/aliyun/certs"
mkdir -p "${CERT_DIR}"

CERT_COUNT=$(ls -1 "${CERT_DIR}"/*.pem 2>/dev/null | wc -l)
if [ "$CERT_COUNT" -lt 2 ]; then
    echo -e "${YELLOW}⚠️  证书文件不足 (${CERT_COUNT}/2)${NC}"
    echo ""
    echo "选项 1: 使用 Let's Encrypt 自动申请"
    echo "选项 2: 手动上传证书文件"
    echo ""
    read -p "是否使用 Let's Encrypt 自动申请证书？(y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "安装 certbot..."
        apt update && apt install -y certbot
        
        echo "申请证书..."
        certbot certonly --standalone -d "${DOMAIN}" -d "www.${DOMAIN}" --non-interactive --agree-tos --email admin@${DOMAIN}
        
        echo "创建符号链接..."
        ln -sf /etc/letsencrypt/live/${DOMAIN}/fullchain.pem "${CERT_DIR}/fullchain.pem"
        ln -sf /etc/letsencrypt/live/${DOMAIN}/privkey.pem "${CERT_DIR}/privkey.pem"
        
        echo -e "${GREEN}✅ Let's Encrypt 证书已安装${NC}"
    else
        echo ""
        echo "请将证书文件放入：${CERT_DIR}/"
        echo "  - fullchain.pem (证书链)"
        echo "  - privkey.pem (私钥)"
        echo ""
        read -p "证书已放置？(y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "请先放置证书文件"
            exit 1
        fi
    fi
else
    echo -e "${GREEN}✅ 证书文件已就绪 (${CERT_COUNT} 个)${NC}"
fi
echo ""

# 步骤 5: 检查 Docker
echo -e "${YELLOW}[5/8] 检查 Docker 环境...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker 未安装${NC}"
    echo "请先安装 Docker："
    echo -e "  ${YELLOW}curl -fsSL https://get.docker.com | sh${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose 未安装${NC}"
    echo "请先安装 Docker Compose"
    exit 1
fi

echo -e "${GREEN}✅ Docker 环境正常${NC}"
echo "  Docker 版本：$(docker --version)"
echo "  Docker Compose 版本：$(docker compose version 2>/dev/null || docker-compose --version)"
echo ""

# 步骤 6: 启动服务
echo -e "${YELLOW}[6/8] 启动 Docker 服务...${NC}"
cd "${DEPLOY_DIR}/deploy/aliyun"

echo "构建并启动服务..."
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build

echo "等待服务启动 (30 秒)..."
sleep 30

echo "检查服务状态..."
docker compose -f docker-compose.prod.yml ps
echo -e "${GREEN}✅ 服务已启动${NC}"
echo ""

# 步骤 7: 数据库迁移
echo -e "${YELLOW}[7/8] 执行数据库迁移...${NC}"
cd "${DEPLOY_DIR}"

if [ -d ".venv" ]; then
    PYTHON_BIN="./.venv/bin/python"
else
    PYTHON_BIN="python3"
fi

PYTHONPATH=backend ${PYTHON_BIN} backend/scripts/deploy_bootstrap.py --migrate
echo -e "${GREEN}✅ 数据库迁移完成${NC}"
echo ""

# 步骤 8: 构建静态资源
echo -e "${YELLOW}[8/8] 构建静态资源...${NC}"
PYTHONPATH=backend ${PYTHON_BIN} backend/scripts/build_static_assets.py
echo -e "${GREEN}✅ 静态资源构建完成${NC}"
echo ""

# 健康检查
echo -e "${BLUE}=========================================="
echo "🏥 健康检查"
echo "==========================================${NC}"

sleep 5

# HTTP 检查
if curl -s -o /dev/null -w "%{http_code}" http://localhost/ | grep -q "200"; then
    echo -e "${GREEN}✅ HTTP 访问正常 (http://localhost/)${NC}"
else
    echo -e "${YELLOW}⚠️  HTTP 访问失败，请检查 Nginx 配置${NC}"
fi

# HTTPS 检查（如果有证书）
if [ -f "${CERT_DIR}/fullchain.pem" ]; then
    if curl -s -k -o /dev/null -w "%{http_code}" https://localhost/ | grep -q "200"; then
        echo -e "${GREEN}✅ HTTPS 访问正常 (https://localhost/)${NC}"
    else
        echo -e "${YELLOW}⚠️  HTTPS 访问失败，请检查证书配置${NC}"
    fi
fi

echo ""

# 完成总结
echo -e "${BLUE}=========================================="
echo "✅ 部署完成！"
echo "==========================================${NC}"
echo ""
echo "🌐 访问地址:"
echo "   首页：https://${DOMAIN}/"
echo "   创作台：https://${DOMAIN}/studio"
echo "   管理后台：https://${DOMAIN}/admin"
echo ""
echo "📊 查看服务状态:"
echo -e "   ${YELLOW}cd ${DEPLOY_DIR}/deploy/aliyun${NC}"
echo -e "   ${YELLOW}docker compose -f docker-compose.prod.yml ps${NC}"
echo ""
echo "📋 查看日志:"
echo -e "   ${YELLOW}docker compose -f docker-compose.prod.yml logs -f backend${NC}"
echo -e "   ${YELLOW}docker compose -f docker-compose.prod.yml logs -f worker${NC}"
echo ""
echo "🔄 重启服务:"
echo -e "   ${YELLOW}docker compose -f docker-compose.prod.yml restart${NC}"
echo ""
echo "🛑 停止服务:"
echo -e "   ${YELLOW}docker compose -f docker-compose.prod.yml down${NC}"
echo ""
echo -e "${BLUE}==========================================${NC}"
echo -e "${GREEN}🎉 AIseek 已成功部署到阿里云！${NC}"
echo -e "${BLUE}==========================================${NC}"
