# 占位视频平台 API 对接文档

> **项目**: AIseek-Trae-v1 - AI 创作模式短视频平台  
> **版本**: v1.0  
> **创建时间**: 2026-03-02  
> **用途**: 对接海量占位视频平台 API，实现语义匹配选素材功能

---

## 📺 推荐平台总览

| 平台 | 视频库 | 免费额度 | 商用许可 | API 质量 | 推荐度 |
|------|--------|---------|---------|---------|--------|
| **Pixabay** | 2.8M+ | 100 次/分钟 | ✅ 免署名 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Pexels** | 1M+ | 400 次/小时 | ✅ 免署名 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Mixkit** | 100K+ | 无限制 | ✅ 免署名 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Coverr** | 5K+ | 无限制 | ✅ 免署名 | ⭐⭐⭐ | ⭐⭐⭐ |

---

## 1️⃣ Pixabay API（首选推荐）

### 📋 基本信息

- **API 文档**: https://pixabay.com/api/docs/
- **Base URL**: `https://pixabay.com/api/`
- **鉴权方式**: API Key（查询参数）
- **注册获取**: https://pixabay.com/api/docs/#api_search_images

### 🔐 鉴权方式

```http
GET https://pixabay.com/api/?key={YOUR_API_KEY}&q=搜索词
```

| 项目 | 说明 |
|------|------|
| **类型** | API Key |
| **位置** | URL Query Parameter |
| **参数名** | `key` |
| **获取方式** | 注册登录后在 https://pixabay.com/api/docs/ 查看 |

### 📊 限流策略

| 指标 | 数值 |
|------|------|
| **默认限制** | 100 次/60 秒 |
| **缓存要求** | 必须缓存 24 小时 |
| **提升限制** | 可申请提高 |
| **响应头** | `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` |

### 🎬 核心接口

#### 1. 搜索视频

```http
GET https://pixabay.com/api/
```

**请求参数**:

| 参数 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| `key` | string | ✅ | API Key | `your_api_key` |
| `q` | string | ❌ | 搜索关键词（URL 编码） | `ocean+sunset` |
| `image_type` | string | ❌ | 媒体类型 | `photo`, `illustration`, `vector` |
| `orientation` | string | ❌ | 方向 | `all`, `horizontal`, `vertical` |
| `min_width` | int | ❌ | 最小宽度 | `1920` |
| `min_height` | int | ❌ | 最小高度 | `1080` |
| `category` | string | ❌ | 分类 | `nature`, `people`, `backgrounds` |
| `order` | string | ❌ | 排序 | `popular`, `latest` |
| `page` | int | ❌ | 页码 | `1` |
| `per_page` | int | ❌ | 每页数量 (3-200) | `20` |
| `lang` | string | ❌ | 语言代码 | `en`, `zh` |

**请求示例**:

```bash
curl "https://pixabay.com/api/?key=YOUR_API_KEY&q=ocean+sunset&image_type=photo&orientation=horizontal&min_width=1920&per_page=20"
```

**响应示例**:

```json
{
  "total": 4692,
  "totalHits": 500,
  "hits": [
    {
      "id": 195893,
      "pageURL": "https://pixabay.com/en/blossom-bloom-flower-195893/",
      "type": "photo",
      "tags": "blossom, bloom, flower",
      "previewURL": "https://cdn.pixabay.com/photo/2013/10/15/09/12/flower-195893_150.jpg",
      "previewWidth": 150,
      "previewHeight": 84,
      "webformatURL": "https://pixabay.com/get/35bbf209e13e39d2_640.jpg",
      "webformatWidth": 640,
      "webformatHeight": 360,
      "largeImageURL": "https://pixabay.com/get/ed6a99fd0a76647_1280.jpg",
      "fullHDURL": "https://pixabay.com/get/ed6a9369fd0a76647_1920.jpg",
      "imageURL": "https://pixabay.com/get/ed6a9364a9fd0a76647.jpg",
      "imageWidth": 4000,
      "imageHeight": 2250,
      "imageSize": 4731420,
      "views": 7671,
      "downloads": 6439,
      "likes": 5,
      "comments": 2,
      "user_id": 48777,
      "user": "Josch13",
      "userImageURL": "https://cdn.pixabay.com/user/2013/11/05/02-10-23-764_250x250.jpg"
    }
  ]
}
```

**响应字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `total` | int | 总命中数 |
| `totalHits` | int | API 可返回的最大数量（默认 500） |
| `hits[].id` | int | 唯一标识符 |
| `hits[].pageURL` | string | 来源页面（含下载链接） |
| `hits[].previewURL` | string | 预览图（150px） |
| `hits[].webformatURL` | string | 中等尺寸（640px，24 小时有效） |
| `hits[].largeImageURL` | string | 大尺寸（1280px） |
| `hits[].fullHDURL` | string | 全高清（1920px） |
| `hits[].imageURL` | string | 原始尺寸 |
| `hits[].imageWidth/Height` | int | 分辨率 |
| `hits[].imageSize` | int | 文件大小（字节） |
| `hits[].user` | string | 作者名 |

#### 2. 获取视频详情

Pixabay 通过 ID 获取单个资源：

```http
GET https://pixabay.com/api/?key=YOUR_API_KEY&id=195893
```

#### 3. 下载视频

Pixabay 视频需要访问 `pageURL` 获取下载链接，或直接使用 `largeImageURL` / `fullHDURL`。

---

### 📜 版权与商用许可

| 项目 | 说明 |
|------|------|
| **商用许可** | ✅ 允许商业用途 |
| **署名要求** | ❌ 不需要署名（但建议） |
| **修改权限** | ✅ 允许修改、剪辑 |
| **地区限制** | ❌ 无地区限制 |
| **许可证** | [Pixabay Content License](https://pixabay.com/service/terms/) |

**允许用途**:
- ✅ 商业视频制作
- ✅ 社交媒体内容
- ✅ 广告营销
- ✅ 教育内容
- ✅ 修改和二次创作

**禁止用途**:
- ❌ 转售原始素材
- ❌ 批量下载建立竞争服务
- ❌ 用于违法内容

---

### 🔔 Webhook/回调支持

| 功能 | 支持情况 |
|------|---------|
| **素材更新通知** | ❌ 不支持 |
| **下架通知** | ❌ 不支持 |
| **推荐方案** | 定期轮询 + 本地缓存校验 |

---

## 2️⃣ Pexels API（备选推荐）

### 📋 基本信息

- **API 文档**: https://www.pexels.com/api/documentation/
- **Base URL**: `https://api.pexels.com/videos/v1/`
- **鉴权方式**: API Key（HTTP Header）
- **注册获取**: https://www.pexels.com/api/

### 🔐 鉴权方式

```http
GET https://api.pexels.com/videos/v1/search?query=nature
Authorization: YOUR_API_KEY
```

| 项目 | 说明 |
|------|------|
| **类型** | API Key |
| **位置** | HTTP Header |
| **Header 名** | `Authorization` |
| **获取方式** | 注册后在 https://www.pexels.com/api/ 获取 |

### 📊 限流策略

| 指标 | 数值 |
|------|------|
| **默认限制** | 400 次/小时 |
| **提升限制** | 可申请 |
| **缓存要求** | 建议缓存 |

### 🎬 核心接口

#### 1. 搜索视频

```http
GET https://api.pexels.com/videos/v1/search
```

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | ✅ | 搜索关键词 |
| `per_page` | int | ❌ | 每页数量 (10-80) |
| `page` | int | ❌ | 页码 |
| `orientation` | string | ❌ | `landscape`, `portrait`, `square` |
| `size` | string | ❌ | `medium`, `large`, `small` |

**请求示例**:

```bash
curl -X GET "https://api.pexels.com/videos/v1/search?query=ocean&per_page=15&orientation=landscape" \
  -H "Authorization: YOUR_API_KEY"
```

**响应示例**:

```json
{
  "total": 1234,
  "page": 1,
  "per_page": 15,
  "videos": [
    {
      "id": 1234567,
      "title": "Ocean Waves",
      "description": "Beautiful ocean waves at sunset",
      "url": "https://www.pexels.com/video/1234567/",
      "image": "https://images.pexels.com/videos/1234567/pictures/preview-0.jpg",
      "duration": 15,
      "width": 1920,
      "height": 1080,
      "user": {
        "id": 98765,
        "name": "John Doe",
        "url": "https://www.pexels.com/@johndoe"
      },
      "video_files": [
        {
          "id": 1,
          "quality": "hd",
          "file_type": "video/mp4",
          "width": 1920,
          "height": 1080,
          "link": "https://player.vimeo.com/external/1234567.hd.mp4"
        },
        {
          "id": 2,
          "quality": "sd",
          "file_type": "video/mp4",
          "width": 640,
          "height": 360,
          "link": "https://player.vimeo.com/external/1234567.sd.mp4"
        }
      ],
      "video_pictures": [
        {
          "id": 1,
          "picture": "https://images.pexels.com/videos/1234567/pictures/preview-0.jpg"
        }
      ]
    }
  ]
}
```

**响应字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `videos[].id` | int | 视频 ID |
| `videos[].title` | string | 标题 |
| `videos[].description` | string | 描述 |
| `videos[].duration` | int | 时长（秒） |
| `videos[].width/height` | int | 分辨率 |
| `videos[].video_files[].quality` | string | 质量 (`hd`, `sd`, `uhd`, `original`) |
| `videos[].video_files[].link` | string | **下载链接**（直接可用） |
| `videos[].video_files[].file_type` | string | 文件类型 |

#### 2. 获取精选视频

```http
GET https://api.pexels.com/videos/v1/popular
GET https://api.pexels.com/videos/v1/trending
GET https://api.pexels.com/videos/v1/featured
```

#### 3. 获取视频详情

```http
GET https://api.pexels.com/videos/v1/{video_id}
```

---

### 📜 版权与商用许可

| 项目 | 说明 |
|------|------|
| **商用许可** | ✅ 允许商业用途 |
| **署名要求** | ❌ 不需要（但建议） |
| **修改权限** | ✅ 允许修改 |
| **许可证** | [Pexels License](https://www.pexels.com/license/) |

---

## 3️⃣ Mixkit（备选）

### 📋 基本信息

- **网站**: https://mixkit.co/
- **API 状态**: 无官方公开 API
- **替代方案**: 直接下载或使用 Envato API
- **许可证**: 免费商用
- **特点**: Envato 旗下，高质量免费素材

---

## 4️⃣ Coverr（备选）

### 📋 基本信息

- **API 文档**: https://coverr.co/api
- **Base URL**: `https://coverr.co/api/`
- **鉴权方式**: 无需 API Key（部分接口）
- **许可证**: 免费商用

### 🎬 核心接口

```http
GET https://coverr.co/api/
GET https://coverr.co/api/videos/{id}
```

---

## 🏗️ 推荐实现架构

### PlaceholderProvider 接口定义

```typescript
interface PlaceholderProvider {
  name: string;
  priority: number; // 优先级，数字越大优先级越高
  
  // 搜索视频素材
  search(params: SearchParams): Promise<SearchResults>;
  
  // 选择最佳匹配
  pick(query: Query, options: PickOptions): Promise<VideoClip>;
  
  // 获取下载地址
  fetch(videoId: string, quality?: Quality): Promise<DownloadInfo>;
}

interface SearchParams {
  keywords: string[];      // 关键词
  theme?: string;          // 主题
  emotion?: string;        // 情绪
  duration?: number;       // 目标时长（秒）
  aspectRatio?: string;    // '16:9' | '9:16' | '1:1'
  minResolution?: string;  // '720p' | '1080p' | '4k'
  page?: number;
  perPage?: number;
}

interface SearchResults {
  total: number;
  hits: VideoClip[];
  hasMore: boolean;
}

interface VideoClip {
  id: string;
  provider: string;
  title: string;
  description?: string;
  tags: string[];
  duration: number;        // 秒
  width: number;
  height: number;
  resolution: string;      // '720p' | '1080p' | '4k'
  aspectRatio: string;
  previewUrl: string;
  downloadUrl: string;
  fileSize?: number;       // 字节
  license: LicenseInfo;
  author?: string;
  score?: number;          // 匹配度评分
}

interface LicenseInfo {
  commercialUse: boolean;  // 可否商用
  attributionRequired: boolean; // 是否需署名
  modificationsAllowed: boolean; // 可否修改
  regionRestrictions?: string[]; // 地区限制
}

interface DownloadInfo {
  url: string;
  expiresAt?: Date;        // URL 过期时间
  quality: string;
  fileSize: number;
  contentType: string;
}
```

---

### 多 Provider 配置示例

```typescript
const providers: PlaceholderProvider[] = [
  {
    name: 'pixabay',
    priority: 10,
    apiKey: process.env.PIXABAY_API_KEY,
    baseUrl: 'https://pixabay.com/api/',
    rateLimit: { requests: 100, windowMs: 60000 },
    cacheTTL: 24 * 60 * 60 * 1000, // 24 小时
  },
  {
    name: 'pexels',
    priority: 9,
    apiKey: process.env.PEXELS_API_KEY,
    baseUrl: 'https://api.pexels.com/videos/v1/',
    rateLimit: { requests: 400, windowMs: 3600000 }, // 每小时
    cacheTTL: 24 * 60 * 60 * 1000,
  },
  {
    name: 'local-cache',
    priority: 5, // 本地缓存优先级最低（作为降级）
    cachePath: './data/video-cache',
  }
];
```

---

### 失败降级策略

```typescript
async function searchWithFallback(query: Query): Promise<VideoClip[]> {
  // 1. 按优先级尝试各 Provider
  for (const provider of providers.sort((a, b) => b.priority - a.priority)) {
    try {
      const results = await provider.search(query);
      if (results.hits.length > 0) {
        // 缓存结果
        await cacheResults(query, results);
        return results.hits;
      }
    } catch (error) {
      console.warn(`Provider ${provider.name} failed:`, error);
      // 继续尝试下一个
    }
  }
  
  // 2. 所有 Provider 失败，使用本地缓存
  const cached = await getFromCache(query);
  if (cached) return cached;
  
  // 3. 最后降级：返回默认背景视频
  return getDefaultBackgroundVariants();
}
```

---

## 📊 10 亿用户规模优化建议

### 缓存策略

```typescript
// 三级缓存架构
const cacheStrategy = {
  L1: {
    name: '内存缓存',
    ttl: 5 * 60 * 1000, // 5 分钟
    maxSize: 10000, // 最多 1 万条
  },
  L2: {
    name: 'Redis 缓存',
    ttl: 24 * 60 * 60 * 1000, // 24 小时
    pattern: 'video:search:{query_hash}',
  },
  L3: {
    name: '本地存储',
    ttl: 7 * 24 * 60 * 60 * 1000, // 7 天
    path: './data/video-cache/',
  }
};
```

### 预取策略

```typescript
// 热门主题预取
const popularThemes = [
  'nature', 'business', 'technology', 'lifestyle',
  'travel', 'food', 'sports', 'music'
];

async function prefetchPopularThemes() {
  for (const theme of popularThemes) {
    await searchWithFallback({ keywords: [theme] });
  }
}

// 每天凌晨 3 点执行
cron.schedule('0 3 * * *', prefetchPopularThemes);
```

---

## 🚀 开发配置包

### 1. 环境变量配置

```bash
# .env
PIXABAY_API_KEY=your_pixabay_api_key
PEXELS_API_KEY=your_pexels_api_key

# 缓存配置
VIDEO_CACHE_TTL=86400000  # 24 小时
VIDEO_CACHE_PATH=./data/video-cache
REDIS_URL=redis://localhost:6379
```

### 2. API 密钥获取链接

- **Pixabay**: https://pixabay.com/api/docs/#api_search_images（登录后查看）
- **Pexels**: https://www.pexels.com/api/

### 3. 测试调用示例

```bash
# Pixabay 测试
curl "https://pixabay.com/api/?key=YOUR_API_KEY&q=nature&image_type=photo"

# Pexels 测试
curl -X GET "https://api.pexels.com/videos/v1/search?query=nature" \
  -H "Authorization: YOUR_API_KEY"
```

---

## 📝 总结

### 推荐方案

**首选 Pixabay** + **备选 Pexels** + **本地缓存降级**

| 特性 | Pixabay | Pexels |
|------|---------|--------|
| 视频数量 | 2.8M+ | 1M+ |
| 限流 | 100 次/分钟 | 400 次/小时 |
| 鉴权 | URL 参数 | HTTP Header |
| 商用 | ✅ | ✅ |
| 署名 | 不需要 | 不需要 |
| API 质量 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## 📌 开发清单

- [ ] 实现 `PlaceholderProvider` 接口
- [ ] 集成 Pixabay API（首选）
- [ ] 集成 Pexels API（备选）
- [ ] 实现语义匹配（embedding + 规则）
- [ ] 实现三级缓存系统
- [ ] 实现失败降级策略
- [ ] 实现热门主题预取
- [ ] 配置 API Key 到环境变量
- [ ] 测试搜索/选择/下载全流程

---

**文档版本**: v1.0  
**最后更新**: 2026-03-02  
**维护者**: AIseek Team
