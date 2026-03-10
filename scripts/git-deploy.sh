#!/bin/bash
# AIseek 标准发布流程 - Git 部署
# 使用方法：bash scripts/git-deploy.sh

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=========================================="
echo "🚀 AIseek 标准发布流程 (Git)"
echo "==========================================${NC}"
echo "时间：$(date '+%Y-%m-%d %H:%M:%S %Z')"
echo -e "${BLUE}==========================================${NC}"
echo ""

# 步骤 1: 检查 Git 状态
echo -e "${YELLOW}[1/6] 检查 Git 状态...${NC}"
git status --short
read -p "确认提交以上更改？(y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ 发布取消"
    exit 1
fi

# 步骤 2: 提交并推送
echo -e "${YELLOW}[2/6] 提交并推送到 GitHub...${NC}"
git add -A
git commit -m "deploy: $(date '+%Y-%m-%d %H:%M') - 常规发布"
git push origin main
echo -e "${GREEN}✅ 代码已推送到 GitHub${NC}"
echo ""

# 步骤 3: SSH 登录服务器拉取代码
echo -e "${YELLOW}[3/6] 服务器拉取最新代码...${NC}"
ssh aliyun "cd /root/AIseek-Trae-v1 && git pull origin main && echo '✅ 代码已更新'"
echo ""

# 步骤 4: 重启服务
echo -e "${YELLOW}[4/6] 重启 Backend 和 Nginx 服务...${NC}"
ssh aliyun "cd /root/AIseek-Trae-v1/deploy/aliyun && docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build backend nginx"
echo -e "${GREEN}✅ 服务已重启${NC}"
echo ""

# 步骤 5: 等待服务启动
echo -e "${YELLOW}[5/6] 等待服务启动 (10 秒)...${NC}"
sleep 10

# 步骤 6: 健康检查
echo -e "${YELLOW}[6/6] 健康检查...${NC}"
ssh aliyun "
    echo '检查容器状态...'
    docker ps --filter 'name=aliyun' --format 'table {{.Names}}\t{{.Status}}'
    
    echo ''
    echo '检查 HTTP 访问...'
    curl -s -o /dev/null -w 'HTTP 状态码：%{http_code}\n' http://localhost/
    
    echo ''
    echo '检查静态文件...'
    curl -s -o /dev/null -w 'studio.js 状态码：%{http_code}\n' http://localhost/static/js/app/studio.js
"

echo ""
echo -e "${BLUE}=========================================="
echo "✅ 发布完成！"
echo "==========================================${NC}"
echo ""
echo "🌐 访问地址:"
echo "   首页：https://www.aiseek.cool/"
echo "   创作台：https://www.aiseek.cool/studio"
echo ""
echo "📋 常用命令:"
echo "   查看日志：ssh aliyun 'cd /root/AIseek-Trae-v1/deploy/aliyun && docker compose logs -f backend'"
echo "   重启服务：ssh aliyun 'cd /root/AIseek-Trae-v1/deploy/aliyun && docker compose restart'"
echo "   查看状态：ssh aliyun 'cd /root/AIseek-Trae-v1/deploy/aliyun && docker compose ps'"
echo ""
echo -e "${GREEN}🎉 发布成功！${NC}"
