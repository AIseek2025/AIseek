# AIseek Logo 设计规范

**更新日期**: 2026-02-25  
**版本**: v2.0 (SVG 矢量版本)

---

## 🎨 Logo 设计说明

### 设计元素

新 Logo 包含两个核心视觉元素：

1. **光盘 (Disc)** 📀
   - 位于左侧的圆形光盘图标
   - 使用红色渐变 (#fe2c55 → #8b0f2e)
   - 象征音乐、音频内容
   - 带有高光效果和纹理圈，增加立体感

2. **彩色音浪 (Sound Wave)** 🌊
   - 位于光盘右侧的 5 条波浪条
   - 使用粉红渐变 (#fe2c55 ↔ #ff6b8a)
   - 象征声音、视频、动态内容
   - 高度不一，形成节奏感

3. **品牌文字 (Wordmark)** ✍️
   - "AI" - 白色 (#ffffff)
   - "seek" - 品牌红 (#fe2c55)
   - 使用系统字体，保证跨平台一致性

### 配色方案

| 颜色 | 用途 | Hex 值 |
|------|------|--------|
| 品牌红 | 主色调、光盘、音浪 | `#fe2c55` |
| 深红 | 光盘渐变暗部 | `#c41540` |
| 暗红 | 光盘渐变最暗 | `#8b0f2e` |
| 粉红 | 音浪高光 | `#ff6b8a` |
| 白色 | 文字、高光 | `#ffffff` |
| 背景黑 | 透明/深色背景 | `#121212` |

---

## 📁 文件位置

### 主要文件

```
backend/
├── static/
│   └── img/
│       └── logo.svg          # SVG 矢量 Logo (推荐)
└── templates/
    └── index.html            # 已内嵌 SVG 代码
```

### 使用方式

#### 1. 直接内嵌 SVG (推荐 - 首页已使用)

```html
<div class="logo" onclick="app.navigate('home')">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 60" width="180" height="54">
        <!-- SVG 内容 -->
    </svg>
</div>
```

**优点**: 
- ✅ 无需额外 HTTP 请求
- ✅ 可 CSS 控制样式
- ✅ 支持 hover 动画

#### 2. 使用外部 SVG 文件

```html
<img src="/static/img/logo.svg" alt="AIseek Logo" height="40">
```

**优点**:
- ✅ 文件复用方便
- ✅ 易于缓存

---

## 🎯 使用规范

### 最小尺寸

- **Web**: 最小宽度 `120px`
- **移动端**: 最小宽度 `90px`
- ** favicon**: 使用光盘图标部分 (`30x30px`)

### 安全边距

Logo 周围应保持至少 **20%** Logo 高度的空白区域：

```
     ← 20% →
  ┌───────────┐
  │           │
← │   LOGO    │ →
  │           │
  └───────────┘
     ← 20% →
```

### 背景使用

| 背景类型 | 是否可用 | 说明 |
|---------|---------|------|
| 深色背景 | ✅ 推荐 | 默认设计，最佳效果 |
| 浅色背景 | ⚠️ 需调整 | 文字需改为深色 |
| 彩色背景 | ⚠️ 谨慎 | 确保对比度足够 |
| 复杂背景 | ❌ 避免 | 影响识别度 |

### 禁止事项

- ❌ 不要改变 Logo 颜色（除非特殊主题需求）
- ❌ 不要拉伸或变形 Logo
- ❌ 不要添加阴影或特效（已有内建效果）
- ❌ 不要在 Logo 周围添加边框
- ❌ 不要旋转或倾斜 Logo

---

## 🎭 交互效果

### Hover 动画 (已实现)

```css
.logo svg {
    transition: transform 0.2s ease;
}

.logo:hover svg {
    transform: scale(1.05);
}
```

**效果**: 鼠标悬停时放大 5%，增加交互反馈

### 点击反馈

```javascript
// 点击 Logo 返回首页
<div class="logo" onclick="app.navigate('home')">
```

---

## 📐 技术规格

### SVG 文件属性

- **视图框**: `viewBox="0 0 200 60"`
- **宽高比**: `10:3` (3.33:1)
- **格式**: SVG 1.1
- **文件大小**: ~2.5KB (未压缩)

### 响应式适配

```html
<!-- 桌面端 -->
<svg width="180" height="54" ...>

<!-- 平板端 -->
<svg width="150" height="45" ...>

<!-- 移动端 -->
<svg width="120" height="36" ...>
```

### 暗色模式支持

Logo 默认设计已适配暗色模式，无需额外调整。

---

## 🔄 版本历史

### v2.0 (2026-02-25) - 当前版本
- ✅ SVG 矢量格式
- ✅ 光盘 + 音浪设计
- ✅ 渐变效果
- ✅ 内嵌到首页

### v1.0 (之前版本)
- ❌ 纯文字 Logo
- ❌ 使用 Font Awesome 图标
- ❌ 无渐变效果

---

## 💡 使用示例

### 导航栏 (完整代码)

```html
<style>
.navbar {
    display: flex;
    align-items: center;
    height: 60px;
    background: #161823;
    padding: 0 24px;
}

.logo {
    display: flex;
    align-items: center;
    cursor: pointer;
    transition: transform 0.2s ease;
}

.logo:hover svg {
    transform: scale(1.05);
}
</style>

<nav class="navbar">
    <div class="logo" onclick="location.href='/'">
        <svg xmlns="http://www.w3.org/2000/svg" 
             viewBox="0 0 200 60" 
             width="180" 
             height="54">
            <!-- SVG content here -->
        </svg>
    </div>
    <!-- 其他导航元素 -->
</nav>
```

### 页脚 Logo

```html
<footer>
    <div class="footer-logo">
        <img src="/static/img/logo.svg" alt="AIseek" height="40">
        <p>© 2026 AIseek. All rights reserved.</p>
    </div>
</footer>
```

### 登录页面

```html
<div class="auth-logo">
    <svg xmlns="http://www.w3.org/2000/svg" 
         viewBox="0 0 200 60" 
         width="200" 
         height="60">
        <!-- SVG content -->
    </svg>
    <h1>欢迎回到 AIseek</h1>
</div>
```

---

## 🎨 设计灵感

- **光盘**: 致敬传统音乐载体，象征音频内容的本质
- **音浪**: 代表数字化、动态、现代的视觉语言
- **红色**: 热情、活力、创造力，符合短视频平台调性
- **渐变**: 增加层次感和现代感

---

## 📞 联系

如需修改 Logo 或使用其他格式，请联系开发团队。

**文件位置**: `/backend/static/img/logo.svg`  
**主要使用**: `/backend/templates/index.html`
