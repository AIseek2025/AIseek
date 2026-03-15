# Docker 空间治理手册

## 快速诊断

```bash
df -h /
du -sh ~/Library/Containers/com.docker.docker
docker system df
```

## 快速释放（无业务中断）

```bash
docker builder prune -af
docker image prune -f
docker container prune -f
```

## 定期巡检

```bash
./scripts/docker_space_guard.sh /
./scripts/docker_space_guard.sh / 70
```

第二个参数是阈值百分比，超过阈值会自动执行 Docker 缓存清理。

## 自动化守护（LaunchAgent）

安装（每 6 小时巡检一次，登录即运行一次）：

```bash
./scripts/install_docker_space_guard_launchagent.sh
```

卸载：

```bash
./scripts/uninstall_docker_space_guard_launchagent.sh
```

查看任务状态：

```bash
launchctl print gui/$(id -u)/com.aiseek.docker-space-guard | head -n 40
tail -n 50 ~/Library/Logs/aiseek-docker-space-guard.log
tail -n 50 ~/Library/Logs/aiseek-docker-space-guard.err.log
```

如安装时报 `Bootstrap failed: 5: Input/output error`，执行：

```bash
./scripts/uninstall_docker_space_guard_launchagent.sh
./scripts/install_docker_space_guard_launchagent.sh
```

## 极端场景恢复（Docker Desktop 无法启动）

1. 先清理项目生成目录（如 `backend/static/worker_media`、`worker/data/placeholder_cache`）。
2. 如果仍然无法启动，关闭 Docker Desktop 后处理 `~/Library/Containers/com.docker.docker/Data/vms/0/data/Docker.raw`。
3. 删除 `Docker.raw` 会重置本机 Docker 镜像和容器，重启 Docker Desktop 后重新拉起服务。

## 本仓库已落地的规避措施

- `backend/.dockerignore` 已忽略 `static/worker_media/` 与 `worker_media/`，防止构建上下文膨胀。
- 增加 `scripts/docker_space_guard.sh`，用于阈值化巡检和自动清理。
