import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Dict, Iterable, Tuple


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "static"
DIST_DIR = STATIC_DIR / "dist"
RELEASES_DIR = DIST_DIR / "r"
CURRENT_MANIFEST_PATH = DIST_DIR / "manifest.current.json"


def _iter_files(base: Path, subdir: str, exts: Tuple[str, ...]) -> Iterable[Path]:
    d = base / subdir
    if not d.exists():
        return []
    return [p for p in d.rglob("*") if p.is_file() and p.suffix.lower() in exts]


def _hash_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:12]


def _write_file_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as f:
        f.write(data)
    tmp.replace(path)


def _release_id() -> str:
    rid = os.getenv("AISEEK_ASSET_RELEASE", "").strip()
    if rid:
        return rid
    return time.strftime("%Y%m%d-%H%M%S")


def _prune_old_releases(keep: int) -> None:
    try:
        keep_n = int(keep)
    except Exception:
        keep_n = 5
    if keep_n < 1:
        keep_n = 1
    try:
        if not RELEASES_DIR.exists():
            return
        subs = [p for p in RELEASES_DIR.iterdir() if p.is_dir()]
        subs.sort(key=lambda p: p.name, reverse=True)
        for p in subs[keep_n:]:
            try:
                shutil.rmtree(p)
            except Exception:
                pass
    except Exception:
        pass


def build() -> Dict[str, str]:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    RELEASES_DIR.mkdir(parents=True, exist_ok=True)
    rid = _release_id()
    release_root = RELEASES_DIR / rid

    files = []
    files.extend(_iter_files(STATIC_DIR, "js", (".js",)))
    files.extend(_iter_files(STATIC_DIR, "css", (".css",)))

    mapping: Dict[str, str] = {}

    for src in files:
        rel = src.relative_to(STATIC_DIR).as_posix()
        raw = src.read_bytes()
        h = _hash_bytes(raw)
        stem = src.stem
        suffix = src.suffix
        out_rel = f"{src.parent.relative_to(STATIC_DIR).as_posix()}/{stem}.{h}{suffix}"
        out = release_root / out_rel
        _write_file_atomic(out, raw)
        mapping[rel] = f"dist/r/{rid}/{out_rel}"

    release_manifest = DIST_DIR / f"manifest.{rid}.json"
    _write_file_atomic(release_manifest, json.dumps(mapping, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    _write_file_atomic(CURRENT_MANIFEST_PATH, json.dumps(mapping, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    _prune_old_releases(int(os.getenv("AISEEK_ASSET_KEEP", "5") or 5))
    return mapping


def clean() -> None:
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)


if __name__ == "__main__":
    mode = os.getenv("MODE", "").strip().lower()
    if mode in {"clean", "rm"}:
        clean()
    m = build()
    print(f"built {len(m)} assets -> {CURRENT_MANIFEST_PATH}")
