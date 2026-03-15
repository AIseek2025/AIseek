from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from app.core.cache import cache


def _runtime_key() -> str:
    return "runtime:ai_production"


def _runtime_file() -> Path:
    root = Path(__file__).resolve().parents[1]
    return root / "runtime" / "ai_production.json"


def read_runtime_ai_production() -> Dict[str, Any]:
    try:
        v = cache.get_json(_runtime_key())
        if isinstance(v, dict):
            return v
    except Exception:
        pass
    p = _runtime_file()
    if not p.exists():
        return {}
    try:
        raw = p.read_text(encoding="utf-8", errors="ignore")
        obj = json.loads(raw or "{}")
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def write_runtime_ai_production(cfg: Dict[str, Any]) -> None:
    obj = cfg if isinstance(cfg, dict) else {}
    try:
        raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return
    try:
        p = _runtime_file()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(raw, encoding="utf-8", errors="ignore")
        tmp.replace(p)
    except Exception:
        pass
    try:
        r = cache.redis()
        if r:
            r.set(_runtime_key(), raw)
    except Exception:
        pass


def patch_runtime_ai_production(delta: Dict[str, Any]) -> Dict[str, Any]:
    cur = read_runtime_ai_production()
    out: Dict[str, Any] = dict(cur) if isinstance(cur, dict) else {}
    for k, v in (delta or {}).items():
        if v is None:
            continue
        out[str(k)] = v
    write_runtime_ai_production(out)
    return out
