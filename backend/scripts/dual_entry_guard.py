import json
import sys
import urllib.request


def _get(url: str):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=20) as r:
        body = (r.read() or b"").decode("utf-8", "ignore")
        try:
            obj = json.loads(body or "{}")
        except Exception:
            obj = {"_raw": body[:4000]}
        return int(r.status), obj, dict(r.headers.items())


def main() -> int:
    a = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1").rstrip("/")
    b = (sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:5001").rstrip("/")
    max_probe_age = int(sys.argv[3]) if len(sys.argv) > 3 else -1

    a_s, a_obj, a_h = _get(f"{a}/api/v1/debug/chain-status?post_id=78")
    b_s, b_obj, b_h = _get(f"{b}/api/v1/debug/chain-status?post_id=78")
    if a_s != 200 or b_s != 200:
        print("DUAL_ENTRY_GUARD_FAIL status")
        return 1

    a_build = str((a_obj or {}).get("build_id", "") or "")
    b_build = str((b_obj or {}).get("build_id", "") or "")
    a_inst = str((a_obj or {}).get("instance_id", "") or "")
    b_inst = str((b_obj or {}).get("instance_id", "") or "")
    a_actions = str(((a_obj or {}).get("assets") or {}).get("actions_js", "") or "")
    b_actions = str(((b_obj or {}).get("assets") or {}).get("actions_js", "") or "")
    a_probe = (a_obj or {}).get("probe") or {}
    b_probe = (b_obj or {}).get("probe") or {}
    a_age = int((a_obj or {}).get("client_probe_age_sec") or 0)
    b_age = int((b_obj or {}).get("client_probe_age_sec") or 0)
    a_fresh = bool((a_obj or {}).get("client_probe_fresh"))
    b_fresh = bool((b_obj or {}).get("client_probe_fresh"))

    ok = (
        bool(a_build)
        and bool(b_build)
        and a_build == b_build
        and bool(a_inst)
        and bool(b_inst)
        and a_inst == b_inst
        and "/static/js/modules/actions.js" in a_actions
        and "/static/js/modules/actions.js" in b_actions
        and int((a_probe or {}).get("result_scenes") or 0) > 0
        and int((b_probe or {}).get("result_scenes") or 0) > 0
    )
    if max_probe_age >= 0:
        ok = ok and a_age <= max_probe_age and b_age <= max_probe_age and a_fresh and b_fresh

    out = {
        "a": a,
        "b": b,
        "build": a_build,
        "instance": a_inst,
        "probe_a": a_probe,
        "probe_b": b_probe,
        "actions_a": a_actions,
        "actions_b": b_actions,
        "client_probe_age_a": a_age,
        "client_probe_age_b": b_age,
        "client_probe_fresh_a": a_fresh,
        "client_probe_fresh_b": b_fresh,
        "max_probe_age": max_probe_age,
        "x_aiseek_build_a": str((a_h or {}).get("x-aiseek-build", "") or ""),
        "x_aiseek_build_b": str((b_h or {}).get("x-aiseek-build", "") or ""),
    }
    print(json.dumps(out, ensure_ascii=False))
    if not ok:
        print("DUAL_ENTRY_GUARD_FAIL invariant")
        return 1
    print("DUAL_ENTRY_GUARD_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
