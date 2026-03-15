import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List


def _get_json(url: str, timeout: int = 8) -> Dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        raw = r.read().decode("utf-8", errors="ignore")
    try:
        return json.loads(raw)
    except Exception:
        return {"_raw": raw}


def _head_status(url: str, timeout: int = 8) -> int:
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return int(getattr(r, "status", 0) or 0)


def _resource_ok(base: str, path_or_url: str) -> bool:
    if not path_or_url:
        return False
    u = path_or_url if str(path_or_url).startswith("http") else f"{base}{path_or_url}"
    try:
        return _head_status(u) == 200
    except Exception:
        return False


def _job_probe(base: str, post_id: int) -> Dict[str, Any]:
    by_post = _get_json(f"{base}/api/v1/ai/jobs/by_post/{int(post_id)}")
    jid = str(by_post.get("job_id") or "")
    if not jid:
        return {"job_id": None, "ok": False, "reason": "job_id_missing"}
    j = _get_json(f"{base}/api/v1/ai/jobs/{jid}")
    ps = j.get("production_script") if isinstance(j, dict) else {}
    ps = ps if isinstance(ps, dict) else {}
    scenes = ps.get("scenes") if isinstance(ps.get("scenes"), list) else []
    narr_all = all(bool(str((s or {}).get("narration") or "").strip()) for s in scenes if isinstance(s, dict)) if scenes else False
    sub_all = all(bool(str((s or {}).get("subtitle") or "").strip()) for s in scenes if isinstance(s, dict)) if scenes else False
    cover_ok = bool(ps.get("cover"))
    ok = bool(str(j.get("status") or "") == "done" and len(scenes) > 0 and narr_all and sub_all and cover_ok)
    return {
        "job_id": jid,
        "job_status": j.get("status"),
        "scenes": int(len(scenes)),
        "narr_all": bool(narr_all),
        "sub_all": bool(sub_all),
        "script_cover": bool(cover_ok),
        "ok": bool(ok),
    }


def _post_probe(base: str, post_id: int) -> Dict[str, Any]:
    p = _get_json(f"{base}/api/v1/posts/{int(post_id)}")
    if p.get("detail"):
        return {"post_id": int(post_id), "ok": False, "reason": str(p.get("detail"))}
    tracks = p.get("subtitle_tracks") if isinstance(p.get("subtitle_tracks"), list) else []
    subtitle_url = str((tracks[0] or {}).get("url") or "") if tracks else ""
    cover_url = str(p.get("cover_url") or "")
    video_url = str(p.get("video_url") or "")
    cover_res = _resource_ok(base, cover_url)
    video_res = _resource_ok(base, video_url)
    sub_res = _resource_ok(base, subtitle_url) if subtitle_url else False
    job = _job_probe(base, int(post_id))
    ok = bool(
        str(p.get("status") or "") == "done"
        and bool(cover_url)
        and bool(video_url)
        and len(tracks) > 0
        and cover_res
        and video_res
        and sub_res
        and bool(job.get("ok"))
    )
    return {
        "post_id": int(post_id),
        "status": p.get("status"),
        "ai_job_id": p.get("ai_job_id"),
        "cover_url": bool(cover_url),
        "video_url": bool(video_url),
        "subtitle_tracks": int(len(tracks)),
        "resource_cover_200": bool(cover_res),
        "resource_video_200": bool(video_res),
        "resource_subtitle_200": bool(sub_res),
        "job": job,
        "ok": bool(ok),
    }


def run_once(base: str, post_ids: List[int]) -> int:
    rows = []
    all_ok = True
    for pid in post_ids:
        r = _post_probe(base, int(pid))
        rows.append(r)
        all_ok = all_ok and bool(r.get("ok"))
    out = {
        "base": base,
        "post_ids": [int(x) for x in post_ids],
        "all_ok": bool(all_ok),
        "items": rows,
        "ts": int(time.time()),
    }
    print(json.dumps(out, ensure_ascii=False))
    print("POST_CONTENT_PROBE_OK" if all_ok else "POST_CONTENT_PROBE_FAIL")
    return 0 if all_ok else 2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1")
    ap.add_argument("--post-ids", default="77,80")
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--interval-sec", type=int, default=8)
    args = ap.parse_args()

    ids = []
    for x in str(args.post_ids or "").split(","):
        x = str(x or "").strip()
        if not x:
            continue
        ids.append(int(x))
    if not ids:
        print("POST_CONTENT_PROBE_FAIL")
        print("no_post_ids")
        return 1

    if not args.watch:
        return run_once(str(args.base), ids)

    interval = max(2, int(args.interval_sec or 8))
    while True:
        code = run_once(str(args.base), ids)
        sys.stdout.flush()
        if code == 0:
            time.sleep(interval)
        else:
            time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
