(() => {
  const API = "/api/v1";
  const $ = (id) => document.getElementById(id);

  let current = { postId: null, jobId: null, evSource: null, lastEv: 0, evRetryMs: 800 };
  let postState = { items: [], cursor: null, done: false, loading: false };

  function token() {
    try { return localStorage.getItem("token") || ""; } catch (_) { return ""; }
  }
  function userId() {
    try { return Number(localStorage.getItem("user_id") || 0) || 0; } catch (_) { return 0; }
  }
  function setAuth(t, uid, uname) {
    try {
      if (t) localStorage.setItem("token", t);
      if (uid) localStorage.setItem("user_id", String(uid));
      if (uname) localStorage.setItem("username", uname);
    } catch (_) {}
  }
  function clearAuth() {
    try {
      localStorage.removeItem("token");
      localStorage.removeItem("user_id");
      localStorage.removeItem("username");
    } catch (_) {}
  }

  function toast(msg, ms = 2600) {
    const el = $("toast");
    if (!el) return;
    el.textContent = String(msg || "");
    el.classList.add("show");
    window.clearTimeout(el.__t);
    el.__t = window.setTimeout(() => el.classList.remove("show"), ms);
  }

  async function apiFetch(path, opts = {}) {
    const h = opts.headers || {};
    const t = token();
    if (t) h["Authorization"] = `Bearer ${t}`;
    opts.headers = h;
    const res = await fetch(path.startsWith("http") ? path : `${path}`, opts);
    let data = null;
    try { data = await res.json(); } catch (_) { data = null; }
    if (!res.ok) {
      const detail = data && data.detail ? data.detail : data;
      const e = new Error(typeof detail === "string" ? detail : "request_failed");
      e.status = res.status;
      e.detail = detail;
      throw e;
    }
    return data;
  }

  async function apiFetchRaw(path, opts = {}) {
    const h = opts.headers || {};
    const t = token();
    if (t) h["Authorization"] = `Bearer ${t}`;
    opts.headers = h;
    const res = await fetch(path.startsWith("http") ? path : `${path}`, opts);
    let data = null;
    try { data = await res.json(); } catch (_) { data = null; }
    if (!res.ok) {
      const detail = data && data.detail ? data.detail : data;
      const e = new Error(typeof detail === "string" ? detail : "request_failed");
      e.status = res.status;
      e.detail = detail;
      throw e;
    }
    return { data, headers: res.headers };
  }

  function fmtStatus(st) {
    const s = String(st || "");
    if (s === "done") return ["done", "good"];
    if (s === "processing" || s === "queued") return [s, "warn"];
    if (s === "returned") return ["回退", "bad"];
    if (s === "failed" || s === "cancelled") return [s, "bad"];
    return [s || "-", ""];
  }

  function setBadge(el, text, klass) {
    if (!el) return;
    el.classList.remove("good", "warn", "bad");
    if (klass) el.classList.add(klass);
    el.textContent = text;
  }

  function showTab(name) {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll("[data-tab]").forEach((t) => {
      if (t.getAttribute("data-tab") === name) t.classList.add("active");
    });
    ["overview", "draft", "history"].forEach((k) => {
      const el = $(`tab_${k}`);
      if (el) el.style.display = k === name ? "" : "none";
    });
  }

  async function login(u, p) {
    const res = await fetch(`${API}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: u, password: p }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error((data && data.detail) || "login_failed");
    setAuth(data.access_token, data.user_id, data.username);
    return data;
  }

  function renderAuthUI() {
    const uid = userId();
    const uname = (() => { try { return localStorage.getItem("username") || ""; } catch (_) { return ""; } })();
    const ok = !!token() && uid > 0;
    $("authName").textContent = ok ? `${uname || "User"} #${uid}` : "未登录";
    $("btnLogout").style.display = ok ? "" : "none";
    $("loginBox").style.display = ok ? "none" : "";
    $("createBox").style.display = ok ? "" : "none";
  }

  async function loadCategories() {
    let cats = [];
    try { cats = await apiFetch(`${API}/posts/categories`); } catch (_) { cats = []; }
    const el = $("inCategory");
    if (!el) return;
    const list = Array.isArray(cats) ? cats : [];
    const opts = [`<option value="">未分类</option>`].concat(list.map((c) => `<option value="${String(c)}">${String(c)}</option>`));
    el.innerHTML = opts.join("");
  }

  async function loadMediaOptions() {
    let data = null;
    try { data = await apiFetch(`${API}/media/options`); } catch (_) { data = null; }
    if (!data || typeof data !== "object") return;
    try {
      const v = data.voice && Array.isArray(data.voice.profiles) ? data.voice.profiles : [];
      const el = $("inVoice");
      if (el && v.length) {
        el.innerHTML = v
          .map((it) => {
            const id = it && it.id !== undefined ? String(it.id) : "";
            const label = it && it.label !== undefined ? String(it.label) : id;
            return `<option value="${escapeHtml(id)}">${escapeHtml(label)}</option>`;
          })
          .join("");
      }
    } catch (_) {}
    try {
      const moods = data.bgm && Array.isArray(data.bgm.moods) ? data.bgm.moods : [];
      const el = $("inBgm");
      if (el && moods.length) {
        el.innerHTML = moods
          .map((it) => {
            const id = it && it.id !== undefined ? String(it.id) : "";
            const label = it && it.label !== undefined ? String(it.label) : id;
            return `<option value="${escapeHtml(id)}">${escapeHtml(label)}</option>`;
          })
          .join("");
      }
    } catch (_) {}
    try {
      const tracks = data.bgm && Array.isArray(data.bgm.tracks) ? data.bgm.tracks : [];
      const el = $("inBgmTrack");
      if (el) {
        const head = [`<option value="">自动</option>`];
        const body = tracks.map((it) => {
          const id = it && it.id !== undefined ? String(it.id) : "";
          const label = it && it.label !== undefined ? String(it.label) : id;
          return `<option value="${escapeHtml(id)}">${escapeHtml(label)}</option>`;
        });
        el.innerHTML = head.concat(body).join("");
      }
    } catch (_) {}
  }

  async function loadMyPosts(reset = true) {
    const uid = userId();
    if (!uid) return;
    if (postState.loading) return;
    if (reset) postState = { items: [], cursor: null, done: false, loading: false };
    if (postState.done && !reset) return;
    postState.loading = true;
    const st = String($("postFilter").value || "all");
    const limit = 30;
    const cursor = postState.cursor ? `&cursor=${encodeURIComponent(postState.cursor)}` : "";
    const out = await apiFetchRaw(`${API}/posts/user/${uid}?viewer_id=${uid}&limit=${limit}${cursor}`);
    const arr = Array.isArray(out.data) ? out.data : [];
    const nextCursor = out.headers ? out.headers.get("x-next-cursor") : null;
    postState.cursor = nextCursor || null;
    if (!nextCursor || !arr.length) postState.done = true;
    postState.items = postState.items.concat(arr);

    const filtered = st === "all" ? postState.items : postState.items.filter((p) => String(p.status || "") === st);
    $("postCount").textContent = String(filtered.length);
    const cur = String(current.postId || "");
    $("postList").innerHTML = filtered
      .map((p) => {
        const pid = Number(p.id || 0) || 0;
        const title = String(p.title || p.summary || "未命名作品");
        const s = String(p.status || "");
        const [lab, cls] = fmtStatus(s);
        const sub = [
          `#${pid}`,
          p.ai_job_id ? `job:${String(p.ai_job_id).slice(0, 8)}` : "",
          p.post_type ? String(p.post_type) : "",
          p.category ? String(p.category) : "",
          p.error_message ? `原因:${String(p.error_message)}` : "",
        ].filter(Boolean);
        const active = cur && String(pid) === cur ? "active" : "";
        return `
          <div class="card ${active}" data-post="${pid}">
            <div class="card-title">
              <div class="t">${escapeHtml(title)}</div>
              <span class="badge ${cls}">${lab}</span>
            </div>
            <div class="card-sub">${sub.map((x) => `<span>${escapeHtml(x)}</span>`).join("")}</div>
          </div>
        `;
      })
      .join("");
    document.querySelectorAll("#postList .card").forEach((el) => {
      el.addEventListener("click", () => {
        const pid = Number(el.getAttribute("data-post") || 0) || 0;
        if (pid) selectPost(pid);
      });
    });
    const more = $("btnLoadMorePosts");
    if (more) more.style.display = !postState.done ? "" : "none";
    postState.loading = false;
  }

  function escapeHtml(s) {
    return String(s || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  async function createJob() {
    const uid = userId();
    if (!uid) return toast("请先登录");
    const title = String($("inTitle").value || "").trim();
    const content = String($("inContent").value || "").trim();
    if (!content) return toast("请输入文稿");
    const category = String($("inCategory").value || "").trim() || null;
    const voice_style = String($("inVoice").value || "").trim() || null;
    const bgm_mood = String($("inBgm").value || "").trim() || null;
    const bgm_id = String(($("inBgmTrack") && $("inBgmTrack").value) || "").trim() || null;
    const subtitle_mode = String(($("inSubMode") && $("inSubMode").value) || "").trim() || null;
    const cover_orientation = String(($("inCoverOrient") && $("inCoverOrient").value) || "").trim() || null;
    const requested_duration_sec = (() => {
      const v = String(($("inDurMax") && $("inDurMax").value) || "").trim();
      const n = Number(v || 0) || 0;
      return n > 0 ? n : null;
    })();
    const custom_instructions = String($("inInstr").value || "").trim() || null;
    try {
      $("btnCreate").disabled = true;
      $("btnCreate").innerHTML = `<i class="fas fa-spinner fa-spin"></i>生成中...`;
      const out = await apiFetch(`${API}/ai/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: uid,
          post_type: "video",
          content,
          title: title || null,
          category,
          custom_instructions,
          voice_style,
          bgm_mood,
          bgm_id,
          subtitle_mode,
          requested_duration_sec,
          cover_orientation,
        }),
      });
      const pid = Number(out.post_id || 0) || 0;
      if (pid) {
        toast("已提交任务");
        $("inContent").value = "";
        await loadMyPosts();
        await selectPost(pid);
      }
    } catch (e) {
      const det = e && e.detail ? e.detail : null;
      if (det && typeof det === "object" && det.action === "cooldown") {
        $("cooldownBadge").style.display = "";
        $("cooldownBadge").textContent = "冷却中";
      }
      toast(`提交失败：${formatErr(e)}`);
    } finally {
      $("btnCreate").disabled = false;
      $("btnCreate").innerHTML = `<i class="fas fa-wand-magic-sparkles"></i>开始生成`;
    }
  }

  function formatErr(e) {
    if (!e) return "unknown";
    if (typeof e === "string") return e;
    if (e.detail) {
      const d = e.detail;
      const s = typeof d === "string" ? d : JSON.stringify(d);
      if (s === "download_disabled") return "作者未开放下载";
      if (s === "not_ready") return "作品尚未生成完成，暂不可下载";
      if (s === "missing_media" || s === "missing_mp4") return "没有可下载的文件";
      return s;
    }
    if (e.message) return e.message;
    return "error";
  }

  async function selectPost(postId) {
    current.postId = Number(postId || 0) || null;
    current.jobId = null;
    current.lastEv = 0;
    current.evRetryMs = 800;
    if (current.evSource) {
      try { current.evSource.close(); } catch (_) {}
      current.evSource = null;
    }
    await loadMyPosts();
    await refreshAll();
  }

  async function refreshAll() {
    await Promise.allSettled([loadPostAndJob(), loadDraft(), loadHistory(), loadPreview(), loadChat()]);
  }

  async function loadPostAndJob() {
    const pid = Number(current.postId || 0) || 0;
    const uid = userId();
    if (!pid || !uid) return;
    const post = await apiFetch(`${API}/posts/${pid}?user_id=${uid}`);
    $("jobTitle").textContent = String(post.title || post.summary || `作品 #${pid}`);
    $("postId").textContent = String(pid);
    const st = String(post.status || "");
    const [lab, cls] = fmtStatus(st);
    setBadge($("jobStatus"), lab, cls);
    let jobId = post.ai_job_id ? String(post.ai_job_id) : "";
    if (!jobId) {
      try {
        const j = await apiFetch(`${API}/ai/jobs/by_post/${pid}?user_id=${uid}`);
        jobId = j && j.job_id ? String(j.job_id) : "";
      } catch (_) {}
    }
    const prevJob = String(current.jobId || "");
    const nextJob = String(jobId || "");
    if (current.evSource && prevJob && nextJob && prevJob !== nextJob) {
      try { current.evSource.close(); } catch (_) {}
      current.evSource = null;
      current.lastEv = 0;
      current.evRetryMs = 800;
      try { $("evLog").textContent = ""; } catch (_) {}
      try { $("evHint").textContent = "-"; } catch (_) {}
    }
    current.jobId = jobId || null;
    $("jobId").textContent = jobId || "-";
    $("btnOpenPost").disabled = !pid;
    $("btnOpenInProfile").disabled = !uid;
    $("btnCancel").disabled = !jobId;
    if (jobId) await loadJob(jobId);
  }

  async function loadJob(jobId) {
    const uid = userId();
    const job = await apiFetch(`${API}/ai/jobs/${encodeURIComponent(jobId)}?user_id=${uid}`);
    const [lab, cls] = fmtStatus(job.status);
    setBadge($("jobStatus"), lab, cls);
    setBadge($("jobProgress"), `${Number(job.progress || 0) || 0}%`, cls);
    $("jobStage").textContent = job.stage ? String(job.stage) : "-";
    $("jobMsg").textContent = job.stage_message ? String(job.stage_message) : "-";
    $("jobId").textContent = String(job.id || "");
    current.jobStatus = String(job.status || "");
    if (job.post_id) $("postId").textContent = String(job.post_id);
    try {
      const btn = $("btnDispatch");
      if (btn) btn.style.display = String(job.stage || "") === "dispatch_failed" ? "" : "none";
    } catch (_) {}
    if (job.status === "queued" || job.status === "processing") {
      attachEvents(jobId);
    } else {
      if (current.evSource && String(current.evJobId || "") === String(jobId || "")) {
        try { current.evSource.close(); } catch (_) {}
        current.evSource = null;
      }
      try { $("evHint").textContent = "SSE 未连接"; } catch (_) {}
    }
    if (job.status === "queued" || job.status === "processing") scheduleJobPoll(jobId);
  }

  function attachEvents(jobId) {
    const uid = userId();
    if (!uid || !jobId) return;
    if (current.evSource) {
      const bound = String(current.evJobId || "");
      if (bound === String(jobId || "")) return;
      try { current.evSource.close(); } catch (_) {}
      current.evSource = null;
    }
    const url = `${API}/ai/jobs/${encodeURIComponent(jobId)}/events/stream?user_id=${uid}&since=${Number(current.lastEv || 0) || 0}`;
    const es = new EventSource(url);
    current.evSource = es;
    current.evJobId = String(jobId || "");
    $("evHint").textContent = "SSE 已连接";
    es.addEventListener("ev", (evt) => {
      try {
        const data = JSON.parse(evt.data || "{}");
        appendEvent(data);
      } catch (_) {}
    });
    es.onerror = () => {
      $("evHint").textContent = "SSE 已断开";
      try { es.close(); } catch (_) {}
      current.evSource = null;
      const backoff = Math.min(15000, Math.max(600, Number(current.evRetryMs || 800) || 800));
      current.evRetryMs = Math.min(15000, Math.floor(backoff * 1.6));
      window.setTimeout(() => {
        if (String(current.jobId || "") === String(jobId || "")) attachEvents(jobId);
      }, backoff);
    };
  }

  function appendEvent(e) {
    const el = $("evLog");
    if (!el || !e) return;
    try {
      const eid = Number(e.id || 0) || 0;
      if (eid > 0) current.lastEv = Math.max(Number(current.lastEv || 0) || 0, eid);
    } catch (_) {}
    const ts = e.ts ? new Date(Number(e.ts) * 1000).toLocaleString() : "";
    const t = String(e.type || e.kind || "");
    const data = e.data !== undefined ? e.data : e.payload;
    try {
      if (t === "progress" && data && typeof data === "object") {
        const st = String(data.status || "");
        const [lab, cls] = fmtStatus(st);
        setBadge($("jobStatus"), lab, cls);
        setBadge($("jobProgress"), `${Number(data.progress || 0) || 0}%`, cls);
        $("jobStage").textContent = data.stage ? String(data.stage) : "-";
        $("jobMsg").textContent = data.stage_message ? String(data.stage_message) : "-";
      }
    } catch (_) {}
    const msg = data !== undefined ? JSON.stringify(data) : "";
    const line = `${ts}  ${t}  ${msg}`.trim();
    const prev = el.textContent || "";
    el.textContent = (prev ? prev + "\n" : "") + line;
    el.scrollTop = el.scrollHeight;
  }

  function scheduleJobPoll(jobId) {
    try {
      if (current.jobPollTimer) window.clearTimeout(current.jobPollTimer);
    } catch (_) {}
    const jid = String(jobId || "");
    if (!jid) return;
    current.jobPollTimer = window.setTimeout(async () => {
      if (String(current.jobId || "") !== jid) return;
      try {
        const uid = userId();
        const job = await apiFetch(`${API}/ai/jobs/${encodeURIComponent(jid)}?user_id=${uid}`);
        const [lab, cls] = fmtStatus(job.status);
        setBadge($("jobStatus"), lab, cls);
        setBadge($("jobProgress"), `${Number(job.progress || 0) || 0}%`, cls);
        $("jobStage").textContent = job.stage ? String(job.stage) : "-";
        $("jobMsg").textContent = job.stage_message ? String(job.stage_message) : "-";
        if (job.status === "queued" || job.status === "processing") scheduleJobPoll(jid);
      } catch (_) {
        scheduleJobPoll(jid);
      }
    }, 3500);
  }

  async function loadDraft() {
    const jobId = current.jobId;
    const uid = userId();
    if (!jobId || !uid) return;
    const raw = await apiFetch(`${API}/ai/jobs/${encodeURIComponent(jobId)}/draft?user_id=${uid}`);
    const dj = raw && raw.draft_json !== undefined ? raw.draft_json : null;
    const rawMode = !!$("toggleRaw").checked;
    if (rawMode) {
      $("draftEditor").value = JSON.stringify(dj || {}, null, 2);
      return;
    }
    if (typeof dj === "string") {
      $("draftEditor").value = dj;
      return;
    }
    if (dj && typeof dj === "object") {
      const s = dj.script || dj.text || dj.narration || "";
      if (typeof s === "string" && s.trim()) {
        $("draftEditor").value = s;
        return;
      }
      $("draftEditor").value = JSON.stringify(dj, null, 2);
      return;
    }
    $("draftEditor").value = "";
  }

  async function saveDraft() {
    const jobId = current.jobId;
    const uid = userId();
    if (!jobId || !uid) return toast("未选择作品");
    const rawMode = !!$("toggleRaw").checked;
    const txt = String($("draftEditor").value || "");
    let draft_json = null;
    if (rawMode) {
      try { draft_json = JSON.parse(txt || "{}"); } catch (e) { return toast("JSON 格式不正确"); }
    } else {
      draft_json = { script: txt };
    }
    try {
      $("btnSaveDraft").disabled = true;
      await apiFetch(`${API}/ai/jobs/${encodeURIComponent(jobId)}/draft`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: uid, draft_json, source: "studio_edit" }),
      });
      toast("已保存脚本");
      await loadHistory();
    } catch (e) {
      toast(`保存失败：${formatErr(e)}`);
    } finally {
      $("btnSaveDraft").disabled = false;
    }
  }

  async function loadHistory() {
    const jobId = current.jobId;
    const uid = userId();
    if (!jobId || !uid) return;
    const out = await apiFetch(`${API}/ai/jobs/${encodeURIComponent(jobId)}/draft/history?user_id=${uid}&limit=50`);
    const items = out && Array.isArray(out.items) ? out.items : [];
    $("historyList").innerHTML = items
      .map((it) => {
        const id = Number(it.id || 0) || 0;
        const src = String(it.source || "");
        const dt = it.created_at ? new Date(it.created_at).toLocaleString() : "";
        return `
          <div class="card" data-ver="${id}">
            <div class="card-title">
              <div class="t">版本 #${id}</div>
              <button class="btn btn-small" data-act="restore" data-ver="${id}"><i class="fas fa-clock-rotate-left"></i>恢复</button>
            </div>
            <div class="card-sub"><span>${escapeHtml(src)}</span><span>${escapeHtml(dt)}</span></div>
          </div>
        `;
      })
      .join("");
    document.querySelectorAll("#historyList [data-act='restore']").forEach((b) => {
      b.addEventListener("click", async (ev) => {
        ev.stopPropagation();
        const id = Number(b.getAttribute("data-ver") || 0) || 0;
        if (id) await restoreVersion(id);
      });
    });
  }

  async function restoreVersion(versionId) {
    const jobId = current.jobId;
    const uid = userId();
    if (!jobId || !uid) return;
    try {
      const v = await apiFetch(`${API}/ai/jobs/${encodeURIComponent(jobId)}/draft/history/${Number(versionId)}?user_id=${uid}`);
      const dj = v && v.draft_json !== undefined ? v.draft_json : null;
      await apiFetch(`${API}/ai/jobs/${encodeURIComponent(jobId)}/draft`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: uid, draft_json: dj, source: "restore" }),
      });
      toast(`已恢复版本 #${versionId}`);
      await loadDraft();
    } catch (e) {
      toast(`恢复失败：${formatErr(e)}`);
    }
  }

  async function rerunFromDraft() {
    const jobId = current.jobId;
    const uid = userId();
    const pid0 = Number(current.postId || 0) || 0;
    if (!uid) return toast("未登录");
    if (!jobId) {
      if (!pid0) return toast("未选择作品");
      try {
        $("btnRerun").disabled = true;
        const out = await apiFetch(`${API}/ai/posts/${encodeURIComponent(String(pid0))}/resubmit`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_id: uid, post_type: "video", content: "", title: "", category: "", subtitle_mode: "zh" }),
        });
        const pid = Number(out.post_id || 0) || 0;
        if (pid) {
          toast("已重新提交并创建任务");
          await selectPost(pid);
        }
      } catch (e) {
        toast(`重提失败：${formatErr(e)}`);
      } finally {
        $("btnRerun").disabled = false;
      }
      return;
    }
    try {
      $("btnRerun").disabled = true;
      const out = await apiFetch(`${API}/ai/jobs/${encodeURIComponent(jobId)}/rerun`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: uid, draft_json: null, source: "studio_rerun" }),
      });
      const pid = Number(out.post_id || 0) || 0;
      if (pid) {
        toast("已创建新任务并绑定到作品");
        await selectPost(pid);
      }
    } catch (e) {
      toast(`重跑失败：${formatErr(e)}`);
    } finally {
      $("btnRerun").disabled = false;
    }
  }

  async function cancelJob() {
    const jobId = current.jobId;
    const uid = userId();
    if (!jobId || !uid) return;
    try {
      await apiFetch(`${API}/ai/jobs/${encodeURIComponent(jobId)}/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: uid }),
      });
      toast("已取消");
      await refreshAll();
    } catch (e) {
      toast(`取消失败：${formatErr(e)}`);
    }
  }

  async function dispatchJob() {
    const jobId = current.jobId;
    const uid = userId();
    if (!jobId || !uid) return;
    try {
      $("btnDispatch").disabled = true;
      const out = await apiFetch(`${API}/ai/jobs/${encodeURIComponent(jobId)}/dispatch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: uid }),
      });
      if (out && out.ok === false) {
        const wait = out.retry_in_sec ? `，建议${Number(out.retry_in_sec) || 0}s后再试` : "";
        toast(`派发失败${wait}`);
      } else {
        toast("已重新派发");
      }
      await refreshAll();
    } catch (e) {
      toast(`派发失败：${formatErr(e)}`);
    } finally {
      try { $("btnDispatch").disabled = false; } catch (_) {}
    }
  }

  async function loadPreview() {
    const pid = Number(current.postId || 0) || 0;
    const uid = userId();
    if (!pid || !uid) return;
    const post = await apiFetch(`${API}/posts/${pid}?user_id=${uid}`);
    const mp4 = post.mp4_url ? String(post.mp4_url) : "";
    const hls = post.video_url ? String(post.video_url) : "";
    const cover = post.cover_url ? String(post.cover_url) : `${API}/media/post-thumb/${pid}?v=${Date.now()}`;
    const tracks = post.subtitle_tracks && Array.isArray(post.subtitle_tracks) ? post.subtitle_tracks : [];
    const src = mp4 || (hls.endsWith(".m3u8") ? "" : hls) || "";
    const ve = $("videoEl");
    if (cover) {
      try { ve.poster = cover; } catch (_) {}
    }
    applySubtitleTracks(tracks);
    if (src) {
      if (ve.src !== src) ve.src = src;
      $("mediaBadge").textContent = mp4 ? "MP4" : "URL";
    } else {
      $("mediaBadge").textContent = "等待生成";
      try { ve.removeAttribute("src"); ve.load(); } catch (_) {}
    }
    try { updateDownloadUI(post); } catch (_) {}
  }

  function updateDownloadUI(post) {
    const btn = $("btnToggleDownload");
    const dl = $("btnDownloadPost");
    if (!btn || !dl) return;
    const enabled = !!(post && post.download_enabled);
    btn.dataset.enabled = enabled ? "1" : "0";
    btn.textContent = enabled ? "下载：开" : "下载：关";
    dl.disabled = false;
  }

  async function toggleDownloadSetting() {
    const pid = Number(current.postId || 0) || 0;
    const uid = userId();
    if (!pid || !uid) return;
    const btn = $("btnToggleDownload");
    if (!btn) return;
    const cur = String(btn.dataset.enabled || "0") === "1";
    const next = !cur;
    try {
      btn.disabled = true;
      const out = await apiFetch(`${API}/posts/${pid}/download/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: uid, download_enabled: next }),
      });
      btn.dataset.enabled = out && out.download_enabled ? "1" : "0";
      btn.textContent = out && out.download_enabled ? "下载：开" : "下载：关";
      toast(out && out.download_enabled ? "已开启下载" : "已关闭下载");
      await refreshAll();
    } catch (e) {
      toast(`设置失败：${formatErr(e)}`);
    } finally {
      btn.disabled = false;
    }
  }

  async function downloadCurrentPost() {
    const pid = Number(current.postId || 0) || 0;
    const uid = userId();
    if (!pid || !uid) return;
    try {
      const out = await apiFetch(`${API}/posts/${pid}/download`);
      if (out && out.kind === "image_text" && Array.isArray(out.files) && out.files.length > 0) {
        const ok = confirm(`将下载${out.files.length}张图片，是否继续？`);
        if (!ok) return;
        out.files.slice(0, 30).forEach((u, i) => {
          setTimeout(() => {
            try {
              const a = document.createElement("a");
              a.href = String(u);
              a.target = "_blank";
              a.rel = "noopener";
              a.click();
            } catch (_) {}
          }, 160 * i);
        });
        toast("已开始下载");
        return;
      }
      const url = out && out.url ? String(out.url) : "";
      if (!url) return toast("没有可下载的文件");
      try {
        const a = document.createElement("a");
        a.href = url;
        a.target = "_blank";
        a.rel = "noopener";
        if (out && out.filename) a.download = String(out.filename);
        document.body.appendChild(a);
        a.click();
        a.remove();
      } catch (_) {
        window.open(url, "_blank");
      }
    } catch (e) {
      toast(`下载失败：${formatErr(e)}`);
    }
  }

  function applySubtitleTracks(tracks) {
    const ve = $("videoEl");
    const sel = $("subSel");
    if (!ve || !sel) return;
    const existing = Array.from(ve.querySelectorAll("track"));
    for (const t of existing) t.remove();

    const list = Array.isArray(tracks) ? tracks : [];
    const items = list
      .map((t) => {
        const lang = t && t.lang !== undefined ? String(t.lang) : "";
        const label = t && t.label !== undefined ? String(t.label) : lang;
        const url = t && t.url !== undefined ? String(t.url) : "";
        const isDefault = !!(t && t.is_default);
        if (!lang || !url) return null;
        return { lang, label, url, isDefault };
      })
      .filter(Boolean);

    const opts = [`<option value="off">字幕：关</option>`].concat(
      items.map((it) => `<option value="${escapeHtml(it.lang)}">${escapeHtml("字幕：" + it.label)}</option>`)
    );
    sel.innerHTML = opts.join("");

    for (const it of items) {
      const tr = document.createElement("track");
      tr.kind = "subtitles";
      tr.srclang = it.lang;
      tr.label = it.label;
      tr.src = it.url;
      tr.default = it.isDefault;
      ve.appendChild(tr);
    }

    const def = items.find((x) => x.isDefault) || items[0] || null;
    sel.value = def ? def.lang : "off";
    syncSubtitleSelection();
  }

  function syncSubtitleSelection() {
    const ve = $("videoEl");
    const sel = $("subSel");
    if (!ve || !sel) return;
    const val = String(sel.value || "off");
    const tracks = ve.textTracks;
    for (let i = 0; i < tracks.length; i++) {
      const tr = tracks[i];
      try {
        tr.mode = val !== "off" && tr.language === val ? "showing" : "disabled";
      } catch (_) {}
    }
  }

  async function toggleMediaList() {
    const el = $("mediaList");
    if (!el) return;
    const show = el.style.display === "none";
    el.style.display = show ? "" : "none";
    if (show) await loadMediaVersions();
  }

  async function loadMediaVersions() {
    const pid = Number(current.postId || 0) || 0;
    const uid = userId();
    if (!pid || !uid) return;
    const out = await apiFetch(`${API}/posts/${pid}/media?user_id=${uid}`);
    const items = out && Array.isArray(out.items) ? out.items : [];
    $("mediaList").innerHTML = items
      .map((m) => {
        const id = Number(m.id || 0) || 0;
        const ver = String(m.version || "");
        const mp4 = m.mp4_url ? String(m.mp4_url) : "";
        const hls = m.hls_url ? String(m.hls_url) : "";
        const dt = m.created_at ? new Date(m.created_at).toLocaleString() : "";
        return `
          <div class="card">
            <div class="card-title">
              <div class="t">${escapeHtml(ver || ("media#" + id))}</div>
              <button class="btn btn-small" data-act="activate" data-id="${id}" data-ver="${escapeHtml(ver)}"><i class="fas fa-check"></i>激活</button>
            </div>
            <div class="card-sub"><span>${escapeHtml(dt)}</span><span>${escapeHtml(mp4 || hls || "")}</span></div>
          </div>
        `;
      })
      .join("");
    document.querySelectorAll("#mediaList [data-act='activate']").forEach((b) => {
      b.addEventListener("click", async () => {
        const id = Number(b.getAttribute("data-id") || 0) || 0;
        const ver = String(b.getAttribute("data-ver") || "").trim();
        await activateMedia(id, ver || null);
      });
    });
  }

  async function activateMedia(mediaId, version) {
    const pid = Number(current.postId || 0) || 0;
    const uid = userId();
    if (!pid || !uid) return;
    try {
      await apiFetch(`${API}/posts/${pid}/media/activate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: uid, media_asset_id: mediaId || null, version: version || null }),
      });
      toast("已切换版本");
      await loadPreview();
      await loadMediaVersions();
    } catch (e) {
      toast(`切换失败：${formatErr(e)}`);
    }
  }

  async function loadChat() {
    const jobId = current.jobId;
    const uid = userId();
    if (!jobId || !uid) return;
    const out = await apiFetch(`${API}/ai/jobs/${encodeURIComponent(jobId)}/chat?user_id=${uid}&limit=80`);
    const msgs = out && Array.isArray(out.messages) ? out.messages : [];
    $("chatLog").innerHTML = msgs
      .map((m) => {
        const role = String(m.role || "");
        const cls = role === "assistant" ? "assistant" : "user";
        const label = role === "assistant" ? "AI" : "我";
        const dt = m.created_at ? new Date(m.created_at).toLocaleString() : "";
        const content = String(m.content || "");
        return `
          <div class="msg ${cls}">
            <div class="r">${escapeHtml(label)} <span class="muted2">${escapeHtml(dt)}</span></div>
            <div class="c">${escapeHtml(content)}</div>
          </div>
        `;
      })
      .join("");
  }

  async function sendChat() {
    const jobId = current.jobId;
    const uid = userId();
    if (!jobId || !uid) return toast("未选择作品");
    const content = String($("chatInput").value || "").trim();
    if (!content) return;
    try {
      $("btnSendChat").disabled = true;
      await apiFetch(`${API}/ai/jobs/${encodeURIComponent(jobId)}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: uid, content }),
      });
      $("chatInput").value = "";
      await loadChat();
      toast("已发送");
    } catch (e) {
      toast(`发送失败：${formatErr(e)}`);
    } finally {
      $("btnSendChat").disabled = false;
    }
  }

  async function chatSuggest() {
    const jobId = current.jobId;
    const uid = userId();
    if (!jobId || !uid) return;
    try {
      $("btnChatSuggest").disabled = true;
      await apiFetch(`${API}/ai/jobs/${encodeURIComponent(jobId)}/chat/ai_suggest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: uid }),
      });
      toast("已触发 AI 建议（稍后查看脚本/事件流）");
    } catch (e) {
      toast(`触发失败：${formatErr(e)}`);
    } finally {
      $("btnChatSuggest").disabled = false;
    }
  }

  async function reviseFromChat() {
    const jobId = current.jobId;
    const uid = userId();
    const pid = Number(current.postId || 0) || 0;
    if (!jobId || !uid || !pid) return;
    try {
      $("btnReviseFromChat").disabled = true;
      const out = await apiFetch(`${API}/ai/jobs/${encodeURIComponent(jobId)}/revise_from_chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: uid }),
      });
      const newJob = out && out.job_id ? String(out.job_id) : "";
      const newPost = out && out.post_id ? Number(out.post_id) : 0;
      toast("已生成新版本");
      if (newPost) await selectPost(newPost);
      else if (newJob) {
        current.jobId = newJob;
        await refreshAll();
      }
    } catch (e) {
      toast(`生成失败：${formatErr(e)}`);
    } finally {
      $("btnReviseFromChat").disabled = false;
    }
  }

  async function suggestScript() {
    const jobId = current.jobId;
    const uid = userId();
    if (!jobId || !uid) return;
    try {
      $("btnSuggest").disabled = true;
      await apiFetch(`${API}/ai/jobs/${encodeURIComponent(jobId)}/chat/ai_suggest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: uid }),
      });
      toast("已触发 AI 建议（稍后在脚本/事件流查看）");
    } catch (e) {
      toast(`触发失败：${formatErr(e)}`);
    } finally {
      $("btnSuggest").disabled = false;
    }
  }

  function openPost() {
    const pid = Number(current.postId || 0) || 0;
    if (!pid) return;
    window.open(`/?post=${pid}`, "_blank");
  }

  function openProfile() {
    const uid = userId();
    if (!uid) return;
    window.open(`/?page=profile&user_id=${uid}`, "_blank");
  }

  function bind() {
    document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => showTab(t.getAttribute("data-tab"))));
    $("btnQuickAdmin").addEventListener("click", async () => {
      $("loginUser").value = "admin";
      $("loginPass").value = "admin123";
      try {
        $("btnLogin").disabled = true;
        await login("admin", "admin123");
        renderAuthUI();
        await initAfterLogin();
      } catch (e) {
        toast(`登录失败：${formatErr(e)}`);
      } finally {
        $("btnLogin").disabled = false;
      }
    });
    $("btnLogin").addEventListener("click", async () => {
      const u = String($("loginUser").value || "").trim();
      const p = String($("loginPass").value || "").trim();
      if (!u || !p) return toast("请输入用户名和密码");
      try {
        $("btnLogin").disabled = true;
        await login(u, p);
        renderAuthUI();
        await initAfterLogin();
      } catch (e) {
        toast(`登录失败：${formatErr(e)}`);
      } finally {
        $("btnLogin").disabled = false;
      }
    });
    $("btnLogout").addEventListener("click", () => {
      clearAuth();
      location.reload();
    });
    $("btnCreate").addEventListener("click", createJob);
    $("btnRefreshPosts").addEventListener("click", loadMyPosts);
    $("btnLoadMorePosts").addEventListener("click", () => loadMyPosts(false));
    $("postFilter").addEventListener("change", loadMyPosts);
    $("btnReloadPreview").addEventListener("click", loadPreview);
    try { $("subSel").addEventListener("change", syncSubtitleSelection); } catch (_) {}
    $("btnListMedia").addEventListener("click", toggleMediaList);
    $("btnOpenPost").addEventListener("click", openPost);
    try { $("btnToggleDownload").addEventListener("click", toggleDownloadSetting); } catch (_) {}
    try { $("btnDownloadPost").addEventListener("click", downloadCurrentPost); } catch (_) {}
    $("btnOpenInProfile").addEventListener("click", openProfile);
    $("btnCancel").addEventListener("click", cancelJob);
    $("btnDispatch").addEventListener("click", dispatchJob);
    $("btnSaveDraft").addEventListener("click", saveDraft);
    $("btnReloadHistory").addEventListener("click", loadHistory);
    $("toggleRaw").addEventListener("change", loadDraft);
    $("btnRerun").addEventListener("click", rerunFromDraft);
    $("btnSuggest").addEventListener("click", suggestScript);
    $("btnReloadChat").addEventListener("click", loadChat);
    $("btnSendChat").addEventListener("click", sendChat);
    $("btnChatSuggest").addEventListener("click", chatSuggest);
    $("btnReviseFromChat").addEventListener("click", reviseFromChat);
    $("btnOpenPost").disabled = true;
    $("btnCancel").disabled = true;
  }

  async function initAfterLogin() {
    await loadCategories();
    await loadMediaOptions();
    await loadMyPosts();
  }

  async function bootstrap() {
    bind();
    renderAuthUI();
    await loadCategories();
    await loadMediaOptions();
    if (token() && userId()) await initAfterLogin();
  }

  window.addEventListener("beforeunload", () => {
    if (current.evSource) {
      try { current.evSource.close(); } catch (_) {}
    }
  });

  bootstrap().catch(() => {});
})();
