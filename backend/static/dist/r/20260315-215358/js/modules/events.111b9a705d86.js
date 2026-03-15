(function () {
    if (window.appEvents) return;

    const listeners = new Map();

    const on = (event, handler) => {
        if (!event || typeof handler !== 'function') return () => {};
        const set = listeners.get(event) || new Set();
        set.add(handler);
        listeners.set(event, set);
        return () => off(event, handler);
    };

    const off = (event, handler) => {
        const set = listeners.get(event);
        if (!set) return;
        set.delete(handler);
        if (set.size === 0) listeners.delete(event);
    };

    const emit = (event, payload) => {
        const set = listeners.get(event);
        if (!set) return;
        Array.from(set).forEach((fn) => {
            try {
                fn(payload);
            } catch (_) {
            }
        });
    };

    window.appEvents = { on, off, emit };
})();
