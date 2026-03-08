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
    return ""


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


def _s3_client(endpoint_url: str, region: str):
    try:
        import boto3
        import botocore.config
    except Exception as e:
        raise SystemExit(f"boto3_missing: {e}")
    extra: Dict[str, str] = {}
    if endpoint_url:
        extra["endpoint_url"] = endpoint_url
    if region:
        extra["region_name"] = region
    # 使用虚拟主机样式访问（阿里云 OSS 要求）
    extra["config"] = botocore.config.Config(
        s3={"addressing_style": "virtual"}
    )
    return boto3.client("s3", **extra)


def _s3_key(prefix: str, filename: str) -> str:
    p = str(prefix or "").strip().strip("/")
    if not p:
        return filename
    return p + "/" + filename


def _list_backups(s3, bucket: str, prefix: str, name: str) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    cont = None
    while True:
        kw = {"Bucket": bucket, "Prefix": prefix} if prefix else {"Bucket": bucket}
        if cont:
            kw["ContinuationToken"] = cont
        resp = s3.list_objects_v2(**kw)
        for it in resp.get("Contents", []) or []:
            k = str(it.get("Key") or "")
            if not k.endswith(".tar.gz"):
                continue
            base = k.rsplit("/", 1)[-1]
            ts = _parse_ts(base, name)
            if ts:
                out.append((ts, base))
        if resp.get("IsTruncated"):
            cont = resp.get("NextContinuationToken")
            continue
        break
    out.sort(key=lambda x: x[0])
    return out


def _delete_backup_set(s3, bucket: str, prefix: str, base: str) -> None:
    if not base.endswith(".tar.gz"):
        return
    prefix_name = base[: -len(".tar.gz")]
    names = [
        base,
        base + ".sha256",
        prefix_name + ".manifest.txt",
        prefix_name + ".filelist.txt",
        prefix_name + ".changes.txt",
        prefix_name + ".README.md",
    ]
    objs = [{"Key": _s3_key(prefix, n)} for n in names]
    try:
        s3.delete_objects(Bucket=bucket, Delete={"Objects": objs, "Quiet": True})
    except Exception:
        for o in objs:
            try:
                s3.delete_object(Bucket=bucket, Key=o["Key"])
            except Exception:
                pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", default="", help="要上传的备份 tar.gz（默认自动选择最新）")
    ap.add_argument("--dir", default="backups", help="备份目录（默认 backups）")
    ap.add_argument("--name", default="AIseek-Trae-v1", help="备份前缀（默认 AIseek-Trae-v1）")
    ap.add_argument("--bucket", default=os.getenv("BACKUP_S3_BUCKET", ""), help="S3 bucket")
    ap.add_argument("--prefix", default=os.getenv("BACKUP_S3_PREFIX", "aiseek-backups"), help="S3 key 前缀")
    ap.add_argument("--endpoint_url", default=os.getenv("BACKUP_S3_ENDPOINT_URL", ""), help="S3 endpoint（R2/MinIO 可用）")
    ap.add_argument("--region", default=os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "")), help="region")
    ap.add_argument("--keep_last_n", type=int, default=int(os.getenv("BACKUP_REMOTE_KEEP_LAST_N", "30") or "30"), help="远端保留最近 N 个备份")
    args = ap.parse_args()

    if not args.bucket:
        raise SystemExit("missing_bucket")

    backups_dir = Path(args.dir).expanduser().resolve()
    archive = Path(args.archive).expanduser().resolve() if args.archive else None
    if not archive:
        archive = _latest_backup_tar(backups_dir, args.name)
    if not archive or not archive.exists():
        raise SystemExit("archive_not_found")

    s3 = _s3_client(args.endpoint_url, args.region)
    sidecars = _build_sidecars(archive)
    for p in sidecars:
        key = _s3_key(args.prefix, p.name)
        s3.upload_file(str(p), args.bucket, key)

    keep = int(args.keep_last_n or 0)
    if keep > 0:
        items = _list_backups(s3, args.bucket, args.prefix.strip().strip("/") + "/" if args.prefix else "", args.name)
        if len(items) > keep:
            doomed = items[: max(0, len(items) - keep)]
            for _, base in doomed:
                _delete_backup_set(s3, args.bucket, args.prefix, base)

    print("ok")


if __name__ == "__main__":
    main()

