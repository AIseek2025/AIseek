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
        this.renderSearchResults();
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
        return { mode, query, viewer, key: `${mode}|${query}|${String(viewer)}` };
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
        return `
                <div class="s-card" data-post-id="${p.id}" data-action="call" data-fn="openPost" data-args="[${p.id}]" data-action-mouseover="call" data-fn-mouseover="showJxPopupById" data-args-mouseover="[${p.id}]" data-pass-el-mouseover="1" data-action-mouseout="call" data-fn-mouseout="hideJxPopup" data-args-mouseout="[]" data-pass-el-mouseout="1">
                    <div class="s-media">
                        <video class="s-media-video" muted playsinline preload="metadata" poster="${cover2}" data-hls="${safeHls}" data-mp4="${safeMp4}" data-video="${safeVideo}"></video>
                        <div class="s-media-controls" data-action="stop" data-stop="1">
                            <div class="s-media-progress" data-action-pointerdown="call" data-fn-pointerdown="searchCardSeek" data-pass-el-pointerdown="1" data-pass-event-pointerdown="1" data-stop="1"><div class="s-media-progress-fill"></div></div>
                            <div class="s-ctrl-row">
                                <div class="s-ctrl-left">
                                    <div class="s-ctrl-btn s-ctrl-play" data-action="call" data-fn="searchCardTogglePlay" data-pass-el="1" data-stop="1"><i class="fas fa-play"></i></div>
                                    <div class="s-ctrl-time"><span class="s-ctrl-time-cur">00:00</span><span class="s-ctrl-time-split">/</span><span class="s-ctrl-time-dur">00:00</span></div>
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
                const url = `/api/v1/search/posts?q=${encodeURIComponent(query)}&limit=${limitPosts}&cursor=${encodeURIComponent(cursor)}`;
                const out = await this.searchFetchLoadMoreCached(url, loadMoreCfg, `search:more:posts`);
                const cur = this.searchStateKeyView();
                if (cur.mode !== mode || cur.query !== query) return;
                if (cur.key !== activeKey) return;
                const posts = Array.isArray(out.data) ? out.data : [];
                if (!posts.length) {
                    this.state.searchCursorPosts = '';
                    return;
                }
                const btn = document.getElementById('search_load_more_posts');
                if (btn && btn.parentElement) btn.parentElement.remove();
                const dateCtx = this.searchDateFmtContext(policy);

                if (mode === 'all') {
                    const wf = document.getElementById('search_posts_waterfall');
                    if (wf) wf.insertAdjacentHTML('beforeend', this.searchRenderVideoCards(posts, dateCtx));
                    const nextCursor = this.searchCursorNormalize(out.next);
                    this.state.searchCursorPosts = nextCursor;
                    if (nextCursor) {
                        if (wf) wf.insertAdjacentHTML('afterend', morePostsHtml);
                    }
                } else {
                    grid.insertAdjacentHTML('beforeend', this.searchRenderVideoCards(posts, dateCtx));
                    const nextCursor = this.searchCursorNormalize(out.next);
                    this.state.searchCursorPosts = nextCursor;
                    if (nextCursor) {
                        grid.insertAdjacentHTML('beforeend', morePostsHtml);
                    }
                }
                try { this.searchBindEngagement(grid); } catch (_) {}
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
            if (mode === 'video') {
                const limit = 24;
                const url = `/api/v1/search/posts?q=${encodeURIComponent(query)}&limit=${limit}`;
                let posts = [];
                let next = '';
                const out = await this.searchFetchFirstPageCached(url, firstPageCfg);
                posts = Array.isArray(out.data) ? out.data : [];
                next = String(out.next || '');
                if (!this.searchIsActiveRender(activeKey, seq)) return;
                try { this.state.searchPosts = Array.isArray(posts) ? posts : []; } catch (_) {}
                this.state.searchCursorPosts = this.searchCursorNormalize(next);
                html = (posts.length === 0) ? '<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--text-secondary);">未找到相关视频</div>' : this.searchRenderVideoCards(posts, dateCtx);
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
                const pUrl = `/api/v1/search/posts?q=${encodeURIComponent(query)}&limit=${limitPosts}`;
                const pair = allowUserLookup
                    ? await Promise.all([
                        this.searchFetchFirstPageCached(pUrl, firstPageCfg),
                        this.searchFetchFirstPageCached(`/api/v1/users/search-user?query=${encodeURIComponent(query)}&limit=${limitUsers}`, firstPageCfg),
                    ])
                    : [await this.searchFetchFirstPageCached(pUrl, firstPageCfg), { data: [], next: '' }];
                if (!this.searchIsActiveRender(activeKey, seq)) return;
                const pOut = pair[0];
                const uOut = pair[1];

                const users = Array.isArray(uOut.data) ? uOut.data : [];
                const posts = Array.isArray(pOut.data) ? pOut.data : [];
                this.state.searchCursorUsers = this.searchCursorNormalize(uOut.next);
                this.state.searchCursorPosts = this.searchCursorNormalize(pOut.next);
                try { this.state.searchPosts = Array.isArray(posts) ? posts : []; } catch (_) {}
                
                if (users.length === 0 && posts.length === 0) {
                    html = '<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--text-secondary);">未找到相关内容</div>';
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
        } catch(e) {
            console.error(e);
            if (!this.searchIsActiveRender(activeKey, seq)) return;
            grid.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--text-secondary);">搜索失败，请重试</div>';
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
                    const d = Number(v.duration || 0);
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
