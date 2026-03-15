# API Keys 配置指南

> ⚠️ **安全提醒**：请勿将真实 API Key 提交到 Git 仓库。`.env.prod` 已加入 `.gitignore`。

---

## 一、环境变量清单

在 `deploy/aliyun/.env.prod` 中配置以下变量（阿里云部署时使用）：

### 1. DeepSeek（文案分析 / 口播稿生成）

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key | `sk-xxxxxxxx` |
| `DEEPSEEK_BASE_URL` | API 地址（可选） | `https://api.deepseek.com/v1` |
| `DEEPSEEK_MODEL` | 模型名称（可选） | `deepseek-chat` |

### 2. 通义万相（封面图 AI 生成）

| 变量名 | 说明 | 备注 |
|--------|------|------|
| `COVER_WAN_API_KEY` | 通义万相 API Key | 与 DASHSCOPE 二选一 |
| `DASHSCOPE_API_KEY` | 阿里云百炼 API Key | 同上，两者等效 |
| `COVER_WAN_BASE_URL` | 可选，默认 dashscope | - |
| `COVER_WAN_MODEL` | 可选，默认 wan2.6-t2i | 需与 cover_service 支持一致 |

### 3. 占位视频（Pixabay / Pexels）

| 变量名 | 说明 | 用途 |
|--------|------|------|
| `PIXABAY_API_KEY` | Pixabay API Key | 背景视频素材 |
| `PEXELS_API_KEY` | Pexels API Key | 背景视频素材 |

### 4. 其他必填

| 变量名 | 说明 |
|--------|------|
| `POSTGRES_PASSWORD` | 数据库密码 |
| `REDIS_PASSWORD` | Redis 密码 |
| `WORKER_SECRET` | Worker 回调鉴权密钥 |

---

## 二、配置步骤

1. 复制示例文件：
   ```bash
   cp deploy/aliyun/.env.prod.example deploy/aliyun/.env.prod
   ```

2. 编辑 `deploy/aliyun/.env.prod`，填入你的 API Key：
   ```bash
   # 示例（请替换为你的真实 Key）
   DEEPSEEK_API_KEY=sk-你的DeepSeek密钥
   COVER_WAN_API_KEY=sk-你的通义万相密钥
   DASHSCOPE_API_KEY=sk-你的通义万相密钥   # 与 COVER_WAN 二选一
   PIXABAY_API_KEY=你的Pixabay密钥
   PEXELS_API_KEY=你的Pexels密钥
   ```

3. 确认 `.env.prod` 未被 Git 跟踪：
   ```bash
   git status deploy/aliyun/.env.prod
   # 应显示为 untracked 或 ignored
   ```

---

## 三、获取 API Key 的链接

- **DeepSeek**: https://platform.deepseek.com/
- **通义万相（阿里云百炼）**: https://bailian.console.aliyun.com/
- **Pixabay**: https://pixabay.com/api/docs/
- **Pexels**: https://www.pexels.com/api/

---

## 四、验证配置

部署后可通过以下方式验证：

1. **DeepSeek**：在 Studio 发起一次 AI 创作，若文案分析正常则配置正确
2. **通义万相**：AI 创作完成后有 AI 生成的封面图（非视频帧兜底）则配置正确
3. **Pixabay/Pexels**：背景视频为在线素材而非本地占位则配置正确

---

## 五、当前服务器配置参考

- **规格**：4vCPU / 16GiB 轻量服务器，80GiB ESSD
- **无 GPU**：AI 封面、TTS、视频合成均依赖 CPU，渲染较慢属正常
- **建议**：短期用户量不大时，当前配置可支撑；后续可考虑 GPU 实例加速
