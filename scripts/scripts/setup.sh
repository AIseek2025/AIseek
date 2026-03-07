#!/bin/bash

# AIseek 整合重构版 - 安装和设置脚本

set -e

echo "="
echo "🔧 AIseek 整合重构版 - 安装设置"
echo "="

# 1. 检查环境
echo "1️⃣ 检查系统环境..."
if [ ! -f ".env" ]; then
    echo "📋 创建环境变量文件..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✅ 已创建 .env 文件"
        echo "   📝 请编辑 .env 文件并设置必要的环境变量"
        echo "   🔑 特别是 DEEPSEEK_KEY"
    else
        echo "❌ 未找到 .env.example 文件"
        exit 1
    fi
else
    echo "✅ .env 文件已存在"
fi

# 2. 检查依赖
echo ""
echo "2️⃣ 检查系统依赖..."
check_dep() {
    if command -v $1 >/dev/null 2>&1; then
        echo "   ✅ $1: $(which $1)"
    else
        echo "   ❌ 未安装 $1"
        return 1
    fi
}

check_dep python3 || {
    echo "   请安装 Python3:"
    echo "   - macOS: brew install python"
    echo "   - Ubuntu: sudo apt install python3 python3-pip"
    echo "   - 其他: https://www.python.org/downloads/"
    exit 1
}

check_dep ffmpeg || {
    echo "   请安装 FFmpeg:"
    echo "   - macOS: brew install ffmpeg"
    echo "   - Ubuntu: sudo apt install ffmpeg"
    echo "   - 其他: https://ffmpeg.org/download.html"
    exit 1
}

# 3. 创建目录结构
echo ""
echo "3️⃣ 创建目录结构..."
mkdir -p worker/{assets,outputs,data,core,models,utils}
mkdir -p web/{static,templates,data}
mkdir -p storage/{videos,audio,temp}
mkdir -p logs

echo "   📁 目录结构创建完成"

# 4. 检查占位视频
echo ""
echo "4️⃣ 检查占位视频..."
if [ ! -f "worker/assets/bg_placeholder.mp4" ]; then
    echo "   ⚠️  未找到占位视频"
    echo "   📝 请将背景视频文件放入: worker/assets/bg_placeholder.mp4"
    echo "   💡 可以使用以下命令创建简单占位视频:"
    echo "      ffmpeg -f lavfi -i color=c=blue:s=1280x720:d=10 -vf \"drawtext=text='AIseek Background':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=(h-text_h)/2\" -c:v libx264 -pix_fmt yuv420p worker/assets/bg_placeholder.mp4"
else
    echo "   ✅ 占位视频已存在"
fi

# 5. 设置脚本权限
echo ""
echo "5️⃣ 设置脚本权限..."
chmod +x scripts/*.sh
chmod +x worker/main.py
chmod +x web/app.py
echo "   ✅ 脚本权限设置完成"

# 6. 创建数据库
echo ""
echo "6️⃣ 初始化数据库..."
if [ -f "worker/data/aiseek.db" ]; then
    echo "   ✅ Worker数据库已存在"
else
    echo "   📝 将在首次启动时创建Worker数据库"
fi

if [ -f "web/data/web.db" ]; then
    echo "   ✅ Web数据库已存在"
else
    echo "   📝 将在首次启动时创建Web数据库"
fi

# 7. 显示下一步操作
echo ""
echo "="
echo "🎉 安装设置完成！"
echo "="
echo "📋 下一步操作:"
echo ""
echo "1. 编辑环境变量:"
echo "   nano .env"
echo "   # 设置 DEEPSEEK_KEY 和其他必要的配置"
echo ""
echo "2. 启动服务:"
echo "   ./scripts/start_all.sh"
echo ""
echo "3. 访问网站:"
echo "   http://localhost:5001"
echo ""
echo "4. 停止服务:"
echo "   ./scripts/stop_all.sh"
echo ""
echo "📚 更多信息请查看 README.md"
echo "="