import argparse
from pathlib import Path


def _parse_ts(name: str):
    s = str(name or "")
    if "-backup-" not in s:
        return ""
    try:
        ts = s.split("-backup-", 1)[1].split(".tar.gz", 1)[0]
        if len(ts) == 15 and ts[8] == "-":
            return ts
    except Exception:
        return ""
    return ""


def _rm(p: Path) -> None:
    try:
        if p.exists():
            p.unlink()
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="backups", help="备份目录（默认 backups）")
    ap.add_argument("--keep", type=int, default=30, help="保留最近 N 个备份（默认 30）")
    ap.add_argument("--name", default="AIseek-Trae-v1", help="备份前缀（默认 AIseek-Trae-v1）")
    args = ap.parse_args()

    backups_dir = Path(args.dir).expanduser().resolve()
    keep = int(args.keep or 0)
    if keep < 1:
        return

    tars = sorted(backups_dir.glob(f"{args.name}-backup-*.tar.gz"))
    if len(tars) <= keep:
        return

    doomed = tars[: max(0, len(tars) - keep)]
    suffixes = [
        ".tar.gz",
        ".tar.gz.sha256",
        ".manifest.txt",
        ".filelist.txt",
        ".changes.txt",
        ".README.md",
    ]
    for tar in doomed:
        base = tar.name
        ts = _parse_ts(base)
        if not ts:
            continue
        prefix = f"{args.name}-backup-{ts}"
        for suf in suffixes:
            _rm(backups_dir / f"{prefix}{suf}")


if __name__ == "__main__":
    main()

