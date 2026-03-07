Object.assign(window.app, {
    escapeHtml: function(s) {
        return String(s || '').replace(/[&<>"']/g, (c) => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        }[c]));
    },

    getGlobalSearchInput: function() {
        return document.getElementById('global_search_input') || document.querySelector('.search-bar input');
    },

    getSearchHistory: function() {
        try {
            const raw = localStorage.getItem('search_history');
            const arr = JSON.parse(raw || '[]');
            return Array.isArray(arr) ? arr.map(s => String(s || '').trim()).filter(Boolean) : [];
        } catch (_) {
            return [];
        }
    },

    setSearchHistory: function(items) {
        try {
            const arr = Array.isArray(items) ? items.map(s => String(s || '').trim()).filter(Boolean) : [];
            localStorage.setItem('search_history', JSON.stringify(arr.slice(0, 12)));
        } catch (_) {
        }
    },

    addSearchHistory: function(keyword) {
        const q = String(keyword || '').trim();
        if (!q) return;
        const arr = this.getSearchHistory();
        const next = [q, ...arr.filter(x => x !== q)];
        this.setSearchHistory(next);
    },

    clearSearchHistory: function() {
        try { localStorage.removeItem('search_history'); } catch (_) {}
        this.renderSearchDropdown();
    },

    renderSearchDropdown: function() {
        const wrap = document.getElementById('search_history_wrap');
        if (!wrap) return;
        const arr = this.getSearchHistory();
        if (!arr.length) {
            wrap.innerHTML = '';
            return;
        }
        wrap.innerHTML = `
            <div class="search-history-head">
                <div class="search-history-title">搜索记录</div>
                <div class="search-history-clear" data-action="call" data-fn="clearSearchHistory" data-args="[]">清除</div>
            </div>
            ${arr.map(k => `
                <div class="hot-word-item" data-action="call" data-fn="doSearch" data-args='[${JSON.stringify(k)}]'>
                    <div class="hot-rank" style="width:18px; height:18px;"><i class="fas fa-history" style="font-size:10px;"></i></div>
                    <div class="hot-text">${this.escapeHtml(k)}</div>
                </div>
            `).join('')}
            <div style="height:10px;"></div>
        `;
    },

    doSearch: function(keyword) {
        const input = this.getGlobalSearchInput();
        if (input) input.value = keyword;
        this.addSearchHistory(keyword);
        this.searchUser();
    },

    searchUser: async function() {
        const input = this.getGlobalSearchInput();
        const query = input ? String(input.value || '').trim() : '';
        if (!query) return alert('请输入搜索内容');

        try {
            if (this.__searchTimer) clearTimeout(this.__searchTimer);
        } catch (_) {}
        this.__searchTimer = setTimeout(() => {
            this.switchPage('search');
            this.state.searchKeyword = query;
            this.addSearchHistory(query);
            this.switchSearchTab('all');
        }, 280);
    },

    switchSearchTab: function(mode) {
        const m = mode || 'all';
        this.state.searchMode = m;
        const a = document.getElementById('search_tab_all');
        const b = document.getElementById('search_tab_video');
        const c = document.getElementById('search_tab_user');
        if (a && b && c) {
            a.classList.toggle('active', m === 'all');
            b.classList.toggle('active', m === 'video');
            c.classList.toggle('active', m === 'user');
        }
        this.renderSearchResults();
    },

    searchLoadMore: async function(kind) {
        const query = (this.state.searchKeyword || '').trim();
        if (!query) return;
        const mode = this.state.searchMode || 'all';
        const k = String(kind || '');

        if (k !== 'posts' && k !== 'users') return;
        if (!this.__searchLoadMoreBusy) this.__searchLoadMoreBusy = {};
        if (this.__searchLoadMoreBusy[k]) return;
        this.__searchLoadMoreBusy[k] = true;

        try {
            const grid = document.getElementById('search_results_grid');
            if (!grid) return;

            const viewer = this.state.user ? this.state.user.id : '';
            const limitPosts = 24;
            const limitUsers = 10;

            const fetchPage = async (url, cancelKey) => {
                if (!this.__searchPageCache) this.__searchPageCache = new Map();
                const ttl = 1500;
                const now = Date.now();
                const canCache = url.indexOf('&cursor=') === -1 && url.indexOf('?cursor=') === -1;
                if (canCache) {
                    const hit = this.__searchPageCache.get(url);
                    if (hit && hit.exp > now) return hit;
                }
                const res = await this.apiRequest('GET', url, undefined, { cancel_key: cancelKey, dedupe_key: url });
                if (!res.ok) throw new Error(`GET ${url} ${res.status}`);
                const data = await res.json();
                const next = res.headers ? (res.headers.get('x-next-cursor') || '') : '';
                const out = { data, next: next || '' };
                if (canCache) this.__searchPageCache.set(url, { ...out, exp: now + ttl });
                return out;
            };

            if (k === 'posts') {
                const cursor = String(this.state.searchCursorPosts || '').trim();
                if (!cursor) return;
                const url = `/api/v1/posts/search?query=${encodeURIComponent(query)}&limit=${limitPosts}${viewer ? `&user_id=${viewer}` : ''}&cursor=${encodeURIComponent(cursor)}`;
                const out = await fetchPage(url, `search:more:posts`);
                const posts = Array.isArray(out.data) ? out.data : [];
                if (!posts.length) {
                    this.state.searchCursorPosts = '';
                    return;
                }
                const btn = document.getElementById('search_load_more_posts');
                if (btn && btn.parentElement) btn.parentElement.remove();

                const renderVideoCards = (ps) => {
                    if (!Array.isArray(ps) || ps.length === 0) return '';
                    return ps.map(p => {
                        const likes = Number(p.likes_count || 0);
                        const likeStr = likes >= 10000 ? (likes/10000).toFixed(1).replace(/\.0$/, '')+'万' : likes;
                        const cover = p.cover_url || ((p.images && p.images.length > 0) ? p.images[0] : `/api/v1/media/post-thumb/${p.id}?v=2`);
                        const hls = (typeof p.hls_url === 'string' && p.hls_url) ? p.hls_url : ((typeof p.video_url === 'string' && /\.m3u8(\?|#|$)/i.test(p.video_url)) ? p.video_url : '');
                        const mp4 = (typeof p.mp4_url === 'string' && p.mp4_url) ? p.mp4_url : ((typeof p.video_url === 'string' && !hls) ? p.video_url : '');
                        const dateTxt = p.created_at ? new Date(p.created_at).toLocaleDateString() : '';
                        return `
                        <div class="s-card" data-action="call" data-fn="openPost" data-args="[${p.id}]" data-action-mouseover="call" data-fn-mouseover="showJxPopupById" data-args-mouseover="[${p.id}]" data-pass-el-mouseover="1" data-action-mouseout="call" data-fn-mouseout="hideJxPopup" data-args-mouseout="[]" data-pass-el-mouseout="1">
                            <div class="s-media">
                                <video class="s-media-video" muted playsinline preload="metadata" poster="${cover}" data-hls="${this.escapeHtml(hls)}" data-mp4="${this.escapeHtml(mp4)}" data-video="${this.escapeHtml(String(p.video_url || ''))}"></video>
                                <div class="s-media-controls" data-action="stop" data-stop="1">
                                    <div class="s-media-progress" data-action-pointerdown="call" data-fn-pointerdown="searchCardSeek" data-pass-el-pointerdown="1" data-pass-event-pointerdown="1" data-stop="1"><div class="s-media-progress-fill"></div></div>
                                    <div class="s-ctrl-row">
                                        <div class="s-ctrl-left">
                                            <div class="s-ctrl-btn s-ctrl-play" data-action="call" data-fn="searchCardTogglePlay" data-pass-el="1" data-stop="1"><i class="fas fa-play"></i></div>
                                            <div class="s-ctrl-time"><span class="s-ctrl-time-cur">00:00</span><span class="s-ctrl-time-split">/</span><span class="s-ctrl-time-dur">00:00</span></div>
                                        </div>
                                        <div class="s-ctrl-right">
                                            <div class="s-ctrl-btn s-ctrl-mute" data-action="call" data-fn="searchCardToggleMute" data-pass-el="1" data-stop="1"><i class="fas fa-volume-up"></i></div>
                                            <input class="s-ctrl-vol" type="range" min="0" max="1" step="0.05" value="1" data-action="stop" data-stop="1" data-action-input="call" data-fn-input="searchCardSetVolume" data-pass-el-input="1" data-pass-value-input="1">
                                            <div class="s-ctrl-btn s-ctrl-fs" data-action="call" data-fn="searchCardFullscreen" data-pass-el="1" data-stop="1"><i class="fas fa-expand"></i></div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div class="s-info" style="padding:10px;">
                                <div class="s-title">${this.formatPostDesc(p.title || p.content_text || '无标题')}</div>
                                <div class="s-meta">
                                    <div class="s-author">
                                        <img src="${p.user_avatar || '/static/img/default_avatar.svg'}">
                                        <span>${p.user_nickname || ('用户' + p.user_id)}</span>
                                    </div>
                                    <div style="display:flex; align-items:center; gap:4px;">
                                        <i class="far fa-heart"></i> ${likeStr}
                                    </div>
                                </div>
                                <div class="s-date" style="margin-top:4px; color:#666;">${dateTxt}</div>
                            </div>
                        </div>`;
                    }).join('');
                };

                if (mode === 'all') {
                    const wf = document.getElementById('search_posts_waterfall');
                    if (wf) wf.insertAdjacentHTML('beforeend', renderVideoCards(posts));
                } else {
                    grid.insertAdjacentHTML('beforeend', renderVideoCards(posts));
                }

                this.state.searchCursorPosts = String(out.next || '').trim();
                if (this.state.searchCursorPosts) {
                    const more = `<div style="grid-column:1/-1; text-align:center; padding:20px;"><button id="search_load_more_posts" class="btn btn-outline" data-action="call" data-fn="searchLoadMore" data-args='[\"posts\"]'>加载更多</button></div>`;
                    if (mode === 'all') {
                        const wf = document.getElementById('search_posts_waterfall');
                        if (wf) wf.insertAdjacentHTML('afterend', more);
                    } else {
                        grid.insertAdjacentHTML('beforeend', more);
                    }
                }
            } else {
                const cursor = String(this.state.searchCursorUsers || '').trim();
                if (!cursor) return;
                const url = `/api/v1/users/search-user?query=${encodeURIComponent(query)}&limit=${limitUsers}&cursor=${encodeURIComponent(cursor)}`;
                const out = await fetchPage(url, `search:more:users`);
                const users = Array.isArray(out.data) ? out.data : [];
                if (!users.length) {
                    this.state.searchCursorUsers = '';
                    return;
                }
                const btn = document.getElementById('search_load_more_users');
                if (btn && btn.parentElement) btn.parentElement.remove();

                const renderUserList = (us) => {
                    if (!Array.isArray(us) || us.length === 0) return '';
                    return us.map(u => `
                        <div class="s-user" style="grid-column:1/-1;" data-action="call" data-fn="viewUserProfile" data-args="[${u.id}]">
                            <img class="s-user-avatar" src="${u.avatar || '/static/img/default_avatar.svg'}">
                            <div class="s-user-info">
                                <div class="s-user-name">${u.nickname || u.username}</div>
                                <div class="s-user-sub">AIseek号：${String(u.aiseek_id || u.id)} · 粉丝 ${u.followers_count || 0}</div>
                            </div>
                            <div class="s-user-right">
                                <div class="s-user-pill">进入主页</div>
                            </div>
                        </div>
                    `).join('');
                };

                grid.insertAdjacentHTML('beforeend', renderUserList(users));
                this.state.searchCursorUsers = String(out.next || '').trim();
                if (this.state.searchCursorUsers) {
                    grid.insertAdjacentHTML('beforeend', `<div style="grid-column:1/-1; text-align:center; padding:20px;"><button id="search_load_more_users" class="btn btn-outline" data-action="call" data-fn="searchLoadMore" data-args='[\"users\"]'>加载更多</button></div>`);
                }
            }
        } catch (e) {
            console.error(e);
        } finally {
            this.__searchLoadMoreBusy[k] = false;
        }
    },

    renderSearchResults: async function() {
        const query = (this.state.searchKeyword || '').trim();
        const mode = this.state.searchMode || 'all';
        const grid = document.getElementById('search_results_grid');
        if (!grid) return;

        const gridClass = mode === 'user' ? 'mode-user' : (mode === 'all' ? 'mode-all' : 'mode-video');
        grid.className = `search-grid ${gridClass}`;
        
        grid.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--text-secondary);">搜索中...</div>';

        const renderUserList = (users) => {
            if (!Array.isArray(users) || users.length === 0) return '';
            return users.map(u => `
                <div class="s-user" style="grid-column:1/-1;" data-action="call" data-fn="viewUserProfile" data-args="[${u.id}]">
                    <img class="s-user-avatar" src="${u.avatar || '/static/img/default_avatar.svg'}">
                    <div class="s-user-info">
                        <div class="s-user-name">${u.nickname || u.username}</div>
                        <div class="s-user-sub">AIseek号：${String(u.aiseek_id || u.id)} · 粉丝 ${u.followers_count || 0}</div>
                    </div>
                    <div class="s-user-right">
                        <div class="s-user-pill">进入主页</div>
                    </div>
                </div>
            `).join('');
        };

        const renderTopUser = (u) => {
            if (!u) return '';
            return `
                <div class="s-user" style="grid-column:1/-1;" data-action="call" data-fn="viewUserProfile" data-args="[${u.id}]">
                    <img class="s-user-avatar" src="${u.avatar || '/static/img/default_avatar.svg'}">
                    <div class="s-user-info">
                        <div class="s-user-name">${u.nickname || u.username}</div>
                        <div class="s-user-sub">AIseek号：${String(u.aiseek_id || u.id)} · 粉丝 ${u.followers_count || 0}</div>
                    </div>
                    <div class="s-user-right">
                        <div class="s-user-pill">进入主页</div>
                    </div>
                </div>
            `;
        };

        const renderVideoCards = (posts) => {
            if (!Array.isArray(posts) || posts.length === 0) return '';
            return posts.map(p => {
                const likes = Number(p.likes_count || 0);
                const likeStr = likes >= 10000 ? (likes/10000).toFixed(1).replace(/\.0$/, '')+'万' : likes;
                const cover = p.cover_url || ((p.images && p.images.length > 0) ? p.images[0] : `/api/v1/media/post-thumb/${p.id}?v=2`);
                const hls = (typeof p.hls_url === 'string' && p.hls_url) ? p.hls_url : ((typeof p.video_url === 'string' && /\.m3u8(\?|#|$)/i.test(p.video_url)) ? p.video_url : '');
                const mp4 = (typeof p.mp4_url === 'string' && p.mp4_url) ? p.mp4_url : ((typeof p.video_url === 'string' && !hls) ? p.video_url : '');
                const dateTxt = p.created_at ? new Date(p.created_at).toLocaleDateString() : '';
                return `
                <div class="s-card" data-action="call" data-fn="openPost" data-args="[${p.id}]" data-action-mouseover="call" data-fn-mouseover="showJxPopupById" data-args-mouseover="[${p.id}]" data-pass-el-mouseover="1" data-action-mouseout="call" data-fn-mouseout="hideJxPopup" data-args-mouseout="[]" data-pass-el-mouseout="1">
                    <div class="s-media">
                        <video class="s-media-video" muted playsinline preload="metadata" poster="${cover}" data-hls="${this.escapeHtml(hls)}" data-mp4="${this.escapeHtml(mp4)}" data-video="${this.escapeHtml(String(p.video_url || ''))}"></video>
                        <div class="s-media-controls" data-action="stop" data-stop="1">
                            <div class="s-media-progress" data-action-pointerdown="call" data-fn-pointerdown="searchCardSeek" data-pass-el-pointerdown="1" data-pass-event-pointerdown="1" data-stop="1"><div class="s-media-progress-fill"></div></div>
                            <div class="s-ctrl-row">
                                <div class="s-ctrl-left">
                                    <div class="s-ctrl-btn s-ctrl-play" data-action="call" data-fn="searchCardTogglePlay" data-pass-el="1" data-stop="1"><i class="fas fa-play"></i></div>
                                    <div class="s-ctrl-time"><span class="s-ctrl-time-cur">00:00</span><span class="s-ctrl-time-split">/</span><span class="s-ctrl-time-dur">00:00</span></div>
                                </div>
                                <div class="s-ctrl-right">
                                    <div class="s-ctrl-btn s-ctrl-mute" data-action="call" data-fn="searchCardToggleMute" data-pass-el="1" data-stop="1"><i class="fas fa-volume-up"></i></div>
                                    <input class="s-ctrl-vol" type="range" min="0" max="1" step="0.05" value="1" data-action="stop" data-stop="1" data-action-input="call" data-fn-input="searchCardSetVolume" data-pass-el-input="1" data-pass-value-input="1">
                                    <div class="s-ctrl-btn s-ctrl-fs" data-action="call" data-fn="searchCardFullscreen" data-pass-el="1" data-stop="1"><i class="fas fa-expand"></i></div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="s-info" style="padding:10px;">
                        <div class="s-title">${this.formatPostDesc(p.title || p.content_text || '无标题')}</div>
                        <div class="s-meta">
                            <div class="s-author">
                                <img src="${p.user_avatar || '/static/img/default_avatar.svg'}">
                                <span>${p.user_nickname || ('用户' + p.user_id)}</span>
                            </div>
                            <div style="display:flex; align-items:center; gap:4px;">
                                <i class="far fa-heart"></i> ${likeStr}
                            </div>
                        </div>
                        <div class="s-date" style="margin-top:4px; color:#666;">${dateTxt}</div>
                    </div>
                </div>`;
            }).join('');
        };

        try {
            this.state.searchCursorPosts = '';
            this.state.searchCursorUsers = '';
            let html = '';
            if (mode === 'video') {
                const viewer = this.state.user ? this.state.user.id : '';
                const limit = 24;
                const url = `/api/v1/posts/search?query=${encodeURIComponent(query)}&limit=${limit}${viewer ? `&user_id=${viewer}` : ''}`;
                if (!this.__searchPageCache) this.__searchPageCache = new Map();
                const ttl = 1500;
                const now = Date.now();
                const hit = this.__searchPageCache.get(url);
                let posts = [];
                let next = '';
                if (hit && hit.exp > now) {
                    posts = Array.isArray(hit.data) ? hit.data : [];
                    next = String(hit.next || '');
                } else {
                    const res = await this.apiRequest('GET', url, undefined, { cancel_key: `search:video`, dedupe_key: url });
                    if (!res.ok) throw new Error(`GET ${url} ${res.status}`);
                    posts = await res.json();
                    next = res.headers ? (res.headers.get('x-next-cursor') || '') : '';
                    this.__searchPageCache.set(url, { exp: now + ttl, data: posts, next: next || '' });
                }
                try { this.state.searchPosts = Array.isArray(posts) ? posts : []; } catch (_) {}
                this.state.searchCursorPosts = String(next || '').trim();
                html = (posts.length === 0) ? '<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--text-secondary);">未找到相关视频</div>' : renderVideoCards(posts);
                if (this.state.searchCursorPosts) {
                    html += `<div style="grid-column:1/-1; text-align:center; padding:20px;"><button id="search_load_more_posts" class="btn btn-outline" data-action="call" data-fn="searchLoadMore" data-args='[\"posts\"]'>加载更多</button></div>`;
                }
            }
            else if (mode === 'user') {
                const limit = 10;
                const url = `/api/v1/users/search-user?query=${encodeURIComponent(query)}&limit=${limit}`;
                if (!this.__searchPageCache) this.__searchPageCache = new Map();
                const ttl = 1500;
                const now = Date.now();
                const hit = this.__searchPageCache.get(url);
                let users = [];
                let next = '';
                if (hit && hit.exp > now) {
                    users = Array.isArray(hit.data) ? hit.data : [];
                    next = String(hit.next || '');
                } else {
                    const res = await this.apiRequest('GET', url, undefined, { cancel_key: `search:user`, dedupe_key: url });
                    if (!res.ok) throw new Error(`GET ${url} ${res.status}`);
                    users = await res.json();
                    next = res.headers ? (res.headers.get('x-next-cursor') || '') : '';
                    this.__searchPageCache.set(url, { exp: now + ttl, data: users, next: next || '' });
                }
                this.state.searchCursorUsers = String(next || '').trim();
                html = (users.length === 0) ? '<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--text-secondary);">未找到相关用户</div>' : renderUserList(users);
                if (this.state.searchCursorUsers) {
                    html += `<div style="grid-column:1/-1; text-align:center; padding:20px;"><button id="search_load_more_users" class="btn btn-outline" data-action="call" data-fn="searchLoadMore" data-args='[\"users\"]'>加载更多</button></div>`;
                }
            }
            else { // All
                const viewer = this.state.user ? this.state.user.id : '';
                const limitUsers = 5;
                const limitPosts = 24;
                const uUrl = `/api/v1/users/search-user?query=${encodeURIComponent(query)}&limit=${limitUsers}`;
                const pUrl = `/api/v1/posts/search?query=${encodeURIComponent(query)}&limit=${limitPosts}${viewer ? `&user_id=${viewer}` : ''}`;

                if (!this.__searchPageCache) this.__searchPageCache = new Map();
                const ttl = 1500;
                const now = Date.now();

                const fetchCached = async (url, cancelKey) => {
                    const hit = this.__searchPageCache.get(url);
                    if (hit && hit.exp > now) return hit;
                    const res = await this.apiRequest('GET', url, undefined, { cancel_key: cancelKey, dedupe_key: url });
                    if (!res.ok) throw new Error(`GET ${url} ${res.status}`);
                    const data = await res.json();
                    const next = res.headers ? (res.headers.get('x-next-cursor') || '') : '';
                    const out = { exp: now + ttl, data, next: next || '' };
                    this.__searchPageCache.set(url, out);
                    return out;
                };

                const [uOut, pOut] = await Promise.all([
                    fetchCached(uUrl, `search:all:users`),
                    fetchCached(pUrl, `search:all:posts`)
                ]);

                const users = Array.isArray(uOut.data) ? uOut.data : [];
                const posts = Array.isArray(pOut.data) ? pOut.data : [];
                this.state.searchCursorUsers = String(uOut.next || '').trim();
                this.state.searchCursorPosts = String(pOut.next || '').trim();
                try { this.state.searchPosts = Array.isArray(posts) ? posts : []; } catch (_) {}
                
                if (users.length === 0 && posts.length === 0) {
                    html = '<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--text-secondary);">未找到相关内容</div>';
                } else {
                    const topUser = Array.isArray(users) && users.length > 0 ? users[0] : null;
                    if (topUser) {
                        html += `<div class="search-section-title">最相关用户</div>`;
                        html += renderTopUser(topUser);
                    }
                    if (Array.isArray(posts) && posts.length > 0) {
                        html += `<div class="search-section-title">相关视频</div>`;
                        html += `<div class="search-waterfall" id="search_posts_waterfall">${renderVideoCards(posts)}</div>`;
                        if (this.state.searchCursorPosts) {
                            html += `<div style="grid-column:1/-1; text-align:center; padding:20px;"><button id="search_load_more_posts" class="btn btn-outline" data-action="call" data-fn="searchLoadMore" data-args='[\"posts\"]'>加载更多</button></div>`;
                        }
                    }
                }
            }
            grid.innerHTML = html;
        } catch(e) {
            console.error(e);
            grid.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--text-secondary);">搜索失败，请重试</div>';
        }
    },
    
    closeSearchPage: function() {
        this.switchPage('recommend');
    },

    searchCardGet: function(el) {
        const card = el && el.closest ? el.closest('.s-card') : null;
        if (!card) return null;
        const v = card.querySelector ? card.querySelector('.s-media-video') : null;
        if (!v) return null;
        return { card, v };
    },

    searchCardEnsureSource: function(v) {
        try {
            const post = {
                hls_url: v && v.dataset ? String(v.dataset.hls || '') : '',
                mp4_url: v && v.dataset ? String(v.dataset.mp4 || '') : '',
                video_url: v && v.dataset ? String(v.dataset.video || '') : '',
            };
            if (window.app && typeof window.app.applyPreferredVideoSource === 'function') {
                const r = window.app.applyPreferredVideoSource(v, post, { autoPlay: false });
                if (r && typeof r.catch === 'function') r.catch(() => {});
                return;
            }
            const src = post.hls_url || post.mp4_url || post.video_url || '';
            if (src && (v.currentSrc || v.src || '') !== src) v.src = src;
        } catch (_) {
        }
    },

    searchCardEnsureBound: function(card, v) {
        try {
            if (v._searchControlsBound) return;
            v._searchControlsBound = true;

            const syncTime = () => {
                try {
                    const t = Number(v.currentTime || 0);
                    const d = Number(v.duration || 0);
                    const curEl = card.querySelector('.s-ctrl-time-cur');
                    const durEl = card.querySelector('.s-ctrl-time-dur');
                    if (curEl) curEl.innerText = this.fmtTime(t);
                    if (durEl) durEl.innerText = (d && Number.isFinite(d)) ? this.fmtTime(d) : '00:00';
                    const fill = card.querySelector('.s-media-progress-fill');
                    if (fill && d && Number.isFinite(d)) fill.style.width = `${Math.max(0, Math.min(100, (t / d) * 100))}%`;
                } catch (_) {
                }
            };

            const syncPlayIcon = () => {
                try {
                    const btn = card.querySelector('.s-ctrl-play i');
                    if (!btn) return;
                    btn.className = v.paused ? 'fas fa-play' : 'fas fa-pause';
                } catch (_) {
                }
            };

            const syncMuteIcon = () => {
                try {
                    const btn = card.querySelector('.s-ctrl-mute i');
                    if (!btn) return;
                    btn.className = (v.muted || v.volume === 0) ? 'fas fa-volume-mute' : 'fas fa-volume-up';
                } catch (_) {
                }
            };

            v.addEventListener('timeupdate', syncTime);
            v.addEventListener('loadedmetadata', syncTime);
            v.addEventListener('play', syncPlayIcon);
            v.addEventListener('pause', syncPlayIcon);
            v.addEventListener('volumechange', syncMuteIcon);
            v.addEventListener('ended', () => {
                try { v.currentTime = 0; } catch (_) {}
                syncTime();
                syncPlayIcon();
            });

            syncTime();
            syncPlayIcon();
            syncMuteIcon();
        } catch (_) {
        }
    },

    searchCardTogglePlay: function(el) {
        const r = this.searchCardGet(el);
        if (!r) return;
        const card = r.card;
        const v = r.v;
        this.searchCardEnsureBound(card, v);
        if (v.paused) {
            this.searchCardEnsureSource(v);
            try {
                const p = v.play();
                if (p && typeof p.catch === 'function') p.catch(() => {});
            } catch (_) {
            }
        } else {
            try { v.pause(); } catch (_) {}
        }
    },

    searchCardToggleMute: function(el) {
        const r = this.searchCardGet(el);
        if (!r) return;
        const card = r.card;
        const v = r.v;
        this.searchCardEnsureBound(card, v);
        try {
            v.muted = !v.muted;
            const vol = card.querySelector('.s-ctrl-vol');
            if (vol) vol.value = v.muted ? '0' : String(v.volume || 1);
        } catch (_) {
        }
    },

    searchCardSetVolume: function(el, value) {
        const r = this.searchCardGet(el);
        if (!r) return;
        const card = r.card;
        const v = r.v;
        this.searchCardEnsureBound(card, v);
        try {
            const vol = Math.max(0, Math.min(1, Number(value)));
            if (!Number.isFinite(vol)) return;
            v.volume = vol;
            v.muted = vol === 0;
        } catch (_) {
        }
        try {
            const volEl = card.querySelector('.s-ctrl-vol');
            if (volEl) volEl.value = String(v.muted ? 0 : (v.volume || 0));
        } catch (_) {
        }
    },

    searchCardFullscreen: function(el) {
        const r = this.searchCardGet(el);
        if (!r) return;
        const card = r.card;
        const v = r.v;
        this.searchCardEnsureBound(card, v);
        try {
            const target = (v && v.requestFullscreen) ? v : (card && card.querySelector ? card.querySelector('.s-media') : null);
            if (target && target.requestFullscreen) target.requestFullscreen().catch(() => {});
        } catch (_) {
        }
    },

    searchCardSeek: function(el, ev) {
        const r = this.searchCardGet(el);
        if (!r) return;
        const card = r.card;
        const v = r.v;
        this.searchCardEnsureBound(card, v);
        const bar = card.querySelector('.s-media-progress');
        if (!bar) return;
        try {
            const d = Number(v.duration || 0);
            if (!d || !Number.isFinite(d)) return;
            const rect = bar.getBoundingClientRect();
            const x = Number(ev && ev.clientX ? ev.clientX : 0) - Number(rect.left || 0);
            const pct = rect.width ? Math.max(0, Math.min(1, x / rect.width)) : 0;
            v.currentTime = pct * d;
        } catch (_) {
        }
    },

    searchPreviewPlay: function(cardEl) {
        const card = cardEl && cardEl.querySelector ? cardEl : null;
        if (!card) return;
        const v = card.querySelector('.s-media-video');
        if (!v) return;
        try {
            if (!v._bindSearchPreview) {
                v._bindSearchPreview = true;
                const bindProgressClick = () => {
                    try {
                        const bar = card.querySelector('.s-media-progress');
                        if (!bar || bar._boundClick) return;
                        bar._boundClick = true;
                        bar.addEventListener('click', (e) => {
                            try {
                                const d = Number(v.duration || 0);
                                if (!d || !Number.isFinite(d)) return;
                                const rect = bar.getBoundingClientRect();
                                const x = Number(e.clientX || 0) - Number(rect.left || 0);
                                const pct = rect.width ? Math.max(0, Math.min(1, x / rect.width)) : 0;
                                v.currentTime = pct * d;
                            } catch (_) {
                            }
                        });
                    } catch (_) {
                    }
                };
                bindProgressClick();
                v.addEventListener('timeupdate', () => {
                    try {
                        const fill = card.querySelector('.s-media-progress-fill');
                        const d = Number(v.duration || 0);
                        const t = Number(v.currentTime || 0);
                        if (!fill || !d || !Number.isFinite(d) || !Number.isFinite(t)) return;
                        const pct = Math.max(0, Math.min(1, t / d));
                        fill.style.width = `${pct * 100}%`;
                    } catch (_) {
                    }
                });
                v.addEventListener('ended', () => {
                    try {
                        const fill = card.querySelector('.s-media-progress-fill');
                        if (fill) fill.style.width = '0%';
                    } catch (_) {
                    }
                });
            }
        } catch (_) {
        }
        try {
            const post = {
                hls_url: v.dataset && v.dataset.hls ? String(v.dataset.hls || '') : '',
                mp4_url: v.dataset && v.dataset.mp4 ? String(v.dataset.mp4 || '') : '',
                video_url: v.dataset && v.dataset.video ? String(v.dataset.video || '') : '',
            };
            if (window.app && typeof window.app.applyPreferredVideoSource === 'function') {
                const r = window.app.applyPreferredVideoSource(v, post, { autoPlay: false });
                if (r && typeof r.catch === 'function') r.catch(() => {});
            } else {
                const src = post.hls_url || post.mp4_url || post.video_url || '';
                if (src && (v.currentSrc || v.src || '') !== src) v.src = src;
            }
        } catch (_) {
        }
        try {
            if (v.src || (v.currentSrc && String(v.currentSrc || ''))) {
                const p = v.play();
                if (p && typeof p.catch === 'function') p.catch(() => {});
            }
        } catch (_) {
        }
    },

    searchPreviewStop: function(cardEl) {
        const card = cardEl && cardEl.querySelector ? cardEl : null;
        if (!card) return;
        const v = card.querySelector('.s-media-video');
        if (!v) return;
        try { v.pause(); } catch (_) {}
        try { v.currentTime = 0; } catch (_) {}
        try {
            const fill = card.querySelector('.s-media-progress-fill');
            if (fill) fill.style.width = '0%';
        } catch (_) {
        }
    },

    sendFriendRequest: async function(targetId) {
        if (!this.state.user) return this.openModal('authModal');
        try {
            const url = '/api/v1/users/friend-request/send';
            const res = await this.apiRequest('POST', url, { from_user_id: this.state.user.id, to_user_id: targetId }, { cancel_key: 'friend:request' });
            const data = await res.json();
            if (!res.ok) return alert(data.detail || data.message || '请求发送失败');
            alert(data.message || '请求已发送');
        } catch(e) { console.error(e); alert('请求发送失败'); }
    },

});
