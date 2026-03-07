import argparse
import hashlib
import tarfile
from datetime import datetime
from pathlib import Path


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_member_name(name: str) -> bool:
    n = str(name or "").replace("\\", "/")
    if not n:
        return False
    if n.startswith("/") or n.startswith("../") or "/../" in f"/{n}":
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", required=True, help="备份 tar.gz 路径")
    ap.add_argument("--dest", default="", help="解压目标目录（默认 ./restore-YYYYMMDD-HHMMSS）")
    ap.add_argument("--skip_sha256", action="store_true", help="跳过 sha256 校验")
    args = ap.parse_args()

    archive = Path(args.archive).expanduser().resolve()
    if not archive.exists():
        raise SystemExit(f"archive_not_found: {archive}")

    sha_file = archive.with_suffix(archive.suffix + ".sha256")
    if not args.skip_sha256 and sha_file.exists():
        raw = sha_file.read_text(encoding="utf-8", errors="ignore").strip()
        want = (raw.split() or [""])[0].strip()
        got = _sha256_file(archive)
        if want and want != got:
            raise SystemExit(f"sha256_mismatch: want={want} got={got}")

    dest = Path(args.dest).expanduser().resolve() if args.dest else Path.cwd() / ("restore-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    dest.mkdir(parents=True, exist_ok=True)

    with tarfile.open(str(archive), "r:gz") as tf:
        members = tf.getmembers()
        safe = []
        for m in members:
            if _safe_member_name(m.name):
                safe.append(m)
            else:
                raise SystemExit(f"unsafe_path_in_archive: {m.name}")
        tf.extractall(path=str(dest), members=safe)

    print(str(dest))


if __name__ == "__main__":
    main()

