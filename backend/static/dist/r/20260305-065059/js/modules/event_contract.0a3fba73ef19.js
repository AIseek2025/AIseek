(function () {
    if (window.appEventContract) return;

    const names = {
        HTTP_REQUEST: 'http:request',
        HTTP_RESPONSE: 'http:response',
        ROUTE_CHANGE: 'route:change',
        FEED_LOADED: 'feed:loaded',
        PLAYER_PLAY: 'player:play',
        PLAYER_PAUSE: 'player:pause',
        PLAYER_ENDED: 'player:ended',
        PLAYER_VOLUME: 'player:volume',
        NOTIFY_OPEN: 'notify:open',
        NOTIFY_LOADED: 'notify:loaded',
        TASK_STATE: 'task:state'
    };

    const contract = {
        [names.HTTP_REQUEST]: ['method', 'url', 'request_id', 'ts'],
        [names.HTTP_RESPONSE]: ['method', 'url', 'status', 'request_id', 'ts'],
        [names.ROUTE_CHANGE]: ['tab', 'ts'],
        [names.FEED_LOADED]: ['source', 'count', 'ts'],
        [names.PLAYER_PLAY]: ['post_id', 'ts'],
        [names.PLAYER_PAUSE]: ['post_id', 'ts'],
        [names.PLAYER_ENDED]: ['post_id', 'ts'],
        [names.PLAYER_VOLUME]: ['post_id', 'volume', 'muted', 'ts'],
        [names.NOTIFY_OPEN]: ['surface', 'ts'],
        [names.NOTIFY_LOADED]: ['surface', 'count', 'ts'],
        [names.TASK_STATE]: ['task', 'status', 'ts']
    };

    const emit = (event, payload) => {
        const p = payload && typeof payload === 'object' ? { ...payload } : {};
        p.ts = p.ts || Date.now();
        try {
            const k = 'aiseek_session_id';
            let sid = null;
            try { sid = localStorage.getItem(k); } catch (_) {}
            if (!sid) {
                const b = new Uint8Array(16);
                if (window.crypto && window.crypto.getRandomValues) window.crypto.getRandomValues(b);
                sid = Array.from(b).map((x) => x.toString(16).padStart(2, '0')).join('');
                try { localStorage.setItem(k, sid); } catch (_) {}
            }
            p.session_id = p.session_id || sid;
        } catch (_) {
        }
        try {
            if (window.app && window.app.state && !p.tab) p.tab = window.app.state.currentTab;
        } catch (_) {
        }
        try {
            if (!p.route) p.route = String(location.hash || '');
        } catch (_) {
        }
        try {
            if (window.appEvents && typeof window.appEvents.emit === 'function') {
                window.appEvents.emit(event, p);
            }
        } catch (_) {
        }
    };

    window.appEventNames = names;
    window.appEventContract = contract;
    window.appEmit = emit;
})();
