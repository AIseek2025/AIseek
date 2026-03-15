import json
import os
import secrets
from pathlib import Path
from typing import Dict, Optional


class AssetManifest:
    def __init__(self, manifest_path: Path):
        self.manifest_path = manifest_path
        self._mtime: int = 0
        self._data: Dict[str, str] = {}

    def _load_if_needed(self) -> None:
        try:
            st = self.manifest_path.stat()
            mt = int(getattr(st, "st_mtime", 0) or 0)
        except Exception:
            mt = 0
        if not mt:
            self._mtime = 0
            self._data = {}
            return
        if mt == self._mtime and self._data:
            return
        try:
            raw = self.manifest_path.read_text(encoding="utf-8", errors="ignore")
            obj = json.loads(raw or "{}")
            if isinstance(obj, dict):
                self._data = {str(k): str(v) for k, v in obj.items()}
                self._mtime = mt
                return
        except Exception:
            pass
        self._mtime = mt
        self._data = {}

    def resolve(self, logical_path: str) -> Optional[str]:
        p = str(logical_path or "").strip().lstrip("/")
        if not p:
            return None
        self._load_if_needed()
        v = self._data.get(p)
        if not v:
            return None
        v = str(v).lstrip("/")
        return "/static/" + v


class RolloutConfig:
    def __init__(self, path: Path):
        self.path = path
        self._mtime: int = 0
        self._data: Dict[str, object] = {}

    def _load_if_needed(self) -> None:
        try:
            st = self.path.stat()
            mt = int(getattr(st, "st_mtime", 0) or 0)
        except Exception:
            mt = 0
        if not mt:
            self._mtime = 0
            self._data = {}
            return
        if mt == self._mtime and self._data:
            return
        try:
            raw = self.path.read_text(encoding="utf-8", errors="ignore")
            obj = json.loads(raw or "{}")
            if isinstance(obj, dict):
                self._data = obj
                self._mtime = mt
                return
        except Exception:
            pass
        self._mtime = mt
        self._data = {}

    def get(self) -> Dict[str, object]:
        self._load_if_needed()
        return dict(self._data or {})


def default_manifest() -> AssetManifest:
    root = Path(__file__).resolve().parents[2]
    d = root / "static" / "dist"
    p = d / "manifest.current.json"
    if not p.exists():
        p2 = d / "manifest.json"
        return AssetManifest(p2)
    return AssetManifest(p)


def rollout_config() -> RolloutConfig:
    root = Path(__file__).resolve().parents[2]
    return RolloutConfig(root / "static" / "dist" / "rollout.json")


def ensure_rollout_cookie(existing: Optional[str]) -> str:
    v = str(existing or "").strip()
    if v:
        return v
    return secrets.token_hex(12)


def _bucket_0_99(s: str) -> int:
    h = 2166136261
    for ch in str(s or ""):
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return int(h % 100)


def choose_manifest(dist_dir: Path, current_manifest_path: Path, cookies: Dict[str, str], headers: Dict[str, str]) -> Path:
    rc = RolloutConfig(dist_dir / "rollout.json")
    cfg = rc.get()
    enabled = bool(cfg.get("enabled")) or False
    canary_release = str(cfg.get("canary_release_id") or "").strip()
    try:
        pct = int(cfg.get("percent") or 0)
    except Exception:
        pct = 0
    if pct < 0:
        pct = 0
    if pct > 100:
        pct = 100
    if enabled and pct > 0 and canary_release:
        sid = (
            str((cookies or {}).get("aiseek_sid") or "").strip()
            or str((headers or {}).get("x-session-id") or "").strip()
        )
        if sid and _bucket_0_99(sid) < pct:
            p = dist_dir / f"manifest.{canary_release}.json"
            if p.exists():
                return p
    return current_manifest_path


def make_asset_url(manifest: AssetManifest, build_id: str):
    bid = str(build_id or "").strip()

    def asset_url(logical_path: str) -> str:
        resolved = manifest.resolve(logical_path)
        if resolved:
            if bid:
                sep = "&" if "?" in resolved else "?"
                return f"{resolved}{sep}v={bid}"
            return resolved
        p = str(logical_path or "").strip().lstrip("/")
        if not p:
            return ""
        if bid:
            return f"/static/{p}?v={bid}"
        return f"/static/{p}"

    return asset_url


def make_asset_url_for_request(build_id: str, cookies: Dict[str, str], headers: Dict[str, str]):
    root = Path(__file__).resolve().parents[2]
    dist = root / "static" / "dist"
    cur_path = dist / "manifest.current.json"
    if not cur_path.exists():
        cur_path = dist / "manifest.json"
    chosen = choose_manifest(dist, cur_path, cookies or {}, headers or {})
    return make_asset_url(AssetManifest(chosen), build_id)
