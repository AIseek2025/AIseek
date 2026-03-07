#!/bin/bash

# AIseek-Trae-v1 重启 Worker 脚本
# 用于应用新的通义万相 API Key 配置

set -e

echo "🔄 AIseek Worker 重启脚本"
echo "="

cd /Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1

# 停止现有进程
echo "🛑 停止现有进程..."
if [ -f ".pids" ]; then
    PIDS=$(cat .pids)
    kill $PIDS 2>/dev/null || true
    rm -f .pids
    echo "✅ 已停止旧进程"
else
    # 尝试查找并杀死相关进程
    pkill -f "python.*main.py" 2>/dev/null || true
    echo "✅ 已清理旧进程"
fi

# 等待进程完全停止
sleep 2

# 验证.env 文件
echo "📋 验证.env 配置..."
if [ ! -f ".env" ]; then
    echo "❌ .env 文件不存在"
    exit 1
fi

# 检查 API Key 是否已配置
if grep -q "COVER_WAN_API_KEY=sk-2636871cd53642758545e6d8b42c632c" .env; then
    echo "✅ 通义万相 API Key 已配置"
else
    echo "❌ 通义万相 API Key 未正确配置"
    echo "   请确保 .env 中包含:"
    echo "   COVER_WAN_API_KEY=sk-2636871cd53642758545e6d8b42c632c"
    exit 1
fi

# 启动 Worker
echo "🚀 启动 Worker 服务..."
cd worker

# 激活虚拟环境
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "❌ 虚拟环境不存在"
    exit 1
fi

# 设置 PYTHONPATH
export PYTHONPATH="$(pwd):$PYTHONPATH"

# 后台启动 (main.py 在 app 目录)
cd app
python3 main.py &
WORKER_PID=$!
echo "📝 Worker PID: $WORKER_PID"

cd ../..

# 保存 PID
echo "$WORKER_PID" > .pids

# 等待启动
echo "⏳ 等待 Worker 启动..."
sleep 5

# 健康检查
WORKER_PORT=${WORKER_PORT:-8000}
if curl -s http://localhost:${WORKER_PORT}/health > /dev/null 2>&1; then
    echo "✅ Worker 启动成功！"
    echo ""
    echo "📊 服务信息:"
    echo "   Worker: http://localhost:${WORKER_PORT}/health"
    echo ""
    echo "🔑 已配置 API Key:"
    echo "   - COVER_WAN_API_KEY: sk-2636***632c ✅"
    echo "   - DASHSCOPE_API_KEY: sk-2636***632c ✅"
    echo ""
    echo "🎯 下次生成封面时将使用通义万相 wan2.6-t2i 模型"
    echo "   生成的封面将是 PNG 格式，分辨率为 1536x1024"
else
    echo "❌ Worker 启动失败"
    echo "   请查看日志："
    echo "   cd worker && tail -f logs/worker.log"
    exit 1
fi

echo "="
echo "✅ 重启完成！"
