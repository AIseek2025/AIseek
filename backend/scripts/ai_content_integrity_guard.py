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


def _get(url: str, headers: dict | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = (r.read() or b"").decode("utf-8", "ignore")
            try:
                obj = json.loads(body or "{}")
            except Exception:
                obj = {"_raw": body[:4000]}
            return int(r.status), obj
    except urllib.error.HTTPError as e:
        body = (e.read() or b"").decode("utf-8", "ignore")
        try:
            obj = json.loads(body or "{}")
        except Exception:
            obj = {"_raw": body[:4000]}
        return int(e.code), obj


def _script_ok(ps: dict) -> bool:
    if not isinstance(ps, dict):
        return False
    scenes = ps.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        return False
    for s in scenes:
        if not isinstance(s, dict):
            return False
        nar = str(s.get("narration") or "").strip()
        sub = str(s.get("subtitle") or "").strip()
        if not nar or not sub:
            return False
    cov = ps.get("cover")
    if not isinstance(cov, dict):
        return False
    return True


def main() -> int:
    base = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1").rstrip("/")
    suf = f"{int(time.time())}{random.randint(1000,9999)}"
    user = f"integrity_{suf}"
    email = f"{user}@example.com"
    pw = "pass123456"

    s, _ = _post(f"{base}/api/v1/auth/register", {"username": user, "email": email, "password": pw, "display_name": user})
    if s not in {200, 201}:
        print("AI_CONTENT_INTEGRITY_GUARD_FAIL register")
        return 1
    s, login = _post(f"{base}/api/v1/auth/login", {"username": user, "password": pw})
    if s != 200:
        print("AI_CONTENT_INTEGRITY_GUARD_FAIL login")
        return 1
    uid = int(login.get("user_id") or login.get("id") or 0)
    tok = str(login.get("access_token") or "")
    if uid <= 0 or not tok:
        print("AI_CONTENT_INTEGRITY_GUARD_FAIL auth_payload")
        return 1
    hs = {"Authorization": f"Bearer {tok}"}

    s, create = _post(
        f"{base}/api/v1/ai/create",
        {"user_id": uid, "long_text": "完整性守卫：必须有字幕、封面、口播稿。", "prompt": "简洁清晰", "category": "科技"},
        hs,
    )
    if s != 200:
        print("AI_CONTENT_INTEGRITY_GUARD_FAIL create")
        return 1
    job_id = str(create.get("job_id") or "")
    post_id = int(create.get("post_id") or 0)
    if not job_id or post_id <= 0:
        print("AI_CONTENT_INTEGRITY_GUARD_FAIL create_payload")
        return 1

    status = {}
    for _ in range(30):
        time.sleep(2)
        ss, status = _get(f"{base}/api/v1/ai/status/{job_id}", hs)
        if ss == 200 and str(status.get("status") or "") in {"done", "failed", "cancelled"}:
            break
    if str(status.get("status") or "") != "done":
        print("AI_CONTENT_INTEGRITY_GUARD_FAIL ai_not_done")
        return 1
    ps_status = ((status.get("result") or {}).get("production_script") or {}) if isinstance(status.get("result"), dict) else {}
    if not _script_ok(ps_status):
        print("AI_CONTENT_INTEGRITY_GUARD_FAIL status_script")
        return 1

    sj, job = _get(f"{base}/api/v1/ai/jobs/{job_id}?user_id={uid}")
    if sj != 200:
        print("AI_CONTENT_INTEGRITY_GUARD_FAIL job_get")
        return 1
    ps_job = (job.get("production_script") or {}) if isinstance(job, dict) else {}
    if not _script_ok(ps_job):
        print("AI_CONTENT_INTEGRITY_GUARD_FAIL job_script")
        return 1

    sbp, by_post = _get(f"{base}/api/v1/ai/jobs/by_post/{post_id}?user_id={uid}")
    if sbp != 200 or not str((by_post or {}).get("job_id") or ""):
        print("AI_CONTENT_INTEGRITY_GUARD_FAIL by_post")
        return 1
    by_job_id = str((by_post or {}).get("job_id") or "")
    sbj, by_job = _get(f"{base}/api/v1/ai/jobs/{by_job_id}?user_id={uid}")
    if sbj != 200 or not _script_ok((by_job or {}).get("production_script") or {}):
        print("AI_CONTENT_INTEGRITY_GUARD_FAIL by_post_script")
        return 1

    sd, draft = _get(f"{base}/api/v1/ai/jobs/{job_id}/draft?user_id={uid}")
    if sd != 200 or not _script_ok((draft or {}).get("draft_json") or {}):
        print("AI_CONTENT_INTEGRITY_GUARD_FAIL draft_script")
        return 1

    scs, cs = _get(f"{base}/api/v1/debug/chain-status?post_id=78")
    probe = (cs or {}).get("probe") if isinstance(cs, dict) else {}
    if scs != 200 or int((probe or {}).get("result_scenes") or 0) <= 0:
        print("AI_CONTENT_INTEGRITY_GUARD_FAIL probe78")
        return 1

    out = {
        "job_id": job_id,
        "post_id": post_id,
        "status_scenes": len((ps_status or {}).get("scenes") or []),
        "job_scenes": len((ps_job or {}).get("scenes") or []),
        "by_post_job_id": by_job_id,
        "draft_scenes": len(((draft or {}).get("draft_json") or {}).get("scenes") or []),
        "probe78_result_scenes": int((probe or {}).get("result_scenes") or 0),
    }
    print(json.dumps(out, ensure_ascii=False))
    print("AI_CONTENT_INTEGRITY_GUARD_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
