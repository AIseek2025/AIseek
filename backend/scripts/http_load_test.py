import json
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


def http_get(url: str):
    req = urllib.request.Request(url, method="GET")
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            r.read()
            return r.status, (time.time() - start)
    except urllib.error.HTTPError as e:
        try:
            e.read()
        except Exception:
            pass
        return e.code, (time.time() - start)
    except Exception:
        return 0, (time.time() - start)


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5002"
    base = base.rstrip("/")
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    total = int(sys.argv[3]) if len(sys.argv) > 3 else 200

    urls = [
        f"{base}/api/v1/posts/feed?limit=20&user_id=1",
        f"{base}/api/v1/posts/search?query={urllib.parse.quote('test')}&user_id=1",
        f"{base}/api/v1/users/1/followers?limit=50",
    ]

    lock = threading.Lock()
    idx = 0
    ok = 0
    bad = 0
    lat = []

    def worker():
        nonlocal idx, ok, bad
        while True:
            with lock:
                if idx >= total:
                    return
                j = idx
                idx += 1
            url = urls[j % len(urls)]
            status, dt = http_get(url)
            with lock:
                lat.append(dt)
                if status == 200:
                    ok += 1
                else:
                    bad += 1

    ts = time.time()
    threads = [threading.Thread(target=worker, daemon=True) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    dur = max(0.001, time.time() - ts)

    lat_sorted = sorted(lat)
    p50 = lat_sorted[int(len(lat_sorted) * 0.50)] if lat_sorted else 0.0
    p90 = lat_sorted[int(len(lat_sorted) * 0.90)] if lat_sorted else 0.0
    p99 = lat_sorted[int(len(lat_sorted) * 0.99)] if lat_sorted else 0.0

    out = {
        "workers": workers,
        "total": total,
        "ok": ok,
        "bad": bad,
        "rps": total / dur,
        "p50_ms": round(p50 * 1000, 2),
        "p90_ms": round(p90 * 1000, 2),
        "p99_ms": round(p99 * 1000, 2),
    }
    print(json.dumps(out, ensure_ascii=False))

    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
