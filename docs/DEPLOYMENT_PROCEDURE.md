# AIseek 标准发布流程

## 📋 发布方式

### 方式一：标准发布（推荐新手）

交互式发布，会显示更改并请求确认。

```bash
cd /Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1
bash scripts/git-deploy.sh
```

**流程：**
1. ✅ 检查 Git 状态（显示待提交的文件）
2. ✅ 确认提交（需要手动确认）
3. ✅ 提交并推送到 GitHub
4. ✅ SSH 登录服务器拉取代码
5. ✅ 重启 Backend 和 Nginx 服务
6. ✅ 自动健康检查

---

### 方式二：快速发布（推荐老手）

一键发布，无需确认。

```bash
# 使用默认提交信息
bash scripts/deploy-quick.sh

# 自定义提交信息
bash scripts/deploy-quick.sh "fix: 修复 HLS 播放问题"
```

**流程：**
1. ✅ 自动提交并推送
2. ✅ 服务器自动更新并重启
3. ✅ 快速健康检查

---

## 🔧 手动发布步骤

如果脚本失败，可以手动执行：

### 1. 本地提交
```bash
cd /Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1
git add -A
git commit -m "fix: 你的修复说明"
git push origin main
```

### 2. 服务器更新
```bash
ssh aliyun
cd /root/AIseek-Trae-v1
git pull origin main
```

### 3. 重启服务
```bash
cd /root/AIseek-Trae-v1/deploy/aliyun
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build backend nginx
```

### 4. 健康检查
```bash
# 检查容器状态
docker compose ps

# 检查 HTTP 访问
curl -I http://localhost/

# 检查静态文件
curl -I http://localhost/static/js/app/studio.js

# 查看日志
docker compose logs -f backend
```

---

## 📝 发布清单

发布前检查：
- [ ] 代码已本地测试
- [ ] Git 状态正常
- [ ] SSH 可以连接服务器 (`ssh aliyun`)
- [ ] 服务器磁盘空间充足

发布后验证：
- [ ] 网站可以正常访问
- [ ] 修复的功能已生效
- [ ] 没有新的错误日志
- [ ] 静态文件已更新（检查版本号/时间戳）

---

## 🚨 常见问题

### Q: SSH 连接失败
```bash
# 添加 SSH 密钥
ssh-add ~/.ssh/id_ed25519

# 测试连接
ssh aliyun
```

### Q: 端口被占用
```bash
# 停止所有旧容器
ssh aliyun "docker ps -aq | xargs docker stop"

# 重新启动
ssh aliyun "cd /root/AIseek-Trae-v1/deploy/aliyun && docker compose up -d"
```

### Q: 静态文件未更新
```bash
# 强制清除浏览器缓存
# Chrome: Cmd+Shift+R (Mac) / Ctrl+Shift+R (Windows)

# 或者检查文件时间戳
ssh aliyun "ls -la /root/AIseek-Trae-v1/backend/static/js/app/studio.js"
```

### Q: 回滚到上一个版本
```bash
ssh aliyun "cd /root/AIseek-Trae-v1 && git log --oneline -5"
ssh aliyun "cd /root/AIseek-Trae-v1 && git reset --hard <commit-hash>"
ssh aliyun "cd /root/AIseek-Trae-v1/deploy/aliyun && docker compose up -d --build"
```

---

## 📊 监控命令

```bash
# 实时日志
ssh aliyun "docker compose logs -f backend nginx"

# 查看资源使用
ssh aliyun "docker stats"

# 检查容器状态
ssh aliyun "docker compose ps"

# 查看磁盘空间
ssh aliyun "df -h"
```

---

**最后更新**: 2026-03-10  
**维护者**: AIseek 团队
