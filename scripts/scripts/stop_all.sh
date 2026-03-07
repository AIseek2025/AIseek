#!/bin/bash

# AIseek 整合重构版 - 停止脚本

echo "🛑 停止AIseek服务..."

# 从PID文件读取进程ID
if [ -f ".pids" ]; then
    read WORKER_PID WEB_PID < .pids
    
    echo "📝 停止进程:"
    echo "   Worker PID: $WORKER_PID"
    echo "   Web PID: $WEB_PID"
    
    # 停止进程
    kill $WORKER_PID 2>/dev/null && echo "✅ Worker已停止" || echo "⚠️  Worker进程不存在"
    kill $WEB_PID 2>/dev/null && echo "✅ Web已停止" || echo "⚠️  Web进程不存在"
    
    # 删除PID文件
    rm -f .pids
else
    echo "🔍 未找到PID文件，尝试查找进程..."
    
    # 查找并停止相关进程
    pkill -f "python3 main.py" 2>/dev/null && echo "✅ 停止Worker进程"
    pkill -f "python3 app.py" 2>/dev/null && echo "✅ 停止Web进程"
    
    # 检查是否还有相关进程
    if pgrep -f "aiseek" > /dev/null || pgrep -f "main.py" > /dev/null || pgrep -f "app.py" > /dev/null; then
        echo "⚠️  仍有相关进程运行，强制停止..."
        pkill -9 -f "main.py" 2>/dev/null
        pkill -9 -f "app.py" 2>/dev/null
    fi
fi

echo ""
echo "🧹 清理完成"
echo "📊 检查进程状态:"
echo "   Worker: $(pgrep -f "main.py" > /dev/null && echo "运行中" || echo "已停止")"
echo "   Web:    $(pgrep -f "app.py" > /dev/null && echo "运行中" || echo "已停止")"