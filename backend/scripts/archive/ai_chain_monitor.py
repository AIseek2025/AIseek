import json
import random
import sys
import time
import urllib.error
import urllib.request


def _post(url: str, payload: dict, headers: dict | None = None) -> tuple[int, dict]:
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return int(r.status), json.loads((r.read() or b"{}").decode("utf-8", "ignore") or "{}")
    except urllib.error.HTTPError as e:
        return int(e.code), json.loads((e.read() or b"{}").decode("utf-8", "ignore") or "{}")


def _get(url: str, headers: dict | None = None) -> tuple[int, dict, dict]:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = (r.read() or b"").decode("utf-8", "ignore")
            try:
                obj = json.loads(body or "{}")
            except Exception:
                obj = {"_raw": body[:20000]}
            return int(r.status), obj, dict(r.headers.items())
    except urllib.error.HTTPError as e:
        body = (e.read() or b"").decode("utf-8", "ignore")
        try:
            obj = json.loads(body or "{}")
        except Exception:
            obj = {"_raw": body[:20000]}
        return int(e.code), obj, dict(e.headers.items() if e.headers else [])


def main() -> int:
    base = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1").rstrip("/")
    suf = f"{int(time.time())}{random.randint(1000,9999)}"
    user = f"mon_{suf}"
    pw = "pass123456"
    email = f"{user}@example.com"

    reg_s, _ = _post(f"{base}/api/v1/auth/register", {"username": user, "email": email, "password": pw, "display_name": user})
    if reg_s not in {200, 201}:
        print("CHAIN_MONITOR_FAIL register")
        return 1

    login_s, login = _post(f"{base}/api/v1/auth/login", {"username": user, "password": pw})
    if login_s != 200:
        print("CHAIN_MONITOR_FAIL login")
        return 1

    uid = int(login.get("user_id") or login.get("id") or 0)
    tok = str(login.get("access_token") or "")
    if not uid or not tok:
        print("CHAIN_MONITOR_FAIL auth_payload")
        return 1

    hs = {"Authorization": f"Bearer {tok}"}
    c_s, create = _post(
        f"{base}/api/v1/ai/create",
        {"user_id": uid, "long_text": "自动链路监测：应有字幕封面口播稿。", "prompt": "简洁", "category": "科技"},
        hs,
    )
    if c_s != 200:
        print("CHAIN_MONITOR_FAIL create")
        return 1

    job_id = str(create.get("job_id") or "")
    post_id = int(create.get("post_id") or 0)
    if not job_id or post_id <= 0:
        print("CHAIN_MONITOR_FAIL create_payload")
        return 1

    status = {}
    for _ in range(25):
        time.sleep(2)
        s_s, status, _ = _get(f"{base}/api/v1/ai/status/{job_id}", hs)
        if s_s == 200 and str(status.get("status") or "") in {"done", "failed", "cancelled"}:
            break

    if str(status.get("status") or "") != "done":
        print("CHAIN_MONITOR_FAIL ai_not_done")
        return 1

    ps = (status.get("result") or {}).get("production_script") if isinstance(status.get("result"), dict) else None
    result_scenes = len((ps or {}).get("scenes") or []) if isinstance(ps, dict) else 0

    p_s, posts, _ = _get(f"{base}/api/v1/posts/user/{uid}?viewer_id={uid}&limit=1", hs)
    if p_s != 200 or not isinstance(posts, list) or not posts:
        print("CHAIN_MONITOR_FAIL posts_list")
        return 1
    list_job_id = str((posts[0] or {}).get("ai_job_id") or "")

    bp_s, by_post, _ = _get(f"{base}/api/v1/ai/jobs/by_post/{post_id}?user_id={uid+9999}", hs)
    dj_s, draft, _ = _get(f"{base}/api/v1/ai/jobs/{job_id}/draft?user_id={uid+9999}", hs)
    gj_s, gjob, _ = _get(f"{base}/api/v1/ai/jobs/{job_id}?user_id={uid+9999}", hs)
    idx_s, _, idx_h = _get(f"{base}/")
    stu_s, _, stu_h = _get(f"{base}/studio")
    idx_build = str((idx_h or {}).get("x-aiseek-build", "") or "")
    stu_build = str((stu_h or {}).get("x-aiseek-build", "") or "")
    idx_inst = str((idx_h or {}).get("x-aiseek-instance", "") or "")
    stu_inst = str((stu_h or {}).get("x-aiseek-instance", "") or "")
    idx_actions = str((idx_h or {}).get("x-chain-actions-js", "") or "")
    stu_actions = str((stu_h or {}).get("x-chain-actions-js", "") or "")
    m_s, m_obj, _ = _get(f"{base}/static/js/main.js?v={idx_build}")
    main_ok = m_s == 200 and "forceGlobalSelectable" in str((m_obj or {}).get("_raw", "") or "")
    a_s, a_obj, _ = _get(f"{base}/static/js/modules/actions.js?v={idx_build}")
    actions_ok = a_s == 200 and "allowSelection" in str((a_obj or {}).get("_raw", "") or "")
    draft_scenes = len(((draft or {}).get("draft_json") or {}).get("scenes") or []) if isinstance((draft or {}).get("draft_json"), dict) else 0
    get_job_scenes = len(((gjob or {}).get("production_script") or {}).get("scenes") or []) if isinstance((gjob or {}).get("production_script"), dict) else 0

    ok = (
        result_scenes > 0
        and bool(list_job_id)
        and bp_s == 200
        and bool((by_post or {}).get("job_id"))
        and dj_s == 200
        and draft_scenes > 0
        and gj_s == 200
        and get_job_scenes > 0
        and idx_s == 200
        and stu_s == 200
        and bool(idx_build)
        and bool(stu_build)
        and bool(idx_inst)
        and bool(stu_inst)
        and idx_inst == stu_inst
        and bool(idx_actions)
        and bool(stu_actions)
        and "/static/js/modules/actions.js" in idx_actions
        and "/static/js/modules/actions.js" in stu_actions
        and bool(main_ok)
        and bool(actions_ok)
    )

    summary = {
        "job_id": job_id,
        "post_id": post_id,
        "result_scenes": result_scenes,
        "list_job_id": list_job_id,
        "by_post_job_id": (by_post or {}).get("job_id"),
        "draft_scenes": draft_scenes,
        "get_job_scenes": get_job_scenes,
        "idx_build": idx_build,
        "stu_build": stu_build,
        "instance": idx_inst,
        "actions_ok": bool(actions_ok),
    }
    print(json.dumps(summary, ensure_ascii=False))
    if not ok:
        print("CHAIN_MONITOR_FAIL invariant")
        return 1
    print("CHAIN_MONITOR_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
