# 阿里云百炼 Coding Plan API 用于封面生成方案

> **项目**: AIseek-Trae-v1 - AI 创作模式短视频平台  
> **版本**: v1.0  
> **创建时间**: 2026-03-02  
> **用途**: 使用阿里云百炼 Coding Plan API Key 实现封面生成功能

---

## ⚠️ 重要说明

### Coding Plan 模型定位

**阿里云百炼 Coding Plan** 是**代码专用大模型**，主要用于：
- ✅ 代码生成
- ✅ 代码理解
- ✅ 代码优化
- ✅ 技术文档生成
- ❌ **不支持直接生成图片**

### 如何用 Coding Plan 生成封面？

**方案**: Coding Plan + 通义万相 API 组合使用

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  Coding Plan    │      │  通义万相 API   │      │   封面图片      │
│  (你的 API Key) │ ───→ │  (单独调用)     │ ───→ │   (URL/Base64)  │
│                 │      │                 │      │                 │
│ 1. 生成提示词   │      │ 2. 文生图       │      │ 3. 返回结果     │
│ 2. 优化描述     │      │                 │      │                 │
└─────────────────┘      └─────────────────┘      └─────────────────┘
```

---

## 🎯 推荐方案

### 方案 A：双 API 组合（推荐）

**使用你的 Coding Plan API Key + 通义万相 API**

**流程**：
1. **Coding Plan**：生成/优化封面提示词
2. **通义万相**：根据提示词生成图片

**优势**：
- ✅ 充分利用你的 Coding Plan API
- ✅ 提示词质量更高（AI 优化）
- ✅ 成本可控

---

### 方案 B：直接使用通义万相

**单独调用通义万相 API**

**流程**：
1. 手动编写提示词
2. 调用通义万相生成图片

**优势**：
- ✅ 简单直接
- ✅ 无需额外 API

---

## 📋 方案 A 完整实现

### 1. 架构设计

```typescript
interface CoverGenerationService {
  // 步骤 1: 用 Coding Plan 优化提示词
  optimizePrompt(userInput: string): Promise<string>;
  
  // 步骤 2: 调用通义万相生成图片
  generateImage(prompt: string): Promise<CoverResult>;
}
```

### 2. 步骤 1: Coding Plan 优化提示词

**接口配置**：

```http
POST https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
Authorization: Bearer sk-xxxxxxxxxxxxxxxxxxxxxxxx (你的 Coding Plan API Key)
Content-Type: application/json
```

**请求示例**：

```json
{
  "model": "qwen-coder-plus",
  "messages": [
    {
      "role": "system",
      "content": "你是一个专业的 AI 绘画提示词优化专家。请将用户输入的简单描述优化为详细的英文绘画提示词，适合用于通义万相 AI 绘画。要求：\n1. 包含主体、风格、色彩、构图等细节\n2. 使用英文\n3. 长度 50-100 词\n4. 适合 YouTube 封面设计"
    },
    {
      "role": "user",
      "content": "iPhone 15 评测视频封面"
    }
  ]
}
```

**响应示例**：

```json
{
  "choices": [
    {
      "message": {
        "content": "Create a professional YouTube thumbnail for iPhone 15 review video. Modern minimalist design with a large iPhone 15 product image in the center, sleek metallic finish, vibrant blue color. Bold white text \"iPhone 15 Review\" at the top. High contrast background with gradient from dark blue to black. Add subtle glow effects around the phone. Professional studio lighting, 4K quality, eye-catching composition, 16:9 aspect ratio."
      }
    }
  ]
}
```

### 3. 步骤 2: 通义万相生成图片

**接口配置**：

```http
POST https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation
Authorization: Bearer sk-xxxxxxxxxxxxxxxxxxxxxxxx (通义万相 API Key)
Content-Type: application/json
```

**请求示例**：

```json
{
  "model": "wanx-v1",
  "input": {
    "prompt": "Create a professional YouTube thumbnail for iPhone 15 review video. Modern minimalist design with a large iPhone 15 product image in the center, sleek metallic finish, vibrant blue color. Bold white text \"iPhone 15 Review\" at the top. High contrast background with gradient from dark blue to black. Add subtle glow effects around the phone. Professional studio lighting, 4K quality, eye-catching composition, 16:9 aspect ratio."
  },
  "parameters": {
    "size": "1536*1024",
    "n": 1,
    "format": "png"
  }
}
```

**响应示例**：

```json
{
  "output": {
    "task_id": "xxx-xxx-xxx",
    "results": [
      {
        "url": "https://dashscope-result.oss-cn-shanghai.aliyuncs.com/xxx/xxx.png"
      }
    ]
  },
  "request_id": "xxx-xxx-xxx",
  "usage": {
    "image_count": 1
  }
}
```

---

## 💰 成本分析

### Coding Plan API 价格

| 模型 | 输入价格 | 输出价格 |
|------|---------|---------|
| **qwen-coder-plus** | ¥0.004/1K tokens | ¥0.012/1K tokens |

**每次提示词优化成本**：约 ¥0.01-0.05

### 通义万相价格

| 模型 | 分辨率 | 价格 |
|------|--------|------|
| **wanx-v1** | 1024x1024 | ¥0.08/张 |
| **wanx-v1** | 1536x1024 | ¥0.12/张 |

**总成本**：¥0.09-0.17/张封面

---

## 🔐 API Key 说明

### 你的 Coding Plan API Key

- **用途**：优化提示词（文本生成）
- **获取地址**：https://bailian.console.aliyun.com/cn-beijing/?tab=model#/efm/coding_plan
- **接口地址**：`https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`
- **模型名称**：`qwen-coder-plus`

### 通义万相 API Key（需要单独获取）

- **用途**：生成图片
- **获取地址**：https://dashscope.console.aliyun.com/
- **接口地址**：`https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation`
- **模型名称**：`wanx-v1`

**注意**：两个 API 使用**不同的接口**，但可能是**同一个 API Key**（取决于你的账号权限）

---

## 🚀 完整代码示例

### Node.js 实现

```javascript
import OpenAI from 'openai';

// 初始化 Coding Plan 客户端
const codingPlanClient = new OpenAI({
  apiKey: process.env.ALIYUN_CODING_PLAN_API_KEY,
  baseURL: 'https://dashscope.aliyuncs.com/compatible-mode/v1'
});

// 步骤 1: 优化提示词
async function optimizePrompt(userInput) {
  const completion = await codingPlanClient.chat.completions.create({
    model: 'qwen-coder-plus',
    messages: [
      {
        role: 'system',
        content: `You are a professional AI art prompt optimizer. 
        Convert simple descriptions into detailed English prompts for image generation.
        Requirements:
        - Include subject, style, colors, composition details
        - Use English
        - 50-100 words
        - Suitable for YouTube thumbnails (16:9 aspect ratio)`
      },
      {
        role: 'user',
        content: userInput
      }
    ]
  });
  
  return completion.choices[0].message.content;
}

// 步骤 2: 生成图片
async function generateImage(prompt) {
  const response = await fetch(
    'https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation',
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${process.env.ALIYUN_WANX_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model: 'wanx-v1',
        input: {
          prompt: prompt
        },
        parameters: {
          size: '1536*1024',
          n: 1,
          format: 'png'
        }
      })
    }
  );
  
  const result = await response.json();
  return {
    url: result.output.results[0].url,
    taskId: result.output.task_id
  };
}

// 完整流程
async function generateCover(userInput) {
  // 优化提示词
  const optimizedPrompt = await optimizePrompt(userInput);
  console.log('Optimized prompt:', optimizedPrompt);
  
  // 生成图片
  const imageResult = await generateImage(optimizedPrompt);
  console.log('Image URL:', imageResult.url);
  
  return imageResult;
}

// 使用示例
generateCover('iPhone 15 评测视频封面');
```

---

## 📊 方案对比

| 方案 | 优点 | 缺点 | 成本 | 推荐度 |
|------|------|------|------|--------|
| **Coding Plan + 通义万相** | 提示词质量高 | 需要两个 API | ¥0.09-0.17/张 | ⭐⭐⭐⭐⭐ |
| **仅通义万相** | 简单直接 | 提示词需手动优化 | ¥0.08-0.12/张 | ⭐⭐⭐⭐ |
| **仅 Coding Plan** | ❌ 无法生成图片 | ❌ 不支持 | - | ❌ |

---

## 🔍 验证你的 API Key 权限

### 方法 1: 检查控制台

1. 访问：https://bailian.console.aliyun.com/
2. 进入 **API-KEY 管理**
3. 查看你的 API Key 权限
4. 确认是否包含 **通义万相** 服务

### 方法 2: 测试调用

```bash
# 测试 Coding Plan（代码生成）
curl -X POST https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions \
  -H "Authorization: Bearer sk-xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-coder-plus",
    "messages": [{"role": "user", "content": "Hello"}]
  }'

# 测试通义万相（图片生成）
curl -X POST https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation \
  -H "Authorization: Bearer sk-xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "wanx-v1",
    "input": {"prompt": "test"}
  }'
```

---

## 📝 环境变量配置

```bash
# ===========================================
# 阿里云百炼 API 配置
# ===========================================

# Coding Plan API（你的现有 Key）
ALIYUN_CODING_PLAN_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
ALIYUN_CODING_PLAN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
ALIYUN_CODING_PLAN_MODEL=qwen-coder-plus

# 通义万相 API（需要确认是否同一 Key）
ALIYUN_WANX_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
ALIYUN_WANX_BASE_URL=https://dashscope.aliyuncs.com/api/v1
ALIYUN_WANX_MODEL=wanx-v1

# 封面质量配置
COVER_DEFAULT_WIDTH=1536
COVER_DEFAULT_HEIGHT=1024
COVER_DEFAULT_FORMAT=png
```

---

## ⚡ 快速开始

### 如果你的 API Key 支持通义万相

**直接使用方案 B**：

```bash
# 1. 配置环境变量
export ALIYUN_WANX_API_KEY=sk-xxx

# 2. 调用通义万相 API
curl -X POST https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation \
  -H "Authorization: Bearer $ALIYUN_WANX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "wanx-v1",
    "input": {
      "prompt": "YouTube thumbnail, tech review style, iPhone 15"
    },
    "parameters": {
      "size": "1536*1024",
      "n": 1,
      "format": "png"
    }
  }'
```

### 如果需要单独开通义万相

**步骤**：

1. 访问：https://dashscope.console.aliyun.com/
2. 进入 **模型广场** → **通义万相**
3. 点击 **开通服务**
4. 确认价格并同意协议
5. 使用**同一个 API Key** 即可

---

## 🎯 最终建议

### 对于 AIseek 项目

**推荐方案**：**方案 A（双 API 组合）**

**原因**：
1. ✅ 充分利用已有 Coding Plan API
2. ✅ 提示词自动优化，质量更高
3. ✅ 成本可控（¥0.09-0.17/张）
4. ✅ 可扩展性强（可接入其他文生图 API）

**实现优先级**：
1. 先验证 API Key 是否支持通义万相
2. 如不支持，单独开通义万相服务
3. 实现双阶段生成流程
4. 添加缓存和降级策略

---

## 📌 开发清单

- [ ] 验证 API Key 权限
- [ ] 测试 Coding Plan 提示词优化
- [ ] 测试通义万相图片生成
- [ ] 实现双阶段生成流程
- [ ] 添加错误处理和重试
- [ ] 实现封面缓存
- [ ] 配置环境变量
- [ ] 集成到 AIseek 工作流

---

**文档版本**: v1.0  
**最后更新**: 2026-03-02  
**维护者**: AIseek Team
