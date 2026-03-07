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

    const getSessionId = () => {
        try {
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
        const body = JSON.stringify({ events: batch });

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

        fetch('/api/v1/observability/events', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body
        }).finally(() => {
            flushing = false;
            if (queue.length) schedule();
        });
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

    window.addEventListener('pagehide', () => {
        try { flush(); } catch (_) {}
    });
})();
