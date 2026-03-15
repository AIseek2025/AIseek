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

    u = "u" + urllib.parse.quote_plus("smoke_" + str(__import__("time").time_ns()))
    status, _, reg = http_json(
        "POST",
        f"{base}/api/v1/auth/register",
        {"username": u, "password": "pw", "email": None, "phone": None},
    )
    if status != 200:
        print("register_failed", status, reg)
        return 1
    uid = int(reg["id"])

    # 登录获取 token
    status, _, login_resp = http_json(
        "POST",
        f"{base}/api/v1/auth/login",
        {"username": u, "password": "pw"},
    )
    if status != 200:
        print("login_failed", status, login_resp)
        return 1
    token = login_resp.get("access_token", "")
    print(f"DEBUG: token={token[:20]}..." if token else "DEBUG: token is empty", file=sys.stderr)

    status, _, post = http_json(
        "POST",
        f"{base}/api/v1/posts/create",
        {"content": "hello", "post_type": "video", "user_id": uid, "custom_instructions": None, "category": None, "voice_style": None, "bgm_mood": None, "title": "t"},
        headers={"Authorization": f"Bearer {token}"} if token else {},
    )
    if status != 200:
        print("create_post_failed", status, post)
        return 2
    pid = int(post["id"])

    status, _, cb = http_json(
        "POST",
        f"{base}/api/v1/posts/callback",
        {
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
        },
        headers={"x-worker-secret": "m3pro_worker_2026"},
    )
    if status != 200:
        print("callback_failed", status, cb)
        return 3

    status, _, got = http_json("GET", f"{base}/api/v1/posts/{pid}?user_id={uid}")
    if status != 200:
        print("get_post_failed", status, got)
        return 4
    if got.get("status") != "done":
        print("post_not_done", got.get("status"))
        return 5
    if "master.m3u8" not in str(got.get("video_url") or ""):
        print("hls_not_updated", got.get("video_url"))
        return 6
    if "cdn.example.com" not in str(got.get("mp4_url") or ""):
        print("mp4_url_not_present", got.get("mp4_url"))
        return 6
    if "covers" not in str(got.get("cover_url") or ""):
        print("cover_not_present", got.get("cover_url"))
        return 7
    if int(got.get("duration") or 0) != 12:
        print("duration_not_present", got.get("duration"))
        return 8
    if int(got.get("video_width") or 0) != 720 or int(got.get("video_height") or 0) != 1280:
        print("video_size_not_present", got.get("video_width"), got.get("video_height"))
        return 9

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
