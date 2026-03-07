#!/bin/bash

echo "=============================================="
echo "🐳 Docker Desktop 安装脚本"
echo "=============================================="
echo ""

# 检查是否已安装
if command -v docker &> /dev/null; then
    echo "✅ Docker 已安装!"
    docker --version
    exit 0
fi

echo "📥 开始安装 Docker Desktop..."
echo ""
echo "⚠️  需要输入 Mac 管理员密码"
echo ""

# 使用 brew 安装
brew install --cask docker

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Docker Desktop 安装成功!"
    echo ""
    echo "📋 下一步操作:"
    echo "1. 打开 Applications → Docker.app"
    echo "2. 首次启动需要输入密码并同意条款"
    echo "3. 等待 Docker 初始化完成（状态栏显示绿色）"
    echo "4. 返回终端继续部署"
    echo ""
else
    echo ""
    echo "❌ 安装失败"
    echo "请手动访问 https://docker.com 下载安装"
    exit 1
fi
