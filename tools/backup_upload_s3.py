#!/usr/bin/env python3
"""
AIseek 备份上传到阿里云 OSS
使用阿里云官方 oss2 SDK（避免 boto3 的 aws-chunked 编码问题）
"""
import argparse
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def _parse_ts(name: str, prefix: str) -> str:
    s = str(name or "")
    needle = f"{prefix}-backup-"
    if needle not in s:
        return ""
    try:
        tail = s.split(needle, 1)[1]
        ts = tail.split(".tar.gz", 1)[0]
        if len(ts) == 15 and ts[8] == "-":
            return ts
    except Exception:
        return ""
    return ts


def _latest_backup_tar(backups_dir: Path, name: str) -> Optional[Path]:
    items = sorted(backups_dir.glob(f"{name}-backup-*.tar.gz"))
    return items[-1] if items else None


def _build_sidecars(archive: Path) -> List[Path]:
    p = archive
    base = p.name
    if not base.endswith(".tar.gz"):
        return [p]
    prefix = base[: -len(".tar.gz")]
    out = [
        p,
        p.with_suffix(p.suffix + ".sha256"),
        p.with_name(prefix + ".manifest.txt"),
        p.with_name(prefix + ".filelist.txt"),
        p.with_name(prefix + ".changes.txt"),
        p.with_name(prefix + ".README.md"),
    ]
    return [x for x in out if x.exists()]


def _oss_client(endpoint: str, access_key: str, secret_key: str):
    """创建阿里云 OSS 客户端"""
    try:
        import oss2
    except Exception as e:
        raise SystemExit(f"oss2_missing: {e}")
    
    auth = oss2.Auth(access_key, secret_key)
    return auth, oss2


def _oss_key(prefix: str, filename: str) -> str:
    p = str(prefix or "").strip().strip("/")
    if not p:
        return filename
    return p + "/" + filename


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", default="", help="要上传的备份 tar.gz（默认自动选择最新）")
    ap.add_argument("--dir", default="backups", help="备份目录（默认 backups）")
    ap.add_argument("--name", default="AIseek-Trae-v1", help="备份前缀（默认 AIseek-Trae-v1）")
    ap.add_argument("--bucket", default=os.getenv("BACKUP_S3_BUCKET", ""), help="OSS bucket")
    ap.add_argument("--prefix", default=os.getenv("BACKUP_S3_PREFIX", "aiseek-backups"), help="OSS key 前缀")
    ap.add_argument("--endpoint_url", default=os.getenv("BACKUP_S3_ENDPOINT_URL", ""), help="OSS endpoint")
    ap.add_argument("--access_key_id", default=os.getenv("AWS_ACCESS_KEY_ID", ""), help="AccessKey ID")
    ap.add_argument("--access_key_secret", default=os.getenv("AWS_SECRET_ACCESS_KEY", ""), help="AccessKey Secret")
    ap.add_argument("--keep_last_n", type=int, default=int(os.getenv("BACKUP_REMOTE_KEEP_LAST_N", "30") or "30"), help="远端保留最近 N 个备份")
    args = ap.parse_args()

    if not args.bucket:
        raise SystemExit("missing_bucket")
    if not args.access_key_id or not args.access_key_secret:
        raise SystemExit("missing_credentials")

    backups_dir = Path(args.dir).expanduser().resolve()
    archive = Path(args.archive).expanduser().resolve() if args.archive else None
    if not archive:
        archive = _latest_backup_tar(backups_dir, args.name)
    if not archive or not archive.exists():
        raise SystemExit("archive_not_found")

    # 创建 OSS 客户端
    auth, oss2 = _oss_client(args.endpoint_url, args.access_key_id, args.access_key_secret)
    bucket = oss2.Bucket(auth, args.endpoint_url, args.bucket)
    
    # 上传文件
    sidecars = _build_sidecars(archive)
    for p in sidecars:
        key = _oss_key(args.prefix, p.name)
        print(f"Uploading {p.name} to {key}...")
        bucket.put_object_from_file(key, str(p))

    print("ok")


if __name__ == "__main__":
    main()
