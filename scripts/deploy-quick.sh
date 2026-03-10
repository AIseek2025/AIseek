#!/bin/bash
# AIseek 快速发布流程 - 一键部署
# 使用方法：bash scripts/deploy-quick.sh [commit_message]

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

COMMIT_MSG="${1:-deploy: $(date '+%Y-%m-%d %H:%M') - 快速发布}"

echo -e "${BLUE}=========================================="
echo "⚡ AIseek 快速发布"
echo "==========================================${NC}"
echo "提交信息：${COMMIT_MSG}"
echo "时间：$(date '+%Y-%m-%d %H:%M:%S %Z')"
echo -e "${BLUE}==========================================${NC}"
echo ""

# 1. 提交并推送
echo -e "${YELLOW}[1/3] 提交并推送代码...${NC}"
git add -A
git commit -m "${COMMIT_MSG}"
git push origin main
echo -e "${GREEN}✅ 代码已推送${NC}"
echo ""

# 2. 创建发布包并上传
echo -e "${YELLOW}[2/3] 创建发布包并上传到服务器...${NC}"
cd /tmp
tar --exclude='__pycache__' --exclude='*.pyc' --exclude='*.log' --exclude='.git' \
    --exclude='backend/static' --exclude='backend/venv' --exclude='backend/logs' \
    -czf aiseek-deploy-$(date +%Y%m%d_%H%M%S).tgz \
    backend/app backend/alembic backend/templates backend/*.py backend/Dockerfile backend/requirements*.txt \
    worker/app worker/*.py worker/requirements*.txt \
    deploy docker-compose.yml
LATEST_PKG=$(ls -t aiseek-deploy-*.tgz | head -1)
scp "$LATEST_PKG" aliyun:/root/ 2>&1 | grep -v "Warning:"
echo -e "${GREEN}✅ 发布包已上传${NC}"
echo ""

# 3. 服务器解压并重启
echo -e "${YELLOW}[3/3] 服务器解压并发布包并重启服务...${NC}"
ssh aliyun "
    cd /root
    LATEST_PKG=\$(ls -t aiseek-deploy-*.tgz | head -1)
    tar -xzf \$LATEST_PKG -C AIseek-Trae-v1/
    cd AIseek-Trae-v1/deploy/aliyun
    docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build backend nginx
    sleep 5
    docker ps --filter 'name=aliyun' --format '{{.Names}}: {{.Status}}'
" 2>&1 | grep -v "Warning:"
echo -e "${GREEN}✅ 服务已重启${NC}"
echo ""

# 4. 健康检查
echo -e "${YELLOW}[4/4] 健康检查...${NC}"
HTTP_CODE=$(ssh aliyun "curl -s -o /dev/null -w '%{http_code}' http://localhost/")
if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ HTTP 访问正常 (状态码：${HTTP_CODE})${NC}"
else
    echo -e "${RED}⚠️  HTTP 访问异常 (状态码：${HTTP_CODE})${NC}"
fi

echo ""
echo -e "${GREEN}🎉 发布完成！${NC}"
echo "访问：https://www.aiseek.cool/"
