#!/bin/bash

# AIseek 虚拟环境配置进度检查脚本
# 可以直接运行或定时执行

echo "🔍 AIseek 虚拟环境配置进度检查"
echo "="
echo "检查时间：$(date '+%Y-%m-%d %H:%M:%S')"
echo ""

cd /Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1

# 1. 检查虚拟环境
echo "📦 1. 虚拟环境状态"
if [ -d "worker/.venv" ]; then
    echo "   ✅ 虚拟环境已创建"
    echo "   位置：$(pwd)/worker/.venv"
else
    echo "   ❌ 虚拟环境未创建"
fi
echo ""

# 2. 检查依赖安装
echo "📦 2. 依赖安装状态"
if [ -d "worker/.venv" ]; then
    source worker/.venv/bin/activate
    PKG_COUNT=$(pip list 2>/dev/null | wc -l)
    echo "   ✅ 已安装 $PKG_COUNT 个包"
    echo "   主要包:"
    pip list 2>/dev/null | grep -E "fastapi|celery|openai|edge-tts|boto3" | head -5 | sed 's/^/      /'
else
    echo "   ❌ 虚拟环境不存在"
fi
echo ""

# 3. 检查 API Key 配置
echo "🔑 3. API Key 配置"
if [ -f ".env" ]; then
    if grep -q "COVER_WAN_API_KEY=sk-2636871cd53642758545e6d8b42c632c" .env; then
        echo "   ✅ 通义万相 API Key 已配置"
    else
        echo "   ❌ 通义万相 API Key 未配置或错误"
    fi
    
    if grep -q "DASHSCOPE_API_KEY=sk-2636871cd53642758545e6d8b42c632c" .env; then
        echo "   ✅ DASHSCOPE_API_KEY 已配置"
    else
        echo "   ❌ DASHSCOPE_API_KEY 未配置"
    fi
else
    echo "   ❌ .env 文件不存在"
fi
echo ""

# 4. 检查 Worker 进程
echo "🚀 4. Worker 服务状态"
WORKER_PID=$(lsof -ti :8000 2>/dev/null | head -1)
if [ -n "$WORKER_PID" ]; then
    echo "   ✅ Worker 正在运行 (PID: $WORKER_PID)"
    
    # 健康检查
    HEALTH=$(curl -s http://localhost:8000/health 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo "   ✅ 健康检查通过"
        echo "   响应：$HEALTH"
    else
        echo "   ⚠️  健康检查失败（可能需要授权）"
    fi
else
    echo "   ❌ Worker 未运行"
    echo "   启动命令：./restart-worker.sh"
fi
echo ""

# 5. 检查错误日志
echo "📋 5. 错误日志检查"
if [ -f "worker/app/logs/worker.log" ]; then
    ERROR_COUNT=$(grep -i "error\|exception\|failed" worker/app/logs/worker.log 2>/dev/null | tail -5 | wc -l)
    if [ $ERROR_COUNT -gt 0 ]; then
        echo "   ⚠️  发现 $ERROR_COUNT 条错误日志"
        echo "   最近错误:"
        grep -i "error\|exception\|failed" worker/app/logs/worker.log 2>/dev/null | tail -3 | sed 's/^/      /'
    else
        echo "   ✅ 未发现明显错误"
    fi
else
    echo "   ⚠️  日志文件不存在"
fi
echo ""

# 6. 总结
echo "="
echo "📊 配置总结"
echo "="

COMPLETED=0
TOTAL=5

[ -d "worker/.venv" ] && COMPLETED=$((COMPLETED+1))
[ $(pip list 2>/dev/null | wc -l) -gt 10 ] && COMPLETED=$((COMPLETED+1))
grep -q "COVER_WAN_API_KEY=sk-2636871cd53642758545e6d8b42c632c" .env 2>/dev/null && COMPLETED=$((COMPLETED+1))
[ -n "$WORKER_PID" ] && COMPLETED=$((COMPLETED+1))
[ $ERROR_COUNT -eq 0 ] && COMPLETED=$((COMPLETED+1))

echo "完成度：$COMPLETED/$TOTAL"

if [ $COMPLETED -eq $TOTAL ]; then
    echo ""
    echo "🎉 配置完成！所有检查通过！"
    echo ""
    echo "✅ 虚拟环境：已创建"
    echo "✅ 依赖安装：已完成"
    echo "✅ API Key: 已配置"
    echo "✅ Worker 服务：运行中"
    echo "✅ 错误日志：无异常"
    echo ""
    echo "🎯 下次生成封面时将使用通义万相 wan2.6-t2i 模型"
    echo "   生成的封面将是 PNG 格式，分辨率为 1536x1024"
elif [ $COMPLETED -ge 3 ]; then
    echo ""
    echo "⚠️  配置基本完成，但还有问题需要解决"
    echo "   请检查上面的错误信息"
else
    echo ""
    echo "❌ 配置未完成，需要继续处理"
    echo "   请检查上面的错误信息"
fi

echo "="
