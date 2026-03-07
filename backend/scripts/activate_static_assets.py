import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "static" / "dist"
CURRENT = DIST_DIR / "manifest.current.json"


def _write_file_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as f:
        f.write(data)
    tmp.replace(path)


def activate(release_id: str) -> None:
    rid = str(release_id or "").strip()
    if not rid:
        raise SystemExit("release_id required")
    src = DIST_DIR / f"manifest.{rid}.json"
    if not src.exists():
        raise SystemExit(f"manifest not found: {src}")
    raw = src.read_text(encoding="utf-8", errors="ignore")
    obj = json.loads(raw or "{}")
    if not isinstance(obj, dict) or not obj:
        raise SystemExit("invalid manifest")
    _write_file_atomic(CURRENT, json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


if __name__ == "__main__":
    rid = os.getenv("AISEEK_ASSET_RELEASE", "").strip() or (os.sys.argv[1] if len(os.sys.argv) > 1 else "")
    activate(rid)
    print(f"activated {rid} -> {CURRENT}")
