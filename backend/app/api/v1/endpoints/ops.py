import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.deps import get_db, require_admin
from app.core.cache import cache
from app.models.all_models import User, Post, AIJob, Interaction


router = APIRouter()


@router.get("/admin/dashboard_overview")
def admin_dashboard_overview(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    now = datetime.utcnow()
    day_start = datetime(now.year, now.month, now.day)
    total_users = int(db.query(func.count(User.id)).scalar() or 0)
    total_contents = int(db.query(func.count(Post.id)).scalar() or 0)
    pending_review = int(
        db.query(func.count(Post.id))
        .filter(Post.status.in_(["pending", "returned", "review", "needs_review"]))
        .scalar()
        or 0
    )
    today_registered = int(db.query(func.count(User.id)).filter(User.created_at >= day_start).scalar() or 0)
    try:
        active_post_users = db.query(func.distinct(Post.user_id)).filter(Post.created_at >= day_start)
        active_inter_users = db.query(func.distinct(Interaction.user_id)).filter(Interaction.created_at >= day_start)
        union_sq = active_post_users.union(active_inter_users).subquery()
        today_active = int(db.query(func.count()).select_from(union_sq).scalar() or 0)
    except Exception:
        today_active = int(db.query(func.count(func.distinct(Post.user_id))).filter(Post.created_at >= day_start).scalar() or 0)
    ai_queue = int(
        db.query(func.count(AIJob.id))
        .filter(AIJob.status.in_(["queued", "dispatch_pending", "processing", "needs_review"]))
        .scalar()
        or 0
    )
    latest_rows = db.query(User).order_by(User.created_at.desc()).limit(8).all()
    latest_users = [
        {
            "id": int(u.id),
            "username": str(u.username or ""),
            "nickname": str(getattr(u, "nickname", "") or ""),
            "created_at": u.created_at.isoformat() if getattr(u, "created_at", None) else None,
        }
        for u in latest_rows
    ]
    ai_status_rows = db.query(AIJob.status, func.count(AIJob.id)).group_by(AIJob.status).all()
    ai_status = {str(st or "unknown"): int(cnt or 0) for st, cnt in ai_status_rows}
    return {
        "total_users": total_users,
        "today_active": today_active,
        "today_registered": today_registered,
        "total_contents": total_contents,
        "pending_review": pending_review,
        "ai_queue": ai_queue,
        "latest_users": latest_users,
        "ai_status": ai_status,
    }


def _dist_dir() -> Path:
    backend_root = Path(__file__).resolve().parents[4]
    return backend_root / "static" / "dist"

def _runtime_dir() -> Path:
    backend_root = Path(__file__).resolve().parents[4]
    return backend_root / "app" / "runtime"


def _safe_release_id(rid: str) -> str:
    s = str(rid or "").strip()
    if not re.fullmatch(r"[0-9A-Za-z._-]{6,64}", s):
        raise HTTPException(status_code=400, detail="invalid_release_id")
    return s


def _read_manifest(path: Path) -> Dict[str, str]:
    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        obj = json.loads(raw or "{}")
        if isinstance(obj, dict):
            return {str(k): str(v) for k, v in obj.items()}
    except Exception:
        pass
    return {}


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as f:
        f.write(data)
    tmp.replace(path)


def _infer_release_id_from_manifest(m: Dict[str, str]) -> Optional[str]:
    for _, v in (m or {}).items():
        s = str(v or "")
        if "dist/r/" in s:
            try:
                tail = s.split("dist/r/", 1)[1]
                rid = tail.split("/", 1)[0]
                if re.fullmatch(r"[0-9A-Za-z._-]{6,64}", rid):
                    return rid
            except Exception:
                pass
    return None


def _urljoin(base: str, path: str) -> str:
    b = str(base or "").strip().rstrip("/")
    p = str(path or "").strip()
    if not b:
        return ""
    if not p:
        return b
    if not p.startswith("/"):
        p = "/" + p
    return b + p


def _probe_url(url: str, timeout_sec: float = 1.2) -> Dict[str, Any]:
    u = str(url or "").strip()
    if not u:
        return {"ok": False, "status_code": None, "error": "missing_url"}
    code: Optional[int] = None
    err: Optional[str] = None
    ok = False
    try:
        req = urllib.request.Request(u, method="GET", headers={"User-Agent": "AIseekAdminProbe/1.0"})
        with urllib.request.urlopen(req, timeout=float(timeout_sec)) as resp:
            try:
                code = int(resp.getcode() or 0) or None
            except Exception:
                code = None
    except urllib.error.HTTPError as e:
        try:
            code = int(getattr(e, "code", 0) or 0) or None
        except Exception:
            code = None
        err = None
    except Exception as e:
        err = str((e and getattr(e, "reason", None)) or (e and getattr(e, "args", None)) or (e and getattr(e, "message", None)) or e)
    if code is not None and 200 <= int(code) < 500:
        ok = True
    if err:
        err = str(err).replace("\n", " ").replace("\r", " ").strip()
        if len(err) > 180:
            err = err[:180]
    return {"ok": bool(ok), "status_code": code, "error": err}


@router.get("/admin/api_health")
def admin_api_health(current_user: User = Depends(require_admin)) -> Dict[str, Any]:
    import time

    def env(name: str, default: Optional[str] = None) -> Optional[str]:
        v = os.getenv(name)
        if v is None:
            return default
        s = str(v).strip()
        return s or default

    s = None
    try:
        from app.core.config import get_settings

        s = get_settings()
    except Exception:
        s = None

    checks: List[Dict[str, Any]] = []
    def add(name: str, url: str, hint: Optional[str] = None):
        checks.append({"name": name, "url": url, "hint": hint})

    deepseek_base = env("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1") or ""
    add("DeepSeek API", _urljoin(deepseek_base, "/models"), "https://api.deepseek.com/v1/models")

    wan_base = env("COVER_WAN_BASE_URL", "https://dashscope.aliyuncs.com") or ""
    add("DashScope Wanx（封面图）", _urljoin(wan_base, "/api/v1/services/aigc/multimodal-generation/generation"), "dashscope.aliyuncs.com")

    openai_base = env("COVER_OPENAI_BASE_URL", "https://api.openai.com/v1") or ""
    add("OpenAI Images（封面图）", _urljoin(openai_base, "/images"), "api.openai.com/v1/images")

    add("Pixabay Videos API（占位视频）", "https://pixabay.com/api/videos/", "pixabay.com/api/videos")
    add("Pexels Videos API（占位视频）", "https://api.pexels.com/videos/v1/search", "api.pexels.com/videos/v1/search")

    try:
        r2e = str(getattr(s, "R2_ENDPOINT_URL", None) or "").strip() if s else ""
    except Exception:
        r2e = ""
    try:
        r2p = str(getattr(s, "R2_PUBLIC_URL", None) or "").strip() if s else ""
    except Exception:
        r2p = ""
    if r2e:
        add("Cloudflare R2 S3 Endpoint", r2e, "R2_ENDPOINT_URL")
    if r2p:
        add("R2 Public URL / CDN", r2p, "R2_PUBLIC_URL")

    try:
        fr = str(getattr(s, "FEED_RECALL_URL", None) or "").strip() if s else ""
    except Exception:
        fr = ""
    if fr:
        add("Feed Recall Remote", fr, "FEED_RECALL_URL")

    try:
        es = str(getattr(s, "ELASTICSEARCH_URL", None) or "").strip() if s else ""
    except Exception:
        es = ""
    if es:
        add("Elasticsearch", es, "ELASTICSEARCH_URL")

    add("cdnjs（前端静态资源）", "https://cdnjs.cloudflare.com/", "cdnjs.cloudflare.com")

    out: List[Dict[str, Any]] = []
    for c in checks:
        u = str(c.get("url") or "").strip()
        r = _probe_url(u, timeout_sec=1.3)
        out.append({"name": str(c.get("name") or ""), "url": u, "ok": bool(r.get("ok")), "status_code": r.get("status_code"), "error": r.get("error"), "hint": c.get("hint")})

    return {"ok": True, "ts": int(time.time()), "apis": out}


class ActivateAssetsIn(BaseModel):
    release_id: str


class RolloutOut(BaseModel):
    enabled: bool = False
    percent: int = 0
    canary_release_id: Optional[str] = None


class RolloutIn(BaseModel):
    enabled: bool = False
    percent: int = 0
    canary_release_id: Optional[str] = None


@router.get("/assets/releases")
def list_asset_releases(current_user: User = Depends(require_admin)) -> Dict[str, Any]:
    d = _dist_dir()
    cur = d / "manifest.current.json"
    cur_map = _read_manifest(cur) if cur.exists() else {}
    current_release_id = _infer_release_id_from_manifest(cur_map)

    items: List[Dict[str, Any]] = []
    if d.exists():
        for p in sorted(d.glob("manifest.*.json"), key=lambda x: x.name, reverse=True):
            name = p.name
            if name == "manifest.current.json":
                continue
            rid = name.removeprefix("manifest.").removesuffix(".json")
            if not rid or rid == "current":
                continue
            m = _read_manifest(p)
            items.append(
                {
                    "release_id": rid,
                    "count": len(m),
                    "active": bool(current_release_id and rid == current_release_id),
                    "mtime": int(getattr(p.stat(), "st_mtime", 0) or 0),
                    "path": str(p),
                }
            )

    return {"ok": True, "current_release_id": current_release_id, "releases": items[:30]}


@router.post("/assets/activate")
def activate_asset_release(body: ActivateAssetsIn, current_user: User = Depends(require_admin)) -> Dict[str, Any]:
    rid = _safe_release_id(body.release_id)
    d = _dist_dir()
    src = d / f"manifest.{rid}.json"
    if not src.exists():
        raise HTTPException(status_code=404, detail="release_not_found")
    m = _read_manifest(src)
    if not m:
        raise HTTPException(status_code=400, detail="invalid_manifest")
    cur = d / "manifest.current.json"
    _write_atomic(cur, json.dumps(m, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    return {"ok": True, "current_release_id": _infer_release_id_from_manifest(m) or rid}


def _rollout_path() -> Path:
    return _dist_dir() / "rollout.json"


def _read_rollout() -> Dict[str, Any]:
    p = _rollout_path()
    if not p.exists():
        return {"enabled": False, "percent": 0, "canary_release_id": None}
    try:
        raw = p.read_text(encoding="utf-8", errors="ignore")
        obj = json.loads(raw or "{}")
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    return {"enabled": False, "percent": 0, "canary_release_id": None}


def _write_rollout(cfg: Dict[str, Any]) -> None:
    _write_atomic(_rollout_path(), json.dumps(cfg, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


@router.get("/assets/rollout", response_model=RolloutOut)
def get_assets_rollout(current_user: User = Depends(require_admin)):
    cfg = _read_rollout()
    try:
        pct = int(cfg.get("percent") or 0)
    except Exception:
        pct = 0
    if pct < 0:
        pct = 0
    if pct > 100:
        pct = 100
    rid = str(cfg.get("canary_release_id") or "").strip() or None
    return {"enabled": bool(cfg.get("enabled")) or False, "percent": pct, "canary_release_id": rid}


@router.post("/assets/rollout", response_model=RolloutOut)
def set_assets_rollout(body: RolloutIn, current_user: User = Depends(require_admin)):
    rid = str(body.canary_release_id or "").strip() or None
    pct = int(body.percent or 0)
    if pct < 0:
        pct = 0
    if pct > 100:
        pct = 100
    if rid:
        _safe_release_id(rid)
        mp = _dist_dir() / f"manifest.{rid}.json"
        if not mp.exists():
            raise HTTPException(status_code=404, detail="release_not_found")
    cfg = {"enabled": bool(body.enabled), "percent": pct, "canary_release_id": rid}
    _write_rollout(cfg)
    return {"enabled": cfg["enabled"], "percent": cfg["percent"], "canary_release_id": cfg["canary_release_id"]}


class RolloutGuardIn(BaseModel):
    minutes: int = 3
    error_threshold: int = 10


@router.post("/assets/rollout/guard")
def guard_assets_rollout(body: RolloutGuardIn, current_user: User = Depends(require_admin)) -> Dict[str, Any]:
    mins = int(body.minutes or 3)
    if mins < 1:
        mins = 1
    if mins > 30:
        mins = 30
    thr = int(body.error_threshold or 10)
    if thr < 1:
        thr = 1
    if thr > 500:
        thr = 500
    root = Path(__file__).resolve().parents[4]
    fp = root / "logs" / "frontend_events.log"
    if not fp.exists():
        return {"ok": True, "action": "noop", "reason": "no_log"}
    import time

    cutoff_ms = int(time.time() * 1000) - mins * 60 * 1000
    cnt = 0
    try:
        with fp.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            start = max(0, size - 800_000)
            f.seek(start)
            data = f.read().decode("utf-8", errors="ignore").splitlines()
    except Exception:
        data = []
    for line in reversed(data):
        try:
            obj = json.loads(line)
            ts = int(obj.get("ts") or 0)
            if ts and ts < cutoff_ms:
                break
            if str(obj.get("name") or "") == "ui:error":
                cnt += 1
                if cnt >= thr:
                    break
        except Exception:
            continue
    if cnt >= thr:
        cfg = _read_rollout()
        cfg["enabled"] = False
        cfg["percent"] = 0
        _write_rollout(cfg)
        return {"ok": True, "action": "disabled", "errors": cnt, "minutes": mins, "threshold": thr}
    return {"ok": True, "action": "ok", "errors": cnt, "minutes": mins, "threshold": thr}


class FeedRecallOut(BaseModel):
    provider: str = "local"
    url: Optional[str] = None
    percent: int = 0
    kind: str = "recent"


class FeedRecallIn(BaseModel):
    provider: str = "local"
    url: Optional[str] = None
    percent: int = 0
    kind: str = "recent"


class ESReindexIn(BaseModel):
    limit: int = 5000


@router.get("/es/reindex/status")
def es_reindex_status(current_user: User = Depends(require_admin)) -> Dict[str, Any]:
    from app.core.cache import cache

    v = cache.get_json("es:reindex:posts:status")
    if isinstance(v, dict):
        return {"ok": True, "status": v}
    return {"ok": True, "status": {"status": "idle"}}


@router.post("/es/reindex")
def es_reindex(body: ESReindexIn, current_user: User = Depends(require_admin)) -> Dict[str, Any]:
    import time

    from app.core.cache import cache
    from app.core.celery_app import apply_async_with_context
    from app.tasks.search_index import rebuild_posts_index_job

    try:
        lim = int(body.limit or 5000)
    except Exception:
        lim = 5000
    if lim < 1:
        lim = 1
    if lim > 2000000:
        lim = 2000000

    job_id = f"{time.strftime('%Y%m%d%H%M%S')}-{int(time.time() * 1000) % 1000000:06d}"
    cache.set_json("es:reindex:posts:status", {"job_id": job_id, "status": "queued", "limit": int(lim)}, ttl=86400)
    ar = apply_async_with_context(rebuild_posts_index_job, args=[str(job_id), int(lim)])
    tid = getattr(ar, "id", None)
    return {"ok": True, "job_id": job_id, "task_id": tid}


@router.post("/es/reindex/cancel")
def es_reindex_cancel(current_user: User = Depends(require_admin)) -> Dict[str, Any]:
    from app.core.cache import cache

    cache.set_json("es:reindex:posts:cancel", 1, ttl=3600)
    return {"ok": True}


@router.get("/es/reindex/jobs")
def es_reindex_jobs(current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> Dict[str, Any]:
    from app.models.all_models import ESReindexJob

    rows = (
        db.query(ESReindexJob)
        .order_by(ESReindexJob.created_at.desc(), ESReindexJob.id.desc())
        .limit(30)
        .all()
    )
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "job_id": str(getattr(r, "id", "") or ""),
                "alias": getattr(r, "alias", None),
                "status": getattr(r, "status", None),
                "new_index": getattr(r, "new_index", None),
                "ok": int(getattr(r, "ok", 0) or 0),
                "total": int(getattr(r, "total", 0) or 0),
                "cancelled": bool(getattr(r, "cancelled", False) or False),
                "created_at": getattr(r, "created_at", None),
                "updated_at": getattr(r, "updated_at", None),
                "error": getattr(r, "error", None),
            }
        )
    return {"ok": True, "jobs": out}


def _feed_recall_path() -> Path:
    return _runtime_dir() / "feed_recall.json"


def _read_feed_recall() -> Dict[str, Any]:
    p = _feed_recall_path()
    if not p.exists():
        return {"provider": "local", "url": "", "percent": 0, "kind": "recent"}
    try:
        raw = p.read_text(encoding="utf-8", errors="ignore")
        obj = json.loads(raw or "{}")
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    return {"provider": "local", "url": "", "percent": 0, "kind": "recent"}


def _write_feed_recall(cfg: Dict[str, Any]) -> None:
    p = _feed_recall_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    _write_atomic(p, json.dumps(cfg, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


@router.get("/feed/recall", response_model=FeedRecallOut)
def get_feed_recall(current_user: User = Depends(require_admin)):
    cfg = _read_feed_recall()
    provider = str(cfg.get("provider") or "local").strip().lower() or "local"
    url = str(cfg.get("url") or "").strip()
    kind = str(cfg.get("kind") or "recent").strip().lower() or "recent"
    try:
        pct = int(cfg.get("percent") or 0)
    except Exception:
        pct = 0
    if pct < 0:
        pct = 0
    if pct > 100:
        pct = 100
    if provider not in {"local", "remote", "auto"}:
        provider = "local"
    if kind not in {"recent", "hot", "blend"}:
        kind = "recent"
    return {"provider": provider, "url": url or None, "percent": pct, "kind": kind}


@router.post("/feed/recall", response_model=FeedRecallOut)
def set_feed_recall(body: FeedRecallIn, current_user: User = Depends(require_admin)):
    provider = str(body.provider or "local").strip().lower() or "local"
    if provider not in {"local", "remote", "auto"}:
        raise HTTPException(status_code=400, detail="invalid_provider")
    url = str(body.url or "").strip()
    kind = str(body.kind or "recent").strip().lower() or "recent"
    if kind not in {"recent", "hot", "blend"}:
        raise HTTPException(status_code=400, detail="invalid_kind")
    pct = int(body.percent or 0)
    if pct < 0:
        pct = 0
    if pct > 100:
        pct = 100
    cfg = {"provider": provider, "url": url, "percent": pct, "kind": kind}
    _write_feed_recall(cfg)
    return {"provider": provider, "url": url or None, "percent": pct, "kind": kind}


class ClientEventsRuntimeOut(BaseModel):
    ingest_sample_rate: float = 1.0
    persist_enabled: bool = True
    persist_strict: bool = True
    persist_sample_rate: float = 1.0
    drop_unknown_heads: bool = True
    rate_limit_enabled: bool = True
    rate_limit_ip_rpm: int = 600
    rate_limit_session_rpm: int = 1200
    signed_required: bool = False
    sig_window_sec: int = 30


class ClientEventsRuntimeIn(BaseModel):
    ingest_sample_rate: Optional[float] = None
    persist_enabled: Optional[bool] = None
    persist_strict: Optional[bool] = None
    persist_sample_rate: Optional[float] = None
    drop_unknown_heads: Optional[bool] = None
    rate_limit_enabled: Optional[bool] = None
    rate_limit_ip_rpm: Optional[int] = None
    rate_limit_session_rpm: Optional[int] = None
    signed_required: Optional[bool] = None
    sig_window_sec: Optional[int] = None


def _client_events_path() -> Path:
    return _runtime_dir() / "client_events.json"

def _client_events_key() -> str:
    return "runtime:client_events"


def _read_client_events() -> Dict[str, Any]:
    from app.observability.runtime_client_events import read_runtime_client_events

    return read_runtime_client_events()


def _write_client_events(cfg: Dict[str, Any]) -> None:
    from app.observability.runtime_client_events import write_runtime_client_events

    write_runtime_client_events(cfg)


@router.get("/client-events/runtime", response_model=ClientEventsRuntimeOut)
def get_client_events_runtime(current_user: User = Depends(require_admin)):
    from app.core.config import get_settings

    s = get_settings()
    cfg = _read_client_events()
    def _f(k: str, default):
        v = cfg.get(k)
        return default if v is None else v
    return {
        "ingest_sample_rate": float(_f("ingest_sample_rate", float(getattr(s, "CLIENT_EVENT_INGEST_SAMPLE_RATE", 1.0) or 1.0))),
        "persist_enabled": bool(_f("persist_enabled", bool(getattr(s, "CLIENT_EVENT_PERSIST_ENABLED", True)))),
        "persist_strict": bool(_f("persist_strict", bool(getattr(s, "CLIENT_EVENT_PERSIST_STRICT", True)))),
        "persist_sample_rate": float(_f("persist_sample_rate", float(getattr(s, "CLIENT_EVENT_PERSIST_SAMPLE_RATE", 1.0) or 1.0))),
        "drop_unknown_heads": bool(_f("drop_unknown_heads", bool(getattr(s, "CLIENT_EVENT_DROP_UNKNOWN_HEADS", True)))),
        "rate_limit_enabled": bool(_f("rate_limit_enabled", bool(getattr(s, "CLIENT_EVENT_RATE_LIMIT_ENABLED", True)))),
        "rate_limit_ip_rpm": int(_f("rate_limit_ip_rpm", int(getattr(s, "CLIENT_EVENT_RATE_LIMIT_IP_RPM", 600) or 600))),
        "rate_limit_session_rpm": int(_f("rate_limit_session_rpm", int(getattr(s, "CLIENT_EVENT_RATE_LIMIT_SESSION_RPM", 1200) or 1200))),
        "signed_required": bool(_f("signed_required", bool(getattr(s, "CLIENT_EVENT_SIGNED_REQUIRED", False)))),
        "sig_window_sec": int(_f("sig_window_sec", int(getattr(s, "CLIENT_EVENT_SIG_WINDOW_SEC", 30) or 30))),
    }


@router.post("/client-events/runtime", response_model=ClientEventsRuntimeOut)
def set_client_events_runtime(body: ClientEventsRuntimeIn, current_user: User = Depends(require_admin)):
    cfg = _read_client_events()
    upd: Dict[str, Any] = dict(cfg)
    if body.ingest_sample_rate is not None:
        r = float(body.ingest_sample_rate)
        if r < 0:
            r = 0.0
        if r > 1:
            r = 1.0
        upd["ingest_sample_rate"] = float(r)
    if body.persist_enabled is not None:
        upd["persist_enabled"] = bool(body.persist_enabled)
    if body.persist_strict is not None:
        upd["persist_strict"] = bool(body.persist_strict)
    if body.persist_sample_rate is not None:
        r = float(body.persist_sample_rate)
        if r < 0:
            r = 0.0
        if r > 1:
            r = 1.0
        upd["persist_sample_rate"] = float(r)
    if body.drop_unknown_heads is not None:
        upd["drop_unknown_heads"] = bool(body.drop_unknown_heads)
    if body.rate_limit_enabled is not None:
        upd["rate_limit_enabled"] = bool(body.rate_limit_enabled)
    if body.rate_limit_ip_rpm is not None:
        v = int(body.rate_limit_ip_rpm)
        if v < 0:
            v = 0
        if v > 200000:
            v = 200000
        upd["rate_limit_ip_rpm"] = int(v)
    if body.rate_limit_session_rpm is not None:
        v = int(body.rate_limit_session_rpm)
        if v < 0:
            v = 0
        if v > 200000:
            v = 200000
        upd["rate_limit_session_rpm"] = int(v)
    if body.signed_required is not None:
        upd["signed_required"] = bool(body.signed_required)
    if body.sig_window_sec is not None:
        v = int(body.sig_window_sec)
        if v < 3:
            v = 3
        if v > 600:
            v = 600
        upd["sig_window_sec"] = int(v)
    _write_client_events(upd)
    return get_client_events_runtime(current_user=current_user)


class ClientEventsGuardIn(BaseModel):
    pending_threshold: int = 20000
    ingest_sample_rate: float = 0.2
    disable_persist: bool = True


@router.post("/client-events/guard")
def guard_client_events(body: ClientEventsGuardIn, current_user: User = Depends(require_admin)) -> Dict[str, Any]:
    thr = int(body.pending_threshold or 20000)
    if thr < 100:
        thr = 100
    if thr > 5_000_000:
        thr = 5_000_000
    rate = float(body.ingest_sample_rate or 0.2)
    if rate < 0:
        rate = 0.0
    if rate > 1:
        rate = 1.0
    from app.observability.client_events_guard import apply_client_events_degrade, get_client_event_backlog

    st = get_client_event_backlog()
    if not bool(st.get("ok")):
        return {"ok": True, "action": "noop", "reason": str(st.get("error") or "unknown")}
    max_pending = int(st.get("pending_max") or 0)
    by_stream = st.get("pending") if isinstance(st.get("pending"), dict) else {}
    if max_pending < thr:
        return {"ok": True, "action": "ok", "pending_max": max_pending, "threshold": thr, "pending": by_stream}
    new_cfg = apply_client_events_degrade(ingest_sample_rate=float(rate), disable_persist=bool(body.disable_persist))
    return {"ok": True, "action": "degraded", "pending_max": max_pending, "threshold": thr, "runtime": new_cfg, "pending": by_stream}
