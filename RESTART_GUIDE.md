# Trae-v1 重启指南

## 快速重启命令

```bash
# 进入项目目录
cd /Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1

# 方法 1：使用脚本（推荐）
./scripts/scripts/stop_all.sh
./scripts/scripts/start_all.sh

# 方法 2：手动重启 Worker
cd worker
source venv/bin/activate
pkill -f "uvicorn.*8000"
sleep 1
nohup uvicorn app.main:app --reload --port 8000 &

# 验证服务
curl http://localhost:8000/health
```

## 服务信息

- **Worker 端口**: 8000
- **健康检查**: http://localhost:8000/health
- **项目目录**: `/Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1`

## 常见问题

1. **虚拟环境不存在**: `python3 -m venv venv`
2. **缺少依赖**: `pip install -r requirements.txt`
3. **端口被占用**: `lsof -ti:8000 | xargs kill -9`
4. **缺少 ffmpeg**: `brew install ffmpeg`
