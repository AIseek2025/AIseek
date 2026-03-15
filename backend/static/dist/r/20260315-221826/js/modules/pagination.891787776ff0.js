(function () {
    if (window.pagination) return;

    const encodeCursor = (obj) => {
        try {
            return btoa(unescape(encodeURIComponent(JSON.stringify(obj))));
        } catch (_) {
            return '';
        }
    };

    const decodeCursor = (cur) => {
        try {
            return JSON.parse(decodeURIComponent(escape(atob(String(cur || '')))));
        } catch (_) {
            return null;
        }
    };

    const buildCursorParams = (cursor) => {
        const c = cursor ? String(cursor) : '';
        return c ? `&cursor=${encodeURIComponent(c)}` : '';
    };

    window.pagination = { encodeCursor, decodeCursor, buildCursorParams };
})();
