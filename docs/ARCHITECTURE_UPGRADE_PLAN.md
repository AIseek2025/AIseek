# AIseek 2.0 架构升级计划

> 评估时间：2026-03-15 | 评估范围：全量代码审查

---

## 一、现状评估

### 1.1 当前技术栈

| 层级 | 技术 | 评估 |
|------|------|------|
| 前端 | Jinja2 + 原生 JS (player.js 2600行, search.js 4000行) | ⚠️ 维护困难，无法支撑复杂交互 |
| 后端 API | FastAPI + SQLAlchemy + Alembic | ✅ 框架选型正确 |
| 数据库 | PostgreSQL 15 | ✅ 但缺少读写分离和分库分表 |
| 缓存/队列 | Redis 7 | ✅ 但 Stream 非长期存储方案 |
| 搜索 | Elasticsearch 8.13 | ✅ 有降级和熔断机制 |
| 异步任务 | Celery + Redis Broker | ⚠️ 线性管线，无法中间干预 |
| AI 模型 | DeepSeek API (文案) + edge-tts (语音) | ⚠️ max_tokens 过低，prompt 需优化 |
| 视频处理 | FFmpeg (软编码) | ⚠️ 与 AI 运算混在同一 Worker |
| 存储 | Cloudflare R2 / 本地 fallback | ⚠️ 错误处理不够健壮 |
| 可观测 | Prometheus + OpenTelemetry | ✅ 基础完善 |

### 1.2 已发现并修复的关键 Bug

| Bug | 根因 | 修复方案 |
|-----|------|---------|
| 口播稿不是 DeepSeek 返回的 | TTS 读取 22 字截断的 subtitle 而非完整 narration | 分离 narration_segments（TTS）和 subtitle_segments（显示） |
| 字幕看不到 | VTT STYLE 块被注释 + 文本截断过度 | 恢复 VTT 样式，subtitle 上限 22→28 字 |
| 封面图看不到 | 无 AI Key 时直接跳过，视频帧兜底不够健壮 | 三级兜底：AI → 视频帧 → 渐变图 |
| DeepSeek 输出质量差 | max_tokens=2400 过低，相似度阈值 0.88 过敏感 | 动态 max_tokens 3600-6000，阈值放宽到 0.95 |

### 1.3 代码规模统计

- Backend: 约 15,000 行 Python
- Worker: 约 5,000 行 Python
- Frontend JS: 约 12,000 行
- 模板 HTML: 约 7,000 行
- 总计: ~39,000 行核心代码

---

## 二、面向 10 亿级用户的分阶段升级路线

### Phase 1: 稳定期（当前 → Q2 2026）

**目标**：修复所有关键 Bug，跑通 AI 一键出片全链路

#### 已完成 ✅

- [x] TTS 读取完整 narration（而非截断 subtitle）
- [x] VTT 字幕样式恢复，文本截断阈值放宽
- [x] 封面三级兜底（AI → 视频帧 → 渐变图）
- [x] DeepSeek 提示词重构 + 动态 max_tokens
- [x] Sanitizer 截断阈值从 22→28 字，相似度从 0.88→0.95
- [x] storage_service 错误处理增强

#### 待实施

- [ ] 配置 DeepSeek API Key、Wanx/OpenAI 封面 Key
- [ ] 在阿里云部署验证全链路
- [ ] 增加端到端冒烟测试覆盖字幕/封面/口播稿
- [ ] Worker 增加 healthcheck 和死任务检测
- [ ] 增加 AI 创作质量监控面板

### Phase 2: 前端现代化（Q2-Q3 2026）

**目标**：将前端升级为 React + Next.js，支撑创作台交互

#### 架构设计

```
├── frontend/                  # Next.js 14+ App Router
│   ├── app/                   # 页面路由
│   │   ├── (main)/            # 主站（推荐流、精选）
│   │   ├── studio/            # 创作工作台
│   │   ├── admin/             # 管理后台
│   │   └── api/               # BFF 层（代理 FastAPI）
│   ├── components/
│   │   ├── player/            # 视频播放器（HLS + 字幕）
│   │   ├── studio/            # 分镜编辑器、时间轴
│   │   └── shared/            # 通用组件
│   ├── lib/                   # 工具库
│   └── store/                 # Zustand 状态管理
```

#### 关键决策

| 决策点 | 选型 | 理由 |
|--------|------|------|
| 框架 | Next.js 14+ | SSR 保证 SEO，App Router 支持流式渲染 |
| 状态管理 | Zustand | 轻量、TypeScript 友好、比 Redux 简洁 |
| UI 组件库 | shadcn/ui + Tailwind | 可定制、性能好、社区活跃 |
| 视频播放 | hls.js + 自研字幕渲染 | 全平台兼容、字幕样式可控 |
| 3D 预览 | Three.js / React Three Fiber | 未来 3D 骨架预览必备 |

#### 迁移策略

1. **并行运行**：Next.js 新前端和 Jinja2 旧前端共存
2. **API 不变**：后端 FastAPI API 保持不变，Next.js BFF 层代理
3. **渐进迁移**：先迁移 Studio，再迁移播放页，最后迁移管理后台

### Phase 3: 后端微服务化（Q3-Q4 2026）

**目标**：引入任务状态机，解耦计算与渲染

#### 3.1 任务状态机

```
原子化步骤：
  语义解析 → 资源检索 → 骨架绑定 → AI 贴皮 → 音轨合成 → 渲染

每个步骤独立可重试，支持中间干预
```

**选型建议**：

| 方案 | 优势 | 劣势 | 推荐度 |
|------|------|------|--------|
| Temporal | 强一致性、支持长时间工作流、自带重试 | 运维复杂 | ⭐⭐⭐⭐⭐ |
| Airflow | 成熟稳定、UI 好 | 更适合 ETL，不适合实时交互 | ⭐⭐⭐ |
| 自研状态机 | 完全可控 | 开发成本高 | ⭐⭐ |

**推荐 Temporal**：原生支持"暂停-恢复-修改-继续"的工作流模式。

#### 3.2 Worker 拆分

```
┌──────────────────────────────────────────┐
│              API Gateway (FastAPI)         │
└────────────────┬─────────────────────────┘
                 │
         ┌───────┴───────┐
         ▼               ▼
  ┌──────────────┐ ┌──────────────┐
  │ Control Worker│ │ Control Worker│  ← 任务分发/状态追踪
  │  (FastAPI)    │ │  (FastAPI)    │
  └──────┬───────┘ └──────┬───────┘
         │                │
    ┌────┴────┐      ┌────┴────┐
    ▼         ▼      ▼         ▼
┌────────┐┌────────┐┌────────┐┌────────┐
│AI Worker││AI Worker││GPU    ││GPU     │
│DeepSeek ││TTS     ││Render ││Render  │
│文案分析  ││语音合成 ││FFmpeg ││UE5    │
└────────┘└────────┘└────────┘└────────┘
```

### Phase 4: 亿级高可用（2027+）

**目标**：支撑 10 亿级用户 + 百集连续剧生产

#### 4.1 数据层

| 组件 | 当前 | 目标 |
|------|------|------|
| 主库 | 单 PostgreSQL | TiDB / CockroachDB (分布式) |
| 读副本 | 无 | 2+ 只读副本 + ProxySQL |
| 缓存 | 单 Redis | Redis Cluster 6+ 节点 |
| 搜索 | 单 ES | ES Cluster 3+ 节点 |
| 对象存储 | R2 / 本地 | 多区域 CDN + 边缘缓存 |

#### 4.2 前端分发

```
用户 → Cloudflare CDN → Edge Worker（SSR）→ Origin (Next.js)
         ↓
    静态资源直出(HTML/JS/CSS)
         ↓
    HLS 视频流 → CDN 边缘节点
```

#### 4.3 AI 渲染管线（百集连续剧）

```
百万字输入
    ↓
V-Parser（语义分割中间件）
    ↓ 按章节/集分割
    ↓
Temporal Workflow（每集一个子工作流）
    ├── 文案编导 (DeepSeek V4)
    ├── 角色一致性 (Character Sheet Manager)
    ├── 3D 骨架绑定 (Three.js / UE5)
    ├── AI 贴皮渲染 (GPU Cluster)
    ├── 语音合成 (TTS + 情感语音)
    └── 视频合成 + HLS 打包
    ↓
自动发布 + 质量审核
```

---

## 三、优先级排序

| 优先级 | 事项 | 预计工期 | 依赖 |
|--------|------|---------|------|
| P0 | 修复字幕/封面/口播稿 Bug | ✅ 已完成 | 无 |
| P0 | 阿里云部署验证 | 1 天 | Bug 修复 |
| P1 | DeepSeek API Key + 封面 Key 配置 | 1 天 | 无 |
| P1 | 端到端测试覆盖 | 3 天 | Bug 修复 |
| P2 | Next.js 前端初始化 + Studio 迁移 | 2-3 周 | P1 完成 |
| P2 | Worker healthcheck + 监控面板 | 1 周 | P1 完成 |
| P3 | Temporal 集成 | 3-4 周 | P2 完成 |
| P3 | Worker 拆分（AI/GPU/Render） | 4-6 周 | Temporal |
| P4 | 数据层升级（TiDB、Redis Cluster） | 持续 | 用户量增长驱动 |
| P4 | UE5 云渲染管线 | 12+ 周 | GPU 基础设施 |

---

## 四、需要你提供的信息

1. **API Keys**：DeepSeek、Wanx（通义万相）、OpenAI 的 API Key 是否已配置到 `.env.prod`？
2. **阿里云服务器配置**：CPU/内存/GPU 规格？是否有 GPU 实例？
3. **当前用户量**：日活/月活规模，用于确定扩容节奏
4. **预算规划**：前端重构是否计划招聘前端工程师，还是 AI 辅助开发？
5. **3D 渲染需求**：百集连续剧的 3D 风格是写实还是卡通？影响 UE5 vs Three.js 选型
6. **`.docx` 文件**：请转换 `AIseek架构升级 0315.docx` 为 .md 格式供我读取
