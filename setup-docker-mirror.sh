#!/bin/bash

echo "=============================================="
echo "🐳 配置 Docker 镜像加速器"
echo "=============================================="
echo ""

# Docker Desktop 配置文件路径
DOCKER_CONFIG="$HOME/.docker/daemon.json"

# 创建配置
cat > "$DOCKER_CONFIG" << 'EOF'
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://docker.1panel.live",
    "https://hub.rat.dev",
    "https://dhub.kubesre.xyz"
  ]
}
EOF

echo "✅ Docker 配置文件已创建：$DOCKER_CONFIG"
echo ""
echo "📋 请手动重启 Docker Desktop:"
echo "1. 点击顶部状态栏 Docker 图标"
echo "2. 选择 'Quit Docker Desktop'"
echo "3. 重新打开 Applications → Docker.app"
echo ""
echo "或者执行命令重启:"
echo "  colima restart  (如果使用 colima)"
echo ""
echo "重启后再次执行:"
echo "  docker-compose up --build"
