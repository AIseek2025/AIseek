# 代码/文件快照说明（2026-03-01）

本文档用于记录当前仓库在 2026-03-01 的整体结构、主要入口、运行方式、以及“哪些目录/文件属于代码、哪些属于运行态数据”。配套备份压缩包见 `backups/`。

## 项目概览

- 形态：抖音风格（桌面端）的内容浏览/社交原型
- 后端：FastAPI（模板渲染 + API + 静态资源），默认 SQLite
- 前端：单页交互（Jinja2 模板 + 原生 JS/CSS），主页面为 `backend/templates/index.html`
- 默认运行入口：`backend/app/main.py`

## 目录结构（高层）

- `.github/workflows/`：CI 工作流
- `.trae/documents/`：产品/技术/页面设计文档（PRD/TAD/PDD）
- `backend/`：后端与前端静态资源（模板、JS、CSS、图片、上传文件、数据库）
- `deploy/`：部署相关（k8s、nginx、compose 等）
- `backups/`：仓库快照备份（tar.gz + 校验/清单）
- 根目录若干文档：修复报告、质量检查、重启指南等

## 后端（backend/）

### 入口与应用骨架

- `backend/app/main.py`
  - FastAPI 应用入口
  - 挂载 API 路由（`backend/app/api/v1/`）
  - 渲染模板（`backend/templates/`）
  - 提供静态资源（`backend/static/`）
  - 说明：项目会用 build id 做静态资源 cache busting；模板 `index.html` 也纳入 build 计算，便于前端直接看到最新样式/布局变更

### API 路由

- `backend/app/api/v1/api.py`：v1 路由聚合
- `backend/app/api/v1/endpoints/`：各领域 endpoint（auth、posts、interaction、messages、users、upload 等）
- `backend/app/models/all_models.py`：SQLAlchemy 模型汇总
- `backend/alembic/` + `alembic.ini`：数据库迁移

### 前端模板与静态资源

- `backend/templates/index.html`：主页面模板（包含大部分 UI 结构与内联 CSS）
- `backend/static/js/main.js`：前端脚本加载器（按 build id 拼接 query，加载各模块）
- `backend/static/js/app/`：前端核心业务逻辑（路由、播放器、评论、搜索、个人中心、私信/通知等）
- `backend/static/js/modules/`：事件分发、埋点、运行时、分页等通用模块
- `backend/static/css/style.css`：额外样式（部分页面仍使用）
- `backend/static/img/`：图标、默认背景、官方背景图库（含 `img/backgrounds/*.svg`）
- `backend/static/uploads/`：上传/生成的媒体资源（头像/背景/图片/视频/缩略图等）

### 运行态数据（会随使用变化）

以下文件/目录是运行过程会变化的“状态数据”，不只是代码：

- `backend/data/web.db`、`backend/sql_app.db`：SQLite 数据库文件（可能存在多个历史/实验库）
- `backend/static/uploads/`：上传/生成的媒体内容
- `backend/logs/`：后端与前端事件日志

## 部署（deploy/）

- `deploy/k8s/`：Kubernetes 部署模板（configmap/deployment/service/ingress/hpa 等）
- `deploy/nginx/`：Nginx 配置（含简单配置）
- 根目录的 `docker-compose*.yml`：不同场景的 Compose 编排文件

## 备份（backups/）

本次已生成仓库快照备份（排除 `.git/`、`backups/`、`.venv/`、缓存与 pyc 等）：

- `backups/AIseek-Trae-v1-backup-20260301-145005.tar.gz`
- `backups/AIseek-Trae-v1-backup-20260301-145005.tar.gz.sha256`
- `backups/AIseek-Trae-v1-backup-20260301-145005.manifest.txt`

说明：
- 该备份旨在保留“代码 + 资源 + 数据/上传/日志”等仓库内容快照；虚拟环境需按 `backend/requirements.txt` 重新创建。

## 运行与验证（本地）

参考根目录 `README.md` 的“快速开始”。常用方式：

- 创建并安装依赖：`.venv` + `backend/requirements.txt`
- 启动服务：运行 `backend/app/main.py`（默认端口 5002）
- 浏览器访问：`http://localhost:5002/`

## 近期前端交互/样式变更（摘要级索引）

以下为便于排查/定位的“变更聚焦点”，不是完整变更记录：

- 设置页新增“背景更换”（评论/私聊/通知/个人悬浮窗），官方图库与默认回退：`backend/templates/index.html`、`backend/static/js/app/profile.js`、`backend/static/js/app/core.js`
- 私信/通知顶栏交互与布局微调：`backend/templates/index.html`
- 搜索结果 hover 浮窗贴边优化：`backend/static/js/app/floating_player.js`
- 个人主页 tab 刷新保持与隐私提示（对外隐藏喜欢/收藏/观看历史）：`backend/static/js/app/profile.js`、`backend/static/js/app/core.js`、`backend/templates/index.html`
- 好友页默认展示首位好友作品加载兜底：`backend/static/js/app/core.js`、`backend/static/js/app/profile.js`

