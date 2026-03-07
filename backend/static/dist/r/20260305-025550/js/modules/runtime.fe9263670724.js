(function () {
    if (window.appRuntime) return;

    const now = () => Date.now();
    const safe = (fn) => {
        try { return fn(); } catch (_) { return null; }
    };

    const state = {
        page: null,
        cleanups: new Map(),
        wrapped: false,
        patchedSwitch: false,
        lastErrAt: 0,
        errCount: 0
    };

    const getToken = () => {
        try {
            const t = localStorage.getItem('token');
            return t ? String(t) : '';
        } catch (_) {
            return '';
        }
    };

    const getSessionId = () => {
        try {
            const k = 'aiseek_sid';
            let v = localStorage.getItem(k);
            if (v) return String(v);
            v = `${Date.now().toString(16)}-${Math.random().toString(16).slice(2)}`;
            localStorage.setItem(k, v);
            return v;
        } catch (_) {
            return '';
        }
    };

    const makeReqId = () => {
        try {
            return `${Date.now().toString(16)}-${Math.random().toString(16).slice(2)}`;
        } catch (_) {
            return String(Date.now());
        }
    };

    const isApiUrl = (u) => {
        try {
            const url = new URL(String(u || ''), window.location && window.location.origin ? window.location.origin : undefined);
            const p = String(url.pathname || '');
            return p.startsWith('/api/');
        } catch (_) {
            return false;
        }
    };

    const patchFetch = () => {
        try {
            if (window.__aiseek_fetch_patched) return;
            if (!window.fetch) return;
            const orig = window.fetch.bind(window);
            window.fetch = function (input, init) {
                try {
                    const req = input;
                    const url = (req && typeof req === 'object' && req.url) ? String(req.url) : String(req || '');
                    if (!isApiUrl(url)) return orig(input, init);

                    const sid = getSessionId();
                    const rid = makeReqId();
                    const token = getToken();

                    if (req && typeof req === 'object' && typeof window.Request === 'function' && req instanceof window.Request) {
                        const headers = new window.Headers(req.headers || undefined);
                        try { if (sid && !headers.get('x-session-id')) headers.set('x-session-id', sid); } catch (_) {}
                        try { if (rid && !headers.get('x-request-id')) headers.set('x-request-id', rid); } catch (_) {}
                        try {
                            if (token && !headers.get('authorization')) headers.set('Authorization', `Bearer ${token}`);
                        } catch (_) {}
                        return orig(new window.Request(req, { headers }), init);
                    }

                    const next = Object.assign({}, init || {});
                    const headers = new window.Headers(next.headers || undefined);
                    try { if (sid && !headers.get('x-session-id')) headers.set('x-session-id', sid); } catch (_) {}
                    try { if (rid && !headers.get('x-request-id')) headers.set('x-request-id', rid); } catch (_) {}
                    try {
                        if (token && !headers.get('authorization')) headers.set('Authorization', `Bearer ${token}`);
                    } catch (_) {}
                    next.headers = headers;
                    return orig(input, next);
                } catch (_) {
                    return orig(input, init);
                }
            };
            window.__aiseek_fetch_patched = true;
        } catch (_) {
        }
    };

    const emit = (name, payload) => {
        try {
            if (window.appEmit) window.appEmit(name, payload || {});
            else if (window.appEvents && typeof window.appEvents.emit === 'function') window.appEvents.emit(String(name || ''), payload || {});
        } catch (_) {
        }
    };

    const normalizeErr = (e) => {
        try {
            if (!e) return { message: 'unknown', stack: '' };
            if (typeof e === 'string') return { message: e, stack: '' };
            return { message: String(e.message || e.toString() || 'error'), stack: String(e.stack || '') };
        } catch (_) {
            return { message: 'error', stack: '' };
        }
    };

    const reportError = (kind, err, extra) => {
        const t = now();
        if (t - state.lastErrAt > 3000) state.errCount = 0;
        state.lastErrAt = t;
        state.errCount += 1;
        if (state.errCount > 12) return;
        const e = normalizeErr(err);
        emit('ui:error', {
            kind: String(kind || 'error'),
            message: e.message,
            stack: e.stack,
            page: state.page || (window.app && window.app.state && window.app.state.currentTab) || null,
            extra: extra && typeof extra === 'object' ? extra : null
        });
    };

    const wrapFn = (fn, name) => {
        if (typeof fn !== 'function') return fn;
        if (fn.__aiseek_wrapped) return fn;
        const w = function () {
            try {
                const r = fn.apply(this, arguments);
                if (r && typeof r.then === 'function' && typeof r.catch === 'function') {
                    return r.catch((e) => {
                        reportError('promise', e, { fn: String(name || '') });
                        throw e;
                    });
                }
                return r;
            } catch (e) {
                reportError('exception', e, { fn: String(name || '') });
                throw e;
            }
        };
        try { w.__aiseek_wrapped = true; } catch (_) {}
        return w;
    };

    const wrapAppMethods = (app) => {
        if (!app || typeof app !== 'object') return;
        if (state.wrapped) return;
        state.wrapped = true;
        try {
            Object.keys(app).forEach((k) => {
                const v = app[k];
                if (typeof v !== 'function') return;
                if (k === 'init') return;
                if (k[0] === '_') return;
                app[k] = wrapFn(v, k);
            });
        } catch (_) {
        }
    };

    const registerCleanup = (page, fn) => {
        if (typeof fn !== 'function') return () => {};
        const p = String(page || state.page || 'global');
        const set = state.cleanups.get(p) || new Set();
        set.add(fn);
        state.cleanups.set(p, set);
        return () => {
            try { set.delete(fn); } catch (_) {}
        };
    };

    const cleanup = (page) => {
        const p = String(page || state.page || 'global');
        const set = state.cleanups.get(p);
        if (!set) return;
        Array.from(set).forEach((fn) => {
            try { fn(); } catch (e) { reportError('cleanup', e, { page: p }); }
        });
        set.clear();
    };

    const enterPage = (page) => {
        const prev = state.page;
        if (prev && prev !== page) cleanup(prev);
        state.page = String(page || '');
        emit('ui:page', { page: state.page, prev });
    };

    const patchSwitchPage = () => {
        if (state.patchedSwitch) return;
        const app = window.app;
        if (!app || typeof app.switchPage !== 'function') return;
        const orig = app.switchPage.bind(app);
        app.switchPage = function (page, opts) {
            try {
                enterPage(String(page || ''));
            } catch (_) {
            }
            return orig(page, opts);
        };
        state.patchedSwitch = true;
    };

    const attach = (app) => {
        try { wrapAppMethods(app); } catch (_) {}
        try { patchSwitchPage(); } catch (_) {}
        try { enterPage((app && app.state && app.state.currentTab) || 'recommend'); } catch (_) {}
    };

    try {
        window.addEventListener('error', (ev) => {
            try {
                const msg = ev && (ev.message || (ev.error && ev.error.message)) || 'error';
                reportError('window.error', ev && ev.error ? ev.error : msg, {
                    filename: ev && ev.filename,
                    lineno: ev && ev.lineno,
                    colno: ev && ev.colno
                });
            } catch (_) {
            }
        });
        window.addEventListener('unhandledrejection', (ev) => {
            try { reportError('unhandledrejection', ev && ev.reason ? ev.reason : ev); } catch (_) {}
        });
    } catch (_) {
    }

    const tick = () => {
        if (window.app) attach(window.app);
    };
    safe(() => tick());
    safe(() => setInterval(() => { try { patchSwitchPage(); } catch (_) {} }, 600));
    safe(() => patchFetch());

    window.appRuntime = {
        attach,
        enterPage,
        registerCleanup,
        cleanup,
        wrapFn,
        reportError
    };
})();
