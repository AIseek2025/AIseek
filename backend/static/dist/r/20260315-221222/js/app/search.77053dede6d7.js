Object.assign(window.app, {
    __searchEscapeMap: {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    },

    escapeHtml: function(s) {
        const map = this.__searchEscapeMap;
        return String(s || '').replace(/[&<>"']/g, (c) => map[c]);
    },

    searchNormalizeHistory: function(items) {
        if (!Array.isArray(items)) return [];
        return items.map(s => String(s || '').trim()).filter(Boolean);
    },

    getGlobalSearchInput: function() {
        return document.getElementById('global_search_input') || document.querySelector('.search-bar input');
    },

    getSearchHistory: function() {
        try {
            const raw = localStorage.getItem('search_history');
            const arr = JSON.parse(raw || '[]');
            return this.searchNormalizeHistory(arr);
        } catch (_) {
            return [];
        }
    },

    setSearchHistory: function(items) {
        try {
            const arr = this.searchNormalizeHistory(items);
            localStorage.setItem('search_history', JSON.stringify(arr.slice(0, 12)));
        } catch (_) {
        }
    },

    searchQualitySortPrefLoad: function() {
        if (this.__searchQualitySortPrefLoaded) return;
        this.__searchQualitySortPrefLoaded = true;
        try {
            const raw = String(localStorage.getItem('search_quality_sort_pref') || '').trim().toLowerCase();
            if (raw === 'quality' || raw === 'unrated') this.state.searchQualitySort = raw;
        } catch (_) {
        }
    },

    searchQualitySortPrefSave: function() {
        try {
            const mode = this.searchQualitySortMode();
            localStorage.setItem('search_quality_sort_pref', mode);
        } catch (_) {
        }
    },

    searchExportTemplateLoad: function() {
        if (this.__searchExportTemplateLoaded) return;
        this.__searchExportTemplateLoaded = true;
        try {
            const raw = String(localStorage.getItem('search_export_template_pref') || '').trim().toLowerCase();
            if (raw === 'standard' || raw === 'qa' || raw === 'lite') this.state.searchExportTemplate = raw;
        } catch (_) {
        }
    },

    searchExportTemplateSave: function() {
        try {
            const t = this.searchExportTemplateCurrent();
            localStorage.setItem('search_export_template_pref', t);
        } catch (_) {
        }
    },

    searchExportCustomColumnsLoad: function() {
        if (this.__searchExportCustomColumnsLoaded) return;
        this.__searchExportCustomColumnsLoaded = true;
        try {
            const raw = String(localStorage.getItem('search_export_custom_columns') || '').trim();
            if (raw) this.state.searchExportCustomColumns = raw;
        } catch (_) {
        }
    },

    searchExportCustomColumnsSave: function(raw) {
        try {
            const v = String(raw || '').trim();
            if (!v) localStorage.removeItem('search_export_custom_columns');
            else localStorage.setItem('search_export_custom_columns', v);
        } catch (_) {
        }
    },

    searchGetExportHistory: function() {
        try {
            const raw = localStorage.getItem('search_export_history');
            const arr = JSON.parse(raw || '[]');
            const list = Array.isArray(arr) ? arr : [];
            const out = [];
            for (let i = 0; i < list.length; i++) {
                const it = list[i] && typeof list[i] === 'object' ? list[i] : {};
                out.push({
                    at_ms: Number(it.at_ms || 0) || 0,
                    query: String(it.query || ''),
                    template: String(it.template || 'standard'),
                    count: Math.max(0, Number(it.count || 0) || 0),
                    filter: String(it.filter || 'all'),
                    sort: String(it.sort || 'default'),
                    search_mode: String(it.search_mode || 'all'),
                    quality_threshold: Math.max(1, Math.min(100, Math.round(Number(it.quality_threshold || 70) || 70))),
                    route_hash: String(it.route_hash || ''),
                    custom_columns: String(it.custom_columns || ''),
                    pinned: !!it.pinned,
                    pin_at_ms: Math.max(0, Number(it.pin_at_ms || 0) || 0),
                });
            }
            out.sort((a, b) => {
                if ((a.pinned ? 1 : 0) !== (b.pinned ? 1 : 0)) return (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0);
                if (a.pinned && b.pinned && a.pin_at_ms !== b.pin_at_ms) return b.pin_at_ms - a.pin_at_ms;
                return b.at_ms - a.at_ms;
            });
            return out;
        } catch (_) {
            return [];
        }
    },

    searchSetExportHistory: function(items) {
        try {
            const arr = Array.isArray(items) ? items : [];
            localStorage.setItem('search_export_history', JSON.stringify(arr.slice(0, 50)));
        } catch (_) {
        }
    },

    searchIsExportHistoryPanelOpen: function() {
        const el = document.getElementById('search_export_history_panel');
        return !!(el && el.classList.contains('active'));
    },

    searchHistoryPanelKeyword: function() {
        return String(this.__searchHistoryPanelKeyword || '').trim().toLowerCase();
    },

    searchHistoryPanelPage: function() {
        const p = Math.max(1, Math.floor(Number(this.__searchHistoryPanelPage || 1) || 1));
        this.__searchHistoryPanelPage = p;
        return p;
    },

    searchHistoryPanelRange: function() {
        const v = String(this.__searchHistoryPanelRange || 'all').trim().toLowerCase();
        if (v === '1d' || v === '7d' || v === '30d' || v === '90d') return v;
        return 'all';
    },

    searchHistoryPanelSelection: function() {
        if (!(this.__searchHistoryPanelSelection instanceof Set)) this.__searchHistoryPanelSelection = new Set();
        return this.__searchHistoryPanelSelection;
    },

    searchGetHistoryViews: function() {
        try {
            const raw = localStorage.getItem('search_export_history_views');
            const arr = JSON.parse(raw || '[]');
            const list = Array.isArray(arr) ? arr : [];
            const out = [];
            for (let i = 0; i < list.length; i++) {
                const it = list[i] && typeof list[i] === 'object' ? list[i] : {};
                const name = String(it.name || '').trim();
                if (!name) continue;
                const rangeRaw = String(it.range || 'all').trim().toLowerCase();
                const range = (rangeRaw === '1d' || rangeRaw === '7d' || rangeRaw === '30d' || rangeRaw === '90d') ? rangeRaw : 'all';
                out.push({
                    name,
                    kw: String(it.kw || ''),
                    range,
                    created_at: Math.max(0, Number(it.created_at || 0) || 0),
                    pinned: !!it.pinned,
                    pin_at: Math.max(0, Number(it.pin_at || 0) || 0),
                });
            }
            out.sort((a, b) => {
                if ((a.pinned ? 1 : 0) !== (b.pinned ? 1 : 0)) return (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0);
                if (a.pinned && b.pinned && a.pin_at !== b.pin_at) return b.pin_at - a.pin_at;
                return b.created_at - a.created_at;
            });
            return out.slice(0, 20);
        } catch (_) {
            return [];
        }
    },

    searchSetHistoryViews: function(items) {
        try {
            const arr = Array.isArray(items) ? items : [];
            localStorage.setItem('search_export_history_views', JSON.stringify(arr.slice(0, 20)));
        } catch (_) {
        }
    },

    searchRenderHistoryViewSelect: function() {
        const sel = document.getElementById('search_export_history_view_select');
        if (!sel) return;
        const views = this.searchGetHistoryViews();
        let html = '<option value="">命名视图</option>';
        for (let i = 0; i < views.length; i++) {
            const v = views[i];
            html += `<option value="${this.escapeHtml(v.name)}">${v.pinned ? '📌 ' : ''}${this.escapeHtml(v.name)}</option>`;
        }
        sel.innerHTML = html;
        if (this.__searchHistoryViewActiveName) sel.value = this.__searchHistoryViewActiveName;
    },

    searchSaveHistoryCurrentView: function() {
        const nameRaw = window.prompt('请输入命名视图名称', String(this.__searchHistoryViewActiveName || '').trim());
        if (nameRaw === null) return;
        const name = String(nameRaw || '').trim();
        if (!name) {
            alert('名称不能为空');
            return;
        }
        const views = this.searchGetHistoryViews();
        const kw = String(this.__searchHistoryPanelKeyword || '').trim();
        const range = this.searchHistoryPanelRange();
        const now = Date.now();
        const next = [];
        let replaced = false;
        for (let i = 0; i < views.length; i++) {
            const v = views[i];
            if (v.name === name) {
                next.push({ name, kw, range, created_at: now, pinned: !!v.pinned, pin_at: Math.max(0, Number(v.pin_at || 0) || 0) });
                replaced = true;
            } else next.push(v);
        }
        if (!replaced) next.unshift({ name, kw, range, created_at: now, pinned: false, pin_at: 0 });
        this.searchSetHistoryViews(next);
        this.__searchHistoryViewActiveName = name;
        this.searchRenderHistoryViewSelect();
        alert('命名视图已保存');
    },

    searchApplyHistoryNamedView: function(v) {
        const name = String(v || '').trim();
        if (!name) return;
        const views = this.searchGetHistoryViews();
        const got = views.find((x) => x && x.name === name);
        if (!got) return;
        this.__searchHistoryViewActiveName = name;
        this.__searchHistoryPanelKeyword = String(got.kw || '');
        this.__searchHistoryPanelRange = String(got.range || 'all');
        this.__searchHistoryPanelPage = 1;
        const input = document.getElementById('search_export_history_filter_input');
        if (input) input.value = this.__searchHistoryPanelKeyword;
        const rangeSel = document.getElementById('search_export_history_range_select');
        if (rangeSel) rangeSel.value = this.__searchHistoryPanelRange;
        this.searchRenderHistoryViewSelect();
        this.searchRenderExportHistoryPanel();
    },

    searchDeleteHistoryNamedView: function() {
        const name = String(this.__searchHistoryViewActiveName || '').trim();
        if (!name) {
            alert('请先选择命名视图');
            return;
        }
        const ok = window.confirm(`确认删除命名视图「${name}」吗？`);
        if (!ok) return;
        const views = this.searchGetHistoryViews().filter((x) => x && x.name !== name);
        this.searchSetHistoryViews(views);
        this.__searchHistoryViewActiveName = '';
        this.searchRenderHistoryViewSelect();
    },

    searchToggleHistoryNamedViewPin: function() {
        const name = String(this.__searchHistoryViewActiveName || '').trim();
        if (!name) {
            alert('请先选择命名视图');
            return;
        }
        const views = this.searchGetHistoryViews();
        const now = Date.now();
        const next = [];
        let toggled = false;
        for (let i = 0; i < views.length; i++) {
            const v = views[i];
            if (v.name === name) {
                const pinned = !v.pinned;
                next.push({ ...v, pinned, pin_at: pinned ? now : 0 });
                toggled = true;
            } else next.push(v);
        }
        if (!toggled) return;
        this.searchSetHistoryViews(next);
        this.searchRenderHistoryViewSelect();
    },

    searchExportHistoryViewsJson: function() {
        const views = this.searchGetHistoryViews();
        if (!views.length) {
            alert('暂无可导出的命名视图');
            return;
        }
        const payload = {
            schema: 'search_history_views_v1',
            exported_at_ms: Date.now(),
            views: views.map((v) => ({
                name: String(v.name || ''),
                kw: String(v.kw || ''),
                range: String(v.range || 'all'),
                pinned: !!v.pinned,
            })),
        };
        this.searchDownloadTextFile(`search_history_views_${Date.now()}.json`, JSON.stringify(payload, null, 2), 'application/json;charset=utf-8;');
    },

    searchTriggerHistoryViewsImport: function() {
        const input = document.getElementById('search_history_views_import_input');
        if (!input) return;
        input.value = '';
        input.click();
    },

    searchMergeImportedHistoryViews: function(items) {
        const list = Array.isArray(items) ? items : [];
        if (!list.length) return 0;
        const cur = this.searchGetHistoryViews();
        const map = new Map();
        for (let i = 0; i < cur.length; i++) map.set(cur[i].name, cur[i]);
        const now = Date.now();
        let merged = 0;
        for (let i = 0; i < list.length; i++) {
            const it = list[i] && typeof list[i] === 'object' ? list[i] : {};
            const name = String(it.name || '').trim();
            if (!name) continue;
            const rangeRaw = String(it.range || 'all').trim().toLowerCase();
            const range = (rangeRaw === '1d' || rangeRaw === '7d' || rangeRaw === '30d' || rangeRaw === '90d') ? rangeRaw : 'all';
            map.set(name, {
                name,
                kw: String(it.kw || ''),
                range,
                created_at: now,
                pinned: !!it.pinned,
                pin_at: it.pinned ? now : 0,
            });
            merged += 1;
        }
        if (!merged) return 0;
        const next = Array.from(map.values()).slice(0, 20);
        this.searchSetHistoryViews(next);
        this.searchRenderHistoryViewSelect();
        return merged;
    },

    searchEncodeHistoryViewsShareCode: function(payload) {
        try {
            const text = JSON.stringify(payload || {});
            const utf8 = unescape(encodeURIComponent(text));
            const b64 = btoa(utf8).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
            return `SV1.${b64}`;
        } catch (_) {
            return '';
        }
    },

    searchHistoryViewsShareCodeMaxAgeMs: function() {
        return 7 * 24 * 3600 * 1000;
    },

    searchHistoryViewsShareDigest: function(payload) {
        try {
            const p = payload && typeof payload === 'object' ? payload : {};
            const canonical = {
                schema: String(p.schema || ''),
                issued_at_ms: Math.max(0, Number(p.issued_at_ms || 0) || 0),
                expires_at_ms: Math.max(0, Number(p.expires_at_ms || 0) || 0),
                views: Array.isArray(p.views) ? p.views.map((v) => ({
                    name: String((v && v.name) || ''),
                    kw: String((v && v.kw) || ''),
                    range: String((v && v.range) || 'all'),
                    pinned: !!(v && v.pinned),
                })) : [],
            };
            const s = JSON.stringify(canonical);
            let h = 2166136261;
            for (let i = 0; i < s.length; i++) {
                h ^= s.charCodeAt(i);
                h = Math.imul(h, 16777619);
            }
            return (h >>> 0).toString(16).padStart(8, '0');
        } catch (_) {
            return '';
        }
    },

    searchDecodeHistoryViewsShareCode: function(code) {
        const raw = String(code || '').trim();
        if (!raw || raw.indexOf('SV1.') !== 0) return { ok: false, error: 'format' };
        try {
            const b64url = raw.slice(4);
            const b64 = b64url.replace(/-/g, '+').replace(/_/g, '/');
            const padLen = (4 - (b64.length % 4)) % 4;
            const padded = b64 + '='.repeat(padLen);
            const utf8 = atob(padded);
            const text = decodeURIComponent(escape(utf8));
            const parsed = JSON.parse(text || '{}');
            if (!parsed || typeof parsed !== 'object') return { ok: false, error: 'payload' };
            const schema = String(parsed.schema || '');
            if (schema !== 'search_history_views_share_v1') return { ok: false, error: 'schema' };
            const issuedAt = Math.max(0, Number(parsed.issued_at_ms || 0) || 0);
            const expiresAt = Math.max(0, Number(parsed.expires_at_ms || 0) || 0);
            if (!issuedAt || !expiresAt || expiresAt < issuedAt) return { ok: false, error: 'time' };
            const now = Date.now();
            if (now > expiresAt) return { ok: false, error: 'expired' };
            const maxAge = this.searchHistoryViewsShareCodeMaxAgeMs();
            if (issuedAt + maxAge < now) return { ok: false, error: 'stale' };
            const sig = String(parsed.sig || '').trim();
            const got = this.searchHistoryViewsShareDigest(parsed);
            if (!sig || !got || sig !== got) return { ok: false, error: 'sig' };
            return { ok: true, payload: parsed };
        } catch (_) {
            return { ok: false, error: 'decode' };
        }
    },

    searchExportHistoryViewsShareCode: async function() {
        const views = this.searchGetHistoryViews();
        if (!views.length) {
            alert('暂无可分享的命名视图');
            return;
        }
        const payload = {
            schema: 'search_history_views_share_v1',
            issued_at_ms: Date.now(),
            expires_at_ms: Date.now() + this.searchHistoryViewsShareCodeMaxAgeMs(),
            views: views.map((v) => ({
                name: String(v.name || ''),
                kw: String(v.kw || ''),
                range: String(v.range || 'all'),
                pinned: !!v.pinned,
            })),
        };
        payload.sig = this.searchHistoryViewsShareDigest(payload);
        const code = this.searchEncodeHistoryViewsShareCode(payload);
        if (!code) {
            alert('生成共享码失败');
            return;
        }
        let copied = false;
        try {
            if (navigator && navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
                await navigator.clipboard.writeText(code);
                copied = true;
            }
        } catch (_) {
        }
        if (copied) {
            alert('共享码已复制到剪贴板');
            return;
        }
        window.prompt('复制以下共享码', code);
    },

    searchBuildHistoryViewsShareUrl: function(code) {
        const c = String(code || '').trim();
        if (!c) return '';
        const base = `${location.origin}${location.pathname}${location.search}`;
        return `${base}#/search?svc=${encodeURIComponent(c)}`;
    },

    searchBuildHistoryViewsShortShareUrl: function(key) {
        const k = String(key || '').trim();
        if (!k) return '';
        return `${location.origin}/s/${encodeURIComponent(k)}`;
    },

    searchBuildHistoryViewsSharePayload: function() {
        const views = this.searchGetHistoryViews();
        if (!views.length) return null;
        const payload = {
            schema: 'search_history_views_share_v1',
            issued_at_ms: Date.now(),
            expires_at_ms: Date.now() + this.searchHistoryViewsShareCodeMaxAgeMs(),
            views: views.map((v) => ({
                name: String(v.name || ''),
                kw: String(v.kw || ''),
                range: String(v.range || 'all'),
                pinned: !!v.pinned,
            })),
        };
        payload.sig = this.searchHistoryViewsShareDigest(payload);
        return payload;
    },

    searchCopyHistoryViewsShareLink: async function() {
        const payload = this.searchBuildHistoryViewsSharePayload();
        if (!payload) {
            alert('暂无可分享的命名视图');
            return;
        }
        const code = this.searchEncodeHistoryViewsShareCode(payload);
        let link = '';
        try {
            const res = await this.apiRequest('POST', '/api/v1/search/share-views', { code }, { cancel_key: 'search:share:create', dedupe_key: 'search:share:create' });
            if (res.ok) {
                const data = await res.json();
                const key = String((data && data.key) || '').trim();
                if (key) link = this.searchBuildHistoryViewsShortShareUrl(key);
            }
        } catch (_) {
        }
        if (!link) link = this.searchBuildHistoryViewsShareUrl(code);
        if (!link) {
            alert('生成分享链接失败');
            return;
        }
        let copied = false;
        try {
            if (navigator && navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
                await navigator.clipboard.writeText(link);
                copied = true;
            }
        } catch (_) {
        }
        if (copied) alert('分享链接已复制到剪贴板');
        else window.prompt('复制以下分享链接', link);
    },

    searchShowHistoryViewsShareQr: async function() {
        const payload = this.searchBuildHistoryViewsSharePayload();
        if (!payload) {
            alert('暂无可分享的命名视图');
            return;
        }
        const code = this.searchEncodeHistoryViewsShareCode(payload);
        let link = '';
        try {
            const res = await this.apiRequest('POST', '/api/v1/search/share-views', { code }, { cancel_key: 'search:share:create', dedupe_key: `search:share:create:${code.slice(0, 120)}` });
            if (res.ok) {
                const data = await res.json();
                const key = String((data && data.key) || '').trim();
                if (key) link = this.searchBuildHistoryViewsShortShareUrl(key);
            }
        } catch (_) {
        }
        if (!link) link = this.searchBuildHistoryViewsShareUrl(code);
        if (!link) {
            alert('生成二维码失败');
            return;
        }
        const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=240x240&data=${encodeURIComponent(link)}`;
        const panel = document.getElementById('search_history_views_qr_panel');
        const img = document.getElementById('search_history_views_qr_img');
        const txt = document.getElementById('search_history_views_qr_link');
        if (!panel || !img || !txt) {
            window.open(qrUrl, '_blank');
            return;
        }
        img.src = qrUrl;
        txt.textContent = link;
        panel.classList.add('active');
    },

    searchCloseHistoryViewsShareQr: function() {
        const panel = document.getElementById('search_history_views_qr_panel');
        if (!panel) return;
        panel.classList.remove('active');
    },

    searchParseHistoryViewsShareInput: function(raw) {
        const txt = String(raw || '').trim();
        if (!txt) return { type: '', value: '' };
        if (txt.startsWith('SV1.')) return { type: 'svc', value: txt };
        if (/^[A-Za-z0-9\-_]{4,64}$/.test(txt)) return { type: 'svk', value: txt };
        try {
            const u = new URL(txt, location.origin);
            const p = u.pathname || '';
            const m = p.match(/^\/s\/([A-Za-z0-9\-_]{4,64})$/);
            if (m && m[1]) return { type: 'svk', value: String(m[1]) };
            const qs = new URLSearchParams(String(u.search || '').replace(/^\?/, ''));
            const svk = String(qs.get('svk') || '').trim();
            if (svk) return { type: 'svk', value: svk };
            const svc = String(qs.get('svc') || '').trim();
            if (svc) return { type: 'svc', value: svc };
            const hash = String(u.hash || '').replace(/^#/, '');
            if (hash) {
                const idx = hash.indexOf('?');
                const hashQ = idx >= 0 ? hash.slice(idx + 1) : hash;
                const hqs = new URLSearchParams(String(hashQ || '').replace(/^\?/, ''));
                const hsvk = String(hqs.get('svk') || '').trim();
                if (hsvk) return { type: 'svk', value: hsvk };
                const hsvc = String(hqs.get('svc') || '').trim();
                if (hsvc) return { type: 'svc', value: hsvc };
            }
        } catch (_) {
        }
        return { type: '', value: '' };
    },

    searchImportHistoryViewsByShareCodeText: function(rawCode, silent) {
        const quiet = !!silent;
        const code = String(rawCode || '').trim();
        if (!code) return { ok: false, error: 'empty', merged: 0 };
        const decoded = this.searchDecodeHistoryViewsShareCode(code);
        if (!decoded || !decoded.ok) {
            const err = decoded && decoded.error ? String(decoded.error) : 'invalid';
            if (!quiet) {
                const msg = err === 'expired' ? '共享码已过期' :
                    (err === 'sig' ? '共享码校验失败，可能已被篡改' :
                        (err === 'schema' ? '共享码版本不兼容' : '共享码无效'));
                alert(msg);
            }
            return { ok: false, error: err, merged: 0 };
        }
        const parsed = decoded.payload || {};
        const items = Array.isArray(parsed.views) ? parsed.views : [];
        if (!items.length) {
            if (!quiet) alert('共享码无效或不包含视图');
            return { ok: false, error: 'empty_views', merged: 0 };
        }
        const merged = this.searchMergeImportedHistoryViews(items);
        if (!merged) {
            if (!quiet) alert('共享码中没有可导入的有效视图');
            return { ok: false, error: 'merge_none', merged: 0 };
        }
        if (!quiet) alert(`已从共享码导入 ${merged} 个命名视图`);
        return { ok: true, error: '', merged };
    },

    searchImportHistoryViewsByShortKey: async function(rawKey, silent) {
        const quiet = !!silent;
        const key = String(rawKey || '').trim();
        if (!key) return { ok: false, error: 'empty_key', merged: 0 };
        try {
            const res = await this.apiRequest('GET', `/api/v1/search/share-views/${encodeURIComponent(key)}`, undefined, { cancel_key: 'search:share:resolve', dedupe_key: `search:share:resolve:${key}` });
            if (!res.ok) {
                const msg = res.status === 404 ? '短链不存在或已过期' : '短链解析失败';
                if (!quiet) alert(msg);
                return { ok: false, error: `http_${res.status}`, merged: 0 };
            }
            const data = await res.json();
            const code = String((data && data.code) || '').trim();
            return this.searchImportHistoryViewsByShareCodeText(code, quiet);
        } catch (_) {
            if (!quiet) alert('短链解析失败，请重试');
            return { ok: false, error: 'resolve_failed', merged: 0 };
        }
    },

    searchImportHistoryViewsByShareCode: function() {
        const got = window.prompt('请粘贴共享码或分享链接');
        if (got === null) return;
        const parsed = this.searchParseHistoryViewsShareInput(got);
        if (parsed.type === 'svk') {
            this.searchImportHistoryViewsByShortKey(parsed.value, false);
            return;
        }
        if (parsed.type === 'svc') {
            this.searchImportHistoryViewsByShareCodeText(parsed.value, false);
            return;
        }
        alert('未识别到有效共享码或短链');
    },

    searchImportHistoryViewsFromInput: function(input) {
        try {
            const el = input || document.getElementById('search_history_views_import_input');
            if (!el || !el.files || !el.files[0]) return;
            const file = el.files[0];
            const reader = new FileReader();
            reader.onload = () => {
                try {
                    const txt = String(reader.result || '');
                    const parsed = JSON.parse(txt || '{}');
                    const items = Array.isArray(parsed) ? parsed : (Array.isArray(parsed.views) ? parsed.views : []);
                    if (!items.length) {
                        alert('导入文件不包含有效视图');
                        return;
                    }
                    const merged = this.searchMergeImportedHistoryViews(items);
                    if (!merged) {
                        alert('导入文件不包含有效视图');
                        return;
                    }
                    alert(`命名视图导入成功，共 ${merged} 项`);
                } catch (_) {
                    alert('导入失败，文件格式无效');
                }
            };
            reader.readAsText(file, 'utf-8');
        } catch (_) {
            alert('导入失败，请重试');
        }
    },

    searchHistoryPanelFilteredEntries: function(list) {
        const arr = Array.isArray(list) ? list : this.searchGetExportHistory();
        const kw = this.searchHistoryPanelKeyword();
        const range = this.searchHistoryPanelRange();
        const now = Date.now();
        const cutoff = range === '1d' ? (now - 24 * 3600 * 1000) : (range === '7d' ? (now - 7 * 24 * 3600 * 1000) : (range === '30d' ? (now - 30 * 24 * 3600 * 1000) : (range === '90d' ? (now - 90 * 24 * 3600 * 1000) : 0)));
        const out = [];
        for (let i = 0; i < arr.length; i++) {
            const it = arr[i] || {};
            if (cutoff > 0) {
                const t = Math.max(0, Number(it.at_ms || 0) || 0);
                if (!t || t < cutoff) continue;
            }
            if (kw) {
                const text = `${String(it.query || '')}|${String(it.template || '')}|${String(it.search_mode || '')}|${String(it.filter || '')}|${String(it.sort || '')}`.toLowerCase();
                if (text.indexOf(kw) < 0) continue;
            }
            out.push({ idx: i, item: it });
        }
        return out;
    },

    searchRecordExportHistory: function(entry) {
        try {
            const cur = this.searchGetExportHistory();
            const e = entry && typeof entry === 'object' ? entry : {};
            const next = [{
                at_ms: Number(e.at_ms || Date.now()) || Date.now(),
                query: String(e.query || ''),
                template: String(e.template || 'standard'),
                count: Math.max(0, Number(e.count || 0) || 0),
                filter: String(e.filter || 'all'),
                sort: String(e.sort || 'default'),
                search_mode: String(e.search_mode || 'all'),
                quality_threshold: Math.max(1, Math.min(100, Math.round(Number(e.quality_threshold || 70) || 70))),
                route_hash: String(e.route_hash || ''),
                custom_columns: String(e.custom_columns || ''),
                pinned: false,
                pin_at_ms: 0,
            }, ...cur].slice(0, 20);
            this.searchSetExportHistory(next);
            if (this.searchIsExportHistoryPanelOpen()) this.searchRenderExportHistoryPanel();
        } catch (_) {
        }
    },

    clearSearchExportHistory: function(force) {
        const skipConfirm = !!force;
        if (!skipConfirm) {
            const ok = window.confirm('确认清空全部导出历史吗？');
            if (!ok) return;
        }
        try { localStorage.removeItem('search_export_history'); } catch (_) {}
        if (this.searchIsExportHistoryPanelOpen()) this.searchRenderExportHistoryPanel();
        if (!skipConfirm) alert('已清空导出历史');
    },

    searchTogglePinExportHistoryByIndex: function(index) {
        const arr = this.searchGetExportHistory();
        const i = Math.max(0, Math.floor(Number(index || 0) || 0));
        if (!arr.length || i >= arr.length) return false;
        const it = arr[i];
        it.pinned = !it.pinned;
        it.pin_at_ms = it.pinned ? Date.now() : 0;
        this.searchSetExportHistory(arr);
        if (this.searchIsExportHistoryPanelOpen()) this.searchRenderExportHistoryPanel();
        return true;
    },

    searchDeleteExportHistoryByIndex: function(index) {
        const arr = this.searchGetExportHistory();
        const i = Math.max(0, Math.floor(Number(index || 0) || 0));
        if (!arr.length || i >= arr.length) return false;
        arr.splice(i, 1);
        this.searchSetExportHistory(arr);
        if (this.searchIsExportHistoryPanelOpen()) this.searchRenderExportHistoryPanel();
        return true;
    },

    addSearchHistory: function(keyword) {
        const q = String(keyword || '').trim();
        if (!q) return;
        const arr = this.getSearchHistory();
        const next = [q, ...arr.filter(x => x !== q)];
        this.setSearchHistory(next);
    },

    clearSearchHistory: function() {
        try { localStorage.removeItem('search_history'); } catch (_) {}
        this.renderSearchDropdown();
    },

    searchToInt: function(v, d) {
        const n = Number(v);
        return Number.isFinite(n) ? Math.floor(n) : d;
    },

    searchCursorNormalize: function(v) {
        return String(v || '').trim();
    },

    searchCurrentUid: function() {
        const user = this.state && this.state.user ? this.state.user : null;
        const uid = user ? Number(user.id || 0) : 0;
        return uid > 0 ? uid : 0;
    },

    searchClamp: function(n, min, max) {
        if (n < min) return min;
        if (n > max) return max;
        return n;
    },

    searchCounterNext: function(counterKey, wrapAt) {
        const key = String(counterKey || '');
        if (!key) return 1;
        const limitRaw = Number(wrapAt || 0);
        const limit = Number.isFinite(limitRaw) ? Math.max(1, Math.floor(limitRaw)) : 1000000000;
        const curRaw = Number(this[key] || 0);
        const cur = Number.isFinite(curRaw) ? Math.max(0, Math.floor(curRaw)) : 0;
        const next = cur >= limit ? 1 : (cur + 1);
        this[key] = next;
        return next;
    },

    searchShouldSweep: function(counterValue, everyOps) {
        const cRaw = Number(counterValue || 0);
        const c = Number.isFinite(cRaw) ? Math.max(0, Math.floor(cRaw)) : 0;
        const eRaw = Number(everyOps || 0);
        const e = Number.isFinite(eRaw) ? Math.max(1, Math.floor(eRaw)) : 1;
        if (c <= 0) return false;
        return (c % e) === 0;
    },

    searchSweepScanLimit: function(maxScan, fallback, hardCap) {
        const capRaw = Number(hardCap || 0);
        const cap = Number.isFinite(capRaw) ? Math.max(1, Math.floor(capRaw)) : 4096;
        const fbRaw = Number(fallback || 0);
        const fb = Number.isFinite(fbRaw) ? Math.max(1, Math.floor(fbRaw)) : 1;
        const nRaw = Number(maxScan || 0);
        const n = Number.isFinite(nRaw) && nRaw > 0 ? Math.floor(nRaw) : fb;
        return Math.min(cap, Math.max(1, n));
    },

    searchDurationLimit: function(rawMs, fallback, hardCap) {
        const capRaw = Number(hardCap || 0);
        const cap = Number.isFinite(capRaw) ? Math.max(0, Math.floor(capRaw)) : 0;
        const fbRaw = Number(fallback || 0);
        const fb = Number.isFinite(fbRaw) ? Math.max(0, Math.floor(fbRaw)) : 0;
        const nRaw = Number(rawMs || 0);
        const n = Number.isFinite(nRaw) ? Math.max(0, Math.floor(nRaw)) : fb;
        if (cap > 0) return Math.min(cap, n);
        return n;
    },

    searchMapTrimToCap: function(mapLike, cap) {
        if (!mapLike || typeof mapLike.size !== 'number') return;
        const cRaw = Number(cap || 0);
        const c = Number.isFinite(cRaw) ? Math.max(0, Math.floor(cRaw)) : 0;
        if (c <= 0) return;
        while (mapLike.size > c) {
            const fk = mapLike.keys().next().value;
            if (!fk) break;
            mapLike.delete(fk);
        }
    },

    searchCachePolicy: function() {
        const now = Date.now();
        const prev = this.__searchCachePolicy || null;
        if (prev && prev.exp > now && prev.value) return prev.value;
        const src = (typeof window !== 'undefined' && window.__AISEEK_SEARCH_CACHE) ? window.__AISEEK_SEARCH_CACHE : {};
        const toInt = this.searchToInt;
        const clamp = this.searchClamp;
        const value = {
            firstPageTtlMs: clamp(toInt(src.firstPageTtlMs, 5000), 500, 30000),
            loadMoreTtlMs: clamp(toInt(src.loadMoreTtlMs, 1500), 200, 12000),
            staleIfErrorMs: clamp(toInt(src.staleIfErrorMs, 20000), 0, 180000),
            loadMoreStaleIfErrorMs: clamp(toInt(src.loadMoreStaleIfErrorMs, 5000), 0, 60000),
            breakerBaseMs: clamp(toInt(src.breakerBaseMs, 800), 100, 10000),
            breakerMaxMs: clamp(toInt(src.breakerMaxMs, 12000), 500, 120000),
            breakerResetMs: clamp(toInt(src.breakerResetMs, 20000), 1000, 300000),
            breakerJitterPct: clamp(toInt(src.breakerJitterPct, 20), 0, 50),
            breakerChannelMaxLen: clamp(toInt(src.breakerChannelMaxLen, 64), 24, 256),
            cancelChannelProbeMaxLen: clamp(toInt(src.cancelChannelProbeMaxLen, 512), 128, 4096),
            breakerStateKeyMaxLen: clamp(toInt(src.breakerStateKeyMaxLen, 96), 24, 512),
            breakerMax: clamp(toInt(src.breakerMax, 256), 32, 4096),
            breakerSweepEveryOps: clamp(toInt(src.breakerSweepEveryOps, 20), 4, 512),
            breakerSweepScan: clamp(toInt(src.breakerSweepScan, 64), 8, 1024),
            cap: clamp(toInt(src.cap, 80), 20, 400),
            sweepEveryOps: clamp(toInt(src.sweepEveryOps, 16), 4, 128),
            sweepScan: clamp(toInt(src.sweepScan, 24), 8, 256),
            sweepMinIntervalMs: clamp(toInt(src.sweepMinIntervalMs, 120), 10, 2000),
            cacheTouchMinIntervalMs: clamp(toInt(src.cacheTouchMinIntervalMs, 200), 0, 5000),
            staleTouchMinIntervalMs: clamp(toInt(src.staleTouchMinIntervalMs, 1000), 0, 10000),
            requestKeyMaxLen: clamp(toInt(src.requestKeyMaxLen, 260), 96, 1024),
            reqKeyCacheMax: clamp(toInt(src.reqKeyCacheMax, 512), 64, 4096),
            reqKeyCacheTtlMs: clamp(toInt(src.reqKeyCacheTtlMs, 30000), 1000, 300000),
            reqKeyTouchMinIntervalMs: clamp(toInt(src.reqKeyTouchMinIntervalMs, 200), 0, 5000),
            reqKeyCacheIndexMaxLen: clamp(toInt(src.reqKeyCacheIndexMaxLen, 640), 128, 4096),
            reqKeyRawUrlProbeMaxLen: clamp(toInt(src.reqKeyRawUrlProbeMaxLen, 2048), 256, 16384),
            reqKeySweepEveryOps: clamp(toInt(src.reqKeySweepEveryOps, 24), 4, 256),
            reqKeySweepScan: clamp(toInt(src.reqKeySweepScan, 64), 8, 512),
            reqKeySweepMinIntervalMs: clamp(toInt(src.reqKeySweepMinIntervalMs, 120), 10, 3000),
            inflightMax: clamp(toInt(src.inflightMax, 512), 64, 4096),
            inflightStaleMs: clamp(toInt(src.inflightStaleMs, 15000), 2000, 180000),
            inflightKeyMaxLen: clamp(toInt(src.inflightKeyMaxLen, 320), 96, 2048),
            inflightSweepEveryOps: clamp(toInt(src.inflightSweepEveryOps, 16), 4, 256),
            inflightSweepScan: clamp(toInt(src.inflightSweepScan, 64), 8, 512),
            inflightSweepMinIntervalMs: clamp(toInt(src.inflightSweepMinIntervalMs, 120), 10, 2000),
            imprDedupMax: clamp(toInt(src.imprDedupMax, 20000), 1000, 200000),
            imprDedupTtlMs: clamp(toInt(src.imprDedupTtlMs, 600000), 60000, 3600000),
            imprKeyMaxLen: clamp(toInt(src.imprKeyMaxLen, 128), 32, 1024),
            imprSweepEveryOps: clamp(toInt(src.imprSweepEveryOps, 24), 4, 256),
            imprSweepScan: clamp(toInt(src.imprSweepScan, 128), 16, 1024),
            imprSweepMinIntervalMs: clamp(toInt(src.imprSweepMinIntervalMs, 160), 10, 3000),
            breakerSweepMinIntervalMs: clamp(toInt(src.breakerSweepMinIntervalMs, 120), 10, 3000),
        };
        this.__searchCachePolicy = { value, exp: now + 10000 };
        return value;
    },

    searchSweepAllow: function(bucket, minIntervalMs) {
        try {
            const b = String(bucket || '');
            if (!b) return true;
            if (!this.__searchSweepStamp) this.__searchSweepStamp = new Map();
            const now = Date.now();
            const prev = Number(this.__searchSweepStamp.get(b) || 0);
            const gap = Math.max(0, Number(minIntervalMs || 0));
            if (gap <= 0 || !prev || (now - prev) >= gap) {
                this.__searchSweepStamp.set(b, now);
                return true;
            }
            return false;
        } catch (_) {
            return true;
        }
    },

    searchRequestPolicy: function() {
        const now = Date.now();
        const prev = this.__searchRequestPolicy || null;
        if (prev && prev.exp > now && prev.value) return prev.value;
        const src = (typeof window !== 'undefined' && window.__AISEEK_SEARCH_REQ) ? window.__AISEEK_SEARCH_REQ : {};
        const toInt = this.searchToInt;
        const clamp = this.searchClamp;
        const value = {
            firstPageTimeoutMs: clamp(toInt(src.firstPageTimeoutMs, 6000), 1200, 20000),
            loadMoreTimeoutMs: clamp(toInt(src.loadMoreTimeoutMs, 4500), 800, 15000),
            firstPageRetries: clamp(toInt(src.firstPageRetries, 0), 0, 2),
            loadMoreRetries: clamp(toInt(src.loadMoreRetries, 0), 0, 1),
        };
        this.__searchRequestPolicy = { value, exp: now + 10000 };
        return value;
    },

    searchQueryPolicy: function() {
        const now = Date.now();
        const prev = this.__searchQueryPolicy || null;
        if (prev && prev.exp > now && prev.value) return prev.value;
        const src = (typeof window !== 'undefined' && window.__AISEEK_SEARCH_QUERY) ? window.__AISEEK_SEARCH_QUERY : {};
        const toInt = this.searchToInt;
        const clamp = this.searchClamp;
        const value = {
            minUserQueryLen: clamp(toInt(src.minUserQueryLen, 1), 1, 8),
        };
        this.__searchQueryPolicy = { value, exp: now + 10000 };
        return value;
    },

    searchMainCachePolicyView: function(policy) {
        const p = policy || this.searchCachePolicy();
        const now = Date.now();
        const prev = this.__searchMainCachePolicyView || null;
        if (prev && prev.src === p && prev.exp > now && prev.value) return prev.value;
        const toInt = this.searchToInt;
        const clamp = this.searchClamp;
        const value = {
            sweepEveryOps: clamp(toInt(p.sweepEveryOps, 16), 1, 512),
            sweepMinIntervalMs: clamp(toInt(p.sweepMinIntervalMs, 120), 10, 3000),
            sweepScan: clamp(toInt(p.sweepScan, 24), 8, 4096),
            cacheTouchMinIntervalMs: clamp(toInt(p.cacheTouchMinIntervalMs, 0), 0, 5000),
            staleTouchMinIntervalMs: clamp(toInt(p.staleTouchMinIntervalMs, 0), 0, 10000),
            cap: clamp(toInt(p.cap, 80), 20, 1000000),
        };
        this.__searchMainCachePolicyView = { src: p, value, exp: now + 1500 };
        return value;
    },

    searchPageFetchPolicyView: function(policy) {
        const p = policy || this.searchCachePolicy();
        const now = Date.now();
        const prev = this.__searchPageFetchPolicyView || null;
        if (prev && prev.src === p && prev.exp > now && prev.value) return prev.value;
        const toInt = this.searchToInt;
        const clamp = this.searchClamp;
        const value = {
            firstPageTtlMs: clamp(toInt(p.firstPageTtlMs, 5000), 100, 120000),
            loadMoreTtlMs: clamp(toInt(p.loadMoreTtlMs, 1500), 100, 120000),
            staleIfErrorMs: clamp(toInt(p.staleIfErrorMs, 0), 0, 1800000),
            loadMoreStaleIfErrorMs: clamp(toInt(p.loadMoreStaleIfErrorMs, 0), 0, 1800000),
            cap: clamp(toInt(p.cap, 80), 20, 1000000),
        };
        this.__searchPageFetchPolicyView = { src: p, value, exp: now + 1500 };
        return value;
    },

    searchExecPolicyView: function(requestPolicy, queryPolicy) {
        const rp = requestPolicy || this.searchRequestPolicy();
        const qp = (queryPolicy === undefined) ? this.searchQueryPolicy() : (queryPolicy || null);
        const now = Date.now();
        const prev = this.__searchExecPolicyView || null;
        if (prev && prev.rp === rp && prev.qp === qp && prev.exp > now && prev.value) return prev.value;
        const toInt = this.searchToInt;
        const clamp = this.searchClamp;
        const minUserQueryLen = qp ? clamp(toInt(qp.minUserQueryLen, 1), 1, 16) : 1;
        const value = {
            firstPageTimeoutMs: clamp(toInt(rp.firstPageTimeoutMs, 6000), 800, 30000),
            loadMoreTimeoutMs: clamp(toInt(rp.loadMoreTimeoutMs, 4500), 800, 30000),
            firstPageRetries: clamp(toInt(rp.firstPageRetries, 0), 0, 3),
            loadMoreRetries: clamp(toInt(rp.loadMoreRetries, 0), 0, 2),
            minUserQueryLen,
        };
        this.__searchExecPolicyView = { rp, qp, value, exp: now + 1500 };
        return value;
    },

    searchLoadMoreBusyPolicyView: function(policy) {
        const p = policy || this.searchCachePolicy();
        const now = Date.now();
        const prev = this.__searchLoadMoreBusyPolicyView || null;
        if (prev && prev.src === p && prev.exp > now && prev.value) return prev.value;
        const toInt = this.searchToInt;
        const clamp = this.searchClamp;
        const value = {
            keyMaxLen: clamp(toInt(p.reqKeyCacheIndexMaxLen, 640), 96, 4096),
            staleMs: clamp(toInt(p.inflightStaleMs, 15000), 1000, 300000),
            cap: clamp(toInt(p.inflightMax, 512) * 4, 64, 200000),
            sweepEveryOps: clamp(toInt(p.inflightSweepEveryOps, 16), 1, 512),
            sweepScan: clamp(toInt(p.inflightSweepScan, 64), 8, 4096),
            sweepMinIntervalMs: clamp(toInt(p.inflightSweepMinIntervalMs, 120), 10, 3000),
        };
        this.__searchLoadMoreBusyPolicyView = { src: p, value, exp: now + 1500 };
        return value;
    },

    searchLoadMoreBusyEnsure: function() {
        if (!this.__searchLoadMoreBusy) this.__searchLoadMoreBusy = new Map();
        return this.__searchLoadMoreBusy;
    },

    searchLoadMoreBusySweep: function(maxScan, nowTs, staleMs) {
        try {
            const busy = this.searchLoadMoreBusyEnsure();
            if (busy.size === 0) return 0;
            const n = this.searchSweepScanLimit(maxScan, 64, 4096);
            const now = Number(nowTs || 0) > 0 ? Number(nowTs) : Date.now();
            const stale = this.searchDurationLimit(staleMs, 15000, 300000);
            let scanned = 0;
            let removed = 0;
            for (const [k, v] of busy.entries()) {
                if (scanned >= n) break;
                scanned += 1;
                const ts = Number(v || 0);
                if (!ts || (now - ts) > stale) {
                    busy.delete(k);
                    removed += 1;
                }
            }
            return removed;
        } catch (_) {
            return 0;
        }
    },

    searchLoadMoreBusyEnter: function(rawKey, policy) {
        try {
            const p = policy || this.searchCachePolicy();
            const cfg = this.searchLoadMoreBusyPolicyView(p);
            const now = Date.now();
            const busyOps = this.searchCounterNext('__searchLoadMoreBusyOps', 1000000000);
            if (this.searchShouldSweep(busyOps, cfg.sweepEveryOps) && this.searchSweepAllow('lmbusy', cfg.sweepMinIntervalMs)) {
                this.searchLoadMoreBusySweep(cfg.sweepScan, now, cfg.staleMs);
            }
            const k = this.searchBoundKey(String(rawKey || ''), cfg.keyMaxLen);
            if (!k) return '';
            const busy = this.searchLoadMoreBusyEnsure();
            const prevTs = Number(busy.get(k) || 0);
            if (prevTs && (now - prevTs) <= cfg.staleMs) return '';
            busy.set(k, now);
            this.searchMapTrimToCap(busy, cfg.cap);
            return k;
        } catch (_) {
            return '';
        }
    },

    searchLoadMoreBusyLeave: function(token) {
        try {
            const k = String(token || '');
            if (!k) return;
            const busy = this.__searchLoadMoreBusy || null;
            if (!busy || !busy.delete) return;
            busy.delete(k);
        } catch (_) {
        }
    },

    searchDateFmtPolicyView: function(policy) {
        const p = policy || this.searchCachePolicy();
        const now = Date.now();
        const prev = this.__searchDateFmtPolicyView || null;
        if (prev && prev.src === p && prev.exp > now && prev.value) return prev.value;
        const toInt = this.searchToInt;
        const clamp = this.searchClamp;
        const value = {
            ttlMs: clamp(toInt(p.sweepMinIntervalMs, 120) * 120, 2000, 1800000),
            cap: clamp(toInt(p.inflightMax, 512) * 8, 128, 200000),
            sweepEveryOps: clamp(toInt(p.sweepEveryOps, 16), 1, 512),
            sweepScan: clamp(toInt(p.sweepScan, 24), 8, 4096),
            sweepMinIntervalMs: clamp(toInt(p.sweepMinIntervalMs, 120), 10, 3000),
        };
        this.__searchDateFmtPolicyView = { src: p, value, exp: now + 1500 };
        return value;
    },

    searchDateFmtEnsure: function() {
        if (!this.__searchDateFmtCache) this.__searchDateFmtCache = new Map();
        return this.__searchDateFmtCache;
    },

    searchDateFmtSweep: function(maxScan, nowTs) {
        try {
            const cache = this.searchDateFmtEnsure();
            if (cache.size === 0) return 0;
            const n = this.searchSweepScanLimit(maxScan, 24, 4096);
            const now = Number(nowTs || 0) > 0 ? Number(nowTs) : Date.now();
            let scanned = 0;
            let removed = 0;
            for (const [k, v] of cache.entries()) {
                if (scanned >= n) break;
                scanned += 1;
                const exp = Number(v && v.exp || 0);
                if (!exp || exp <= now) {
                    cache.delete(k);
                    removed += 1;
                }
            }
            return removed;
        } catch (_) {
            return 0;
        }
    },

    searchDateFmtContext: function(policy) {
        const p = policy || this.searchCachePolicy();
        const cfg = this.searchDateFmtPolicyView(p);
        const now = Date.now();
        const ops = this.searchCounterNext('__searchDateFmtOps', 1000000000);
        if (this.searchShouldSweep(ops, cfg.sweepEveryOps) && this.searchSweepAllow('datefmt', cfg.sweepMinIntervalMs)) {
            this.searchDateFmtSweep(cfg.sweepScan, now);
        }
        const ttl = this.searchDurationLimit(cfg.ttlMs, 2000, 1800000);
        return { now, cfg, ttl };
    },

    searchDateFmtWithContext: function(input, ctx) {
        try {
            if (!input) return '';
            const c = ctx || this.searchDateFmtContext(null);
            const now = Number(c && c.now || 0) > 0 ? Number(c.now) : Date.now();
            const ttl = this.searchDurationLimit(Number(c && c.ttl || 0), 2000, 1800000);
            const cap = Number(c && c.cfg && c.cfg.cap || 0);
            const key = String(input || '');
            const cache = this.searchDateFmtEnsure();
            const hit = cache.get(key);
            if (hit && Number(hit.exp || 0) > now) return String(hit.v || '');
            let out = '';
            try {
                out = new Date(key).toLocaleDateString();
            } catch (_) {
                out = '';
            }
            cache.set(key, { v: out, exp: now + ttl });
            this.searchMapTrimToCap(cache, cap);
            return out;
        } catch (_) {
            return '';
        }
    },

    searchDateFmt: function(input, policy) {
        try {
            const ctx = this.searchDateFmtContext(policy || null);
            return this.searchDateFmtWithContext(input, ctx);
        } catch (_) {
            return '';
        }
    },

    searchInflightPolicyView: function(policy) {
        const p = policy || this.searchCachePolicy();
        const now = Date.now();
        const prev = this.__searchInflightPolicyView || null;
        if (prev && prev.src === p && prev.exp > now && prev.value) return prev.value;
        const toInt = this.searchToInt;
        const clamp = this.searchClamp;
        const value = {
            inflightStaleMs: clamp(toInt(p.inflightStaleMs, 15000), 1000, 300000),
            inflightMax: clamp(toInt(p.inflightMax, 512), 16, 1000000),
            inflightSweepScan: clamp(toInt(p.inflightSweepScan, 64), 8, 4096),
            inflightKeyMaxLen: clamp(toInt(p.inflightKeyMaxLen, 320), 64, 4096),
            inflightSweepEveryOps: clamp(toInt(p.inflightSweepEveryOps, 16), 1, 512),
            inflightSweepMinIntervalMs: clamp(toInt(p.inflightSweepMinIntervalMs, 120), 10, 3000),
        };
        this.__searchInflightPolicyView = { src: p, value, exp: now + 1500 };
        return value;
    },

    searchBreakerPolicyView: function(policy) {
        const p = policy || this.searchCachePolicy();
        const now = Date.now();
        const prev = this.__searchBreakerPolicyView || null;
        if (prev && prev.src === p && prev.exp > now && prev.value) return prev.value;
        const toInt = this.searchToInt;
        const clamp = this.searchClamp;
        const value = {
            breakerResetMs: clamp(toInt(p.breakerResetMs, 20000), 1000, 300000),
            breakerMax: clamp(toInt(p.breakerMax, 256), 32, 1000000),
            breakerSweepScan: clamp(toInt(p.breakerSweepScan, 64), 8, 4096),
            breakerSweepEveryOps: clamp(toInt(p.breakerSweepEveryOps, 20), 1, 512),
            breakerSweepMinIntervalMs: clamp(toInt(p.breakerSweepMinIntervalMs, 120), 10, 3000),
            breakerBaseMs: clamp(toInt(p.breakerBaseMs, 800), 100, 60000),
            breakerMaxMs: clamp(toInt(p.breakerMaxMs, 12000), 500, 300000),
            breakerJitterPct: clamp(toInt(p.breakerJitterPct, 20), 0, 50),
            breakerStateKeyMaxLen: clamp(toInt(p.breakerStateKeyMaxLen, 96), 24, 1024),
        };
        this.__searchBreakerPolicyView = { src: p, value, exp: now + 1500 };
        return value;
    },

    searchCacheTouchMaybe: function(key, hit, now, touchMin) {
        const cache = this.searchPageCacheEnsure();
        const lastAt = Number(hit && hit.at || 0);
        if (touchMin <= 0 || !lastAt || (now - lastAt) >= touchMin) {
            hit.at = now;
            cache.delete(key);
            cache.set(key, hit);
        }
    },

    searchPageCacheEnsure: function() {
        if (!this.__searchPageCache) this.__searchPageCache = new Map();
        return this.__searchPageCache;
    },

    searchPageCacheTrimToCap: function(cap) {
        const cache = this.searchPageCacheEnsure();
        this.searchMapTrimToCap(cache, cap);
    },

    searchCacheGet: function(key) {
        try {
            const cache = this.searchPageCacheEnsure();
            const policy = this.searchCachePolicy();
            const cfg = this.searchMainCachePolicyView(policy);
            const cacheOps = this.searchCounterNext('__searchCacheOps', 1000000000);
            if (this.searchShouldSweep(cacheOps, cfg.sweepEveryOps) && this.searchSweepAllow('cache', cfg.sweepMinIntervalMs)) this.searchCacheSweep(cfg.sweepScan);
            const hit = cache.get(key);
            if (!hit) return null;
            const now = Date.now();
            if (!hit.exp || hit.exp <= now) {
                cache.delete(key);
                return null;
            }
            this.searchCacheTouchMaybe(key, hit, now, cfg.cacheTouchMinIntervalMs);
            return hit;
        } catch (_) {
            return null;
        }
    },

    searchCacheGetStale: function(key, maxStaleMs) {
        try {
            const cache = this.searchPageCacheEnsure();
            const hit = cache.get(key);
            if (!hit || !hit.exp) return null;
            const now = Date.now();
            const policy = this.searchCachePolicy();
            const cfg = this.searchMainCachePolicyView(policy);
            if (hit.exp > now) {
                this.searchCacheTouchMaybe(key, hit, now, cfg.cacheTouchMinIntervalMs);
                return hit;
            }
            const staleMs = this.searchDurationLimit(maxStaleMs, 0, 1800000);
            if (staleMs <= 0) return null;
            if ((now - Number(hit.exp || 0)) > staleMs) return null;
            const staleTouchMin = Math.max(cfg.cacheTouchMinIntervalMs, cfg.staleTouchMinIntervalMs);
            this.searchCacheTouchMaybe(key, hit, now, staleTouchMin);
            return hit;
        } catch (_) {
            return null;
        }
    },

    searchCacheSweep: function(maxScan) {
        try {
            const cache = this.searchPageCacheEnsure();
            if (cache.size === 0) return 0;
            const n = this.searchSweepScanLimit(maxScan, 24, 4096);
            const now = Date.now();
            let scanned = 0;
            let removed = 0;
            for (const [k, v] of cache.entries()) {
                if (scanned >= n) break;
                scanned += 1;
                if (!v || !v.exp || v.exp <= now) {
                    cache.delete(k);
                    removed += 1;
                }
            }
            return removed;
        } catch (_) {
            return 0;
        }
    },

    searchCacheSet: function(key, value, ttl, cap) {
        try {
            const cache = this.searchPageCacheEnsure();
            const policy = this.searchCachePolicy();
            const cfg = this.searchMainCachePolicyView(policy);
            const t = Number(ttl || 0);
            if (t <= 0) return value || null;
            const cacheOps = this.searchCounterNext('__searchCacheOps', 1000000000);
            if (this.searchShouldSweep(cacheOps, cfg.sweepEveryOps) && this.searchSweepAllow('cache', cfg.sweepMinIntervalMs)) this.searchCacheSweep(cfg.sweepScan);
            const now = Date.now();
            const out = { ...(value || {}), exp: now + (t > 0 ? t : 0), at: now };
            cache.delete(key);
            cache.set(key, out);
            const cacheCap = this.searchSweepScanLimit(cap, cfg.cap, 1000000);
            this.searchPageCacheTrimToCap(cacheCap);
            return out;
        } catch (_) {
            return value || null;
        }
    },

    searchInflightEnsure: function() {
        if (!this.__searchPageInflight) this.__searchPageInflight = new Map();
        return this.__searchPageInflight;
    },

    searchInflightTrimToCap: function(cap) {
        const inflight = this.searchInflightEnsure();
        this.searchMapTrimToCap(inflight, cap);
    },

    searchInflightSweep: function(maxScan) {
        try {
            const inflight = this.searchInflightEnsure();
            if (inflight.size === 0) return 0;
            const p = this.searchCachePolicy();
            const cfg = this.searchInflightPolicyView(p);
            const n = this.searchSweepScanLimit(maxScan, cfg.inflightSweepScan, 4096);
            const now = Date.now();
            let scanned = 0;
            let removed = 0;
            for (const [k, v] of inflight.entries()) {
                if (scanned >= n) break;
                scanned += 1;
                const ts = Number(v && v.ts || 0);
                const pv = v && v.p;
                if (!pv || !ts || (now - ts) > cfg.inflightStaleMs) {
                    inflight.delete(k);
                    removed += 1;
                }
            }
            const beforeTrim = inflight.size;
            this.searchInflightTrimToCap(cfg.inflightMax);
            removed += Math.max(0, beforeTrim - inflight.size);
            return removed;
        } catch (_) {
            return 0;
        }
    },

    searchInflightGetOrRun: async function(key, runner) {
        const inflight = this.searchInflightEnsure();
        const pol = this.searchCachePolicy();
        const cfg = this.searchInflightPolicyView(pol);
        const rawKey = String(key || '');
        const mapKey = this.searchBoundKey(rawKey, cfg.inflightKeyMaxLen);
        const inflightOps = this.searchCounterNext('__searchInflightOps', 1000000000);
        if (this.searchShouldSweep(inflightOps, cfg.inflightSweepEveryOps) && this.searchSweepAllow('inflight', cfg.inflightSweepMinIntervalMs)) this.searchInflightSweep(cfg.inflightSweepScan);
        const pending = inflight.get(mapKey);
        const pendingPromise = pending && pending.p ? pending.p : pending;
        if (pendingPromise) return await pendingPromise;
        const runp = Promise.resolve().then(runner);
        const now = Date.now();
        inflight.set(mapKey, { p: runp, ts: now });
        try {
            return await runp;
        } finally {
            try {
                const cur = inflight.get(mapKey);
                if (!cur || cur.p === runp || cur === runp) inflight.delete(mapKey);
            } catch (_) {}
        }
    },

    searchBreakerEnsure: function() {
        if (!this.__searchBreaker) this.__searchBreaker = new Map();
        return this.__searchBreaker;
    },

    searchBreakerTrimToCap: function(cap) {
        const breaker = this.searchBreakerEnsure();
        this.searchMapTrimToCap(breaker, cap);
    },

    searchBreakerSweep: function(maxScan) {
        try {
            const breaker = this.searchBreakerEnsure();
            if (breaker.size === 0) return 0;
            const p = this.searchCachePolicy();
            const cfg = this.searchBreakerPolicyView(p);
            const now = Date.now();
            const n = this.searchSweepScanLimit(maxScan, cfg.breakerSweepScan, 4096);
            let scanned = 0;
            let removed = 0;
            for (const [k, v] of breaker.entries()) {
                if (scanned >= n) break;
                scanned += 1;
                const until = Number(v && v.until || 0);
                if (!until || until <= 0 || (now - until) > cfg.breakerResetMs) {
                    breaker.delete(k);
                    removed += 1;
                }
            }
            const beforeTrim = breaker.size;
            this.searchBreakerTrimToCap(cfg.breakerMax);
            removed += Math.max(0, beforeTrim - breaker.size);
            return removed;
        } catch (_) {
            return 0;
        }
    },

    searchBreakerAllow: function(channelKey) {
        try {
            const p = this.searchCachePolicy();
            const cfg = this.searchBreakerPolicyView(p);
            const k = this.searchBreakerStateKey(channelKey, p, cfg);
            if (!k) return true;
            const breaker = this.searchBreakerEnsure();
            const breakerOps = this.searchCounterNext('__searchBreakerOps', 1000000000);
            if (this.searchShouldSweep(breakerOps, cfg.breakerSweepEveryOps) && this.searchSweepAllow('breaker', cfg.breakerSweepMinIntervalMs)) this.searchBreakerSweep(cfg.breakerSweepScan);
            const now = Date.now();
            const st = breaker.get(k);
            if (!st) return true;
            if (Number(st.until || 0) <= now) {
                breaker.delete(k);
                return true;
            }
            return false;
        } catch (_) {
            return true;
        }
    },

    searchBreakerOnSuccess: function(channelKey) {
        try {
            const breaker = this.__searchBreaker || null;
            if (!breaker) return;
            const p = this.searchCachePolicy();
            const cfg = this.searchBreakerPolicyView(p);
            const k = this.searchBreakerStateKey(channelKey, p, cfg);
            if (!k) return;
            breaker.delete(k);
        } catch (_) {
        }
    },

    searchBreakerOnFailure: function(channelKey) {
        try {
            const p = this.searchCachePolicy();
            const cfg = this.searchBreakerPolicyView(p);
            const k = this.searchBreakerStateKey(channelKey, p, cfg);
            if (!k) return;
            const breaker = this.searchBreakerEnsure();
            const now = Date.now();
            const prev = breaker.get(k) || { n: 0, until: 0 };
            const prevUntil = Number(prev.until || 0);
            const prevN = Number(prev.n || 0);
            const n = (prevUntil > now) ? (prevN + 1) : 1;
            const raw = Math.min(cfg.breakerMaxMs, cfg.breakerBaseMs * Math.pow(2, Math.max(0, n - 1)));
            const jitter = (Math.random() * 2 - 1) * (cfg.breakerJitterPct / 100);
            const wait = Math.max(50, Math.min(cfg.breakerMaxMs, Math.round(raw * (1 + jitter))));
            breaker.set(k, { n, until: now + wait });
            this.searchBreakerTrimToCap(cfg.breakerMax);
        } catch (_) {
        }
    },

    searchIsBreakerOpenError: function(err) {
        try {
            const msg = String(err && err.message || err || '');
            return msg.indexOf('breaker_open:') === 0;
        } catch (_) {
            return false;
        }
    },

    searchShouldTripBreaker: function(err) {
        try {
            if (this.searchIsBreakerOpenError(err)) return false;
            const st = Number(err && err.status || 0);
            if (Number.isFinite(st) && st > 0) {
                if (st === 429) return true;
                if (st >= 500) return true;
                return false;
            }
            return true;
        } catch (_) {
            return true;
        }
    },

    searchImprEnsure: function() {
        if (!this.__searchImprSent) this.__searchImprSent = new Map();
        return this.__searchImprSent;
    },

    searchImprPolicyView: function(policy) {
        const p = policy || this.searchCachePolicy();
        const now = Date.now();
        const prev = this.__searchImprPolicyView || null;
        if (prev && prev.src === p && prev.exp > now && prev.value) return prev.value;
        const toInt = this.searchToInt;
        const clamp = this.searchClamp;
        const value = {
            imprDedupTtlMs: clamp(toInt(p.imprDedupTtlMs, 600000), 1000, 7200000),
            imprDedupMax: clamp(toInt(p.imprDedupMax, 20000), 100, 1000000),
            imprSweepScan: clamp(toInt(p.imprSweepScan, 128), 8, 4096),
            imprSweepEveryOps: clamp(toInt(p.imprSweepEveryOps, 24), 1, 512),
            imprSweepMinIntervalMs: clamp(toInt(p.imprSweepMinIntervalMs, 160), 10, 3000),
            imprKeyMaxLen: clamp(toInt(p.imprKeyMaxLen, 128), 24, 4096),
        };
        this.__searchImprPolicyView = { src: p, value, exp: now + 1500 };
        return value;
    },

    searchImprTrimToCap: function(cap) {
        const impr = this.searchImprEnsure();
        this.searchMapTrimToCap(impr, cap);
    },

    searchImprSweep: function(maxScan) {
        try {
            const impr = this.searchImprEnsure();
            if (impr.size === 0) return 0;
            const p = this.searchCachePolicy();
            const cfg = this.searchImprPolicyView(p);
            const now = Date.now();
            const n = this.searchSweepScanLimit(maxScan, cfg.imprSweepScan, 4096);
            let scanned = 0;
            let removed = 0;
            for (const [k, ts] of impr.entries()) {
                if (scanned >= n) break;
                scanned += 1;
                if (!ts || (now - Number(ts || 0)) > cfg.imprDedupTtlMs) {
                    impr.delete(k);
                    removed += 1;
                }
            }
            const beforeTrim = impr.size;
            this.searchImprTrimToCap(cfg.imprDedupMax);
            removed += Math.max(0, beforeTrim - impr.size);
            return removed;
        } catch (_) {
            return 0;
        }
    },

    searchImprMarkSeen: function(key) {
        try {
            if (!key) return true;
            const impr = this.searchImprEnsure();
            const p = this.searchCachePolicy();
            const cfg = this.searchImprPolicyView(p);
            const mapKey = this.searchBoundKey(String(key || ''), cfg.imprKeyMaxLen);
            const imprOps = this.searchCounterNext('__searchImprOps', 1000000000);
            if (this.searchShouldSweep(imprOps, cfg.imprSweepEveryOps) && this.searchSweepAllow('impr', cfg.imprSweepMinIntervalMs)) this.searchImprSweep(cfg.imprSweepScan);
            const now = Date.now();
            const prev = Number(impr.get(mapKey) || 0);
            if (prev && (now - prev) <= cfg.imprDedupTtlMs) return false;
            impr.delete(mapKey);
            impr.set(mapKey, now);
            this.searchImprTrimToCap(cfg.imprDedupMax);
            return true;
        } catch (_) {
            return true;
        }
    },

    searchHash32: function(s) {
        let h = 2166136261;
        const t = String(s || '');
        for (let i = 0; i < t.length; i++) {
            h ^= t.charCodeAt(i);
            h = Math.imul(h, 16777619);
        }
        return (h >>> 0).toString(16).padStart(8, '0');
    },

    searchHash32Bounded: function(s, maxChars) {
        const t = String(s || '');
        const mRaw = Number(maxChars || 0);
        const m = Number.isFinite(mRaw) ? Math.max(0, Math.floor(mRaw)) : 0;
        if (m <= 0 || t.length <= m) return this.searchHash32(t);
        const windowChars = Math.max(16, Math.min(256, Math.floor(m / 2)));
        const seed = `${t.length}|${t.slice(0, windowChars)}|${t.slice(-windowChars)}`;
        return this.searchHash32(seed);
    },

    searchBoundKeyByHash: function(raw, maxLen, preHash) {
        const s = String(raw || '');
        const nRaw = Number(maxLen || 0);
        if (!Number.isFinite(nRaw)) return s;
        const n = Math.max(0, Math.floor(nRaw));
        if (n <= 0 || s.length <= n) return s;
        const h = String(preHash || this.searchHash32Bounded(s, 4096));
        if (n <= 1) return h.slice(0, Math.max(0, n));
        const suffixLen = h.length + 1;
        if (n <= suffixLen) return h.slice(0, n);
        const prefixLen = n - suffixLen;
        return `${s.slice(0, prefixLen)}|${h}`;
    },

    searchBoundKey: function(raw, maxLen) {
        return this.searchBoundKeyByHash(raw, maxLen, '');
    },

    searchBoundKeyPair: function(raw, maxLenA, maxLenB) {
        const s = String(raw || '');
        const aRaw = Number(maxLenA || 0);
        const bRaw = Number(maxLenB || 0);
        const aFinite = Number.isFinite(aRaw);
        const bFinite = Number.isFinite(bRaw);
        const a = aFinite ? Math.max(0, Math.floor(aRaw)) : 0;
        const b = bFinite ? Math.max(0, Math.floor(bRaw)) : 0;
        const needA = aFinite && a > 0 && s.length > a;
        const needB = bFinite && b > 0 && s.length > b;
        if (!needA && !needB) {
            return {
                first: this.searchBoundKeyByHash(s, maxLenA, ''),
                second: this.searchBoundKeyByHash(s, maxLenB, ''),
            };
        }
        const h = this.searchHash32Bounded(s, 4096);
        return {
            first: this.searchBoundKeyByHash(s, maxLenA, h),
            second: this.searchBoundKeyByHash(s, maxLenB, h),
        };
    },

    searchScopedRawKey: function(scope, rawUrl, maxProbeChars) {
        const s = String(scope || '');
        const u = String(rawUrl || '');
        const mRaw = Number(maxProbeChars || 0);
        const mNorm = Number.isFinite(mRaw) ? Math.max(0, Math.floor(mRaw)) : 0;
        const m = Math.min(mNorm, 4096);
        if (m <= 0 || u.length <= m) return `${s}|${u}`;
        const hu = this.searchHash32Bounded(u, 4096);
        return `${s}|${u.slice(0, m)}|#${u.length}:${hu}`;
    },

    searchBreakerStateKey: function(channelKey, policy, policyView) {
        const cfg = policyView || this.searchBreakerPolicyView(policy);
        return this.searchBoundKey(String(channelKey || ''), cfg.breakerStateKeyMaxLen);
    },

    searchReqKeyCacheEnsure: function() {
        if (!this.__searchReqKeyCache) this.__searchReqKeyCache = new Map();
        return this.__searchReqKeyCache;
    },

    searchReqKeyTouchMaybe: function(cacheKey, hit, now, touchMin) {
        const cache = this.searchReqKeyCacheEnsure();
        const lastAt = Number(hit && hit.at || 0);
        if (touchMin <= 0 || !lastAt || (now - lastAt) >= touchMin) {
            hit.at = now;
            cache.delete(cacheKey);
            cache.set(cacheKey, hit);
        }
    },

    searchReqKeyGetMaybe: function(cacheKey, now, touchMin) {
        const cache = this.searchReqKeyCacheEnsure();
        const hit = cache.get(cacheKey);
        if (!hit || !hit.key) return '';
        const exp = Number(hit.exp || 0);
        if (!exp || exp <= now) {
            cache.delete(cacheKey);
            return '';
        }
        this.searchReqKeyTouchMaybe(cacheKey, hit, now, touchMin);
        return String(hit.key);
    },

    searchReqKeyPut: function(cacheKey, key, now, ttlMs, cap) {
        const cache = this.searchReqKeyCacheEnsure();
        const ttlRaw = Number(ttlMs || 0);
        const ttl = Number.isFinite(ttlRaw) ? Math.max(0, Math.floor(ttlRaw)) : 0;
        cache.set(cacheKey, { key, exp: now + ttl, at: now });
        this.searchReqKeyTrimToCap(cap);
    },

    searchReqKeyTrimToCap: function(cap) {
        const cache = this.searchReqKeyCacheEnsure();
        this.searchMapTrimToCap(cache, cap);
    },

    searchReqKeySweepExpired: function(maxScan, now) {
        const cache = this.searchReqKeyCacheEnsure();
        if (cache.size === 0) return 0;
        const limit = this.searchSweepScanLimit(maxScan, 64, 4096);
        const nowRaw = Number(now || 0);
        const nowTs = Number.isFinite(nowRaw) && nowRaw > 0 ? nowRaw : Date.now();
        let scanned = 0;
        let removed = 0;
        for (const [k, v] of cache.entries()) {
            if (scanned >= limit) break;
            scanned += 1;
            const exp = Number(v && v.exp || 0);
            if (!exp || exp <= nowTs) {
                cache.delete(k);
                removed += 1;
            }
        }
        return removed;
    },

    searchReqKeyPolicyView: function(policy) {
        const p = policy || this.searchCachePolicy();
        const now = Date.now();
        const prev = this.__searchReqKeyPolicyView || null;
        if (prev && prev.src === p && prev.exp > now && prev.value) return prev.value;
        const toInt = this.searchToInt;
        const clamp = this.searchClamp;
        const value = {
            reqKeySweepEveryOps: clamp(toInt(p.reqKeySweepEveryOps, 24), 1, 256),
            reqKeySweepMinIntervalMs: clamp(toInt(p.reqKeySweepMinIntervalMs, 120), 10, 3000),
            reqKeySweepScan: clamp(toInt(p.reqKeySweepScan, 64), 8, 512),
            reqKeyCacheMax: clamp(toInt(p.reqKeyCacheMax, 512), 64, 4096),
            reqKeyTouchMinIntervalMs: clamp(toInt(p.reqKeyTouchMinIntervalMs, 0), 0, 5000),
            reqKeyCacheTtlMs: clamp(toInt(p.reqKeyCacheTtlMs, 30000), 1000, 300000),
            reqKeyCacheIndexMaxLen: clamp(toInt(p.reqKeyCacheIndexMaxLen, 640), 128, 4096),
            reqKeyRawUrlProbeMaxLen: clamp(toInt(p.reqKeyRawUrlProbeMaxLen, 2048), 256, 16384),
            requestKeyMaxLen: clamp(toInt(p.requestKeyMaxLen, 260), 96, 1024),
        };
        this.__searchReqKeyPolicyView = { src: p, value, exp: now + 1500 };
        return value;
    },

    searchReqKeyScope: function(now) {
        const uid = this.searchCurrentUid();
        if (uid > 0) return `u:${uid}`;
        const cached = this.__searchScope || null;
        if (cached && cached.exp > now && cached.key) return String(cached.key);
        let sid = String(this.__searchSid || '');
        if (!sid) {
            try {
                sid = String(localStorage.getItem('__aiseek_sid') || '');
            } catch (_) {
                sid = '';
            }
        }
        if (!sid) {
            sid = `${now.toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
            try { localStorage.setItem('__aiseek_sid', sid); } catch (_) {}
        }
        this.__searchSid = sid;
        const scope = `g:${sid.slice(0, 48)}`;
        this.__searchScope = { key: scope, exp: now + 60000 };
        return scope;
    },

    searchReqKeyFallbackKey: function(url, policy) {
        try {
            const cfg = this.searchReqKeyPolicyView(policy);
            return this.searchBoundKey(`g:anon|${String(url || '')}`, cfg.requestKeyMaxLen);
        } catch (_) {
            return this.searchBoundKey(`g:anon|${String(url || '')}`, 260);
        }
    },

    searchScopedRequestKey: function(url) {
        try {
            const policy = this.searchCachePolicy();
            const cfg = this.searchReqKeyPolicyView(policy);
            const u = String(url || '');
            this.searchReqKeyCacheEnsure();
            const now = Date.now();
            const reqKeyOps = this.searchCounterNext('__searchReqKeyOps', 1000000000);
            if (this.searchShouldSweep(reqKeyOps, cfg.reqKeySweepEveryOps) && this.searchSweepAllow('reqkey', cfg.reqKeySweepMinIntervalMs)) {
                this.searchReqKeySweepExpired(cfg.reqKeySweepScan, now);
                this.searchReqKeyTrimToCap(cfg.reqKeyCacheMax);
            }
            const scope = this.searchReqKeyScope(now);
            const raw = this.searchScopedRawKey(scope, u, cfg.reqKeyRawUrlProbeMaxLen);
            const boundPair = this.searchBoundKeyPair(raw, cfg.reqKeyCacheIndexMaxLen, cfg.requestKeyMaxLen);
            const cacheKey = boundPair.first;
            const hitKey = this.searchReqKeyGetMaybe(cacheKey, now, cfg.reqKeyTouchMinIntervalMs);
            if (hitKey) return hitKey;
            const key = boundPair.second;
            this.searchReqKeyPut(cacheKey, key, now, cfg.reqKeyCacheTtlMs, cfg.reqKeyCacheMax);
            return key;
        } catch (_) {
            return this.searchReqKeyFallbackKey(url, null);
        }
    },

    searchCancelPolicyView: function(policy) {
        const p = policy || this.searchCachePolicy();
        const now = Date.now();
        const prev = this.__searchCancelPolicyView || null;
        if (prev && prev.src === p && prev.exp > now && prev.value) return prev.value;
        const toInt = this.searchToInt;
        const clamp = this.searchClamp;
        const value = {
            cancelChannelProbeMaxLen: clamp(toInt(p.cancelChannelProbeMaxLen, 512), 64, 4096),
            breakerChannelMaxLen: clamp(toInt(p.breakerChannelMaxLen, 64), 24, 1024),
        };
        this.__searchCancelPolicyView = { src: p, value, exp: now + 1500 };
        return value;
    },

    searchCancelCachePolicyView: function(policy) {
        const p = policy || this.searchCachePolicy();
        const now = Date.now();
        const prev = this.__searchCancelCachePolicyView || null;
        if (prev && prev.src === p && prev.exp > now && prev.value) return prev.value;
        const toInt = this.searchToInt;
        const clamp = this.searchClamp;
        const value = {
            ttlMs: clamp(toInt(p.sweepMinIntervalMs, 120) * 20, 2000, 180000),
            cap: clamp(toInt(p.breakerMax, 256) * 8, 128, 20000),
            keyMaxLen: clamp(toInt(p.reqKeyCacheIndexMaxLen, 640), 96, 4096),
            touchMinMs: clamp(toInt(p.cacheTouchMinIntervalMs, 200), 0, 5000),
            sweepEveryOps: clamp(toInt(p.sweepEveryOps, 16), 1, 512),
            sweepScan: clamp(toInt(p.sweepScan, 24), 8, 4096),
            sweepMinIntervalMs: clamp(toInt(p.sweepMinIntervalMs, 120), 10, 3000),
        };
        this.__searchCancelCachePolicyView = { src: p, value, exp: now + 1500 };
        return value;
    },

    searchCancelCacheEnsure: function() {
        if (!this.__searchCancelCache) this.__searchCancelCache = new Map();
        return this.__searchCancelCache;
    },

    searchCancelCacheGetMaybe: function(cacheKey, now, touchMin) {
        const cache = this.searchCancelCacheEnsure();
        const hit = cache.get(cacheKey);
        if (!hit || !hit.v) return '';
        const exp = Number(hit.exp || 0);
        if (!exp || exp <= now) {
            cache.delete(cacheKey);
            return '';
        }
        const lastAt = Number(hit.at || 0);
        if (touchMin <= 0 || !lastAt || (now - lastAt) >= touchMin) {
            hit.at = now;
            cache.delete(cacheKey);
            cache.set(cacheKey, hit);
        }
        return String(hit.v);
    },

    searchCancelCachePut: function(cacheKey, value, now, ttlMs, cap) {
        const cache = this.searchCancelCacheEnsure();
        const ttl = this.searchDurationLimit(ttlMs, 0, 1800000);
        if (ttl <= 0) return;
        cache.set(cacheKey, { v: String(value || ''), exp: now + ttl, at: now });
        this.searchMapTrimToCap(cache, cap);
    },

    searchCancelCacheSweepExpired: function(maxScan, nowTs) {
        const cache = this.searchCancelCacheEnsure();
        if (cache.size === 0) return 0;
        const n = this.searchSweepScanLimit(maxScan, 24, 4096);
        const now = Number(nowTs || 0) > 0 ? Number(nowTs) : Date.now();
        let scanned = 0;
        let removed = 0;
        for (const [k, v] of cache.entries()) {
            if (scanned >= n) break;
            scanned += 1;
            const exp = Number(v && v.exp || 0);
            if (!exp || exp <= now) {
                cache.delete(k);
                removed += 1;
            }
        }
        return removed;
    },

    searchCancelChannelFromKey: function(rawKey, policy, policyView) {
        const s = String(rawKey || '');
        if (!s) return 'misc';
        const cfg = policyView || this.searchCancelPolicyView(policy);
        const p = policy || this.searchCachePolicy();
        const cacheCfg = this.searchCancelCachePolicyView(p);
        const now = Date.now();
        const cacheOps = this.searchCounterNext('__searchCancelCacheOps', 1000000000);
        if (this.searchShouldSweep(cacheOps, cacheCfg.sweepEveryOps) && this.searchSweepAllow('cancelcache', cacheCfg.sweepMinIntervalMs)) {
            this.searchCancelCacheSweepExpired(cacheCfg.sweepScan, now);
            this.searchMapTrimToCap(this.searchCancelCacheEnsure(), cacheCfg.cap);
        }
        const cacheKey = this.searchBoundKey(s, cacheCfg.keyMaxLen);
        const hit = this.searchCancelCacheGetMaybe(cacheKey, now, cacheCfg.touchMinMs);
        if (hit) return hit;
        const probeRaw = s.length > cfg.cancelChannelProbeMaxLen ? s.slice(0, cfg.cancelChannelProbeMaxLen) : s;
        const probe = probeRaw.toLowerCase();
        let out = '';
        if (probe.indexOf('/search/posts') >= 0 || probe.indexOf('search:more:posts') >= 0) out = 'posts';
        else if (probe.indexOf('/users/search-user') >= 0 || probe.indexOf('search:more:users') >= 0) out = 'users';
        else if (probe.indexOf('/search/hot') >= 0 || probe.indexOf('search:hot') >= 0) out = 'hot';
        else out = this.searchBoundKey(`misc:${probe}`, cfg.breakerChannelMaxLen);
        this.searchCancelCachePut(cacheKey, out, now, cacheCfg.ttlMs, cacheCfg.cap);
        return out;
    },

    renderSearchDropdown: function() {
        const wrap = document.getElementById('search_history_wrap');
        if (!wrap) return;
        const arr = this.getSearchHistory();
        if (!arr.length) {
            wrap.innerHTML = '';
        } else {
            wrap.innerHTML = `
                <div class="search-history-head">
                    <div class="search-history-title">搜索记录</div>
                    <div class="search-history-clear" data-action="call" data-fn="clearSearchHistory" data-args="[]">清除</div>
                </div>
                ${arr.map(k => `
                    <div class="hot-word-item" data-action="call" data-fn="doSearch" data-args='[${JSON.stringify(k)}]'>
                        <div class="hot-rank" style="width:18px; height:18px;"><i class="fas fa-history" style="font-size:10px;"></i></div>
                        <div class="hot-text">${this.escapeHtml(k)}</div>
                    </div>
                `).join('')}
                <div style="height:10px;"></div>
            `;
        }
        try { this.renderSearchHotWords(); } catch (_) {}
    },

    fetchSearchHotWords: async function() {
        const now = Date.now();
        const prev = this.__searchHotCache || null;
        if (prev && prev.exp && prev.exp > now && Array.isArray(prev.items)) return prev.items;
        if (this.__searchHotInflight) {
            try { return await this.__searchHotInflight; } catch (_) {}
        }
        try {
            this.__searchHotInflight = (async () => {
                const res = await this.apiRequest('GET', '/api/v1/search/hot?limit=6', undefined, { cancel_key: 'search:hot', dedupe_key: 'search:hot' });
                if (!res.ok) throw new Error('hot_failed');
                const data = await res.json();
                const items = Array.isArray(data) ? data.map(x => String(x || '').trim()).filter(Boolean).slice(0, 12) : [];
                this.__searchHotCache = { exp: Date.now() + 30_000, items };
                return items;
            })();
            return await this.__searchHotInflight;
        } catch (_) {
            this.__searchHotCache = { exp: Date.now() + 10_000, items: [] };
            return [];
        } finally {
            try { this.__searchHotInflight = null; } catch (_) {}
        }
    },

    renderSearchHotWords: async function() {
        const dd = document.getElementById('search_hot_dropdown');
        if (!dd) return;
        try {
            const input = this.getGlobalSearchInput();
            const ae = document.activeElement;
            const active = dd.classList && dd.classList.contains('active');
            const focused = input && ae && (ae === input || (ae.closest && ae.closest('.search-bar')));
            if (!active && !focused) return;
        } catch (_) {}
        const now = Date.now();
        try {
            if (this.__searchHotRenderAt && now - this.__searchHotRenderAt < 400) return;
        } catch (_) {}
        this.__searchHotRenderAt = now;
        const title = dd.querySelector('.hot-word-title');
        if (!title) return;
        let box = dd.querySelector('#search_hot_words');
        if (!box) {
            box = document.createElement('div');
            box.id = 'search_hot_words';
            title.insertAdjacentElement('afterend', box);
            try {
                let cur = box.nextElementSibling;
                const moved = [];
                while (cur && cur.classList && cur.classList.contains('hot-word-item')) {
                    const nxt = cur.nextElementSibling;
                    moved.push(cur);
                    cur = nxt;
                }
                moved.forEach(el => {
                    try { box.appendChild(el); } catch (_) {}
                });
            } catch (_) {}
        }
        const items = await this.fetchSearchHotWords();
        if (!items.length) return;
        const sig = items.join('\u0001');
        if (this.__searchHotSig === sig) return;
        this.__searchHotSig = sig;
        box.innerHTML = items.map((k, idx) => {
            const rank = idx + 1;
            const cls = rank <= 3 ? 'hot-rank top3' : 'hot-rank';
            return `
                <div class="hot-word-item" data-action="call" data-fn="doSearch" data-args='[${JSON.stringify(k)}]'>
                    <div class="${cls}">${rank}</div>
                    <div class="hot-text">${this.escapeHtml(k)}</div>
                </div>
            `;
        }).join('');
    },

    doSearch: function(keyword) {
        const input = this.getGlobalSearchInput();
        if (input) input.value = keyword;
        this.addSearchHistory(keyword);
        this.searchUser();
    },

    searchUserCommit: function(query) {
        this.switchPage('search');
        this.state.searchKeyword = query;
        this.addSearchHistory(query);
        this.searchSyncRouteHash();
        this.switchSearchTab('all');
    },

    searchUser: async function() {
        const input = this.getGlobalSearchInput();
        const query = input ? String(input.value || '').trim() : '';
        if (!query) return alert('请输入搜索内容');
        try {
            const uid = this.searchCurrentUid();
            if (window.appEmit) window.appEmit('search:query', { q: query, user_id: uid || null });
        } catch (_) {}

        try {
            if (this.__searchTimer) clearTimeout(this.__searchTimer);
        } catch (_) {}
        if (!this.__searchUserCommitBound) this.__searchUserCommitBound = (q) => this.searchUserCommit(q);
        this.__searchTimer = setTimeout(this.__searchUserCommitBound, 280, query);
    },

    switchSearchTab: function(mode) {
        const m = mode || 'all';
        this.state.searchMode = m;
        let tabs = this.__searchTabEls || null;
        if (!tabs) {
            tabs = {
                a: document.getElementById('search_tab_all'),
                b: document.getElementById('search_tab_video'),
                c: document.getElementById('search_tab_user'),
            };
            this.__searchTabEls = tabs;
        }
        const a = tabs.a;
        const b = tabs.b;
        const c = tabs.c;
        if (a && b && c) {
            a.classList.toggle('active', m === 'all');
            b.classList.toggle('active', m === 'video');
            c.classList.toggle('active', m === 'user');
        }
        this.searchSyncQualityFilterUi();
        this.searchSyncRouteHash();
        this.renderSearchResults();
    },

    searchQualityFilterMode: function() {
        const m = String(this.state.searchQualityMode || 'all').trim().toLowerCase();
        if (m === 'cd' || m === 'd' || m === 'score' || m === 'unrated') return m;
        return 'all';
    },

    searchQualityThreshold: function() {
        const v = Math.round(Number(this.state.searchQualityThreshold || 70) || 70);
        if (v < 1) return 1;
        if (v > 100) return 100;
        return v;
    },

    searchQualitySortMode: function() {
        this.searchQualitySortPrefLoad();
        const m = String(this.state.searchQualitySort || 'default').trim().toLowerCase();
        if (m === 'quality' || m === 'unrated') return m;
        return 'default';
    },

    searchExportTemplateCurrent: function() {
        this.searchExportTemplateLoad();
        const t = String(this.state.searchExportTemplate || 'standard').trim().toLowerCase();
        if (t === 'qa' || t === 'lite' || t === 'custom') return t;
        return 'standard';
    },

    searchExportAllColumns: function() {
        return ['post_id', 'title', 'author', 'quality_grade', 'quality_score', 'avg_cps', 'max_line_len', 'dense_ratio', 'cue_count', 'cover_provider', 'cover_ms', 'cover_degrade_count', 'cover_no_key_count', 'created_at', 'search_query', 'search_mode', 'quality_filter', 'quality_threshold', 'quality_sort', 'route_hash'];
    },

    searchExportColumnsFromCustomRaw: function(raw) {
        const allow = new Set(this.searchExportAllColumns());
        const arr = String(raw || '').split(',').map((x) => String(x || '').trim()).filter(Boolean);
        const out = [];
        for (let i = 0; i < arr.length; i++) {
            const k = arr[i];
            if (allow.has(k) && out.indexOf(k) < 0) out.push(k);
        }
        return out;
    },

    searchExportTemplateColumns: function(tpl) {
        const t = String(tpl || this.searchExportTemplateCurrent()).trim().toLowerCase();
        if (t === 'lite') {
            return ['post_id', 'title', 'author', 'quality_grade', 'quality_score', 'search_query', 'search_mode', 'quality_filter', 'quality_sort'];
        }
        if (t === 'qa') {
            return ['post_id', 'title', 'author', 'quality_grade', 'quality_score', 'avg_cps', 'max_line_len', 'dense_ratio', 'cue_count', 'cover_provider', 'cover_ms', 'cover_degrade_count', 'cover_no_key_count', 'created_at', 'search_query', 'search_mode', 'quality_filter', 'quality_threshold', 'quality_sort', 'route_hash'];
        }
        if (t === 'custom') {
            this.searchExportCustomColumnsLoad();
            const cols = this.searchExportColumnsFromCustomRaw(this.state.searchExportCustomColumns || '');
            return cols.length > 0 ? cols : ['post_id', 'title', 'author', 'quality_grade', 'quality_score', 'search_query', 'search_mode'];
        }
        return ['post_id', 'title', 'author', 'quality_grade', 'quality_score', 'avg_cps', 'max_line_len', 'dense_ratio', 'cue_count', 'cover_provider', 'cover_ms', 'cover_degrade_count', 'cover_no_key_count', 'created_at', 'search_query', 'search_mode', 'quality_filter', 'quality_threshold', 'quality_sort'];
    },

    searchSyncQualityFilterUi: function() {
        try {
            const modeBtn = document.getElementById('search_filter_quality_mode');
            const thBtn = document.getElementById('search_filter_quality_threshold');
            const thSel = document.getElementById('search_filter_quality_threshold_select');
            const sortBtn = document.getElementById('search_filter_quality_sort');
            const expTplSel = document.getElementById('search_export_template_select');
            const mode = this.searchQualityFilterMode();
            const th = this.searchQualityThreshold();
            const sort = this.searchQualitySortMode();
            const tpl = this.searchExportTemplateCurrent();
            const modeText = mode === 'all' ? '模式：全部' : (mode === 'cd' ? '模式：C+D' : (mode === 'd' ? '模式：仅D' : (mode === 'unrated' ? '模式：仅无评分' : '模式：分数阈值')));
            if (modeBtn) {
                modeBtn.classList.toggle('active', mode !== 'all');
                modeBtn.setAttribute('aria-pressed', mode !== 'all' ? 'true' : 'false');
                modeBtn.textContent = modeText;
            }
            if (thBtn) {
                thBtn.classList.toggle('active', mode === 'score');
                thBtn.setAttribute('aria-pressed', mode === 'score' ? 'true' : 'false');
                thBtn.textContent = `阈值：<${th}`;
            }
            if (thSel) {
                thSel.value = '';
                const opt = thSel.querySelector(`option[value="${th}"]`);
                if (opt && mode === 'score') thSel.value = String(th);
            }
            if (sortBtn) {
                sortBtn.classList.toggle('active', sort !== 'default');
                sortBtn.setAttribute('aria-pressed', sort !== 'default' ? 'true' : 'false');
                sortBtn.textContent = sort === 'default' ? '排序：默认' : (sort === 'quality' ? '排序：质量巡检' : '排序：无评分优先');
            }
            if (expTplSel) expTplSel.value = tpl;
        } catch (_) {
        }
    },

    toggleSearchQualityMode: function() {
        const mode = this.searchQualityFilterMode();
        const next = mode === 'all' ? 'cd' : (mode === 'cd' ? 'd' : (mode === 'd' ? 'unrated' : (mode === 'unrated' ? 'score' : 'all')));
        this.state.searchQualityMode = next;
        this.searchSyncQualityFilterUi();
        this.searchSyncRouteHash();
        this.renderSearchResults();
    },

    setSearchQualityThreshold: function() {
        try {
            const cur = this.searchQualityThreshold();
            const got = window.prompt('请输入分数阈值（1-100）', String(cur));
            if (got === null) return;
            const v = Math.round(Number(got) || 0);
            if (!v || v < 1 || v > 100) return;
            this.state.searchQualityThreshold = v;
        } catch (_) {
            return;
        }
        this.searchSyncQualityFilterUi();
        this.searchSyncRouteHash();
        this.renderSearchResults();
    },

    setSearchQualityThresholdPreset: function(v) {
        const n = Math.round(Number(v) || 0);
        if (!n || n < 1 || n > 100) return;
        this.state.searchQualityThreshold = n;
        if (this.searchQualityFilterMode() !== 'score') this.state.searchQualityMode = 'score';
        this.searchSyncQualityFilterUi();
        this.searchSyncRouteHash();
        this.renderSearchResults();
    },

    toggleSearchQualitySort: function() {
        const m = this.searchQualitySortMode();
        const next = m === 'default' ? 'quality' : (m === 'quality' ? 'unrated' : 'default');
        this.state.searchQualitySort = next;
        this.searchQualitySortPrefSave();
        this.searchSyncQualityFilterUi();
        this.searchSyncRouteHash();
        this.renderSearchResults();
    },

    setSearchExportTemplatePreset: function(v) {
        const t = String(v || '').trim().toLowerCase();
        if (t !== 'standard' && t !== 'qa' && t !== 'lite' && t !== 'custom') return;
        this.state.searchExportTemplate = t;
        if (t === 'custom') this.searchExportCustomColumnsLoad();
        this.searchExportTemplateSave();
        this.searchSyncQualityFilterUi();
    },

    configureSearchExportColumns: function() {
        try {
            this.searchExportCustomColumnsLoad();
            const allow = this.searchExportAllColumns();
            const hint = allow.join(', ');
            const current = String(this.state.searchExportCustomColumns || '');
            const got = window.prompt(`请输入导出字段，英文逗号分隔\n可选：${hint}`, current || 'post_id,title,author,quality_grade,quality_score,search_query,search_mode');
            if (got === null) return;
            const cols = this.searchExportColumnsFromCustomRaw(got);
            if (!cols.length) {
                alert('至少保留一个合法字段');
                return;
            }
            const raw = cols.join(',');
            this.state.searchExportCustomColumns = raw;
            this.searchExportCustomColumnsSave(raw);
            this.state.searchExportTemplate = 'custom';
            this.searchExportTemplateSave();
            this.searchSyncQualityFilterUi();
        } catch (_) {
            alert('字段配置失败，请重试');
        }
    },

    searchRenderExportHistoryPanel: function() {
        const wrap = document.getElementById('search_export_history_panel');
        const body = document.getElementById('search_export_history_panel_body');
        const pager = document.getElementById('search_export_history_panel_pager');
        const filterInput = document.getElementById('search_export_history_filter_input');
        const rangeSel = document.getElementById('search_export_history_range_select');
        if (!wrap || !body || !pager) return;
        const arr = this.searchGetExportHistory();
        const kw = this.searchHistoryPanelKeyword();
        const range = this.searchHistoryPanelRange();
        const selected = this.searchHistoryPanelSelection();
        if (filterInput && String(filterInput.value || '').trim().toLowerCase() !== kw) filterInput.value = this.__searchHistoryPanelKeyword || '';
        if (rangeSel && String(rangeSel.value || '').trim().toLowerCase() !== range) rangeSel.value = range;
        const entries = this.searchHistoryPanelFilteredEntries(arr);
        const maxIdx = Math.max(0, arr.length - 1);
        Array.from(selected).forEach((idx) => {
            if (!Number.isFinite(Number(idx)) || Number(idx) < 0 || Number(idx) > maxIdx) selected.delete(idx);
        });
        if (!entries.length) {
            body.innerHTML = '<div class="search-export-empty">暂无导出记录</div>';
            pager.textContent = '第 0/0 页';
            return;
        }
        const pageSize = 8;
        const pageCount = Math.max(1, Math.ceil(entries.length / pageSize));
        const page = Math.min(this.searchHistoryPanelPage(), pageCount);
        this.__searchHistoryPanelPage = page;
        const start = (page - 1) * pageSize;
        const end = Math.min(entries.length, start + pageSize);
        let html = '';
        for (let i = start; i < end; i++) {
            const row = entries[i];
            const rowIdx = row.idx;
            const it = row.item || {};
            const dt = new Date(Number(it.at_ms || 0) || Date.now()).toLocaleString();
            const pin = it.pinned ? '📌' : '';
            const query = this.escapeHtml(String(it.query || '-'));
            const meta = `${this.escapeHtml(String(it.template || 'standard'))} · ${Math.max(0, Number(it.count || 0) || 0)}条 · ${this.escapeHtml(String(it.search_mode || 'all'))} · ${this.escapeHtml(String(it.filter || 'all'))} · ${this.escapeHtml(String(it.sort || 'default'))}`;
            html += `
                <div class="search-export-row">
                    <div class="search-export-main">
                        <div class="search-export-title">${pin} ${query}</div>
                        <div class="search-export-meta">${this.escapeHtml(dt)} · ${meta}</div>
                    </div>
                    <div class="search-export-actions">
                        <button class="search-export-btn" data-action="call" data-fn="searchHistoryPanelToggleSelect" data-args="[${rowIdx}]">${selected.has(rowIdx) ? '取消选择' : '选择'}</button>
                        <button class="search-export-btn" data-action="call" data-fn="searchHistoryPanelReplay" data-args="[${rowIdx}]">重放</button>
                        <button class="search-export-btn" data-action="call" data-fn="searchHistoryPanelTogglePin" data-args="[${rowIdx}]">${it.pinned ? '取消固定' : '固定'}</button>
                        <button class="search-export-btn danger" data-action="call" data-fn="searchHistoryPanelDelete" data-args="[${rowIdx}]">删除</button>
                    </div>
                </div>
            `;
        }
        body.innerHTML = html;
        pager.textContent = `第 ${page}/${pageCount} 页 · 共 ${entries.length} 条 · 已选 ${selected.size}`;
    },

    searchOpenExportHistoryPanel: function() {
        const wrap = document.getElementById('search_export_history_panel');
        if (!wrap) return;
        this.__searchHistoryPanelPage = 1;
        this.__searchHistoryPanelSelection = new Set();
        this.searchRenderHistoryViewSelect();
        wrap.classList.add('active');
        this.searchRenderExportHistoryPanel();
    },

    searchCloseExportHistoryPanel: function() {
        const wrap = document.getElementById('search_export_history_panel');
        if (!wrap) return;
        wrap.classList.remove('active');
    },

    searchHistoryPanelReplay: function(index) {
        this.searchReplayExportHistoryByIndex(index);
        this.searchCloseExportHistoryPanel();
    },

    searchHistoryPanelTogglePin: function(index) {
        this.searchTogglePinExportHistoryByIndex(index);
    },

    searchHistoryPanelDelete: function(index) {
        const ok = window.confirm('确认删除这条导出历史吗？');
        if (!ok) return;
        this.searchDeleteExportHistoryByIndex(index);
    },

    searchHistoryPanelClear: function() {
        this.clearSearchExportHistory();
    },

    searchHistoryPanelSetRange: function(v) {
        const r = String(v || '').trim().toLowerCase();
        this.__searchHistoryPanelRange = (r === '1d' || r === '7d' || r === '30d' || r === '90d') ? r : 'all';
        this.__searchHistoryViewActiveName = '';
        this.searchRenderHistoryViewSelect();
        this.__searchHistoryPanelPage = 1;
        this.searchRenderExportHistoryPanel();
    },

    searchHistoryPanelSetKeyword: function(v) {
        this.__searchHistoryPanelKeyword = String(v || '').trim();
        this.__searchHistoryViewActiveName = '';
        this.searchRenderHistoryViewSelect();
        this.__searchHistoryPanelPage = 1;
        this.searchRenderExportHistoryPanel();
    },

    searchHistoryPanelClearKeyword: function() {
        this.__searchHistoryPanelKeyword = '';
        this.__searchHistoryPanelPage = 1;
        const input = document.getElementById('search_export_history_filter_input');
        if (input) input.value = '';
        this.searchRenderExportHistoryPanel();
    },

    searchHistoryPanelPrevPage: function() {
        const cur = this.searchHistoryPanelPage();
        this.__searchHistoryPanelPage = Math.max(1, cur - 1);
        this.searchRenderExportHistoryPanel();
    },

    searchHistoryPanelNextPage: function() {
        const cur = this.searchHistoryPanelPage();
        this.__searchHistoryPanelPage = cur + 1;
        this.searchRenderExportHistoryPanel();
    },

    searchHistoryPanelToggleSelect: function(index) {
        const idx = Math.max(0, Math.floor(Number(index || 0) || 0));
        const set = this.searchHistoryPanelSelection();
        if (set.has(idx)) set.delete(idx);
        else set.add(idx);
        this.searchRenderExportHistoryPanel();
    },

    searchHistoryPanelToggleSelectPage: function() {
        const entries = this.searchHistoryPanelFilteredEntries().map((x) => x.idx);
        const page = this.searchHistoryPanelPage();
        const start = (page - 1) * 8;
        const pageIdx = entries.slice(start, start + 8);
        if (!pageIdx.length) return;
        const set = this.searchHistoryPanelSelection();
        const allSelected = pageIdx.every((x) => set.has(x));
        for (let i = 0; i < pageIdx.length; i++) {
            if (allSelected) set.delete(pageIdx[i]);
            else set.add(pageIdx[i]);
        }
        this.searchRenderExportHistoryPanel();
    },

    searchHistoryPanelBulkPin: function(targetPinned) {
        const target = !!targetPinned;
        const set = this.searchHistoryPanelSelection();
        const ids = Array.from(set).map((x) => Math.max(0, Math.floor(Number(x || 0) || 0))).sort((a, b) => b - a);
        if (!ids.length) {
            alert('请先选择要操作的历史');
            return;
        }
        const ok = window.confirm(target ? `确认固定已选的 ${ids.length} 条历史吗？` : `确认取消固定已选的 ${ids.length} 条历史吗？`);
        if (!ok) return;
        const arr = this.searchGetExportHistory();
        const ts = Date.now();
        for (let i = 0; i < ids.length; i++) {
            const idx = ids[i];
            if (idx < 0 || idx >= arr.length) continue;
            arr[idx].pinned = target;
            arr[idx].pin_at_ms = target ? ts : 0;
        }
        this.searchSetExportHistory(arr);
        this.searchRenderExportHistoryPanel();
    },

    searchHistoryPanelBulkPinOn: function() {
        this.searchHistoryPanelBulkPin(true);
    },

    searchHistoryPanelBulkPinOff: function() {
        this.searchHistoryPanelBulkPin(false);
    },

    searchHistoryPanelBulkDelete: function() {
        const set = this.searchHistoryPanelSelection();
        const ids = Array.from(set).map((x) => Math.max(0, Math.floor(Number(x || 0) || 0))).sort((a, b) => b - a);
        if (!ids.length) {
            alert('请先选择要删除的历史');
            return;
        }
        const ok = window.confirm(`确认删除已选的 ${ids.length} 条历史吗？`);
        if (!ok) return;
        const arr = this.searchGetExportHistory();
        for (let i = 0; i < ids.length; i++) {
            const idx = ids[i];
            if (idx >= 0 && idx < arr.length) arr.splice(idx, 1);
        }
        this.searchSetExportHistory(arr);
        this.__searchHistoryPanelSelection = new Set();
        this.searchRenderExportHistoryPanel();
    },

    searchHistoryPanelExportFilteredCsv: function() {
        const arr = this.searchGetExportHistory();
        const entries = this.searchHistoryPanelFilteredEntries(arr);
        if (!entries.length) {
            alert('当前筛选无可导出的历史');
            return;
        }
        const now = Date.now();
        const head = ['at_ms', 'at_local', 'query', 'template', 'count', 'search_mode', 'quality_filter', 'quality_sort', 'quality_threshold', 'pinned', 'route_hash', 'custom_columns'];
        const rows = [head.join(',')];
        for (let i = 0; i < entries.length; i++) {
            const it = entries[i].item || {};
            const atMs = Math.max(0, Number(it.at_ms || 0) || 0);
            const row = [
                atMs,
                atMs ? new Date(atMs).toLocaleString() : '',
                String(it.query || ''),
                String(it.template || 'standard'),
                Math.max(0, Number(it.count || 0) || 0),
                String(it.search_mode || 'all'),
                String(it.filter || 'all'),
                String(it.sort || 'default'),
                Math.max(1, Math.min(100, Math.round(Number(it.quality_threshold || 70) || 70))),
                it.pinned ? 1 : 0,
                String(it.route_hash || ''),
                String(it.custom_columns || ''),
            ];
            rows.push(row.map((x) => this.searchCsvCell(x)).join(','));
        }
        const csv = '\ufeff' + rows.join('\n');
        this.searchDownloadTextFile(`search_export_history_filtered_${now}.csv`, csv, 'text/csv;charset=utf-8;');
    },

    openSearchExportHistory: function() {
        this.searchOpenExportHistoryPanel();
    },

    openSearchExportHistoryPrompt: function() {
        const arr = this.searchGetExportHistory();
        if (!arr.length) {
            alert('暂无导出记录');
            return;
        }
        const lines = [];
        for (let i = 0; i < arr.length && i < 10; i++) {
            const it = arr[i] || {};
            const dt = new Date(Number(it.at_ms || 0) || Date.now());
            lines.push(`${i + 1}. ${it.pinned ? '📌' : '  '} ${dt.toLocaleString()} | ${String(it.template || 'standard')} | ${Math.max(0, Number(it.count || 0) || 0)}条 | ${String(it.query || '-')} | ${String(it.search_mode || 'all')} | ${String(it.filter || 'all')} | ${String(it.sort || 'default')}`);
        }
        const msg = `最近导出记录（最多10条）\n${lines.join('\n')}\n\n输入序号重放（1-${Math.min(10, arr.length)}）\n输入 p序号 固定/取消固定，如 p1\n输入 d序号 删除，如 d2\n输入 clear 清空全部`;
        const got = window.prompt(msg, '');
        if (got === null || String(got).trim() === '') return;
        const cmd = String(got).trim().toLowerCase();
        if (cmd === 'clear') {
            const ok = window.confirm('确认清空全部导出历史吗？');
            if (!ok) return;
            this.clearSearchExportHistory(true);
            alert('已清空导出历史');
            return;
        }
        if (/^p\d+$/.test(cmd)) {
            const n = Math.floor(Number(cmd.slice(1)) || 0);
            if (n < 1 || n > Math.min(10, arr.length)) {
                alert('序号无效');
                return;
            }
            this.searchTogglePinExportHistoryByIndex(n - 1);
            alert('已更新固定状态');
            return;
        }
        if (/^d\d+$/.test(cmd)) {
            const n = Math.floor(Number(cmd.slice(1)) || 0);
            if (n < 1 || n > Math.min(10, arr.length)) {
                alert('序号无效');
                return;
            }
            this.searchDeleteExportHistoryByIndex(n - 1);
            alert('已删除该条历史');
            return;
        }
        const n = Math.floor(Number(cmd) || 0);
        if (n < 1 || n > Math.min(10, arr.length)) { alert('序号无效'); return; }
        this.searchReplayExportHistoryByIndex(n - 1);
    },

    searchParseRouteHashParams: function(hash) {
        const out = { q: '', smode: '', qf: '', qth: 0, qsort: '' };
        try {
            const h = String(hash || '').trim();
            const idx = h.indexOf('?');
            if (idx < 0) return out;
            const qs = new URLSearchParams(h.slice(idx + 1));
            out.q = String(qs.get('q') || '').trim();
            out.smode = String(qs.get('smode') || '').trim();
            out.qf = String(qs.get('qf') || '').trim();
            out.qth = Math.round(Number(qs.get('qth') || 0) || 0);
            out.qsort = String(qs.get('qsort') || '').trim();
            return out;
        } catch (_) {
            return out;
        }
    },

    searchReplayExportHistoryByIndex: function(index) {
        const arr = this.searchGetExportHistory();
        const i = Math.max(0, Math.floor(Number(index || 0) || 0));
        if (!arr.length || i >= arr.length) return;
        const it = arr[i] || {};
        const parsed = this.searchParseRouteHashParams(it.route_hash || '');
        const route = {
            q: String(parsed.q || it.query || '').trim(),
            smode: String(parsed.smode || it.search_mode || 'all').trim(),
            qf: String(parsed.qf || it.filter || 'all').trim(),
            qth: Math.round(Number(parsed.qth || it.quality_threshold || 70) || 70),
            qsort: String(parsed.qsort || it.sort || 'default').trim(),
        };
        const tpl = String(it.template || '').trim().toLowerCase();
        if (tpl === 'standard' || tpl === 'qa' || tpl === 'lite' || tpl === 'custom') {
            this.state.searchExportTemplate = tpl;
            this.searchExportTemplateSave();
        }
        if (tpl === 'custom') {
            const raw = String(it.custom_columns || '').trim();
            if (raw) {
                this.state.searchExportCustomColumns = raw;
                this.searchExportCustomColumnsSave(raw);
            }
        }
        this.state.pendingSearchRoute = route;
        this.switchPage('search');
    },

    replayLatestSearchExportHistory: function() {
        this.searchReplayExportHistoryByIndex(0);
    },

    searchBuildRouteHash: function() {
        const q = String(this.state.searchKeyword || '').trim();
        if (!q) return '#/search';
        const mode = String(this.state.searchMode || 'all').trim() || 'all';
        const qf = this.searchQualityFilterMode();
        const qth = this.searchQualityThreshold();
        const qsort = this.searchQualitySortMode();
        const qs = new URLSearchParams();
        qs.set('q', q);
        qs.set('smode', mode);
        if (qf !== 'all') qs.set('qf', qf);
        if (qf === 'score') qs.set('qth', String(qth));
        if (qsort !== 'default') qs.set('qsort', qsort);
        return `#/search?${qs.toString()}`;
    },

    searchSyncRouteHash: function() {
        try {
            const cur = String(this.state.currentTab || '');
            if (cur !== 'search') return;
            const targetHash = this.searchBuildRouteHash();
            if (!targetHash || String(location.hash || '') === targetHash) return;
            const url = `${location.pathname}${location.search}${targetHash}`;
            if (window.history && typeof window.history.replaceState === 'function') window.history.replaceState(null, '', url);
            else location.hash = targetHash;
        } catch (_) {
        }
    },

    searchApplyRouteParams: function(route) {
        try {
            const r = route && typeof route === 'object' ? route : null;
            if (!r) {
                this.searchSyncQualityFilterUi();
                if (String(this.state.searchKeyword || '').trim()) this.renderSearchResults();
                return;
            }
            const svc = String(r.svc || '').trim();
            const svk = String(r.svk || '').trim();
            if (svk) this.searchImportHistoryViewsByShortKey(svk, true);
            else if (svc) this.searchImportHistoryViewsByShareCodeText(svc, true);
            const q = String(r.q || '').trim();
            const smode = String(r.smode || 'all').trim();
            const qf = String(r.qf || 'all').trim();
            const qth = Math.round(Number(r.qth || this.searchQualityThreshold()) || this.searchQualityThreshold());
            const qsortRaw = String(r.qsort || '').trim();
            if (q) {
                this.state.searchKeyword = q;
                const input = this.getGlobalSearchInput();
                if (input && input.value !== q) input.value = q;
            }
            this.state.searchQualityMode = qf;
            this.state.searchQualityThreshold = qth;
            if (qsortRaw) {
                this.state.searchQualitySort = qsortRaw;
                this.searchQualitySortPrefSave();
            } else {
                this.searchQualitySortPrefLoad();
            }
            this.switchSearchTab(['video', 'user', 'all'].includes(smode) ? smode : 'all');
        } catch (_) {
            this.searchSyncQualityFilterUi();
        }
    },

    searchRememberPosts: function(posts, reset) {
        if (reset || !this.__searchPostMap) this.__searchPostMap = new Map();
        const arr = Array.isArray(posts) ? posts : [];
        for (let i = 0; i < arr.length; i++) {
            const p = arr[i];
            const id = Number((p && p.id) || 0);
            if (!id) continue;
            this.__searchPostMap.set(id, p);
        }
    },

    searchCsvCell: function(v) {
        const s = String(v == null ? '' : v);
        if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
        return s;
    },

    searchDownloadTextFile: function(filename, text, mime) {
        const blob = new Blob([text], { type: String(mime || 'text/plain;charset=utf-8;') });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = String(filename || `export_${Date.now()}.txt`);
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1200);
    },

    exportSearchQualityCsv: function() {
        try {
            const grid = document.getElementById('search_results_grid');
            if (!grid) return;
            const cards = Array.from(grid.querySelectorAll('.s-card[data-post-id]'));
            if (!cards.length) {
                alert('当前无可导出的视频结果');
                return;
            }
            const map = this.__searchPostMap || new Map();
            const tpl = this.searchExportTemplateCurrent();
            const cols = this.searchExportTemplateColumns(tpl);
            const rows = [cols.join(',')];
            const q = String(this.state.searchKeyword || '').trim();
            const smode = String(this.state.searchMode || 'all');
            const qf = this.searchQualityFilterMode();
            const qth = this.searchQualityThreshold();
            const qsort = this.searchQualitySortMode();
            const routeHash = this.searchBuildRouteHash();
            const nowTs = Date.now();
            const snapRows = [];
            for (let i = 0; i < cards.length; i++) {
                const id = Number(cards[i].getAttribute('data-post-id') || 0);
                const p = map.get(id) || { id };
                const gq = p && typeof p.generation_quality === 'object' && p.generation_quality ? p.generation_quality : {};
                const sa = p && typeof p.subtitle_audit === 'object' && p.subtitle_audit ? p.subtitle_audit : {};
                const best = sa && typeof sa.best === 'object' && sa.best ? sa.best : {};
                const cm = p && typeof p.cover_metrics === 'object' && p.cover_metrics ? p.cover_metrics : {};
                const rowObj = {
                    post_id: Number((p && p.id) || id || 0),
                    title: (p && p.title) || '',
                    author: (p && (p.user_nickname || p.user_id)) || '',
                    quality_grade: String(gq.subtitle_quality_grade || '').toUpperCase(),
                    quality_score: Number(gq.subtitle_quality_score || 0) || 0,
                    avg_cps: Number(best.avg_cps || 0) || 0,
                    max_line_len: Number(best.max_line_len || 0) || 0,
                    dense_ratio: Number(best.dense_ratio || 0) || 0,
                    cue_count: Number(best.cue_count || 0) || 0,
                    cover_provider: String(cm.provider || ''),
                    cover_ms: Number(cm.total_provider_ms || 0) || 0,
                    cover_degrade_count: Number(cm.degrade_count || 0) || 0,
                    cover_no_key_count: Number(cm.skip_no_key_count || 0) || 0,
                    created_at: String((p && p.created_at) || ''),
                    search_query: q,
                    search_mode: smode,
                    quality_filter: qf,
                    quality_threshold: qth,
                    quality_sort: qsort,
                    route_hash: routeHash,
                };
                const row = cols.map((k) => this.searchCsvCell(rowObj[k]));
                rows.push(row.join(','));
                snapRows.push({
                    post_id: rowObj.post_id,
                    quality_grade: rowObj.quality_grade,
                    quality_score: rowObj.quality_score,
                    cover_ms: rowObj.cover_ms,
                    cover_degrade_count: rowObj.cover_degrade_count,
                });
            }
            const csv = '\ufeff' + rows.join('\n');
            const prefix = `search_quality_export_${nowTs}`;
            this.searchDownloadTextFile(`${prefix}.csv`, csv, 'text/csv;charset=utf-8;');
            const snapshot = {
                exported_at_ms: nowTs,
                query: q,
                search_mode: smode,
                quality_filter: qf,
                quality_threshold: qth,
                quality_sort: qsort,
                export_template: tpl,
                route_hash: routeHash,
                columns: cols,
                visible_count: cards.length,
                rows: snapRows,
            };
            this.searchDownloadTextFile(`${prefix}.json`, JSON.stringify(snapshot, null, 2), 'application/json;charset=utf-8;');
            this.searchRecordExportHistory({
                at_ms: nowTs,
                query: q,
                template: tpl,
                count: cards.length,
                filter: qf,
                sort: qsort,
                search_mode: smode,
                quality_threshold: qth,
                route_hash: routeHash,
                custom_columns: tpl === 'custom' ? String(this.state.searchExportCustomColumns || '') : '',
            });
        } catch (_) {
            alert('导出失败，请重试');
        }
    },

    searchRenderUserCard: function(u) {
        const avatar = (u && u.avatar) ? u.avatar : '/static/img/default_avatar.svg';
        const nickname = this.escapeHtml((u && (u.nickname || u.username)) || '');
        const aiseekId = String((u && (u.aiseek_id || u.id)) || '');
        const followers = Number((u && u.followers_count) || 0);
        const uid = Number((u && u.id) || 0);
        return `
                <div class="s-user" style="grid-column:1/-1;" data-action="call" data-fn="viewUserProfile" data-args="[${uid}]">
                    <img class="s-user-avatar" src="${avatar}">
                    <div class="s-user-info">
                        <div class="s-user-name">${nickname}</div>
                        <div class="s-user-sub">AIseek号：${aiseekId} · 粉丝 ${followers}</div>
                    </div>
                    <div class="s-user-right">
                        <div class="s-user-pill">进入主页</div>
                    </div>
                </div>
            `;
    },

    searchRenderUserList: function(users) {
        if (!Array.isArray(users) || users.length === 0) return '';
        let html = '';
        for (let i = 0; i < users.length; i++) {
            html += this.searchRenderUserCard(users[i]);
        }
        return html;
    },

    searchRenderTopUser: function(u) {
        if (!u) return '';
        return this.searchRenderUserCard(u);
    },

    searchStateKeyView: function() {
        const mode = String(this.state.searchMode || 'all');
        const query = String((this.state.searchKeyword || '').trim());
        const viewer = this.state.user ? this.state.user.id : '';
        const qMode = this.searchQualityFilterMode();
        const qTh = qMode === 'score' ? this.searchQualityThreshold() : 0;
        const qSort = this.searchQualitySortMode();
        return { mode, query, viewer, qMode, qTh, qSort, key: `${mode}|${query}|${String(viewer)}|${qMode}|${qTh}|${qSort}` };
    },

    searchPostQuality: function(p) {
        const gq = p && typeof p.generation_quality === 'object' && p.generation_quality ? p.generation_quality : null;
        if (!gq) return { grade: '', score: 0 };
        const grade = String(gq.subtitle_quality_grade || '').trim().toUpperCase();
        const score = Math.max(0, Math.min(100, Number(gq.subtitle_quality_score || 0) || 0));
        return { grade, score };
    },

    searchFilterPostsByQuality: function(posts) {
        const arr = Array.isArray(posts) ? posts : [];
        const mode = this.searchQualityFilterMode();
        const th = this.searchQualityThreshold();
        if (mode === 'all') return arr;
        const out = [];
        for (let i = 0; i < arr.length; i++) {
            const q = this.searchPostQuality(arr[i]);
            const g = q.grade;
            const s = q.score;
            if (mode === 'cd') {
                if (g === 'C' || g === 'D') out.push(arr[i]);
                continue;
            }
            if (mode === 'd') {
                if (g === 'D') out.push(arr[i]);
                continue;
            }
            if (mode === 'score') {
                if (s > 0 && s < th) out.push(arr[i]);
                continue;
            }
            if (mode === 'unrated') {
                if (!g && s <= 0) out.push(arr[i]);
            }
        }
        return out;
    },

    searchSortPostsByQuality: function(posts) {
        const arr = Array.isArray(posts) ? posts.slice() : [];
        const mode = this.searchQualitySortMode();
        if (mode === 'default') return arr;
        const rankGrade = (g) => {
            if (g === 'D') return 4;
            if (g === 'C') return 3;
            if (g === 'B') return 2;
            if (g === 'A') return 1;
            return 0;
        };
        arr.sort((a, b) => {
            const qa = this.searchPostQuality(a);
            const qb = this.searchPostQuality(b);
            const ga = String(qa.grade || '');
            const gb = String(qb.grade || '');
            const sa = Math.max(0, Number(qa.score || 0) || 0);
            const sb = Math.max(0, Number(qb.score || 0) || 0);
            const na = (!ga && sa <= 0) ? 1 : 0;
            const nb = (!gb && sb <= 0) ? 1 : 0;
            if (mode === 'unrated' && na !== nb) return nb - na;
            const ra = rankGrade(ga);
            const rb = rankGrade(gb);
            if (ra !== rb) return rb - ra;
            if (sa !== sb) return sa - sb;
            const aid = Number((a && a.id) || 0);
            const bid = Number((b && b.id) || 0);
            return bid - aid;
        });
        return arr;
    },

    searchCollectPostsForView: async function(query, limit, startCursor, cfg, fetchKind) {
        const q = String(query || '').trim();
        const lim = Math.max(1, Number(limit || 0) || 24);
        const mode = this.searchQualityFilterMode();
        const filterOn = mode !== 'all';
        const maxRounds = filterOn ? 4 : 1;
        let rounds = 0;
        let cursor = String(startCursor || '').trim();
        let nextCursor = '';
        let merged = [];
        let scannedPosts = 0;
        let matchedPosts = 0;
        while (rounds < maxRounds) {
            rounds += 1;
            const url = cursor
                ? `/api/v1/search/posts?q=${encodeURIComponent(q)}&limit=${lim}&cursor=${encodeURIComponent(cursor)}`
                : `/api/v1/search/posts?q=${encodeURIComponent(q)}&limit=${lim}`;
            let out = null;
            if (fetchKind === 'more') {
                out = await this.searchFetchLoadMoreCached(url, cfg, `search:more:posts:auto:${rounds}`);
            } else {
                out = await this.searchFetchFirstPageCached(url, cfg);
            }
            const raw = Array.isArray(out && out.data) ? out.data : [];
            scannedPosts += raw.length;
            const picked = this.searchFilterPostsByQuality(raw);
            matchedPosts += picked.length;
            if (picked.length > 0) merged = merged.concat(picked);
            nextCursor = this.searchCursorNormalize(out && out.next);
            if (!filterOn) break;
            if (merged.length >= lim) break;
            if (!nextCursor) break;
            cursor = nextCursor;
        }
        const sorted = this.searchSortPostsByQuality(merged);
        return { posts: sorted.slice(0, lim), nextCursor: nextCursor || '', scanned_posts: scannedPosts, matched_posts: matchedPosts, rounds };
    },

    searchUpdateResultsSummary: function(stats) {
        try {
            const mainEl = document.getElementById('search_results_summary_main');
            const subEl = document.getElementById('search_results_summary_sub');
            if (!mainEl || !subEl) return;
            const grid = document.getElementById('search_results_grid');
            const mode = String(this.state.searchMode || 'all');
            const users = grid ? grid.querySelectorAll('.s-user').length : 0;
            const posts = grid ? grid.querySelectorAll('.s-card').length : 0;
            if (mode === 'video') {
                mainEl.textContent = `为你找到视频 ${posts} 条`;
            } else if (mode === 'user') {
                mainEl.textContent = `为你找到用户 ${users} 个`;
            } else {
                mainEl.textContent = `为你找到用户 ${users} 个 · 视频 ${posts} 条`;
            }
            const qMode = this.searchQualityFilterMode();
            const qSort = this.searchQualitySortMode();
            const scanned = Math.max(0, Number((stats && stats.scanned_posts) || 0) || 0);
            const matched = Math.max(0, Number((stats && stats.matched_posts) || 0) || 0);
            if (qMode === 'all') {
                if (scanned > 0 && mode !== 'user') {
                    const sortTxt = qSort === 'default' ? '' : (qSort === 'quality' ? ' · 质量巡检排序' : ' · 无评分优先排序');
                    subEl.textContent = `视频扫描 ${scanned} 条${sortTxt}`;
                }
                else subEl.textContent = '';
                return;
            }
            const label = qMode === 'cd' ? 'C+D' : (qMode === 'd' ? '仅D' : (qMode === 'unrated' ? '仅无评分' : `分数<${this.searchQualityThreshold()}`));
            const sortTxt = qSort === 'default' ? '' : (qSort === 'quality' ? ' · 质量巡检排序' : ' · 无评分优先排序');
            const base = scanned > 0 ? scanned : Math.max(posts, matched);
            const hit = Math.max(0, Math.min(base, matched || posts));
            const rate = base > 0 ? Math.round((hit / base) * 100) : 0;
            subEl.textContent = `质量筛选 ${label} · 命中 ${hit}/${base}（${rate}%）${sortTxt}`;
        } catch (_) {
        }
    },

    searchGetActiveKeyNorm: function() {
        const cached = this.__searchActiveKeyNorm;
        if (typeof cached === 'string') return cached;
        const v = String(this.__searchActiveKey || '').trim();
        this.__searchActiveKeyNorm = v;
        return v;
    },

    searchReqOpts: function(dedupeKey, channelKey, retries, timeoutMs) {
        const dk = String(dedupeKey || '');
        const ch = channelKey ? String(channelKey) : this.searchCancelChannelFromKey(dk);
        return {
            cancel_key: `search:req:${ch}`,
            dedupe_key: dk,
            retries: retries,
            timeout_ms: timeoutMs,
        };
    },

    searchFetchFirstPageCached: async function(url, cfg) {
        const scoped = this.searchScopedRequestKey(url);
        const hit = this.searchCacheGet(scoped);
        if (hit) return hit;
        const breakerKey = this.searchCancelChannelFromKey(scoped, cfg.policy, cfg.cancelCfg);
        if (!this.searchBreakerAllow(`fp:${breakerKey}`)) {
            const staleFast = this.searchCacheGetStale(scoped, cfg.staleIfErrorMs);
            if (staleFast) return staleFast;
            throw new Error(`breaker_open:${breakerKey}`);
        }
        try {
            return await this.searchInflightGetOrRun(`rq:${scoped}`, async () => {
                const res = await this.apiRequest('GET', url, undefined, this.searchReqOpts(scoped, breakerKey, cfg.firstPageRetries, cfg.firstPageTimeoutMs));
                if (!res.ok) {
                    const err = new Error(`GET ${url} ${res.status}`);
                    err.status = Number(res.status || 0);
                    throw err;
                }
                const data = await res.json();
                const next = res.headers ? (res.headers.get('x-next-cursor') || '') : '';
                const out = this.searchCacheSet(scoped, { data, next: next || '' }, cfg.ttl, cfg.cacheCap);
                this.searchBreakerOnSuccess(`fp:${breakerKey}`);
                return out;
            });
        } catch (e) {
            if (this.searchShouldTripBreaker(e)) this.searchBreakerOnFailure(`fp:${breakerKey}`);
            const stale = this.searchCacheGetStale(scoped, cfg.staleIfErrorMs);
            if (stale) return stale;
            throw e;
        }
    },

    searchFetchLoadMoreCached: async function(url, cfg, cancelKey) {
        if (!this.__searchPageCache) this.__searchPageCache = new Map();
        const scoped = this.searchScopedRequestKey(url);
        const hit = this.searchCacheGet(scoped);
        if (hit) return hit;
        const ch = this.searchCancelChannelFromKey(cancelKey || scoped, cfg.policy, cfg.cancelCfg);
        const breakerKey = ch;
        if (!this.searchBreakerAllow(`lm:${breakerKey}`)) {
            const staleFast = this.searchCacheGetStale(scoped, cfg.loadMoreStaleIfErrorMs);
            if (staleFast) return staleFast;
            throw new Error(`breaker_open:${breakerKey}`);
        }
        const inflightKey = `rq:${scoped}`;
        try {
            return await this.searchInflightGetOrRun(inflightKey, async () => {
                const res = await this.apiRequest('GET', url, undefined, this.searchReqOpts(scoped, `more:${ch}`, cfg.loadMoreRetries, cfg.loadMoreTimeoutMs));
                if (!res.ok) {
                    const err = new Error(`GET ${url} ${res.status}`);
                    err.status = Number(res.status || 0);
                    throw err;
                }
                const data = await res.json();
                const next = res.headers ? (res.headers.get('x-next-cursor') || '') : '';
                const out = { data, next: next || '' };
                this.searchCacheSet(scoped, out, cfg.ttl, cfg.cacheCap);
                this.searchBreakerOnSuccess(`lm:${breakerKey}`);
                return out;
            });
        } catch (e) {
            if (this.searchShouldTripBreaker(e)) this.searchBreakerOnFailure(`lm:${breakerKey}`);
            const stale = this.searchCacheGetStale(scoped, cfg.loadMoreStaleIfErrorMs);
            if (stale) return stale;
            throw e;
        }
    },

    searchIsActiveRender: function(activeKey, seq) {
        return this.__searchActiveKey === activeKey && this.__searchSeq === seq;
    },

    searchFmtCardObservability: function(p) {
        try {
            const cm = p && typeof p.cover_metrics === 'object' && p.cover_metrics ? p.cover_metrics : null;
            const gq = p && typeof p.generation_quality === 'object' && p.generation_quality ? p.generation_quality : null;
            const sa = p && typeof p.subtitle_audit === 'object' && p.subtitle_audit ? p.subtitle_audit : null;
            let coverLine = null;
            if (cm) {
                const provider = String(cm.provider || '').trim() || 'unknown';
                const ms = Math.max(0, Number(cm.total_provider_ms || 0) || 0);
                const degrade = Math.max(0, Number(cm.degrade_count || 0) || 0);
                const noKey = Math.max(0, Number(cm.skip_no_key_count || 0) || 0);
                let level = 'ok';
                if (degrade > 0 || noKey > 0) level = 'degrade';
                if (ms >= 5000) level = 'slow';
                let tag = '正常';
                if (level === 'degrade') tag = '降级';
                if (level === 'slow') tag = '偏慢';
                let detail = `封面 ${provider} · ${ms}ms`;
                if (degrade > 0) detail += ` · 降级${degrade}`;
                if (noKey > 0) detail += ` · 无Key${noKey}`;
                coverLine = { tag, detail, level };
            }
            let qualityLine = null;
            if (gq) {
                const score = Math.max(0, Math.min(100, Number(gq.subtitle_quality_score || 0) || 0));
                const grade = String(gq.subtitle_quality_grade || '').trim().toUpperCase();
                let level = 'ok';
                if (grade === 'C') level = 'degrade';
                if (grade === 'D') level = 'slow';
                let tag = `字幕 ${grade || 'N/A'}`;
                if (!grade) tag = '字幕 待评估';
                if (grade === 'A') tag = '字幕 A 优秀';
                if (grade === 'B') tag = '字幕 B 可发布';
                if (grade === 'C') tag = '字幕 C 待优化';
                if (grade === 'D') tag = '字幕 D 建议重生成';
                let detail = `质量 ${score}`;
                const best = sa && typeof sa.best === 'object' && sa.best ? sa.best : null;
                let gradeClass = 'q-na';
                if (grade === 'A') gradeClass = 'q-a';
                if (grade === 'B') gradeClass = 'q-b';
                if (grade === 'C') gradeClass = 'q-c';
                if (grade === 'D') gradeClass = 'q-d';
                if (best) {
                    const cps = Number(best.avg_cps || 0) || 0;
                    const maxLine = Math.max(0, Number(best.max_line_len || 0) || 0);
                    detail += ` · ${cps.toFixed(1)}字/秒 · 最大${maxLine}字`;
                    qualityLine = { tag, detail, level, gradeClass, metrics: { score, grade, cps, maxLine, denseRatio: Number(best.dense_ratio || 0) || 0, cueCount: Math.max(0, Number(best.cue_count || 0) || 0) } };
                } else {
                    qualityLine = { tag, detail, level, gradeClass, metrics: { score, grade, cps: 0, maxLine: 0, denseRatio: 0, cueCount: 0 } };
                }
            }
            if (!coverLine && !qualityLine) return null;
            return { cover: coverLine, quality: qualityLine };
        } catch (_) {
            return null;
        }
    },

    searchRenderVideoCard: function(p, dateCtx) {
        const likes = Number((p && p.likes_count) || 0);
        const likeStr = likes >= 10000 ? (likes / 10000).toFixed(1).replace(/\.0$/, '') + '万' : likes;
        const cover = (p && p.cover_url) || ((p && p.images && p.images.length > 0) ? p.images[0] : `/api/v1/media/post-thumb/${p.id}?v=2`);
        const hls = (typeof (p && p.hls_url) === 'string' && p.hls_url) ? p.hls_url : ((typeof (p && p.video_url) === 'string' && /\.m3u8(\?|#|$)/i.test(p.video_url)) ? p.video_url : '');
        const mp4 = (typeof (p && p.mp4_url) === 'string' && p.mp4_url) ? p.mp4_url : ((typeof (p && p.video_url) === 'string' && !hls) ? p.video_url : '');
        const videoUrl = String((p && p.video_url) || '');
        const dateTxt = this.searchDateFmtWithContext(p && p.created_at, dateCtx);
        const author = this.escapeHtml((p && p.user_nickname) || ('用户' + (p && p.user_id)));
        const cover2 = this.escapeHtml(cover);
        const safeHls = this.escapeHtml(hls);
        const safeMp4 = this.escapeHtml(mp4);
        const safeVideo = this.escapeHtml(videoUrl);
        const srvDur = Math.max(0, Number((p && p.duration) || 0) || 0);
        const durText = srvDur > 0 ? this.fmtTime(srvDur) : '00:00';
        const obsObj = this.searchFmtCardObservability(p);
        const obsCover = obsObj && obsObj.cover ? obsObj.cover : null;
        const obsQuality = obsObj && obsObj.quality ? obsObj.quality : null;
        const obsTag = this.escapeHtml(obsCover && obsCover.tag ? obsCover.tag : '');
        const obsDetail = this.escapeHtml(obsCover && obsCover.detail ? obsCover.detail : '');
        const obsLevel = this.escapeHtml(obsCover && obsCover.level ? obsCover.level : '');
        const obsQTag = this.escapeHtml(obsQuality && obsQuality.tag ? obsQuality.tag : '');
        const obsQDetail = this.escapeHtml(obsQuality && obsQuality.detail ? obsQuality.detail : '');
        const obsQLevel = this.escapeHtml(obsQuality && obsQuality.level ? obsQuality.level : '');
        const obsQGradeClass = this.escapeHtml(obsQuality && obsQuality.gradeClass ? obsQuality.gradeClass : 'q-na');
        const obsQMetrics = obsQuality && typeof obsQuality.metrics === 'object' && obsQuality.metrics ? obsQuality.metrics : null;
        const obsQScore = Math.max(0, Math.min(100, Number(obsQMetrics && obsQMetrics.score || 0) || 0));
        const obsQGrade = this.escapeHtml(String(obsQMetrics && obsQMetrics.grade || 'N/A').toUpperCase());
        const obsQCps = Number(obsQMetrics && obsQMetrics.cps || 0) || 0;
        const obsQLine = Math.max(0, Number(obsQMetrics && obsQMetrics.maxLine || 0) || 0);
        const obsQDense = Math.max(0, Number(obsQMetrics && obsQMetrics.denseRatio || 0) || 0);
        const obsQCue = Math.max(0, Number(obsQMetrics && obsQMetrics.cueCount || 0) || 0);
        const obsQHint = this.escapeHtml((obsQLine > 22 || obsQCps > 8 || obsQDense > 0.2) ? '建议优化：控制行长≤22、语速≤8字/秒、高密度比例≤20%' : '质量阈值：行长≤22、语速≤8字/秒、高密度比例≤20%');
        return `
                <div class="s-card" data-post-id="${p.id}" data-action="call" data-fn="openPost" data-args="[${p.id}]" data-action-mouseover="call" data-fn-mouseover="showJxPopupById" data-args-mouseover="[${p.id}]" data-pass-el-mouseover="1" data-action-mouseout="call" data-fn-mouseout="hideJxPopup" data-args-mouseout="[]" data-pass-el-mouseout="1">
                    <div class="s-media">
                        <video class="s-media-video" muted playsinline preload="metadata" poster="${cover2}" data-hls="${safeHls}" data-mp4="${safeMp4}" data-video="${safeVideo}" data-duration="${srvDur}"></video>
                        <div class="s-media-controls" data-action="stop" data-stop="1">
                            <div class="s-media-progress" data-action-pointerdown="call" data-fn-pointerdown="searchCardSeek" data-pass-el-pointerdown="1" data-pass-event-pointerdown="1" data-stop="1"><div class="s-media-progress-fill"></div></div>
                            <div class="s-ctrl-row">
                                <div class="s-ctrl-left">
                                    <div class="s-ctrl-btn s-ctrl-play" data-action="call" data-fn="searchCardTogglePlay" data-pass-el="1" data-stop="1"><i class="fas fa-play"></i></div>
                                    <div class="s-ctrl-time"><span class="s-ctrl-time-cur">00:00</span><span class="s-ctrl-time-split">/</span><span class="s-ctrl-time-dur">${durText}</span></div>
                                </div>
                                <div class="s-ctrl-right">
                                    <div class="s-ctrl-btn s-ctrl-mute" data-action="call" data-fn="searchCardToggleMute" data-pass-el="1" data-stop="1"><i class="fas fa-volume-up"></i></div>
                                    <input class="s-ctrl-vol" type="range" min="0" max="1" step="0.05" value="1" data-action="stop" data-stop="1" data-action-input="call" data-fn-input="searchCardSetVolume" data-pass-el-input="1" data-pass-value-input="1">
                                    <div class="s-ctrl-btn s-ctrl-fs" data-action="call" data-fn="searchCardFullscreen" data-pass-el="1" data-stop="1"><i class="fas fa-expand"></i></div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="s-info" style="padding:10px;">
                        <div class="s-title">${this.formatPostDesc((p && p.title) || (p && p.content_text) || '无标题')}</div>
                        <div class="s-meta">
                            <div class="s-author">
                                <img src="${(p && p.user_avatar) || '/static/img/default_avatar.svg'}">
                                <span>${author}</span>
                            </div>
                            <div style="display:flex; align-items:center; gap:4px;">
                                <i class="far fa-heart"></i> ${likeStr}
                            </div>
                        </div>
                        <div class="s-date" style="margin-top:4px; color:#666;">${dateTxt}</div>
                        ${obsCover ? `<div class="s-obs-line"><span class="s-obs-badge ${obsLevel}">${obsTag}</span><span class="s-obs-text">${obsDetail}</span></div>` : ''}
                        ${obsQuality ? `<div class="s-obs-line s-obs-quality-line"><span class="s-obs-badge ${obsQLevel} ${obsQGradeClass}">${obsQTag}</span><span class="s-obs-text">${obsQDetail}</span></div>` : ''}
                        ${obsQuality ? `<div class="s-obs-hover"><div class="s-obs-kv">评分 ${obsQScore} · 等级 ${obsQGrade}</div><div class="s-obs-kv">速度 ${obsQCps.toFixed(2)}字/秒 · 行长 ${obsQLine}</div><div class="s-obs-kv">高密度 ${Math.round(obsQDense * 100)}% · 字幕条数 ${obsQCue}</div><div class="s-obs-hint">映射：A优秀 B可发布 C待优化 D建议重生成</div></div>` : ''}
                        ${obsQuality ? `<div class="s-obs-actions"><button class="s-obs-toggle" data-action="call" data-fn="searchToggleObsDetail" data-pass-el="1" data-stop="1">质量细节</button></div>` : ''}
                        ${obsQuality ? `<div class="s-obs-detail" hidden><div class="s-obs-kv">评分 ${obsQScore} · 等级 ${obsQGrade}</div><div class="s-obs-kv">速度 ${obsQCps.toFixed(2)}字/秒 · 行长 ${obsQLine}</div><div class="s-obs-kv">高密度 ${Math.round(obsQDense * 100)}% · 字幕条数 ${obsQCue}</div><div class="s-obs-hint">${obsQHint}</div></div>` : ''}
                    </div>
                </div>`;
    },

    searchRenderVideoCards: function(posts, dateCtx) {
        if (!Array.isArray(posts) || posts.length === 0) return '';
        let html = '';
        for (let i = 0; i < posts.length; i++) {
            html += this.searchRenderVideoCard(posts[i], dateCtx);
        }
        return html;
    },

    searchToggleObsDetail: function(el) {
        try {
            const card = el && el.closest ? el.closest('.s-card') : null;
            if (!card) return;
            const panel = card.querySelector('.s-obs-detail');
            const btn = card.querySelector('.s-obs-toggle');
            if (!panel) return;
            const next = !card.classList.contains('s-obs-expanded');
            card.classList.toggle('s-obs-expanded', next);
            panel.hidden = !next;
            if (btn) btn.textContent = next ? '收起细节' : '质量细节';
        } catch (_) {
        }
    },

    searchLoadMore: async function(kind) {
        const stateView = this.searchStateKeyView();
        const query = stateView.query;
        if (!query) return;
        const mode = stateView.mode;
        const k = String(kind || '');
        let busyKey = '';

        if (k !== 'posts' && k !== 'users') return;

        try {
            const grid = document.getElementById('search_results_grid');
            if (!grid) return;

            const activeKey = stateView.key;
            const policy = this.searchCachePolicy();
            busyKey = this.searchLoadMoreBusyEnter(`${activeKey}|${k}`, policy);
            if (!busyKey) return;
            const limitPosts = 24;
            const limitUsers = 10;
            const fetchCfg = this.searchPageFetchPolicyView(policy);
            const cancelCfg = this.searchCancelPolicyView(policy);
            const reqPolicy = this.searchRequestPolicy();
            const execCfg = this.searchExecPolicyView(reqPolicy, null);
            const loadMoreTimeoutMs = execCfg.loadMoreTimeoutMs;
            const loadMoreRetries = execCfg.loadMoreRetries;
            const loadMoreStaleIfErrorMs = fetchCfg.loadMoreStaleIfErrorMs;
            const ttl = fetchCfg.loadMoreTtlMs;
            const cacheCap = fetchCfg.cap;
            const loadMoreCfg = {
                policy,
                cancelCfg,
                loadMoreTimeoutMs,
                loadMoreRetries,
                loadMoreStaleIfErrorMs,
                ttl,
                cacheCap,
            };
            const morePostsHtml = `<div style="grid-column:1/-1; text-align:center; padding:20px;"><button id="search_load_more_posts" class="btn btn-outline" data-action="call" data-fn="searchLoadMore" data-args='[\"posts\"]'>加载更多</button></div>`;
            const moreUsersHtml = `<div style="grid-column:1/-1; text-align:center; padding:20px;"><button id="search_load_more_users" class="btn btn-outline" data-action="call" data-fn="searchLoadMore" data-args='[\"users\"]'>加载更多</button></div>`;

            if (k === 'posts') {
                const cursor = String(this.state.searchCursorPosts || '').trim();
                if (!cursor) return;
                const cur = this.searchStateKeyView();
                if (cur.mode !== mode || cur.query !== query) return;
                if (cur.key !== activeKey) return;
                const out = await this.searchCollectPostsForView(query, limitPosts, cursor, loadMoreCfg, 'more');
                const cur2 = this.searchStateKeyView();
                if (cur2.mode !== mode || cur2.query !== query) return;
                if (cur2.key !== activeKey) return;
                const posts = Array.isArray(out.posts) ? out.posts : [];
                this.searchRememberPosts(posts, false);
                try { this.state.searchPosts = (Array.isArray(this.state.searchPosts) ? this.state.searchPosts : []).concat(posts); } catch (_) {}
                this.state.searchCursorPosts = this.searchCursorNormalize(out.nextCursor);
                if (!this.__searchSummaryAgg) this.__searchSummaryAgg = { scanned_posts: 0, matched_posts: 0 };
                this.__searchSummaryAgg.scanned_posts += Math.max(0, Number(out.scanned_posts || 0) || 0);
                this.__searchSummaryAgg.matched_posts += Math.max(0, Number(out.matched_posts || 0) || 0);
                if (!posts.length) {
                    this.searchUpdateResultsSummary(this.__searchSummaryAgg);
                    return;
                }
                const btn = document.getElementById('search_load_more_posts');
                if (btn && btn.parentElement) btn.parentElement.remove();
                const dateCtx = this.searchDateFmtContext(policy);

                if (mode === 'all') {
                    const wf = document.getElementById('search_posts_waterfall');
                    if (wf && posts.length > 0) wf.insertAdjacentHTML('beforeend', this.searchRenderVideoCards(posts, dateCtx));
                    const nextCursor = this.searchCursorNormalize(out.nextCursor);
                    if (nextCursor) {
                        if (wf) wf.insertAdjacentHTML('afterend', morePostsHtml);
                    }
                } else {
                    if (posts.length > 0) grid.insertAdjacentHTML('beforeend', this.searchRenderVideoCards(posts, dateCtx));
                    const nextCursor = this.searchCursorNormalize(out.nextCursor);
                    if (nextCursor) {
                        grid.insertAdjacentHTML('beforeend', morePostsHtml);
                    }
                }
                try { this.searchBindEngagement(grid); } catch (_) {}
                this.searchUpdateResultsSummary(this.__searchSummaryAgg);
            } else {
                const cursor = String(this.state.searchCursorUsers || '').trim();
                if (!cursor) return;
                const url = `/api/v1/users/search-user?query=${encodeURIComponent(query)}&limit=${limitUsers}&cursor=${encodeURIComponent(cursor)}`;
                const out = await this.searchFetchLoadMoreCached(url, loadMoreCfg, `search:more:users`);
                const cur = this.searchStateKeyView();
                if (cur.mode !== mode || cur.query !== query) return;
                if (cur.key !== activeKey) return;
                const users = Array.isArray(out.data) ? out.data : [];
                if (!users.length) {
                    this.state.searchCursorUsers = '';
                    return;
                }
                const btn = document.getElementById('search_load_more_users');
                if (btn && btn.parentElement) btn.parentElement.remove();
                grid.insertAdjacentHTML('beforeend', this.searchRenderUserList(users));
                try { this.searchBindEngagement(grid); } catch (_) {}
                const nextCursor = this.searchCursorNormalize(out.next);
                this.state.searchCursorUsers = nextCursor;
                if (nextCursor) {
                    grid.insertAdjacentHTML('beforeend', moreUsersHtml);
                }
                this.searchUpdateResultsSummary(this.__searchSummaryAgg || null);
            }
        } catch (e) {
            console.error(e);
        } finally {
            this.searchLoadMoreBusyLeave(busyKey);
        }
    },

    renderSearchResults: async function() {
        const stateView = this.searchStateKeyView();
        const query = stateView.query;
        const mode = stateView.mode;
        const grid = document.getElementById('search_results_grid');
        if (!grid) return;

        const activeKey = stateView.key;
        this.__searchSeq = (this.__searchSeq || 0) + 1;
        const seq = this.__searchSeq;
        this.__searchActiveKey = activeKey;
        this.__searchActiveKeyNorm = String(activeKey).trim();
        try { grid.dataset.searchKey = String(activeKey); } catch (_) {}
        this.searchSyncQualityFilterUi();
        const reqPolicy = this.searchRequestPolicy();
        const queryPolicy = this.searchQueryPolicy();
        const execCfg = this.searchExecPolicyView(reqPolicy, queryPolicy);
        const firstPageRetries = execCfg.firstPageRetries;
        const firstPageTimeoutMs = execCfg.firstPageTimeoutMs;
        const allowUserLookup = String(query || '').length >= execCfg.minUserQueryLen;

        const gridClass = mode === 'user' ? 'mode-user' : (mode === 'all' ? 'mode-all' : 'mode-video');
        grid.className = `search-grid ${gridClass}`;
        
        grid.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--text-secondary);">搜索中...</div>';

        try {
            this.state.searchCursorPosts = '';
            this.state.searchCursorUsers = '';
            this.searchRememberPosts([], true);
            this.__searchSummaryAgg = { scanned_posts: 0, matched_posts: 0 };
            if (!this.__searchPageCache) this.__searchPageCache = new Map();
            const policy = this.searchCachePolicy();
            const dateCtx = this.searchDateFmtContext(policy);
            const fetchCfg = this.searchPageFetchPolicyView(policy);
            const cancelCfg = this.searchCancelPolicyView(policy);
            const firstPageTtlMs = fetchCfg.firstPageTtlMs;
            const staleIfErrorMs = fetchCfg.staleIfErrorMs;
            const cacheCap = fetchCfg.cap;
            const firstPageCfg = {
                policy,
                cancelCfg,
                staleIfErrorMs,
                cacheCap,
                firstPageRetries,
                firstPageTimeoutMs,
                ttl: firstPageTtlMs,
            };
            let html = '';
            let summaryStats = null;
            if (mode === 'video') {
                const limit = 24;
                let posts = [];
                let next = '';
                const out = await this.searchCollectPostsForView(query, limit, '', firstPageCfg, 'first');
                posts = Array.isArray(out.posts) ? out.posts : [];
                this.searchRememberPosts(posts, true);
                next = String(out.nextCursor || '');
                summaryStats = { scanned_posts: Number(out.scanned_posts || 0) || 0, matched_posts: Number(out.matched_posts || 0) || 0 };
                if (!this.searchIsActiveRender(activeKey, seq)) return;
                try { this.state.searchPosts = Array.isArray(posts) ? posts : []; } catch (_) {}
                this.state.searchCursorPosts = this.searchCursorNormalize(next);
                const modeLabel = this.searchQualityFilterMode() === 'all' ? '未找到相关视频' : (this.searchQualityFilterMode() === 'cd' ? '未找到C/D等级视频' : (this.searchQualityFilterMode() === 'd' ? '未找到D等级视频' : (this.searchQualityFilterMode() === 'unrated' ? '未找到无评分视频' : `未找到分数低于${this.searchQualityThreshold()}的视频`)));
                html = (posts.length === 0) ? `<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--text-secondary);">${modeLabel}</div>` : this.searchRenderVideoCards(posts, dateCtx);
                if (this.state.searchCursorPosts) {
                    html += `<div style="grid-column:1/-1; text-align:center; padding:20px;"><button id="search_load_more_posts" class="btn btn-outline" data-action="call" data-fn="searchLoadMore" data-args='[\"posts\"]'>加载更多</button></div>`;
                }
            }
            else if (mode === 'user') {
                const limit = 10;
                let users = [];
                let next = '';
                if (allowUserLookup) {
                    const url = `/api/v1/users/search-user?query=${encodeURIComponent(query)}&limit=${limit}`;
                    const out = await this.searchFetchFirstPageCached(url, firstPageCfg);
                    users = Array.isArray(out.data) ? out.data : [];
                    next = String(out.next || '');
                }
                if (!this.searchIsActiveRender(activeKey, seq)) return;
                this.state.searchCursorUsers = this.searchCursorNormalize(next);
                html = (users.length === 0) ? '<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--text-secondary);">未找到相关用户</div>' : this.searchRenderUserList(users);
                if (this.state.searchCursorUsers) {
                    html += `<div style="grid-column:1/-1; text-align:center; padding:20px;"><button id="search_load_more_users" class="btn btn-outline" data-action="call" data-fn="searchLoadMore" data-args='[\"users\"]'>加载更多</button></div>`;
                }
            }
            else { // All
                const limitUsers = 5;
                const limitPosts = 24;
                const pair = allowUserLookup
                    ? await Promise.all([
                        this.searchCollectPostsForView(query, limitPosts, '', firstPageCfg, 'first'),
                        this.searchFetchFirstPageCached(`/api/v1/users/search-user?query=${encodeURIComponent(query)}&limit=${limitUsers}`, firstPageCfg),
                    ])
                    : [await this.searchCollectPostsForView(query, limitPosts, '', firstPageCfg, 'first'), { data: [], next: '' }];
                if (!this.searchIsActiveRender(activeKey, seq)) return;
                const pOut = pair[0];
                const uOut = pair[1];

                const users = Array.isArray(uOut.data) ? uOut.data : [];
                const posts = Array.isArray(pOut.posts) ? pOut.posts : [];
                this.searchRememberPosts(posts, true);
                summaryStats = { scanned_posts: Number(pOut.scanned_posts || 0) || 0, matched_posts: Number(pOut.matched_posts || 0) || 0 };
                this.state.searchCursorUsers = this.searchCursorNormalize(uOut.next);
                this.state.searchCursorPosts = this.searchCursorNormalize(pOut.nextCursor);
                try { this.state.searchPosts = Array.isArray(posts) ? posts : []; } catch (_) {}
                
                if (users.length === 0 && posts.length === 0) {
                    const emptyText = this.searchQualityFilterMode() === 'all' ? '未找到相关内容' : '未找到相关用户或符合质量筛选的视频';
                    html = `<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--text-secondary);">${emptyText}</div>`;
                } else {
                    const topUser = Array.isArray(users) && users.length > 0 ? users[0] : null;
                    if (topUser) {
                        html += `<div class="search-section-title">最相关用户</div>`;
                        html += this.searchRenderTopUser(topUser);
                    }
                    if (Array.isArray(posts) && posts.length > 0) {
                        html += `<div class="search-section-title">相关视频</div>`;
                        html += `<div class="search-waterfall" id="search_posts_waterfall">${this.searchRenderVideoCards(posts, dateCtx)}</div>`;
                        if (this.state.searchCursorPosts) {
                            html += `<div style="grid-column:1/-1; text-align:center; padding:20px;"><button id="search_load_more_posts" class="btn btn-outline" data-action="call" data-fn="searchLoadMore" data-args='[\"posts\"]'>加载更多</button></div>`;
                        }
                    }
                }
            }
            if (!this.searchIsActiveRender(activeKey, seq)) return;
            grid.innerHTML = html;
            try { this.searchBindEngagement(grid); } catch (_) {}
            this.__searchSummaryAgg = summaryStats || { scanned_posts: 0, matched_posts: 0 };
            this.searchUpdateResultsSummary(this.__searchSummaryAgg);
        } catch(e) {
            console.error(e);
            if (!this.searchIsActiveRender(activeKey, seq)) return;
            grid.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--text-secondary);">搜索失败，请重试</div>';
            this.searchUpdateResultsSummary(null);
        }
    },
    
    closeSearchPage: function() {
        this.switchPage('recommend');
    },

    searchBindEngagement: function(rootEl) {
        const root = rootEl || document.getElementById('search_results_grid');
        if (!root) return;
        const q = String(this.state.searchKeyword || '').trim();
        if (!q) return;
        const cards = root.querySelectorAll('.s-card');
        if (!this.__searchEngBound) {
            this.__searchEngBound = true;
            try {
                root.addEventListener('click', (e) => {
                    try {
                        const t = e && e.target;
                        if (!t || !t.closest) return;
                        const controls = t.closest('.s-media-controls');
                        if (controls) return;
                        if (t.closest('.s-obs-toggle') || t.closest('.s-obs-detail')) return;
                        const card = t.closest('.s-card');
                        if (!card) return;
                        const emit = window.appEmit;
                        if (!emit) return;
                        let ds = null;
                        let rootDs = null;
                        const rootCtx = root.__searchCtx || null;
                        const ctx = card._searchCtx || rootCtx;
                        let rootKey = root._searchKey || '';
                        if (!rootKey) {
                            rootDs = root.dataset || {};
                            rootKey = rootDs.searchKey || '';
                            if (rootKey && root._searchKey !== rootKey) root._searchKey = rootKey;
                        }
                        const ak = rootKey || (ctx ? (ctx.activeKey || '') : '') || ((typeof this.__searchActiveKeyNorm === 'string') ? this.__searchActiveKeyNorm : this.searchGetActiveKeyNorm());
                        if (ak) {
                            let searchKey = card._searchKey || '';
                            if (!searchKey) {
                                ds = card.dataset || {};
                                searchKey = ds.searchKey || '';
                                if (searchKey && card._searchKey !== searchKey) card._searchKey = searchKey;
                            }
                            if (searchKey !== ak) return;
                        }
                        let pid = (typeof card._searchPid === 'number') ? card._searchPid : 0;
                        if (!pid) {
                            if (!ds) ds = card.dataset || {};
                            pid = Number(ds.postId || 0);
                            if (pid && card._searchPid !== pid) card._searchPid = pid;
                        }
                        if (!pid) return;
                        let pos = ((typeof card._searchPosInt === 'number') ? card._searchPosInt : 0) || null;
                        if (!pos) {
                            if (!ds) ds = card.dataset || {};
                            pos = Number(ds.pos || 0) || null;
                            if (pos && card._searchPosInt !== pos) card._searchPosInt = pos;
                        }
                        let rootQ = root._searchQ || '';
                        if (!rootQ) {
                            if (!rootDs) rootDs = root.dataset || {};
                            rootQ = rootDs.q || '';
                            if (rootQ && root._searchQ !== rootQ) root._searchQ = rootQ;
                        }
                        let query = card._searchQ || '';
                        if (!query) {
                            if (!ds) ds = card.dataset || {};
                            query = ds.q || rootQ || (ctx ? (ctx.q || '') : '') || String(this.state.searchKeyword || '').trim();
                            if (query && card._searchQ !== query) card._searchQ = query;
                        }
                        const uid = ((typeof card._searchUid === 'number') ? card._searchUid : 0) || (ctx ? Number(ctx.uid || 0) : this.searchCurrentUid());
                        emit('search:click', { q: query, user_id: uid || null, post_id: pid, pos });
                    } catch (_) {}
                }, true);
            } catch (_) {
            }
        }
        try {
            const activeKey = this.searchGetActiveKeyNorm();
            const activeKeyNorm = activeKey || '';
            const hasActiveKey = !!activeKeyNorm;
            const uid = this.searchCurrentUid();
            const prevCtx = root.__searchCtx || null;
            let ctx = { q, activeKey: activeKeyNorm, uid };
            if (prevCtx && prevCtx.q === q && prevCtx.activeKey === activeKeyNorm) {
                const prevUid = (typeof prevCtx.uid === 'number') ? prevCtx.uid : Number(prevCtx.uid || 0);
                if (prevUid === uid) ctx = prevCtx;
            }
            if (root.dataset) {
                if (root.dataset.q !== q) root.dataset.q = q;
                if (root.dataset.searchKey !== activeKeyNorm) root.dataset.searchKey = activeKeyNorm;
            }
            if (root._searchQ !== q) root._searchQ = q;
            if (root._searchKey !== activeKeyNorm) root._searchKey = activeKeyNorm;
            if (root.__searchCtx !== ctx) root.__searchCtx = ctx;
            const ctxKey = `${q}|${activeKeyNorm}|${uid}`;
            if (root.__searchCtxKey !== ctxKey) root.__searchCtxKey = ctxKey;
            const totalCards = cards.length;
            let startIdx = 0;
            const prevBindCtx = root.__searchBindCtx || null;
            if (prevBindCtx && prevBindCtx.q === q && prevBindCtx.activeKey === activeKeyNorm) {
                const prevBindUid = (typeof prevBindCtx.uid === 'number') ? prevBindCtx.uid : Number(prevBindCtx.uid || 0);
                if (prevBindUid === uid) {
                    const processed = (typeof prevBindCtx.processed === 'number') ? prevBindCtx.processed : Number(prevBindCtx.processed || 0);
                    if (processed > 0 && totalCards >= processed) startIdx = processed;
                }
            }
            const qImprPrefix = `${q}|`;
            for (let i = startIdx; i < totalCards; i++) {
                const el = cards[i];
                if (!el) continue;
                const posInt = i + 1;
                if (el._searchCtx !== ctx) el._searchCtx = ctx;
                if (el._searchCtxKey !== ctxKey) el._searchCtxKey = ctxKey;
                if (el._searchUid !== uid) el._searchUid = uid;
                if (el._searchPosInt !== posInt) el._searchPosInt = posInt;
                if (el._searchQ !== q) el._searchQ = q;
                if (el._searchKey !== activeKeyNorm) el._searchKey = activeKeyNorm;
                const pidCached = (typeof el._searchPid === 'number') ? el._searchPid : 0;
                const imprKeyCached = el._searchImprKey || '';
                const cacheReady = !!pidCached && imprKeyCached === (qImprPrefix + pidCached);
                if (cacheReady) continue;
                const ds = el.dataset;
                if (!ds) continue;
                const pos = String(posInt);
                const dsPostId = ds.postId || '';
                const dsMatchMeta = ds.pos === pos && ds.q === q && (!hasActiveKey || ds.searchKey === activeKeyNorm);
                const hasDsPostId = !!dsPostId;
                let dsPidFast = 0;
                let expectedFastImprKey = '';
                if (dsMatchMeta && hasDsPostId) {
                    dsPidFast = Number(dsPostId);
                    if (dsPidFast) {
                        const dsImprKey = imprKeyCached || ds.imprKey || '';
                        if (dsImprKey) {
                            expectedFastImprKey = qImprPrefix + dsPidFast;
                            if (dsImprKey === expectedFastImprKey) continue;
                        }
                    }
                }
                if (hasDsPostId && !dsMatchMeta) dsPidFast = Number(dsPostId);
                let pid = dsPidFast || pidCached;
                if (!pid) {
                    const rawArgs = String(el.getAttribute('data-args') || '');
                    if (el._searchRawArgsCache !== rawArgs) {
                        let parsedPid = 0;
                        if (rawArgs) {
                            try { parsedPid = Number((JSON.parse(rawArgs)[0] || 0)); } catch (_) {}
                        }
                        el._searchRawArgsCache = rawArgs;
                        el._searchRawArgsPid = parsedPid;
                    }
                    pid = (typeof el._searchRawArgsPid === 'number') ? el._searchRawArgsPid : Number(el._searchRawArgsPid || 0);
                }
                if (pid) {
                    if (!dsPostId) ds.postId = String(pid);
                    if (el._searchPid !== pid) el._searchPid = pid;
                }
                if (ds.pos !== pos) ds.pos = pos;
                if (ds.q !== q) ds.q = q;
                if (ds.searchKey !== activeKeyNorm) ds.searchKey = activeKeyNorm;
                if (pid) {
                    const imprKey = (pid === dsPidFast && expectedFastImprKey) ? expectedFastImprKey : (qImprPrefix + pid);
                    if (el._searchImprKey !== imprKey) el._searchImprKey = imprKey;
                    if (ds.imprKey !== imprKey) ds.imprKey = imprKey;
                }
            }
            root.__searchBindScanStart = startIdx;
            if (prevBindCtx) {
                if (prevBindCtx.q !== q) prevBindCtx.q = q;
                if (prevBindCtx.activeKey !== activeKeyNorm) prevBindCtx.activeKey = activeKeyNorm;
                if (prevBindCtx.uid !== uid) prevBindCtx.uid = uid;
                if (prevBindCtx.processed !== totalCards) prevBindCtx.processed = totalCards;
            } else {
                root.__searchBindCtx = { q, activeKey: activeKeyNorm, uid, processed: totalCards };
            }
        } catch (_) {
        }
        try {
            if (!this.__searchImprObserved) this.__searchImprObserved = new Set();
            if (!this.__searchImprObs) {
                this.__searchImprObs = new IntersectionObserver((entries) => {
                    try {
                        for (let i = 0; i < entries.length; i++) this.searchHandleImpressionEntry(entries[i]);
                    } catch (_) {}
                }, { threshold: 0.6 });
            }
            const imprObs = this.__searchImprObs;
            const imprObserved = this.__searchImprObserved;
            try {
                if (imprObserved.size > 0) {
                    const p = this.searchCachePolicy();
                    const imprCfg = this.searchImprPolicyView(p);
                    const obsOps = this.searchCounterNext('__searchImprObsOps', 1000000000);
                    if (this.searchShouldSweep(obsOps, imprCfg.imprSweepEveryOps) && this.searchSweepAllow('improbs', imprCfg.imprSweepMinIntervalMs)) {
                        const maxScan = this.searchSweepScanLimit(imprCfg.imprSweepScan, 128, 4096);
                        let scanned = 0;
                        for (const el of imprObserved) {
                            if (scanned >= maxScan) break;
                            scanned += 1;
                            if (!el || !el.isConnected || !root.contains(el)) {
                                try { imprObs.unobserve(el); } catch (_) {}
                                try { imprObserved.delete(el); } catch (_) {}
                            }
                        }
                    }
                }
            } catch (_) {
            }
            const imprCtx = root.__searchCtx || null;
            let imprBindKey = root.__searchCtxKey || '';
            if (!imprBindKey) {
                if (!imprCtx) {
                    imprBindKey = '||0';
                } else {
                    const imprQ = imprCtx.q || '';
                    const imprActiveKey = imprCtx.activeKey || '';
                    const imprUid = (typeof imprCtx.uid === 'number') ? imprCtx.uid : Number(imprCtx.uid || 0);
                    imprBindKey = imprQ + '|' + imprActiveKey + '|' + imprUid;
                }
            }
            const totalCards = cards.length;
            const obsStartRaw = root.__searchBindScanStart;
            const obsStart = (typeof obsStartRaw === 'number' && obsStartRaw >= 0 && obsStartRaw <= totalCards) ? obsStartRaw : 0;
            for (let i = obsStart; i < totalCards; i++) {
                const el = cards[i];
                if (!el || !el.isConnected || !el.dataset) {
                    if (el) {
                        if (el._searchImprBound) el._searchImprBound = false;
                        if (el._searchImprBindKey) el._searchImprBindKey = '';
                    }
                    continue;
                }
                if (el._searchImprBound && el._searchImprBindKey === imprBindKey) continue;
                try {
                    if (!el._searchImprBound) el._searchImprBound = true;
                    if (el._searchImprBindKey !== imprBindKey) el._searchImprBindKey = imprBindKey;
                    if (!imprObserved.has(el)) {
                        imprObs.observe(el);
                        imprObserved.add(el);
                    }
                } catch (_) {}
            }
        } catch (_) {
        }
    },

    searchImprDrop: function(el) {
        if (!el) return;
        const obs = this.__searchImprObs;
        const observed = this.__searchImprObserved;
        if (!obs && !observed) return;
        let shouldUnobserve = true;
        if (observed && observed.delete) shouldUnobserve = !!observed.delete(el);
        if (!shouldUnobserve) return;
        try { if (obs) obs.unobserve(el); } catch (_) {}
    },

    searchHandleImpressionEntry: function(en) {
        if (!en || !en.isIntersecting) return;
        const el = en.target;
        if (!el) return this.searchImprDrop(el);
        const emit = window.appEmit;
        if (!emit) return this.searchImprDrop(el);
        let ds = null;
        const ctx = el._searchCtx || null;
        const ak = (ctx ? (ctx.activeKey || '') : '') || ((typeof this.__searchActiveKeyNorm === 'string') ? this.__searchActiveKeyNorm : this.searchGetActiveKeyNorm());
        if (ak) {
            let searchKey = el._searchKey || '';
            if (!searchKey) {
                ds = el.dataset || {};
                searchKey = ds.searchKey || '';
                if (searchKey && el._searchKey !== searchKey) el._searchKey = searchKey;
            }
            if (searchKey !== ak) return this.searchImprDrop(el);
        }
        let pid = (typeof el._searchPid === 'number') ? el._searchPid : 0;
        if (!pid) {
            if (!ds) ds = el.dataset || {};
            pid = Number(ds.postId || 0);
            if (pid && el._searchPid !== pid) el._searchPid = pid;
        }
        if (!pid) return this.searchImprDrop(el);
        let query = el._searchQ || '';
        if (!query) {
            if (!ds) ds = el.dataset || {};
            query = ds.q || (ctx ? (ctx.q || '') : '');
            if (query && el._searchQ !== query) el._searchQ = query;
        }
        if (!query) return this.searchImprDrop(el);
        let k = el._searchImprKey || '';
        if (!k) {
            if (!ds) ds = el.dataset || {};
            k = ds.imprKey || '';
        }
        if (!k) {
            k = `${query}|${pid}`;
            el._searchImprKey = k;
            if (ds) ds.imprKey = k;
        } else {
            if (el._searchImprKey !== k) el._searchImprKey = k;
            if (ds && ds.imprKey !== k) ds.imprKey = k;
        }
        if (!this.searchImprMarkSeen(k)) return this.searchImprDrop(el);
        let pos = ((typeof el._searchPosInt === 'number') ? el._searchPosInt : 0) || null;
        if (!pos) {
            if (!ds) ds = el.dataset || {};
            pos = Number(ds.pos || 0) || null;
            if (pos && el._searchPosInt !== pos) el._searchPosInt = pos;
        }
        const uid = ((typeof el._searchUid === 'number') ? el._searchUid : 0) || (ctx ? Number(ctx.uid || 0) : this.searchCurrentUid());
        emit('search:impression', { q: query, user_id: uid || null, post_id: pid, pos });
        this.searchImprDrop(el);
    },

    searchCardGet: function(el) {
        const card = el && el.closest ? el.closest('.s-card') : null;
        if (!card) return null;
        const refs = this.searchCardRefs(card);
        const v = refs.v;
        if (!v) return null;
        return { card, v, refs };
    },

    searchCardRefs: function(card) {
        try {
            if (!card || !card.querySelector) return {};
            const prev = card.__searchRefs || null;
            if (prev && prev.v && prev.v.isConnected) return prev;
            const refs = {
                v: card.querySelector('.s-media-video'),
                curEl: card.querySelector('.s-ctrl-time-cur'),
                durEl: card.querySelector('.s-ctrl-time-dur'),
                fillEl: card.querySelector('.s-media-progress-fill'),
                playIconEl: card.querySelector('.s-ctrl-play i'),
                muteIconEl: card.querySelector('.s-ctrl-mute i'),
                volEl: card.querySelector('.s-ctrl-vol'),
                progressEl: card.querySelector('.s-media-progress'),
                mediaEl: card.querySelector('.s-media'),
            };
            card.__searchRefs = refs;
            return refs;
        } catch (_) {
            return {};
        }
    },

    searchCardEnsureSource: function(v) {
        try {
            const ds = v && v.dataset ? v.dataset : null;
            if (!ds) return;
            const hls = ds.hls || '';
            const mp4 = ds.mp4 || '';
            const video = ds.video || '';
            const sourceKey = `${hls}|${mp4}|${video}`;
            if (v._searchSourceKey !== sourceKey) {
                v._searchSourceKey = sourceKey;
                v._searchSourcePost = { hls_url: hls, mp4_url: mp4, video_url: video };
                v._searchAssignedSrc = '';
            }
            if (window.app && typeof window.app.applyPreferredVideoSource === 'function') {
                const r = window.app.applyPreferredVideoSource(v, v._searchSourcePost, { autoPlay: false });
                if (r && typeof r.catch === 'function') r.catch(() => {});
                return;
            }
            const src = hls || mp4 || video || '';
            if (!src || v._searchAssignedSrc === src) return;
            if ((v.currentSrc || v.src || '') !== src) v.src = src;
            v._searchAssignedSrc = src;
        } catch (_) {
        }
    },

    searchCardEnsureBound: function(card, v, refsArg) {
        try {
            if (v._searchControlsBound) return;
            v._searchControlsBound = true;
            const refs = refsArg || this.searchCardRefs(card);

            const syncTime = () => {
                try {
                    const t = Number(v.currentTime || 0);
                    const dMeta = Number(v.duration || 0);
                    const dFallback = Number(v.dataset && v.dataset.duration ? v.dataset.duration : 0) || 0;
                    const d = (dMeta && Number.isFinite(dMeta)) ? dMeta : dFallback;
                    const curEl = refs.curEl;
                    const durEl = refs.durEl;
                    const curSec = Number.isFinite(t) ? Math.max(0, Math.floor(t)) : 0;
                    const durSec = (d && Number.isFinite(d)) ? Math.max(0, Math.floor(d)) : 0;
                    if (curEl && v._searchCurSec !== curSec) {
                        v._searchCurSec = curSec;
                        curEl.innerText = this.fmtTime(curSec);
                    }
                    if (durEl && v._searchDurSec !== durSec) {
                        v._searchDurSec = durSec;
                        durEl.innerText = durSec > 0 ? this.fmtTime(durSec) : '00:00';
                    }
                    const fill = refs.fillEl;
                    if (fill && d && Number.isFinite(d)) {
                        const pct = Math.max(0, Math.min(100, Math.round((t / d) * 1000) / 10));
                        if (v._searchFillPct !== pct) {
                            v._searchFillPct = pct;
                            fill.style.width = `${pct}%`;
                        }
                    } else if (fill && v._searchFillPct !== 0) {
                        v._searchFillPct = 0;
                        fill.style.width = '0%';
                    }
                } catch (_) {
                }
            };

            const syncPlayIcon = () => {
                try {
                    const btn = refs.playIconEl;
                    if (!btn) return;
                    const cls = v.paused ? 'fas fa-play' : 'fas fa-pause';
                    if (v._searchPlayCls === cls) return;
                    v._searchPlayCls = cls;
                    btn.className = cls;
                } catch (_) {
                }
            };

            const syncMuteIcon = () => {
                try {
                    const btn = refs.muteIconEl;
                    if (!btn) return;
                    const cls = (v.muted || v.volume === 0) ? 'fas fa-volume-mute' : 'fas fa-volume-up';
                    if (v._searchMuteCls === cls) return;
                    v._searchMuteCls = cls;
                    btn.className = cls;
                } catch (_) {
                }
            };

            v.addEventListener('timeupdate', syncTime);
            v.addEventListener('loadedmetadata', syncTime);
            v.addEventListener('play', syncPlayIcon);
            v.addEventListener('pause', syncPlayIcon);
            v.addEventListener('volumechange', syncMuteIcon);
            v.addEventListener('ended', () => {
                try { v.currentTime = 0; } catch (_) {}
                syncTime();
                syncPlayIcon();
            });

            syncTime();
            syncPlayIcon();
            syncMuteIcon();
        } catch (_) {
        }
    },

    searchCardTogglePlay: function(el) {
        const r = this.searchCardGet(el);
        if (!r) return;
        const card = r.card;
        const v = r.v;
        const refs = r.refs || this.searchCardRefs(card);
        this.searchCardEnsureBound(card, v, refs);
        if (v.paused) {
            this.searchCardEnsureSource(v);
            try {
                const p = v.play();
                if (p && typeof p.catch === 'function') p.catch(() => {});
            } catch (_) {
            }
        } else {
            try { v.pause(); } catch (_) {}
        }
    },

    searchCardToggleMute: function(el) {
        const r = this.searchCardGet(el);
        if (!r) return;
        const card = r.card;
        const v = r.v;
        const refs = r.refs || this.searchCardRefs(card);
        this.searchCardEnsureBound(card, v, refs);
        try {
            v.muted = !v.muted;
            const vol = refs.volEl;
            if (vol) {
                const nextVol = v.muted ? '0' : String(v.volume || 1);
                if (vol.value !== nextVol) vol.value = nextVol;
            }
        } catch (_) {
        }
    },

    searchCardSetVolume: function(el, value) {
        const r = this.searchCardGet(el);
        if (!r) return;
        const card = r.card;
        const v = r.v;
        const refs = r.refs || this.searchCardRefs(card);
        this.searchCardEnsureBound(card, v, refs);
        try {
            const vol = Math.max(0, Math.min(1, Number(value)));
            if (!Number.isFinite(vol)) return;
            const prevVol = Number(v.volume || 0);
            if (Math.abs(prevVol - vol) > 0.0001) v.volume = vol;
            const nextMuted = vol === 0;
            if (v.muted !== nextMuted) v.muted = nextMuted;
        } catch (_) {
        }
        try {
            const volEl = el && el.classList && el.classList.contains('s-ctrl-vol') ? el : refs.volEl;
            if (volEl) {
                const nextVol = String(v.muted ? 0 : (v.volume || 0));
                if (volEl.value !== nextVol) volEl.value = nextVol;
            }
        } catch (_) {
        }
    },

    searchCardFullscreen: function(el) {
        const r = this.searchCardGet(el);
        if (!r) return;
        const card = r.card;
        const v = r.v;
        const refs = r.refs || this.searchCardRefs(card);
        this.searchCardEnsureBound(card, v, refs);
        try {
            const target = (v && v.requestFullscreen) ? v : refs.mediaEl;
            if (target && target.requestFullscreen) target.requestFullscreen().catch(() => {});
        } catch (_) {
        }
    },

    searchCardSeekApply: function(v, bar, ev) {
        if (!v || !bar) return;
        try {
            const d = Number(v.duration || 0);
            if (!d || !Number.isFinite(d)) return;
            const rect = bar.getBoundingClientRect();
            const x = Number(ev && ev.clientX ? ev.clientX : 0) - Number(rect.left || 0);
            const pct = rect.width ? Math.max(0, Math.min(1, x / rect.width)) : 0;
            v.currentTime = pct * d;
        } catch (_) {
        }
    },

    searchCardSeek: function(el, ev) {
        const r = this.searchCardGet(el);
        if (!r) return;
        const card = r.card;
        const v = r.v;
        const refs = r.refs || this.searchCardRefs(card);
        this.searchCardEnsureBound(card, v, refs);
        const bar = el && el.classList && el.classList.contains('s-media-progress')
            ? el
            : refs.progressEl;
        this.searchCardSeekApply(v, bar, ev);
    },

    searchPreviewPlay: function(cardEl) {
        const card = cardEl && cardEl.querySelector ? cardEl : null;
        if (!card) return;
        const refs = this.searchCardRefs(card);
        const v = refs.v;
        if (!v) return;
        this.searchCardEnsureBound(card, v, refs);
        try {
            if (!v._bindSearchPreview) {
                v._bindSearchPreview = true;
                const bindProgressClick = () => {
                    try {
                        const bar = refs.progressEl;
                        if (!bar || bar._boundClick) return;
                        bar._boundClick = true;
                        bar.addEventListener('click', (e) => this.searchCardSeekApply(v, bar, e));
                    } catch (_) {
                    }
                };
                bindProgressClick();
            }
        } catch (_) {
        }
        this.searchCardEnsureSource(v);
        try {
            if ((v.src || v.currentSrc) && v.paused) {
                const p = v.play();
                if (p && typeof p.catch === 'function') p.catch(() => {});
            }
        } catch (_) {
        }
    },

    searchPreviewStop: function(cardEl) {
        const card = cardEl && cardEl.querySelector ? cardEl : null;
        if (!card) return;
        const refs = this.searchCardRefs(card);
        const v = refs.v;
        if (!v) return;
        try { if (!v.paused) v.pause(); } catch (_) {}
        try {
            const cur = Number(v.currentTime || 0);
            if (Number.isFinite(cur) && cur > 0.001) v.currentTime = 0;
        } catch (_) {}
        try {
            const fill = refs.fillEl;
            if (fill && v._searchFillPct !== 0) {
                v._searchFillPct = 0;
                fill.style.width = '0%';
            }
        } catch (_) {
        }
    },

    sendFriendRequest: async function(targetId) {
        if (!this.state.user) return this.openModal('authModal');
        try {
            const url = '/api/v1/users/friend-request/send';
            const res = await this.apiRequest('POST', url, { from_user_id: this.state.user.id, to_user_id: targetId }, { cancel_key: 'friend:request' });
            const data = await res.json();
            if (!res.ok) return alert(data.detail || data.message || '请求发送失败');
            alert(data.message || '请求已发送');
        } catch(e) { console.error(e); alert('请求发送失败'); }
    },

});
