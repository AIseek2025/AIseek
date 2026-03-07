Object.assign(window.app, {
    _prefetchKey: function(url) {
        const s = String(url || '');
        let h = 2166136261;
        for (let i = 0; i < s.length; i++) {
            h ^= s.charCodeAt(i);
            h = Math.imul(h, 16777619);
        }
        return 'p' + (h >>> 0).toString(16);
    },

    _ensurePreloadImageLink: function(url) {
        const u = (typeof url === 'string' ? url : '').trim();
        if (!u) return;
        const k = this._prefetchKey(u);
        if (document.getElementById(k)) return;
        try {
            const link = document.createElement('link');
            link.id = k;
            link.rel = 'preload';
            link.as = 'image';
            link.href = u;
            link.crossOrigin = 'anonymous';
            try { link.fetchPriority = 'high'; } catch (_) {}
            document.head.appendChild(link);
        } catch (_) {
        }
    },

    prewarmCoverUrl: function(url) {
        const u = (typeof url === 'string' ? url : '').trim();
        if (!u) return;
        try {
            this._ensurePreloadImageLink(u);
            const img = new Image();
            img.decoding = 'async';
            img.loading = 'eager';
            try { img.fetchPriority = 'high'; } catch (_) {}
            img.src = u;
            try {
                if (typeof img.decode === 'function') {
                    img.decode().catch(() => {});
                }
            } catch (_) {
            }
        } catch (_) {
        }
    },

    prewarmHlsUrl: function(url) {
        const u = (typeof url === 'string' ? url : '').trim();
        if (!u || u.indexOf('.m3u8') === -1) return;
        try {
            this.netPrefetch(u);
        } catch (_) {
        }
        try {
            const base = u.replace(/master\.m3u8(\?.*)?$/i, '');
            const v2 = base + 'v2/index.m3u8';
            this.netPrefetch(v2);
        } catch (_) {
        }
    },

    _scheduleIdle: function(fn) {
        try {
            if (typeof requestIdleCallback === 'function') return requestIdleCallback(fn, { timeout: 350 });
        } catch (_) {
        }
        return setTimeout(() => { try { fn(); } catch (_) {} }, 30);
    },

    _prewarmSlideMedia: function(slide) {
        try {
            const v = slide ? slide.querySelector('video') : null;
            if (!v) return;
            const hls = v.dataset ? String(v.dataset.hls || '') : '';
            const poster = (v.getAttribute && v.getAttribute('poster')) ? String(v.getAttribute('poster') || '') : '';
            if (poster) this.prewarmCoverUrl(poster);
            if (hls) this.prewarmHlsUrl(hls);
        } catch (_) {
        }
    },

    resolveVideoSources: function(post) {
        const p = post || {};
        const hls = (typeof p.hls_url === 'string' && p.hls_url) ? p.hls_url : '';
        const mp4 = (typeof p.mp4_url === 'string' && p.mp4_url) ? p.mp4_url : '';
        const v = (typeof p.video_url === 'string' && p.video_url) ? p.video_url : '';
        const hls2 = (!hls && /\.m3u8(\?|#|$)/i.test(v)) ? v : hls;
        const mp42 = mp4 || ((!hls2 && v) ? v : '');
        return { hls_url: hls2, mp4_url: mp42 };
    },

    applyPreferredVideoSource: async function(video, post, opts = {}) {
        const v = video;
        if (!v) return;
        const sources = this.resolveVideoSources(post);
        const hlsUrl = sources.hls_url || '';
        const mp4Url = sources.mp4_url || '';
        const canNativeHls = !!(hlsUrl && v.canPlayType && v.canPlayType('application/vnd.apple.mpegurl'));
        const target = (hlsUrl && canNativeHls) ? hlsUrl : (hlsUrl || mp4Url || '');
        if (!target) return;

        const key = `srcBound`;
        if (v.dataset && v.dataset[key] !== '1') {
            if (v.dataset) v.dataset[key] = '1';
            v.addEventListener('error', async () => {
                try {
                    const cur = (v.currentSrc || v.src || '').trim();
                    if (hlsUrl && mp4Url && cur && cur.indexOf('.m3u8') !== -1) {
                        try {
                            const h = v._aiseekHls;
                            if (h && typeof h.destroy === 'function') {
                                h.destroy();
                            }
                        } catch (_) {}
                        v.src = mp4Url;
                        try { v.load(); } catch (_) {}
                        try {
                            if (opts && opts.autoPlay) await v.play();
                        } catch (_) {}
                    }
                } catch (_) {}
            });
        }

        if (hlsUrl && !canNativeHls) {
            try {
                const Hls = window.Hls;
                if (Hls && typeof Hls.isSupported === 'function' && Hls.isSupported()) {
                    try {
                        const prev = v._aiseekHls;
                        if (prev && typeof prev.destroy === 'function') prev.destroy();
                    } catch (_) {}
                    const hls = new Hls({ enableWorker: true, lowLatencyMode: false });
                    v._aiseekHls = hls;
                    hls.on(Hls.Events.ERROR, async (_, data) => {
                        try {
                            if (data && data.fatal && mp4Url) {
                                try { hls.destroy(); } catch (_) {}
                                try { v._aiseekHls = null; } catch (_) {}
                                v.src = mp4Url;
                                try { v.load(); } catch (_) {}
                                try { if (opts && opts.autoPlay) await v.play(); } catch (_) {}
                            }
                        } catch (_) {}
                    });
                    hls.loadSource(hlsUrl);
                    hls.attachMedia(v);
                    return;
                }
            } catch (_) {
            }
        }

        try {
            const prev = v._aiseekHls;
            if (prev && typeof prev.destroy === 'function') prev.destroy();
            v._aiseekHls = null;
        } catch (_) {}
        if ((v.currentSrc || v.src || '') !== target) v.src = target;
    },
    ensureRecommendMediaCrop: function(video) {
        const v = video;
        if (!v || !v.closest) return;
        if (!v.closest('#page-recommend')) return;
        if (v.dataset && v.dataset.cropBound === '1') return;
        if (v.dataset) v.dataset.cropBound = '1';

        const tryApply = () => {
            try { this.applyRecommendMediaCrop(v); } catch (_) {}
        };

        let rafTries = 0;
        const rafLoop = () => {
            rafTries += 1;
            tryApply();
            const w = Number(v.videoWidth || 0);
            const h = Number(v.videoHeight || 0);
            if ((w && h) || rafTries >= 30) return;
            requestAnimationFrame(rafLoop);
        };
        requestAnimationFrame(rafLoop);

        v.addEventListener('loadedmetadata', tryApply, { once: true });
        v.addEventListener('loadeddata', tryApply, { once: true });
        v.addEventListener('resize', tryApply);
    },

    applyRecommendMediaCrop: function(video) {
        const v = video;
        if (!v) return;
        const container = v.closest ? v.closest('.video-player-container') : null;
        if (!container) return;
        const w = Number(v.videoWidth || 0);
        const h = Number(v.videoHeight || 0);
        if (!w || !h) return;
        const ratio = w / h;
        if (ratio > 1.1) {
            container.style.setProperty('--media-pos-x', '56%');
        } else {
            container.style.setProperty('--media-pos-x', '50%');
        }
    },

    loadRecommend: async function() {
        const container = document.getElementById('page-recommend');
        container.innerHTML = '<div style="color:#888; display:flex; justify-content:center; align-items:center; height:100%;">加载中...</div>';

        try {
            let url = '/api/v1/posts/feed';
            const params = [];
            if (this.state.user) params.push(`user_id=${this.state.user.id}`);
            params.push('limit=20');
            if (params.length > 0) url += '?' + params.join('&');
            const res = await this.apiRequest('GET', url, undefined, { cancel_key: 'feed:recommend', dedupe_key: url });
            const nextCursor = res.headers ? res.headers.get('x-next-cursor') : null;
            const posts = await res.json();
            this.state.recommendPosts = posts;
            this.state.recommendCursor = nextCursor || null;
            this.renderRecommendPosts(posts);

            try {
                if (window.appEmit) window.appEmit('feed:loaded', { source: 'recommend', count: Array.isArray(posts) ? posts.length : 0 });
            } catch (_) {
            }
        } catch(e) {
            container.innerHTML = '<div style="color:#888; display:flex; justify-content:center; align-items:center; height:100%;">加载失败</div>';
        }
    },

    loadMoreRecommend: async function() {
        if (this.state.recommendLoadingMore) return;
        if (!this.state.recommendCursor) return;
        const container = document.getElementById('page-recommend');
        if (!container) return;
        this.state.recommendLoadingMore = true;

        try {
            let url = '/api/v1/posts/feed';
            const params = [];
            if (this.state.user) params.push(`user_id=${this.state.user.id}`);
            params.push('limit=20');
            params.push(`cursor=${encodeURIComponent(this.state.recommendCursor)}`);
            url += '?' + params.join('&');

            const res = await this.apiRequest('GET', url, undefined, { cancel_key: 'feed:recommend_more', dedupe_key: url });
            const nextCursor = res.headers ? res.headers.get('x-next-cursor') : null;
            const posts = await res.json();
            const arr = Array.isArray(posts) ? posts : [];

            if (arr.length > 0) {
                const prev = Array.isArray(this.state.recommendPosts) ? this.state.recommendPosts : [];
                this.state.recommendPosts = prev.concat(arr);
                this.appendRecommendPosts(arr);
            }
            this.state.recommendCursor = nextCursor || null;

            try {
                if (window.appEmit) window.appEmit('feed:loaded', { source: 'recommend_more', count: arr.length });
            } catch (_) {
            }
        } catch (_) {
        } finally {
            this.state.recommendLoadingMore = false;
        }
    },

    appendRecommendPosts: function(posts) {
        const container = document.getElementById('page-recommend');
        if (!container) return;
        const arr = Array.isArray(posts) ? posts : [];
        arr.forEach(post => {
            if (!post || !post.id) return;
            if (document.getElementById(`slide-${post.id}`)) return;
            const slide = document.createElement('div');
            slide.className = 'video-slide';
            slide.id = `slide-${post.id}`;
            slide.dataset.postId = String(post.id);
            slide.innerHTML = this.renderVideoSlide(post);
            container.appendChild(slide);
            this.bindVideoEvents(slide, post);
            if (this._recommendObserver) {
                try { this._recommendObserver.observe(slide); } catch (_) {}
            }
        });
    },

    renderVideoSlide: function(post, opts = {}) {
        const showNavArrows = opts.showNavArrows !== false;
        const status = (post && post.status) ? String(post.status) : 'done';
        const isReady = status === 'done';
        const isVideo = (post.post_type === 'video') || (post.video_url && !(/\.(jpg|jpeg|png|gif|webp)(\?|#|$)/i.test(post.video_url)));
        const vidId = `vid-${post.id}`;
        
        const hlsUrl = (post && (post.hls_url || (post.video_url && /\.m3u8(\?|#|$)/i.test(post.video_url) ? post.video_url : ''))) || '';
        const mp4Url = (post && (post.mp4_url || (!hlsUrl ? post.video_url : ''))) || '';
        const poster = (post && post.cover_url) ? String(post.cover_url) : `/api/v1/media/post-thumb/${encodeURIComponent(String(post.id))}?v=${Date.now()}`;
        const posterAttr = poster ? ` poster="${poster}"` : '';
        const vw = Number((post && (post.video_width || post.width)) || 0);
        const vh = Number((post && (post.video_height || post.height)) || 0);
        const arAttr = (vw > 0 && vh > 0) ? ` style="aspect-ratio:${vw}/${vh};"` : '';
        const canPlayNow = isVideo && !!(hlsUrl || mp4Url);
        const media = (isVideo && (isReady || canPlayNow))
            ? `
                <video id="${vidId}" data-hls="${hlsUrl}" data-mp4="${mp4Url}"${posterAttr}${arAttr} loop playsinline webkit-playsinline muted autoplay preload="metadata"></video>
                ${isReady ? '' : `
                    <div style="position:absolute; inset:0; background:linear-gradient(to top, rgba(0,0,0,0.62), rgba(0,0,0,0.10) 55%);"></div>
                    <div style="position:absolute; left:16px; right:16px; bottom:18px; color:rgba(255,255,255,0.90); font-weight:850; font-size:14px;">
                        发布中
                    </div>
                `}
            `
            : (isVideo
                ? `
                    <div style="position:absolute; inset:0; background:#000;"></div>
                    ${poster ? `<img src="${poster}" style="position:absolute; inset:0; width:100%; height:100%; object-fit:cover; opacity:0.9;">` : ''}
                    <div style="position:absolute; inset:0; background:linear-gradient(to top, rgba(0,0,0,0.70), rgba(0,0,0,0.12) 55%);"></div>
                    <div style="position:absolute; left:16px; right:16px; bottom:18px; color:rgba(255,255,255,0.88); font-weight:800; font-size:14px;">
                        发布中
                    </div>
                `
                : `<img src="${post.images && post.images.length > 0 ? post.images[0] : (post.video_url || '')}">`);
        
        const avatar = post.user_avatar || '/static/img/default_avatar.svg';
        const nickname = post.user_nickname || '用户' + post.user_id;
        const desc = this.formatPostDesc(post.content_text || post.title || '');

        // Check if I am following this user
        // Note: The feed API needs to return 'is_following'. If not, we might need to check separately or default to show +
        const isOwner = (!!this.state.user && Number(this.state.user.id || 0) === Number(post.user_id || 0));
        const showFollow = (!this.state.user || (this.state.user.id !== post.user_id && !post.is_following));
        const canDownload = !!(post && post.download_enabled) || isOwner;
        const downloadBtn = canDownload ? `
                        <div class="action-item" data-action="call" data-fn="downloadPost" data-args="[${post.id}]" data-stop="1">
                            <div class="action-icon"><i class="fas fa-download"></i></div>
                            <div class="action-text">下载</div>
                        </div>
        ` : '';

        const navArrows = showNavArrows ? `
            <div class="video-nav-arrows">
                <div class="nav-arrow" data-action="call" data-fn="playPrev" data-args="[${post.id}]" data-stop="1"><i class="fas fa-chevron-up"></i></div>
                <div class="nav-arrow" data-action="call" data-fn="playNext" data-args="[${post.id}]" data-stop="1"><i class="fas fa-chevron-down"></i></div>
            </div>
        ` : '';

        return `
            <div class="video-stage ${showNavArrows ? '' : 'no-nav-arrows'}" id="stage-${post.id}">
                <div class="video-player-container" data-action="stageClick" data-action-dblclick="stageDblClick" data-post-id="${post.id}">
                    ${media}
                
                    <!-- Right Actions -->
                    <div class="video-actions">
                        <div class="action-item avatar-action" data-action="call" data-fn="viewUserProfile" data-args="[${post.user_id}]" data-stop="1">
                            <img src="${avatar}">
                            <div class="follow-plus" data-user-id="${post.user_id}" style="${showFollow ? '' : 'display:none;'}" data-action="call" data-fn="toggleFollow" data-args="[${post.user_id}]" data-pass-el="1" data-stop="1"><i class="fas fa-plus"></i></div>
                        </div>
                        <div class="action-item" data-action="call" data-fn="toggleLike" data-args="[${post.id}]" data-pass-el="1" data-stop="1">
                            <div class="action-icon"><i class="fas fa-heart" style="color:${post.is_liked ? '#fe2c55' : 'var(--text-color)'}"></i></div>
                            <div class="action-text">${post.likes_count || 0}</div>
                        </div>
                        <div class="action-item" data-action="call" data-fn="openComments" data-args="[${post.id}]" data-pass-el="1" data-stop="1">
                            <div class="action-icon"><i class="fas fa-comment-dots"></i></div>
                            <div class="action-text">${post.comments_count || 0}</div>
                        </div>
                        <div class="action-item" data-action="call" data-fn="toggleFavorite" data-args="[${post.id}]" data-pass-el="1" data-stop="1">
                        <div class="action-icon"><i class="${post.is_favorited ? 'fas' : 'far'} fa-star" style="color:${post.is_favorited ? '#ffb800' : 'var(--text-color)'}"></i></div>
                        <div class="action-text">${Number.isFinite(Number(post.favorites_count)) ? Number(post.favorites_count) : 0}</div>
                        </div>
                        <div class="action-item" data-action="call" data-fn="openFloatingPlayer" data-args="[${post.id}]" data-stop="1">
                            <div class="action-icon"><i class="fas fa-window-restore"></i></div>
                            <div class="action-text">小窗</div>
                        </div>
                        <div class="action-item" data-action="call" data-fn="toggleRepost" data-args="[${post.id}]" data-pass-el="1" data-stop="1">
                            <div class="action-icon"><i class="fas fa-retweet" style="color:${post.is_reposted ? '#00d4ff' : 'var(--text-color)'}"></i></div>
                            <div class="action-text">${post.shares_count || 0}</div>
                        </div>
                        <div class="action-item" data-action="call" data-fn="sharePost" data-args="[${post.id}]" data-stop="1">
                            <div class="action-icon"><i class="fas fa-share"></i></div>
                            <div class="action-text">分享</div>
                        </div>
                        ${downloadBtn}
                    </div>

                    <!-- Info -->
                    <div class="video-info-overlay">
                        <div class="video-author" data-action="call" data-fn="viewUserProfile" data-args="[${post.user_id}]" data-stop="1">@${nickname}</div>
                        <div class="video-desc">${desc}</div>
                        <div class="video-music"><i class="fas fa-music"></i> 原声 - ${nickname}</div>
                    </div>

                    <!-- Controls Bar -->
                    <div class="video-controls-bar" data-action="stop" data-stop="1">
                        <div class="v-progress-container" id="prog-c-${post.id}" data-action="call" data-fn="seekByPostId" data-args="[${post.id}]" data-pass-event="1" data-stop="1" data-el-pos="0"
                             data-action-pointerdown="call" data-fn-pointerdown="seekStartByPostId" data-args-pointerdown="[${post.id}]" data-pass-el-pointerdown="1" data-pass-event-pointerdown="1"
                             data-action-pointermove="call" data-fn-pointermove="seekMoveByPostId" data-args-pointermove="[${post.id}]" data-pass-el-pointermove="1" data-pass-event-pointermove="1"
                             data-action-pointerup="call" data-fn-pointerup="seekEndByPostId" data-args-pointerup="[${post.id}]" data-pass-el-pointerup="1" data-pass-event-pointerup="1"
                             data-action-pointercancel="call" data-fn-pointercancel="seekCancelByPostId" data-args-pointercancel="[${post.id}]" data-pass-el-pointercancel="1" data-pass-event-pointercancel="1">
                            <div class="v-progress-track"></div>
                            <div class="v-progress-filled" id="prog-f-${post.id}"></div>
                        </div>
                        
                        <div class="v-controls-row">
                            <div class="v-left">
                                 <i class="fas fa-play" id="btn-play-${post.id}" data-action="call" data-fn="togglePlayByPostId" data-args="[${post.id}]" data-stop="1"></i>
                                 <span class="v-time" id="time-${post.id}">00:00 / 00:00</span>
                            </div>
                            
                            <div class="v-center">
                                 <div class="danmaku-input-box">
                                     <input id="dm-input-${post.id}" placeholder="发弹幕..." data-action-keydown="call" data-fn="sendDanmaku" data-args="[${post.id}]" data-pass-value="1" data-key-code="13">
                                 </div>
                            </div>

                            <div class="v-right">
                                 <div class="v-btn ${this.state.autoPlay?'active':''}" id="btn-lianbo-${post.id}" title="连播" data-action="call" data-fn="toggleAutoPlay" data-args="[]" data-stop="1">连播</div>
                                 <div class="v-btn ${this.state.isCleanMode?'active':''}" id="btn-clean-${post.id}" title="清屏" data-action="call" data-fn="toggleCleanMode" data-args="[]" data-stop="1">清屏</div>
                                 <div class="v-btn speed-btn">
                                     <span id="quality-txt-${post.id}">智能</span>
                                     <div class="speed-menu">
                                         <div class="speed-opt" data-action="call" data-fn="setQuality" data-args='["ultra"]' data-pass-el="1" data-el-pos="0">超高清</div>
                                         <div class="speed-opt" data-action="call" data-fn="setQuality" data-args='["hd"]' data-pass-el="1" data-el-pos="0">高清</div>
                                         <div class="speed-opt" data-action="call" data-fn="setQuality" data-args='["sd"]' data-pass-el="1" data-el-pos="0">标清</div>
                                         <div class="speed-opt active" data-action="call" data-fn="setQuality" data-args='["auto"]' data-pass-el="1" data-el-pos="0">智能</div>
                                     </div>
                                 </div>
                                 <div class="v-btn speed-btn">
                                     <span id="speed-txt-${post.id}">倍速</span>
                                     <div class="speed-menu">
                                         <div class="speed-opt" data-speed="2.0" data-action="call" data-fn="setPlaybackSpeedByEl" data-args="[]" data-pass-el="1" data-el-pos="0" data-stop="1">2.0x</div>
                                         <div class="speed-opt" data-speed="1.5" data-action="call" data-fn="setPlaybackSpeedByEl" data-args="[]" data-pass-el="1" data-el-pos="0" data-stop="1">1.5x</div>
                                         <div class="speed-opt" data-speed="1.25" data-action="call" data-fn="setPlaybackSpeedByEl" data-args="[]" data-pass-el="1" data-el-pos="0" data-stop="1">1.25x</div>
                                         <div class="speed-opt active" data-speed="1.0" data-action="call" data-fn="setPlaybackSpeedByEl" data-args="[]" data-pass-el="1" data-el-pos="0" data-stop="1">1.0x</div>
                                         <div class="speed-opt" data-speed="0.75" data-action="call" data-fn="setPlaybackSpeedByEl" data-args="[]" data-pass-el="1" data-el-pos="0" data-stop="1">0.75x</div>
                                     </div>
                                 </div>
                                <div class="v-btn vol-btn" id="vol-wrap-${post.id}">
                                    <i class="fas fa-volume-up" id="btn-vol-${post.id}" data-action="call" data-fn="toggleGlobalMute" data-args="[]" data-stop="1"></i>
                                    <div class="v-vol-pop" id="vol-pop-${post.id}">
                                        <input class="v-vol-slider" id="vol-slider-${post.id}" type="range" min="0" max="1" step="0.01" value="1" data-action-input="call" data-fn="setGlobalVolumeFromEl" data-args="[]" data-pass-el="1" data-el-pos="0" data-stop="1">
                                        <div class="v-vol-pct" id="vol-pct-${post.id}">100%</div>
                                    </div>
                                </div>
                                 <div class="v-btn" data-action="call" data-fn="toggleFullscreenByPostId" data-args="[${post.id}]" data-stop="1"><i class="fas fa-expand" id="btn-full-${post.id}"></i></div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="comments-side" data-action="stop" data-stop="1">
                    <div class="comments-side-inner">
                        <div class="comments-head">
                            <div class="comments-title">全部评论 (<span class="comments-count">0</span>)</div>
                            <i class="fas fa-times comments-close" data-action="call" data-fn="closeComments" data-args="[]"></i>
                        </div>
                        <div class="comments-list"></div>
                        <div class="comments-input-wrap">
                            <div class="comments-reply-bar">
                                <div class="comments-reply-text"></div>
                                <div class="cancel" data-action="call" data-fn="clearCommentReply" data-args="[]">取消</div>
                            </div>
                            <div class="comments-input-row">
                                <textarea class="comments-input" placeholder="善语结善缘，恶语伤人心" data-action-keydown="call" data-fn="postComment" data-args="[]" data-key-code="13" data-no-shift="1" data-prevent="1"></textarea>
                                <button class="comments-send" data-action="call" data-fn="postComment" data-args="[]">发送</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            ${navArrows}
        `;
    },

    initObserverIn: function(rootEl) {
        if (!rootEl) return;
        const options = { root: rootEl, threshold: 0.6 };
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                const video = entry.target.querySelector('video');
                const btnPlay = entry.target.querySelector('[id^=btn-play-]');
                if (!video) return;

                if (entry.isIntersecting) {
                    const pid = entry.target && entry.target.dataset ? parseInt(entry.target.dataset.postId || '0', 10) : 0;
                    try {
                        if (pid && document.body.classList.contains('comments-open')) {
                            const cur = Number(this.state.currentPostId || 0);
                            if (cur && cur !== pid && typeof this.closeComments === 'function') this.closeComments();
                        }
                    } catch (_) {
                    }
                    try {
                        if (!this.state.feedImprSent) this.state.feedImprSent = {};
                        const now = Date.now();
                        const last = this.state.feedImprSent[pid] || 0;
                        if (pid && now - last > 30 * 1000) {
                            this.state.feedImprSent[pid] = now;
                            const uid = this.state.user ? Number(this.state.user.id || 0) : 0;
                            if (window.appEmit) window.appEmit('feed:impression', { post_id: pid, user_id: uid || null, source: 'recommend' });
                        }
                    } catch (_) {
                    }
                    if (pid) this.recordWatch(pid);
                    if (pid) this.state.activePostId = pid;
                    this.pauseAllVideosExcept(video);
                    const p = video.play();
                    if (p) p.then(() => { if (btnPlay) btnPlay.className = 'fas fa-pause'; })
                           .catch(async () => {
                               try {
                                   video.muted = true;
                                   await video.play();
                                   if (btnPlay) btnPlay.className = 'fas fa-pause';
                               } catch (_) {
                                   if (btnPlay) btnPlay.className = 'fas fa-play';
                               }
                           });
                } else {
                    video.pause();
                    video.currentTime = 0;
                    if (btnPlay) btnPlay.className = 'fas fa-play';
                }
            });
        }, options);
        rootEl.querySelectorAll('.video-slide').forEach(el => observer.observe(el));
    },

    ensureRecommendNavArrows: function() {
        const page = document.getElementById('page-recommend');
        if (!page) return;
        if (document.getElementById('recommend_nav_arrows')) return;
        const box = document.createElement('div');
        box.id = 'recommend_nav_arrows';
        box.className = 'video-nav-arrows';
        box.innerHTML = `
            <div class="nav-arrow" data-dir="prev"><i class="fas fa-chevron-up"></i></div>
            <div class="nav-arrow" data-dir="next"><i class="fas fa-chevron-down"></i></div>
        `;
        box.addEventListener('click', (e) => {
            const t = e && e.target ? e.target : null;
            const btn = t && t.closest ? t.closest('.nav-arrow') : null;
            if (!btn) return;
            e.preventDefault();
            e.stopPropagation();
            const pid = Number(this.state.activePostId || this.state.currentPostId || 0);
            if (!pid) return;
            if (btn.dataset && btn.dataset.dir === 'prev') this.playPrev(pid);
            else this.playNext(pid);
        });
        page.appendChild(box);
    },

    setQuality: function(el, mode) {
        const parent = el.parentElement;
        // Only remove active from siblings
        Array.from(parent.children).forEach(o => o.classList.remove('active'));
        el.classList.add('active');
        const txt = mode === 'ultra' ? '超高清' : (mode === 'hd' ? '高清' : (mode === 'sd' ? '标清' : '智能'));
        parent.previousElementSibling.innerText = txt;

        try {
            const slide = el.closest ? el.closest('.video-slide') : null;
            const video = slide ? slide.querySelector('video') : null;
            if (!video) return;
            const hls = (video.dataset && video.dataset.hls) ? String(video.dataset.hls) : '';
            if (!hls) return;
            const nativeHls = !!(video.canPlayType && video.canPlayType('application/vnd.apple.mpegurl'));
            const hlsjs = video._aiseekHls;
            if (!nativeHls && hlsjs && typeof hlsjs.levels !== 'undefined') {
                if (mode === 'auto') hlsjs.currentLevel = -1;
                else {
                    const want = mode === 'sd' ? 360 : (mode === 'hd' ? 540 : 720);
                    let idx = -1;
                    try {
                        for (let i = 0; i < hlsjs.levels.length; i++) {
                            const lv = hlsjs.levels[i] || {};
                            const h = Number(lv.height || 0);
                            if (h && Math.abs(h - want) <= 40) { idx = i; break; }
                        }
                    } catch (_) {
                    }
                    if (idx >= 0) hlsjs.currentLevel = idx;
                }
                return;
            }
            if (!nativeHls) return;

            const base = hls.replace(/master\.m3u8(\?.*)?$/i, '');
            let target = hls;
            if (mode === 'sd') target = base + 'v0/index.m3u8';
            else if (mode === 'hd') target = base + 'v1/index.m3u8';
            else if (mode === 'ultra') target = base + 'v2/index.m3u8';
            else target = base + 'master.m3u8';

            const t = Number(video.currentTime || 0);
            const paused = !!video.paused;
            if ((video.currentSrc || video.src || '') !== target) {
                video.src = target;
                try { video.load(); } catch (_) {}
                const resume = async () => {
                    try { if (t > 0) video.currentTime = t; } catch (_) {}
                    try { if (!paused) await video.play(); } catch (_) {}
                };
                if (video.readyState >= 1) resume();
                else video.addEventListener('loadedmetadata', resume, { once: true });
            }
        } catch (_) {
        }
    },

    _getSlideByPostId: function(postId) {
        try { return document.getElementById(`slide-${Number(postId || 0)}`); } catch (_) { return null; }
    },

    _getVideoByPostId: function(postId) {
        const slide = this._getSlideByPostId(postId);
        return slide ? slide.querySelector('video') : null;
    },

    _setPlayIcon: function(postId, playing) {
        const btn = document.getElementById(`btn-play-${Number(postId || 0)}`);
        if (!btn) return;
        btn.className = playing ? 'fas fa-pause' : 'fas fa-play';
    },

    handleStageClick: function(postId) {
        const pid = Number(postId || 0);
        if (!pid) return;
        if (!this._clickTimerByPostId) this._clickTimerByPostId = {};
        if (this._clickTimerByPostId[pid]) return;
        this._clickTimerByPostId[pid] = setTimeout(() => {
            this._clickTimerByPostId[pid] = null;
            try { this.togglePlayByPostId(pid); } catch (_) {}
        }, 220);
    },

    handleStageDblClick: async function(postId) {
        const pid = Number(postId || 0);
        if (!pid) return;
        if (this._clickTimerByPostId && this._clickTimerByPostId[pid]) {
            try { clearTimeout(this._clickTimerByPostId[pid]); } catch (_) {}
            this._clickTimerByPostId[pid] = null;
        }
        try { await this.toggleFullscreenByPostId(pid); } catch (_) {}
    },

    togglePlayByPostId: async function(postId) {
        const pid = Number(postId || 0);
        const video = this._getVideoByPostId(pid);
        if (!video) return;
        try {
            if (video.paused) {
                try { this.pauseAllVideosExcept(video); } catch (_) {}
                try { video.muted = !!this.state.isMuted; video.volume = Number(this.state.globalVolume || 0); } catch (_) {}
                try {
                    const p = video.play();
                    if (p && typeof p.then === 'function') await p;
                    this._setPlayIcon(pid, true);
                } catch (_) {
                    try { video.muted = true; const p2 = video.play(); if (p2 && typeof p2.then === 'function') await p2; this._setPlayIcon(pid, true); } catch (_) { this._setPlayIcon(pid, false); }
                }
            } else {
                try { video.pause(); } catch (_) {}
                this._setPlayIcon(pid, false);
            }
        } catch (_) {
        }
    },

    seekByPostId: function(postId, ev) {
        const pid = Number(postId || 0);
        const video = this._getVideoByPostId(pid);
        const prog = document.getElementById(`prog-c-${pid}`);
        if (!video || !prog || !ev) return;
        try {
            const rect = prog.getBoundingClientRect();
            const pct = Math.max(0, Math.min(1, (Number(ev.clientX || 0) - rect.left) / (rect.width || 1)));
            video.currentTime = pct * (video.duration || 0);
        } catch (_) {
        }
    },

    seekStartByPostId: function(progEl, postId, ev) {
        if (!progEl || !ev) return;
        try { progEl.setPointerCapture(ev.pointerId); } catch (_) {}
        try {
            progEl._seekActive = true;
            progEl._seekPointerId = ev.pointerId;
        } catch (_) {
        }
        this.seekByPostId(postId, ev);
    },

    seekMoveByPostId: function(progEl, postId, ev) {
        if (!progEl || !ev) return;
        try {
            if (!progEl._seekActive) return;
            if (Number(progEl._seekPointerId) !== Number(ev.pointerId)) return;
        } catch (_) {
            return;
        }
        this.seekByPostId(postId, ev);
    },

    seekEndByPostId: function(progEl, postId, ev) {
        if (!progEl || !ev) return;
        try {
            if (!progEl._seekActive) return;
            if (Number(progEl._seekPointerId) !== Number(ev.pointerId)) return;
        } catch (_) {
            return;
        }
        try { progEl._seekActive = false; } catch (_) {}
        this.seekByPostId(postId, ev);
    },

    seekCancelByPostId: function(progEl, postId, ev) {
        if (!progEl) return;
        try { progEl._seekActive = false; } catch (_) {}
    },

    _syncGlobalVolumeUIAll: function() {
        const isMuted = !!this.state.isMuted;
        const vol = Math.max(0, Math.min(1, Number(this.state.globalVolume || 0)));
        document.querySelectorAll('video').forEach(v => {
            try {
                if (Math.abs((v.volume || 0) - vol) > 0.01) v.volume = vol;
                if (v.muted !== isMuted) v.muted = isMuted;
            } catch (_) {
            }
        });
        document.querySelectorAll('[id^=vol-slider-]').forEach(sl => {
            try { sl.value = String(vol); } catch (_) {}
        });
        document.querySelectorAll('[id^=vol-pct-]').forEach(p => {
            try { p.innerText = `${Math.round(vol * 100)}%`; } catch (_) {}
        });
        document.querySelectorAll('[id^=btn-vol-]').forEach(b => {
            try {
                if (isMuted || vol === 0) b.className = 'fas fa-volume-mute';
                else if (vol < 0.5) b.className = 'fas fa-volume-down';
                else b.className = 'fas fa-volume-up';
            } catch (_) {
            }
        });
    },

    setGlobalVolumeFromEl: function(el) {
        if (!el) return;
        try {
            const v = Math.max(0, Math.min(1, parseFloat(el.value) || 0));
            this.state.globalVolume = v;
            this.state.isMuted = (v === 0);
            localStorage.setItem('global_volume', v);
            localStorage.setItem('is_muted', this.state.isMuted ? '1' : '0');
            this._syncGlobalVolumeUIAll();
            const m = String(el.id || '').match(/vol-slider-(\d+)/);
            const pid = m ? Number(m[1] || 0) : 0;
            try {
                if (window.appEmit) window.appEmit((window.appEventNames && window.appEventNames.PLAYER_VOLUME) || 'player:volume', { post_id: pid || null, volume: this.state.globalVolume, muted: this.state.isMuted, ts: Date.now() });
                else if (window.appEvents && typeof window.appEvents.emit === 'function') window.appEvents.emit((window.appEventNames && window.appEventNames.PLAYER_VOLUME) || 'player:volume', { post_id: pid || null, volume: this.state.globalVolume, muted: this.state.isMuted, ts: Date.now() });
            } catch (_) {
            }
        } catch (_) {
        }
    },

    toggleGlobalMute: function() {
        try {
            this.state.isMuted = !this.state.isMuted;
            if (!this.state.isMuted && Number(this.state.globalVolume || 0) === 0) this.state.globalVolume = 0.5;
            localStorage.setItem('is_muted', this.state.isMuted ? '1' : '0');
            localStorage.setItem('global_volume', this.state.globalVolume);
            this._syncGlobalVolumeUIAll();
            try {
                if (window.appEmit) window.appEmit((window.appEventNames && window.appEventNames.PLAYER_VOLUME) || 'player:volume', { post_id: null, volume: this.state.globalVolume, muted: this.state.isMuted, ts: Date.now() });
                else if (window.appEvents && typeof window.appEvents.emit === 'function') window.appEvents.emit((window.appEventNames && window.appEventNames.PLAYER_VOLUME) || 'player:volume', { post_id: null, volume: this.state.globalVolume, muted: this.state.isMuted, ts: Date.now() });
            } catch (_) {
            }
        } catch (_) {
        }
    },

    toggleFullscreenByPostId: async function(postId) {
        const pid = Number(postId || 0);
        const slide = this._getSlideByPostId(pid);
        const container = slide ? (slide.querySelector('.video-player-container') || slide) : null;
        try {
            if (document.fullscreenElement) await document.exitFullscreen();
            else if (container && container.requestFullscreen) {
                await container.requestFullscreen();
                this.state.fullscreenPostId = pid;
            }
        } catch (_) {
        }
    },

    setPlaybackSpeedByEl: function(el) {
        if (!el) return;
        const slide = el.closest ? el.closest('.video-slide') : null;
        const video = slide ? slide.querySelector('video') : null;
        if (!video) return;
        const speed = parseFloat(el.dataset.speed);
        if (!Number.isFinite(speed)) return;
        try { video.playbackRate = speed; } catch (_) {}
        const pid = slide && slide.dataset ? Number(slide.dataset.postId || 0) : 0;
        const speedTxt = pid ? document.getElementById(`speed-txt-${pid}`) : null;
        if (speedTxt) speedTxt.innerText = speed === 1.0 ? '倍速' : speed + 'x';
        try {
            const opts = slide.querySelectorAll('.speed-opt[data-speed]');
            opts.forEach(o => o.classList.remove('active'));
            el.classList.add('active');
        } catch (_) {
        }
    },

    toggleAutoPlay: function() {
        this.state.autoPlay = !this.state.autoPlay;
        document.querySelectorAll('[id^=btn-lianbo-]').forEach(b => {
            try { if (this.state.autoPlay) b.classList.add('active'); else b.classList.remove('active'); } catch (_) {}
        });
    },

    toggleCleanMode: function() {
        this.state.isCleanMode = !this.state.isCleanMode;
        document.querySelectorAll('[id^=btn-clean-]').forEach(b => {
            try { if (this.state.isCleanMode) b.classList.add('active'); else b.classList.remove('active'); } catch (_) {}
        });
        document.querySelectorAll('.video-actions, .video-info-overlay').forEach(el => {
            try { el.style.opacity = this.state.isCleanMode ? '0' : '1'; } catch (_) {}
        });
    },

    setJingxuanCategory: function(el, cat) {
        const c = String(cat || '');
        this.state.category = (c === '全部' ? 'all' : c);
        try {
            const tabs = document.getElementById('jx-tabs');
            if (tabs) Array.from(tabs.children).forEach(ch => { try { ch.className = 'tab-item'; } catch (_) {} });
            if (el && el.classList) el.className = 'tab-item active';
        } catch (_) {
        }
        try { this.loadJingxuanData(); } catch (_) {}
    },

    bindVideoEvents: function(slide, post) {
        const video = slide.querySelector('video');
        if (!video) return;

        try {
            this.applyPreferredVideoSource(video, post, { autoPlay: true });
        } catch (_) {
        }

        const emitPlayer = (event, payload) => {
            try {
                if (window.appEmit) window.appEmit(event, payload);
                else if (window.appEvents && typeof window.appEvents.emit === 'function') window.appEvents.emit(event, { ...(payload || {}), ts: Date.now() });
            } catch (_) {
            }
        };

        this.loadDanmaku(post.id);

        const container = slide.querySelector('.video-player-container') || slide;
        const btnPlay = slide.querySelector(`#btn-play-${post.id}`);
        const timeDisplay = slide.querySelector(`#time-${post.id}`);
        const progContainer = slide.querySelector(`#prog-c-${post.id}`);
        const progFilled = slide.querySelector(`#prog-f-${post.id}`);
        const btnLianbo = slide.querySelector(`#btn-lianbo-${post.id}`);
        const btnClean = slide.querySelector(`#btn-clean-${post.id}`);
        const btnVol = slide.querySelector(`#btn-vol-${post.id}`);
        const btnFull = slide.querySelector(`#btn-full-${post.id}`);
        const volWrap = slide.querySelector(`#vol-wrap-${post.id}`);
        const volPop = slide.querySelector(`#vol-pop-${post.id}`);
        const volSlider = slide.querySelector(`#vol-slider-${post.id}`);
        const volPct = slide.querySelector(`#vol-pct-${post.id}`);
        const controlsBar = slide.querySelector('.video-controls-bar');
        // Only select speed options, not quality options
        const speedOpts = slide.querySelectorAll('.speed-opt[data-speed]');
        const speedTxt = slide.querySelector(`#speed-txt-${post.id}`);

        const applyCrop = () => {
            try { this.applyRecommendMediaCrop(video); } catch (_) {}
        };
        if (video.readyState >= 1) applyCrop();
        else video.addEventListener('loadedmetadata', applyCrop, { once: true });
        this.ensureRecommendMediaCrop(video);

        // Initialize Volume from Global State
        video.muted = this.state.isMuted;
        video.volume = this.state.globalVolume;

        video.addEventListener('play', () => emitPlayer((window.appEventNames && window.appEventNames.PLAYER_PLAY) || 'player:play', { post_id: post.id }));
        video.addEventListener('pause', () => emitPlayer((window.appEventNames && window.appEventNames.PLAYER_PAUSE) || 'player:pause', { post_id: post.id }));

        // Time Update
        video.ontimeupdate = () => {
            const pct = (video.currentTime / video.duration) * 100;
            progFilled.style.width = `${pct}%`;
            timeDisplay.innerText = `${this.fmtTime(video.currentTime)} / ${this.fmtTime(video.duration)}`;
            this.tickDanmaku(post.id, video.currentTime, slide);
            try {
                const pid = Number(post.id || 0);
                if (pid) this.recordWatchProgress(pid, { watch_time_sec: Number(video.currentTime || 0), duration_sec: Number(video.duration || 0) });
            } catch (_) {
            }
        };
        try { this._syncGlobalVolumeUIAll(); } catch (_) {}

        // Auto Scroll
        video.onended = () => {
            emitPlayer((window.appEventNames && window.appEventNames.PLAYER_ENDED) || 'player:ended', { post_id: post.id });
            try {
                const pid = Number(post.id || 0);
                if (pid) this.recordWatchProgress(pid, { watch_time_sec: Number(video.duration || video.currentTime || 0), duration_sec: Number(video.duration || 0), completed: true });
            } catch (_) {
            }
            if (this.state.autoPlay) {
                const nextSlide = slide.nextElementSibling;
                if (nextSlide) nextSlide.scrollIntoView({ behavior: 'smooth' });
                else video.play();
            } else {
                video.play();
            }
        };
    },

    hideAllVolumePops: function() {
        document.querySelectorAll('.v-vol-pop.active').forEach(el => el.classList.remove('active'));
    },

    pauseAllVideosExcept: function(exceptVideo) {
        const except = exceptVideo || null;
        document.querySelectorAll('video').forEach(v => {
            if (except && v === except) return;
            try { v.pause(); } catch (_) {}
        });
    },

    handleGlobalKeydown: function(e) {
        if (!e) return;
        const t = e.target;
        const tag = t && t.tagName ? String(t.tagName).toUpperCase() : '';
        const typing = tag === 'INPUT' || tag === 'TEXTAREA' || (t && t.isContentEditable);
        if (typing) return;

        if (e.code === 'Escape') {
            const wrap = document.getElementById('floating_player');
            if (wrap && wrap.style.display !== 'none') {
                e.preventDefault();
                this.closeFloatingPlayer();
                return;
            }
        }

        const floatWrap = document.getElementById('floating_player');
        const floatVisible = floatWrap && floatWrap.style.display !== 'none';
        if (floatVisible) {
            const fv = document.getElementById('floating_player_video');
            if (e.code === 'Space') {
                e.preventDefault();
                if (fv) {
                    if (fv.paused) fv.play().then(() => {}).catch(() => {});
                    else fv.pause();
                }
                return;
            }
            if (e.code === 'Enter') {
                e.preventDefault();
                if (typeof this.floatingToggleFullscreen === 'function') this.floatingToggleFullscreen();
                return;
            }
            if (e.code === 'KeyM') {
                e.preventDefault();
                if (fv) {
                    fv.muted = !fv.muted;
                    this.state.isMuted = fv.muted;
                    localStorage.setItem('is_muted', this.state.isMuted ? '1' : '0');
                }
                return;
            }
            if (e.code === 'ArrowLeft') {
                e.preventDefault();
                if (fv && Number.isFinite(fv.duration) && fv.duration) fv.currentTime = Math.max(0, (fv.currentTime || 0) - 5);
                return;
            }
            if (e.code === 'ArrowRight') {
                e.preventDefault();
                if (fv && Number.isFinite(fv.duration) && fv.duration) fv.currentTime = Math.min(fv.duration, (fv.currentTime || 0) + 5);
                return;
            }
        }

        if (e.code === 'KeyU') {
            e.preventDefault();
            const wrap = document.getElementById('floating_player');
            if (wrap && wrap.style.display !== 'none') this.closeFloatingPlayer();
            else this.openFloatingPlayer(this.state.activePostId);
            return;
        }

        const activeId = Number(this.state.activePostId || this.state.currentPostId || this.state.fullscreenPostId || 0);
        const slide = activeId ? document.getElementById(`slide-${activeId}`) : null;
        const video = slide ? slide.querySelector('video') : null;
        const btnPlay = activeId ? document.getElementById(`btn-play-${activeId}`) : null;

        if (e.code === 'ArrowUp' && this.state.currentTab === 'recommend' && activeId) {
            e.preventDefault();
            this.playPrev(activeId);
            return;
        }
        if (e.code === 'ArrowDown' && this.state.currentTab === 'recommend' && activeId) {
            e.preventDefault();
            this.playNext(activeId);
            return;
        }

        if (e.code === 'Space') {
            e.preventDefault();
            if (document.fullscreenElement) {
                const fs = document.fullscreenElement;
                const v = fs ? fs.querySelector('video') : null;
                const btn = fs ? fs.querySelector('[id^=btn-play-]') : null;
                if (v) {
                    if (v.paused) { v.play().then(() => {}).catch(() => {}); if (btn) btn.className = 'fas fa-pause'; }
                    else { v.pause(); if (btn) btn.className = 'fas fa-play'; }
                }
                return;
            }
            if (video) {
                if (video.paused) {
                    video.play().then(() => {}).catch(() => {});
                    if (btnPlay) btnPlay.className = 'fas fa-pause';
                } else {
                    video.pause();
                    if (btnPlay) btnPlay.className = 'fas fa-play';
                }
            }
            return;
        }

        if (e.code === 'Enter') {
            e.preventDefault();
            if (document.fullscreenElement) {
                document.exitFullscreen().catch(() => {});
                return;
            }
            const target = slide ? (slide.querySelector('.video-player-container') || slide) : null;
            if (target && target.requestFullscreen) {
                target.requestFullscreen().then(() => {
                    this.state.fullscreenPostId = activeId || null;
                }).catch(() => {});
            }
            return;
        }
    },

    fmtTime: function(s) {
        if (!s || isNaN(s)) return '00:00';
        const m = Math.floor(s / 60);
        const sec = Math.floor(s % 60);
        return `${m.toString().padStart(2,'0')}:${sec.toString().padStart(2,'0')}`;
    },

    fmtDateTime: function(d) {
        if (!d) return '';
        const dt = new Date(d);
        if (isNaN(dt.getTime())) return '';
        const y = dt.getFullYear();
        const mo = String(dt.getMonth() + 1).padStart(2, '0');
        const da = String(dt.getDate()).padStart(2, '0');
        const h = String(dt.getHours()).padStart(2, '0');
        const mi = String(dt.getMinutes()).padStart(2, '0');
        return `${y}-${mo}-${da} ${h}:${mi}`;
    },

    bindJxFeaturedControls: function(mainEl) {
        const video = mainEl.querySelector('video');
        const bar = mainEl.querySelector('.jx-controls-bar');
        if (!video || !bar) return;
        const pid = Number(mainEl && mainEl.dataset ? (mainEl.dataset.postId || 0) : 0);

        try {
            const hls = video.dataset ? String(video.dataset.hls || '') : '';
            const mp4 = video.dataset ? String(video.dataset.mp4 || '') : '';
            const v = hls || mp4 || '';
            const p = { hls_url: hls, mp4_url: mp4, video_url: v };
            const r = this.applyPreferredVideoSource(video, p, { autoPlay: false });
            if (r && typeof r.catch === 'function') r.catch(() => {});
        } catch (_) {
        }

        const btnPlay = bar.querySelector('[data-role="play"]');
        const btnMute = bar.querySelector('[data-role="mute"]');
        const btnFs = bar.querySelector('[data-role="fullscreen"]');
        const progress = bar.querySelector('[data-role="progress"]');
        const filled = bar.querySelector('.jx-progress-filled');
        const tCur = bar.querySelector('[data-role="current"]');
        const tDur = bar.querySelector('[data-role="duration"]');
        const vol = bar.querySelector('[data-role="vol"]');

        let lastVol = 0.6;
        video.muted = true;
        video.volume = 0;
        if (vol) vol.value = '0';

        const setPlayIcon = () => {
            const i = btnPlay ? btnPlay.querySelector('i') : null;
            if (!i) return;
            i.className = video.paused ? 'fas fa-play' : 'fas fa-pause';
        };
        const setMuteIcon = () => {
            const i = btnMute ? btnMute.querySelector('i') : null;
            if (!i) return;
            i.className = (video.muted || video.volume === 0) ? 'fas fa-volume-mute' : 'fas fa-volume-up';
        };
        const sync = () => {
            const dur = video.duration || 0;
            const cur = video.currentTime || 0;
            if (tCur) tCur.textContent = this.fmtTime(cur);
            if (tDur) tDur.textContent = this.fmtTime(dur);
            if (filled) filled.style.width = dur > 0 ? `${Math.min(100, (cur / dur) * 100)}%` : '0%';
        };

        bar.addEventListener('click', (e) => e.stopPropagation());

        if (btnPlay) {
            btnPlay.addEventListener('click', async (e) => {
                e.stopPropagation();
                try {
                    if (video.paused) {
                        if (pid) this.recordWatch(pid);
                        await video.play();
                    }
                    else video.pause();
                } catch(_) {}
                setPlayIcon();
            });
        }

        if (btnMute) {
            btnMute.addEventListener('click', (e) => {
                e.stopPropagation();
                const willMute = !(video.muted || video.volume === 0);
                if (willMute) {
                    if (video.volume > 0) lastVol = video.volume;
                    video.muted = true;
                    video.volume = 0;
                    if (vol) vol.value = '0';
                } else {
                    video.muted = false;
                    video.volume = Math.max(0.05, lastVol);
                    if (vol) vol.value = String(video.volume);
                }
                setMuteIcon();
            });
        }

        if (vol) {
            vol.addEventListener('input', (e) => {
                e.stopPropagation();
                const v = parseFloat(vol.value);
                if (!isNaN(v)) {
                    video.volume = v;
                    video.muted = v === 0;
                    if (v > 0) lastVol = v;
                }
                setMuteIcon();
            });
            vol.addEventListener('click', (e) => e.stopPropagation());
        }

        if (progress) {
            progress.addEventListener('click', (e) => {
                e.stopPropagation();
                const rect = progress.getBoundingClientRect();
                const ratio = rect.width > 0 ? (e.clientX - rect.left) / rect.width : 0;
                const dur = video.duration || 0;
                if (dur > 0) video.currentTime = Math.max(0, Math.min(dur, ratio * dur));
                sync();
            });
        }

        if (btnFs) {
            btnFs.addEventListener('click', async (e) => {
                e.stopPropagation();
                const el = mainEl;
                try {
                    if (document.fullscreenElement) await document.exitFullscreen();
                    else if (el.requestFullscreen) await el.requestFullscreen();
                } catch(_) {}
            });
        }

        video.addEventListener('loadedmetadata', () => {
            sync();
            setPlayIcon();
            setMuteIcon();
        });
        video.addEventListener('timeupdate', sync);
        video.addEventListener('play', setPlayIcon);
        video.addEventListener('pause', setPlayIcon);
        video.addEventListener('volumechange', setMuteIcon);
        sync();
        setPlayIcon();
        setMuteIcon();
    },

    bindJxMiniControls: function(cardEl) {
        const video = cardEl ? cardEl.querySelector('video') : null;
        const bar = cardEl ? cardEl.querySelector('.jx-mini-controls') : null;
        if (!video || !bar) return;

        try {
            const hls = video.dataset ? String(video.dataset.hls || '') : '';
            const mp4 = video.dataset ? String(video.dataset.mp4 || '') : '';
            const v = hls || mp4 || '';
            const p = { hls_url: hls, mp4_url: mp4, video_url: v };
            const r = this.applyPreferredVideoSource(video, p, { autoPlay: false });
            if (r && typeof r.catch === 'function') r.catch(() => {});
        } catch (_) {
        }

        const btnPlay = bar.querySelector('[data-role="play"]');
        const btnMute = bar.querySelector('[data-role="mute"]');
        const btnFs = bar.querySelector('[data-role="fullscreen"]');
        const progress = bar.querySelector('[data-role="progress"]');
        const filled = bar.querySelector('.jx-mini-filled');
        const tCur = bar.querySelector('[data-role="current"]');
        const tDur = bar.querySelector('[data-role="duration"]');

        let lastVol = 0.6;
        video.muted = true;
        video.volume = 0;

        const setPlayIcon = () => {
            const i = btnPlay ? btnPlay.querySelector('i') : null;
            if (!i) return;
            i.className = video.paused ? 'fas fa-play' : 'fas fa-pause';
        };
        const setMuteIcon = () => {
            const i = btnMute ? btnMute.querySelector('i') : null;
            if (!i) return;
            i.className = (video.muted || video.volume === 0) ? 'fas fa-volume-mute' : 'fas fa-volume-up';
        };
        const sync = () => {
            const dur = video.duration || 0;
            const cur = video.currentTime || 0;
            if (tCur) tCur.textContent = this.fmtTime(cur);
            if (tDur) tDur.textContent = this.fmtTime(dur);
            if (filled) filled.style.width = dur > 0 ? `${Math.min(100, (cur / dur) * 100)}%` : '0%';
        };

        bar.addEventListener('click', (e) => e.stopPropagation());

        if (btnPlay) {
            btnPlay.addEventListener('click', async (e) => {
                e.stopPropagation();
                try {
                    if (video.paused) {
                        // Pause all other videos
                        document.querySelectorAll('video').forEach(v => {
                            if (v !== video && !v.paused) v.pause();
                        });
                        await video.play();
                    }
                    else video.pause();
                } catch (_) {}
                setPlayIcon();
            });
        }

        if (btnMute) {
            btnMute.addEventListener('click', (e) => {
                e.stopPropagation();
                const willMute = !(video.muted || video.volume === 0);
                if (willMute) {
                    if (video.volume > 0) lastVol = video.volume;
                    video.muted = true;
                    video.volume = 0;
                } else {
                    video.muted = false;
                    video.volume = Math.max(0.05, lastVol);
                }
                setMuteIcon();
            });
        }

        if (progress) {
            progress.addEventListener('click', (e) => {
                e.stopPropagation();
                const rect = progress.getBoundingClientRect();
                const ratio = rect.width > 0 ? (e.clientX - rect.left) / rect.width : 0;
                const dur = video.duration || 0;
                if (dur > 0) video.currentTime = Math.max(0, Math.min(dur, ratio * dur));
                sync();
            });
        }

        if (btnFs) {
            btnFs.addEventListener('click', async (e) => {
                e.stopPropagation();
                try {
                    if (document.fullscreenElement) await document.exitFullscreen();
                    else if (cardEl.requestFullscreen) await cardEl.requestFullscreen();
                } catch (_) {}
            });
        }

        video.addEventListener('loadedmetadata', () => {
            sync();
            setPlayIcon();
            setMuteIcon();
        });
        video.addEventListener('timeupdate', sync);
        video.addEventListener('play', setPlayIcon);
        video.addEventListener('pause', setPlayIcon);
        video.addEventListener('volumechange', setMuteIcon);
        sync();
        setPlayIcon();
        setMuteIcon();

        setPlayIcon();
    },

    initObserver: function() {
        this.ensureRecommendNavArrows();
        const options = { root: document.getElementById('page-recommend'), threshold: [0, 0.08, 0.25, 0.6] };
        if (this._recommendObserver && typeof this._recommendObserver.disconnect === 'function') {
            try { this._recommendObserver.disconnect(); } catch (_) {}
        }
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                const video = entry.target.querySelector('video');
                const btnPlay = entry.target.querySelector('[id^=btn-play-]');
                if (!video) return;

                if (entry.intersectionRatio >= 0.08) {
                    this._scheduleIdle(() => {
                        try {
                            const slides = Array.from(document.querySelectorAll('#page-recommend .video-slide'));
                            const idx = slides.indexOf(entry.target);
                            if (idx >= 0) {
                                if (idx + 1 < slides.length) this._prewarmSlideMedia(slides[idx + 1]);
                                if (idx + 2 < slides.length) this._prewarmSlideMedia(slides[idx + 2]);
                            }
                        } catch (_) {
                        }
                    });
                }

                if (entry.intersectionRatio >= 0.6) {
                    const pid = entry.target && entry.target.dataset ? parseInt(entry.target.dataset.postId || '0', 10) : 0;
                    if (pid) this.recordWatch(pid);
                    if (pid) this.state.activePostId = pid;
                    this.pauseAllVideosExcept(video);
                    const p = video.play();
                    if (p) {
                        p.then(() => {
                            if (btnPlay) btnPlay.className = 'fas fa-pause';
                        }).catch(async () => {
                            try {
                                video.muted = true;
                                video.volume = 0;
                                await video.play();
                                if (btnPlay) btnPlay.className = 'fas fa-pause';
                            } catch (_) {
                                if (btnPlay) btnPlay.className = 'fas fa-play';
                            }
                        });
                    }

                    try {
                        const slides = Array.from(document.querySelectorAll('#page-recommend .video-slide'));
                        const idx = slides.indexOf(entry.target);
                        if (idx >= 0 && slides.length - idx <= 3) this.loadMoreRecommend();
                    } catch (_) {
                    }
                } else {
                    video.pause();
                    video.currentTime = 0;
                    if(btnPlay) btnPlay.className = 'fas fa-play';
                }
            });
        }, options);
        this._recommendObserver = observer;
        try {
            if (window.appRuntime && typeof window.appRuntime.registerCleanup === 'function') {
                window.appRuntime.registerCleanup('recommend', () => {
                    try {
                        if (this._recommendObserver && typeof this._recommendObserver.disconnect === 'function') this._recommendObserver.disconnect();
                    } catch (_) {
                    }
                });
            }
        } catch (_) {
        }
        document.querySelectorAll('.video-slide').forEach(el => observer.observe(el));
    },

    recordWatch: function(postId) {
        if (!this.state.user) return;
        const pid = Number(postId || 0);
        if (!pid) return;

        const now = Date.now();
        const last = this.state.watchRecorded[pid] || 0;
        if (now - last < 10 * 60 * 1000) return;
        this.state.watchRecorded[pid] = now;

        try {
            this.apiBeacon('POST', '/api/v1/interaction/history', { post_id: pid, user_id: this.state.user.id }, { keepalive: true });
        } catch (_) {
        }
        try { this.bumpViewsCount(pid); } catch (_) {}
    },

    recordWatchProgress: function(postId, opts = {}) {
        if (!this.state.user) return;
        const pid = Number(postId || 0);
        if (!pid) return;
        const wt = Number(opts.watch_time_sec || 0);
        const dur = Number(opts.duration_sec || 0);
        const completed = !!opts.completed;
        const dwell = Number(opts.dwell_ms || 0);
        if (!(wt > 0 || completed || dwell > 0)) return;

        const now = Date.now();
        const st = (this.state.watchProgress && this.state.watchProgress[pid]) ? this.state.watchProgress[pid] : { lastSent: 0, lastWt: 0 };
        const minInterval = 4000;
        const minDelta = 1.5;
        const shouldSend = completed || (now - (st.lastSent || 0) >= minInterval && (wt - (st.lastWt || 0) >= minDelta));
        if (!shouldSend) {
            if (!this.state.watchProgress) this.state.watchProgress = {};
            this.state.watchProgress[pid] = st;
            return;
        }
        st.lastSent = now;
        st.lastWt = Math.max(st.lastWt || 0, wt);
        if (!this.state.watchProgress) this.state.watchProgress = {};
        this.state.watchProgress[pid] = st;

        const payload = { post_id: pid, user_id: this.state.user.id, watch_time_sec: wt || null, duration_sec: dur || null, completed: completed ? true : null, dwell_ms: dwell || null };
        try {
            if (window.appEmit) window.appEmit('player:watch', payload);
        } catch (_) {
        }
        try {
            let viaStream = false;
            try {
                if (window.__aiseekFlags && window.__aiseekFlags.watch_via_stream) viaStream = true;
                if (!viaStream) {
                    const meta = document.querySelector('meta[name="aiseek-flags"]');
                    const raw = meta ? String(meta.getAttribute('content') || '') : '';
                    if (raw) {
                        const obj = JSON.parse(raw);
                        if (obj && obj.watch_via_stream) viaStream = true;
                        if (!window.__aiseekFlags) window.__aiseekFlags = obj;
                    }
                }
            } catch (_) {}
            if (!viaStream) this.apiBeacon('POST', '/api/v1/interaction/watch', payload, { keepalive: true });
        } catch (_) {
        }
    },

    bumpViewsCount: function(postId) {
        const pid = Number(postId || 0);
        if (!pid) return;
        const incIn = (arr) => {
            const a = Array.isArray(arr) ? arr : [];
            for (let i = 0; i < a.length; i++) {
                const p = a[i];
                if (p && Number(p.id) === pid) {
                    const cur = Number(p.views_count || 0);
                    p.views_count = (Number.isFinite(cur) ? cur : 0) + 1;
                    return Number(p.views_count || 0);
                }
            }
            return null;
        };
        let next = incIn(this.state.recommendPosts);
        if (next == null) next = incIn(this.state.jingxuanPosts);
        if (next == null) next = 1;
        const fmtViews = (n) => {
            const v = Number(n || 0);
            if (v >= 100000000) return (v / 100000000).toFixed(1).replace(/\.0$/, '') + '亿';
            if (v >= 10000) return (v / 10000).toFixed(1).replace(/\.0$/, '') + '万';
            return String(v);
        };
        try {
            document.querySelectorAll(`.jx-view-count[data-post-id="${pid}"]`).forEach(el => {
                el.textContent = `播放 ${fmtViews(next)}`;
            });
        } catch (_) {
        }
    },

    playNext: function(currentPostId) {
        const slides = Array.from(document.querySelectorAll('#page-recommend .video-slide'));
        const idx = slides.findIndex(s => s.id === `slide-${currentPostId}`);
        if (idx >= 0 && idx + 1 < slides.length) {
            try {
                const v = slides[idx + 1].querySelector('video');
                const hls = v && v.dataset ? String(v.dataset.hls || '') : '';
                if (hls) this.prewarmHlsUrl(hls);
                try {
                    const p = v ? (v.getAttribute('poster') || '') : '';
                    if (p) this.prewarmCoverUrl(p);
                } catch (_) {}
            } catch (_) {
            }
            slides[idx + 1].scrollIntoView({ behavior: 'smooth' });
        }
    },

    playPrev: function(currentPostId) {
        const slides = Array.from(document.querySelectorAll('#page-recommend .video-slide'));
        const idx = slides.findIndex(s => s.id === `slide-${currentPostId}`);
        if (idx > 0) {
            try {
                const v = slides[idx - 1].querySelector('video');
                const hls = v && v.dataset ? String(v.dataset.hls || '') : '';
                if (hls) this.prewarmHlsUrl(hls);
                try {
                    const p = v ? (v.getAttribute('poster') || '') : '';
                    if (p) this.prewarmCoverUrl(p);
                } catch (_) {}
            } catch (_) {
            }
            slides[idx - 1].scrollIntoView({ behavior: 'smooth' });
        }
    },

    loadJingxuan: async function() {
        if (!this.state.category) this.state.category = 'all';
        const tabs = document.getElementById('jx-tabs');
        tabs.innerHTML = ''; // Force clear to ensure latest categories
        const base = Array.isArray(this.state.categories) && this.state.categories.length > 0
            ? this.state.categories
            : ['大模型', 'Agent', '机器人', 'AIGC', '多模态', '编程', '提示词', '资讯', 'Tools', '办公', '变现', '电商', '游戏', '金融', '影视', '教育', '少儿'];
        const cats = ['全部', ...base];
        cats.forEach(c => {
            const div = document.createElement('div');
            div.className = `tab-item ${this.state.category === (c==='全部'?'all':c) ? 'active' : ''}`;
            div.innerText = c;
            try {
                div.dataset.action = 'call';
                div.dataset.fn = 'setJingxuanCategory';
                div.dataset.args = JSON.stringify([c]);
                div.dataset.passEl = '1';
                div.dataset.elPos = '0';
            } catch (_) {
            }
            tabs.appendChild(div);
        });
        this.loadJingxuanData();
    },

    refreshJingxuanViews: async function() {
        if (this.state.currentTab !== 'jingxuan') return;
        if (!Array.isArray(this.state.jingxuanPosts) || this.state.jingxuanPosts.length === 0) return;
        try {
            let url = '/api/v1/posts/feed';
            const params = [];
            if (this.state.category && this.state.category !== 'all') params.push(`category=${this.state.category}`);
            if (this.state.user) params.push(`user_id=${this.state.user.id}`);
            params.push('limit=50');
            if (params.length > 0) url += '?' + params.join('&');
            const res = await this.apiRequest('GET', url, undefined, { cancel_key: 'feed:jingxuan:views', dedupe_key: url });
            if (!res.ok) return;
            const posts = await res.json();
            const arr = Array.isArray(posts) ? posts : [];
            if (!arr.length) return;
            const byId = new Map(arr.map((p) => [Number(p && p.id), Number(p && p.views_count || 0)]));
            const fmtViews = (n) => {
                const v = Number(n || 0);
                if (v >= 100000000) return (v / 100000000).toFixed(1).replace(/\.0$/, '') + '亿';
                if (v >= 10000) return (v / 10000).toFixed(1).replace(/\.0$/, '') + '万';
                return String(v);
            };
            this.state.jingxuanPosts.forEach((p) => {
                const pid = Number(p && p.id);
                if (!pid || !byId.has(pid)) return;
                p.views_count = Number(byId.get(pid) || 0);
            });
            document.querySelectorAll('.jx-view-count[data-post-id]').forEach((el) => {
                const pid = Number(el.getAttribute('data-post-id') || 0);
                if (!pid || !byId.has(pid)) return;
                el.textContent = `播放 ${fmtViews(byId.get(pid) || 0)}`;
            });
        } catch (_) {
        }
    },

    loadJingxuanData: async function() {
        const container = document.getElementById('jx-grid');
        const main = document.getElementById('jx-main_player');
        const side = document.getElementById('jx_side_grid');
        const below = document.getElementById('jx_below_row');
        if (!container) return;
        if (!this.state.category) this.state.category = 'all';
        container.innerHTML = '<div style="color:#888; grid-column:1/-1; text-align:center;">加载中...</div>';
        if (main) main.innerHTML = '';
        if (side) side.innerHTML = '';
        if (below) below.innerHTML = '';
        try {
            this.state.jingxuanLoadingMore = false;
            let url = '/api/v1/posts/feed';
            const params = [];
            if (this.state.category !== 'all') params.push(`category=${this.state.category}`);
            if (this.state.user) params.push(`user_id=${this.state.user.id}`);
            params.push('limit=50');
            if (params.length > 0) url += '?' + params.join('&');

            const res = await this.apiRequest('GET', url, undefined, { cancel_key: 'feed:jingxuan', dedupe_key: url });
            if (!res.ok) throw new Error(`GET ${url} ${res.status}`);
            const posts = await res.json();
            this.state.jingxuanCursor = (res && res.headers && typeof res.headers.get === 'function') ? (res.headers.get('x-next-cursor') || null) : null;
            this.state.jingxuanPosts = Array.isArray(posts) ? posts : [];
            try { this.state.jingxuanSeenIds = new Set(this.state.jingxuanPosts.map(p => Number(p && p.id))); } catch (_) { this.state.jingxuanSeenIds = null; }
            try {
                if (this.state.jingxuanViewsTimer) clearInterval(this.state.jingxuanViewsTimer);
                this.state.jingxuanViewsTimer = setInterval(() => {
                    try { this.refreshJingxuanViews(); } catch (_) {}
                }, 5000);
                setTimeout(() => { try { this.refreshJingxuanViews(); } catch (_) {} }, 900);
            } catch (_) {
            }
            
            container.innerHTML = '';
            if (posts.length === 0) {
                container.innerHTML = '<div style="color:#888; grid-column:1/-1; text-align:center; padding:30px 0;">暂无作品</div>';
                if (main) main.innerHTML = '<div style="height:100%; display:flex; align-items:center; justify-content:center; color:#888;">暂无作品</div>';
                if (side) side.innerHTML = '<div style="height:100%; display:flex; align-items:center; justify-content:center; color:#888;">暂无作品</div>';
                if (below) below.innerHTML = '<div style="height:100%; display:flex; align-items:center; justify-content:center; color:#888;">暂无作品</div>';
                return;
            }

            const featured = posts[0];
            const sidePosts = posts.slice(1, 3);
            const belowPosts = posts.slice(3, 7);
            const gridPosts = posts.slice(7);

            const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
            const fmtViews = (n) => {
                const v = Number(n || 0);
                if (v >= 100000000) return (v / 100000000).toFixed(1).replace(/\.0$/, '') + '亿';
                if (v >= 10000) return (v / 10000).toFixed(1).replace(/\.0$/, '') + '万';
                return String(v);
            };
            const fmtCreatedAgo = (createdAt) => {
                if (!createdAt) return '';
                const ms = typeof createdAt === 'number' ? (createdAt > 1e12 ? createdAt : createdAt * 1000) : new Date(createdAt).getTime();
                if (!ms || isNaN(ms)) return '';
                return this.fmtTimeAgo(ms);
            };
            const buildTitleTags = (post) => {
                const base = (post.title || post.content_text || '').trim() || '无标题';
                if (base.includes('#')) return base;
                const fromBody = String(post.content_text || '');
                const tagsFound = [];
                try {
                    const re = /#([^\s#]{1,20})/g;
                    let m;
                    while ((m = re.exec(fromBody)) !== null) {
                        const t = String(m[1] || '').trim();
                        if (!t) continue;
                        const k = `#${t}`;
                        if (!tagsFound.includes(k)) tagsFound.push(k);
                        if (tagsFound.length >= 12) break;
                    }
                } catch (_) {
                }
                const tags = [];
                if (tagsFound.length > 0) tags.push(...tagsFound.slice(0, 12));
                else {
                    if (post.category) tags.push(`#${post.category}`);
                    else tags.push('#AI教学');
                    tags.push('#AI认知');
                }
                return `${base} ${tags.join(' ')}`.replace(/\s+/g, ' ').trim();
            };
            const renderSmallCard = (post) => {
                const isV = (post.post_type === 'video') || (post.video_url && !(/\.(jpg|jpeg|png|gif|webp)(\?|#|$)/i.test(post.video_url)));
                const poster = post.cover_url || `/api/v1/media/post-thumb/${encodeURIComponent(String(post.id))}?v=${Date.now()}`;
                const imgUrl = (poster || (Array.isArray(post.images) && post.images.length > 0 ? post.images[0] : '') || post.video_url || '');
                const srcs = this.resolveVideoSources(post);
                const hls = srcs.hls_url || '';
                const mp4 = srcs.mp4_url || '';
                const media = isV
                    ? `
                        <video data-hls="${hls}" data-mp4="${mp4}" poster="${poster}" muted loop playsinline webkit-playsinline preload="metadata"></video>
                        <div class="jx-mini-controls" data-action="stop" data-stop="1">
                            <div class="jx-mini-progress" data-role="progress"><div class="jx-mini-filled"></div></div>
                            <div class="jx-mini-row">
                                <div class="jx-mini-left">
                                    <div class="jx-mini-btn" data-role="play"><i class="fas fa-pause"></i></div>
                                    <div class="jx-mini-time"><span data-role="current">00:00</span> / <span data-role="duration">00:00</span></div>
                                </div>
                                <div class="jx-mini-right">
                                    <div class="jx-mini-btn" data-role="mute"><i class="fas fa-volume-mute"></i></div>
                                    <div class="jx-mini-btn" data-role="fullscreen"><i class="fas fa-expand"></i></div>
                                </div>
                            </div>
                        </div>
                    `
                    : `<img src="${imgUrl}">`;
                const author = post.user_nickname || ('用户' + post.user_id);
                const views = fmtViews(post.views_count || 0);
                const ago = fmtCreatedAgo(post.created_at);
                const parts = [`@${author}`];
                if (ago) parts.push(ago);
                const line = parts.join(' ');
                return `
                    <div class="jx-media">${media}</div>
                    <div class="jx-card-meta">
                        <div class="jx-meta-title">${esc(buildTitleTags(post))}</div>
                        <div class="jx-meta-sub">
                            <div class="left">${esc(line)}</div>
                            <div class="right" style="display:flex; align-items:center; gap:6px; color:rgba(255,255,255,0.78);">
                                <i class="far fa-eye"></i>
                                <span class="jx-view-count" data-post-id="${post.id}">播放 ${esc(views)}</span>
                            </div>
                        </div>
                    </div>
                `;
            };

            if (main && featured) {
                const isVideo = (featured.post_type === 'video') || (featured.video_url && !(/\.(jpg|jpeg|png|gif|webp)(\?|#|$)/i.test(featured.video_url)));
                const srcs = this.resolveVideoSources(featured);
                const hls = srcs.hls_url || '';
                const mp4 = srcs.mp4_url || '';
                const poster = featured.cover_url || `/api/v1/media/post-thumb/${encodeURIComponent(String(featured.id))}?v=${Date.now()}`;
                const media = isVideo
                    ? `<video data-hls="${hls}" data-mp4="${mp4}" poster="${poster}" muted loop playsinline webkit-playsinline preload="metadata"></video>`
                    : `<img src="${poster || featured.images?.[0] || featured.video_url}">`;
                const title = featured.content_text || featured.title || '';
                const author = featured.user_nickname || ('用户' + featured.user_id);
                const views = fmtViews(featured.views_count || 0);
                const metaBottom = isVideo ? 78 : 14;
                const controls = isVideo ? `
                    <div class="jx-controls-bar" data-action="stop" data-stop="1">
                        <div class="jx-progress" data-role="progress"><div class="jx-progress-filled"></div></div>
                        <div class="jx-controls-row">
                            <div class="jx-controls-left">
                                <div class="jx-ctrl-btn" data-role="play"><i class="fas fa-pause"></i></div>
                                <div class="jx-time"><span data-role="current">00:00</span> / <span data-role="duration">00:00</span></div>
                            </div>
                            <div class="jx-controls-right">
                                <div class="jx-vol-wrap">
                                    <div class="jx-ctrl-btn" data-role="mute"><i class="fas fa-volume-mute"></i></div>
                                    <input class="jx-vol" data-role="vol" type="range" min="0" max="1" step="0.01" value="0">
                                </div>
                                <div class="jx-ctrl-btn" data-role="fullscreen"><i class="fas fa-expand"></i></div>
                            </div>
                        </div>
                    </div>
                ` : '';
                main.innerHTML = `
                    ${media}
                    <div style="position:absolute; inset:0; background:linear-gradient(to top, rgba(0,0,0,0.75), rgba(0,0,0,0.0) 55%);"></div>
                    <div style="position:absolute; left:16px; bottom:${metaBottom}px; right:16px;">
                        <div style="font-size:18px; font-weight:700; color:white; line-height:1.35; max-height:54px; overflow:hidden;">${title}</div>
                        <div style="margin-top:8px; display:flex; gap:10px; align-items:center; color:rgba(255,255,255,0.75); font-size:12px;">
                            <span>@${author}</span>
                            <span>·</span>
                            <span>${(featured.created_at ? new Date(featured.created_at).toLocaleDateString() : '')}</span>
                            <span style="margin-left:auto; display:flex; align-items:center; gap:6px; color:rgba(255,255,255,0.80);">
                                <i class="far fa-eye"></i>
                                <span class="jx-view-count" data-post-id="${featured.id}">播放 ${esc(views)}</span>
                            </span>
                        </div>
                    </div>
                    ${controls}
                `;
                try {
                    main.dataset.action = 'call';
                    main.dataset.fn = 'openPost';
                    main.dataset.args = JSON.stringify([featured.id]);
                    main.dataset.postId = String(featured.id);
                } catch (_) {
                }
                if (isVideo) this.bindJxFeaturedControls(main);
            }

            if (side) {
                side.innerHTML = '';
                sidePosts.forEach(post => {
                    const card = document.createElement('div');
                    card.className = 'jx-card';
                    card.innerHTML = renderSmallCard(post);
                    try {
                        card.dataset.action = 'call';
                        card.dataset.fn = 'openPost';
                        card.dataset.args = JSON.stringify([post.id]);
                    } catch (_) {
                    }
                    if (card.querySelector('video')) this.bindJxMiniControls(card);
                    const mediaEl = card.querySelector('.jx-media');
                    if (mediaEl) {
                        try {
                            mediaEl.setAttribute('data-action-mouseover', 'call');
                            mediaEl.setAttribute('data-fn-mouseover', 'showJxPopupById');
                            mediaEl.setAttribute('data-args-mouseover', JSON.stringify([post.id]));
                            mediaEl.setAttribute('data-pass-el', '1');
                            mediaEl.setAttribute('data-action-mouseout', 'call');
                            mediaEl.setAttribute('data-fn-mouseout', 'hideJxPopup');
                            mediaEl.setAttribute('data-args-mouseout', '[]');
                        } catch (_) {
                        }
                    }
                    side.appendChild(card);
                });
            }

            if (below) {
                below.innerHTML = '';
                belowPosts.forEach(post => {
                    const card = document.createElement('div');
                    card.className = 'jx-card';
                    card.innerHTML = renderSmallCard(post);
                    try {
                        card.dataset.action = 'call';
                        card.dataset.fn = 'openPost';
                        card.dataset.args = JSON.stringify([post.id]);
                    } catch (_) {
                    }
                    if (card.querySelector('video')) this.bindJxMiniControls(card);
                    const mediaEl = card.querySelector('.jx-media');
                    if (mediaEl) {
                        try {
                            mediaEl.setAttribute('data-action-mouseover', 'call');
                            mediaEl.setAttribute('data-fn-mouseover', 'showJxPopupById');
                            mediaEl.setAttribute('data-args-mouseover', JSON.stringify([post.id]));
                            mediaEl.setAttribute('data-pass-el', '1');
                            mediaEl.setAttribute('data-action-mouseout', 'call');
                            mediaEl.setAttribute('data-fn-mouseout', 'hideJxPopup');
                            mediaEl.setAttribute('data-args-mouseout', '[]');
                        } catch (_) {
                        }
                    }
                    below.appendChild(card);
                });
            }

            gridPosts.forEach(post => {
                const card = document.createElement('div');
                card.className = 'jx-card';
                card.innerHTML = renderSmallCard(post);
                try {
                    card.dataset.action = 'call';
                    card.dataset.fn = 'openPost';
                    card.dataset.args = JSON.stringify([post.id]);
                } catch (_) {
                }
                if (card.querySelector('video')) this.bindJxMiniControls(card);
                const mediaEl = card.querySelector('.jx-media');
                if (mediaEl) {
                    try {
                        mediaEl.setAttribute('data-action-mouseover', 'call');
                        mediaEl.setAttribute('data-fn-mouseover', 'showJxPopupById');
                        mediaEl.setAttribute('data-args-mouseover', JSON.stringify([post.id]));
                        mediaEl.setAttribute('data-pass-el', '1');
                        mediaEl.setAttribute('data-action-mouseout', 'call');
                        mediaEl.setAttribute('data-fn-mouseout', 'hideJxPopup');
                        mediaEl.setAttribute('data-args-mouseout', '[]');
                    } catch (_) {
                    }
                }
                container.appendChild(card);
            });
            try { this.initJingxuanInfiniteScroll(); } catch (_) {}
        } catch(e) { container.innerHTML = '加载失败'; }
    },

    initJingxuanInfiniteScroll: function() {
        const page = document.getElementById('page-jingxuan');
        if (!page || page._jxScrollBound) return;
        page._jxScrollBound = true;
        page.addEventListener('scroll', () => {
            try {
                if (this.state.currentTab !== 'jingxuan') return;
                const remain = (page.scrollHeight - (page.scrollTop + page.clientHeight));
                if (remain <= 260) this.loadMoreJingxuan();
            } catch (_) {
            }
        }, { passive: true });
    },

    loadMoreJingxuan: async function() {
        if (this.state.jingxuanLoadingMore) return;
        const cursor = String(this.state.jingxuanCursor || '');
        if (!cursor) return;
        this.state.jingxuanLoadingMore = true;
        const container = document.getElementById('jx-grid');
        try {
            let url = '/api/v1/posts/feed';
            const params = [];
            if (this.state.category !== 'all') params.push(`category=${this.state.category}`);
            if (this.state.user) params.push(`user_id=${this.state.user.id}`);
            params.push('limit=50');
            params.push(`cursor=${encodeURIComponent(cursor)}`);
            url += '?' + params.join('&');
            const res = await this.apiRequest('GET', url, undefined, { cancel_key: 'feed:jingxuan:more', dedupe_key: url });
            if (!res.ok) throw new Error(`GET ${url} ${res.status}`);
            const posts = await res.json();
            this.state.jingxuanCursor = (res && res.headers && typeof res.headers.get === 'function') ? (res.headers.get('x-next-cursor') || null) : null;
            const arr = Array.isArray(posts) ? posts : [];
            const seen = (this.state.jingxuanSeenIds && typeof this.state.jingxuanSeenIds.add === 'function') ? this.state.jingxuanSeenIds : null;
            const fresh = [];
            for (const p of arr) {
                const pid = Number(p && p.id);
                if (!pid) continue;
                if (seen) {
                    if (seen.has(pid)) continue;
                    seen.add(pid);
                }
                fresh.push(p);
            }
            if (fresh.length > 0) {
                if (!Array.isArray(this.state.jingxuanPosts)) this.state.jingxuanPosts = [];
                this.state.jingxuanPosts.push(...fresh);
                const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
                const fmtViews = (n) => {
                    const v = Number(n || 0);
                    if (v >= 100000000) return (v / 100000000).toFixed(1).replace(/\.0$/, '') + '亿';
                    if (v >= 10000) return (v / 10000).toFixed(1).replace(/\.0$/, '') + '万';
                    return String(v);
                };
                const fmtCreatedAgo = (createdAt) => {
                    if (!createdAt) return '';
                    const ms = typeof createdAt === 'number' ? (createdAt > 1e12 ? createdAt : createdAt * 1000) : new Date(createdAt).getTime();
                    if (!ms || isNaN(ms)) return '';
                    return this.fmtTimeAgo(ms);
                };
                const buildTitleTags = (post) => {
                    const base = (post.title || post.content_text || '').trim() || '无标题';
                    if (base.includes('#')) return base;
                    const fromBody = String(post.content_text || '');
                    const tagsFound = [];
                    try {
                        const re = /#([^\s#]{1,20})/g;
                        let m;
                        while ((m = re.exec(fromBody)) !== null) {
                            const t = String(m[1] || '').trim();
                            if (!t) continue;
                            const k = `#${t}`;
                            if (!tagsFound.includes(k)) tagsFound.push(k);
                            if (tagsFound.length >= 12) break;
                        }
                    } catch (_) {
                    }
                    const tags = [];
                    if (tagsFound.length > 0) tags.push(...tagsFound.slice(0, 12));
                    else {
                        if (post.category) tags.push(`#${post.category}`);
                        else tags.push('#AI教学');
                        tags.push('#AI认知');
                    }
                    return `${base} ${tags.join(' ')}`.replace(/\s+/g, ' ').trim();
                };
                const renderSmallCard = (post) => {
                    const isV = (post.post_type === 'video') || (post.video_url && !(/\.(jpg|jpeg|png|gif|webp)(\?|#|$)/i.test(post.video_url)));
                    const poster = post.cover_url || `/api/v1/media/post-thumb/${encodeURIComponent(String(post.id))}?v=${Date.now()}`;
                    const imgUrl = (poster || (Array.isArray(post.images) && post.images.length > 0 ? post.images[0] : '') || post.video_url || '');
                    const srcs = this.resolveVideoSources(post);
                    const hls = srcs.hls_url || '';
                    const mp4 = srcs.mp4_url || '';
                    const media = isV
                        ? `
                            <video data-hls="${hls}" data-mp4="${mp4}" poster="${poster}" muted loop playsinline webkit-playsinline preload="metadata"></video>
                            <div class="jx-mini-controls" data-action="stop" data-stop="1">
                                <div class="jx-mini-progress" data-role="progress"><div class="jx-mini-filled"></div></div>
                                <div class="jx-mini-row">
                                    <div class="jx-mini-left">
                                        <div class="jx-mini-btn" data-role="play"><i class="fas fa-pause"></i></div>
                                        <div class="jx-mini-time"><span data-role="current">00:00</span> / <span data-role="duration">00:00</span></div>
                                    </div>
                                    <div class="jx-mini-right">
                                        <div class="jx-mini-btn" data-role="mute"><i class="fas fa-volume-mute"></i></div>
                                        <div class="jx-mini-btn" data-role="fullscreen"><i class="fas fa-expand"></i></div>
                                    </div>
                                </div>
                            </div>
                        `
                        : `<img src="${imgUrl}">`;
                    const author = post.user_nickname || ('用户' + post.user_id);
                    const views = fmtViews(post.views_count || 0);
                    const ago = fmtCreatedAgo(post.created_at);
                    const parts = [`@${author}`];
                    if (ago) parts.push(ago);
                    const line = parts.join(' ');
                    return `
                        <div class="jx-media">${media}</div>
                        <div class="jx-card-meta">
                            <div class="jx-meta-title">${esc(buildTitleTags(post))}</div>
                            <div class="jx-meta-sub">
                                <div class="left">${esc(line)}</div>
                                <div class="right" style="display:flex; align-items:center; gap:6px; color:rgba(255,255,255,0.78);">
                                    <i class="far fa-eye"></i>
                                    <span class="jx-view-count" data-post-id="${post.id}">播放 ${esc(views)}</span>
                                </div>
                            </div>
                        </div>
                    `;
                };
                fresh.forEach(post => {
                    const card = document.createElement('div');
                    card.className = 'jx-card';
                    card.innerHTML = renderSmallCard(post);
                    try {
                        card.dataset.action = 'call';
                        card.dataset.fn = 'openPost';
                        card.dataset.args = JSON.stringify([post.id]);
                    } catch (_) {
                    }
                    if (card.querySelector('video')) this.bindJxMiniControls(card);
                    const mediaEl = card.querySelector('.jx-media');
                    if (mediaEl) {
                        try {
                            mediaEl.setAttribute('data-action-mouseover', 'call');
                            mediaEl.setAttribute('data-fn-mouseover', 'showJxPopupById');
                            mediaEl.setAttribute('data-args-mouseover', JSON.stringify([post.id]));
                            mediaEl.setAttribute('data-pass-el', '1');
                            mediaEl.setAttribute('data-action-mouseout', 'call');
                            mediaEl.setAttribute('data-fn-mouseout', 'hideJxPopup');
                            mediaEl.setAttribute('data-args-mouseout', '[]');
                        } catch (_) {
                        }
                    }
                    if (container) container.appendChild(card);
                });
            }
        } catch (_) {
        } finally {
            this.state.jingxuanLoadingMore = false;
        }
    },

});
