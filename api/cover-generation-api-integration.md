# 封面设计大模型 API 对接文档

> **项目**: AIseek-Trae-v1 - AI 创作模式短视频平台  
> **版本**: v1.0  
> **创建时间**: 2026-03-02  
> **用途**: 对接封面生成大模型 API，实现多厂商自动切换与稳定出片

---

## 📺 推荐平台总览

| 平台 | 模型 | 质量 | 速度 | 价格 | 推荐度 |
|------|------|------|------|------|--------|
| **OpenAI** | gpt-image-1 / DALL·E 3 | ⭐⭐⭐⭐⭐ | 中 | $0.044/张 | ⭐⭐⭐⭐⭐ |
| **Stability AI** | SDXL / SD 3 | ⭐⭐⭐⭐⭐ | 快 | $0.002-0.01/张 | ⭐⭐⭐⭐⭐ |
| **Leonardo.ai** | Phoenix / SDXL | ⭐⭐⭐⭐ | 快 | $0.001-0.005/张 | ⭐⭐⭐⭐ |
| **Recraft** | Recraft V3 | ⭐⭐⭐⭐ | 中 | $0.01-0.03/张 | ⭐⭐⭐⭐ |
| **DeepAI** | Stable Diffusion | ⭐⭐⭐ | 快 | $0.0005/张 | ⭐⭐⭐ |

---

## 1️⃣ OpenAI Images API（首选推荐）

### 📋 基本信息

| 项目 | 详情 |
|------|------|
| **模型** | gpt-image-1（最新）、DALL·E 3、DALL·E 2 |
| **API 文档** | https://platform.openai.com/docs/api-reference/images |
| **Base URL** | `https://api.openai.com/v1/images/generations` |
| **鉴权方式** | Bearer Token（HTTP Header） |
| **注册链接** | https://platform.openai.com/api-keys |

### 🔐 鉴权方式

```http
POST https://api.openai.com/v1/images/generations
Authorization: Bearer sk-xxxxxxxxxxxxxxxxxxxxxxxx
Content-Type: application/json
```

| 项目 | 说明 |
|------|------|
| **类型** | Bearer Token |
| **位置** | HTTP Header |
| **Header 名** | `Authorization` |
| **格式** | `Bearer sk-xxx` |

### 💰 价格

| 模型 | 分辨率 | 价格 |
|------|--------|------|
| **gpt-image-1** | 1024x1024 | $0.044/张 |
| **gpt-image-1** | 1536x1024 | $0.053/张 |
| **gpt-image-1** | 1024x1536 | $0.053/张 |
| **DALL·E 3** | 1024x1024 | $0.040/张 |
| **DALL·E 3** | 1792x1024 | $0.080/张 |
| **DALL·E 3** | 1024x1792 | $0.080/张 |
| **DALL·E 2** | 1024x1024 | $0.020/张 |

### 🎬 核心接口

#### 1. 生成图片

```http
POST https://api.openai.com/v1/images/generations
```

**请求参数**:

| 参数 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| `model` | string | ✅ | 模型名称 | `gpt-image-1`、`dall-e-3` |
| `prompt` | string | ✅ | 文字描述 | `A minimalist YouTube thumbnail` |
| `n` | int | ❌ | 生成数量（1-10） | `1` |
| `size` | string | ❌ | 分辨率 | `1024x1024`、`1536x1024` |
| `quality` | string | ❌ | 质量 | `low`、`medium`、`high`、`auto` |
| `response_format` | string | ❌ | 返回格式 | `url` 或 `b64_json` |
| `style` | string | ❌ | 风格（DALL·E 3） | `vivid`、`natural` |
| `background` | string | ❌ | 背景 | `transparent`、`opaque`、`auto` |
| `output_format` | string | ❌ | 输出格式 | `png`、`webp`、`jpeg` |

**请求示例**:

```bash
curl -X POST "https://api.openai.com/v1/images/generations" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-image-1",
    "prompt": "Create a YouTube thumbnail for a tech review video about iPhone 15. Bold text \"iPhone 15 Review\", modern design, vibrant colors, professional look",
    "n": 1,
    "size": "1536x1024",
    "quality": "high",
    "response_format": "url",
    "output_format": "png"
  }'
```

**响应示例**:

```json
{
  "created_at": 1772425200,
  "data": [
    {
      "url": "https://oaidalleapiprodscus.blob.core.windows.net/private/org-xxx/image-xxx.png",
      "revised_prompt": "A professional YouTube thumbnail featuring an iPhone 15 with bold text...",
      "b64_json": null
    }
  ]
}
```

**响应字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `created_at` | int | Unix 时间戳 |
| `data[].url` | string | 图片 URL（30 天有效） |
| `data[].b64_json` | string | Base64 编码（如设置） |
| `data[].revised_prompt` | string | 优化后的提示词 |

---

#### 2. 编辑图片（可选）

```http
POST https://api.openai.com/v1/images/edits
```

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `model` | string | ✅ | 模型名称 |
| `image` | file | ✅ | 原图（PNG） |
| `prompt` | string | ✅ | 编辑指令 |
| `mask` | file | ❌ | 遮罩区域 |
| `n` | int | ❌ | 生成数量 |
| `size` | string | ❌ | 分辨率 |

---

### 📜 封面设计提示词模板

#### YouTube 封面

```
Create a YouTube thumbnail for [TOPIC]. 
Requirements:
- Bold, readable text: "[TITLE]"
- High contrast colors
- Professional design
- 16:9 aspect ratio
- Eye-catching composition
- Modern style
- Include [KEY_ELEMENT]
```

#### 产品评测

```
YouTube thumbnail for product review:
- Product: [PRODUCT_NAME]
- Title: "[REVIEW_TITLE]"
- Style: Professional tech review
- Colors: Vibrant, high contrast
- Elements: Product image, rating stars, bold text
- Mood: Exciting, informative
```

#### 教程类

```
Educational video thumbnail:
- Topic: [TUTORIAL_TOPIC]
- Title: "[TUTORIAL_TITLE]"
- Style: Clean, educational
- Colors: Bright, friendly
- Elements: Step numbers, icons, clear text
- Mood: Approachable, helpful
```

---

## 2️⃣ Stability AI API（备选推荐）

### 📋 基本信息

| 项目 | 详情 |
|------|------|
| **模型** | SDXL 1.0、Stable Diffusion 3、Stable Image Ultra |
| **API 文档** | https://platform.stability.ai/docs/api-reference |
| **Base URL** | `https://api.stability.ai/v2beta/stable-image/generate` |
| **鉴权方式** | Bearer Token |
| **注册链接** | https://platform.stability.ai/account/keys |

### 🔐 鉴权方式

```http
POST https://api.stability.ai/v2beta/stable-image/generate/sdxl
Authorization: Bearer sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

### 💰 价格

| 模型 | 价格 |
|------|------|
| **SDXL 1.0** | $0.002-0.007/张 |
| **Stable Diffusion 3** | $0.01-0.03/张 |
| **Stable Image Ultra** | $0.03-0.05/张 |

### 🎬 核心接口

#### 生成图片（SDXL）

```http
POST https://api.stability.ai/v2beta/stable-image/generate/sdxl
```

**请求参数**（FormData）:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `prompt` | string | ✅ | 文字描述 |
| `negative_prompt` | string | ❌ | 反向提示词 |
| `output_format` | string | ❌ | `png`、`jpeg`、`webp` |
| `width` | int | ❌ | 宽度（512-2048） |
| `height` | int | ❌ | 高度（512-2048） |
| `steps` | int | ❌ | 步数（30-50） |
| `cfg_scale` | float | ❌ | 提示词权重（5-10） |
| `seed` | int | ❌ | 随机种子 |

**请求示例**:

```bash
curl -X POST "https://api.stability.ai/v2beta/stable-image/generate/sdxl" \
  -H "Authorization: Bearer $STABILITY_API_KEY" \
  -H "Accept: image/*" \
  -F "prompt=A professional YouTube thumbnail with bold text" \
  -F "negative_prompt=blurry, low quality, distorted text" \
  -F "width=1536" \
  -F "height=1024" \
  -F "output_format=png"
```

**响应**: 直接返回图片二进制数据

---

## 3️⃣ Leonardo.ai API（备选）

### 📋 基本信息

| 项目 | 详情 |
|------|------|
| **模型** | Phoenix、SDXL、Leonardo Diffusion |
| **API 文档** | https://docs.leonardo.ai/ |
| **Base URL** | `https://cloud.leonardo.ai/api/rest/v1/` |
| **鉴权方式** | Bearer Token |
| **注册链接** | https://app.leonardo.ai/api-keys |

### 💰 价格

| 模型 | 价格 |
|------|------|
| **Phoenix** | ~$0.005/张 |
| **SDXL** | ~$0.002/张 |
| **自定义模型** | 按训练成本 |

### 🎬 核心接口

#### 创建生成任务

```http
POST https://cloud.leonardo.ai/api/rest/v1/generations
```

**请求参数**:

```json
{
  "prompt": "YouTube thumbnail, professional design, bold text",
  "modelId": "model-id-here",
  "width": 1536,
  "height": 1024,
  "num_images": 1,
  "negative_prompt": "blurry, low quality"
}
```

#### 获取生成结果

```http
GET https://cloud.leonardo.ai/api/rest/v1/generations/{generationId}
```

**响应示例**:

```json
{
  "generated_images": [
    {
      "url": "https://cdn.leonardo.ai/xxx/xxx.png",
      "nsfw": false
    }
  ]
}
```

---

## 4️⃣ DeepAI API（经济型）

### 📋 基本信息

| 项目 | 详情 |
|------|------|
| **模型** | Stable Diffusion |
| **API 文档** | https://deepai.org/apis/text2image |
| **Base URL** | `https://api.deepai.org/api/text2img` |
| **鉴权方式** | API Key |
| **价格** | $0.0005/张起 |

### 🎬 核心接口

```http
POST https://api.deepai.org/api/text2img
```

**请求示例**:

```bash
curl -X POST "https://api.deepai.org/api/text2img" \
  -H "api-key: YOUR_API_KEY" \
  -d "text=A YouTube thumbnail design"
```

---

## 🏗️ Provider 接口定义

### CoverProvider 接口

```typescript
interface CoverProvider {
  name: string;
  priority: number;
  enabled: boolean;
  
  // 生成封面
  generate(params: CoverParams): Promise<CoverResult>;
  
  // 健康检查
  healthCheck(): Promise<HealthStatus>;
}

interface CoverParams {
  prompt: string;           // 提示词
  negativePrompt?: string;  // 反向提示词
  width: number;            // 宽度
  height: number;           // 高度
  quality?: 'low' | 'medium' | 'high';
  style?: string;           // 风格
  n?: number;               // 生成数量
}

interface CoverResult {
  success: boolean;
  imageUrl?: string;        // 图片 URL
  imageBase64?: string;     // Base64 编码
  prompt?: string;          // 实际使用的提示词
  model: string;            // 使用的模型
  cost?: number;            // 成本（美元）
  duration?: number;        // 生成耗时（秒）
  error?: string;           // 错误信息
}

interface HealthStatus {
  healthy: boolean;
  latency?: number;
  lastError?: string;
  lastCheck: number;
}
```

---

### 多 Provider 配置示例

```typescript
const coverProviders: CoverProvider[] = [
  {
    name: 'openai',
    priority: 10,
    enabled: true,
    config: {
      apiKey: process.env.COVER_OPENAI_API_KEY,
      baseUrl: process.env.COVER_OPENAI_BASE_URL || 'https://api.openai.com/v1',
      model: process.env.COVER_OPENAI_MODEL || 'gpt-image-1',
    }
  },
  {
    name: 'stability',
    priority: 9,
    enabled: true,
    config: {
      apiKey: process.env.COVER_STABILITY_API_KEY,
      baseUrl: 'https://api.stability.ai/v2beta',
      model: 'stable-diffusion-xl-1024-v1-0',
    }
  },
  {
    name: 'leonardo',
    priority: 8,
    enabled: true,
    config: {
      apiKey: process.env.COVER_LEONARDO_API_KEY,
      baseUrl: 'https://cloud.leonardo.ai/api/rest/v1',
      model: 'phoenix',
    }
  },
  {
    name: 'deepai',
    priority: 5,
    enabled: true,
    config: {
      apiKey: process.env.COVER_DEEPAI_API_KEY,
      baseUrl: 'https://api.deepai.org/api',
      model: 'text2img',
    }
  }
];

// Provider 选择顺序
const coverProviderOrder = [
  'openai',      // 首选
  'stability',   // 备选 1
  'leonardo',    // 备选 2
  'deepai'       // 降级
];
```

---

### 失败降级策略

```typescript
async function generateCoverWithFallback(
  prompt: string, 
  options: CoverOptions
): Promise<CoverResult> {
  const providers = coverProviders
    .filter(p => p.enabled)
    .sort((a, b) => b.priority - a.priority);
  
  let lastError: string | null = null;
  
  for (const provider of providers) {
    try {
      // 健康检查
      const health = await provider.healthCheck();
      if (!health.healthy) {
        console.warn(`Provider ${provider.name} unhealthy, skipping`);
        continue;
      }
      
      // 生成封面
      const result = await provider.generate({
        prompt,
        width: options.width || 1536,
        height: options.height || 1024,
        quality: options.quality || 'high',
        n: 1
      });
      
      if (result.success) {
        // 缓存结果
        await cacheCover(prompt, result);
        return result;
      }
      
      lastError = result.error || 'Unknown error';
    } catch (error) {
      console.warn(`Provider ${provider.name} failed:`, error);
      lastError = error.message;
      
      // 记录错误到观测系统
      await recordProviderError(provider.name, error);
    }
  }
  
  // 所有 Provider 失败，返回本地默认封面
  return getDefaultCover();
}
```

---

## 📊 熔断与观测

### 熔断器配置

```typescript
interface CircuitBreakerConfig {
  failureThreshold: number;    // 失败阈值
  successThreshold: number;    // 恢复阈值
  timeout: number;             // 超时时间（ms）
  monitoringWindow: number;    // 监控窗口（ms）
}

const circuitBreakerConfig: CircuitBreakerConfig = {
  failureThreshold: 5,      // 5 次失败后熔断
  successThreshold: 2,      // 2 次成功后恢复
  timeout: 60000,           // 60 秒超时
  monitoringWindow: 300000  // 5 分钟监控窗口
};
```

### 观测指标

```typescript
interface ProviderMetrics {
  totalRequests: number;
  successfulRequests: number;
  failedRequests: number;
  averageLatency: number;
  p95Latency: number;
  p99Latency: number;
  costPerRequest: number;
  lastError?: string;
  lastSuccess: number;
  circuitState: 'closed' | 'open' | 'half-open';
}
```

---

## 🚀 环境变量配置

```bash
# ===========================================
# 封面生成 API 配置 (Cover Generation)
# ===========================================

# Provider 选择顺序
COVER_PROVIDER_ORDER=openai,stability,leonardo,deepai

# OpenAI 配置
COVER_OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
COVER_OPENAI_BASE_URL=https://api.openai.com/v1
COVER_OPENAI_MODEL=gpt-image-1

# Stability AI 配置
COVER_STABILITY_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
COVER_STABILITY_BASE_URL=https://api.stability.ai/v2beta
COVER_STABILITY_MODEL=stable-diffusion-xl-1024-v1-0

# Leonardo.ai 配置
COVER_LEONARDO_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
COVER_LEONARDO_BASE_URL=https://cloud.leonardo.ai/api/rest/v1
COVER_LEONARDO_MODEL=phoenix

# DeepAI 配置
COVER_DEEPAI_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
COVER_DEEPAI_BASE_URL=https://api.deepai.org/api
COVER_DEEPAI_MODEL=text2img

# 封面质量配置
COVER_DEFAULT_WIDTH=1536
COVER_DEFAULT_HEIGHT=1024
COVER_DEFAULT_QUALITY=high
COVER_DEFAULT_FORMAT=png

# 缓存配置
COVER_CACHE_TTL=86400000
COVER_CACHE_PATH=./data/cover-cache

# 熔断配置
COVER_CIRCUIT_FAILURE_THRESHOLD=5
COVER_CIRCUIT_TIMEOUT=60000
```

---

## 📝 API Key 获取指南

### OpenAI

1. 访问：https://platform.openai.com/api-keys
2. 登录/注册 OpenAI 账号
3. 点击 **Create new secret key**
4. 复制保存（只显示一次）
5. **充值**: https://platform.openai.com/account/billing

**免费额度**: 新账号 $5（3 个月有效）

---

### Stability AI

1. 访问：https://platform.stability.ai/account/keys
2. 登录/注册账号
3. 点击 **Create API Key**
4. 复制保存

**免费额度**: 新账号 25 积分（约 10-50 张图）

---

### Leonardo.ai

1. 访问：https://app.leonardo.ai/api-keys
2. 登录/注册账号
3. 点击 **Generate Key**
4. 复制保存

**免费额度**: 每天 150 积分（约 30-75 张图）

---

### DeepAI

1. 访问：https://deepai.org/dashboard/profile
2. 登录/注册账号
3. 查看 API Key
4. 复制保存

**免费额度**: 有限免费额度

---

## 📊 平台对比总结

| 特性 | OpenAI | Stability | Leonardo | DeepAI |
|------|--------|-----------|----------|--------|
| **质量** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **速度** | 中（10-30 秒） | 快（3-10 秒） | 快（5-15 秒） | 快（2-5 秒） |
| **价格** | $0.04-0.08 | $0.002-0.03 | $0.001-0.005 | $0.0005 |
| **免费额度** | $5 | 25 积分 | 150 积分/天 | 有限 |
| **返回格式** | URL/Base64 | 二进制 | URL | URL |
| **商用许可** | ✅ | ✅ | ✅ | ✅ |
| **推荐场景** | 高质量封面 | 批量生成 | 性价比 | 测试 |

---

## 🎯 推荐配置

### 生产环境

```bash
# 首选 OpenAI（高质量）
COVER_PROVIDER_ORDER=openai,stability,leonardo
COVER_OPENAI_MODEL=gpt-image-1
COVER_DEFAULT_QUALITY=high

# 降级 Stability（批量）
COVER_STABILITY_MODEL=stable-diffusion-xl-1024-v1-0
```

### 经济环境

```bash
# 首选 Stability（性价比）
COVER_PROVIDER_ORDER=stability,leonardo,deepai
COVER_STABILITY_MODEL=stable-diffusion-xl-1024-v1-0
COVER_DEFAULT_QUALITY=medium
```

### 测试环境

```bash
# 使用 Leonardo（免费额度多）
COVER_PROVIDER_ORDER=leonardo,deepai
COVER_LEONARDO_MODEL=phoenix
```

---

## 📌 开发清单

- [ ] 实现 CoverProvider 接口
- [ ] 集成 OpenAI Images API
- [ ] 集成 Stability AI API
- [ ] 集成 Leonardo.ai API（可选）
- [ ] 实现失败降级策略
- [ ] 实现熔断器
- [ ] 实现观测指标收集
- [ ] 配置环境变量
- [ ] 测试多 Provider 切换
- [ ] 添加封面缓存

---

**文档版本**: v1.0  
**最后更新**: 2026-03-02  
**维护者**: AIseek Team
