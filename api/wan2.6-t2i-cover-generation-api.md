# 通义万相 wan2.6-t2i 封面生成 API 对接文档

> **项目**: AIseek-Trae-v1 - AI 创作模式短视频平台  
> **模型**: 通义万相 wan2.6-t2i（Text to Image）  
> **版本**: v1.0  
> **创建时间**: 2026-03-02  
> **API Key**: `sk-***`（请勿把密钥写入仓库；改用环境变量 `COVER_WAN_API_KEY` 配置）  
> **用途**: 封面设计大模型平台 API 完整对接文档

---

## 📋 基本信息

| 项目 | 详情 |
|------|------|
| **平台** | 阿里云百炼（DashScope） |
| **模型** | 通义万相 wan2.6-t2i |
| **模型类型** | 文生图（Text to Image） |
| **API 文档** | https://help.aliyun.com/zh/model-studio/ |
| **控制台** | https://bailian.console.aliyun.com/ |
| **鉴权方式** | Bearer Token（HTTP Header） |
| **返回格式** | **URL**（OSS 阿里云对象存储） |

---

## 🔐 鉴权方式

### HTTP Header

```http
Authorization: Bearer sk-***
Content-Type: application/json
```

| 项目 | 说明 |
|------|------|
| **类型** | Bearer Token |
| **位置** | HTTP Header |
| **Header 名** | `Authorization` |
| **格式** | `Bearer sk-xxxxxxxxxxxxxxxxxxxxxxxx` |
| **API Key** | `sk-***`（建议使用环境变量 `COVER_WAN_API_KEY`） |

---

## 🌐 API 端点

### HTTP 路径

```http
POST https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
```

**地域说明**：

| 地域 | Base URL |
|------|---------|
| **中国大陆** | `https://dashscope.aliyuncs.com/` |
| **新加坡** | `https://dashscope-intl.aliyuncs.com/` |
| **美国** | `https://dashscope-us.aliyuncs.com/` |

---

## 🎬 核心接口

### 1. 文生图（Text to Image）

#### 接口定义

```http
POST https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
```

#### 请求参数

**请求体结构**：

```json
{
  "model": "wan2.6-t2i",
  "input": {
    "messages": [
      {
        "role": "user",
        "content": [
          { "text": "string (required)" }
        ]
      }
    ]
  },
  "parameters": {
    "size": "string (optional)",
    "n": "integer (optional)",
    "negative_prompt": "string (optional)",
    "prompt_extend": "boolean (optional)",
    "watermark": "boolean (optional)",
    "seed": "integer (optional)"
  }
}
```

**详细参数说明**：

| 参数 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| **model** | string | ✅ | 模型名称 | `wan2.6-t2i` |
| **input.prompt** | string | ✅ | 正向提示词（支持中文） | `"YouTube 封面，科技风格"` |
| **input.negative_prompt** | string | ❌ | 反向提示词 | `"模糊，低质量，文字扭曲"` |
| **parameters.size** | string | ❌ | 分辨率 | `"1024*1024"`、`"1536*1024"` |
| **parameters.n** | integer | ❌ | 生成数量（1-4） | `1` |
| **parameters.num_inference_steps** | integer | ❌ | 推理步数（20-50） | `30` |
| **parameters.guidance_scale** | number | ❌ | 提示词相关性（3-10） | `7.5` |
| **parameters.seed** | integer | ❌ | 随机种子 | `42` |
| **parameters.style** | string | ❌ | 风格 | `"<cartoon>"`、`"<photorealistic>"` |

---

### 2. 完整请求示例

#### cURL

```bash
curl -X POST https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation \
  -H "Authorization: Bearer $COVER_WAN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "wan2.6-t2i",
    "input": {
      "prompt": "YouTube 封面设计，科技评测视频，iPhone 15 评测，现代简约风格，鲜艳色彩，专业设计，16:9 比例",
      "negative_prompt": "模糊，低质量，文字扭曲，水印，logo"
    },
    "parameters": {
      "size": "1536*1024",
      "n": 1,
      "num_inference_steps": 30,
      "guidance_scale": 7.5,
      "style": "<photorealistic>"
    }
  }'
```

#### Python

```python
import requests

API_KEY = os.getenv("COVER_WAN_API_KEY")
URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

payload = {
    "model": "wan2.6-t2i",
    "input": {
        "prompt": "YouTube 封面设计，科技评测视频，iPhone 15 评测，现代简约风格，鲜艳色彩",
        "negative_prompt": "模糊，低质量，文字扭曲"
    },
    "parameters": {
        "size": "1536*1024",
        "n": 1,
        "num_inference_steps": 30,
        "guidance_scale": 7.5
    }
}

response = requests.post(URL, headers=headers, json=payload)
result = response.json()
print(result)
```

#### Node.js

```javascript
const fetch = require('node-fetch');

const API_KEY = process.env.COVER_WAN_API_KEY;
const URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation";

const payload = {
  model: "wan2.6-t2i",
  input: {
    prompt: "YouTube 封面设计，科技评测视频，iPhone 15 评测，现代简约风格",
    negative_prompt: "模糊，低质量，文字扭曲"
  },
  parameters: {
    size: "1536*1024",
    n: 1,
    num_inference_steps: 30,
    guidance_scale: 7.5
  }
};

const response = await fetch(URL, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${API_KEY}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(payload)
});

const result = await response.json();
console.log(result);
```

---

### 3. 响应格式

#### 成功响应

```json
{
  "output": {
    "task_id": "0b1c2d3e-4f5g-6h7i-8j9k-0l1m2n3o4p5q",
    "results": [
      {
        "url": "https://dashscope-result.oss-cn-shanghai.aliyuncs.com/1d/2e/3f4g5h6i7j8k9l0m1n2o3p4q5r6s7t8u.png",
        "seed": 42
      }
    ]
  },
  "request_id": "a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6",
  "usage": {
    "image_count": 1
  },
  "model": "wan2.6-t2i"
}
```

#### 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `output.task_id` | string | 任务 ID（用于异步查询） |
| `output.results[].url` | string | **生成的图片 URL**（OSS 地址，长期有效） |
| `output.results[].seed` | integer | 使用的随机种子 |
| `request_id` | string | 请求 ID（用于问题排查） |
| `usage.image_count` | integer | 生成的图片数量 |
| `model` | string | 使用的模型名称 |

#### 错误响应

```json
{
  "code": "InvalidParameter",
  "message": "The input prompt is empty.",
  "request_id": "a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6"
}
```

**常见错误码**：

| 错误码 | 说明 | 解决方法 |
|--------|------|---------|
| `InvalidParameter` | 参数错误 | 检查参数格式和必填项 |
| `Unauthorized` | 鉴权失败 | 检查 API Key 是否正确 |
| `QuotaExceeded` | 配额超限 | 检查账户余额或免费额度 |
| `InternalError` | 服务器错误 | 稍后重试 |

---

## 📐 分辨率参数详解

### 支持的分辨率

| 分辨率 | 参数值 | 适用场景 |
|--------|--------|---------|
| **1024x1024** | `"1024*1024"` | 正方形封面、Instagram |
| **1536x1024** | `"1536*1024"` | **YouTube 封面（16:9）** ⭐ |
| **1024x1536** | `"1024*1536"` | 竖屏封面、抖音/TikTok |
| **1280x1280** | `"1280*1280"` | 高清正方形 |
| **2048x2048** | `"2048*2048"` | 超高清（如支持） |

### YouTube 封面推荐配置

```json
{
  "size": "1536*1024",
  "n": 1,
  "num_inference_steps": 30,
  "guidance_scale": 7.5
}
```

---

## 🎨 风格参数详解

### 内置风格

| 风格 | 参数值 | 说明 |
|------|--------|------|
| **写实风格** | `"<photorealistic>"` | 照片级真实 ⭐ |
| **卡通风格** | `"<cartoon>"` | 动漫/卡通 |
| **油画风格** | `"<oil-painting>"` | 油画质感 |
| **水彩风格** | `"<watercolor>"` | 水彩画效果 |
| **3D 风格** | `"<3d-render>"` | 3D 渲染 |
| **像素风格** | `"<pixel-art>"` | 像素艺术 |
| **赛博朋克** | `"<cyberpunk>"` | 赛博朋克风 |
| **中国风** | `"<chinese-style>"` | 中国传统风格 |

### 风格使用示例

```json
{
  "input": {
    "prompt": "YouTube 封面，科技评测"
  },
  "parameters": {
    "style": "<photorealistic>",
    "size": "1536*1024"
  }
}
```

---

## 💰 价格说明

### 计费模式

| 分辨率 | 价格（元/张） |
|--------|-------------|
| **1024x1024** | ¥0.08 |
| **1536x1024** | ¥0.12 |
| **1024x1536** | ¥0.12 |
| **2048x2048** | ¥0.20 |

### 免费额度

- ✅ 新用户注册送 **¥100-1000** 代金券
- ✅ 通义万相每日 **100 次免费调用**（具体以控制台为准）

---

## 🏗️ Provider 接口实现

### TypeScript 接口定义

```typescript
interface WanxProvider {
  name: 'aliyun-wanx';
  priority: 10;
  enabled: boolean;
  
  generate(params: CoverParams): Promise<CoverResult>;
  healthCheck(): Promise<HealthStatus>;
}

interface CoverParams {
  prompt: string;
  negativePrompt?: string;
  width: number;
  height: number;
  quality?: 'low' | 'medium' | 'high';
  style?: string;
  n?: number;
}

interface CoverResult {
  success: boolean;
  imageUrl?: string;
  imageBase64?: string;
  prompt?: string;
  model: string;
  cost?: number;
  duration?: number;
  error?: string;
  taskId?: string;
  seed?: number;
}
```

### 完整实现示例

```typescript
class WanxCoverProvider implements WanxProvider {
  name = 'aliyun-wanx' as const;
  priority = 10;
  enabled = true;
  
  private apiKey = process.env.COVER_WAN_API_KEY || "";
  private baseUrl = "https://dashscope.aliyuncs.com";
  private model = "wan2.6-t2i";
  
  async generate(params: CoverParams): Promise<CoverResult> {
    const startTime = Date.now();
    
    try {
      const payload = {
        model: this.model,
        input: {
          messages: [
            {
              role: "user",
              content: [{ text: params.prompt }]
            }
          ]
        },
        parameters: {
          size: `${params.width}*${params.height}`,
          n: params.n || 1,
          negative_prompt: params.negativePrompt || "模糊，低质量，文字扭曲，水印",
          prompt_extend: true,
          watermark: false
        }
      };
      
      const response = await fetch(`${this.baseUrl}/api/v1/services/aigc/multimodal-generation/generation`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });
      
      const result = await response.json();
      
      if (!response.ok) {
        throw new Error(result.message || 'API request failed');
      }
      
      return {
        success: true,
        imageUrl: result.output?.choices?.[0]?.message?.content?.[0]?.image,
        prompt: params.prompt,
        model: this.model,
        cost: this.calculateCost(params.width, params.height),
        duration: Date.now() - startTime,
        taskId: result.request_id
      };
      
    } catch (error) {
      return {
        success: false,
        error: error.message,
        model: this.model,
        duration: Date.now() - startTime
      };
    }
  }
  
  private getStepsByQuality(quality?: string): number {
    switch (quality) {
      case 'low': return 20;
      case 'medium': return 25;
      case 'high': return 30;
      default: return 30;
    }
  }
  
  private calculateCost(width: number, height: number): number {
    const area = width * height;
    if (area <= 1024 * 1024) return 0.08;
    if (area <= 1536 * 1024) return 0.12;
    return 0.20;
  }
  
  async healthCheck(): Promise<HealthStatus> {
    try {
      const result = await this.generate({
        prompt: "test",
        width: 1024,
        height: 1024,
        n: 1
      });
      
      return {
        healthy: result.success,
        latency: result.duration,
        lastCheck: Date.now()
      };
    } catch (error) {
      return {
        healthy: false,
        lastError: error.message,
        lastCheck: Date.now()
      };
    }
  }
}
```

---

## 🚀 环境变量配置

```bash
# ===========================================
# 通义万相 wan2.6-t2i 配置
# ===========================================

# API Key（你的）
COVER_WAN_API_KEY=sk-***

# Base URL
COVER_WAN_BASE_URL=https://dashscope.aliyuncs.com

# 模型名称
COVER_WAN_MODEL=wan2.6-t2i

# 默认分辨率（YouTube 封面 16:9）
COVER_DEFAULT_WIDTH=1536
COVER_DEFAULT_HEIGHT=1024

# 默认质量
COVER_DEFAULT_QUALITY=high
COVER_DEFAULT_STEPS=30
COVER_DEFAULT_GUIDANCE=7.5

# 默认风格
COVER_DEFAULT_STYLE=<photorealistic>

# 输出格式
COVER_DEFAULT_FORMAT=png

# 缓存配置
COVER_CACHE_TTL=86400000
COVER_CACHE_PATH=./data/cover-cache

# 熔断配置
COVER_CIRCUIT_FAILURE_THRESHOLD=5
COVER_CIRCUIT_TIMEOUT=60000
```

---

## 📝 封面设计提示词模板

### YouTube 科技评测

```
YouTube 封面设计，[产品名称] 评测视频，现代简约风格，鲜艳色彩，专业设计，
产品高清图片居中， bold 白色标题文字，高对比度背景，渐变色彩，
专业摄影棚灯光，4K 质量，吸引眼球的构图，16:9 比例

英文优化版：
YouTube thumbnail design for [PRODUCT] review video, modern minimalist style, 
vibrant colors, professional design, product image in center, bold white title text, 
high contrast background with gradient, professional studio lighting, 4K quality, 
eye-catching composition, 16:9 aspect ratio
```

### 教程类视频

```
教育视频封面，[主题] 教程，清晰易读文字，明亮友好色彩，
步骤编号图标，简洁布局，16:9 比例，专业设计

英文优化版：
Educational video thumbnail, [TOPIC] tutorial, clear readable text, 
bright friendly colors, step numbers and icons, clean layout, 
16:9 aspect ratio, professional design
```

### 生活方式类

```
生活方式视频封面，[主题]，温暖色调，自然光线，
人物生活场景，轻松愉快氛围，电影感调色，16:9 比例

英文优化版：
Lifestyle video thumbnail, [THEME], warm tones, natural lighting, 
people in daily life scene, relaxed joyful atmosphere, 
cinematic color grading, 16:9 aspect ratio
```

---

## 🔍 异步任务处理

### 任务状态查询

对于长时间运行的任务，可以使用 `task_id` 查询状态：

```http
GET https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}
Authorization: Bearer $COVER_WAN_API_KEY
```

**响应**：

```json
{
  "output": {
    "task_status": "SUCCEEDED",
    "results": [
      {
        "url": "https://xxx.png"
      }
    ]
  },
  "request_id": "xxx"
}
```

**任务状态**：

| 状态 | 说明 |
|------|------|
| `PENDING` | 等待中 |
| `RUNNING` | 生成中 |
| `SUCCEEDED` | 成功 |
| `FAILED` | 失败 |

---

## ⚠️ 注意事项

### 图片 URL 有效期

- ✅ **长期有效**（OSS 存储，理论上永久可用）
- ⚠️ 建议下载到本地或自己的 CDN 备份

### 内容审核

- ❌ 禁止生成 NSFW 内容
- ❌ 禁止生成政治敏感内容
- ❌ 禁止生成侵权内容
- ✅ 违规内容会被拒绝并可能封号

### 最佳实践

1. **提示词优化**：
   - 使用英文提示词效果更好
   - 包含主体、风格、色彩、构图等细节
   - 长度 50-100 词

2. **参数调优**：
   - `num_inference_steps`: 30（质量与速度平衡）
   - `guidance_scale`: 7.5（通用值）
   - `seed`: 固定值可复现结果

3. **错误处理**：
   - 实现重试机制（3 次）
   - 记录 `request_id` 便于排查
   - 实现熔断降级

---

## 📌 开发清单

- [ ] 配置 API Key 到环境变量
- [ ] 实现 WanxProvider 接口
- [ ] 测试文生图 API
- [ ] 实现提示词优化（可选）
- [ ] 实现错误处理和重试
- [ ] 实现封面缓存
- [ ] 实现健康检查
- [ ] 集成到 AIseek 工作流
- [ ] 添加观测和日志

---

## 🔗 相关资源

| 资源 | 链接 |
|------|------|
| **阿里云百炼控制台** | https://bailian.console.aliyun.com/ |
| **通义万相模型页** | https://bailian.console.aliyun.com/cn-beijing/?tab=model#/model-market/detail/wan2.6-t2i |
| **API Key 管理** | https://bailian.console.aliyun.com/?tab=model#/api-key |
| **官方文档** | https://help.aliyun.com/zh/model-studio/ |
| **价格详情** | https://help.aliyun.com/zh/model-studio/pricing |

---

**文档版本**: v1.0  
**最后更新**: 2026-03-02  
**API Key**: `sk-***`  
**维护者**: AIseek Team
