Object.assign(window.app, {
    apiRuntimePolicy: function() {
        const now = Date.now();
        const prev = this.__apiRuntimePolicy || null;
        if (prev && prev.exp > now && prev.value) return prev.value;
        const src = (typeof window !== 'undefined' && window.__AISEEK_API_RUNTIME) ? window.__AISEEK_API_RUNTIME : {};
        const toInt = (v, d) => {
            const n = Number(v);
            return Number.isFinite(n) ? Math.floor(n) : d;
        };
        const clamp = (n, min, max) => {
            if (n < min) return min;
            if (n > max) return max;
            return n;
        };
        const value = {
            inflightMax: clamp(toInt(src.inflightMax, 1200), 200, 10000),
            inflightStaleMs: clamp(toInt(src.inflightStaleMs, 120000), 5000, 900000),
            circuitMax: clamp(toInt(src.circuitMax, 512), 64, 4096),
            circuitStaleMs: clamp(toInt(src.circuitStaleMs, 300000), 30000, 3600000),
            circuitThreshold: clamp(toInt(src.circuitThreshold, 3), 2, 20),
            circuitOpenMs: clamp(toInt(src.circuitOpenMs, 10000), 1000, 120000),
            circuitCountCanceledAbort: !!(src && src.circuitCountCanceledAbort),
            circuitKeyMode: String((src && src.circuitKeyMode) || 'origin_method_path').toLowerCase(),
            circuitPathDepth: clamp(toInt(src.circuitPathDepth, 3), 1, 8),
            circuitKeyMaxLen: clamp(toInt(src.circuitKeyMaxLen, 220), 64, 512),
            circuitKeyCacheMax: clamp(toInt(src.circuitKeyCacheMax, 2048), 128, 20000),
            circuitKeyCacheTtlMs: clamp(toInt(src.circuitKeyCacheTtlMs, 30000), 1000, 300000),
            circuitKeySweepEveryOps: clamp(toInt(src.circuitKeySweepEveryOps, 32), 4, 512),
            circuitKeySweepScan: clamp(toInt(src.circuitKeySweepScan, 96), 8, 2048),
            circuitKeySweepMinIntervalMs: clamp(toInt(src.circuitKeySweepMinIntervalMs, 120), 10, 5000),
            circuitKeyCacheIndexMaxLen: clamp(toInt(src.circuitKeyCacheIndexMaxLen, 640), 128, 4096),
            apiCacheMax: clamp(toInt(src.apiCacheMax, 800), 100, 10000),
            apiCacheKeyMaxLen: clamp(toInt(src.apiCacheKeyMaxLen, 320), 96, 2048),
            apiCacheStaleIfErrorMs: clamp(toInt(src.apiCacheStaleIfErrorMs, 15000), 0, 300000),
            inflightKeyMaxLen: clamp(toInt(src.inflightKeyMaxLen, 320), 96, 2048),
            sweepEveryOps: clamp(toInt(src.sweepEveryOps, 20), 5, 200),
            sweepScan: clamp(toInt(src.sweepScan, 64), 16, 1024),
            sweepMinIntervalMs: clamp(toInt(src.sweepMinIntervalMs, 120), 10, 5000),
        };
        this.__apiRuntimePolicy = { value, exp: now + 10000 };
        return value;
    },

    apiHash32: function(s) {
        let h = 2166136261;
        const t = String(s || '');
        for (let i = 0; i < t.length; i++) {
            h ^= t.charCodeAt(i);
            h = Math.imul(h, 16777619);
        }
        return (h >>> 0).toString(16);
    },

    apiCacheKey: function(url) {
        try {
            const p = this.apiRuntimePolicy();
            const raw = `GET:${String(url || '')}`;
            const maxLen = Number(p.apiCacheKeyMaxLen || 320);
            if (raw.length <= maxLen) return raw;
            return `${raw.slice(0, maxLen - 10)}|${this.apiHash32(raw)}`;
        } catch (_) {
            return `GET:${String(url || '')}`;
        }
    },

    apiBoundKey: function(raw, maxLen) {
        const s = String(raw || '');
        const n = Number(maxLen || 0);
        if (n <= 0 || s.length <= n) return s;
        return `${s.slice(0, n - 10)}|${this.apiHash32(s)}`;
    },

    apiCircuitCurrent: function(cb, stateKey) {
        const cur = cb.get(stateKey) || { fail: 0, openUntil: 0, ts: 0 };
        return {
            fail: Number(cur.fail || 0),
            openUntil: Number(cur.openUntil || 0),
            ts: Number(cur.ts || 0),
        };
    },

    apiCircuitSet: function(cb, stateKey, fail, openUntil) {
        cb.set(stateKey, {
            fail: Number(fail || 0),
            openUntil: Number(openUntil || 0),
            ts: Date.now(),
        });
    },

    apiCircuitOnSuccess: function(cb, stateKey) {
        this.apiCircuitSet(cb, stateKey, 0, 0);
    },

    apiCircuitOnFailure: function(cb, stateKey) {
        const p = this.apiRuntimePolicy();
        const cur = this.apiCircuitCurrent(cb, stateKey);
        const nextFail = Number(cur.fail || 0) + 1;
        const threshold = Number(p.circuitThreshold || 3);
        const openMs = Number(p.circuitOpenMs || 10000);
        const openUntil = nextFail >= threshold ? (Date.now() + openMs) : 0;
        this.apiCircuitSet(cb, stateKey, nextFail, openUntil);
    },

    apiShouldCountCircuitFailure: function(err) {
        try {
            if (!err || String(err.name || '') !== 'AbortError') return true;
            const p = this.apiRuntimePolicy();
            if (err && err.__aiseek_abort_timeout) return true;
            return !!(p && p.circuitCountCanceledAbort);
        } catch (_) {
            return true;
        }
    },

    apiCircuitKey: function(method, url) {
        try {
            const p = this.apiRuntimePolicy();
            const mode = String(p.circuitKeyMode || 'origin_method_path').toLowerCase();
            const m = String(method || 'GET').toUpperCase();
            const depth = Number(p.circuitPathDepth || 3);
            const maxLen = Number(p.circuitKeyMaxLen || 220);
            if (!this.__apiCircuitKeyCache) this.__apiCircuitKeyCache = new Map();
            this.__apiCircuitKeyOps = Number(this.__apiCircuitKeyOps || 0) + 1;
            if (this.__apiCircuitKeyOps % Number(p.circuitKeySweepEveryOps || 32) === 0) {
                const now = Date.now();
                const last = Number(this.__apiCircuitKeySweepAt || 0);
                const minGap = Number(p.circuitKeySweepMinIntervalMs || 120);
                if (last <= 0 || minGap <= 0 || (now - last) >= minGap) {
                    this.__apiCircuitKeySweepAt = now;
                    const scanN = Number(p.circuitKeySweepScan || 96);
                    let scanned = 0;
                    for (const [k, v] of this.__apiCircuitKeyCache.entries()) {
                        if (scanned >= scanN) break;
                        scanned += 1;
                        if (!v || !v.exp || Number(v.exp || 0) <= now) this.__apiCircuitKeyCache.delete(k);
                    }
                    while (this.__apiCircuitKeyCache.size > Number(p.circuitKeyCacheMax || 2048)) {
                        const fk = this.__apiCircuitKeyCache.keys().next().value;
                        if (!fk) break;
                        this.__apiCircuitKeyCache.delete(fk);
                    }
                }
            }
            const rawCacheKey = `${m}|${mode}|${depth}|${maxLen}|${String(url || '')}`;
            const cacheKey = this.apiBoundKey(rawCacheKey, Number(p.circuitKeyCacheIndexMaxLen || 640));
            const hit = this.__apiCircuitKeyCache.get(cacheKey);
            if (hit && hit.key && Number(hit.exp || 0) > Date.now()) {
                this.__apiCircuitKeyCache.delete(cacheKey);
                this.__apiCircuitKeyCache.set(cacheKey, hit);
                return String(hit.key);
            }
            const u = new URL(url, location.href);
            const origin = String(u.origin || 'default');
            const parts = String(u.pathname || '/').split('/').filter(Boolean).slice(0, depth).map((seg) => {
                const s = String(seg || '');
                if (/^\d+$/.test(s)) return ':n';
                if (/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(s)) return ':uuid';
                if (/^[0-9a-f]{12,}$/i.test(s)) return ':h';
                if (/^[A-Za-z0-9_-]{20,}$/.test(s)) return ':id';
                return s.length > 24 ? s.slice(0, 24) : s;
            });
            const pathKey = '/' + parts.join('/');
            let out = '';
            if (mode === 'origin') out = origin;
            else if (mode === 'origin_method') out = `${origin}|${m}`;
            else if (mode === 'origin_path') out = `${origin}|${pathKey}`;
            else out = `${origin}|${m}|${pathKey}`;
            const finalKey = out.length > maxLen ? out.slice(0, maxLen) : out;
            this.__apiCircuitKeyCache.set(cacheKey, { key: finalKey, exp: Date.now() + Number(p.circuitKeyCacheTtlMs || 30000) });
            while (this.__apiCircuitKeyCache.size > Number(p.circuitKeyCacheMax || 2048)) {
                const fk = this.__apiCircuitKeyCache.keys().next().value;
                if (!fk) break;
                this.__apiCircuitKeyCache.delete(fk);
            }
            return finalKey;
        } catch (_) {
            return 'default';
        }
    },

    apiSweepMaps: function(inflight, cb, cache) {
        try {
            const p = this.apiRuntimePolicy();
            this.__apiOps = Number(this.__apiOps || 0) + 1;
            if (this.__apiOps % Number(p.sweepEveryOps || 20) !== 0) return;
            const now = Date.now();
            const last = Number(this.__apiSweepAt || 0);
            const minGap = Number(p.sweepMinIntervalMs || 120);
            if (last > 0 && minGap > 0 && (now - last) < minGap) return;
            this.__apiSweepAt = now;
            const scan = Number(p.sweepScan || 64);
            let i = 0;
            if (inflight && typeof inflight.entries === 'function') {
                for (const [k, v] of inflight.entries()) {
                    if (i >= scan) break;
                    i += 1;
                    const ts = Number(v && v.ts || 0);
                    if (!ts || now - ts > Number(p.inflightStaleMs || 120000)) inflight.delete(k);
                }
                while (inflight.size > Number(p.inflightMax || 1200)) {
                    const fk = inflight.keys().next().value;
                    if (!fk) break;
                    inflight.delete(fk);
                }
            }
            i = 0;
            if (cb && typeof cb.entries === 'function') {
                for (const [k, v] of cb.entries()) {
                    if (i >= scan) break;
                    i += 1;
                    const ts = Number(v && v.ts || 0);
                    const fail = Number(v && v.fail || 0);
                    const openUntil = Number(v && v.openUntil || 0);
                    if ((fail <= 0 && openUntil <= now) || (ts && now - ts > Number(p.circuitStaleMs || 300000))) cb.delete(k);
                }
                while (cb.size > Number(p.circuitMax || 512)) {
                    const fk = cb.keys().next().value;
                    if (!fk) break;
                    cb.delete(fk);
                }
            }
            i = 0;
            if (cache && typeof cache.entries === 'function') {
                for (const [k, v] of cache.entries()) {
                    if (i >= scan) break;
                    i += 1;
                    if (!v || !v.exp || v.exp <= now) cache.delete(k);
                }
                while (cache.size > Number(p.apiCacheMax || 800)) {
                    const fk = cache.keys().next().value;
                    if (!fk) break;
                    cache.delete(fk);
                }
            }
        } catch (_) {
        }
    },

    apiRequest: async function(method, url, body, opts) {
        const init = opts && typeof opts === 'object' ? { ...opts } : {};
        init.method = method;
        init.headers = init.headers ? { ...init.headers } : {};
        try {
            const token = localStorage.getItem('token');
            if (token && !init.headers['Authorization'] && !init.headers['authorization']) {
                init.headers['Authorization'] = `Bearer ${String(token)}`;
            }
        } catch (_) {
        }
        try {
            const getCookie = (name) => {
                try {
                    const s = String(document.cookie || '');
                    const parts = s.split(';');
                    for (let i = 0; i < parts.length; i++) {
                        const p = parts[i].trim();
                        if (!p) continue;
                        const j = p.indexOf('=');
                        if (j <= 0) continue;
                        const k = p.slice(0, j).trim();
                        if (k !== name) continue;
                        return decodeURIComponent(p.slice(j + 1).trim());
                    }
                } catch (_) {
                }
                return null;
            };
            const key = '__aiseek_sid';
            let sid = null;
            try {
                const sid2 = getCookie('aiseek_sid');
                if (sid2) sid = String(sid2);
            } catch (_) {
            }
            if (!sid) sid = localStorage.getItem(key);
            if (!sid) {
                sid = `${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
                localStorage.setItem(key, sid);
            }
            if (!init.headers['x-session-id']) init.headers['x-session-id'] = String(sid);
            if (!init.headers['x-aiseek-sid']) init.headers['x-aiseek-sid'] = String(sid);
        } catch (_) {
        }

        const m = String(method || 'GET').toUpperCase();
        const timeoutMs = Number.isFinite(Number(init.timeout_ms)) ? Number(init.timeout_ms) : (m === 'GET' ? 8000 : 12000);
        const retries = Number.isFinite(Number(init.retries)) ? Number(init.retries) : (m === 'GET' ? 1 : 0);
        const backoffBase = 180;

        if (body !== undefined) {
            const isForm =
                typeof window !== 'undefined' &&
                typeof window.FormData === 'function' &&
                body instanceof window.FormData;
            if (isForm) {
                init.body = body;
            } else {
                init.headers['Content-Type'] = init.headers['Content-Type'] || 'application/json';
                init.body = typeof body === 'string' ? body : JSON.stringify(body);
            }
        }
        try {
            const hasKey = !!(init.headers['idempotency-key'] || init.headers['Idempotency-Key'] || init.headers['x-idempotency-key'] || init.headers['X-Idempotency-Key']);
            const enabled = init.idempotency === false ? false : true;
            const u = String(url || '');
            const should =
                enabled &&
                !hasKey &&
                m !== 'GET' &&
                typeof init.body === 'string' &&
                init.body.length > 0 &&
                (u.includes('/api/v1/ai/') || u.includes('/api/v1/posts/') || u.includes('/api/v1/users/'));
            if (should) {
                let h = 2166136261;
                const s = `${m}|${u}|${init.body}`;
                for (let i = 0; i < s.length; i++) {
                    h ^= s.charCodeAt(i);
                    h = Math.imul(h, 16777619);
                }
                const bucket = Math.floor(Date.now() / 30000);
                init.headers['x-idempotency-key'] = `ik_${(h >>> 0).toString(16)}_${bucket}`;
            }
        } catch (_) {
        }

        const stateKey = this.apiCircuitKey(m, url);

        const cb = (window.__aiseekCircuitBreaker = window.__aiseekCircuitBreaker || new Map());
        const st = this.apiCircuitCurrent(cb, stateKey);
        const now = Date.now();
        if (st.openUntil && now < st.openUntil) {
            throw new Error(`circuit_open ${stateKey}`);
        }

        const inflight = (window.__aiseekInflight = window.__aiseekInflight || new Map());
        const apiCache = (window.__aiseekApiCache = window.__aiseekApiCache || new Map());
        this.apiSweepMaps(inflight, cb, apiCache);
        const runtimePolicy = this.apiRuntimePolicy();
        const inflightKeyMaxLen = Number(runtimePolicy.inflightKeyMaxLen || 320);
        const cancelKey = init.cancel_key ? this.apiBoundKey(String(init.cancel_key), inflightKeyMaxLen) : '';
        const cancelMapKey = cancelKey ? `C:${cancelKey}` : '';

        const attemptOnce = async () => {
            const controller = new AbortController();
            if (cancelMapKey) {
                try {
                    const prev = inflight.get(cancelMapKey);
                    if (prev && prev.controller) {
                        try { prev.controller.abort(); } catch (_) {}
                    }
                    inflight.set(cancelMapKey, { controller, ts: Date.now() });
                } catch (_) {
                }
            }
            let timeoutAbort = false;
            const t = setTimeout(() => {
                timeoutAbort = true;
                controller.abort();
            }, timeoutMs);
            try {
                const res = await fetch(url, { ...init, signal: controller.signal });
                const reqId = (res && res.headers && res.headers.get('x-request-id')) || null;
                try {
                    if (window.appEvents && typeof window.appEvents.emit === 'function') {
                        window.appEvents.emit('http:response', { method: m, url, status: res.status, request_id: reqId, ts: Date.now() });
                    }
                } catch (_) {
                }

                if (res.ok) {
                    this.apiCircuitOnSuccess(cb, stateKey);
                } else {
                    this.apiCircuitOnSuccess(cb, stateKey);
                }
                return res;
            } catch (e) {
                try {
                    if (e && String(e.name || '') === 'AbortError' && timeoutAbort) {
                        e.__aiseek_abort_timeout = true;
                    }
                } catch (_) {
                }
                throw e;
            } finally {
                clearTimeout(t);
                if (cancelMapKey) {
                    try {
                        const cur = inflight.get(cancelMapKey);
                        if (cur && cur.controller === controller) inflight.delete(cancelMapKey);
                    } catch (_) {
                    }
                }
            }
        };

        if (m === 'GET') {
            const dedupeKey = init.dedupe_key ? this.apiBoundKey(String(init.dedupe_key), inflightKeyMaxLen) : '';
            const dedupeMapKey = dedupeKey ? `D:${dedupeKey}` : '';
            const pending = dedupeMapKey ? inflight.get(dedupeMapKey) : null;
            if (pending && pending.promise) {
                return pending.promise;
            }
            const p = (async () => {
                let lastErr = null;
                for (let i = 0; i <= retries; i++) {
                    try {
                        const res = await attemptOnce();
                        if (res.ok || res.status < 500) return res;
                        throw new Error(`HTTP_${res.status}`);
                    } catch (e) {
                        lastErr = e;
                        if (this.apiShouldCountCircuitFailure(e)) this.apiCircuitOnFailure(cb, stateKey);
                        if (i >= retries) break;
                        const jitter = Math.floor(Math.random() * 120);
                        const wait = backoffBase * Math.pow(2, i) + jitter;
                        await new Promise((r) => setTimeout(r, wait));
                    }
                }
                throw lastErr || new Error('request_failed');
            })();
            if (dedupeMapKey) inflight.set(dedupeMapKey, { promise: p, ts: Date.now() });
            try {
                return await p;
            } finally {
                if (dedupeMapKey) {
                    try {
                        const cur = inflight.get(dedupeMapKey);
                        if (cur && cur.promise === p) inflight.delete(dedupeMapKey);
                    } catch (_) {
                    }
                }
            }
        }

        let lastErr = null;
        for (let i = 0; i <= retries; i++) {
            try {
                const res = await attemptOnce();
                if (res.ok || res.status < 500) return res;
                throw new Error(`HTTP_${res.status}`);
            } catch (e) {
                lastErr = e;
                if (this.apiShouldCountCircuitFailure(e)) this.apiCircuitOnFailure(cb, stateKey);
                if (i >= retries) break;
                const jitter = Math.floor(Math.random() * 120);
                const wait = backoffBase * Math.pow(2, i) + jitter;
                await new Promise((r) => setTimeout(r, wait));
            }
        }
        throw lastErr || new Error('request_failed');
    },

    apiGetJSON: async function(url, opts) {
        const o = opts && typeof opts === 'object' ? { ...opts } : {};
        const ttl = Number.isFinite(Number(o.cache_ttl_ms)) ? Number(o.cache_ttl_ms) : (o.cache ? 1000 : 0);
        const cache = (window.__aiseekApiCache = window.__aiseekApiCache || new Map());
        const policy = this.apiRuntimePolicy();
        const k = this.apiCacheKey(url);
        const now = Date.now();
        let stale = null;
        if (ttl > 0) {
            const hit = cache.get(k);
            if (hit && hit.exp > now) {
                cache.delete(k);
                cache.set(k, hit);
                return hit.val;
            }
            if (hit && hit.exp) stale = hit;
        }
        try {
            const res = await this.apiRequest('GET', url, undefined, o);
            if (!res.ok) throw new Error(`GET ${url} ${res.status}`);
            const val = await res.json();
            if (ttl > 0) {
                cache.delete(k);
                cache.set(k, { exp: Date.now() + ttl, val });
                while (cache.size > Number(policy.apiCacheMax || 800)) {
                    const fk = cache.keys().next().value;
                    if (!fk) break;
                    cache.delete(fk);
                }
            }
            return val;
        } catch (e) {
            const staleIfErrorMs = Number(policy.apiCacheStaleIfErrorMs || 0);
            if (stale && staleIfErrorMs > 0 && (now - Number(stale.exp || 0)) <= staleIfErrorMs) {
                return stale.val;
            }
            throw e;
        }
    },

    apiPostJSON: async function(url, data, opts) {
        const res = await this.apiRequest('POST', url, data, opts);
        if (!res.ok) throw new Error(`POST ${url} ${res.status}`);
        return await res.json();
    },

    apiBeacon: async function(method, url, body, opts) {
        const init = opts && typeof opts === 'object' ? { ...opts } : {};
        init.method = String(method || 'POST').toUpperCase();
        init.headers = init.headers ? { ...init.headers } : {};
        try {
            const token = localStorage.getItem('token');
            if (token && !init.headers['Authorization'] && !init.headers['authorization']) {
                init.headers['Authorization'] = `Bearer ${String(token)}`;
            }
        } catch (_) {
        }
        try {
            const key = '__aiseek_sid';
            let sid = localStorage.getItem(key);
            if (!sid) {
                sid = `${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
                localStorage.setItem(key, sid);
            }
            if (!init.headers['x-session-id']) init.headers['x-session-id'] = String(sid);
        } catch (_) {
        }
        try {
            if (body !== undefined) {
                const isForm =
                    typeof window !== 'undefined' &&
                    typeof window.FormData === 'function' &&
                    body instanceof window.FormData;
                if (isForm) init.body = body;
                else {
                    init.headers['Content-Type'] = init.headers['Content-Type'] || 'application/json';
                    init.body = typeof body === 'string' ? body : JSON.stringify(body);
                }
            }
        } catch (_) {
        }
        try {
            init.keepalive = init.keepalive === false ? false : true;
        } catch (_) {
        }
        try {
            const res = await fetch(url, init);
            return res;
        } catch (_) {
            return null;
        }
    },

    netPrefetch: async function(url, opts) {
        const init = opts && typeof opts === 'object' ? { ...opts } : {};
        init.method = init.method || 'GET';
        try {
            init.mode = init.mode || 'no-cors';
            init.cache = init.cache || 'no-store';
            init.credentials = init.credentials || 'omit';
            init.keepalive = init.keepalive === false ? false : true;
        } catch (_) {
        }
        try {
            await fetch(url, init);
        } catch (_) {
        }
    }
});
