(() => {
  const API = "/api/v1";
  const $ = (id) => document.getElementById(id);

  let current = { postId: null, jobId: null, evSource: null, lastEv: 0, evRetryMs: 800, voiceSampleUrl: null, avatarSampleUrl: null };
  let postState = { items: [], cursor: null, done: false, loading: false };
  let worksViewMode = "card";
  let applyLayoutPreset = null;
  let resetWorkspaceLayout = null;

  function token() {
    try { return localStorage.getItem("token") || ""; } catch (_) { return ""; }
  }
  function ensureUserIdFromToken() {
    try {
      const uid0 = Number(localStorage.getItem("user_id") || 0) || 0;
      if (uid0) return uid0;
    } catch (_) {}
    try {
      const t = token();
      if (!t) return 0;
      const parts = String(t).split(".");
      if (parts.length < 2) return 0;
      let p = String(parts[1] || "");
      p = p.replace(/-/g, "+").replace(/_/g, "/");
      while (p.length % 4) p += "=";
      const jsonStr = atob(p);
      const obj = JSON.parse(jsonStr || "{}");
      const uid = Number(obj && obj.sub ? obj.sub : 0) || 0;
      if (uid) {
        try { localStorage.setItem("user_id", String(uid)); } catch (_) {}
      }
      return uid;
    } catch (_) {
      return 0;
    }
  }
  function userId() {
    try {
      const uid = Number(localStorage.getItem("user_id") || 0) || 0;
      if (uid) return uid;
    } catch (_) {}
    return ensureUserIdFromToken();
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

  function applyTheme(theme) {
    const t = theme === "light" ? "light" : "dark";
    try { document.body.setAttribute("data-theme", t); } catch (_) {}
    try { localStorage.setItem("studio_theme", t); } catch (_) {}
    const lab = $("themeLabel");
    if (lab) lab.textContent = t === "light" ? "深色" : "浅色";
  }

  function applyTitleTone(tone) {
    const t = tone === "soft" ? "soft" : "pure";
    try { document.body.setAttribute("data-title-tone", t); } catch (_) {}
    try { localStorage.setItem("studio_title_tone", t); } catch (_) {}
    const lab = $("titleToneLabel");
    if (lab) lab.textContent = t === "soft" ? "淡红" : "纯红";
  }

  function applyBrand(brand) {
    const b = brand === "vivid" ? "vivid" : "stable";
    try { document.body.setAttribute("data-brand", b); } catch (_) {}
    try { localStorage.setItem("studio_brand", b); } catch (_) {}
    const lab = $("brandLabel");
    if (lab) lab.textContent = b === "vivid" ? "活力" : "稳重";
  }

  function initTheme() {
    let t = "dark";
    try { t = localStorage.getItem("studio_theme") || "dark"; } catch (_) {}
    applyTheme(t);
    let tt = "pure";
    try { tt = localStorage.getItem("studio_title_tone") || "pure"; } catch (_) {}
    applyTitleTone(tt);
    let den = "comfortable";
    try { den = localStorage.getItem("studio_density") || "comfortable"; } catch (_) {}
    applyDensity(den);
    let b = "stable";
    try { b = localStorage.getItem("studio_brand") || "stable"; } catch (_) {}
    applyBrand(b);
  }

  function applyDensity(density) {
    const d = density === "compact" ? "compact" : "comfortable";
    try { document.body.setAttribute("data-density", d); } catch (_) {}
    try { localStorage.setItem("studio_density", d); } catch (_) {}
    const lab = $("densityLabel");
    if (lab) lab.textContent = d === "compact" ? "紧凑" : "舒适";
  }

  function initWorksViewMode() {
    try { worksViewMode = localStorage.getItem("studio_works_view_mode") || "card"; } catch (_) { worksViewMode = "card"; }
    worksViewMode = worksViewMode === "compact" ? "compact" : "card";
    const list = $("postList");
    if (list) {
      list.classList.toggle("compact", worksViewMode === "compact");
    }
    const b1 = $("btnWorksCompact");
    const b2 = $("btnWorksCard");
    if (b1) b1.classList.toggle("btn-primary", worksViewMode === "compact");
    if (b2) b2.classList.toggle("btn-primary", worksViewMode !== "compact");
  }

  function setWorksViewMode(mode) {
    worksViewMode = mode === "compact" ? "compact" : "card";
    try { localStorage.setItem("studio_works_view_mode", worksViewMode); } catch (_) {}
    initWorksViewMode();
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

  async function uploadLocalFile(file) {
    if (!file) throw new Error("未选择文件");
    const form = new FormData();
    form.append("file", file);
    const t = token();
    const headers = t ? { Authorization: `Bearer ${t}` } : {};
    const res = await fetch(`${API}/upload/local`, { method: "POST", headers, body: form });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(String((data && data.detail) || "上传失败"));
    const url = String((data && data.url) || "").trim();
    if (!url) throw new Error("上传返回为空");
    return url;
  }

  function fmtStatus(st) {
    const s = String(st || "");
    if (s === "done") return ["done", "good"];
    if (s === "preview") return ["待发布", "warn"];
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
    try {
      const n = $("authName");
      if (n) n.textContent = ok ? `${uname || "User"} #${uid}` : "未登录";
    } catch (_) {}
    $("loginBox").style.display = ok ? "none" : "";
    $("createBox").style.display = ok ? "" : "none";
  }

  function updateBgmTrackFull() {
    const el = $("inBgmTrack");
    const box = $("bgmTrackFull");
    if (!el || !box) return;
    let label = "";
    try {
      const idx = Number(el.selectedIndex || 0);
      const opt = el.options && el.options[idx] ? el.options[idx] : null;
      label = opt ? String(opt.textContent || "") : "";
    } catch (_) {
      label = "";
    }
    const id = String(el.value || "").trim();
    const show = !!id && !!label.trim();
    box.textContent = show ? label : "";
    box.style.display = show ? "" : "none";
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
        try { el.onchange = updateBgmTrackFull; } catch (_) {}
        try { updateBgmTrackFull(); } catch (_) {}
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
    try {
      const st = String($("postFilter").value || "all");
      const limit = 30;
      const cursor = postState.cursor ? `&cursor=${encodeURIComponent(postState.cursor)}` : "";
      const out = await apiFetchRaw(`${API}/posts/user/${uid}?viewer_id=${uid}&ai_only=1&limit=${limit}${cursor}`);
      const arr = Array.isArray(out.data) ? out.data : [];
      const nextCursor = out.headers ? out.headers.get("x-next-cursor") : null;
      postState.cursor = nextCursor || null;
      if (!nextCursor || !arr.length) postState.done = true;
      postState.items = postState.items.concat(arr);

      const filtered = st === "all" ? postState.items : postState.items.filter((p) => String(p.status || "") === st);
      try {
        const wt = $("worksTitle");
        if (wt) wt.textContent = `5. 我的创作（${String(filtered.length)}）`;
      } catch (_) {}
      const cur = String(current.postId || "");
      const list = $("postList");
      if (list) list.classList.toggle("compact", worksViewMode === "compact");
      $("postList").innerHTML = filtered
        .map((p) => {
          const pid = Number(p.id || 0) || 0;
          const rawTitle = String(p.title || "");
          const title = (rawTitle && rawTitle.toLowerCase() !== "untitled") ? rawTitle : String(p.summary || `作品 #${pid}`);
          const s = String(p.status || "");
          const [lab, cls] = fmtStatus(s);
          const map = { done: "已发布", preview: "待发布", processing: "处理中", queued: "排队中", failed: "失败", cancelled: "已取消", returned: "已回退" };
          const statusText = map[String(lab || "").toLowerCase()] || lab || "-";
          const active = cur && String(pid) === cur ? "active" : "";
          const dlOn = !!p.download_enabled;
          return `
            <div class="card ${active}" data-post="${pid}">
              <div class="card-title">
                <div class="t">${escapeHtml(title)}</div>
              </div>
              <div class="row" style="margin-top:8px; justify-content:space-between;">
                <span class="status-pill ${cls}">${escapeHtml(statusText)}</span>
                <button class="btn btn-small" data-act="dl-toggle" data-post="${pid}" data-enabled="${dlOn ? "1" : "0"}">下载：${dlOn ? "开" : "关"}</button>
              </div>
            </div>
          `;
        })
        .join("");
      document.querySelectorAll("#postList .card").forEach((el) => {
        el.querySelectorAll('[data-act="dl-toggle"]').forEach((btn) => {
          btn.addEventListener("click", async (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            const pid = Number(btn.getAttribute("data-post") || 0) || 0;
            const cur = String(btn.getAttribute("data-enabled") || "0") === "1";
            if (!pid) return;
            await togglePostDownloadSetting(pid, !cur);
            btn.setAttribute("data-enabled", !cur ? "1" : "0");
            btn.textContent = `下载：${!cur ? "开" : "关"}`;
          });
        });
        el.addEventListener("click", () => {
          const pid = Number(el.getAttribute("data-post") || 0) || 0;
          if (pid) selectPost(pid);
        });
      });
      const more = $("btnLoadMorePosts");
      if (more) more.style.display = !postState.done ? "" : "none";
      return filtered;
    } catch (e) {
      $("postList").innerHTML = '<div class="muted" style="padding:10px 6px;">加载失败，请刷新或重新登录</div>';
      try { toast(String((e && e.message) || '加载失败')); } catch (_) {}
      postState.done = true;
      return [];
    } finally {
      postState.loading = false;
    }
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
    const tags = String(($("inTags") && $("inTags").value) || "").trim() || null;
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
    const voice_sample_url = String(current.voiceSampleUrl || "").trim() || null;
    const avatar_video_url = String(current.avatarSampleUrl || "").trim() || null;
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
          tags,
          category,
          custom_instructions,
          voice_sample_url,
          avatar_video_url,
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
    const rawTitle = String(post.title || "");
    const title = (!rawTitle || rawTitle.toLowerCase() === "untitled") ? "" : rawTitle;
    $("jobTitle").textContent = String(title || post.summary || `作品 #${pid}`);
    $("postId").textContent = String(pid);
    const st = String(post.status || "");
    current.postStatus = st;
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
    $("btnPublishPost").disabled = st !== "preview";
    $("btnOpenInProfile").disabled = !uid;
    $("btnCancel").disabled = !jobId;
    if (jobId) await loadJob(jobId);
  }

  async function loadJob(jobId) {
    const uid = userId();
    const job = await apiFetch(`${API}/ai/jobs/${encodeURIComponent(jobId)}?user_id=${uid}`);
    const shown = (String(current.postStatus || "") === "preview" && String(job.status || "") === "done") ? "preview" : job.status;
    const [lab, cls] = fmtStatus(shown);
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
      // If job is already done, refresh post status to enable publish button
      if (job.status === "done") {
        setTimeout(() => loadPostAndJob(), 500);
      }

      if (current.evSource && String(current.evJobId || "") === String(jobId || "")) {
        try { current.evSource.close(); } catch (_) {}
        current.evSource = null;
      }
      try { $("evHint").textContent = "任务已结束"; } catch (_) {}
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
    $("evHint").textContent = "SSE 连接中";
    es.onopen = () => {
      try { $("evHint").textContent = "SSE 已连接"; } catch (_) {}
    };
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
        
        // Auto-refresh post status when job is done to enable publish button
        if (st === "done") {
          // Add a small delay to ensure backend state is consistent
          setTimeout(() => {
             loadPostAndJob();
          }, 1000);
        }
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
          body: JSON.stringify({ user_id: uid, post_type: "video", content: "", title: "", category: "", subtitle_mode: "off" }),
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
    
    // Allow HLS or MP4
    const src = hls || mp4 || "";
    const ve = $("videoEl");
    
    // Explicitly reset poster first
    try { ve.removeAttribute("poster"); } catch (_) {}
    
    if (cover) {
      try { ve.poster = cover; } catch (_) {}
    }
    applySubtitleTracks(tracks);
    
    if (src) {
      // Clean up previous HLS instance if exists
      if (current.hls) {
        try { current.hls.destroy(); } catch(_) {}
        current.hls = null;
      }

      if (src.endsWith(".m3u8")) {
        if (window.Hls && Hls.isSupported()) {
          const hlsObj = new Hls();
          hlsObj.loadSource(src);
          hlsObj.attachMedia(ve);
          current.hls = hlsObj;
        } else if (ve.canPlayType('application/vnd.apple.mpegurl')) {
          // Native support (Safari)
          ve.src = src;
        } else {
          // Fallback
          ve.src = src;
        }
      } else {
        if (ve.src !== src) ve.src = src;
      }
      
      // Ensure controls are enabled for CC button
      ve.controls = true;
      ve.crossOrigin = "anonymous";
    } else {
      try { ve.removeAttribute("src"); ve.load(); } catch (_) {}
    }
    try { updateDownloadUI(post); } catch (_) {}
  }

  async function togglePostDownloadSetting(pid, next) {
    const uid = userId();
    if (!pid || !uid) return;
    await apiFetch(`${API}/posts/${pid}/download/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: uid, download_enabled: !!next }),
    });
  }

  async function publishCurrentPost() {
    const pid = Number(current.postId || 0) || 0;
    const uid = userId();
    if (!pid || !uid) return;
    const st = String(current.postStatus || "");
    if (st !== "preview") {
      toast("当前作品无需发布");
      return;
    }
    try {
      await apiFetch(`${API}/posts/${pid}/publish`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: uid }),
      });
      toast("发布成功");
      await refreshAll();
      await loadMyPosts();
    } catch (e) {
      toast(`发布失败：${e && e.message ? e.message : e}`);
    }
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
        if (out.files.length > 1) {
          const ok = confirm(`将下载${out.files.length}张图片，是否继续？`);
          if (!ok) return;
        }
        out.files.slice(0, 30).forEach((u, i) => {
          setTimeout(() => {
            try {
              const href = String(u || "").trim();
              if (!href) return;
              const a = document.createElement("a");
              a.href = href;
              a.target = "_blank";
              a.rel = "noopener";
              try {
                const clean = href.split("?")[0] || href;
                const name = clean.split("/").pop() || "";
                if (name) a.download = name;
              } catch (_) {}
              document.body.appendChild(a);
              a.click();
              a.remove();
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
    const postId = Number(current.postId || 0) || 0;
    const uid = userId();
    if ((!jobId && !postId) || !uid) return;
    const out = postId
      ? await apiFetch(`${API}/ai/posts/${encodeURIComponent(String(postId))}/chat?user_id=${uid}&limit=200`)
      : await apiFetch(`${API}/ai/jobs/${encodeURIComponent(jobId)}/chat?user_id=${uid}&limit=80`);
    const msgs = out && Array.isArray(out.messages) ? out.messages : [];
    $("chatLog").innerHTML = msgs
      .map((m) => {
        const role = String(m.role || "");
        const cls = role === "assistant" ? "assistant" : "user";
        const label = role === "assistant" ? "AI" : "我";
        const dt = m.created_at ? new Date(m.created_at).toLocaleString() : "";
        const content = String(m.content || "");
        const jid = m.job_id ? String(m.job_id) : "";
        return `
          <div class="msg ${cls}">
            <div class="r">${escapeHtml(label)} <span class="muted2">${escapeHtml(dt)}${jid ? " · " + escapeHtml(jid.slice(0, 8)) : ""}</span></div>
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

  function relocateWorkbenchBlocks() {
    try {
      const create = $("createBox");
      const mount = $("createMount");
      if (create && mount && create.parentElement !== mount) mount.appendChild(create);
    } catch (_) {}
  }

  function initWorkspaceModules() {
    const board = $("workspaceBoard");
    if (!board) return;
    const key = "studio_workspace_order_v4";
    const presetKey = "studio_workspace_preset_v4";
    const presets = {
      create: ["create", "task", "preview", "chat", "works"],
      review: ["task", "preview", "works", "chat", "create"],
      chat: ["chat", "preview", "task", "create", "works"],
    };
    const defaults = presets.create.slice();
    const modules = Array.from(board.querySelectorAll(".ws-module[data-module]"));
    const byKey = new Map(modules.map((m) => [String(m.getAttribute("data-module") || ""), m]));
    const applyOrder = (order, persist = true) => {
      const used = new Set();
      (Array.isArray(order) ? order : defaults).forEach((k) => {
        const el = byKey.get(String(k || ""));
        if (!el || used.has(k)) return;
        board.appendChild(el);
        used.add(k);
      });
      defaults.forEach((k) => {
        const el = byKey.get(k);
        if (!el || used.has(k)) return;
        board.appendChild(el);
        used.add(k);
      });
      modules.forEach((m) => {
        const k = String(m.getAttribute("data-module") || "");
        if (!k || used.has(k)) return;
        board.appendChild(m);
      });
      if (persist) {
        try { localStorage.setItem(key, JSON.stringify(Array.from(board.querySelectorAll(".ws-module[data-module]")).map((m) => String(m.getAttribute("data-module") || "")).filter(Boolean))); } catch (_) {}
      }
    };

    try {
      const presetSel = $("layoutPreset");
      const raw = localStorage.getItem(key);
      const presetSaved = String(localStorage.getItem(presetKey) || "custom");
      if (presetSel) presetSel.value = presetSaved;
      const saved = raw ? JSON.parse(raw) : null;
      const order = Array.isArray(saved) && saved.length ? saved.map((x) => String(x || "")) : defaults;
      applyOrder(order, false);
    } catch (_) {}

    let dragging = null;
    const saveOrder = () => {
      try {
        const order = Array.from(board.querySelectorAll(".ws-module[data-module]")).map((m) => String(m.getAttribute("data-module") || "")).filter(Boolean);
        localStorage.setItem(key, JSON.stringify(order));
      } catch (_) {}
    };
    board.querySelectorAll(".ws-module[data-module]").forEach((mod) => {
      const handle = mod.querySelector(".drag-handle");
      if (handle) {
        handle.addEventListener("mousedown", () => {
          mod.dataset.dragReady = "1";
        });
        handle.addEventListener("mouseup", () => {
          delete mod.dataset.dragReady;
        });
      }
      mod.addEventListener("dragstart", (e) => {
        if (mod.dataset.dragReady !== "1") {
          e.preventDefault();
          return;
        }
        dragging = mod;
        mod.classList.add("dragging");
        try { e.dataTransfer.effectAllowed = "move"; } catch (_) {}
      });
      mod.addEventListener("dragend", () => {
        mod.classList.remove("dragging");
        delete mod.dataset.dragReady;
        dragging = null;
        try { localStorage.setItem(presetKey, "custom"); } catch (_) {}
        const presetSel = $("layoutPreset");
        if (presetSel) presetSel.value = "custom";
        saveOrder();
      });
    });
    board.addEventListener("dragover", (e) => {
      if (!dragging) return;
      e.preventDefault();
      const el = document.elementFromPoint(Number(e.clientX || 0), Number(e.clientY || 0));
      const target = el && el.closest ? el.closest(".ws-module[data-module]") : null;
      if (!target || target === dragging) return;
      const rect = target.getBoundingClientRect();
      const before = Number(e.clientY || 0) < (rect.top + rect.height / 2);
      board.insertBefore(dragging, before ? target : target.nextSibling);
    });
    board.addEventListener("drop", (e) => {
      if (!dragging) return;
      e.preventDefault();
      saveOrder();
    });

    applyLayoutPreset = (name) => {
      const n = String(name || "custom");
      if (n === "custom") return;
      const order = presets[n] || presets.create;
      applyOrder(order, true);
      try { localStorage.setItem(presetKey, n); } catch (_) {}
      const presetSel = $("layoutPreset");
      if (presetSel) presetSel.value = n;
    };
    resetWorkspaceLayout = () => {
      applyOrder(defaults, true);
      try { localStorage.removeItem(key); } catch (_) {}
      try { localStorage.setItem(presetKey, "create"); } catch (_) {}
    };
  }

  async function uploadVoiceSample() {
    const ipt = document.createElement("input");
    ipt.type = "file";
    ipt.accept = "audio/*";
    ipt.onchange = async () => {
      try {
        const f = ipt.files && ipt.files[0] ? ipt.files[0] : null;
        if (!f) return;
        const url = await uploadLocalFile(f);
        current.voiceSampleUrl = url;
        if ($("voiceSampleHint")) $("voiceSampleHint").textContent = "已上传";
        toast("语音样本上传成功");
      } catch (e) {
        toast(`语音样本上传失败：${formatErr(e)}`);
      }
    };
    ipt.click();
  }

  async function uploadAvatarSample() {
    const ipt = document.createElement("input");
    ipt.type = "file";
    ipt.accept = "video/*";
    ipt.onchange = async () => {
      try {
        const f = ipt.files && ipt.files[0] ? ipt.files[0] : null;
        if (!f) return;
        const url = await uploadLocalFile(f);
        current.avatarSampleUrl = url;
        if ($("avatarSampleHint")) $("avatarSampleHint").textContent = "已上传";
        toast("视频样本上传成功");
      } catch (e) {
        toast(`视频样本上传失败：${formatErr(e)}`);
      }
    };
    ipt.click();
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
    $("btnCreate").addEventListener("click", createJob);
    try { $("btnTheme").addEventListener("click", () => applyTheme(document.body.getAttribute("data-theme") === "light" ? "dark" : "light")); } catch (_) {}
    try { $("btnTitleTone").addEventListener("click", () => applyTitleTone(document.body.getAttribute("data-title-tone") === "soft" ? "pure" : "soft")); } catch (_) {}
    try { $("btnBrand").addEventListener("click", () => applyBrand(document.body.getAttribute("data-brand") === "vivid" ? "stable" : "vivid")); } catch (_) {}
    try { $("btnDensity").addEventListener("click", () => applyDensity(document.body.getAttribute("data-density") === "compact" ? "comfortable" : "compact")); } catch (_) {}
    try { $("btnResetLayout").addEventListener("click", () => { if (resetWorkspaceLayout) resetWorkspaceLayout(); }); } catch (_) {}
    try { $("layoutPreset").addEventListener("change", (e) => { if (applyLayoutPreset) applyLayoutPreset(e && e.target ? e.target.value : "custom"); }); } catch (_) {}
    try { $("btnWorksCompact").addEventListener("click", () => setWorksViewMode("compact")); } catch (_) {}
    try { $("btnWorksCard").addEventListener("click", () => setWorksViewMode("card")); } catch (_) {}
    try { $("btnUploadVoiceSample").addEventListener("click", uploadVoiceSample); } catch (_) {}
    try { $("btnUploadAvatarSample").addEventListener("click", uploadAvatarSample); } catch (_) {}
    $("btnRefreshPosts").addEventListener("click", loadMyPosts);
    $("btnLoadMorePosts").addEventListener("click", () => loadMyPosts(false));
    $("postFilter").addEventListener("change", loadMyPosts);
    $("btnReloadPreview").addEventListener("click", loadPreview);
    try { $("subSel").addEventListener("change", syncSubtitleSelection); } catch (_) {}
    $("btnListMedia").addEventListener("click", toggleMediaList);
    $("btnOpenPost").addEventListener("click", openPost);
    try { $("btnPublishPost").addEventListener("click", publishCurrentPost); } catch (_) {}
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
    try { $("btnPublishPost").disabled = true; } catch (_) {}
    $("btnCancel").disabled = true;
  }

  async function initAfterLogin() {
    await loadCategories();
    await loadMediaOptions();
    const list = await loadMyPosts();
    const cur = Number(current.postId || 0) || 0;
    if (!cur && Array.isArray(list) && list.length) {
      const first = list[0];
      const pid = first && first.id ? Number(first.id || 0) || 0 : 0;
      if (pid) await selectPost(pid);
    }
  }

  async function bootstrap() {
    initTheme();
    initWorksViewMode();
    relocateWorkbenchBlocks();
    initWorkspaceModules();
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
