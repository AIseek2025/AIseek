Object.assign(window.app, {
    ensureFloatingPlayer: function() {
        let wrap = document.getElementById('floating_player');
        if (wrap) return wrap;

        wrap = document.createElement('div');
        wrap.id = 'floating_player';
        wrap.style.position = 'fixed';
        wrap.style.width = '640px';
        wrap.style.height = '360px';
        wrap.style.right = '18px';
        wrap.style.bottom = '18px';
        wrap.style.borderRadius = '12px';
        wrap.style.overflow = 'hidden';
        wrap.style.background = '#000';
        wrap.style.boxShadow = '0 16px 64px rgba(0,0,0,0.65)';
        wrap.style.zIndex = '5000';
        wrap.style.display = 'none';
        wrap.style.touchAction = 'none';
        wrap.style.cursor = 'grab';

        const video = document.createElement('video');
        video.id = 'floating_player_video';
        video.style.width = '100%';
        video.style.height = '100%';
        video.style.objectFit = 'cover';
        video.style.display = 'block';
        video.playsInline = true;
        video.loop = true;
        video.preload = 'metadata';
        try {
            video.dataset.action = 'floatingClick';
            video.setAttribute('data-action-dblclick', 'floatingDblClick');
        } catch (_) {
        }

        const overlay = document.createElement('div');
        overlay.id = 'floating_player_overlay';
        overlay.style.position = 'absolute';
        overlay.style.inset = '0';
        overlay.style.background = 'linear-gradient(to top, rgba(0,0,0,0.55), rgba(0,0,0,0.0) 55%)';
        overlay.style.opacity = '0';
        overlay.style.transition = 'opacity 0.18s';
        overlay.style.display = 'flex';
        overlay.style.flexDirection = 'column';
        overlay.style.justifyContent = 'flex-end';
        overlay.style.alignItems = 'stretch';
        overlay.style.padding = '10px 10px 10px';
        overlay.style.pointerEvents = 'none';
        overlay.style.zIndex = '3';

        const mkHandle = (dir, css) => {
            const h = document.createElement('div');
            h.className = `floating-resize-handle floating-resize-${dir}`;
            h.style.position = 'absolute';
            h.style.width = '18px';
            h.style.height = '18px';
            h.style.borderRadius = '7px';
            h.style.background = 'rgba(255,255,255,0.18)';
            h.style.border = '1px solid rgba(255,255,255,0.18)';
            h.style.boxShadow = '0 8px 18px rgba(0,0,0,0.35)';
            h.style.pointerEvents = 'auto';
            h.style.zIndex = '6';
            h.style.display = 'none';
            h.style.cursor = (dir === 'nw' || dir === 'se') ? 'nwse-resize' : 'nesw-resize';
            h.style.touchAction = 'none';
            Object.assign(h.style, css || {});
            try {
                h.dataset.elPos = '0';
                h.dataset.stop = '1';
                h.dataset.actionPointerdown = 'call';
                h.dataset.fnPointerdown = 'floatingResizeStart';
                h.dataset.argsPointerdown = JSON.stringify([dir]);
                h.dataset.passElPointerdown = '1';
                h.dataset.passEventPointerdown = '1';
                h.dataset.actionPointermove = 'call';
                h.dataset.fnPointermove = 'floatingResizeMove';
                h.dataset.argsPointermove = JSON.stringify([dir]);
                h.dataset.passElPointermove = '1';
                h.dataset.passEventPointermove = '1';
                h.dataset.actionPointerup = 'call';
                h.dataset.fnPointerup = 'floatingResizeEnd';
                h.dataset.argsPointerup = JSON.stringify([dir]);
                h.dataset.passElPointerup = '1';
                h.dataset.passEventPointerup = '1';
                h.dataset.actionPointercancel = 'call';
                h.dataset.fnPointercancel = 'floatingResizeCancel';
                h.dataset.argsPointercancel = JSON.stringify([dir]);
                h.dataset.passElPointercancel = '1';
                h.dataset.passEventPointercancel = '1';
            } catch (_) {
            }
            return h;
        };
        const hNW = mkHandle('nw', { left: '10px', top: '10px' });
        const hNE = mkHandle('ne', { right: '10px', top: '10px' });
        const hSW = mkHandle('sw', { left: '10px', bottom: '10px' });
        const hSE = mkHandle('se', { right: '10px', bottom: '10px' });

        const progress = document.createElement('div');
        progress.id = 'floating_player_progress';
        progress.style.height = '6px';
        progress.style.borderRadius = '999px';
        progress.style.background = 'rgba(255,255,255,0.18)';
        progress.style.overflow = 'hidden';
        progress.style.cursor = 'pointer';
        progress.style.pointerEvents = 'auto';
        progress.style.marginBottom = '10px';

        const progressFill = document.createElement('div');
        progressFill.id = 'floating_player_progress_fill';
        progressFill.style.height = '100%';
        progressFill.style.width = '0%';
        progressFill.style.background = 'rgba(254,44,85,0.92)';
        progress.appendChild(progressFill);
        const timeRow = document.createElement('div');
        timeRow.id = 'floating_player_time';
        timeRow.style.display = 'flex';
        timeRow.style.justifyContent = 'space-between';
        timeRow.style.alignItems = 'center';
        timeRow.style.fontSize = '12px';
        timeRow.style.fontWeight = '700';
        timeRow.style.color = 'rgba(255,255,255,0.78)';
        timeRow.style.marginBottom = '8px';
        timeRow.style.pointerEvents = 'none';
        timeRow.innerHTML = `<span id="floating_time_cur">00:00</span><span id="floating_time_dur">00:00</span>`;
        try {
            progress.dataset.action = 'call';
            progress.dataset.fn = 'floatingSeek';
            progress.dataset.args = '[]';
            progress.dataset.passEvent = '1';
            progress.dataset.stop = '1';
        } catch (_) {
        }

        const controlsRow = document.createElement('div');
        controlsRow.id = 'floating_player_controls';
        controlsRow.style.display = 'flex';
        controlsRow.style.alignItems = 'center';
        controlsRow.style.justifyContent = 'space-between';

        const left = document.createElement('div');
        left.style.display = 'flex';
        left.style.alignItems = 'center';
        left.style.gap = '10px';

        const btnPlay = document.createElement('div');
        btnPlay.id = 'floating_btn_play';
        btnPlay.style.width = '34px';
        btnPlay.style.height = '34px';
        btnPlay.style.borderRadius = '999px';
        btnPlay.style.background = 'rgba(255,255,255,0.18)';
        btnPlay.style.display = 'flex';
        btnPlay.style.alignItems = 'center';
        btnPlay.style.justifyContent = 'center';
        btnPlay.style.cursor = 'pointer';
        btnPlay.style.pointerEvents = 'auto';
        btnPlay.innerHTML = '<i class="fas fa-pause" style="color:white;"></i>';
        try {
            btnPlay.dataset.action = 'call';
            btnPlay.dataset.fn = 'floatingTogglePlay';
            btnPlay.dataset.args = '[]';
            btnPlay.dataset.stop = '1';
        } catch (_) {
        }

        const btnMute = document.createElement('div');
        btnMute.id = 'floating_btn_mute';
        btnMute.style.width = '34px';
        btnMute.style.height = '34px';
        btnMute.style.borderRadius = '999px';
        btnMute.style.background = 'rgba(255,255,255,0.18)';
        btnMute.style.display = 'flex';
        btnMute.style.alignItems = 'center';
        btnMute.style.justifyContent = 'center';
        btnMute.style.cursor = 'pointer';
        btnMute.style.pointerEvents = 'auto';
        btnMute.innerHTML = '<i class="fas fa-volume-mute" style="color:white;"></i>';
        try {
            btnMute.dataset.action = 'call';
            btnMute.dataset.fn = 'floatingToggleMute';
            btnMute.dataset.args = '[]';
            btnMute.dataset.stop = '1';
        } catch (_) {
        }

        left.appendChild(btnPlay);
        left.appendChild(btnMute);

        const right = document.createElement('div');
        right.style.display = 'flex';
        right.style.alignItems = 'center';
        right.style.gap = '10px';

        const btnFs = document.createElement('div');
        btnFs.id = 'floating_btn_fullscreen';
        btnFs.style.width = '34px';
        btnFs.style.height = '34px';
        btnFs.style.borderRadius = '999px';
        btnFs.style.background = 'rgba(255,255,255,0.18)';
        btnFs.style.display = 'flex';
        btnFs.style.alignItems = 'center';
        btnFs.style.justifyContent = 'center';
        btnFs.style.cursor = 'pointer';
        btnFs.style.pointerEvents = 'auto';
        btnFs.innerHTML = '<i class="fas fa-expand" style="color:white;"></i>';
        try {
            btnFs.dataset.action = 'call';
            btnFs.dataset.fn = 'floatingToggleFullscreen';
            btnFs.dataset.args = '[]';
            btnFs.dataset.stop = '1';
        } catch (_) {
        }

        const btnSize = document.createElement('div');
        btnSize.id = 'floating_btn_size';
        btnSize.style.width = '34px';
        btnSize.style.height = '34px';
        btnSize.style.borderRadius = '999px';
        btnSize.style.background = 'rgba(255,255,255,0.18)';
        btnSize.style.display = 'flex';
        btnSize.style.alignItems = 'center';
        btnSize.style.justifyContent = 'center';
        btnSize.style.cursor = 'pointer';
        btnSize.style.pointerEvents = 'auto';
        btnSize.innerHTML = '<i class="fas fa-compress" style="color:white;"></i>';
        try {
            btnSize.dataset.action = 'call';
            btnSize.dataset.fn = 'toggleFloatingPlayerSize';
            btnSize.dataset.args = '[]';
            btnSize.dataset.stop = '1';
        } catch (_) {
        }

        const btnClose = document.createElement('div');
        btnClose.id = 'floating_btn_close';
        btnClose.style.position = 'absolute';
        btnClose.style.top = '10px';
        btnClose.style.right = '10px';
        btnClose.style.width = '34px';
        btnClose.style.height = '34px';
        btnClose.style.borderRadius = '999px';
        btnClose.style.background = 'rgba(255,255,255,0.18)';
        btnClose.style.display = 'flex';
        btnClose.style.alignItems = 'center';
        btnClose.style.justifyContent = 'center';
        btnClose.style.cursor = 'pointer';
        btnClose.style.pointerEvents = 'auto';
        btnClose.style.opacity = '0';
        btnClose.style.transition = 'opacity 0.18s';
        btnClose.style.zIndex = '7';
        btnClose.innerHTML = '<i class="fas fa-times" style="color:white;"></i>';
        try {
            btnClose.dataset.action = 'call';
            btnClose.dataset.fn = 'floatingClose';
            btnClose.dataset.args = '[]';
            btnClose.dataset.stop = '1';
            btnClose.dataset.actionPointerdown = 'call';
            btnClose.dataset.fnPointerdown = 'floatingClose';
            btnClose.dataset.argsPointerdown = '[]';
            btnClose.dataset.stopPointerdown = '1';
        } catch (_) {
        }

        right.appendChild(btnFs);
        right.appendChild(btnSize);

        controlsRow.appendChild(left);
        controlsRow.appendChild(right);
        overlay.appendChild(timeRow);
        overlay.appendChild(progress);
        overlay.appendChild(controlsRow);

        wrap.appendChild(video);
        wrap.appendChild(overlay);
        wrap.appendChild(btnClose);
        wrap.appendChild(hNW);
        wrap.appendChild(hNE);
        wrap.appendChild(hSW);
        wrap.appendChild(hSE);
        document.body.appendChild(wrap);

        try {
            let st = document.getElementById('floating_player_css');
            if (!st) {
                st = document.createElement('style');
                st.id = 'floating_player_css';
                document.head.appendChild(st);
            }
            st.textContent = '#floating_player:hover #floating_player_overlay,#floating_player:hover #floating_btn_close{opacity:1 !important;pointer-events:auto !important;}@media (hover: none){#floating_player_overlay,#floating_btn_close{opacity:1 !important;pointer-events:auto !important;}}';
        } catch (_) {
        }

        const restore = () => {
            try {
                const raw = localStorage.getItem('floating_player_rect');
                if (!raw) return;
                const r = JSON.parse(raw);
                if (!r || typeof r !== 'object') return;
                if (Number.isFinite(r.w) && Number.isFinite(r.h)) {
                    wrap.style.width = `${Math.max(240, Math.min(560, r.w))}px`;
                    wrap.style.height = `${Math.max(135, Math.min(315, r.h))}px`;
                }
                if (Number.isFinite(r.x) && Number.isFinite(r.y)) {
                    wrap.style.left = `${r.x}px`;
                    wrap.style.top = `${r.y}px`;
                    wrap.style.right = 'auto';
                    wrap.style.bottom = 'auto';
                }
            } catch (_) {
            }
        };
        restore();

        const syncMuteIcon = () => {
            const i = btnMute.querySelector('i');
            if (!i) return;
            i.className = (video.muted || video.volume === 0) ? 'fas fa-volume-mute' : 'fas fa-volume-up';
        };
        const syncPlayIcon = () => {
            const i = btnPlay.querySelector('i');
            if (!i) return;
            i.className = video.paused ? 'fas fa-play' : 'fas fa-pause';
        };
        const syncFsIcon = () => {
            const i = btnFs.querySelector('i');
            if (!i) return;
            i.className = document.fullscreenElement ? 'fas fa-compress' : 'fas fa-expand';
        };

        video.addEventListener('play', syncPlayIcon);
        video.addEventListener('pause', syncPlayIcon);
        video.addEventListener('volumechange', syncMuteIcon);
        syncPlayIcon();
        syncMuteIcon();
        document.addEventListener('fullscreenchange', syncFsIcon);
        syncFsIcon();

        const clamp = () => {
            const rect = wrap.getBoundingClientRect();
            const maxX = Math.max(0, window.innerWidth - rect.width);
            const maxY = Math.max(0, window.innerHeight - rect.height);
            const x = Math.max(0, Math.min(maxX, rect.left));
            const y = Math.max(0, Math.min(maxY, rect.top));
            wrap.style.left = `${x}px`;
            wrap.style.top = `${y}px`;
            wrap.style.right = 'auto';
            wrap.style.bottom = 'auto';
        };
        const saveRect = () => {
            try {
                const rect = wrap.getBoundingClientRect();
                localStorage.setItem('floating_player_rect', JSON.stringify({ x: rect.left, y: rect.top, w: rect.width, h: rect.height }));
            } catch (_) {
            }
        };
        wrap._floatingClamp = clamp;
        wrap._floatingSaveRect = saveRect;
        clamp();

        try {
            wrap.dataset.actionPointerdown = 'call';
            wrap.dataset.fnPointerdown = 'floatingDragStart';
            wrap.dataset.argsPointerdown = '[]';
            wrap.dataset.passEventPointerdown = '1';
            wrap.dataset.actionPointermove = 'call';
            wrap.dataset.fnPointermove = 'floatingDragMove';
            wrap.dataset.argsPointermove = '[]';
            wrap.dataset.passEventPointermove = '1';
            wrap.dataset.actionPointerup = 'call';
            wrap.dataset.fnPointerup = 'floatingDragEnd';
            wrap.dataset.argsPointerup = '[]';
            wrap.dataset.passEventPointerup = '1';
            wrap.dataset.actionPointercancel = 'call';
            wrap.dataset.fnPointercancel = 'floatingDragCancel';
            wrap.dataset.argsPointercancel = '[]';
            wrap.dataset.passEventPointercancel = '1';
        } catch (_) {
        }

        try {
            progress.dataset.actionPointerdown = 'call';
            progress.dataset.fnPointerdown = 'floatingSeekStart';
            progress.dataset.argsPointerdown = '[]';
            progress.dataset.passEventPointerdown = '1';
            progress.dataset.actionPointermove = 'call';
            progress.dataset.fnPointermove = 'floatingSeekMove';
            progress.dataset.argsPointermove = '[]';
            progress.dataset.passEventPointermove = '1';
            progress.dataset.actionPointerup = 'call';
            progress.dataset.fnPointerup = 'floatingSeekEnd';
            progress.dataset.argsPointerup = '[]';
            progress.dataset.passEventPointerup = '1';
            progress.dataset.actionPointercancel = 'call';
            progress.dataset.fnPointercancel = 'floatingSeekCancel';
            progress.dataset.argsPointercancel = '[]';
            progress.dataset.passEventPointercancel = '1';
        } catch (_) {
        }
        video.addEventListener('timeupdate', () => {
            const d = Number(video.duration || 0);
            const t = Number(video.currentTime || 0);
            if (!d || !Number.isFinite(d) || !Number.isFinite(t)) return;
            progressFill.style.width = `${Math.max(0, Math.min(100, (t / d) * 100))}%`;
            try {
                const a = document.getElementById('floating_time_cur');
                const b = document.getElementById('floating_time_dur');
                if (a) a.innerText = this.fmtTime(t);
                if (b) b.innerText = this.fmtTime(d);
            } catch (_) {
            }
        });
        video.addEventListener('loadedmetadata', () => {
            try {
                const d = Number(video.duration || 0);
                const b = document.getElementById('floating_time_dur');
                if (b) b.innerText = (d && Number.isFinite(d)) ? this.fmtTime(d) : '00:00';
            } catch (_) {
            }
        });

        return wrap;
    },

    findPostById: function(postId) {
        const pid = Number(postId || 0);
        if (!pid) return null;
        const pools = [
            this.state.recommendPosts,
            this.state.jingxuanPosts,
            this.state.profilePosts,
            this.state.searchPosts
        ];
        for (let i = 0; i < pools.length; i++) {
            const arr = Array.isArray(pools[i]) ? pools[i] : [];
            for (let j = 0; j < arr.length; j++) {
                const p = arr[j];
                if (p && Number(p.id) === pid) return p;
            }
        }
        return null;
    },

    openFloatingPlayer: async function(postId, opts = {}) {
        const pid = Number(postId || this.state.activePostId || 0);
        if (!pid) return;
        const wrap = this.ensureFloatingPlayer();
        const video = document.getElementById('floating_player_video');
        if (!wrap || !video) return;

        const srcVideo = document.getElementById(`vid-${pid}`);
        const post = this.findPostById(pid) || null;
        const src = (srcVideo && srcVideo.currentSrc) ? srcVideo.currentSrc : ((post && post.video_url) ? post.video_url : '');
        const sources = (post && window.app && typeof window.app.resolveVideoSources === 'function') ? window.app.resolveVideoSources(post) : { hls_url: '', mp4_url: '' };
        const hlsUrl = sources.hls_url || '';
        const mp4Url = sources.mp4_url || (src && !/\.m3u8(\?|#|$)/i.test(src) ? src : '');
        const hlsFallback = hlsUrl || (src && /\.m3u8(\?|#|$)/i.test(src) ? src : '');
        if (!mp4Url && !hlsFallback) return;

        const curTime = srcVideo ? Number(srcVideo.currentTime || 0) : 0;
        const wasPaused = opts && opts.forcePlay ? false : (srcVideo ? !!srcVideo.paused : false);

        this.state.floatingPostId = pid;

        if (opts && opts.preset === 'jx') {
            let ratio = 16 / 9;
            let minW = 360;
            let minH = 202;
            try {
                if (opts && opts.anchorEl && opts.anchorEl.getBoundingClientRect) {
                    const ar = opts.anchorEl.getBoundingClientRect();
                    const aw = Math.round(Number(ar.width || 0));
                    const ah = Math.round(Number(ar.height || 0));
                    if (aw > 120 && ah > 120) {
                        minW = aw;
                        minH = ah;
                        ratio = aw / ah;
                    }
                }
            } catch (_) {
            }
            const headerH = (() => {
                try {
                    const v = getComputedStyle(document.documentElement).getPropertyValue('--header-height');
                    const n = parseFloat(String(v || '').replace('px', '').trim());
                    return Number.isFinite(n) ? n : 56;
                } catch (_) {
                    return 56;
                }
            })();

            const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
            const maxW = Math.max(240, Math.min(window.innerWidth - 24, 720));
            const maxH = Math.max(135, Math.min(window.innerHeight - headerH - 24, 405));
            const baseW = clamp(minW, 240, maxW);
            let w = baseW;
            let h = w / ratio;
            if (h > maxH) {
                h = maxH;
                w = h * ratio;
            }
            if (h < 135) {
                h = 135;
                w = h * ratio;
            }
            wrap.style.width = `${w}px`;
            wrap.style.height = `${h}px`;
            wrap.dataset.jxMinW = String(w);
            wrap.dataset.jxMinH = String(h);
            wrap.dataset.jxMaxW = String(maxW);
            wrap.dataset.jxMaxH = String(maxH);
            try {
                wrap.dataset.resizeEnabled = '1';
                wrap.dataset.noPersist = '1';
                const hs = wrap.querySelectorAll('.floating-resize-handle');
                Array.from(hs).forEach((x) => { try { x.style.display = 'block'; } catch (_) {} });
            } catch (_) {
            }
        } else {
            try {
                wrap.dataset.resizeEnabled = '0';
                wrap.dataset.noPersist = '0';
                const hs = wrap.querySelectorAll('.floating-resize-handle');
                Array.from(hs).forEach((x) => { try { x.style.display = 'none'; } catch (_) {} });
            } catch (_) {
            }
        }

        wrap.style.display = 'block';
        if (opts && opts.preset === 'jx' && opts.anchorEl && opts.anchorEl.getBoundingClientRect) {
            const r = opts.anchorEl.getBoundingClientRect();
            const bw = wrap.getBoundingClientRect().width;
            const bh = wrap.getBoundingClientRect().height;
            const headerH = (() => {
                try {
                    const v = getComputedStyle(document.documentElement).getPropertyValue('--header-height');
                    const n = parseFloat(String(v || '').replace('px', '').trim());
                    return Number.isFinite(n) ? n : 56;
                } catch (_) {
                    return 56;
                }
            })();
            const pad = 12;
            const anchorCx = Number(r.left || 0) + Number(r.width || 0) / 2;
            const preferRight = anchorCx < (window.innerWidth / 2);
            const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
            const leftA = clamp(preferRight ? (window.innerWidth - bw - pad) : pad, pad, Math.max(pad, window.innerWidth - bw - pad));
            const leftB = clamp(!preferRight ? (window.innerWidth - bw - pad) : pad, pad, Math.max(pad, window.innerWidth - bw - pad));
            const top0 = clamp(headerH + pad, pad, Math.max(pad, window.innerHeight - bh - pad));
            const overlap = (wr, ar) => {
                const ox = Math.max(0, Math.min(wr.right, ar.right) - Math.max(wr.left, ar.left));
                const oy = Math.max(0, Math.min(wr.bottom, ar.bottom) - Math.max(wr.top, ar.top));
                return ox * oy;
            };
            const place = (left, top) => {
                wrap.style.left = `${left}px`;
                wrap.style.top = `${top}px`;
                wrap.style.right = 'auto';
                wrap.style.bottom = 'auto';
            };
            place(leftA, top0);
            let wr = wrap.getBoundingClientRect();
            if (overlap(wr, r) > 1) {
                place(leftB, top0);
                wr = wrap.getBoundingClientRect();
                if (overlap(wr, r) > 1) {
                    const top1 = clamp(Number(r.bottom || 0) + pad, pad, Math.max(pad, window.innerHeight - bh - pad));
                    place(leftB, top1);
                }
            }
        } else if (opts && opts.preset === 'jx') {
            const headerH = (() => {
                try {
                    const v = getComputedStyle(document.documentElement).getPropertyValue('--header-height');
                    const n = parseFloat(String(v || '').replace('px', '').trim());
                    return Number.isFinite(n) ? n : 56;
                } catch (_) {
                    return 56;
                }
            })();
            const sidebarW = (() => {
                try {
                    const v = getComputedStyle(document.documentElement).getPropertyValue('--sidebar-width');
                    const n = parseFloat(String(v || '').replace('px', '').trim());
                    return Number.isFinite(n) ? n : 240;
                } catch (_) {
                    return 240;
                }
            })();
            wrap.style.left = `${Math.max(10, sidebarW + 16)}px`;
            wrap.style.top = `${Math.max(10, headerH + 12)}px`;
            wrap.style.right = 'auto';
            wrap.style.bottom = 'auto';
        } else if (opts && opts.anchorEl && opts.anchorEl.getBoundingClientRect) {
            const r = opts.anchorEl.getBoundingClientRect();
            const bw = wrap.getBoundingClientRect().width;
            const bh = wrap.getBoundingClientRect().height;
            const gap = 12;
            const roomRight = window.innerWidth - r.right;
            const left = (roomRight >= bw + gap) ? (r.right + gap) : (r.left - bw - gap);
            const top = Math.max(10, Math.min(window.innerHeight - bh - 10, r.top));
            wrap.style.left = `${Math.max(10, left)}px`;
            wrap.style.top = `${top}px`;
            wrap.style.right = 'auto';
            wrap.style.bottom = 'auto';
        }
        if (wrap._floatingClamp) wrap._floatingClamp();

        try {
            if (post && post.cover_url) video.poster = String(post.cover_url);
            else video.removeAttribute('poster');
        } catch (_) {
        }

        try {
            if (window.app && typeof window.app.applyPreferredVideoSource === 'function') {
                await window.app.applyPreferredVideoSource(video, { hls_url: hlsFallback, mp4_url: mp4Url, video_url: (post && post.video_url) ? post.video_url : src }, { autoPlay: !wasPaused });
            } else {
                const target = hlsFallback || mp4Url;
                if (target && video.src !== target) video.src = target;
            }
        } catch (_) {
            const target = hlsFallback || mp4Url;
            if (target && video.src !== target) video.src = target;
        }

        video.muted = !!this.state.isMuted;
        video.volume = Number.isFinite(Number(this.state.globalVolume)) ? Number(this.state.globalVolume) : 0.5;
        try { if (typeof this.pauseAllVideosExcept === 'function') this.pauseAllVideosExcept(video); } catch (_) {}

        const seekAndPlay = async () => {
            try {
                if (Number.isFinite(curTime) && curTime > 0) video.currentTime = curTime;
            } catch (_) {
            }
            try {
                if (!wasPaused) await video.play();
            } catch (_) {
            }
        };

        if (video.readyState >= 2) await seekAndPlay();
        else {
            video.onloadedmetadata = () => {
                video.onloadedmetadata = null;
                seekAndPlay();
            };
        }
    },

    floatingTogglePlay: function() {
        const video = document.getElementById('floating_player_video');
        const btn = document.getElementById('floating_btn_play');
        const icon = btn ? btn.querySelector('i') : null;
        if (!video) return;
        try {
            if (video.paused) {
                const p = video.play();
                if (p && typeof p.catch === 'function') p.catch(() => {});
            } else {
                video.pause();
            }
        } catch (_) {
        }
        try { if (icon) icon.className = video.paused ? 'fas fa-play' : 'fas fa-pause'; } catch (_) {}
    },

    floatingToggleMute: function() {
        const video = document.getElementById('floating_player_video');
        const btn = document.getElementById('floating_btn_mute');
        const icon = btn ? btn.querySelector('i') : null;
        if (!video) return;
        try {
            if (video.muted || video.volume === 0) {
                video.muted = false;
                if ((this.state.globalVolume || 0) === 0) this.state.globalVolume = 0.5;
                video.volume = Number(this.state.globalVolume || 0.5);
            } else {
                video.muted = true;
            }
            this.state.isMuted = !!video.muted;
            localStorage.setItem('is_muted', this.state.isMuted ? '1' : '0');
            localStorage.setItem('global_volume', String(this.state.globalVolume || 0.5));
        } catch (_) {
        }
        try { if (icon) icon.className = (video.muted || video.volume === 0) ? 'fas fa-volume-mute' : 'fas fa-volume-up'; } catch (_) {}
    },

    floatingToggleFullscreen: function() {
        const wrap = document.getElementById('floating_player');
        const btn = document.getElementById('floating_btn_fullscreen');
        const icon = btn ? btn.querySelector('i') : null;
        if (!wrap) return;
        try {
            if (document.fullscreenElement) {
                document.exitFullscreen().catch(() => {});
            } else if (wrap.requestFullscreen) {
                wrap.requestFullscreen().catch(() => {});
            }
        } catch (_) {
        }
        try { if (icon) icon.className = document.fullscreenElement ? 'fas fa-compress' : 'fas fa-expand'; } catch (_) {}
    },

    floatingClick: function() {
        return;
    },

    floatingDblClick: function() {
        try { this.floatingTogglePlay(); } catch (_) {}
    },

    floatingSeek: function(ev) {
        const video = document.getElementById('floating_player_video');
        const prog = document.getElementById('floating_player_progress');
        if (!video || !prog || !ev) return;
        try {
            const rect = prog.getBoundingClientRect();
            const pct = Math.max(0, Math.min(1, (Number(ev.clientX || 0) - rect.left) / (rect.width || 1)));
            const dur = Number(video.duration || 0);
            if (Number.isFinite(dur) && dur > 0) video.currentTime = pct * dur;
        } catch (_) {
        }
    },

    clampFloatingPlayer: function() {
        const wrap = document.getElementById('floating_player');
        if (!wrap || wrap.style.display === 'none') return;
        try { if (wrap._floatingClamp) wrap._floatingClamp(); } catch (_) {}
    },

    floatingDragStart: function(ev) {
        if (!ev) return;
        const wrap = document.getElementById('floating_player');
        if (!wrap || wrap.style.display === 'none') return;
        const t = ev.target;
        if (t && t.closest && (t.closest('#floating_player_controls') || t.closest('#floating_player_progress') || t.closest('.floating-resize-handle'))) return;
        try { wrap.setPointerCapture(ev.pointerId); } catch (_) {}
        const rect = wrap.getBoundingClientRect();
        this._floatingDrag = {
            active: true,
            pointerId: ev.pointerId,
            startX: Number(ev.clientX || 0),
            startY: Number(ev.clientY || 0),
            startLeft: Number(rect.left || 0),
            startTop: Number(rect.top || 0)
        };
        try { wrap.style.cursor = 'grabbing'; } catch (_) {}
    },

    floatingDragMove: function(ev) {
        const s = this._floatingDrag;
        if (!ev || !s || !s.active) return;
        if (Number(s.pointerId) !== Number(ev.pointerId)) return;
        const wrap = document.getElementById('floating_player');
        if (!wrap) return;
        const dx = Number(ev.clientX || 0) - Number(s.startX || 0);
        const dy = Number(ev.clientY || 0) - Number(s.startY || 0);
        try {
            wrap.style.left = `${Number(s.startLeft || 0) + dx}px`;
            wrap.style.top = `${Number(s.startTop || 0) + dy}px`;
            wrap.style.right = 'auto';
            wrap.style.bottom = 'auto';
        } catch (_) {
        }
        try { if (wrap._floatingClamp) wrap._floatingClamp(); } catch (_) {}
    },

    floatingDragEnd: function(ev) {
        const s = this._floatingDrag;
        if (!ev || !s || !s.active) return;
        if (Number(s.pointerId) !== Number(ev.pointerId)) return;
        const wrap = document.getElementById('floating_player');
        if (!wrap) return;
        s.active = false;
        try { wrap.style.cursor = 'grab'; } catch (_) {}
        try { if (wrap._floatingClamp) wrap._floatingClamp(); } catch (_) {}
        try {
            if (String(wrap.dataset.noPersist || '') !== '1' && wrap._floatingSaveRect) wrap._floatingSaveRect();
        } catch (_) {}
    },

    floatingDragCancel: function(ev) {
        const s = this._floatingDrag;
        if (!s || !s.active) return;
        const wrap = document.getElementById('floating_player');
        s.active = false;
        try { if (wrap) wrap.style.cursor = 'grab'; } catch (_) {}
        try { if (wrap && wrap._floatingClamp) wrap._floatingClamp(); } catch (_) {}
    },

    floatingResizeStart: function(handleEl, dir, ev) {
        if (!handleEl || !ev) return;
        const wrap = document.getElementById('floating_player');
        if (!wrap || String(wrap.dataset.resizeEnabled || '') !== '1') return;
        try { handleEl.setPointerCapture(ev.pointerId); } catch (_) {}
        const rect = wrap.getBoundingClientRect();
        const minW = Number(wrap.dataset.jxMinW || 0) || 360;
        const minH = Number(wrap.dataset.jxMinH || 0) || 202;
        const maxW = Number(wrap.dataset.jxMaxW || 0) || (window.innerWidth - 20);
        const maxH = Number(wrap.dataset.jxMaxH || 0) || (window.innerHeight - 20);
        this._floatingResize = {
            active: true,
            pointerId: ev.pointerId,
            dir: String(dir || ''),
            startX: Number(ev.clientX || 0),
            startY: Number(ev.clientY || 0),
            startLeft: Number(rect.left || 0),
            startTop: Number(rect.top || 0),
            startW: Number(rect.width || 0),
            startH: Number(rect.height || 0),
            ratio: (Number(rect.width || 0) && Number(rect.height || 0)) ? (Number(rect.width || 0) / Number(rect.height || 1)) : (16 / 9),
            minW,
            minH,
            maxW,
            maxH,
        };
        try { wrap.style.cursor = 'nwse-resize'; } catch (_) {}
    },

    floatingResizeMove: function(handleEl, dir, ev) {
        const s = this._floatingResize;
        if (!ev || !s || !s.active) return;
        if (Number(s.pointerId) !== Number(ev.pointerId)) return;
        const wrap = document.getElementById('floating_player');
        if (!wrap) return;
        const d = String(s.dir || dir || '');
        const sx = d.includes('e') ? 1 : -1;
        const sy = d.includes('s') ? 1 : -1;
        const dx = Number(ev.clientX || 0) - Number(s.startX || 0);
        const dy = Number(ev.clientY || 0) - Number(s.startY || 0);
        const deltaW = sx * dx;
        const deltaW2 = sy * dy * Number(s.ratio || (16 / 9));
        const base = Math.abs(deltaW) >= Math.abs(deltaW2) ? deltaW : deltaW2;
        let newW = Number(s.startW || 0) + base;
        if (!Number.isFinite(newW) || newW <= 0) return;
        newW = Math.max(Number(s.minW || 0), Math.min(Number(s.maxW || 0), newW));
        let newH = newW / Number(s.ratio || (16 / 9));
        newH = Math.max(Number(s.minH || 0), Math.min(Number(s.maxH || 0), newH));
        newW = newH * Number(s.ratio || (16 / 9));
        try {
            wrap.style.width = `${newW}px`;
            wrap.style.height = `${newH}px`;
        } catch (_) {
        }
        try {
            if (d.includes('w')) {
                wrap.style.left = `${Number(s.startLeft || 0) + (Number(s.startW || 0) - newW)}px`;
                wrap.style.right = 'auto';
            }
            if (d.includes('n')) {
                wrap.style.top = `${Number(s.startTop || 0) + (Number(s.startH || 0) - newH)}px`;
                wrap.style.bottom = 'auto';
            }
        } catch (_) {
        }
        try { if (wrap._floatingClamp) wrap._floatingClamp(); } catch (_) {}
    },

    floatingResizeEnd: function(handleEl, dir, ev) {
        const s = this._floatingResize;
        if (!ev || !s || !s.active) return;
        if (Number(s.pointerId) !== Number(ev.pointerId)) return;
        const wrap = document.getElementById('floating_player');
        s.active = false;
        try { if (wrap) wrap.style.cursor = 'grab'; } catch (_) {}
        try { if (wrap && wrap._floatingClamp) wrap._floatingClamp(); } catch (_) {}
        try {
            if (wrap && String(wrap.dataset.noPersist || '') !== '1' && wrap._floatingSaveRect) wrap._floatingSaveRect();
        } catch (_) {}
    },

    floatingResizeCancel: function(handleEl, dir, ev) {
        const s = this._floatingResize;
        if (!s || !s.active) return;
        const wrap = document.getElementById('floating_player');
        s.active = false;
        try { if (wrap) wrap.style.cursor = 'grab'; } catch (_) {}
        try { if (wrap && wrap._floatingClamp) wrap._floatingClamp(); } catch (_) {}
    },

    floatingSeekStart: function(ev) {
        if (!ev) return;
        const prog = document.getElementById('floating_player_progress');
        if (!prog) return;
        try { prog.setPointerCapture(ev.pointerId); } catch (_) {}
        this._floatingSeek = { active: true, pointerId: ev.pointerId };
        this.floatingSeek(ev);
    },

    floatingSeekMove: function(ev) {
        const s = this._floatingSeek;
        if (!ev || !s || !s.active) return;
        if (Number(s.pointerId) !== Number(ev.pointerId)) return;
        this.floatingSeek(ev);
    },

    floatingSeekEnd: function(ev) {
        const s = this._floatingSeek;
        if (!ev || !s || !s.active) return;
        if (Number(s.pointerId) !== Number(ev.pointerId)) return;
        s.active = false;
        this.floatingSeek(ev);
    },

    floatingSeekCancel: function(ev) {
        const s = this._floatingSeek;
        if (!s) return;
        s.active = false;
    },

    floatingClose: function() {
        try { this.closeFloatingPlayer(); } catch (_) {}
    },

    closeFloatingPlayer: function() {
        const wrap = document.getElementById('floating_player');
        const video = document.getElementById('floating_player_video');
        if (video) {
            try { video.pause(); } catch (_) {}
            try { video.removeAttribute('src'); video.load(); } catch (_) {}
        }
        if (wrap) wrap.style.display = 'none';
        this.state.floatingPostId = null;
    },

    toggleFloatingPlayerSize: function() {
        const wrap = document.getElementById('floating_player');
        if (!wrap) return;
        const btn = document.getElementById('floating_btn_size');
        const icon = btn ? btn.querySelector('i') : null;
        const curW = wrap.getBoundingClientRect().width;
        const small = curW >= 600;
        const nextW = small ? 520 : 640;
        const nextH = small ? 292 : 360;
        wrap.style.width = `${nextW}px`;
        wrap.style.height = `${nextH}px`;
        if (icon) icon.className = small ? 'fas fa-expand' : 'fas fa-compress';
        if (wrap._floatingClamp) wrap._floatingClamp();
        if (String(wrap.dataset.noPersist || '') !== '1' && wrap._floatingSaveRect) wrap._floatingSaveRect();
    }
});
