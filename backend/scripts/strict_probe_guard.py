import json
import subprocess
import sys
import urllib.parse
import urllib.request


def _get(url: str) -> tuple[int, dict]:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=20) as r:
        body = (r.read() or b"").decode("utf-8", "ignore")
        try:
            obj = json.loads(body or "{}")
        except Exception:
            obj = {"_raw": body[:4000]}
        return int(r.status), obj


def main() -> int:
    base = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5002").rstrip("/")
    max_age = int(sys.argv[2]) if len(sys.argv) > 2 else 180
    q = urllib.parse.urlencode(
        {
            "page": "strict_guard",
            "build": "ci",
            "entry": "auto",
            "href": "ci",
            "sel_ok": "true",
            "sel_len": "10",
            "probe_ps": "1",
            "probe_exist": "1",
            "actions_js": "/static/js/modules/actions.js",
            "pd_blocked": "0",
            "md_blocked": "0",
            "ss_blocked": "0",
        }
    )
    _get(f"{base}/api/v1/debug/client-probe/ping?{q}")
    p = subprocess.run(
        [
            sys.executable,
            "backend/scripts/dual_entry_guard.py",
            base,
            base,
            str(max_age),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=40,
    )
    sys.stdout.write(p.stdout or "")
    return int(p.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
