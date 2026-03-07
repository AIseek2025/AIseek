import json
import sys
import time
import random
from typing import Optional, Dict
import urllib.error
import urllib.parse
import urllib.request


def http_get(url: str, headers: Optional[Dict[str, str]] = None):
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=6) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def http_post_json(url: str, payload: dict, headers: Optional[Dict[str, str]] = None):
    data = json.dumps(payload).encode("utf-8")
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(
        url, data=data, headers=h, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=6) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def must_json(b: bytes):
    return json.loads(b.decode("utf-8", "ignore") or "{}")


def auth_register(base: str, username: str, password: str) -> None:
    http_post_json(f"{base}/api/v1/auth/register", {"username": username, "password": password})


def auth_login(base: str, username: str, password: str) -> tuple[int, str]:
    s, _, b = http_post_json(f"{base}/api/v1/auth/login", {"username": username, "password": password})
    if s != 200:
        raise RuntimeError(f"login_failed {s}")
    data = must_json(b)
    return int(data["user_id"]), str(data["access_token"])


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5002"
    base = base.rstrip("/")

    failures = []

    s, h, body = http_get(f"{base}/")
    if s != 200:
        failures.append(f"GET / => {s}")
    build = h.get("x-aiseek-build")
    if not build:
        failures.append("missing x-aiseek-build")

    uid1 = 0
    uid2 = 0
    tok1 = ""
    auth_h1 = {}
    try:
        suf = f"{int(time.time())}_{random.randint(1000, 9999)}"
        pw = f"pw_{suf}"
        for i in range(5):
            u1 = f"smoke_u1_{suf}_{i}"
            u2 = f"smoke_u2_{suf}_{i}"
            auth_register(base, u1, pw)
            auth_register(base, u2, pw)
            try:
                uid1, tok1 = auth_login(base, u1, pw)
                uid2, _tok2 = auth_login(base, u2, pw)
                break
            except Exception:
                uid1, uid2, tok1 = 0, 0, ""
        if uid1 and tok1:
            auth_h1 = {"Authorization": f"Bearer {tok1}"}
        else:
            failures.append("failed to create smoke users")
    except Exception as e:
        failures.append(f"failed to create smoke users: {e}")

    pid = 1
    try:
        s, _, b = http_get(f"{base}/api/v1/posts/feed?limit=1")
        if s == 200:
            arr = must_json(b)
            if isinstance(arr, list) and arr and int(arr[0].get("id") or 0) > 0:
                pid = int(arr[0]["id"])
    except Exception:
        pid = 1

    if uid1 and tok1:
        s, _, _ = http_post_json(f"{base}/api/v1/interaction/history", {"post_id": pid, "user_id": uid1}, headers=auth_h1)
        if s != 200:
            failures.append(f"POST /api/v1/interaction/history => {s}")

        s, _, _ = http_post_json(f"{base}/api/v1/interaction/history", {"post_id": pid, "user_id": uid1}, headers=auth_h1)
        if s != 200:
            failures.append(f"POST /api/v1/interaction/history (dup) => {s}")

        s, _, b = http_get(f"{base}/api/v1/interaction/history/{uid1}")
        if s != 200:
            failures.append(f"GET /api/v1/interaction/history/{uid1} => {s}")
        else:
            try:
                arr = json.loads(b.decode("utf-8", "ignore"))
                if not isinstance(arr, list):
                    failures.append("history payload not list")
            except Exception:
                failures.append("history payload invalid json")

        s, _, b = http_post_json(f"{base}/api/v1/interaction/like", {"post_id": pid, "user_id": uid1}, headers=auth_h1)
        if s != 200:
            failures.append(f"POST /api/v1/interaction/like => {s}")
        else:
            try:
                data = json.loads(b.decode("utf-8", "ignore"))
                if data.get("status") not in ("liked", "unliked"):
                    failures.append("like status invalid")
            except Exception:
                failures.append("like payload invalid json")

        s, _, b = http_post_json(f"{base}/api/v1/interaction/favorite", {"post_id": pid, "user_id": uid1}, headers=auth_h1)
        if s != 200:
            failures.append(f"POST /api/v1/interaction/favorite => {s}")
        else:
            try:
                data = json.loads(b.decode("utf-8", "ignore"))
                if data.get("status") not in ("favorited", "unfavorited"):
                    failures.append("favorite status invalid")
            except Exception:
                failures.append("favorite payload invalid json")

        if uid2 and uid2 != uid1:
            s, _, b = http_post_json(f"{base}/api/v1/users/follow", {"user_id": uid1, "target_id": uid2}, headers=auth_h1)
            if s != 200:
                failures.append(f"POST /api/v1/users/follow => {s}")
            else:
                try:
                    data = json.loads(b.decode("utf-8", "ignore"))
                    if data.get("message") not in ("Followed", "Unfollowed"):
                        failures.append("follow message invalid")
                except Exception:
                    failures.append("follow payload invalid json")

            s, _, b = http_get(f"{base}/api/v1/users/profile/{uid2}?current_user_id={uid1}")
            if s != 200:
                failures.append(f"GET /api/v1/users/profile/{uid2} => {s}")
            else:
                try:
                    data = json.loads(b.decode("utf-8", "ignore"))
                    if "is_following" not in data:
                        failures.append("profile is_following missing")
                except Exception:
                    failures.append("profile payload invalid json")

        q = urllib.parse.quote("test")
        s, _, _ = http_get(f"{base}/api/v1/posts/search?query={q}&user_id={uid1}")
        if s != 200:
            failures.append(f"GET /api/v1/posts/search => {s}")

        s, _, b = http_post_json(f"{base}/api/v1/users/update-profile", {"user_id": uid1, "nickname": "smoke_nick"}, headers=auth_h1)
        if s != 200:
            failures.append(f"POST /api/v1/users/update-profile => {s}")
        else:
            try:
                data = must_json(b)
                if data.get("status") != "ok":
                    failures.append("update-profile status not ok")
            except Exception:
                failures.append("update-profile payload invalid json")

        s, _, b = http_get(f"{base}/api/v1/users/profile/{uid1}?current_user_id={uid2}")
        if s != 200:
            failures.append(f"GET /api/v1/users/profile/{uid1} => {s}")
        else:
            try:
                data = must_json(b)
                u = data.get("user") or {}
                if isinstance(u, dict) and "reputation_score" in u:
                    failures.append("reputation_score should be hidden for non-owner")
            except Exception:
                failures.append("profile payload invalid json (privacy)")

        s, _, b = http_post_json(
            f"{base}/api/v1/messages/send",
            {"sender_id": uid1, "receiver_id": uid2, "content": "hello"},
            headers=auth_h1,
        )
        if s != 200:
            failures.append(f"POST /api/v1/messages/send => {s}")
        else:
            try:
                msg = must_json(b)
                if int(msg.get("sender_id") or 0) != uid1:
                    failures.append("dm sender_id mismatch")
            except Exception:
                failures.append("dm send payload invalid json")

        s, _, b = http_get(f"{base}/api/v1/messages/list?user_id={uid1}&other_id={uid2}", headers=auth_h1)
        if s != 200:
            failures.append(f"GET /api/v1/messages/list => {s}")
        else:
            try:
                arr = must_json(b)
                if not isinstance(arr, list):
                    failures.append("dm list payload not list")
            except Exception:
                failures.append("dm list payload invalid json")

        s2, _, _ = http_post_json(
            f"{base}/api/v1/interaction/comment",
            {"post_id": pid, "user_id": uid1, "content": "smoke comment"},
            headers=auth_h1,
        )
        if s2 != 200:
            failures.append(f"POST /api/v1/interaction/comment => {s2}")
        else:
            s3, _, b3 = http_get(f"{base}/api/v1/interaction/comments/{pid}?limit=1")
            if s3 != 200:
                failures.append(f"GET /api/v1/interaction/comments => {s3}")
            else:
                try:
                    carr = must_json(b3)
                    if isinstance(carr, list) and carr:
                        ts = float(carr[0].get("created_at") or 0)
                        if ts and abs(time.time() - ts) > 180:
                            failures.append("comment created_at drift too large")
                except Exception:
                    failures.append("comments payload invalid json")

    s, _, b = http_get(f"{base}/api/v1/posts/{pid}?user_id={uid1 or 1}")
    if s != 200:
        failures.append(f"GET /api/v1/posts/{pid}?user_id => {s}")
    else:
        try:
            p = json.loads(b.decode("utf-8", "ignore"))
            if "is_liked" not in p or "is_favorited" not in p or "is_following" not in p:
                failures.append("post flags missing")
        except Exception:
            failures.append("post payload invalid json")

    if uid1:
        s, h, _ = http_get(f"{base}/api/v1/users/{uid1}/following?limit=2")
        if s != 200:
            failures.append(f"GET /api/v1/users/{uid1}/following => {s}")
        if h.get("x-total-count") is None:
            failures.append("missing x-total-count for following")

        s, h, _ = http_get(f"{base}/api/v1/users/{uid1}/followers?limit=2")
        if s != 200:
            failures.append(f"GET /api/v1/users/{uid1}/followers => {s}")
        if h.get("x-total-count") is None:
            failures.append("missing x-total-count for followers")

        s, h, _ = http_get(f"{base}/api/v1/interaction/likes/{uid1}?limit=2")
        if s != 200:
            failures.append(f"GET /api/v1/interaction/likes/{uid1} => {s}")
        if h.get("x-total-count") is None:
            failures.append("missing x-total-count for likes")

        s, h, _ = http_get(f"{base}/api/v1/interaction/favorites/{uid1}?limit=2")
        if s != 200:
            failures.append(f"GET /api/v1/interaction/favorites/{uid1} => {s}")
        if h.get("x-total-count") is None:
            failures.append("missing x-total-count for favorites")

        s, h, _ = http_get(f"{base}/api/v1/interaction/history/{uid1}?limit=2")
        if s != 200:
            failures.append(f"GET /api/v1/interaction/history/{uid1} => {s}")
        if h.get("x-total-count") is None:
            failures.append("missing x-total-count for history")

    if failures:
        print("FAIL")
        for f in failures:
            print("-", f)
        sys.exit(1)

    print("OK")
    print("build:", build)


if __name__ == "__main__":
    main()
