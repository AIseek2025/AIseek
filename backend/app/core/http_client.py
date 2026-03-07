from __future__ import annotations

import hmac
import hashlib
import time
from typing import Any, Dict, Optional

from app.core.config import get_settings
from app.core.request_context import get_canary, get_request_id, get_session_id
from app.core.cache import cache

try:
    from prometheus_client import Counter

    HTTP_OUT_TOTAL = Counter(
        "aiseek_http_out_total",
        "Outbound HTTP attempts",
        ["service", "outcome"],
    )
except Exception:
    HTTP_OUT_TOTAL = None
_HTTP_SESSION = None


def build_outgoing_headers(
    extra: Optional[Dict[str, str]] = None,
    *,
    signed_method: Optional[str] = None,
    signed_path: Optional[str] = None,
) -> Dict[str, str]:
    h: Dict[str, str] = {}
    try:
        rid = get_request_id()
        if rid:
            h["x-request-id"] = str(rid)
    except Exception:
        pass
    try:
        sid = get_session_id()
        if sid:
            h["x-session-id"] = str(sid)
    except Exception:
        pass
    try:
        c = get_canary()
        if c is not None:
            h["x-canary"] = "1" if c else "0"
    except Exception:
        pass
    if extra:
        for k, v in extra.items():
            if v is None:
                continue
            h[str(k)] = str(v)
    try:
        s = get_settings()
        required = bool(getattr(s, "FEED_RECALL_SIGNED_REQUIRED", False)) or False
        secret = str(getattr(s, "FEED_RECALL_SHARED_SECRET", "") or "").strip()
        if required and secret and signed_method and signed_path:
            ts = str(int(time.time()))
            msg = f"{ts}\n{str(signed_method).upper()}\n{str(signed_path)}".encode("utf-8")
            sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
            h["x-aiseek-ts"] = ts
            h["x-aiseek-sig"] = sig
    except Exception:
        pass
    try:
        from opentelemetry.propagate import inject

        inject(h)
    except Exception:
        pass
    return h


def _metric(service: str, outcome: str) -> None:
    try:
        if HTTP_OUT_TOTAL is not None:
            HTTP_OUT_TOTAL.labels(str(service or "unknown"), str(outcome or "unknown")).inc()
    except Exception:
        pass


def _cb_key(service: str) -> str:
    return f"cb:http:{str(service or 'unknown')}"


def _cb_get(service: str) -> dict:
    obj = cache.get_json(_cb_key(service))
    return obj if isinstance(obj, dict) else {}


def _cb_set(service: str, obj: dict, ttl: int) -> None:
    cache.set_json(_cb_key(service), obj, ttl=ttl)


def _cb_is_open(service: str) -> bool:
    st = _cb_get(service)
    try:
        open_until = float(st.get("open_until") or 0)
    except Exception:
        open_until = 0
    return open_until > time.time()


def cb_state(service: str) -> dict:
    return _cb_get(service)


def cb_is_open(service: str) -> bool:
    return _cb_is_open(service)


def _cb_mark_success(service: str) -> None:
    try:
        _cb_set(service, {"fail": 0, "open_until": 0}, ttl=600)
    except Exception:
        pass


def _cb_mark_failure(service: str) -> None:
    s = get_settings()
    thr = int(getattr(s, "HTTP_OUTBOUND_CB_FAIL_THRESHOLD", 5) or 5)
    if thr < 1:
        thr = 1
    if thr > 50:
        thr = 50
    open_sec = int(getattr(s, "HTTP_OUTBOUND_CB_OPEN_SEC", 30) or 30)
    if open_sec < 1:
        open_sec = 1
    if open_sec > 600:
        open_sec = 600
    st = _cb_get(service)
    try:
        fail = int(st.get("fail") or 0) + 1
    except Exception:
        fail = 1
    open_until = float(st.get("open_until") or 0)
    if fail >= thr:
        open_until = time.time() + open_sec
    try:
        _cb_set(service, {"fail": fail, "open_until": open_until}, ttl=max(open_sec * 2, 120))
    except Exception:
        pass


def _get_http_session():
    global _HTTP_SESSION
    if _HTTP_SESSION is not None:
        return _HTTP_SESSION
    try:
        import requests
        from requests.adapters import HTTPAdapter

        s = get_settings()
        pool_conns = int(getattr(s, "HTTP_OUTBOUND_POOL_CONNECTIONS", 256) or 256)
        pool_max = int(getattr(s, "HTTP_OUTBOUND_POOL_MAXSIZE", 256) or 256)
        if pool_conns < 8:
            pool_conns = 8
        if pool_max < 8:
            pool_max = 8
        if pool_conns > 2048:
            pool_conns = 2048
        if pool_max > 2048:
            pool_max = 2048
        sess = requests.Session()
        ad = HTTPAdapter(pool_connections=pool_conns, pool_maxsize=pool_max)
        sess.mount("http://", ad)
        sess.mount("https://", ad)
        _HTTP_SESSION = sess
    except Exception:
        _HTTP_SESSION = False
    return _HTTP_SESSION


def http_get_json(
    url: str,
    *,
    service: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: Optional[float] = None,
    retries: Optional[int] = None,
) -> Optional[Any]:
    u = str(url or "").strip()
    if not u:
        _metric(service, "bad_url")
        return None
    if _cb_is_open(service):
        _metric(service, "circuit_open")
        return None
    s = get_settings()
    to = float(timeout if timeout is not None else getattr(s, "HTTP_OUTBOUND_TIMEOUT_SEC", 0.6) or 0.6)
    if to < 0.05:
        to = 0.05
    if to > 20:
        to = 20
    att = int(retries if retries is not None else getattr(s, "HTTP_OUTBOUND_RETRIES", 1) or 1)
    if att < 0:
        att = 0
    if att > 5:
        att = 5
    backoff = float(getattr(s, "HTTP_OUTBOUND_RETRY_BACKOFF_SEC", 0.0) or 0.0)
    if backoff < 0:
        backoff = 0.0
    if backoff > 1.0:
        backoff = 1.0
    last_err: Optional[str] = None
    sess = _get_http_session()
    for i in range(att + 1):
        try:
            if sess:
                resp = sess.get(u, params=params, headers=headers, timeout=to)
            else:
                import requests
                resp = requests.get(u, params=params, headers=headers, timeout=to)
            code = int(getattr(resp, "status_code", 0) or 0)
            if code >= 500:
                last_err = f"http_{code}"
                raise RuntimeError(last_err)
            if code != 200:
                _cb_mark_failure(service)
                _metric(service, f"bad_status_{code}")
                return None
            try:
                data = resp.json()
            except Exception:
                _cb_mark_failure(service)
                _metric(service, "bad_json")
                return None
            _cb_mark_success(service)
            _metric(service, "ok")
            return data
        except Exception as e:
            last_err = str(e) or last_err
            if i < att:
                if backoff > 0:
                    time.sleep(backoff * (i + 1))
                continue
            _cb_mark_failure(service)
            _metric(service, "error")
            return None
    _cb_mark_failure(service)
    _metric(service, "error")
    return None
