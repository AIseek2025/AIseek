from __future__ import annotations

import base64
import os
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
import redis

from app.core.config import OUTPUTS_DIR, settings


@dataclass(frozen=True)
class CoverPlan:
    title_text: str
    subtitle_text: str
    visual_prompt_en: str
    orientation: str = "portrait"
    style: str = "modern, minimal, high-contrast"


@dataclass(frozen=True)
class CoverResult:
    ok: bool
    provider: str
    image_path: Optional[str]
    trace: list[dict]


def _redis_client() -> Optional["redis.Redis"]:
    try:
        url = str((os.getenv("REDIS_URL") or os.getenv("CELERY_BROKER_URL") or "")).strip()
        if not url:
            url = "redis://localhost:6379/0"
        r = redis.Redis.from_url(url, decode_responses=True, socket_timeout=0.5, socket_connect_timeout=0.25)
        r.ping()
        return r
    except Exception:
        return None


def _cb_open(provider: str) -> bool:
    p = str(provider or "").strip().lower()
    if not p:
        return False
    r = _redis_client()
    if r is None:
        return False
    try:
        until = int(r.get(f"cv:cb:open_until:{p}") or 0)
        return until and int(time.time()) < until
    except Exception:
        return False


def _cb_success(provider: str) -> None:
    p = str(provider or "").strip().lower()
    if not p:
        return
    r = _redis_client()
    if r is None:
        return
    try:
        r.delete(f"cv:cb:fail:{p}")
        r.delete(f"cv:cb:open_until:{p}")
    except Exception:
        return


def _cb_fail(provider: str, *, hard: bool = False) -> None:
    p = str(provider or "").strip().lower()
    if not p:
        return
    r = _redis_client()
    if r is None:
        return
    try:
        fk = f"cv:cb:fail:{p}"
        n = int(r.incr(fk))
        if n == 1:
            r.expire(fk, 300)
        if hard or n >= 3:
            backoff = 60 if n < 6 else 180 if n < 10 else 600
            until = int(time.time()) + int(backoff)
            ok = r.set(f"cv:cb:open_until:{p}", str(until), ex=int(backoff), nx=True)
            if not ok:
                r.expire(f"cv:cb:open_until:{p}", int(backoff))
    except Exception:
        return


def _sanitize_cover_text(s: str) -> str:
    t = str(s or "").strip()
    if not t:
        return ""
    t = re.sub(r"(?:\+?86)?1[3-9]\d{9}", "[REDACTED]", t)
    t = re.sub(r"\b\d{17}[\dXx]\b", "[REDACTED]", t)
    t = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[REDACTED]", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:80]


def _has_wan_key() -> bool:
    key = str(getattr(settings, "cover_wan_api_key", "") or "").strip()
    if key:
        return True
    return bool(
        str(os.getenv("DASHSCOPE_API_KEY") or "").strip()
        or str(os.getenv("COVER_WAN_API_KEY") or "").strip()
        or str(os.getenv("WANX_API_KEY") or "").strip()
    )


def _has_openai_key() -> bool:
    key = str(getattr(settings, "cover_openai_api_key", "") or "").strip()
    if key:
        return True
    return bool(str(os.getenv("OPENAI_API_KEY") or "").strip())


def has_any_ai_cover_provider() -> bool:
    return _has_wan_key() or _has_openai_key()


def build_cover_plan(analysis: dict, *, fallback_title: str = "", fallback_summary: str = "", orientation: str = "portrait") -> CoverPlan:
    title_text = ""
    subtitle_text = ""
    visual_prompt_en = ""
    try:
        ps = analysis.get("production_script") if isinstance(analysis, dict) else None
        cover = ps.get("cover") if isinstance(ps, dict) and isinstance(ps.get("cover"), dict) else {}
        title_text = str(cover.get("title_text") or "").strip()
        subtitle_text = str(cover.get("subtitle_text") or "").strip()
        visual_prompt_en = str(cover.get("visual_prompt_en") or "").strip()
    except Exception:
        pass
    if not title_text:
        title_text = str(fallback_title or "").strip()
    if not subtitle_text:
        subtitle_text = str(fallback_summary or "").strip()
    if not visual_prompt_en:
        visual_prompt_en = "abstract tech background, clean typography, vertical poster"
    ori = str(orientation or "").strip().lower() or "portrait"
    if ori not in {"portrait", "landscape"}:
        ori = "portrait"
    title_s = _sanitize_cover_text(title_text).strip("，。！？；：,.!?;:")
    subtitle_s = _sanitize_cover_text(subtitle_text).strip("，。！？；：,.!?;:")
    if len(title_s) > 18:
        title_s = title_s[:18].strip()
    if len(subtitle_s) > 24:
        subtitle_s = subtitle_s[:24].strip()
    return CoverPlan(
        title_text=title_s,
        subtitle_text=subtitle_s,
        visual_prompt_en=str(visual_prompt_en)[:220],
        orientation=ori,
    )


def _openai_generate(job_id: str, plan: CoverPlan, trace: list[dict]) -> Optional[str]:
    # Try all possible env vars for OpenAI key
    key = str(getattr(settings, "cover_openai_api_key", "") or "").strip()
    if not key:
        key = str(os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        trace.append({"t": "provider_skip", "p": "openai", "reason": "no_key"})
        return None
    if _cb_open("openai"):
        trace.append({"t": "provider_skip", "p": "openai", "reason": "circuit_open"})
        return None
    try:
        from openai import OpenAI
    except Exception:
        trace.append({"t": "provider_skip", "p": "openai", "reason": "client_unavailable"})
        return None

    req = "9:16 vertical" if str(plan.orientation) != "landscape" else "16:9 landscape"
    size = "1024x1792" if str(plan.orientation) != "landscape" else "1792x1024"
    prompt = (
        f"Design a {req} cover image for a short educational video.\n"
        f"Main title text: {plan.title_text}\n"
        f"Subtitle text: {plan.subtitle_text}\n"
        f"Visual style prompt: {plan.visual_prompt_en}\n"
        f"Style: {plan.style}\n"
        f"Requirements: {req}, clean layout, readable title area, no violence or gore."
    )
    out_dir = OUTPUTS_DIR / "covers" / str(job_id) / str(uuid.uuid4())
    out_dir.mkdir(parents=True, exist_ok=True)
    out_png = out_dir / "cover.png"
    try:
        client = OpenAI(api_key=key, base_url=str(getattr(settings, "cover_openai_base_url", "https://api.openai.com/v1")))
        t0 = time.time()
        res = client.images.generate(
            model=str(getattr(settings, "cover_openai_model", "gpt-image-1")),
            prompt=prompt,
            size=size,
        )
        dt = int(round((time.time() - t0) * 1000))
        b64 = None
        try:
            if res and getattr(res, "data", None):
                d0 = res.data[0]
                b64 = getattr(d0, "b64_json", None) or getattr(d0, "b64", None)
        except Exception:
            b64 = None
        if not b64:
            trace.append({"t": "provider_fail", "p": "openai", "ms": dt, "reason": "no_image_data"})
            _cb_fail("openai", hard=False)
            return None
        raw = base64.b64decode(b64)
        out_png.write_bytes(raw)
        if out_png.exists() and out_png.stat().st_size > 10_000:
            trace.append({"t": "provider_ok", "p": "openai", "ms": dt, "path": str(out_png)})
            _cb_success("openai")
            return str(out_png)
        trace.append({"t": "provider_fail", "p": "openai", "ms": dt, "reason": "small_file"})
        _cb_fail("openai", hard=False)
        return None
    except Exception as e:
        trace.append({"t": "provider_fail", "p": "openai", "reason": str(e)[:180]})
        _cb_fail("openai", hard=False)
        return None


def _wanx_generate(job_id: str, plan: CoverPlan, trace: list[dict]) -> Optional[str]:
    """Generate cover using 通义万相 wan2.6-t2i (multimodal-generation API)."""
    key = str(getattr(settings, "cover_wan_api_key", "") or "").strip()
    if not key:
        key = str(os.getenv("DASHSCOPE_API_KEY") or "").strip()
    if not key:
        key = str(os.getenv("COVER_WAN_API_KEY") or "").strip()
    if not key:
        key = str(os.getenv("WANX_API_KEY") or "").strip()

    if not key:
        trace.append({"t": "provider_skip", "p": "wanx", "reason": "no_key"})
        return None

    if _cb_open("wanx"):
        trace.append({"t": "provider_skip", "p": "wanx", "reason": "circuit_open"})
        return None

    base = str(getattr(settings, "cover_wan_base_url", "https://dashscope.aliyuncs.com") or "").rstrip("/")
    if base.endswith("/api/v1"):
        base = base[: -len("/api/v1")]

    url = f"{base}/api/v1/services/aigc/multimodal-generation/generation"
    model = str(getattr(settings, "cover_wan_model", "wan2.6-t2i") or "wan2.6-t2i")

    size = "1024*1536" if str(plan.orientation) != "landscape" else "1536*1024"
    prompt = (
        f"一张高质量的短视频封面图，{'9:16竖屏' if str(plan.orientation) != 'landscape' else '16:9横屏'}。"
        f"主标题文字：{plan.title_text}。"
        f"画面描述：{plan.visual_prompt_en}。"
        f"风格：{plan.style}，高清晰度，电影质感，色彩鲜艳，构图完美，无模糊，无水印。"
    )
    negative_prompt = "模糊，低质量，文字扭曲，水印，logo，变形"

    payload = {
        "model": model,
        "input": {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
        },
        "parameters": {
            "size": size,
            "n": 1,
            "num_inference_steps": 30,
            "guidance_scale": 7.5,
            "style": "<photorealistic>",
        },
    }

    out_dir = OUTPUTS_DIR / "covers" / str(job_id) / str(uuid.uuid4())
    out_dir.mkdir(parents=True, exist_ok=True)
    out_img = out_dir / "cover.png"

    try:
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

        t0 = time.time()
        with httpx.Client(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
            resp = client.post(url, headers=headers, json=payload)

        if resp.status_code != 200:
            trace.append({
                "t": "provider_fail", "p": "wanx",
                "reason": f"http_status:{resp.status_code}", "body": resp.text[:200],
            })
            _cb_fail("wanx", hard=False)
            return None

        js = resp.json()

        if "code" in js and js.get("code"):
            trace.append({
                "t": "provider_fail", "p": "wanx",
                "reason": js.get("message", str(js))[:200],
            })
            _cb_fail("wanx", hard=False)
            return None

        task_id = None
        if isinstance(js.get("output"), dict):
            task_id = js.get("output", {}).get("task_id")

        if task_id:
            start_poll = time.time()
            poll_attempts = 0
            while time.time() - start_poll < 120:
                poll_attempts += 1
                time.sleep(3)
                task_url = f"{base}/api/v1/tasks/{task_id}"
                try:
                    with httpx.Client(timeout=httpx.Timeout(15.0)) as client:
                        r_task = client.get(task_url, headers={"Authorization": f"Bearer {key}"})
                    if r_task.status_code != 200:
                        continue
                    js_task = r_task.json()
                    status = js_task.get("output", {}).get("task_status")
                    if poll_attempts % 5 == 0:
                        trace.append({"t": "wanx_poll", "status": status, "attempt": poll_attempts})
                    if status == "SUCCEEDED":
                        js = js_task
                        break
                    if status == "FAILED":
                        trace.append({"t": "provider_fail", "p": "wanx", "reason": "task_failed"})
                        _cb_fail("wanx", hard=False)
                        return None
                except Exception as e:
                    if poll_attempts % 5 == 0:
                        trace.append({"t": "wanx_poll_error", "err": str(e)[:100]})
                    continue

        img_url = None
        try:
            results = js.get("output", {}).get("results", [])
            if results:
                img_url = results[0].get("url")
        except Exception:
            pass

        if not img_url:
            trace.append({"t": "provider_fail", "p": "wanx", "reason": "no_image_url"})
            _cb_fail("wanx", hard=False)
            return None

        with httpx.Client(timeout=httpx.Timeout(30.0)) as client:
            r_img = client.get(img_url)
        if r_img.status_code == 200:
            out_img.write_bytes(r_img.content)
            dt = int(round((time.time() - t0) * 1000))
            if out_img.exists() and out_img.stat().st_size > 1000:
                trace.append({"t": "provider_ok", "p": "wanx", "ms": dt, "path": str(out_img)})
                _cb_success("wanx")
                return str(out_img)

        trace.append({"t": "provider_fail", "p": "wanx", "reason": "download_failed"})
        _cb_fail("wanx", hard=False)
        return None

    except Exception as e:
        trace.append({"t": "provider_fail", "p": "wanx", "reason": str(e)[:200]})
        _cb_fail("wanx", hard=False)
        return None


class CoverService:
    def generate_cover_image(self, job_id: str, plan: CoverPlan) -> CoverResult:
        trace: list[dict] = [{"t": "cover_start", "job_id": str(job_id), "providers": list(getattr(settings, "cover_provider_order", []) or [])}]
        order = [str(x or "").strip().lower() for x in (getattr(settings, "cover_provider_order", None) or []) if str(x or "").strip()]
        if not order:
            order = ["wanx", "openai", "frame"]
        if bool(getattr(settings, "cover_fast_degrade_no_key", True)):
            has_wan = _has_wan_key()
            has_openai = _has_openai_key()
            if not has_wan and not has_openai:
                trace.append({"t": "cover_short_circuit", "reason": "all_ai_no_key"})
                for p in order:
                    if p in {"wanx", "openai"}:
                        trace.append({"t": "provider_skip", "p": p, "reason": "no_key"})
                    if p == "frame":
                        trace.append({"t": "provider_defer", "p": "frame"})
                return CoverResult(ok=False, provider="none", image_path=None, trace=trace)
        for p in order:
            if p == "wanx":
                path = _wanx_generate(job_id, plan, trace)
                if path:
                    return CoverResult(ok=True, provider="wanx", image_path=path, trace=trace)
            if p == "openai":
                path = _openai_generate(job_id, plan, trace)
                if path:
                    return CoverResult(ok=True, provider="openai", image_path=path, trace=trace)
            if p == "frame":
                trace.append({"t": "provider_defer", "p": "frame"})
        return CoverResult(ok=False, provider="none", image_path=None, trace=trace)
