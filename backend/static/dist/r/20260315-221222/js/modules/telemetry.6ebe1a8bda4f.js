(function () {
    if (window.__aiseekTelemetry) return;
    window.__aiseekTelemetry = true;

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

    const getSessionId = () => {
        try {
            const sidCookie = getCookie('aiseek_sid');
            if (sidCookie) return sidCookie;
            const k = 'aiseek_session_id';
            let v = localStorage.getItem(k);
            if (!v) {
                v = genId();
                localStorage.setItem(k, v);
            }
            return v;
        } catch (_) {
            return genId();
        }
    };

    const sessionId = getSessionId();

    const queue = [];
    let timer = null;
    let flushing = false;
    let lastFlush = 0;
    let token = null;
    let tokenExp = 0;
    let tokenInFlight = false;

    const refreshToken = (force) => {
        try {
            const now = Math.floor(Date.now() / 1000);
            if (!force && token && tokenExp && tokenExp - now > 60) return;
            if (tokenInFlight) return;
            tokenInFlight = true;
            const api = window.app;
            const p =
                api && typeof api.apiGetJSON === 'function'
                    ? api.apiGetJSON('/api/v1/observability/token', { cache_ttl_ms: 1000 })
                    : null;
            if (p && typeof p.then === 'function') {
                p.then((obj) => {
                    tokenInFlight = false;
                    if (!obj || obj.ok !== true) return;
                    if (obj.token) token = String(obj.token);
                    if (obj.exp) tokenExp = Number(obj.exp) || 0;
                }).catch(() => {
                    tokenInFlight = false;
                });
                return;
            }
            const xhr = new XMLHttpRequest();
            xhr.open('GET', '/api/v1/observability/token', true);
            xhr.onreadystatechange = () => {
                if (xhr.readyState !== 4) return;
                tokenInFlight = false;
                if (xhr.status !== 200) return;
                try {
                    const obj = JSON.parse(xhr.responseText || '{}');
                    if (!obj || obj.ok !== true) return;
                    if (obj.token) token = String(obj.token);
                    if (obj.exp) tokenExp = Number(obj.exp) || 0;
                } catch (_) {
                }
            };
            xhr.send();
        } catch (_) {
            tokenInFlight = false;
        }
    };

    const safeClone = (obj) => {
        try {
            return JSON.parse(JSON.stringify(obj));
        } catch (_) {
            return null;
        }
    };

    const enrich = (event, payload) => {
        const p = payload && typeof payload === 'object' ? payload : {};
        const ts = Number(p.ts || Date.now());
        const tab = p.tab || (window.app && window.app.state && window.app.state.currentTab) || null;
        const route = p.route || String(location.hash || '');
        const requestId = p.request_id || window.__aiseekLastRequestId || null;

        return {
            name: String(event || ''),
            ts,
            session_id: p.session_id || sessionId,
            request_id: requestId,
            tab,
            route,
            data: safeClone(p)
        };
    };

    const schedule = () => {
        if (timer) return;
        timer = setTimeout(() => {
            timer = null;
            flush();
        }, 1500);
    };

    const flush = () => {
        if (flushing) return;
        if (queue.length === 0) return;
        const now = Date.now();
        if (now - lastFlush < 400) return schedule();

        flushing = true;
        lastFlush = now;

        const batch = queue.splice(0, 50);
        refreshToken(false);
        const body = JSON.stringify({ token, events: batch });

        try {
            if (navigator.sendBeacon) {
                const ok = navigator.sendBeacon('/api/v1/observability/events', new Blob([body], { type: 'application/json' }));
                if (ok) {
                    flushing = false;
                    if (queue.length) schedule();
                    return;
                }
            }
        } catch (_) {
        }

        try {
            const xhr = new XMLHttpRequest();
            xhr.open('POST', '/api/v1/observability/events', true);
            xhr.setRequestHeader('Content-Type', 'application/json');
            try { xhr.setRequestHeader('x-session-id', String(sessionId)); } catch (_) {}
            try { xhr.setRequestHeader('x-aiseek-sid', String(sessionId)); } catch (_) {}
            try { xhr.setRequestHeader('x-request-id', String(genId())); } catch (_) {}
            try { if (token) xhr.setRequestHeader('x-aiseek-token', String(token)); } catch (_) {}
            xhr.onreadystatechange = () => {
                if (xhr.readyState !== 4) return;
                flushing = false;
                if (queue.length) schedule();
            };
            xhr.send(body);
        } catch (_) {
            flushing = false;
            if (queue.length) schedule();
        }
    };

    const push = (event, payload) => {
        const e = enrich(event, payload);
        if (!e.name) return;
        queue.push(e);
        if (queue.length >= 20) return flush();
        schedule();
    };

    try {
        const ev = window.appEvents;
        if (ev && typeof ev.emit === 'function' && !ev.__telemetry_patched) {
            const orig = ev.emit.bind(ev);
            ev.emit = (event, payload) => {
                try { push(event, payload); } catch (_) {}
                return orig(event, payload);
            };
            ev.__telemetry_patched = true;
        }
    } catch (_) {
    }

    try {
        refreshToken(true);
    } catch (_) {
    }

    window.addEventListener('pagehide', () => {
        try { flush(); } catch (_) {}
    });
})();
