import json
import random
import sys
import time
from typing import Optional, Dict, Tuple
import urllib.error
import urllib.request


def _http_post_json(url: str, payload: dict, headers: Optional[Dict] = None) -> Tuple[int, bytes]:
    data = json.dumps(payload).encode("utf-8")
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _http_get(url: str, headers: Optional[Dict] = None) -> Tuple[int, bytes]:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _must_json(b: bytes):
    return json.loads(b.decode("utf-8", "ignore") or "{}")

def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _register(base: str, username: str, password: str) -> None:
    _http_post_json(f"{base}/api/v1/auth/register", {"username": username, "password": password})


def _login(base: str, username: str, password: str) -> tuple[int, str]:
    s, b = _http_post_json(f"{base}/api/v1/auth/login", {"username": username, "password": password})
    if s != 200:
        raise RuntimeError(f"login_failed {s}")
    data = _must_json(b)
    return int(data["user_id"]), str(data["access_token"])


def _create_image_post(base: str, token: str, user_id: int, title: str) -> int:
    payload = {
        "user_id": user_id,
        "post_type": "image_text",
        "title": title,
        "content": "",
        "images": ["img/default_bg.svg"],
    }
    s, b = _http_post_json(
        f"{base}/api/v1/posts/create",
        payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    if s != 200:
        raise RuntimeError(f"post_create_failed {s} {b[:200]!r}")
    data = _must_json(b)
    return int(data["id"])

def _create_video_post(base: str, token: str, user_id: int, title: str, file_key: str) -> int:
    payload = {
        "user_id": user_id,
        "post_type": "video",
        "title": title,
        "content": "",
        "file_key": file_key,
    }
    s, b = _http_post_json(
        f"{base}/api/v1/posts/create",
        payload,
        headers=_auth_headers(token),
    )
    if s != 200:
        raise RuntimeError(f"post_create_failed {s} {b[:200]!r}")
    data = _must_json(b)
    return int(data["id"])

def _submit_ai(base: str, token: str, user_id: int, content: str) -> tuple[str, int]:
    payload = {
        "user_id": user_id,
        "post_type": "video",
        "title": "e2e_ai_job",
        "content": content,
        "category": None,
        "custom_instructions": None,
    }
    s, b = _http_post_json(
        f"{base}/api/v1/ai/submit",
        payload,
        headers=_auth_headers(token),
    )
    if s != 200:
        raise RuntimeError(f"ai_submit_failed {s} {b[:200]!r}")
    data = _must_json(b)
    job_id = str(data.get("job_id") or "").strip()
    post_id = int(data.get("post_id") or 0)
    if not job_id or post_id <= 0:
        raise RuntimeError(f"ai_submit_unexpected {data!r}")
    return job_id, post_id

def _follow(base: str, token: str, user_id: int, target_id: int) -> None:
    s, b = _http_post_json(
        f"{base}/api/v1/users/follow",
        {"user_id": user_id, "target_id": target_id},
        headers=_auth_headers(token),
    )
    if s != 200:
        raise RuntimeError(f"follow_failed {s} {b[:200]!r}")

def _wait_profile_nickname(base: str, user_id: int, current_user_id: int, expected: str, timeout_sec: float = 8.0) -> None:
    start = time.time()
    while time.time() - start < timeout_sec:
        s, b = _http_get(f"{base}/api/v1/users/profile/{user_id}?current_user_id={current_user_id}")
        if s == 200:
            try:
                data = _must_json(b)
                u = (data.get("user") or {}) if isinstance(data, dict) else {}
                nick = str(u.get("nickname") or "").strip()
                if nick == str(expected or ""):
                    return
            except Exception:
                pass
        time.sleep(0.25)
    raise RuntimeError("profile_save_not_visible")


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5002"
    base = base.rstrip("/")

    suf = f"{int(time.time())}_{random.randint(1000, 9999)}"
    pw = f"pw_{suf}"
    u1 = f"e2e_u1_{suf}"
    u2 = f"e2e_u2_{suf}"

    _register(base, u1, pw)
    _register(base, u2, pw)
    uid1, tok1 = _login(base, u1, pw)
    uid2, tok2 = _login(base, u2, pw)

    video_title = f"e2e_video_{suf}"
    _create_video_post(
        base,
        tok2,
        uid2,
        title=video_title,
        file_key="worker_media/videos/testjob/f4f81100-2003-404d-87b1-4653f897490f.mp4",
    )
    _create_image_post(base, tok2, uid2, title="e2e_friend_post")
    _follow(base, tok1, uid1, uid2)
    _follow(base, tok2, uid2, uid1)
    ai_text = (
        "这是一个用于端到端测试的示例文稿，内容健康、无敏感信息。\n"
        "请把它改写成适合短视频口播的脚本：开头一句抓人、分点讲清楚、结尾有总结。\n"
        "主题：AI 如何提升工作效率。包含：任务拆解、信息检索、草稿生成、校对润色、行动清单。\n"
        "要求：中文输出，语气自然，不要夸大承诺，不要涉及任何违法或暴力内容。\n"
        "示例要点：\n"
        "1) 用 AI 做信息整理：把长文总结成 5 条要点。\n"
        "2) 用 AI 做初稿：把要点扩写成段落。\n"
        "3) 用 AI 做校对：检查错别字与逻辑。\n"
        "4) 用 AI 做复盘：输出下一步行动。\n"
    )
    _submit_ai(base, tok1, uid1, content=ai_text)

    from playwright.sync_api import sync_playwright

    msg_txt = f"hello_e2e_{suf}"
    nick_txt = f"e2eNick_{suf[-8:]}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        ctx.add_init_script(
            "(() => {\n"
            f"  try {{ localStorage.setItem('token', {json.dumps(tok1)}); }} catch(e) {{}}\n"
            f"  try {{ localStorage.setItem('user_id', {json.dumps(str(uid1))}); }} catch(e) {{}}\n"
            f"  try {{ localStorage.setItem('username', {json.dumps(u1)}); }} catch(e) {{}}\n"
            "})();"
        )
        page = ctx.new_page()

        page.goto(f"{base}/", wait_until="domcontentloaded")
        page.wait_for_function("() => window.app && typeof window.app.openModal === 'function' && typeof window.app.switchPage === 'function'")
        page.evaluate("(uid) => { try { window.app.fetchCurrentUser(uid); } catch(e) {} }", uid1)
        page.wait_for_function(
            "(uid) => !!(window.app && window.app.state && window.app.state.user && Number(window.app.state.user.id) === Number(uid))",
            arg=uid1,
        )
        page.evaluate("() => window.app.openModal('authModal')")
        page.wait_for_selector("#authModal.modal.active")
        page.evaluate("() => window.app.closeModal('authModal')")
        page.wait_for_function("() => !document.getElementById('authModal').classList.contains('active')")

        page.goto(f"{base}/#/profile?tab=works", wait_until="domcontentloaded")
        page.wait_for_selector("#p-header .profile-name")
        page.click("#p-header i[data-action='openEditProfile']")
        page.wait_for_selector("#editProfileModal.modal.active")
        page.fill("#edit_nickname", nick_txt)
        page.click("#editProfileModal button[data-fn='saveProfile']")
        page.wait_for_function("() => !document.getElementById('editProfileModal').classList.contains('active')")
        _wait_profile_nickname(base, uid1, uid1, nick_txt)

        page.goto(f"{base}/#/u/{uid2}?tab=works", wait_until="domcontentloaded")
        page.wait_for_selector("#p-header button:has-text('私信')")
        try:
            page.wait_for_selector("#p-content .p-card", timeout=8000)
        except Exception:
            page.evaluate("() => { try { window.app.switchProfileTab('works'); } catch(e) {} }")
            page.wait_for_selector("#p-content .p-card", timeout=8000)

        page.click("#p-header button:has-text('私信')")
        page.wait_for_selector("#messageModal.modal.active")
        page.wait_for_function(
            "() => (document.getElementById('dm_chat_header_name')?.innerText || '').trim() !== '选择一个会话'"
        )
        header_txt = page.eval_on_selector("#dm_chat_header_name", "el => (el.innerText || '').trim()")
        if not header_txt or header_txt == "选择一个会话":
            raise RuntimeError(f"dm_header_missing {header_txt!r}")
        page.wait_for_function("(pid) => !!(window.app && window.app.state && Number(window.app.state.dmPeerId || 0) === Number(pid))", arg=uid2)
        page.evaluate(
            "(txt) => { const i = document.getElementById('dm_input'); if (i) i.value = String(txt || ''); return window.app.sendDMMessage(); }",
            msg_txt,
        )
        page.wait_for_function(
            "(txt) => { const box = document.getElementById('dm_chat_box'); return !!(box && (box.innerText || '').includes(String(txt || ''))); }",
            arg=msg_txt,
            timeout=20000,
        )

        page.goto(f"{base}/#/profile?tab=works", wait_until="domcontentloaded")
        page.wait_for_selector("#p-header .profile-meta", timeout=12000)
        ok_meta = page.evaluate(
            "() => { const h=document.getElementById('p-header'); const m=h? h.querySelector('.profile-meta'):null; if(!h||!m) return false; const a=h.getBoundingClientRect(); const b=m.getBoundingClientRect(); return b.bottom <= (a.bottom + 1); }"
        )
        if not ok_meta:
            raise RuntimeError("profile_meta_clipped")

        page.goto(f"{base}/#/friends", wait_until="domcontentloaded")
        page.wait_for_selector("#friends_list_panel .friend-item", timeout=15000)
        page.wait_for_selector("#friends_main_panel .friend-feed-container", timeout=15000)

        page.goto(f"{base}/#/search", wait_until="domcontentloaded")
        page.wait_for_function("() => window.app && typeof window.app.searchUser === 'function'")
        page.evaluate(
            "(q) => { const inp = window.app.getGlobalSearchInput && window.app.getGlobalSearchInput(); if (inp) inp.value = q; window.app.searchUser(); }",
            video_title,
        )
        page.wait_for_selector("#search_results_grid .s-card", timeout=15000)
        ok_float = page.evaluate(
            "() => {\n"
            "  const card = document.querySelector('#search_results_grid .s-card');\n"
            "  if (!card) return { ok:false, why:'no_card' };\n"
            "  const arg = card.getAttribute('data-args') || '';\n"
            "  let pid = 0;\n"
            "  try { const a = JSON.parse(arg); pid = Number(a && a[0] ? a[0] : 0) || 0; } catch(e) { pid = 0; }\n"
            "  if (!pid) return { ok:false, why:'no_post_id', arg };\n"
            "  const anchor = card.querySelector('.s-media') || card.querySelector('video') || card;\n"
            "  window.app.openFloatingPlayer(pid, { preset:'jx', anchorEl: anchor, forcePlay:true });\n"
            "  const wrap = document.getElementById('floating_player');\n"
            "  if (!wrap || getComputedStyle(wrap).display === 'none') return { ok:false, why:'no_wrap' };\n"
            "  const wr = wrap.getBoundingClientRect();\n"
            "  const ar = anchor.getBoundingClientRect();\n"
            "  const pad = 12;\n"
            "  const overlapX = Math.max(0, Math.min(wr.right, ar.right) - Math.max(wr.left, ar.left));\n"
            "  const overlapY = Math.max(0, Math.min(wr.bottom, ar.bottom) - Math.max(wr.top, ar.top));\n"
            "  const overlap = overlapX * overlapY;\n"
            "  const szOk = Math.abs(wr.width - ar.width) <= 6 && Math.abs(wr.height - ar.height) <= 6;\n"
            "  const topOk = wr.top <= (window.innerHeight * 0.55);\n"
            "  const cornerOk = (wr.left <= (pad + 2)) || ((window.innerWidth - wr.right) <= (pad + 2));\n"
            "  const noCover = overlap <= 1;\n"
            "  return { ok: !!(szOk && topOk && cornerOk && noCover), szOk, topOk, cornerOk, noCover, wr: {l:wr.left,t:wr.top,w:wr.width,h:wr.height}, ar: {l:ar.left,t:ar.top,w:ar.width,h:ar.height}, overlap };\n"
            "}"
        )
        if not ok_float or not ok_float.get("ok"):
            raise RuntimeError(f"floating_bad {ok_float}")

        page.goto(f"{base}/#/recommend", wait_until="domcontentloaded")
        page.wait_for_selector(".video-nav-arrows .nav-arrow", timeout=12000)
        bg = page.eval_on_selector(".video-nav-arrows .nav-arrow", "el => getComputedStyle(el).backgroundColor")
        if not bg or bg in ("rgba(0, 0, 0, 0)", "transparent"):
            raise RuntimeError(f"nav_arrow_invisible {bg!r}")

        page.goto(f"{base}/studio", wait_until="domcontentloaded")
        page.wait_for_function("() => { const el = document.getElementById('createBox'); return !!el && getComputedStyle(el).display !== 'none'; }", timeout=15000)
        page.wait_for_selector("#postList .card", timeout=20000)
        try:
            page.click("#postList .card:has-text('e2e_ai_job')")
        except Exception:
            page.click("#postList .card")
        page.wait_for_function("() => !!document.getElementById('btnToggleDownload') && !!document.getElementById('btnToggleDownload').dataset.enabled", timeout=20000)
        page.wait_for_function("() => (document.getElementById('btnToggleDownload')?.innerText || '').trim() === '下载：开'", timeout=20000)
        before = page.eval_on_selector("#btnToggleDownload", "el => (el.innerText || '').trim()")
        page.click("#btnToggleDownload")
        page.wait_for_function("(b) => (document.getElementById('btnToggleDownload')?.innerText || '').trim() !== String(b || '')", arg=before, timeout=20000)
        after = page.eval_on_selector("#btnToggleDownload", "el => (el.innerText || '').trim()")
        page.click("#btnToggleDownload")
        page.wait_for_function("(a) => (document.getElementById('btnToggleDownload')?.innerText || '').trim() === String(a || '')", arg=before, timeout=20000)

        try:
            ctx.close()
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass

    sys.stdout.write("OK\n")
    sys.stdout.write(f"user_id:{uid1} peer_id:{uid2}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
