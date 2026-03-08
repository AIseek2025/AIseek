import argparse
import os
import subprocess
from pathlib import Path


def _run(cmd: list[str]) -> str:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if p.returncode != 0:
        raise SystemExit(p.stdout.strip() or "cmd_failed")
    return (p.stdout or "").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default=os.getenv("BACKUP_NAME", "AIseek-Trae-v1"))
    ap.add_argument("--backups_dir", default=os.getenv("BACKUPS_DIR", "backups"))
    ap.add_argument("--keep_local", type=int, default=int(os.getenv("BACKUP_KEEP_LAST_N", "30") or "30"))
    ap.add_argument("--keep_remote", type=int, default=int(os.getenv("BACKUP_REMOTE_KEEP_LAST_N", "30") or "30"))
    ap.add_argument("--require_remote", action="store_true", default=(os.getenv("BACKUP_REQUIRE_REMOTE", "0") in {"1", "true", "TRUE", "yes", "YES"}))
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    os.chdir(str(repo_root))

    archive_path = _run(["python", "tools/backup_run.py", "--name", args.name])

    bucket = os.getenv("BACKUP_S3_BUCKET", "").strip()
    if args.require_remote and not bucket:
        raise SystemExit("missing_BACKUP_S3_BUCKET")
    if bucket:
        _run(
            [
                "python",
                "tools/backup_upload_s3.py",
                "--archive",
                archive_path,
                "--dir",
                args.backups_dir,
                "--name",
                args.name,
                "--bucket",
                bucket,
                "--prefix",
                os.getenv("BACKUP_S3_PREFIX", "aiseek-backups"),
                "--endpoint_url",
                os.getenv("BACKUP_S3_ENDPOINT_URL", ""),
                "--access_key_id",
                os.getenv("AWS_ACCESS_KEY_ID", ""),
                "--access_key_secret",
                os.getenv("AWS_SECRET_ACCESS_KEY", ""),
                "--keep_last_n",
                str(args.keep_remote),
            ]
        )

    _run(["python", "tools/backup_prune.py", "--dir", args.backups_dir, "--keep", str(args.keep_local), "--name", args.name])

    print(archive_path)


if __name__ == "__main__":
    main()
