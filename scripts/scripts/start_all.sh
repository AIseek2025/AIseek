#!/bin/bash

# AIseek 整合重构版 - 完整启动脚本
# 基于AIseek 1.0版本-Trae版优秀设计

set -e

echo "="
echo "🤖 AIseek 整合重构版 - 启动脚本"
echo "="

# 检查环境变量
if [ ! -f ".env" ]; then
    echo "❌ 未找到 .env 文件"
    echo "📋 请复制 .env.example 并配置必要的环境变量："
    echo "   cp .env.example .env"
    echo "   # 编辑 .env 文件，设置 DEEPSEEK_KEY 等"
    exit 1
fi

# 检查依赖
check_dependency() {
    if ! command -v $1 &> /dev/null; then
        echo "❌ 需要安装 $1"
        echo "   请运行: $2"
        exit 1
    fi
}

echo "🔍 检查依赖..."
check_dependency "python3" "brew install python 或访问 https://www.python.org/"
check_dependency "ffmpeg" "brew install ffmpeg"
check_dependency "git" "brew install git"

echo "✅ 依赖检查通过"

# 创建必要的目录
echo "📁 创建目录..."
mkdir -p worker/assets worker/outputs worker/data
mkdir -p web/static web/templates web/data

# 检查占位视频
if [ ! -f "worker/assets/bg_placeholder.mp4" ]; then
    echo "⚠️  未找到占位视频: worker/assets/bg_placeholder.mp4"
    echo "   请在该路径放入一个背景视频文件"
    echo "   可以使用命令下载示例:"
    echo "   curl -L -o worker/assets/bg_placeholder.mp4 'https://示例视频URL'"
    read -p "是否继续？(y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 启动Worker
echo "🚀 启动Worker..."
cd worker

# 创建虚拟环境
if [ ! -d ".venv" ]; then
    echo "📦 创建Python虚拟环境..."
    python3 -m venv .venv
fi

# 激活虚拟环境
source .venv/bin/activate

# 安装依赖
echo "📦 安装Python依赖..."
pip install --upgrade pip
pip install -r requirements.txt

# 在后台启动Worker
echo "🔧 启动Worker服务 (端口: ${WORKER_PORT:-5000})..."
python3 main.py &
WORKER_PID=$!
echo "📝 Worker PID: $WORKER_PID"

cd ..

# 等待Worker启动
echo "⏳ 等待Worker启动..."
sleep 3

# 检查Worker健康状态
if curl -s http://localhost:${WORKER_PORT:-5000}/health > /dev/null; then
    echo "✅ Worker启动成功"
else
    echo "❌ Worker启动失败"
    kill $WORKER_PID 2>/dev/null || true
    exit 1
fi

# 启动Web
echo "🌐 启动Web网站..."
cd web

# 创建虚拟环境
if [ ! -d ".venv" ]; then
    echo "📦 创建Python虚拟环境..."
    python3 -m venv .venv
fi

# 激活虚拟环境
source .venv/bin/activate

# 安装依赖
echo "📦 安装Python依赖..."
pip install --upgrade pip
pip install -r requirements.txt

# 在后台启动Web
echo "🔧 启动Web服务 (端口: ${WEB_PORT:-5001})..."
python3 app.py &
WEB_PID=$!
echo "📝 Web PID: $WEB_PID"

cd ..

# 等待Web启动
echo "⏳ 等待Web启动..."
sleep 3

# 检查Web健康状态
if curl -s http://localhost:${WEB_PORT:-5001}/api/health > /dev/null; then
    echo "✅ Web启动成功"
else
    echo "❌ Web启动失败"
    kill $WORKER_PID $WEB_PID 2>/dev/null || true
    exit 1
fi

echo ""
echo "="
echo "🎉 AIseek 整合重构版启动完成！"
echo "="
echo "📊 服务状态:"
echo "   Worker: http://localhost:${WORKER_PORT:-5000}/health"
echo "   Web:    http://localhost:${WEB_PORT:-5001}/api/health"
echo ""
echo "🌐 访问地址:"
echo "   🔗 http://localhost:${WEB_PORT:-5001}"
echo ""
echo "📋 可用功能:"
echo "   - 提交长文生成视频"
echo "   - 查看任务状态"
echo "   - 播放生成的视频"
echo ""
echo "🛑 停止服务:"
echo "   运行: ./scripts/stop_all.sh"
echo "   或按 Ctrl+C"
echo "="

# 保存PID文件
echo "$WORKER_PID $WEB_PID" > .pids

# 等待用户中断
trap 'echo "正在停止服务..."; kill $WORKER_PID $WEB_PID 2>/dev/null || true; rm -f .pids; exit 0' INT TERM

wait