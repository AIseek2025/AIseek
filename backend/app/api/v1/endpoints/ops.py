import json
import os
import re
import csv
import io
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.deps import get_db, require_admin
from app.core.cache import cache
from app.models.all_models import User, Post, AIJob, Interaction, Comment, PostCounterEvent, NotificationEvent, ClientEvent


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


@router.get("/admin/search-share/metrics")
def admin_search_share_metrics(
    days: int = Query(7, ge=1, le=30),
    sample_limit: int = Query(30, ge=1, le=100),
    sample_window_hours: int = Query(168, ge=1, le=24 * 30),
    sample_event_kw: str = Query("", max_length=64),
    sample_key_kw: str = Query("", max_length=64),
    sample_status: str = Query("", max_length=16),
    sample_only_errors: bool = Query(False),
    current_user: User = Depends(require_admin),
) -> Dict[str, Any]:
    _ = current_user
    storage = "local"
    try:
        if cache.redis_enabled():
            storage = "redis"
    except Exception:
        storage = "local"

    def _to_int_map(obj: Any) -> Dict[str, int]:
        if not isinstance(obj, dict):
            return {}
        out: Dict[str, int] = {}
        for k, v in obj.items():
            try:
                out[str(k)] = int(v or 0)
            except Exception:
                out[str(k)] = 0
        return out

    totals_raw = cache.hgetall("search:share:views:metrics:total") or {}
    totals = _to_int_map(totals_raw)
    create_ok = int(totals.get("create_ok") or 0)
    create_reused = int(totals.get("create_reused") or 0)
    create_failed = int(totals.get("create_failed") or 0)
    resolve_ok = int(totals.get("resolve_ok") or 0)
    resolve_not_found = int(totals.get("resolve_not_found") or 0)
    resolve_expired = int(totals.get("resolve_expired") or 0)
    resolve_cache_unavailable = int(totals.get("resolve_cache_unavailable") or 0)
    create_total = max(0, create_ok + create_reused + create_failed)
    resolve_total = max(0, resolve_ok + resolve_not_found + resolve_expired + resolve_cache_unavailable)
    resolve_hit_rate = float(resolve_ok) / float(resolve_total) if resolve_total > 0 else 0.0
    resolve_miss_rate = float(resolve_not_found + resolve_expired) / float(resolve_total) if resolve_total > 0 else 0.0
    resolve_error_rate = float(resolve_cache_unavailable) / float(resolve_total) if resolve_total > 0 else 0.0
    create_client_error_total = int(
        (totals.get("create_empty") or 0)
        + (totals.get("create_too_long") or 0)
        + (totals.get("create_invalid") or 0)
        + (totals.get("create_expired") or 0)
    )
    create_server_error_total = int((totals.get("create_cache_unavailable") or 0) + (totals.get("create_failed") or 0))
    resolve_client_error_total = int(
        (totals.get("resolve_invalid_key") or 0)
        + (totals.get("resolve_not_found") or 0)
        + (totals.get("resolve_expired") or 0)
    )
    resolve_server_error_total = int(totals.get("resolve_cache_unavailable") or 0)
    summary = {
        "create_total": int(create_total),
        "resolve_total": int(resolve_total),
        "resolve_hit_rate": float(resolve_hit_rate),
        "resolve_miss_rate": float(resolve_miss_rate),
        "resolve_error_rate": float(resolve_error_rate),
        "create_client_error_total": int(create_client_error_total),
        "create_server_error_total": int(create_server_error_total),
        "resolve_client_error_total": int(resolve_client_error_total),
        "resolve_server_error_total": int(resolve_server_error_total),
    }
    now = datetime.utcnow()
    series: List[Dict[str, Any]] = []
    for i in range(int(days) - 1, -1, -1):
        d = now - timedelta(days=i)
        ds = d.strftime("%Y%m%d")
        key = f"search:share:views:metrics:day:{ds}"
        m = _to_int_map(cache.hgetall(key) or {})
        d_ok = int(m.get("resolve_ok") or 0)
        d_nf = int(m.get("resolve_not_found") or 0)
        d_ex = int(m.get("resolve_expired") or 0)
        d_err = int(m.get("resolve_cache_unavailable") or 0)
        d_total = max(0, d_ok + d_nf + d_ex + d_err)
        d_cc = int((m.get("create_empty") or 0) + (m.get("create_too_long") or 0) + (m.get("create_invalid") or 0) + (m.get("create_expired") or 0))
        d_cs = int((m.get("create_cache_unavailable") or 0) + (m.get("create_failed") or 0))
        d_rc = int((m.get("resolve_invalid_key") or 0) + (m.get("resolve_not_found") or 0) + (m.get("resolve_expired") or 0))
        d_rs = int(m.get("resolve_cache_unavailable") or 0)
        m["_resolve_total"] = int(d_total)
        m["_resolve_hit_rate"] = float(d_ok) / float(d_total) if d_total > 0 else 0.0
        m["_resolve_miss_rate"] = float(d_nf + d_ex) / float(d_total) if d_total > 0 else 0.0
        m["_create_client_error_total"] = int(d_cc)
        m["_create_server_error_total"] = int(d_cs)
        m["_resolve_client_error_total"] = int(d_rc)
        m["_resolve_server_error_total"] = int(d_rs)
        series.append({"day": ds, "metrics": m})
    samples: List[Dict[str, Any]] = []
    ev_kw = str(sample_event_kw or "").strip().lower()
    key_kw = str(sample_key_kw or "").strip().lower()
    st_kw = str(sample_status or "").strip()
    only_err = bool(sample_only_errors)
    now_ts = int(datetime.utcnow().timestamp())
    min_ts = int(now_ts - max(1, int(sample_window_hours)) * 3600)
    prev_min_ts = int(min_ts - max(1, int(sample_window_hours)) * 3600)
    scanned_total = 0
    status_counts: Dict[str, int] = {"200": 0, "4xx": 0, "5xx": 0, "other": 0}
    event_counts: Dict[str, int] = {}
    curr_cmp_total = 0
    curr_cmp_5xx = 0
    prev_cmp_total = 0
    prev_cmp_5xx = 0
    try:
        r = cache.redis()
        if r:
            scan_limit = max(int(sample_limit) * 5, 200)
            scan_limit = min(scan_limit, 1000)
            arr = r.lrange("search:share:views:metrics:samples", 0, int(scan_limit) - 1) or []
            for raw in arr:
                scanned_total += 1
                try:
                    obj = json.loads(str(raw or "") or "{}")
                except Exception:
                    obj = None
                if not isinstance(obj, dict):
                    continue
                ts = int(obj.get("ts") or 0)
                if ts <= 0 or ts < prev_min_ts:
                    continue
                ev = str(obj.get("event") or "")
                st = str(obj.get("detail") or "")
                if ev_kw and ev.lower().find(ev_kw) < 0:
                    continue
                kk = str(obj.get("key") or "")
                if key_kw and kk.lower().find(key_kw) < 0:
                    continue
                if st_kw and st != st_kw:
                    continue
                if only_err and st == "200":
                    continue
                if ts >= min_ts:
                    curr_cmp_total += 1
                    if st.startswith("5"):
                        curr_cmp_5xx += 1
                elif ts >= prev_min_ts:
                    prev_cmp_total += 1
                    if st.startswith("5"):
                        prev_cmp_5xx += 1
                    continue
                if len(samples) >= int(sample_limit):
                    continue
                if st == "200":
                    status_counts["200"] = int(status_counts.get("200") or 0) + 1
                elif st.startswith("4"):
                    status_counts["4xx"] = int(status_counts.get("4xx") or 0) + 1
                elif st.startswith("5"):
                    status_counts["5xx"] = int(status_counts.get("5xx") or 0) + 1
                else:
                    status_counts["other"] = int(status_counts.get("other") or 0) + 1
                if ev:
                    event_counts[ev] = int(event_counts.get(ev) or 0) + 1
                samples.append(
                    {
                        "ts": ts,
                        "event": ev,
                        "key": kk,
                        "detail": st,
                    }
                )
    except Exception:
        samples = []
    returned_total = int(len(samples))
    ok_count = int(status_counts.get("200") or 0)
    err4_count = int(status_counts.get("4xx") or 0)
    err5_count = int(status_counts.get("5xx") or 0)
    ok_rate = float(ok_count) / float(returned_total) if returned_total > 0 else 0.0
    err4_rate = float(err4_count) / float(returned_total) if returned_total > 0 else 0.0
    err5_rate = float(err5_count) / float(returned_total) if returned_total > 0 else 0.0
    health_level = "healthy"
    health_reason = "ok"
    if returned_total < 5:
        health_level = "insufficient"
        health_reason = "low_sample"
    elif err5_rate >= 0.20:
        health_level = "critical"
        health_reason = "high_5xx_rate"
    elif err5_rate >= 0.10 or err4_rate >= 0.50:
        health_level = "warning"
        health_reason = "elevated_error_rate"
    curr_cmp_err5_rate = float(curr_cmp_5xx) / float(curr_cmp_total) if curr_cmp_total > 0 else 0.0
    prev_cmp_err5_rate = float(prev_cmp_5xx) / float(prev_cmp_total) if prev_cmp_total > 0 else 0.0
    trend_delta = float(curr_cmp_err5_rate - prev_cmp_err5_rate)
    trend_direction = "unknown"
    trend_confidence = "low"
    if curr_cmp_total >= 5 and prev_cmp_total >= 5:
        if trend_delta >= 0.05:
            trend_direction = "worsening"
        elif trend_delta <= -0.05:
            trend_direction = "improving"
        else:
            trend_direction = "stable"
    cmp_base = min(int(curr_cmp_total), int(prev_cmp_total))
    if cmp_base >= 20:
        trend_confidence = "high"
    elif cmp_base >= 10:
        trend_confidence = "medium"
    trend_alert = bool(trend_direction == "worsening" and curr_cmp_err5_rate >= 0.10 and cmp_base >= 10)
    health_alert = bool(health_level in ("warning", "critical") or trend_alert)
    alert_level = "info"
    suggested_action = "observe"
    if health_level == "critical":
        alert_level = "critical"
        suggested_action = "check_backend_5xx"
    elif health_alert:
        alert_level = "warning"
        suggested_action = "investigate_error_spike" if trend_alert else "check_client_error_pattern"
    elif health_level == "insufficient":
        alert_level = "notice"
        suggested_action = "collect_more_samples"
    action_priority = 0
    recommended_recheck_minutes = 120
    if alert_level == "critical":
        action_priority = 3
        recommended_recheck_minutes = 5
    elif alert_level == "warning":
        action_priority = 2
        recommended_recheck_minutes = 15
    elif alert_level == "notice":
        action_priority = 1
        recommended_recheck_minutes = 60
    if trend_confidence == "low" and alert_level != "critical":
        recommended_recheck_minutes = int(recommended_recheck_minutes + 15)
    action_due_ts = int(now_ts + int(recommended_recheck_minutes) * 60)
    action_status = "idle"
    if health_alert:
        action_status = "active"
    elif alert_level == "notice":
        action_status = "scheduled"
    action_due_in_seconds = int(action_due_ts - now_ts)
    action_overdue = bool(action_due_in_seconds <= 0 and action_status in ("active", "scheduled"))
    action_overdue_minutes = int(max(0, (0 - int(action_due_in_seconds)) // 60))
    breach_level = "none"
    if action_overdue_minutes >= 60:
        breach_level = "critical"
    elif action_overdue_minutes >= 15:
        breach_level = "major"
    elif action_overdue_minutes > 0:
        breach_level = "minor"
    escalation_hint = "monitor"
    if breach_level == "critical":
        escalation_hint = "page_oncall_owner"
    elif breach_level == "major":
        escalation_hint = "notify_feature_owner"
    elif breach_level == "minor":
        escalation_hint = "postpone_noncritical_work"
    escalation_required = bool(breach_level in ("major", "critical"))
    escalation_deadline_ts = 0
    if breach_level == "critical":
        escalation_deadline_ts = int(now_ts + 5 * 60)
    elif breach_level == "major":
        escalation_deadline_ts = int(now_ts + 15 * 60)
    escalation_due_in_seconds = int(escalation_deadline_ts - now_ts) if escalation_deadline_ts > 0 else 0
    escalation_urgency = "normal"
    if escalation_required:
        if escalation_due_in_seconds <= 0:
            escalation_urgency = "critical"
        elif escalation_due_in_seconds <= 5 * 60:
            escalation_urgency = "warning"
    escalation_window_overdue = bool(escalation_required and escalation_due_in_seconds <= 0)
    escalation_stage = "not_required"
    if escalation_required and escalation_window_overdue:
        escalation_stage = "breached"
    elif escalation_required and escalation_urgency == "warning":
        escalation_stage = "expiring"
    elif escalation_required:
        escalation_stage = "active"
    escalation_sla_level = "none"
    if escalation_stage == "breached":
        escalation_sla_level = "sev1"
    elif escalation_stage == "expiring":
        escalation_sla_level = "sev2"
    elif escalation_stage == "active":
        escalation_sla_level = "sev3"
    escalation_playbook_action = "observe"
    if escalation_sla_level == "sev1":
        escalation_playbook_action = "trigger_incident_bridge"
    elif escalation_sla_level == "sev2":
        escalation_playbook_action = "start_owner_warroom"
    elif escalation_sla_level == "sev3":
        escalation_playbook_action = "assign_primary_owner"
    escalation_target_response_minutes = 0
    escalation_owner_role = "observer"
    if escalation_sla_level == "sev1":
        escalation_target_response_minutes = 5
        escalation_owner_role = "incident_commander"
    elif escalation_sla_level == "sev2":
        escalation_target_response_minutes = 15
        escalation_owner_role = "feature_owner"
    elif escalation_sla_level == "sev3":
        escalation_target_response_minutes = 30
        escalation_owner_role = "duty_engineer"
    escalation_ack_status = "not_required"
    if escalation_required and escalation_window_overdue:
        escalation_ack_status = "overdue"
    elif escalation_required:
        escalation_ack_status = "pending"
    escalation_ack_due_ts = int(escalation_deadline_ts) if escalation_required else 0
    escalation_ack_due_in_seconds = int(escalation_due_in_seconds) if escalation_required else 0
    ack_breach_level = "none"
    if escalation_ack_status == "overdue":
        ack_overdue_minutes = int(max(0, abs(escalation_ack_due_in_seconds) // 60))
        if ack_overdue_minutes >= 30:
            ack_breach_level = "critical"
        elif ack_overdue_minutes >= 10:
            ack_breach_level = "major"
        else:
            ack_breach_level = "minor"
    ack_nudge_action = "none"
    if ack_breach_level == "critical":
        ack_nudge_action = "escalate_to_incident_commander"
    elif ack_breach_level == "major":
        ack_nudge_action = "page_feature_owner"
    elif ack_breach_level == "minor":
        ack_nudge_action = "remind_duty_engineer"
    ack_nudge_channel = "none"
    if ack_nudge_action == "escalate_to_incident_commander":
        ack_nudge_channel = "phone_call"
    elif ack_nudge_action == "page_feature_owner":
        ack_nudge_channel = "pager"
    elif ack_nudge_action == "remind_duty_engineer":
        ack_nudge_channel = "chatops"
    ack_nudge_urgency = "normal"
    if ack_breach_level == "critical":
        ack_nudge_urgency = "critical"
    elif ack_breach_level == "major":
        ack_nudge_urgency = "high"
    elif ack_breach_level == "minor":
        ack_nudge_urgency = "medium"
    ack_nudge_retry_count = 0
    ack_nudge_next_ts = 0
    if ack_nudge_action != "none":
        if ack_nudge_urgency == "critical":
            ack_nudge_retry_count = 3
            ack_nudge_next_ts = int(now_ts + 2 * 60)
        elif ack_nudge_urgency == "high":
            ack_nudge_retry_count = 2
            ack_nudge_next_ts = int(now_ts + 5 * 60)
        else:
            ack_nudge_retry_count = 1
            ack_nudge_next_ts = int(now_ts + 10 * 60)
    ack_nudge_next_in_seconds = int(ack_nudge_next_ts - now_ts) if ack_nudge_next_ts > 0 else 0
    ack_nudge_backoff_minutes = 0
    if ack_nudge_next_in_seconds > 0:
        ack_nudge_backoff_minutes = int(max(1, ack_nudge_next_in_seconds // 60))
    ack_nudge_state = "idle"
    if ack_nudge_action != "none" and ack_nudge_next_in_seconds > 0:
        ack_nudge_state = "scheduled"
    ack_nudge_attempted_count = int(ack_nudge_retry_count + (1 if ack_nudge_action != "none" else 0))
    ack_nudge_success_rate = 1.0
    if ack_breach_level == "critical":
        ack_nudge_success_rate = 0.35
    elif ack_breach_level == "major":
        ack_nudge_success_rate = 0.55
    elif ack_breach_level == "minor":
        ack_nudge_success_rate = 0.75
    ack_nudge_quality_grade = "excellent"
    ack_nudge_recommendation = "keep_current_strategy"
    if ack_nudge_success_rate < 0.4:
        ack_nudge_quality_grade = "poor"
        ack_nudge_recommendation = "escalate_channel_and_owner"
    elif ack_nudge_success_rate < 0.6:
        ack_nudge_quality_grade = "fair"
        ack_nudge_recommendation = "increase_retry_frequency"
    elif ack_nudge_success_rate < 0.8:
        ack_nudge_quality_grade = "good"
        ack_nudge_recommendation = "keep_and_monitor"
    ack_nudge_quality_score = int(round(ack_nudge_success_rate * 100))
    ack_nudge_quality_confidence = "high"
    if ack_nudge_attempted_count <= 1:
        ack_nudge_quality_confidence = "low"
    elif ack_nudge_attempted_count == 2:
        ack_nudge_quality_confidence = "medium"
    ack_nudge_quality_prev_score = int(round(max(0.0, min(1.0, 1.0 - float(prev_cmp_err5_rate))) * 100))
    ack_nudge_quality_trend_delta = int(ack_nudge_quality_score - ack_nudge_quality_prev_score)
    ack_nudge_quality_trend_direction = "stable"
    if ack_nudge_quality_trend_delta >= 5:
        ack_nudge_quality_trend_direction = "improving"
    elif ack_nudge_quality_trend_delta <= -5:
        ack_nudge_quality_trend_direction = "worsening"
    ack_nudge_quality_trend_confidence = str(trend_confidence)
    ack_nudge_quality_trend_alert_level = "info"
    ack_nudge_quality_trend_recommendation = "keep_strategy"
    if ack_nudge_quality_trend_direction == "worsening":
        if ack_nudge_quality_trend_delta <= -20:
            ack_nudge_quality_trend_alert_level = "critical"
            ack_nudge_quality_trend_recommendation = "escalate_owner_and_channel"
        elif ack_nudge_quality_trend_delta <= -10:
            ack_nudge_quality_trend_alert_level = "warning"
            ack_nudge_quality_trend_recommendation = "increase_retry_and_monitor"
        else:
            ack_nudge_quality_trend_alert_level = "notice"
            ack_nudge_quality_trend_recommendation = "tighten_observation_window"
    elif ack_nudge_quality_trend_direction == "improving":
        if ack_nudge_quality_trend_delta >= 10:
            ack_nudge_quality_trend_alert_level = "notice"
            ack_nudge_quality_trend_recommendation = "reduce_nudge_frequency"
        else:
            ack_nudge_quality_trend_alert_level = "info"
            ack_nudge_quality_trend_recommendation = "keep_and_monitor"
    if ack_nudge_quality_trend_confidence == "low" and ack_nudge_quality_trend_alert_level in ("notice", "warning"):
        ack_nudge_quality_trend_alert_level = "info"
        ack_nudge_quality_trend_recommendation = "collect_more_samples"
    trend_escalation_required = False
    trend_escalation_stage = "observe"
    trend_escalation_owner_role = "observer"
    trend_escalation_playbook_action = "observe"
    trend_escalation_target_response_minutes = 0
    if ack_nudge_quality_trend_alert_level == "critical":
        trend_escalation_required = True
        trend_escalation_stage = "critical"
        trend_escalation_owner_role = "incident_commander"
        trend_escalation_playbook_action = "trigger_incident_bridge"
        trend_escalation_target_response_minutes = 5
    elif ack_nudge_quality_trend_alert_level == "warning" and ack_nudge_quality_trend_confidence in ("high", "medium"):
        trend_escalation_required = True
        trend_escalation_stage = "warning"
        trend_escalation_owner_role = "feature_owner"
        trend_escalation_playbook_action = "start_owner_warroom"
        trend_escalation_target_response_minutes = 15
    elif ack_nudge_quality_trend_alert_level == "notice" and ack_nudge_quality_trend_confidence == "high":
        trend_escalation_required = True
        trend_escalation_stage = "notice"
        trend_escalation_owner_role = "duty_engineer"
        trend_escalation_playbook_action = "assign_primary_owner"
        trend_escalation_target_response_minutes = 30
    effective_escalation_required = bool(escalation_required or trend_escalation_required)
    effective_escalation_owner_role = str(escalation_owner_role if escalation_required else trend_escalation_owner_role)
    effective_escalation_playbook_action = str(escalation_playbook_action if escalation_required else trend_escalation_playbook_action)
    effective_escalation_target_response_minutes = int(
        escalation_target_response_minutes if escalation_required else trend_escalation_target_response_minutes
    )
    effective_escalation_source = "base"
    if not escalation_required and trend_escalation_required:
        effective_escalation_source = "trend"
    elif escalation_required and trend_escalation_required:
        effective_escalation_source = "base_and_trend"
    effective_escalation_urgency = "normal"
    if effective_escalation_required:
        if effective_escalation_target_response_minutes <= 5:
            effective_escalation_urgency = "critical"
        elif effective_escalation_target_response_minutes <= 15:
            effective_escalation_urgency = "high"
        else:
            effective_escalation_urgency = "medium"
    effective_escalation_due_ts = int(now_ts + max(0, int(effective_escalation_target_response_minutes)) * 60) if effective_escalation_required else 0
    effective_escalation_due_in_seconds = int(effective_escalation_due_ts - now_ts) if effective_escalation_due_ts > 0 else 0
    effective_escalation_overdue = bool(effective_escalation_required and effective_escalation_due_in_seconds <= 0)
    effective_escalation_due_in_minutes = int(abs(effective_escalation_due_in_seconds) // 60) if effective_escalation_required else 0
    effective_escalation_breach_level = "none"
    if effective_escalation_overdue:
        if effective_escalation_due_in_minutes >= 30:
            effective_escalation_breach_level = "critical"
        elif effective_escalation_due_in_minutes >= 10:
            effective_escalation_breach_level = "major"
        else:
            effective_escalation_breach_level = "minor"
    effective_escalation_followup_action = "observe"
    if effective_escalation_breach_level == "critical":
        effective_escalation_followup_action = "page_incident_manager"
    elif effective_escalation_breach_level == "major":
        effective_escalation_followup_action = "notify_feature_owner"
    elif effective_escalation_breach_level == "minor":
        effective_escalation_followup_action = "remind_duty_engineer"
    effective_escalation_followup_required = bool(effective_escalation_followup_action != "observe")
    effective_escalation_followup_due_minutes = 0
    if effective_escalation_breach_level == "critical":
        effective_escalation_followup_due_minutes = 3
    elif effective_escalation_breach_level == "major":
        effective_escalation_followup_due_minutes = 10
    elif effective_escalation_breach_level == "minor":
        effective_escalation_followup_due_minutes = 30
    effective_escalation_followup_due_ts = int(now_ts + int(effective_escalation_followup_due_minutes) * 60) if effective_escalation_followup_required else 0
    effective_escalation_followup_due_in_seconds = int(effective_escalation_followup_due_ts - now_ts) if effective_escalation_followup_due_ts > 0 else 0
    effective_escalation_followup_status = "not_required"
    if effective_escalation_followup_required and effective_escalation_followup_due_in_seconds <= 0:
        effective_escalation_followup_status = "overdue"
    elif effective_escalation_followup_required:
        effective_escalation_followup_status = "pending"
    effective_escalation_followup_channel = "none"
    if effective_escalation_followup_action == "page_incident_manager":
        effective_escalation_followup_channel = "phone_call"
    elif effective_escalation_followup_action == "notify_feature_owner":
        effective_escalation_followup_channel = "pager"
    elif effective_escalation_followup_action == "remind_duty_engineer":
        effective_escalation_followup_channel = "chatops"
    effective_escalation_followup_urgency = "normal"
    if effective_escalation_followup_status == "overdue":
        effective_escalation_followup_urgency = "critical"
    elif effective_escalation_followup_status == "pending" and effective_escalation_followup_due_minutes <= 10 and effective_escalation_followup_due_minutes > 0:
        effective_escalation_followup_urgency = "high"
    elif effective_escalation_followup_status == "pending":
        effective_escalation_followup_urgency = "medium"
    effective_escalation_followup_retry_count = 0
    if effective_escalation_breach_level == "critical":
        effective_escalation_followup_retry_count = 3
    elif effective_escalation_breach_level == "major":
        effective_escalation_followup_retry_count = 2
    elif effective_escalation_breach_level == "minor":
        effective_escalation_followup_retry_count = 1
    if effective_escalation_followup_status == "overdue":
        effective_escalation_followup_retry_count = int(effective_escalation_followup_retry_count + 1)
    effective_escalation_followup_backoff_minutes = 0
    if effective_escalation_followup_urgency == "critical":
        effective_escalation_followup_backoff_minutes = 2
    elif effective_escalation_followup_urgency == "high":
        effective_escalation_followup_backoff_minutes = 5
    elif effective_escalation_followup_urgency == "medium":
        effective_escalation_followup_backoff_minutes = 10
    effective_escalation_followup_next_ts = int(now_ts + int(effective_escalation_followup_backoff_minutes) * 60) if effective_escalation_followup_required else 0
    effective_escalation_followup_next_in_seconds = int(effective_escalation_followup_next_ts - now_ts) if effective_escalation_followup_next_ts > 0 else 0
    effective_escalation_followup_state = "idle"
    if effective_escalation_followup_required and effective_escalation_followup_next_ts > 0:
        effective_escalation_followup_state = "scheduled"
    effective_escalation_followup_quality_score = 100
    if effective_escalation_followup_status == "overdue":
        effective_escalation_followup_quality_score -= 40
    elif effective_escalation_followup_status == "pending":
        effective_escalation_followup_quality_score -= 20
    effective_escalation_followup_quality_score -= int(max(0, effective_escalation_followup_retry_count) * 8)
    if effective_escalation_followup_urgency == "critical":
        effective_escalation_followup_quality_score -= 15
    elif effective_escalation_followup_urgency == "high":
        effective_escalation_followup_quality_score -= 8
    effective_escalation_followup_quality_score = int(max(0, min(100, effective_escalation_followup_quality_score)))
    effective_escalation_followup_quality_grade = "excellent"
    if effective_escalation_followup_quality_score < 50:
        effective_escalation_followup_quality_grade = "poor"
    elif effective_escalation_followup_quality_score < 70:
        effective_escalation_followup_quality_grade = "fair"
    elif effective_escalation_followup_quality_score < 85:
        effective_escalation_followup_quality_grade = "good"
    effective_escalation_followup_quality_recommendation = "keep_current_followup"
    if effective_escalation_followup_quality_grade == "poor":
        effective_escalation_followup_quality_recommendation = "escalate_followup_owner"
    elif effective_escalation_followup_quality_grade == "fair":
        effective_escalation_followup_quality_recommendation = "increase_followup_frequency"
    elif effective_escalation_followup_quality_grade == "good":
        effective_escalation_followup_quality_recommendation = "maintain_and_watch"
    effective_escalation_followup_quality_prev_score = int(round(max(0.0, min(1.0, 1.0 - float(prev_cmp_err5_rate))) * 100))
    effective_escalation_followup_quality_trend_delta = int(
        effective_escalation_followup_quality_score - effective_escalation_followup_quality_prev_score
    )
    effective_escalation_followup_quality_trend_direction = "stable"
    if effective_escalation_followup_quality_trend_delta >= 5:
        effective_escalation_followup_quality_trend_direction = "improving"
    elif effective_escalation_followup_quality_trend_delta <= -5:
        effective_escalation_followup_quality_trend_direction = "worsening"
    effective_escalation_followup_quality_trend_confidence = str(trend_confidence)
    effective_escalation_followup_quality_trend_alert_level = "info"
    effective_escalation_followup_quality_trend_recommendation = "keep_followup_strategy"
    if effective_escalation_followup_quality_trend_direction == "worsening":
        if effective_escalation_followup_quality_trend_delta <= -20:
            effective_escalation_followup_quality_trend_alert_level = "critical"
            effective_escalation_followup_quality_trend_recommendation = "escalate_followup_owner_and_channel"
        elif effective_escalation_followup_quality_trend_delta <= -10:
            effective_escalation_followup_quality_trend_alert_level = "warning"
            effective_escalation_followup_quality_trend_recommendation = "increase_retry_frequency"
        else:
            effective_escalation_followup_quality_trend_alert_level = "notice"
            effective_escalation_followup_quality_trend_recommendation = "tighten_followup_window"
    elif effective_escalation_followup_quality_trend_direction == "improving":
        if effective_escalation_followup_quality_trend_delta >= 10:
            effective_escalation_followup_quality_trend_alert_level = "notice"
            effective_escalation_followup_quality_trend_recommendation = "reduce_retry_frequency"
        else:
            effective_escalation_followup_quality_trend_alert_level = "info"
            effective_escalation_followup_quality_trend_recommendation = "keep_and_monitor"
    if (
        effective_escalation_followup_quality_trend_confidence == "low"
        and effective_escalation_followup_quality_trend_alert_level in ("notice", "warning")
    ):
        effective_escalation_followup_quality_trend_alert_level = "info"
        effective_escalation_followup_quality_trend_recommendation = "collect_more_samples"
    action_bucket = "observe"
    if action_priority >= 3:
        action_bucket = "immediate"
    elif action_priority == 2:
        action_bucket = "soon"
    elif action_priority == 1:
        action_bucket = "today"
    action_note = "passive_observation"
    if suggested_action == "check_backend_5xx":
        action_note = "backend_chain_check"
    elif suggested_action == "investigate_error_spike":
        action_note = "error_spike_triage"
    elif suggested_action == "check_client_error_pattern":
        action_note = "client_pattern_review"
    elif suggested_action == "collect_more_samples":
        action_note = "sample_expansion"
    sample_stats = {
        "scanned_total": int(scanned_total),
        "returned_total": returned_total,
        "window_hours": int(sample_window_hours),
        "min_ts": int(min_ts),
        "now_ts": int(now_ts),
        "health_level": str(health_level),
        "health_reason": str(health_reason),
        "health_alert": bool(health_alert),
        "alert_level": str(alert_level),
        "suggested_action": str(suggested_action),
        "action_priority": int(action_priority),
        "recommended_recheck_minutes": int(recommended_recheck_minutes),
        "action_due_ts": int(action_due_ts),
        "action_status": str(action_status),
        "action_due_in_seconds": int(action_due_in_seconds),
        "action_overdue": bool(action_overdue),
        "action_overdue_minutes": int(action_overdue_minutes),
        "breach_level": str(breach_level),
        "escalation_hint": str(escalation_hint),
        "escalation_required": bool(escalation_required),
        "escalation_deadline_ts": int(escalation_deadline_ts),
        "escalation_due_in_seconds": int(escalation_due_in_seconds),
        "escalation_urgency": str(escalation_urgency),
        "escalation_window_overdue": bool(escalation_window_overdue),
        "escalation_stage": str(escalation_stage),
        "escalation_sla_level": str(escalation_sla_level),
        "escalation_playbook_action": str(escalation_playbook_action),
        "escalation_target_response_minutes": int(escalation_target_response_minutes),
        "escalation_owner_role": str(escalation_owner_role),
        "escalation_ack_status": str(escalation_ack_status),
        "escalation_ack_due_ts": int(escalation_ack_due_ts),
        "escalation_ack_due_in_seconds": int(escalation_ack_due_in_seconds),
        "ack_breach_level": str(ack_breach_level),
        "ack_nudge_action": str(ack_nudge_action),
        "ack_nudge_channel": str(ack_nudge_channel),
        "ack_nudge_urgency": str(ack_nudge_urgency),
        "ack_nudge_retry_count": int(ack_nudge_retry_count),
        "ack_nudge_next_ts": int(ack_nudge_next_ts),
        "ack_nudge_next_in_seconds": int(ack_nudge_next_in_seconds),
        "ack_nudge_backoff_minutes": int(ack_nudge_backoff_minutes),
        "ack_nudge_state": str(ack_nudge_state),
        "ack_nudge_attempted_count": int(ack_nudge_attempted_count),
        "ack_nudge_success_rate": float(ack_nudge_success_rate),
        "ack_nudge_quality_grade": str(ack_nudge_quality_grade),
        "ack_nudge_recommendation": str(ack_nudge_recommendation),
        "ack_nudge_quality_score": int(ack_nudge_quality_score),
        "ack_nudge_quality_confidence": str(ack_nudge_quality_confidence),
        "ack_nudge_quality_prev_score": int(ack_nudge_quality_prev_score),
        "ack_nudge_quality_trend_delta": int(ack_nudge_quality_trend_delta),
        "ack_nudge_quality_trend_direction": str(ack_nudge_quality_trend_direction),
        "ack_nudge_quality_trend_confidence": str(ack_nudge_quality_trend_confidence),
        "ack_nudge_quality_trend_alert_level": str(ack_nudge_quality_trend_alert_level),
        "ack_nudge_quality_trend_recommendation": str(ack_nudge_quality_trend_recommendation),
        "trend_escalation_required": bool(trend_escalation_required),
        "trend_escalation_stage": str(trend_escalation_stage),
        "trend_escalation_owner_role": str(trend_escalation_owner_role),
        "trend_escalation_playbook_action": str(trend_escalation_playbook_action),
        "trend_escalation_target_response_minutes": int(trend_escalation_target_response_minutes),
        "effective_escalation_required": bool(effective_escalation_required),
        "effective_escalation_owner_role": str(effective_escalation_owner_role),
        "effective_escalation_playbook_action": str(effective_escalation_playbook_action),
        "effective_escalation_target_response_minutes": int(effective_escalation_target_response_minutes),
        "effective_escalation_source": str(effective_escalation_source),
        "effective_escalation_urgency": str(effective_escalation_urgency),
        "effective_escalation_due_ts": int(effective_escalation_due_ts),
        "effective_escalation_due_in_seconds": int(effective_escalation_due_in_seconds),
        "effective_escalation_overdue": bool(effective_escalation_overdue),
        "effective_escalation_due_in_minutes": int(effective_escalation_due_in_minutes),
        "effective_escalation_breach_level": str(effective_escalation_breach_level),
        "effective_escalation_followup_action": str(effective_escalation_followup_action),
        "effective_escalation_followup_required": bool(effective_escalation_followup_required),
        "effective_escalation_followup_due_minutes": int(effective_escalation_followup_due_minutes),
        "effective_escalation_followup_due_ts": int(effective_escalation_followup_due_ts),
        "effective_escalation_followup_due_in_seconds": int(effective_escalation_followup_due_in_seconds),
        "effective_escalation_followup_status": str(effective_escalation_followup_status),
        "effective_escalation_followup_channel": str(effective_escalation_followup_channel),
        "effective_escalation_followup_urgency": str(effective_escalation_followup_urgency),
        "effective_escalation_followup_retry_count": int(effective_escalation_followup_retry_count),
        "effective_escalation_followup_backoff_minutes": int(effective_escalation_followup_backoff_minutes),
        "effective_escalation_followup_next_ts": int(effective_escalation_followup_next_ts),
        "effective_escalation_followup_next_in_seconds": int(effective_escalation_followup_next_in_seconds),
        "effective_escalation_followup_state": str(effective_escalation_followup_state),
        "effective_escalation_followup_quality_score": int(effective_escalation_followup_quality_score),
        "effective_escalation_followup_quality_grade": str(effective_escalation_followup_quality_grade),
        "effective_escalation_followup_quality_recommendation": str(effective_escalation_followup_quality_recommendation),
        "effective_escalation_followup_quality_prev_score": int(effective_escalation_followup_quality_prev_score),
        "effective_escalation_followup_quality_trend_delta": int(effective_escalation_followup_quality_trend_delta),
        "effective_escalation_followup_quality_trend_direction": str(effective_escalation_followup_quality_trend_direction),
        "effective_escalation_followup_quality_trend_confidence": str(effective_escalation_followup_quality_trend_confidence),
        "effective_escalation_followup_quality_trend_alert_level": str(effective_escalation_followup_quality_trend_alert_level),
        "effective_escalation_followup_quality_trend_recommendation": str(effective_escalation_followup_quality_trend_recommendation),
        "action_bucket": str(action_bucket),
        "action_note": str(action_note),
        "status_counts": status_counts,
        "status_rates": {"ok": float(ok_rate), "err4xx": float(err4_rate), "err5xx": float(err5_rate)},
        "health_trend": {
            "direction": str(trend_direction),
            "confidence": str(trend_confidence),
            "alert": bool(trend_alert),
            "delta_err5_rate": float(trend_delta),
            "current_err5_rate": float(curr_cmp_err5_rate),
            "previous_err5_rate": float(prev_cmp_err5_rate),
            "current_total": int(curr_cmp_total),
            "previous_total": int(prev_cmp_total),
        },
        "event_top": [{"event": k, "count": int(v)} for k, v in sorted(event_counts.items(), key=lambda it: int(it[1]), reverse=True)[:8]],
    }
    return {"ok": True, "storage": storage, "totals": totals, "summary": summary, "series": series, "samples": samples, "sample_stats": sample_stats}


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


class AIProductionRuntimeOut(BaseModel):
    dispatch_hold_enabled: bool
    dispatch_hold_reason: str
    auto_hold_enabled: bool
    auto_hold_queue_threshold: int
    auto_release_on_disable: bool
    auto_release_limit: int
    auto_release_batch_size: int
    auto_release_interval_sec: int
    auto_release_adaptive_enabled: bool
    auto_release_adaptive_fail_ratio: float
    auto_release_adaptive_multiplier_pct: int
    auto_release_adaptive_apply_min_confidence: float
    auto_release_adaptive_apply_blend_pct: int
    auto_release_rollback_enabled: bool
    auto_release_rollback_fail_ratio_increase: float
    auto_release_rollback_min_samples: int
    last_auto_release_ts: int
    last_auto_release_count: int
    last_auto_release_effective_batch: int
    last_auto_release_adaptive_mode: str
    last_auto_release_fail_ratio: float
    adaptive_rollback_active: bool
    adaptive_rollback_applied_ts: int
    adaptive_rollback_baseline_fail_ratio: float
    adaptive_rollback_prev_fail_ratio: float
    adaptive_rollback_prev_multiplier_pct: int
    last_adaptive_rollback_ts: int
    last_adaptive_rollback_reason: str


class AIProductionRuntimeIn(BaseModel):
    dispatch_hold_enabled: Optional[bool] = None
    dispatch_hold_reason: Optional[str] = None
    auto_hold_enabled: Optional[bool] = None
    auto_hold_queue_threshold: Optional[int] = None
    auto_release_on_disable: Optional[bool] = None
    auto_release_limit: Optional[int] = None
    auto_release_batch_size: Optional[int] = None
    auto_release_interval_sec: Optional[int] = None
    auto_release_adaptive_enabled: Optional[bool] = None
    auto_release_adaptive_fail_ratio: Optional[float] = None
    auto_release_adaptive_multiplier_pct: Optional[int] = None
    auto_release_adaptive_apply_min_confidence: Optional[float] = None
    auto_release_adaptive_apply_blend_pct: Optional[int] = None
    auto_release_rollback_enabled: Optional[bool] = None
    auto_release_rollback_fail_ratio_increase: Optional[float] = None
    auto_release_rollback_min_samples: Optional[int] = None


class AIProductionReleaseHoldIn(BaseModel):
    limit: int = 500
    disable_hold: bool = True
    reason: Optional[str] = None


class AIProductionReleaseTickIn(BaseModel):
    force: bool = False
    reason: Optional[str] = None


class AIProductionAdaptiveApplyIn(BaseModel):
    use_suggestion: bool = True
    force: bool = False
    fail_ratio: Optional[float] = None
    multiplier_pct: Optional[int] = None


class AIProductionAdaptiveRollbackCheckIn(BaseModel):
    force: bool = False


class AIBackfillMissingScriptsIn(BaseModel):
    limit: int = 500
    confirm_phrase: str


class PostRecoveryExecuteIn(BaseModel):
    post_id: int
    confirm_phrase: str


class ContentIntegrityRepairIn(BaseModel):
    limit: int = 1000
    confirm_phrase: str


def _read_ai_production_runtime() -> Dict[str, Any]:
    from app.observability.runtime_ai_production import read_runtime_ai_production

    return read_runtime_ai_production()


def _write_ai_production_runtime(cfg: Dict[str, Any]) -> None:
    from app.observability.runtime_ai_production import write_runtime_ai_production

    write_runtime_ai_production(cfg)


def _release_dispatch_hold_jobs(db: Session, limit: int, reason: str) -> Dict[str, int]:
    lim = int(limit or 500)
    if lim < 1:
        lim = 1
    if lim > 5000:
        lim = 5000
    rsn = str(reason or "manual_release").strip()[:120] or "manual_release"
    ids = (
        db.query(AIJob.id)
        .filter(AIJob.status == "queued")
        .filter(AIJob.stage == "dispatch_hold")
        .order_by(AIJob.updated_at.asc())
        .limit(lim)
        .all()
    )
    release_ids: List[str] = []
    for row in ids:
        jid = str(getattr(row, "id", None) or (row[0] if isinstance(row, (tuple, list)) and row else "")).strip()
        if jid:
            release_ids.append(jid)
    released = 0
    if release_ids:
        released = int(
            db.query(AIJob)
            .filter(AIJob.id.in_(release_ids))
            .filter(AIJob.status == "queued")
            .filter(AIJob.stage == "dispatch_hold")
            .update(
                {
                    AIJob.stage: "dispatch_pending",
                    AIJob.stage_message: "等待派发",
                    AIJob.next_dispatch_at: datetime.now(),
                },
                synchronize_session=False,
            )
            or 0
        )
    db.commit()
    for jid in release_ids[:released]:
        try:
            from app.services.job_event_service import append_job_event

            append_job_event(str(jid), "dispatch_released", {"reason": rsn})
            append_job_event(str(jid), "dispatch_pending", {"reason": rsn, "released": True})
        except Exception:
            pass
    return {"released": int(released), "scanned": int(len(release_ids)), "effective_batch": int(lim)}


def _run_backfill_missing_scripts(db: Session, limit: int, dry_run: bool) -> Dict[str, Any]:
    from app.api.v1.endpoints.ai_jobs import _resolve_best_script_for_job, _is_usable_draft

    lim = int(limit or 500)
    if lim < 1:
        lim = 1
    if lim > 5000:
        lim = 5000
    rows = (
        db.query(AIJob)
        .filter(AIJob.status == "done")
        .order_by(AIJob.created_at.desc())
        .limit(lim)
        .all()
    )
    scanned = 0
    updated = 0
    fixed_result = 0
    fixed_draft = 0
    skipped = 0
    failed = 0
    samples: List[Dict[str, Any]] = []
    for j in rows:
        scanned += 1
        res = getattr(j, "result_json", None) if isinstance(getattr(j, "result_json", None), dict) else {}
        ps = res.get("production_script") if isinstance(res.get("production_script"), dict) else None
        dj = getattr(j, "draft_json", None) if isinstance(getattr(j, "draft_json", None), dict) else None
        if _is_usable_draft(ps) and _is_usable_draft(dj):
            skipped += 1
            continue
        p = db.query(Post).filter(Post.id == int(getattr(j, "post_id", 0) or 0)).first()
        best = _resolve_best_script_for_job(db, j, p)
        if not _is_usable_draft(best):
            failed += 1
            if len(samples) < 12:
                samples.append({"job_id": str(getattr(j, "id", "")), "post_id": int(getattr(j, "post_id", 0) or 0), "status": "unresolved"})
            continue
        changed = False
        if not _is_usable_draft(dj):
            setattr(j, "draft_json", best)
            fixed_draft += 1
            changed = True
        if not _is_usable_draft(ps):
            r2 = dict(res)
            r2["production_script"] = best
            setattr(j, "result_json", r2)
            fixed_result += 1
            changed = True
        if changed:
            updated += 1
            if len(samples) < 12:
                samples.append({"job_id": str(getattr(j, "id", "")), "post_id": int(getattr(j, "post_id", 0) or 0), "status": "patched"})
    if dry_run:
        db.rollback()
    else:
        db.commit()
    return {
        "dry_run": bool(dry_run),
        "limit": int(lim),
        "scanned": int(scanned),
        "updated_jobs": int(updated),
        "fixed_result_script": int(fixed_result),
        "fixed_draft_script": int(fixed_draft),
        "skipped_already_ok": int(skipped),
        "failed_unresolved": int(failed),
        "samples": samples,
    }


def _run_content_integrity_repair(db: Session, limit: int, dry_run: bool) -> Dict[str, Any]:
    from app.api.v1.endpoints.ai_jobs import _resolve_best_script_for_job, _is_usable_draft

    lim = int(limit or 1000)
    if lim < 1:
        lim = 1
    if lim > 5000:
        lim = 5000
    rows = db.query(Post).order_by(Post.id.desc()).limit(lim).all()
    scanned = 0
    bad = 0
    fixed_posts = 0
    linked_job = 0
    fixed_script = 0
    unresolved = 0
    samples: List[Dict[str, Any]] = []
    for p in rows:
        scanned += 1
        st = str(getattr(p, "status", "") or "")
        if st not in {"done", "preview"}:
            continue
        if not getattr(p, "video_url", None) or not getattr(p, "cover_url", None):
            continue
        jid = str(getattr(p, "ai_job_id", "") or "")
        j = db.query(AIJob).filter(AIJob.id == jid).first() if jid else None
        if not j:
            j = db.query(AIJob).filter(AIJob.post_id == int(getattr(p, "id", 0) or 0)).order_by(AIJob.created_at.desc()).first()
        if not j:
            bad += 1
            unresolved += 1
            if len(samples) < 20:
                samples.append({"post_id": int(getattr(p, "id", 0) or 0), "reason": "job_missing"})
            continue
        res = getattr(j, "result_json", None) if isinstance(getattr(j, "result_json", None), dict) else {}
        ps = res.get("production_script") if isinstance(res.get("production_script"), dict) else None
        dj = getattr(j, "draft_json", None) if isinstance(getattr(j, "draft_json", None), dict) else None
        ok = _is_usable_draft(ps) and _is_usable_draft(dj)
        if st == "done" and ok and str(getattr(p, "ai_job_id", "") or "") == str(getattr(j, "id", "") or ""):
            continue
        bad += 1
        changed = False
        if str(getattr(p, "ai_job_id", "") or "") != str(getattr(j, "id", "") or ""):
            p.ai_job_id = str(getattr(j, "id", "") or "")
            linked_job += 1
            changed = True
        if st != "done":
            p.status = "done"
            changed = True
        if not ok:
            best = _resolve_best_script_for_job(db, j, p)
            if _is_usable_draft(best):
                if not _is_usable_draft(dj):
                    j.draft_json = best
                if not _is_usable_draft(ps):
                    r2 = dict(res)
                    r2["production_script"] = best
                    j.result_json = r2
                fixed_script += 1
                changed = True
        if changed:
            fixed_posts += 1
            if len(samples) < 20:
                samples.append({"post_id": int(getattr(p, "id", 0) or 0), "job_id": str(getattr(j, "id", "") or ""), "status": str(getattr(p, "status", "") or "")})
        else:
            unresolved += 1
    if dry_run:
        db.rollback()
    else:
        db.commit()
    return {
        "dry_run": bool(dry_run),
        "limit": int(lim),
        "scanned": int(scanned),
        "bad_candidates": int(bad),
        "fixed_posts": int(fixed_posts),
        "linked_job": int(linked_job),
        "fixed_script": int(fixed_script),
        "unresolved": int(unresolved),
        "samples": samples,
    }


def _build_post_recovery_preview(db: Session, post_id: int) -> Dict[str, Any]:
    pid = int(post_id or 0)
    if pid <= 0:
        raise HTTPException(status_code=400, detail="invalid_post_id")
    p = db.query(Post).filter(Post.id == pid).first()
    jobs = db.query(AIJob).filter(AIJob.post_id == pid).order_by(AIJob.created_at.desc()).limit(20).all()
    ce_cnt = int(db.query(func.count(PostCounterEvent.id)).filter(PostCounterEvent.post_id == pid).scalar() or 0)
    inter_cnt = int(db.query(func.count(Interaction.id)).filter(Interaction.post_id == pid).scalar() or 0)
    cmt_cnt = int(db.query(func.count(Comment.id)).filter(Comment.post_id == pid).scalar() or 0)
    ne_cnt = 0
    cl_cnt = 0
    try:
        ne_rows = db.query(NotificationEvent).order_by(NotificationEvent.id.desc()).limit(2000).all()
        for ev in ne_rows:
            pl = getattr(ev, "payload", None)
            if isinstance(pl, dict) and int(pl.get("post_id") or 0) == pid:
                ne_cnt += 1
    except Exception:
        ne_cnt = 0
    try:
        cl_rows = db.query(ClientEvent).order_by(ClientEvent.id.desc()).limit(2000).all()
        for ev in cl_rows:
            dt = getattr(ev, "data", None)
            if isinstance(dt, dict) and int(dt.get("post_id") or 0) == pid:
                cl_cnt += 1
    except Exception:
        cl_cnt = 0
    job_rows: List[Dict[str, Any]] = []
    for j in jobs[:8]:
        res = getattr(j, "result_json", None) if isinstance(getattr(j, "result_json", None), dict) else {}
        ps = res.get("production_script") if isinstance(res.get("production_script"), dict) else {}
        dj = getattr(j, "draft_json", None) if isinstance(getattr(j, "draft_json", None), dict) else {}
        job_rows.append(
            {
                "job_id": str(getattr(j, "id", "")),
                "status": str(getattr(j, "status", "") or ""),
                "created_at": getattr(j, "created_at", None).isoformat() if getattr(j, "created_at", None) else None,
                "result_scenes": int(len((ps or {}).get("scenes") or [])),
                "draft_scenes": int(len((dj or {}).get("scenes") or [])),
            }
        )
    can_flip_done = bool(
        p
        and str(getattr(p, "status", "") or "") in {"preview", "removed", "deleted"}
        and bool(getattr(p, "video_url", None))
        and bool(getattr(p, "cover_url", None))
    )
    reason = "post_not_found"
    if p:
        reason = "post_exists"
    elif jobs:
        reason = "post_missing_but_jobs_exist"
    elif ce_cnt + inter_cnt + cmt_cnt + ne_cnt + cl_cnt > 0:
        reason = "post_missing_with_event_traces"
    return {
        "post_id": int(pid),
        "post_exists": bool(p),
        "post": {
            "status": str(getattr(p, "status", "") or "") if p else None,
            "user_id": int(getattr(p, "user_id", 0) or 0) if p else None,
            "ai_job_id": str(getattr(p, "ai_job_id", "") or "") if p else None,
            "video_url": bool(getattr(p, "video_url", None)) if p else False,
            "cover_url": bool(getattr(p, "cover_url", None)) if p else False,
            "title": str(getattr(p, "title", "") or "") if p else "",
        },
        "job_count": int(len(jobs)),
        "jobs": job_rows,
        "trace_counts": {
            "post_counter_events": int(ce_cnt),
            "interactions": int(inter_cnt),
            "comments": int(cmt_cnt),
            "notification_events": int(ne_cnt),
            "client_events": int(cl_cnt),
        },
        "can_recover_status_to_done": bool(can_flip_done),
        "recovery_reason": str(reason),
        "backup_restore_required": bool((not p) and len(jobs) == 0),
    }


def _execute_post_recovery(db: Session, post_id: int) -> Dict[str, Any]:
    pv = _build_post_recovery_preview(db, post_id)
    if not bool(pv.get("post_exists")):
        return {"ok": False, "action": "no_write", "reason": str(pv.get("recovery_reason") or "post_not_found"), "preview": pv}
    if not bool(pv.get("can_recover_status_to_done")):
        return {"ok": False, "action": "no_write", "reason": "post_not_recoverable_by_status_flip", "preview": pv}
    p = db.query(Post).filter(Post.id == int(post_id)).first()
    if not p:
        return {"ok": False, "action": "no_write", "reason": "post_not_found_after_preview", "preview": pv}
    if not getattr(p, "ai_job_id", None):
        j = db.query(AIJob).filter(AIJob.post_id == int(post_id)).order_by(AIJob.created_at.desc()).first()
        if j and getattr(j, "id", None):
            p.ai_job_id = str(getattr(j, "id"))
    p.status = "done"
    db.commit()
    return {"ok": True, "action": "status_flip_to_done", "post_id": int(post_id), "status": "done", "preview": pv}


def _append_auto_release_history(cfg: Dict[str, Any], *, ts: int, released: int, effective_batch: int, fail_ratio: float, mode: str) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(cfg if isinstance(cfg, dict) else {})
    arr = out.get("auto_release_history")
    hist = arr if isinstance(arr, list) else []
    evt = {
        "ts": int(ts),
        "released": int(released),
        "effective_batch": int(effective_batch),
        "fail_ratio": float(max(0.0, min(1.0, float(fail_ratio or 0.0)))),
        "mode": str(mode or "normal")[:32] or "normal",
    }
    hist2 = [x for x in hist if isinstance(x, dict)]
    hist2.append(evt)
    if len(hist2) > 120:
        hist2 = hist2[-120:]
    out["auto_release_history"] = hist2
    return out


def _append_adaptive_rollback_history(
    cfg: Dict[str, Any],
    *,
    ts: int,
    reason: str,
    avg_fail_ratio: float,
    threshold: float,
    samples: int,
    restored_fail_ratio: float,
    restored_multiplier_pct: int,
) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(cfg if isinstance(cfg, dict) else {})
    arr = out.get("adaptive_rollback_history")
    hist = arr if isinstance(arr, list) else []
    evt = {
        "ts": int(ts),
        "reason": str(reason or "")[:64],
        "avg_fail_ratio": float(max(0.0, min(1.0, float(avg_fail_ratio or 0.0)))),
        "threshold": float(max(0.0, min(1.0, float(threshold or 0.0)))),
        "samples": int(max(0, int(samples or 0))),
        "restored_fail_ratio": float(max(0.0, min(1.0, float(restored_fail_ratio or 0.0)))),
        "restored_multiplier_pct": int(max(5, min(100, int(restored_multiplier_pct or 50)))),
    }
    hist2 = [x for x in hist if isinstance(x, dict)]
    hist2.append(evt)
    if len(hist2) > 120:
        hist2 = hist2[-120:]
    out["adaptive_rollback_history"] = hist2
    return out


def _append_adaptive_apply_history(
    cfg: Dict[str, Any],
    *,
    ts: int,
    force: bool,
    blend_pct: int,
    confidence: float,
    applied_fail_ratio: float,
    applied_multiplier_pct: int,
) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(cfg if isinstance(cfg, dict) else {})
    arr = out.get("adaptive_apply_history")
    hist = arr if isinstance(arr, list) else []
    evt = {
        "ts": int(ts),
        "force": bool(force),
        "blend_pct": int(max(0, min(100, int(blend_pct or 0)))),
        "confidence": float(max(0.0, min(1.0, float(confidence or 0.0)))),
        "applied_fail_ratio": float(max(0.0, min(1.0, float(applied_fail_ratio or 0.0)))),
        "applied_multiplier_pct": int(max(5, min(100, int(applied_multiplier_pct or 50)))),
    }
    hist2 = [x for x in hist if isinstance(x, dict)]
    hist2.append(evt)
    if len(hist2) > 120:
        hist2 = hist2[-120:]
    out["adaptive_apply_history"] = hist2
    return out


def _filter_audit_events(
    events: List[Dict[str, Any]],
    *,
    reason: Optional[str],
    since_ts: Optional[int],
    until_ts: Optional[int],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    kw = str(reason or "").strip().lower()
    s_ts = int(since_ts or 0)
    u_ts = int(until_ts or 0)
    for x in events:
        if not isinstance(x, dict):
            continue
        ts = int(x.get("ts", 0) or 0)
        if s_ts > 0 and ts > 0 and ts < s_ts:
            continue
        if u_ts > 0 and ts > 0 and ts > u_ts:
            continue
        if kw:
            hay = " ".join(
                [
                    str(x.get("reason", "") or ""),
                    str(x.get("mode", "") or ""),
                    str(x.get("action", "") or ""),
                ]
            ).lower()
            if kw not in hay:
                continue
        out.append(x)
    return out


def _audit_reason_value(x: Dict[str, Any], kind: str) -> str:
    if str(kind) == "rollback":
        return str(x.get("reason", "") or "unknown")
    if str(kind) == "apply":
        return "force" if bool(x.get("force", False)) else "normal"
    return str(x.get("mode", "") or "unknown")


def _audit_day_value(ts: int) -> str:
    try:
        return datetime.utcfromtimestamp(int(ts or 0)).strftime("%Y-%m-%d")
    except Exception:
        return "unknown"


def _ai_production_stage_counts(db: Session) -> Dict[str, int]:
    rows = (
        db.query(AIJob.stage, func.count(AIJob.id))
        .filter(AIJob.status == "queued")
        .group_by(AIJob.stage)
        .all()
    )
    out: Dict[str, int] = {}
    for st, cnt in rows:
        k = str(st or "")
        out[k] = int(cnt or 0)
    return out


def _ai_production_adaptive_suggestion(runtime: Dict[str, Any]) -> Dict[str, Any]:
    cfg = runtime if isinstance(runtime, dict) else {}
    arr = cfg.get("auto_release_history")
    hist = [x for x in (arr if isinstance(arr, list) else []) if isinstance(x, dict)][-30:]
    if not hist:
        return {
            "fail_ratio": float(cfg.get("auto_release_adaptive_fail_ratio", 0.35) or 0.35),
            "multiplier_pct": int(cfg.get("auto_release_adaptive_multiplier_pct", 50) or 50),
            "confidence": 0.0,
            "samples": 0,
        }
    w_sum = 0.0
    fr_sum = 0.0
    for it in hist:
        rel = int(it.get("released", 0) or 0)
        eff = int(it.get("effective_batch", 0) or 0)
        w = max(1.0, float(min(max(rel, 0), max(eff, 1))))
        fr = float(it.get("fail_ratio", 0.0) or 0.0)
        if fr < 0:
            fr = 0.0
        if fr > 1:
            fr = 1.0
        w_sum += w
        fr_sum += (fr * w)
    avg_fail = (fr_sum / w_sum) if w_sum > 0 else 0.0
    rec_fail = max(0.15, min(0.85, float(avg_fail + 0.08)))
    if avg_fail >= 0.50:
        rec_mul = 35
    elif avg_fail >= 0.35:
        rec_mul = 50
    else:
        rec_mul = 70
    return {
        "fail_ratio": float(round(rec_fail, 4)),
        "multiplier_pct": int(rec_mul),
        "confidence": float(round(min(1.0, len(hist) / 20.0), 3)),
        "samples": int(len(hist)),
    }


def _maybe_apply_adaptive_rollback(cfg: Dict[str, Any], force: bool = False) -> tuple[Dict[str, Any], Dict[str, Any]]:
    out: Dict[str, Any] = dict(cfg if isinstance(cfg, dict) else {})
    if not bool(out.get("auto_release_rollback_enabled", True)):
        return out, {"action": "disabled"}
    active = bool(out.get("adaptive_rollback_active", False))
    if not active and not bool(force):
        return out, {"action": "inactive"}
    arr = out.get("auto_release_history")
    hist = [x for x in (arr if isinstance(arr, list) else []) if isinstance(x, dict)]
    applied_ts = int(out.get("adaptive_rollback_applied_ts", 0) or 0)
    if applied_ts > 0:
        hist = [x for x in hist if int(x.get("ts", 0) or 0) >= applied_ts]
    samples = len(hist)
    min_samples = int(out.get("auto_release_rollback_min_samples", 6) or 6)
    if min_samples < 1:
        min_samples = 1
    fr_vals: List[float] = []
    for x in hist:
        v = float(x.get("fail_ratio", 0.0) or 0.0)
        if v < 0:
            v = 0.0
        if v > 1:
            v = 1.0
        fr_vals.append(v)
    avg_fail = float(sum(fr_vals) / len(fr_vals)) if fr_vals else float(out.get("last_auto_release_fail_ratio", 0.0) or 0.0)
    baseline = float(out.get("adaptive_rollback_baseline_fail_ratio", out.get("last_auto_release_fail_ratio", 0.0)) or 0.0)
    inc = float(out.get("auto_release_rollback_fail_ratio_increase", 0.12) or 0.12)
    if inc < 0:
        inc = 0.0
    threshold = float(baseline + inc)
    if (samples < min_samples) and not bool(force):
        return out, {"action": "insufficient_samples", "samples": int(samples), "min_samples": int(min_samples), "avg_fail_ratio": float(avg_fail), "threshold": float(threshold)}
    if (avg_fail < threshold) and not bool(force):
        return out, {"action": "healthy", "samples": int(samples), "avg_fail_ratio": float(avg_fail), "threshold": float(threshold)}
    prev_fr = float(out.get("adaptive_rollback_prev_fail_ratio", out.get("auto_release_adaptive_fail_ratio", 0.35)) or 0.35)
    prev_mul = int(out.get("adaptive_rollback_prev_multiplier_pct", out.get("auto_release_adaptive_multiplier_pct", 50)) or 50)
    if prev_mul < 5:
        prev_mul = 5
    if prev_mul > 100:
        prev_mul = 100
    out["auto_release_adaptive_fail_ratio"] = float(max(0.0, min(1.0, prev_fr)))
    out["auto_release_adaptive_multiplier_pct"] = int(prev_mul)
    out["adaptive_rollback_active"] = False
    rb_ts = int(datetime.now().timestamp())
    out["last_adaptive_rollback_ts"] = int(rb_ts)
    out["last_adaptive_rollback_reason"] = "force" if bool(force) else "fail_ratio_regression"
    out = _append_adaptive_rollback_history(
        out,
        ts=int(rb_ts),
        reason=str(out.get("last_adaptive_rollback_reason", "")),
        avg_fail_ratio=float(avg_fail),
        threshold=float(threshold),
        samples=int(samples),
        restored_fail_ratio=float(prev_fr),
        restored_multiplier_pct=int(prev_mul),
    )
    return out, {
        "action": "rolled_back",
        "samples": int(samples),
        "avg_fail_ratio": float(avg_fail),
        "threshold": float(threshold),
        "restored_fail_ratio": float(prev_fr),
        "restored_multiplier_pct": int(prev_mul),
    }


@router.get("/ai-production/runtime", response_model=AIProductionRuntimeOut)
def get_ai_production_runtime(current_user: User = Depends(require_admin)):
    cfg = _read_ai_production_runtime()

    def _f(k: str, default):
        v = cfg.get(k)
        return default if v is None else v

    return {
        "dispatch_hold_enabled": bool(_f("dispatch_hold_enabled", False)),
        "dispatch_hold_reason": str(_f("dispatch_hold_reason", "manual_hold")),
        "auto_hold_enabled": bool(_f("auto_hold_enabled", True)),
        "auto_hold_queue_threshold": int(_f("auto_hold_queue_threshold", 2000)),
        "auto_release_on_disable": bool(_f("auto_release_on_disable", True)),
        "auto_release_limit": int(_f("auto_release_limit", 500)),
        "auto_release_batch_size": int(_f("auto_release_batch_size", 200)),
        "auto_release_interval_sec": int(_f("auto_release_interval_sec", 15)),
        "auto_release_adaptive_enabled": bool(_f("auto_release_adaptive_enabled", True)),
        "auto_release_adaptive_fail_ratio": float(_f("auto_release_adaptive_fail_ratio", 0.35)),
        "auto_release_adaptive_multiplier_pct": int(_f("auto_release_adaptive_multiplier_pct", 50)),
        "auto_release_adaptive_apply_min_confidence": float(_f("auto_release_adaptive_apply_min_confidence", 0.4)),
        "auto_release_adaptive_apply_blend_pct": int(_f("auto_release_adaptive_apply_blend_pct", 30)),
        "auto_release_rollback_enabled": bool(_f("auto_release_rollback_enabled", True)),
        "auto_release_rollback_fail_ratio_increase": float(_f("auto_release_rollback_fail_ratio_increase", 0.12)),
        "auto_release_rollback_min_samples": int(_f("auto_release_rollback_min_samples", 6)),
        "last_auto_release_ts": int(_f("last_auto_release_ts", 0)),
        "last_auto_release_count": int(_f("last_auto_release_count", 0)),
        "last_auto_release_effective_batch": int(_f("last_auto_release_effective_batch", 0)),
        "last_auto_release_adaptive_mode": str(_f("last_auto_release_adaptive_mode", "normal")),
        "last_auto_release_fail_ratio": float(_f("last_auto_release_fail_ratio", 0.0)),
        "adaptive_rollback_active": bool(_f("adaptive_rollback_active", False)),
        "adaptive_rollback_applied_ts": int(_f("adaptive_rollback_applied_ts", 0)),
        "adaptive_rollback_baseline_fail_ratio": float(_f("adaptive_rollback_baseline_fail_ratio", 0.0)),
        "adaptive_rollback_prev_fail_ratio": float(_f("adaptive_rollback_prev_fail_ratio", 0.35)),
        "adaptive_rollback_prev_multiplier_pct": int(_f("adaptive_rollback_prev_multiplier_pct", 50)),
        "last_adaptive_rollback_ts": int(_f("last_adaptive_rollback_ts", 0)),
        "last_adaptive_rollback_reason": str(_f("last_adaptive_rollback_reason", "")),
    }


@router.post("/ai-production/runtime", response_model=AIProductionRuntimeOut)
def set_ai_production_runtime(body: AIProductionRuntimeIn, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    cfg = _read_ai_production_runtime()
    upd: Dict[str, Any] = dict(cfg)
    prev_hold_enabled = bool(cfg.get("dispatch_hold_enabled", False))
    if body.dispatch_hold_enabled is not None:
        upd["dispatch_hold_enabled"] = bool(body.dispatch_hold_enabled)
    if body.dispatch_hold_reason is not None:
        upd["dispatch_hold_reason"] = str(body.dispatch_hold_reason or "manual_hold").strip()[:120] or "manual_hold"
    if body.auto_hold_enabled is not None:
        upd["auto_hold_enabled"] = bool(body.auto_hold_enabled)
    if body.auto_hold_queue_threshold is not None:
        v = int(body.auto_hold_queue_threshold)
        if v < 10:
            v = 10
        if v > 200000:
            v = 200000
        upd["auto_hold_queue_threshold"] = int(v)
    if body.auto_release_on_disable is not None:
        upd["auto_release_on_disable"] = bool(body.auto_release_on_disable)
    if body.auto_release_limit is not None:
        v = int(body.auto_release_limit)
        if v < 1:
            v = 1
        if v > 5000:
            v = 5000
        upd["auto_release_limit"] = int(v)
    if body.auto_release_batch_size is not None:
        v = int(body.auto_release_batch_size)
        if v < 1:
            v = 1
        if v > 1000:
            v = 1000
        upd["auto_release_batch_size"] = int(v)
    if body.auto_release_interval_sec is not None:
        v = int(body.auto_release_interval_sec)
        if v < 1:
            v = 1
        if v > 3600:
            v = 3600
        upd["auto_release_interval_sec"] = int(v)
    if body.auto_release_adaptive_enabled is not None:
        upd["auto_release_adaptive_enabled"] = bool(body.auto_release_adaptive_enabled)
    if body.auto_release_adaptive_fail_ratio is not None:
        v = float(body.auto_release_adaptive_fail_ratio)
        if v < 0:
            v = 0.0
        if v > 1:
            v = 1.0
        upd["auto_release_adaptive_fail_ratio"] = float(v)
    if body.auto_release_adaptive_multiplier_pct is not None:
        v = int(body.auto_release_adaptive_multiplier_pct)
        if v < 5:
            v = 5
        if v > 100:
            v = 100
        upd["auto_release_adaptive_multiplier_pct"] = int(v)
    if body.auto_release_adaptive_apply_min_confidence is not None:
        v = float(body.auto_release_adaptive_apply_min_confidence)
        if v < 0:
            v = 0.0
        if v > 1:
            v = 1.0
        upd["auto_release_adaptive_apply_min_confidence"] = float(v)
    if body.auto_release_adaptive_apply_blend_pct is not None:
        v = int(body.auto_release_adaptive_apply_blend_pct)
        if v < 5:
            v = 5
        if v > 100:
            v = 100
        upd["auto_release_adaptive_apply_blend_pct"] = int(v)
    if body.auto_release_rollback_enabled is not None:
        upd["auto_release_rollback_enabled"] = bool(body.auto_release_rollback_enabled)
    if body.auto_release_rollback_fail_ratio_increase is not None:
        v = float(body.auto_release_rollback_fail_ratio_increase)
        if v < 0:
            v = 0.0
        if v > 1:
            v = 1.0
        upd["auto_release_rollback_fail_ratio_increase"] = float(v)
    if body.auto_release_rollback_min_samples is not None:
        v = int(body.auto_release_rollback_min_samples)
        if v < 1:
            v = 1
        if v > 200:
            v = 200
        upd["auto_release_rollback_min_samples"] = int(v)
    _write_ai_production_runtime(upd)
    now_hold_enabled = bool(upd.get("dispatch_hold_enabled", False))
    if prev_hold_enabled and not now_hold_enabled and bool(upd.get("auto_release_on_disable", True)):
        limit = min(int(upd.get("auto_release_limit", 500) or 500), int(upd.get("auto_release_batch_size", 200) or 200))
        reason = str(upd.get("dispatch_hold_reason", "manual_release") or "manual_release")
        try:
            st = _release_dispatch_hold_jobs(db, limit=limit, reason=reason)
            upd["last_auto_release_ts"] = int(datetime.now().timestamp())
            upd["last_auto_release_count"] = int(st.get("released", 0) or 0)
            upd["last_auto_release_effective_batch"] = int(st.get("effective_batch", 0) or 0)
            upd["last_auto_release_adaptive_mode"] = "disable_hold"
            upd["last_auto_release_fail_ratio"] = float(upd.get("last_auto_release_fail_ratio", 0.0) or 0.0)
            upd = _append_auto_release_history(
                upd,
                ts=int(upd.get("last_auto_release_ts", 0) or 0),
                released=int(st.get("released", 0) or 0),
                effective_batch=int(st.get("effective_batch", 0) or 0),
                fail_ratio=float(upd.get("last_auto_release_fail_ratio", 0.0) or 0.0),
                mode="disable_hold",
            )
            _write_ai_production_runtime(upd)
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
    return get_ai_production_runtime(current_user=current_user)


@router.get("/ai-production/status")
def get_ai_production_status(current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> Dict[str, Any]:
    cfg0 = _read_ai_production_runtime()
    cfg1, rb = _maybe_apply_adaptive_rollback(cfg0, force=False)
    if rb.get("action") == "rolled_back":
        _write_ai_production_runtime(cfg1)
    runtime = get_ai_production_runtime(current_user=current_user).model_dump()
    suggestion = _ai_production_adaptive_suggestion(runtime)
    min_conf = float(runtime.get("auto_release_adaptive_apply_min_confidence", 0.4) or 0.4)
    can_apply = bool(float(suggestion.get("confidence", 0.0) or 0.0) >= min_conf)
    apply_reason = "ready" if can_apply else "low_confidence"
    stage_counts = _ai_production_stage_counts(db)
    now_ts = int(datetime.now().timestamp())
    last_ts = int(runtime.get("last_auto_release_ts", 0) or 0)
    interval_sec = int(runtime.get("auto_release_interval_sec", 15) or 15)
    wait_sec = 0
    if last_ts > 0 and interval_sec > 0:
        wait_sec = max(0, int(interval_sec - max(0, now_ts - last_ts)))
    return {
        "ok": True,
        "queued_total": int(sum(int(v or 0) for v in stage_counts.values())),
        "hold_count": int(stage_counts.get("dispatch_hold", 0)),
        "pending_count": int(stage_counts.get("dispatch_pending", 0)),
        "dispatching_count": int(stage_counts.get("dispatching", 0)),
        "failed_count": int(stage_counts.get("dispatch_failed", 0)),
        "adaptive_mode": str(runtime.get("last_auto_release_adaptive_mode", "normal") or "normal"),
        "adaptive_fail_ratio": float(runtime.get("last_auto_release_fail_ratio", 0.0) or 0.0),
        "adaptive_suggestion": suggestion,
        "adaptive_suggestion_apply": {"can_apply": bool(can_apply), "reason": str(apply_reason), "min_confidence": float(min_conf)},
        "adaptive_rollback": rb,
        "next_auto_release_in_sec": int(wait_sec),
        "runtime": runtime,
    }


@router.get("/ai-production/audit")
def get_ai_production_audit(
    limit: int = 20,
    reason: Optional[str] = None,
    since_ts: Optional[int] = None,
    until_ts: Optional[int] = None,
    current_user: User = Depends(require_admin),
) -> Dict[str, Any]:
    runtime = get_ai_production_runtime(current_user=current_user).model_dump()
    cfg = _read_ai_production_runtime()
    lim = int(limit or 20)
    if lim < 1:
        lim = 1
    if lim > 200:
        lim = 200
    ar = cfg.get("auto_release_history")
    rr = cfg.get("adaptive_rollback_history")
    ap = cfg.get("adaptive_apply_history")
    auto_release_history = [x for x in (ar if isinstance(ar, list) else []) if isinstance(x, dict)][-max(lim * 2, 60):]
    rollback_history = [x for x in (rr if isinstance(rr, list) else []) if isinstance(x, dict)][-max(lim * 2, 60):]
    apply_history = [x for x in (ap if isinstance(ap, list) else []) if isinstance(x, dict)][-max(lim * 2, 60):]
    auto_release_history = _filter_audit_events(auto_release_history, reason=reason, since_ts=since_ts, until_ts=until_ts)[-lim:]
    rollback_history = _filter_audit_events(rollback_history, reason=reason, since_ts=since_ts, until_ts=until_ts)[-lim:]
    apply_history = _filter_audit_events(apply_history, reason=reason, since_ts=since_ts, until_ts=until_ts)[-lim:]
    auto_release_history.reverse()
    rollback_history.reverse()
    apply_history.reverse()
    return {
        "ok": True,
        "runtime": runtime,
        "auto_release_history": auto_release_history,
        "adaptive_apply_history": apply_history,
        "adaptive_rollback_history": rollback_history,
    }


@router.get("/ai-production/audit/export")
def export_ai_production_audit(
    kind: str = Query("rollback"),
    format: str = Query("json"),
    limit: int = 200,
    reason: Optional[str] = None,
    since_ts: Optional[int] = None,
    until_ts: Optional[int] = None,
    current_user: User = Depends(require_admin),
):
    _ = current_user
    k = str(kind or "rollback").strip().lower()
    if k not in {"rollback", "apply", "release"}:
        k = "rollback"
    fmt = str(format or "json").strip().lower()
    if fmt not in {"json", "csv"}:
        fmt = "json"
    lim = int(limit or 200)
    if lim < 1:
        lim = 1
    if lim > 5000:
        lim = 5000
    cfg = _read_ai_production_runtime()
    if k == "rollback":
        src = [x for x in (cfg.get("adaptive_rollback_history") if isinstance(cfg.get("adaptive_rollback_history"), list) else []) if isinstance(x, dict)]
        cols = ["ts", "reason", "avg_fail_ratio", "threshold", "samples", "restored_fail_ratio", "restored_multiplier_pct"]
    elif k == "apply":
        src = [x for x in (cfg.get("adaptive_apply_history") if isinstance(cfg.get("adaptive_apply_history"), list) else []) if isinstance(x, dict)]
        cols = ["ts", "force", "blend_pct", "confidence", "applied_fail_ratio", "applied_multiplier_pct"]
    else:
        src = [x for x in (cfg.get("auto_release_history") if isinstance(cfg.get("auto_release_history"), list) else []) if isinstance(x, dict)]
        cols = ["ts", "released", "effective_batch", "fail_ratio", "mode"]
    items = _filter_audit_events(src, reason=reason, since_ts=since_ts, until_ts=until_ts)[-lim:]
    items.reverse()
    if fmt == "json":
        return {"ok": True, "kind": k, "count": int(len(items)), "items": items}
    sio = io.StringIO()
    w = csv.DictWriter(sio, fieldnames=cols)
    w.writeheader()
    for it in items:
        row = {c: it.get(c) for c in cols}
        w.writerow(row)
    return PlainTextResponse(content=sio.getvalue(), media_type="text/csv; charset=utf-8")


@router.get("/ai-production/audit/summary")
def get_ai_production_audit_summary(
    kind: str = Query("rollback"),
    days: int = 7,
    reason: Optional[str] = None,
    current_user: User = Depends(require_admin),
) -> Dict[str, Any]:
    _ = current_user
    k = str(kind or "rollback").strip().lower()
    if k not in {"rollback", "apply", "release"}:
        k = "rollback"
    d = int(days or 7)
    if d < 1:
        d = 1
    if d > 90:
        d = 90
    now_ts = int(datetime.now().timestamp())
    since_ts = int(now_ts - d * 24 * 3600)
    cfg = _read_ai_production_runtime()
    if k == "rollback":
        src = [x for x in (cfg.get("adaptive_rollback_history") if isinstance(cfg.get("adaptive_rollback_history"), list) else []) if isinstance(x, dict)]
    elif k == "apply":
        src = [x for x in (cfg.get("adaptive_apply_history") if isinstance(cfg.get("adaptive_apply_history"), list) else []) if isinstance(x, dict)]
    else:
        src = [x for x in (cfg.get("auto_release_history") if isinstance(cfg.get("auto_release_history"), list) else []) if isinstance(x, dict)]
    items = _filter_audit_events(src, reason=reason, since_ts=since_ts, until_ts=None)
    reason_map: Dict[str, int] = {}
    day_map: Dict[str, int] = {}
    for it in items:
        rs = _audit_reason_value(it, k)
        reason_map[rs] = int(reason_map.get(rs, 0) or 0) + 1
        day = _audit_day_value(int(it.get("ts", 0) or 0))
        day_map[day] = int(day_map.get(day, 0) or 0) + 1
    reasons = [{"reason": rk, "count": int(rv)} for rk, rv in reason_map.items()]
    reasons.sort(key=lambda x: int(x.get("count", 0) or 0), reverse=True)
    trends = [{"day": dk, "count": int(dv)} for dk, dv in day_map.items()]
    trends.sort(key=lambda x: str(x.get("day", "")))
    return {"ok": True, "kind": k, "days": int(d), "reason": str(reason or ""), "count": int(len(items)), "reasons": reasons[:20], "trends": trends}


@router.post("/ai-production/release-tick")
def run_ai_production_release_tick(
    body: AIProductionReleaseTickIn,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    runtime = get_ai_production_runtime(current_user=current_user).model_dump()
    hold_enabled = bool(runtime.get("dispatch_hold_enabled", False))
    if hold_enabled and not bool(body.force):
        st = get_ai_production_status(current_user=current_user, db=db)
        return {"ok": True, "action": "hold_enabled", "status": st}
    now_ts = int(datetime.now().timestamp())
    interval_sec = int(runtime.get("auto_release_interval_sec", 15) or 15)
    last_ts = int(runtime.get("last_auto_release_ts", 0) or 0)
    wait_sec = 0
    if last_ts > 0 and interval_sec > 0:
        wait_sec = max(0, int(interval_sec - max(0, now_ts - last_ts)))
    if wait_sec > 0 and not bool(body.force):
        st = get_ai_production_status(current_user=current_user, db=db)
        return {"ok": True, "action": "throttled", "wait_sec": int(wait_sec), "status": st}
    limit = min(int(runtime.get("auto_release_limit", 500) or 500), int(runtime.get("auto_release_batch_size", 200) or 200))
    reason = str(body.reason or "manual_tick").strip()[:120] or "manual_tick"
    st = _release_dispatch_hold_jobs(db, limit=limit, reason=reason)
    runtime["last_auto_release_ts"] = int(now_ts)
    runtime["last_auto_release_count"] = int(st.get("released", 0) or 0)
    runtime["last_auto_release_effective_batch"] = int(st.get("effective_batch", 0) or 0)
    runtime["last_auto_release_adaptive_mode"] = "manual_tick"
    runtime["last_auto_release_fail_ratio"] = float(runtime.get("last_auto_release_fail_ratio", 0.0) or 0.0)
    runtime = _append_auto_release_history(
        runtime,
        ts=int(now_ts),
        released=int(st.get("released", 0) or 0),
        effective_batch=int(st.get("effective_batch", 0) or 0),
        fail_ratio=float(runtime.get("last_auto_release_fail_ratio", 0.0) or 0.0),
        mode="manual_tick",
    )
    _write_ai_production_runtime(runtime)
    out = get_ai_production_status(current_user=current_user, db=db)
    return {"ok": True, "action": "released", "released": int(st.get("released", 0) or 0), "status": out}


@router.post("/ai-production/adaptive-suggestion/apply")
def apply_ai_production_adaptive_suggestion(
    body: AIProductionAdaptiveApplyIn,
    current_user: User = Depends(require_admin),
) -> Dict[str, Any]:
    cfg = _read_ai_production_runtime()
    runtime = get_ai_production_runtime(current_user=current_user).model_dump()
    sug = _ai_production_adaptive_suggestion(runtime)
    upd: Dict[str, Any] = dict(cfg if isinstance(cfg, dict) else {})
    conf = float(sug.get("confidence", 0.0) or 0.0)
    min_conf = float(runtime.get("auto_release_adaptive_apply_min_confidence", 0.4) or 0.4)
    blend_pct = int(runtime.get("auto_release_adaptive_apply_blend_pct", 30) or 30)
    if blend_pct < 5:
        blend_pct = 5
    if blend_pct > 100:
        blend_pct = 100
    if not bool(body.force) and conf < min_conf:
        return {"ok": True, "action": "insufficient_confidence", "confidence": float(conf), "min_confidence": float(min_conf), "suggestion": sug, "runtime": runtime}
    if bool(body.use_suggestion):
        old_fr = float(runtime.get("auto_release_adaptive_fail_ratio", 0.35) or 0.35)
        old_mul = int(runtime.get("auto_release_adaptive_multiplier_pct", 50) or 50)
        new_fr = float(sug.get("fail_ratio", 0.35) or 0.35)
        new_mul = int(sug.get("multiplier_pct", 50) or 50)
        if not bool(body.force):
            p = float(blend_pct) / 100.0
            new_fr = (old_fr * (1.0 - p)) + (new_fr * p)
            new_mul = int(round((old_mul * (1.0 - p)) + (new_mul * p)))
        upd["auto_release_adaptive_fail_ratio"] = float(new_fr)
        upd["auto_release_adaptive_multiplier_pct"] = int(new_mul)
    if body.fail_ratio is not None:
        v = float(body.fail_ratio)
        if v < 0:
            v = 0.0
        if v > 1:
            v = 1.0
        upd["auto_release_adaptive_fail_ratio"] = float(v)
    if body.multiplier_pct is not None:
        v = int(body.multiplier_pct)
        if v < 5:
            v = 5
        if v > 100:
            v = 100
        upd["auto_release_adaptive_multiplier_pct"] = int(v)
    if bool(body.use_suggestion):
        upd["adaptive_rollback_active"] = True
        upd["adaptive_rollback_applied_ts"] = int(datetime.now().timestamp())
        upd["adaptive_rollback_baseline_fail_ratio"] = float(runtime.get("last_auto_release_fail_ratio", 0.0) or 0.0)
        upd["adaptive_rollback_prev_fail_ratio"] = float(runtime.get("auto_release_adaptive_fail_ratio", 0.35) or 0.35)
        upd["adaptive_rollback_prev_multiplier_pct"] = int(runtime.get("auto_release_adaptive_multiplier_pct", 50) or 50)
    ts = int(datetime.now().timestamp())
    upd = _append_adaptive_apply_history(
        upd,
        ts=int(ts),
        force=bool(body.force),
        blend_pct=int(blend_pct),
        confidence=float(conf),
        applied_fail_ratio=float(upd.get("auto_release_adaptive_fail_ratio", 0.35) or 0.35),
        applied_multiplier_pct=int(upd.get("auto_release_adaptive_multiplier_pct", 50) or 50),
    )
    _write_ai_production_runtime(upd)
    return {
        "ok": True,
        "action": "applied",
        "applied": {
            "fail_ratio": float(upd.get("auto_release_adaptive_fail_ratio", 0.35) or 0.35),
            "multiplier_pct": int(upd.get("auto_release_adaptive_multiplier_pct", 50) or 50),
        },
        "apply_meta": {"force": bool(body.force), "blend_pct": int(blend_pct), "confidence": float(conf), "min_confidence": float(min_conf)},
        "suggestion": sug,
        "runtime": get_ai_production_runtime(current_user=current_user).model_dump(),
    }


@router.post("/ai-production/adaptive-rollback/check")
def check_ai_production_adaptive_rollback(
    body: AIProductionAdaptiveRollbackCheckIn,
    current_user: User = Depends(require_admin),
) -> Dict[str, Any]:
    cfg = _read_ai_production_runtime()
    upd, action = _maybe_apply_adaptive_rollback(cfg, force=bool(body.force))
    if action.get("action") == "rolled_back":
        _write_ai_production_runtime(upd)
    return {"ok": True, "action": action, "runtime": get_ai_production_runtime(current_user=current_user).model_dump()}


@router.post("/ai-production/guard")
def guard_ai_production(current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> Dict[str, Any]:
    cfg = get_ai_production_runtime(current_user=current_user).model_dump()
    if not bool(cfg.get("auto_hold_enabled", True)):
        return {"ok": True, "action": "disabled", "runtime": cfg}
    queued = int(
        db.query(func.count(AIJob.id))
        .filter(AIJob.status == "queued")
        .filter(AIJob.stage.in_(["dispatch_pending", "dispatch_failed", "dispatching"]))
        .scalar()
        or 0
    )
    thr = int(cfg.get("auto_hold_queue_threshold", 2000) or 2000)
    if queued < thr:
        return {"ok": True, "action": "ok", "queued": queued, "threshold": thr, "runtime": cfg}
    upd: Dict[str, Any] = dict(cfg)
    upd["dispatch_hold_enabled"] = True
    upd["dispatch_hold_reason"] = "queue_pressure_auto_hold"
    _write_ai_production_runtime(upd)
    return {
        "ok": True,
        "action": "hold_enabled",
        "queued": queued,
        "threshold": thr,
        "runtime": get_ai_production_runtime(current_user=current_user).model_dump(),
    }


@router.post("/ai-production/release-hold")
def release_ai_production_hold(
    body: AIProductionReleaseHoldIn,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    reason = str(body.reason or "manual_release").strip()[:120] or "manual_release"
    st = _release_dispatch_hold_jobs(db, limit=int(body.limit or 500), reason=reason)
    released = int(st.get("released", 0) or 0)
    scanned = int(st.get("scanned", 0) or 0)
    cfg = _read_ai_production_runtime()
    if bool(body.disable_hold):
        cfg["dispatch_hold_enabled"] = False
        cfg["dispatch_hold_reason"] = reason
        _write_ai_production_runtime(cfg)
    return {
        "ok": True,
        "released": int(released),
        "scanned": int(scanned),
        "disable_hold": bool(body.disable_hold),
        "runtime": get_ai_production_runtime(current_user=current_user).model_dump(),
    }


@router.get("/ai-production/backfill-missing-scripts/preview")
def preview_backfill_missing_scripts(
    limit: int = Query(500),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    return {"ok": True, "result": _run_backfill_missing_scripts(db, limit=int(limit or 500), dry_run=True)}


@router.post("/ai-production/backfill-missing-scripts/execute")
def execute_backfill_missing_scripts(
    body: AIBackfillMissingScriptsIn,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    phrase = str(getattr(body, "confirm_phrase", "") or "").strip()
    if phrase != "BACKFILL_AI_MISSING_SCRIPTS":
        raise HTTPException(status_code=400, detail="invalid_confirm_phrase")
    return {"ok": True, "result": _run_backfill_missing_scripts(db, limit=int(body.limit or 500), dry_run=False)}


@router.get("/ai-production/content-integrity-repair/preview")
def preview_content_integrity_repair(
    limit: int = Query(1000),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    return {"ok": True, "result": _run_content_integrity_repair(db, limit=int(limit or 1000), dry_run=True)}


@router.post("/ai-production/content-integrity-repair/execute")
def execute_content_integrity_repair(
    body: ContentIntegrityRepairIn,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    phrase = str(getattr(body, "confirm_phrase", "") or "").strip()
    if phrase != "CONTENT_INTEGRITY_REPAIR":
        raise HTTPException(status_code=400, detail="invalid_confirm_phrase")
    return {"ok": True, "result": _run_content_integrity_repair(db, limit=int(body.limit or 1000), dry_run=False)}


@router.get("/post-recovery/preview")
def preview_post_recovery(
    post_id: int = Query(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    return {"ok": True, "result": _build_post_recovery_preview(db, int(post_id))}


@router.post("/post-recovery/execute")
def execute_post_recovery(
    body: PostRecoveryExecuteIn,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _ = current_user
    phrase = str(getattr(body, "confirm_phrase", "") or "").strip()
    if phrase != "RECOVER_POST_BY_ID":
        raise HTTPException(status_code=400, detail="invalid_confirm_phrase")
    return {"ok": True, "result": _execute_post_recovery(db, int(body.post_id))}


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
