import os
import signal
import subprocess
import sys
import time
import urllib.request as u
import importlib.util
import json


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


def _write_report(path: str, base: str, checks: list[dict], exit_code: int) -> None:
    obj = {
        "base": base,
        "exit_code": int(exit_code),
        "all_passed": bool(int(exit_code) == 0),
        "checks": checks,
        "ts": int(time.time()),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _write_summary(path: str, base: str, checks: list[dict], exit_code: int) -> None:
    total = len(checks or [])
    passed = len([c for c in (checks or []) if bool(c.get("ok"))])
    failed = len([c for c in (checks or []) if not bool(c.get("ok"))])
    failed_rows = [c for c in (checks or []) if not bool(c.get("ok"))]
    failed_names = ", ".join([str(c.get("name") or "") for c in failed_rows]) if failed_rows else "none"
    lines = [
        "# CI Guard Summary",
        "",
        f"- base: {base}",
        f"- exit_code: {int(exit_code)}",
        f"- all_passed: {'true' if int(exit_code) == 0 else 'false'}",
        f"- checks_total: {total}",
        f"- checks_passed: {passed}",
        f"- checks_failed: {failed}",
        f"- failed_checks: {failed_names}",
        "",
        "## Failures",
        "",
    ]
    if failed_rows:
        for c in failed_rows:
            lines.append(f"- {c.get('name','')}: returncode={c.get('returncode','')} status={c.get('status','')} skipped={'1' if c.get('skipped') else '0'}")
    else:
        lines.append("- none")
    lines.extend([
        "",
        "## Suggested Actions",
        "",
    ])
    if failed_rows:
        for c in failed_rows:
            name = str(c.get("name") or "")
            action = _suggest_action(name)
            lines.append(f"- {name}: {action}")
    else:
        lines.append("- none")
    lines.extend([
        "",
        "## Checks",
        "",
        "| check | ok | returncode | skipped | status |",
        "|---|---:|---:|---:|---:|",
    ])
    for c in checks or []:
        lines.append(
            f"| {c.get('name','')} | {'1' if c.get('ok') else '0'} | {c.get('returncode','')} | {'1' if c.get('skipped') else '0'} | {c.get('status','')} |"
        )
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _suggest_action(name: str) -> str:
    m = {
        "livez": "先检查 backend 启动日志与端口占用，再检查 main.py 启动参数。",
        "readyz": "检查数据库/Redis连通性与初始化迁移是否完成。",
        "metrics_status": "检查服务是否完整启动及 /metrics 路由是否被中间件拦截。",
        "metrics_key": "检查 Prometheus 指标注入逻辑与路由命名是否变更。",
        "interaction_smoke_test": "检查互动API鉴权、依赖服务与测试用户初始化。",
        "callback_smoke_test": "检查worker回调签名、secret配置和回调路由。",
        "worker_callback_alert_smoke_test": "检查告警阈值、回调错误链路和任务状态同步。",
        "search_card_observability_regression": "检查搜索卡片埋点字段、上报接口和Redis Stream。",
        "ai_pipeline_regression_guard": "检查AI关键函数签名与兜底逻辑是否被改动。",
        "ai_long_text_quality_regression": "检查字幕切分、质量评分与文本清洗规则。",
        "strict_probe_guard": "检查client_probe上报是否新鲜，确认双入口build/instance一致。",
        "ai_content_integrity_guard": "检查status/job/by_post/draft脚本兜底链路与cover字段。",
        "e2e_ui_smoke": "检查前端脚本加载链路、页面可交互性与Playwright环境。",
    }
    return m.get(name, "检查该步骤日志输出与最近改动文件，定位首个异常点。")


def _write_outputs(report_path: str, summary_path: str, base: str, checks: list[dict], exit_code: int) -> None:
    _write_report(report_path, base, checks, exit_code)
    _write_summary(summary_path, base, checks, exit_code)


def _run_check(cmd: list[str], env: dict, timeout: int, name: str, cwd: str = None) -> tuple[int, str]:
    import os
    # Use project root as working directory if not specified
    if cwd is None:
        cwd = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    p = subprocess.run(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # stderr already merged to stdout
        text=True,
        timeout=timeout,
        cwd=cwd,
    )
    output = str(p.stdout or "") + str(p.stderr or "")
    return int(p.returncode), output


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5002"
    base = base.rstrip("/")
    port = int(base.rsplit(":", 1)[-1]) if ":" in base else 5002

    env = os.environ.copy()
    env["PYTHONPATH"] = "backend"
    report_path = env.get("CI_GUARD_REPORT_PATH", "ci_guard_report.json")
    summary_path = env.get("CI_GUARD_SUMMARY_PATH", "ci_guard_summary.md")
    checks: list[dict] = []
    proc = subprocess.Popen(
        [sys.executable, "backend/app/main.py", "--port", str(port)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        ok = wait_ok(f"{base}/livez", timeout_sec=15.0)
        checks.append({"name": "livez", "ok": bool(ok)})
        if not ok:
            _write_outputs(report_path, summary_path, base, checks, 2)
            return 2

        s, _ = http_get(f"{base}/readyz")
        checks.append({"name": "readyz", "status": int(s), "ok": bool(s == 200)})
        if s != 200:
            _write_outputs(report_path, summary_path, base, checks, 3)
            return 3

        http_get(f"{base}/api/v1/posts/1")

        s, body = http_get(f"{base}/metrics")
        checks.append({"name": "metrics_status", "status": int(s), "ok": bool(s == 200)})
        if s != 200:
            _write_outputs(report_path, summary_path, base, checks, 4)
            return 4
        m_ok = b"/api/v1/posts/{post_id}" in body
        checks.append({"name": "metrics_key", "ok": bool(m_ok)})
        if not m_ok:
            _write_outputs(report_path, summary_path, base, checks, 5)
            return 5

        rc, out = _run_check([sys.executable, "backend/scripts/interaction_smoke_test.py", base], env, 90, "interaction_smoke_test")
        checks.append({"name": "interaction_smoke_test", "ok": bool(rc == 0), "returncode": int(rc)})
        if rc != 0:
            sys.stdout.write(out)
            _write_outputs(report_path, summary_path, base, checks, 6)
            return 6

        rc, out = _run_check([sys.executable, "backend/scripts/callback_smoke_test.py", base], env, 90, "callback_smoke_test")
        checks.append({"name": "callback_smoke_test", "ok": bool(rc == 0), "returncode": int(rc)})
        if rc != 0:
            sys.stdout.write(out)
            _write_outputs(report_path, summary_path, base, checks, 7)
            return 7

        rc, out = _run_check([sys.executable, "backend/scripts/worker_callback_alert_smoke_test.py", base], env, 90, "worker_callback_alert_smoke_test")
        checks.append({"name": "worker_callback_alert_smoke_test", "ok": bool(rc == 0), "returncode": int(rc)})
        if rc != 0:
            sys.stdout.write(out)
            _write_outputs(report_path, summary_path, base, checks, 8)
            return 8

        rc, out = _run_check([sys.executable, "backend/scripts/search_card_observability_regression.py"], env, 30, "search_card_observability_regression")
        checks.append({"name": "search_card_observability_regression", "ok": bool(rc == 0), "returncode": int(rc)})
        if rc != 0:
            sys.stdout.write(out)
            _write_outputs(report_path, summary_path, base, checks, 9)
            return 9

        rc, out = _run_check([sys.executable, "backend/scripts/ai_pipeline_regression_guard.py"], env, 30, "ai_pipeline_regression_guard")
        checks.append({"name": "ai_pipeline_regression_guard", "ok": bool(rc == 0), "returncode": int(rc)})
        if rc != 0:
            sys.stdout.write(out)
            _write_outputs(report_path, summary_path, base, checks, 10)
            return 10

        rc, out = _run_check([sys.executable, "backend/scripts/ai_long_text_quality_regression.py"], env, 30, "ai_long_text_quality_regression")
        checks.append({"name": "ai_long_text_quality_regression", "ok": bool(rc == 0), "returncode": int(rc)})
        if rc != 0:
            sys.stdout.write(out)
            _write_outputs(report_path, summary_path, base, checks, 11)
            return 11

        rc, out = _run_check([sys.executable, "backend/scripts/strict_probe_guard.py", base, "180"], env, 60, "strict_probe_guard")
        checks.append({"name": "strict_probe_guard", "ok": bool(rc == 0), "returncode": int(rc)})
        if rc != 0:
            sys.stdout.write(out)
            _write_outputs(report_path, summary_path, base, checks, 13)
            return 13

        rc, out = _run_check([sys.executable, "backend/scripts/ai_content_integrity_guard.py", base], env, 180, "ai_content_integrity_guard")
        checks.append({"name": "ai_content_integrity_guard", "ok": bool(rc == 0), "returncode": int(rc)})
        if rc != 0:
            sys.stdout.write(out)
            _write_outputs(report_path, summary_path, base, checks, 14)
            return 14

        if importlib.util.find_spec("playwright") is not None:
            rc, out = _run_check([sys.executable, "backend/scripts/e2e_ui_smoke.py", base], env, 240, "e2e_ui_smoke")
            checks.append({"name": "e2e_ui_smoke", "ok": bool(rc == 0), "returncode": int(rc)})
            if rc != 0:
                sys.stdout.write(out)
                _write_outputs(report_path, summary_path, base, checks, 12)
                return 12
        else:
            sys.stdout.write("SKIP_E2E_NO_PLAYWRIGHT\n")
            checks.append({"name": "e2e_ui_smoke", "ok": True, "skipped": True})

        _write_outputs(report_path, summary_path, base, checks, 0)
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
