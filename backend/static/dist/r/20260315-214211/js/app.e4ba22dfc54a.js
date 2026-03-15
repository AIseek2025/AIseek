(function () {
    if (window.__aiseek_main_js_loaded) return;
    window.__aiseek_main_js_loaded = true;
    try {
        const s = document.createElement('script');
        s.src = '/static/js/main.js?v=1';
        s.async = true;
        document.head.appendChild(s);
    } catch (_) {
        try { location.reload(); } catch (_) {}
    }
})();

