import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional, Dict


def http_json(method: str, url: str, payload: Optional[dict] = None, headers: Optional[Dict[str, str]] = None):
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    h = {"content-type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read()
            return r.status, r.headers, json.loads(raw.decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            obj = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            obj = {"raw": raw[:200].decode("utf-8", errors="ignore")}
        return e.code, e.headers, obj


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5002"
    base = base.rstrip("/")

    status, _, login = http_json("POST", f"{base}/api/v1/auth/login", {"username": "admin", "password": "admin123"})
    if status != 200:
        print("admin_login_failed", status, login)
        return 1
    token = str(login.get("access_token") or "")
    if not token:
        print("no_token")
        return 2

    status, _, th = http_json("GET", f"{base}/api/v1/posts/admin/metrics/worker-callback/thresholds", headers={"authorization": f"Bearer {token}"})
    if status != 200:
        print("get_thresholds_failed", status, th)
        return 3

    u = "u" + urllib.parse.quote_plus("smoke_" + str(__import__("time").time_ns()))
    status, _, reg = http_json("POST", f"{base}/api/v1/auth/register", {"username": u, "password": "pw", "email": None, "phone": None})
    if status != 200:
        print("register_failed", status, reg)
        return 4
    uid = int(reg["id"])

    status, _, post = http_json(
        "POST",
        f"{base}/api/v1/posts/create",
        {"content": "hello", "post_type": "video", "user_id": uid, "custom_instructions": None, "category": None, "voice_style": None, "bgm_mood": None, "title": "t"},
    )
    if status != 200:
        print("create_post_failed", status, post)
        return 5
    pid = int(post["id"])

    payload = {
        "job_id": str(pid),
        "status": "done",
        "video_url": "https://cdn.example.com/hls/x/master.m3u8",
        "mp4_url": "https://cdn.example.com/videos/x.mp4",
        "cover_url": "https://cdn.example.com/covers/x.webp",
        "duration": 12,
        "video_width": 720,
        "video_height": 1280,
        "images": None,
        "error": None,
        "title": "t2",
        "summary": "s",
    }
    headers = {"x-worker-secret": "m3pro_worker_2026"}
    status, _, cb = http_json("POST", f"{base}/api/v1/posts/callback", payload, headers=headers)
    if status != 200:
        print("callback_failed", status, cb)
        return 6
    for _ in range(7):
        http_json("POST", f"{base}/api/v1/posts/callback", payload, headers=headers)

    status, _, alerts = http_json(
        "GET",
        f"{base}/api/v1/posts/admin/metrics/worker-callback/alerts?days=1&limit=50&include_acked=true",
        headers={"authorization": f"Bearer {token}"},
    )
    if status != 200:
        print("get_alerts_failed", status, alerts)
        return 7

    items = alerts.get("items") if isinstance(alerts, dict) else None
    if not isinstance(items, list) or not items:
        print("SKIP_NO_ALERTS")
        return 0

    first = items[0] if isinstance(items[0], dict) else {}
    day = str(first.get("day") or "").strip()
    aid = str(first.get("id") or "").strip()
    if day and aid:
        status, _, ack = http_json(
            "POST",
            f"{base}/api/v1/posts/admin/metrics/worker-callback/alerts/{urllib.parse.quote_plus(day)}/{urllib.parse.quote_plus(aid)}/ack",
            payload={},
            headers={"authorization": f"Bearer {token}"},
        )
        if status != 200:
            print("ack_failed", status, ack)
            return 8

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
