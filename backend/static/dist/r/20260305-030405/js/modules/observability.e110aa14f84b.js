(function () {
    if (window.__aiseekFetchWrapped) return;
    window.__aiseekFetchWrapped = true;

    const origFetch = window.fetch ? window.fetch.bind(window) : null;
    if (!origFetch) return;

    const genId = () => {
        try {
            if (window.crypto && window.crypto.getRandomValues) {
                const b = new Uint8Array(16);
                window.crypto.getRandomValues(b);
                return Array.from(b).map((x) => x.toString(16).padStart(2, '0')).join('');
            }
        } catch (_) {
        }
        return String(Date.now()) + '-' + String(Math.random()).slice(2);
    };

    window.fetch = (input, init) => {
        try {
            const nextInit = init ? { ...init } : {};
            const headers = new Headers(nextInit.headers || (typeof input === 'object' && input && input.headers) || undefined);
            if (!headers.has('x-request-id')) headers.set('x-request-id', genId());
            try {
                const k = 'aiseek_session_id';
                let sid = null;
                try { sid = localStorage.getItem(k); } catch (_) {}
                if (!sid) {
                    sid = genId();
                    try { localStorage.setItem(k, sid); } catch (_) {}
                }
                if (!headers.has('x-session-id')) headers.set('x-session-id', sid);
            } catch (_) {
            }
            nextInit.headers = headers;
            try {
                if (window.appEvents && typeof window.appEvents.emit === 'function') {
                    const method = (nextInit.method || 'GET').toUpperCase();
                    const url = typeof input === 'string' ? input : (input && input.url) || '';
                    const rid = headers.get('x-request-id');
                    window.__aiseekLastRequestId = rid;
                    window.appEvents.emit('http:request', { method, url, request_id: rid, session_id: headers.get('x-session-id'), ts: Date.now() });
                }
            } catch (_) {
            }
            const method = (nextInit.method || 'GET').toUpperCase();
            const url = typeof input === 'string' ? input : (input && input.url) || '';
            const rid = headers.get('x-request-id');
            const t0 = Date.now();
            const p = origFetch(input, nextInit);
            if (p && typeof p.then === 'function') {
                return p.then((res) => {
                    try {
                        if (window.appEvents && typeof window.appEvents.emit === 'function') {
                            window.appEvents.emit('http:response', { method, url, status: res ? res.status : 0, request_id: rid, latency_ms: Date.now() - t0, ts: Date.now() });
                        }
                    } catch (_) {
                    }
                    return res;
                }).catch((e) => {
                    try {
                        if (window.appEvents && typeof window.appEvents.emit === 'function') {
                            window.appEvents.emit('http:error', { method, url, request_id: rid, latency_ms: Date.now() - t0, message: String((e && e.message) || e || 'fetch_error'), ts: Date.now() });
                        }
                    } catch (_) {
                    }
                    throw e;
                });
            }
            return p;
        } catch (_) {
            return origFetch(input, init);
        }
    };
})();
