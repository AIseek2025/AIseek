# 通义万相 API Key 配置说明

> **配置时间**: 2026-03-03 00:45  
> **API Key**: `sk-2636871cd53642758545e6d8b42c632c`  
> **模型**: 通义万相 wan2.6-t2i

---

## ✅ 已完成的配置

### 1. 环境变量已添加到 `.env` 文件

```bash
# 封面生成 API 配置
COVER_WAN_API_KEY=sk-2636871cd53642758545e6d8b42c632c
DASHSCOPE_API_KEY=sk-2636871cd53642758545e6d8b42c632c

COVER_WAN_MODEL=wan2.6-t2i
COVER_WAN_BASE_URL=https://dashscope.aliyuncs.com/api/v1

COVER_DEFAULT_WIDTH=1536
COVER_DEFAULT_HEIGHT=1024
COVER_DEFAULT_QUALITY=high
COVER_DEFAULT_FORMAT=png
```

---

## 🔄 需要重启服务

### 方法 1: 使用重启脚本（推荐）

```bash
cd /Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1
./restart-worker.sh
```

### 方法 2: 手动重启

```bash
# 1. 停止现有进程
cd /Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1
./scripts/stop_all.sh

# 2. 重新启动
./scripts/scripts/start_all.sh
```

### 方法 3: 如果运行在 Docker

```bash
# 重启 worker 容器
docker-compose restart worker

# 或者重新构建
docker-compose up -d --build worker
```

---

## 🔍 验证配置

### 检查环境变量

```bash
cd /Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1

# 检查 API Key 是否已配置
grep "COVER_WAN_API_KEY" .env
grep "DASHSCOPE_API_KEY" .env
```

**预期输出**:
```
COVER_WAN_API_KEY=sk-2636871cd53642758545e6d8b42c632c
DASHSCOPE_API_KEY=sk-2636871cd53642758545e6d8b42c632c
```

### 测试 API Key

```bash
# 测试通义万相 API
curl -X POST https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation \
  -H "Authorization: Bearer sk-2636871cd53642758545e6d8b42c632c" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "wan2.6-t2i",
    "input": {
      "prompt": "test"
    },
    "parameters": {
      "size": "1024*1024",
      "n": 1
    }
  }'
```

**成功响应**应该包含 `output.results[0].url`。

### 检查 Worker 状态

```bash
# 查看 Worker 健康状态
curl http://localhost:8000/health

# 查看 Worker 日志
tail -f /Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/worker/logs/worker.log
```

---

## 📊 配置效果验证

### 配置前 vs 配置后

| 项目 | 配置前 | 配置后 |
|------|--------|--------|
| **封面生成方式** | 视频抽帧（兜底） | 通义万相 AI 生成 |
| **封面尺寸** | 720x1280 | 1536x1024 |
| **封面格式** | .jpg | .png |
| **封面质量** | 一般 | 高清 AI 生成 |

### 如何判断是否使用了通义万相

1. **查看生成的封面文件**:
   - 如果是 `.png` 格式 → ✅ 使用了通义万相
   - 如果是 `.jpg` 格式且 720x1280 → ❌ 仍是抽帧兜底

2. **查看 Worker 日志**:
   ```bash
   tail -f worker/logs/worker.log | grep -i "wanx\|cover"
   ```
   
   应该看到类似：
   ```
   [INFO] Using Wanx provider for cover generation
   [INFO] Generated cover: cover_xxx.png (1536x1024)
   ```

---

## 🛠️ 故障排查

### 问题 1: API Key 未生效

**症状**: 生成的封面仍然是 720x1280 .jpg

**解决**:
1. 确保已重启 Worker 进程
2. 检查 Worker 日志中是否有 API Key 加载信息
3. 确认 Worker 进程读取的是正确的 `.env` 文件

### 问题 2: API 调用失败

**症状**: Worker 日志显示 API 错误

**可能原因**:
- API Key 无效或过期
- 账户余额不足
- 网络问题

**解决**:
```bash
# 测试 API Key
curl -X POST https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation \
  -H "Authorization: Bearer sk-2636871cd53642758545e6d8b42c632c" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "wan2.6-t2i",
    "input": {"prompt": "test"}
  }'
```

### 问题 3: Worker 无法启动

**症状**: 启动脚本报错

**解决**:
```bash
# 查看详细错误
cd worker
source .venv/bin/activate
python3 main.py

# 查看日志
tail -f logs/worker.log
```

---

## 📝 配置清单

- [x] `.env` 文件添加 `COVER_WAN_API_KEY`
- [x] `.env` 文件添加 `DASHSCOPE_API_KEY`
- [x] 配置通义万相模型参数
- [x] 创建重启脚本 `restart-worker.sh`
- [ ] **重启 Worker 进程** ← 需要执行
- [ ] **验证封面生成** ← 需要测试

---

## 🎯 下一步

1. **执行重启**:
   ```bash
   ./restart-worker.sh
   ```

2. **测试生成**:
   - 提交一个视频生成任务
   - 等待任务完成
   - 检查生成的封面文件

3. **验证结果**:
   - 封面应该是 `.png` 格式
   - 分辨率应该是 `1536x1024`
   - 质量应该明显高于抽帧

---

## 📞 相关文档

- [通义万相 API 文档](./api/wan2.6-t2i-cover-generation-api.md)
- [占位视频 API 文档](./api/placeholder-video-api-integration.md)
- [封面生成 API 对比](./api/cover-generation-api-integration.md)

---

**配置完成时间**: 2026-03-03 00:45  
**最后更新**: 2026-03-03 00:45
