import argparse
import hashlib
import tarfile
from datetime import datetime
from pathlib import Path
from typing import Optional


def _now_ts() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_excluded(rel: str) -> bool:
    s = rel.replace("\\", "/")
    if s.startswith("./"):
        s = s[2:]
    if s.startswith("/"):
        s = s[1:]
    if not s or s == ".":
        return True
    if s == ".DS_Store" or s.endswith("/.DS_Store"):
        return True
    if s.startswith(".git/") or s == ".git":
        return True
    if s.startswith("backups/") or s == "backups":
        return True
    if s.startswith(".venv/") or s == ".venv":
        return True
    if s == "backend/gunicorn.ctl":
        return True
    if "/__pycache__/" in f"/{s}/" or s.endswith("/__pycache__"):
        return True
    if s.endswith(".pyc"):
        return True
    return False


def _iter_files(root: Path):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if _is_excluded(rel):
            continue
        yield p, rel


def _latest_backup_tar(backups_dir: Path, name: str) -> Optional[Path]:
    items = sorted(backups_dir.glob(f"{name}-backup-*.tar.gz"))
    return items[-1] if items else None


def _parse_ts_from_name(name: str, prefix: str) -> Optional[datetime]:
    s = str(name or "")
    needle = f"{prefix}-backup-"
    if needle not in s:
        return None
    try:
        tail = s.split(needle, 1)[1]
        ts = tail.split(".tar.gz", 1)[0]
        return datetime.strptime(ts, "%Y%m%d-%H%M%S")
    except Exception:
        return None


def _safe_write(p: Path, data: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    tmp.replace(p)


def _build_backup_readme(prefix: str, prev_name: Optional[str], changes_path: str) -> str:
    lines = []
    lines.append(f"# 备份说明：{prefix}")
    lines.append("")
    lines.append(f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}（本机时间）")
    if prev_name:
        lines.append(f"- 上一次备份：{prev_name}")
    lines.append("")
    lines.append("## 变更清单")
    lines.append(f"- 见同目录文件：`{changes_path}`")
    lines.append("")
    lines.append("## 恢复")
    lines.append("- 推荐恢复到新目录，再手动比对合并需要的配置与数据。")
    lines.append("")
    lines.append("```bash")
    lines.append("python tools/restore_run.py --archive backups/" + prefix + ".tar.gz --dest ./restore-" + prefix.split("backup-")[-1])
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="AIseek-Trae-v1", help="备份前缀（默认 AIseek-Trae-v1）")
    args = ap.parse_args()

    script = Path(__file__).resolve()
    repo_root = script.parents[1]
    backups_dir = repo_root / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    ts = _now_ts()
    prefix = f"{args.name}-backup-{ts}"
    archive = backups_dir / f"{prefix}.tar.gz"

    prev = _latest_backup_tar(backups_dir, args.name)
    prev_name = prev.name if prev else None
    prev_dt = _parse_ts_from_name(prev_name or "", args.name) if prev_name else None

    added = 0
    filelist: list[str] = []
    with tarfile.open(str(archive), "w:gz") as tf:
        for p, rel in _iter_files(repo_root):
            tf.add(str(p), arcname=rel, recursive=False)
            filelist.append(rel)
            added += 1
    filelist.sort()

    sha = _sha256_file(archive)
    _safe_write(backups_dir / f"{prefix}.tar.gz.sha256", f"{sha}  {archive.name}\n")
    _safe_write(backups_dir / f"{prefix}.filelist.txt", "\n".join(filelist) + ("\n" if filelist else ""))

    changed: list[str] = []
    if prev_dt:
        cutoff = prev_dt.timestamp()
        for rel in filelist:
            try:
                p = repo_root / rel
                if p.exists() and p.stat().st_mtime > cutoff:
                    changed.append(rel)
            except Exception:
                continue
    else:
        changed = list(filelist)
    changed.sort()
    _safe_write(backups_dir / f"{prefix}.changes.txt", "\n".join(changed) + ("\n" if changed else ""))

    manifest = []
    manifest.append(f"备份文件：{archive.name}")
    manifest.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}（本机时间）")
    if prev_name:
        manifest.append(f"上一备份：{prev_name}")
    manifest.append(f"SHA256：{sha}")
    manifest.append(f"归档文件数（加入 tar 的文件数）：{added}")
    manifest.append("")
    manifest.append("打包范围：")
    manifest.append("- 以仓库根目录为打包根（包含 backend/、worker/、deploy/、docs/、以及根目录的文档与配置等）")
    manifest.append("")
    manifest.append("排除项（为避免递归与缓存/临时文件膨胀）：")
    manifest.append("- ./.git")
    manifest.append("- ./backups")
    manifest.append("- ./.venv")
    manifest.append("- ./backend/gunicorn.ctl（Unix socket）")
    manifest.append("- **/__pycache__")
    manifest.append("- **/*.pyc")
    manifest.append("- **/.DS_Store")
    manifest.append("")
    manifest.append("说明：")
    manifest.append("- 本备份面向“代码 + 模板 + 前端静态资源 + 部署文件 + 文档 + SQLite/上传文件”等整体快照。")
    manifest.append("- 如需同时备份虚拟环境依赖，请在目标机器上用 backend/requirements.txt 重建 .venv。")
    manifest.append("")
    _safe_write(backups_dir / f"{prefix}.manifest.txt", "\n".join(manifest))
    _safe_write(backups_dir / f"{prefix}.README.md", _build_backup_readme(prefix, prev_name, f"{prefix}.changes.txt"))

    print(str(archive))


if __name__ == "__main__":
    main()

