import os
import signal
import subprocess
import sys
import time
import urllib.request as u
import importlib.util


def wait_ok(url: str, timeout_sec: float = 12.0) -> bool:
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            r = u.urlopen(url, timeout=1.5)
            if r.status == 200:
                return True
        except Exception:
            time.sleep(0.2)
    return False


def http_get(url: str) -> tuple[int, bytes]:
    try:
        r = u.urlopen(url, timeout=6)
        return r.status, r.read()
    except Exception:
        return 0, b""


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5002"
    base = base.rstrip("/")
    port = int(base.rsplit(":", 1)[-1]) if ":" in base else 5002

    env = os.environ.copy()
    env["PYTHONPATH"] = "backend"
    proc = subprocess.Popen(
        [sys.executable, "backend/app/main.py", "--port", str(port)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        if not wait_ok(f"{base}/livez", timeout_sec=15.0):
            return 2

        s, _ = http_get(f"{base}/readyz")
        if s != 200:
            return 3

        http_get(f"{base}/api/v1/posts/1")

        s, body = http_get(f"{base}/metrics")
        if s != 200:
            return 4
        if b"/api/v1/posts/{post_id}" not in body:
            return 5

        p = subprocess.run(
            [sys.executable, "backend/scripts/interaction_smoke_test.py", base],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=90,
        )
        if p.returncode != 0:
            sys.stdout.write(p.stdout)
            return 6

        p2 = subprocess.run(
            [sys.executable, "backend/scripts/callback_smoke_test.py", base],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=90,
        )
        if p2.returncode != 0:
            sys.stdout.write(p2.stdout)
            return 7

        p3 = subprocess.run(
            [sys.executable, "backend/scripts/worker_callback_alert_smoke_test.py", base],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=90,
        )
        if p3.returncode != 0:
            sys.stdout.write(p3.stdout)
            return 8

        if importlib.util.find_spec("playwright") is not None:
            p4 = subprocess.run(
                [sys.executable, "backend/scripts/e2e_ui_smoke.py", base],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=240,
            )
            if p4.returncode != 0:
                sys.stdout.write(p4.stdout)
                return 9
        else:
            sys.stdout.write("SKIP_E2E_NO_PLAYWRIGHT\n")

        return 0
    finally:
        try:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=6)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
