# Kubernetes Deployment

## 目标
在 Kubernetes 上实现无状态 Web 水平扩展、HPA 自动伸缩、滚动升级、就绪/存活探针、Worker 异步扩展，并将数据库/缓存/搜索等关键依赖外置为高可用服务。

## 目录
- `deploy/k8s/`：kustomize 资源清单（Deployment/Service/HPA/PDB/Ingress/ConfigMap/Secret 示例）

## 关键约束
- Web 必须无状态：所有状态放在 DB/Redis/对象存储，Pod 可随时被替换。
- 静态资源与媒体文件建议走 CDN：应用只返回 URL 与元数据。
- 数据库/Redis/ES 推荐使用托管或成熟 Helm Chart；本仓库的 k8s 清单默认把它们视为外部依赖（通过环境变量接入）。

## 就绪与存活探针
后端提供：
- `/livez`：进程存活
- `/readyz`：就绪检查（默认检查 DB；`READINESS_STRICT=1` 时会额外检查 Redis）

## 配置方式
### ConfigMap
- [backend-configmap.yaml](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/deploy/k8s/backend-configmap.yaml)

### Secret
- [backend-secret.example.yaml](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/deploy/k8s/backend-secret.example.yaml)

## 伸缩策略
- Web：HPA 基于 CPU，`min=3 max=60`，配合 PDB `minAvailable=2`
- Worker：HPA 基于 CPU，`min=1 max=30`（实际生产更建议按队列积压指标伸缩）

## 应用发布
### 镜像
清单里使用：
- `aiseek-backend:latest`
- `aiseek-worker:latest`

生产应替换为带版本号的镜像标签，并启用镜像仓库拉取凭据。

### 应用资源
使用 kustomize：
- [kustomization.yaml](file:///Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/deploy/k8s/kustomization.yaml)

## 数据层建议（生产）
- Postgres：主从 + 读写分离；热点表做分区；极限规模按业务域拆库拆表。
- Redis：Cluster/哨兵或托管服务；限制连接数与超时，避免雪崩。
- Elasticsearch：独立集群，应用侧设置超时与重试，避免搜索拖垮主链路。
- 对象存储 + CDN：媒体文件与静态资源走 CDN，应用节点只处理动态 API 与鉴权。
