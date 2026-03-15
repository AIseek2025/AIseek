# 归档脚本

本目录存放一次性或运维调试脚本，非 CI/部署主流程依赖。

## 脚本说明

| 脚本 | 用途 |
|------|------|
| `backfill_ai_missing_scripts.py` | 为 done 的 AIJob 补全 production_script/draft |
| `backfill_missing_video_covers.py` | 为无 cover 的 video post 补封面 |
| `backfill_preview_posts_done.py` | 将 preview post 关联 ai_job_id 并更新状态 |
| `restore_missing_post_from_template.py` | 从模板 post 恢复缺失 post |
| `ai_chain_monitor.py` | 监控 AI chain（HTTP 探测） |
| `post_content_probe.py` | 探测 post 内容与资源可用性 |
| `http_load_test.py` | HTTP 负载测试 |

## 使用方式

从项目根目录执行，例如：

```bash
PYTHONPATH=backend python backend/scripts/archive/backfill_missing_video_covers.py
```
