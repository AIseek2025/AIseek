Object.assign(window.app, {
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
            const key = '__aiseek_sid';
            let sid = localStorage.getItem(key);
            if (!sid) {
                sid = `${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
                localStorage.setItem(key, sid);
            }
            if (!init.headers['x-session-id']) init.headers['x-session-id'] = String(sid);
        } catch (_) {
        }

        const m = String(method || 'GET').toUpperCase();
        const timeoutMs = Number.isFinite(Number(init.timeout_ms)) ? Number(init.timeout_ms) : (m === 'GET' ? 8000 : 12000);
        const retries = Number.isFinite(Number(init.retries)) ? Number(init.retries) : (m === 'GET' ? 1 : 0);
        const backoffBase = 180;

        if (body !== undefined) {
            init.headers['Content-Type'] = init.headers['Content-Type'] || 'application/json';
            init.body = typeof body === 'string' ? body : JSON.stringify(body);
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

        const stateKey = (() => {
            try {
                return new URL(url, location.href).origin;
            } catch (_) {
                return 'default';
            }
        })();

        const cb = (window.__aiseekCircuitBreaker = window.__aiseekCircuitBreaker || new Map());
        const st = cb.get(stateKey) || { fail: 0, openUntil: 0 };
        const now = Date.now();
        if (st.openUntil && now < st.openUntil) {
            throw new Error(`circuit_open ${stateKey}`);
        }

        const inflight = (window.__aiseekInflight = window.__aiseekInflight || new Map());
        const cancelKey = init.cancel_key ? String(init.cancel_key) : '';

        const attemptOnce = async () => {
            const controller = new AbortController();
            if (cancelKey) {
                try {
                    const prev = inflight.get(cancelKey);
                    if (prev && prev.controller) {
                        try { prev.controller.abort(); } catch (_) {}
                    }
                    inflight.set(cancelKey, { controller, ts: Date.now() });
                } catch (_) {
                }
            }
            const t = setTimeout(() => controller.abort(), timeoutMs);
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
                    cb.set(stateKey, { fail: 0, openUntil: 0 });
                } else if (res.status >= 500) {
                    const nextFail = (st.fail || 0) + 1;
                    const openUntil = nextFail >= 3 ? Date.now() + 10000 : 0;
                    cb.set(stateKey, { fail: nextFail, openUntil });
                } else {
                    cb.set(stateKey, { fail: 0, openUntil: 0 });
                }
                return res;
            } finally {
                clearTimeout(t);
                if (cancelKey) {
                    try {
                        const cur = inflight.get(cancelKey);
                        if (cur && cur.controller === controller) inflight.delete(cancelKey);
                    } catch (_) {
                    }
                }
            }
        };

        if (m === 'GET') {
            const dedupeKey = init.dedupe_key ? String(init.dedupe_key) : '';
            const key = dedupeKey ? `D:${dedupeKey}` : '';
            if (key && inflight.get(key) && inflight.get(key).promise) {
                return inflight.get(key).promise;
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
                        const nextFail = (st.fail || 0) + 1;
                        const openUntil = nextFail >= 3 ? Date.now() + 10000 : 0;
                        cb.set(stateKey, { fail: nextFail, openUntil });
                        if (i >= retries) break;
                        const jitter = Math.floor(Math.random() * 120);
                        const wait = backoffBase * Math.pow(2, i) + jitter;
                        await new Promise((r) => setTimeout(r, wait));
                    }
                }
                throw lastErr || new Error('request_failed');
            })();
            if (key) inflight.set(key, { promise: p, ts: Date.now() });
            try {
                return await p;
            } finally {
                if (key) {
                    try {
                        const cur = inflight.get(key);
                        if (cur && cur.promise === p) inflight.delete(key);
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
                const nextFail = (st.fail || 0) + 1;
                const openUntil = nextFail >= 3 ? Date.now() + 10000 : 0;
                cb.set(stateKey, { fail: nextFail, openUntil });
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
        const k = `GET:${url}`;
        const now = Date.now();
        if (ttl > 0) {
            const hit = cache.get(k);
            if (hit && hit.exp > now) return hit.val;
        }

        const res = await this.apiRequest('GET', url, undefined, o);
        if (!res.ok) throw new Error(`GET ${url} ${res.status}`);
        const val = await res.json();
        if (ttl > 0) cache.set(k, { exp: now + ttl, val });
        return val;
    },

    apiPostJSON: async function(url, data, opts) {
        const res = await this.apiRequest('POST', url, data, opts);
        if (!res.ok) throw new Error(`POST ${url} ${res.status}`);
        return await res.json();
    }
});
