(() => {
    const forceGlobalSelectable = () => {
        const isControl = (el) => {
            try {
                return !!(el && el.closest && el.closest('button,.btn,[role="button"],.status-pill,.drag-handle,.p-del,input,textarea,select,option,a'));
            } catch (_) {
                return false;
            }
        };
        try {
            if (document.getElementById('aiseek_global_selectable')) return;
            const st = document.createElement('style');
            st.id = 'aiseek_global_selectable';
            st.textContent = `
                body, body * {
                    -webkit-user-select: text !important;
                    user-select: text !important;
                }
                button, .btn, [role="button"], .status-pill, .drag-handle, .p-del {
                    -webkit-user-select: none !important;
                    user-select: none !important;
                }
            `;
            document.head.appendChild(st);
        } catch (_) {
        }
        try {
            if (!window.__aiseekGlobalPreventPatched) {
                const rawPrevent = Event.prototype.preventDefault;
                Event.prototype.preventDefault = function () {
                    try {
                        const t = this && this.target;
                        const tp = String((this && this.type) || '');
                        if (!isControl(t) && (tp === 'mousedown' || tp === 'selectstart' || tp === 'pointerdown' || tp === 'dragstart')) {
                            return;
                        }
                    } catch (_) {
                    }
                    return rawPrevent.apply(this, arguments);
                };
                window.__aiseekGlobalPreventPatched = true;
            }
        } catch (_) {
        }
        try {
            document.addEventListener('selectstart', (ev) => {
                if (isControl(ev.target)) return;
                try { ev.stopImmediatePropagation(); } catch (_) {}
            }, true);
        } catch (_) {
        }
        try {
            document.addEventListener('dragstart', (ev) => {
                try {
                    const t = ev && ev.target && ev.target.closest ? ev.target.closest('.drag-handle') : null;
                    if (!t) ev.preventDefault();
                } catch (_) {
                    ev.preventDefault();
                }
            }, true);
        } catch (_) {
        }
    };

    const loadScript = (src) => new Promise((resolve, reject) => {
        const s = document.createElement('script');
        s.src = src;
        s.async = false;
        s.onload = () => resolve();
        s.onerror = () => reject(new Error(`Failed to load ${src}`));
        document.head.appendChild(s);
    });

    const showBootError = (err) => {
        try {
            const existing = document.getElementById('aiseek_boot_error');
            if (existing) return;
            const box = document.createElement('div');
            box.id = 'aiseek_boot_error';
            box.style.position = 'fixed';
            box.style.inset = '0';
            box.style.zIndex = '999999';
            box.style.background = 'rgba(0,0,0,0.78)';
            box.style.display = 'flex';
            box.style.alignItems = 'center';
            box.style.justifyContent = 'center';
            box.style.padding = '24px';
            const card = document.createElement('div');
            card.style.width = 'min(880px, 96vw)';
            card.style.maxHeight = '80vh';
            card.style.overflow = 'auto';
            card.style.borderRadius = '14px';
            card.style.background = '#252632';
            card.style.border = '1px solid rgba(255,255,255,0.10)';
            card.style.boxShadow = '0 18px 70px rgba(0,0,0,0.58)';
            card.style.padding = '18px 18px 14px';
            const title = document.createElement('div');
            title.style.fontSize = '16px';
            title.style.fontWeight = '800';
            title.style.color = 'rgba(255,255,255,0.92)';
            title.style.marginBottom = '10px';
            title.innerText = '前端初始化失败';
            const msg = document.createElement('div');
            msg.style.fontSize = '13px';
            msg.style.color = 'rgba(255,255,255,0.78)';
            msg.style.lineHeight = '1.6';
            msg.style.whiteSpace = 'pre-wrap';
            const e = err || {};
            const text = (e && (e.stack || e.message)) ? String(e.stack || e.message) : String(e);
            msg.innerText = text;
            const actions = document.createElement('div');
            actions.style.display = 'flex';
            actions.style.justifyContent = 'flex-end';
            actions.style.gap = '10px';
            actions.style.marginTop = '12px';
            const btn = document.createElement('button');
            btn.innerText = '刷新重试';
            btn.style.height = '36px';
            btn.style.padding = '0 16px';
            btn.style.borderRadius = '10px';
            btn.style.border = 'none';
            btn.style.cursor = 'pointer';
            btn.style.fontWeight = '700';
            btn.style.background = '#fe2c55';
            btn.style.color = 'white';
            btn.onclick = () => location.reload();
            actions.appendChild(btn);
            card.appendChild(title);
            card.appendChild(msg);
            card.appendChild(actions);
            box.appendChild(card);
            document.body.appendChild(box);
        } catch (_) {
        }
    };

    const boot = async () => {
        forceGlobalSelectable();
        const build =
            (document.body && document.body.dataset && document.body.dataset.aiseekBuild) ||
            (document.querySelector('meta[name="aiseek-build"]') && document.querySelector('meta[name="aiseek-build"]').getAttribute('content')) ||
            String(Date.now());
        const v = `v=${encodeURIComponent(String(build))}`;
        const must = (ok, msg) => {
            if (ok) return;
            throw new Error(String(msg || 'boot check failed'));
        };
        const mustFn = (name) => {
            const app = window.app;
            must(app && typeof app[name] === 'function', `window.app.${String(name)} missing`);
        };
        try {
            await loadScript(`/static/js/modules/events.js?${v}`);
            await loadScript(`/static/js/modules/event_contract.js?${v}`);
            await loadScript(`/static/js/modules/observability.js?${v}`);
            await loadScript(`/static/js/modules/telemetry.js?${v}`);
            await loadScript(`/static/js/modules/pagination.js?${v}`);
            await loadScript(`/static/js/modules/runtime.js?${v}`);
            await loadScript(`/static/js/modules/actions.js?${v}`);
            must(window.__aiseekActionDispatcher, 'actions dispatcher missing');

            await loadScript(`/static/js/app/core.js?${v}`);
            if (!window.app) throw new Error('window.app missing after core.js');
            mustFn('switchTab');

            await loadScript(`/static/js/app/helpers.js?${v}`);
            mustFn('openModal');
            await loadScript(`/static/js/app/api.js?${v}`);
            mustFn('apiRequest');
            await loadScript(`/static/js/app/interaction_store.js?${v}`);
            await loadScript(`/static/js/app/router.js?${v}`);
            mustFn('switchPage');
            await loadScript(`/static/js/app/notifications.js?${v}`);
            try {
                await loadScript('https://cdn.jsdelivr.net/npm/hls.js@1.6.15/dist/hls.min.js');
            } catch (_) {
            }
            await loadScript(`/static/js/app/player.js?${v}`);
            mustFn('loadRecommend');
            await loadScript(`/static/js/app/comments.js?${v}`);
            mustFn('closeComments');
            await Promise.all([
                loadScript(`/static/js/app/search.js?${v}`),
                loadScript(`/static/js/app/profile.js?${v}`),
                loadScript(`/static/js/app/creator.js?${v}`),
                loadScript(`/static/js/app/auth.js?${v}`),
                loadScript(`/static/js/app/floating_player.js?${v}`),
            ]);
            mustFn('loadProfile');

            if (window.app && typeof window.app.init === 'function') {
                await window.app.init();
            } else {
                throw new Error('window.app.init missing');
            }
        } catch (e) {
            showBootError(e);
            throw e;
        }
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => void boot());
    } else {
        void boot();
    }
})();
