Object.assign(window.app, {
    updateNotifyBadge: function(unread) {
        const bell = document.querySelector('.fa-bell.nav-icon');
        if (!bell) return;
        let badge = document.getElementById('notify_badge');
        if (!badge) {
            badge = document.createElement('span');
            badge.id = 'notify_badge';
            badge.style.position = 'absolute';
            badge.style.top = '-4px';
            badge.style.right = '-8px';
            badge.style.minWidth = '16px';
            badge.style.height = '16px';
            badge.style.padding = '0 5px';
            badge.style.borderRadius = '999px';
            badge.style.background = '#fe2c55';
            badge.style.color = 'white';
            badge.style.fontSize = '10px';
            badge.style.fontWeight = '800';
            badge.style.display = 'flex';
            badge.style.alignItems = 'center';
            badge.style.justifyContent = 'center';
            badge.style.transform = 'scale(0.95)';
            badge.style.pointerEvents = 'none';
            bell.appendChild(badge);
        }
        const n = Number(unread || 0);
        if (!n) {
            badge.style.display = 'none';
            badge.innerText = '';
            return;
        }
        badge.style.display = 'flex';
        badge.innerText = n > 99 ? '99+' : String(n);
    },

    markAllNotificationsRead: async function() {
        const action = { type: 'open_inbox', tab: 'notify' };
        if (typeof this.ensureAuth === 'function') {
            if (!this.ensureAuth(action)) return;
        } else if (!this.state.user) {
            this.state.pendingAuthAction = action;
            this.openModal('authModal');
            return;
        }
        try {
            const res = await this.apiRequest('POST', '/api/v1/interaction/notifications_mark_read', { user_id: this.state.user.id });
            if (!res.ok) throw new Error('mark_read_failed');
            const ret = await res.json();
            if (ret && ret.ok) {
                this.updateNotifyBadge(0);
                this.toast('已全部标记为已读');
                this.loadHeaderDropdowns();
                const modal = document.getElementById('notificationModal');
                if (modal && modal.classList.contains('active')) this.loadNotifications();
                const inbox = document.getElementById('page-inbox');
                if (inbox && inbox.classList.contains('active')) this.loadInboxPage();
            }
        } catch (_) {
            this.toast('操作失败，请重试');
        }
    },

    openInbox: function(tab) {
        const t = tab === 'dm' ? 'dm' : 'notify';
        this.state.inboxTab = t;
        const action = { type: 'open_inbox', tab: t };
        if (typeof this.ensureAuth === 'function') {
            if (!this.ensureAuth(action)) return;
        } else if (!this.state.user) {
            this.state.pendingAuthAction = action;
            this.openModal('authModal');
            return;
        }
        try { this.closeModal('messageModal'); } catch (_) {}
        try { this.closeModal('notificationModal'); } catch (_) {}
        if (t === 'dm') this.openModal('messageModal');
        else this.openModal('notificationModal');
    },

    hoverInboxEnter: function(tab) {
        const t = tab === 'dm' ? 'dm' : 'notify';
        try {
            if (this._inboxHoverTimer) clearTimeout(this._inboxHoverTimer);
            this._inboxHoverTimer = null;
        } catch (_) {
        }
        try { this.openInbox(t); } catch (_) {}
    },

    hoverInboxLeave: function(tab) {
        const t = tab === 'dm' ? 'dm' : 'notify';
        try {
            if (this._inboxHoverTimer) clearTimeout(this._inboxHoverTimer);
        } catch (_) {
        }
        this._inboxHoverTimer = setTimeout(() => {
            try {
                const icon = document.getElementById(t === 'dm' ? 'nav_dm_icon' : 'nav_notify_icon');
                const panel = document.getElementById(t === 'dm' ? 'dmHoverPanel' : 'notifyHoverPanel');
                const iconHover = !!(icon && icon.matches && icon.matches(':hover'));
                const panelHover = !!(panel && panel.matches && panel.matches(':hover'));
                try {
                    const ae = document.activeElement;
                    const panelFocus = !!(panel && ae && panel.contains && panel.contains(ae));
                    if (panelFocus) return;
                } catch (_) {
                }
                try {
                    if (t === 'dm') {
                        const until = Number(this.state.dmFilePickingUntil || 0);
                        if (until && Date.now() < until) return;
                    }
                } catch (_) {
                }
                if (iconHover || panelHover) return;
                if (t === 'dm') this.closeModal('messageModal');
                else this.closeModal('notificationModal');
            } catch (_) {
            }
        }, 120);
    },

    switchInboxTab: function(tab, opts = {}) {
        const t = tab === 'dm' ? 'dm' : 'notify';
        this.state.inboxTab = t;
        const a = document.getElementById('inbox_tab_notify');
        const b = document.getElementById('inbox_tab_dm');
        if (a && b) {
            a.classList.toggle('active', t === 'notify');
            b.classList.toggle('active', t === 'dm');
        }
        const mark = document.getElementById('inbox_mark_read');
        if (mark) mark.style.display = t === 'notify' ? 'flex' : 'none';
        const inp = document.getElementById('inbox_search');
        if (inp) inp.placeholder = t === 'dm' ? '搜索用户名字' : '搜索通知内容';
        if (opts && opts.skipSwitch) return;
        this.loadInboxPage();
    },

    loadInboxPage: async function() {
        if (!this.state.user) return;
        const t = this.state.inboxTab === 'dm' ? 'dm' : 'notify';
        this.switchInboxTab(t, { skipSwitch: true });
        const left = document.getElementById('inbox_left_list');
        const right = document.getElementById('inbox_right_panel');
        if (!left || !right) return;
        if (t === 'dm') await this.loadInboxDMConversations();
        else await this.loadInboxNotifications();
    },

    filterInboxList: function(q) {
        const t = this.state.inboxTab === 'dm' ? 'dm' : 'notify';
        const query = String(q || '').trim().toLowerCase();
        this.state.inboxSearchQuery = query;
        if (t === 'dm') this.renderInboxDMConversations();
        else this.renderInboxNotifications();
    },

    loadHeaderDropdowns: async function() {
        if (!this.state.user) return;
        
        // 1. Notifications
        try {
            const url = `/api/v1/interaction/notifications/${this.state.user.id}`;
            const res = await this.apiRequest('GET', url, undefined, { cancel_key: 'drop:notify', dedupe_key: url });
            const items = res && res.ok ? await res.json() : [];
            const list = document.getElementById('drop_notify_list');
            if (list) {
                if (!items || items.length === 0) {
                    list.innerHTML = '<div style="padding:20px; text-align:center; color:#666; font-size:12px;">暂无新通知</div>';
                } else {
                    list.innerHTML = '';
                    items.slice(0, 5).forEach(n => {
                        const div = document.createElement('div');
                        div.className = 'drop-item';
                        div.innerHTML = `
                            <img src="${n.actor?.avatar || '/static/img/default_avatar.svg'}" class="drop-avatar">
                            <div class="drop-content">
                                <div class="drop-name">${n.actor?.nickname || '用户'}</div>
                                <div class="drop-text">${n.text}</div>
                                <div class="drop-time">${this.fmtTimeAgo(n.created_at ? n.created_at * 1000 : Date.now())}</div>
                            </div>
                        `;
                        try {
                            div.dataset.action = 'call';
                            div.dataset.fn = 'openInbox';
                            div.dataset.args = '["notify"]';
                        } catch (_) {
                        }
                        list.appendChild(div);
                    });
                }
            }
        } catch(e) {}

        try {
            const url2 = `/api/v1/interaction/notifications_unread/${this.state.user.id}`;
            const res = await this.apiRequest('GET', url2, undefined, { cancel_key: 'drop:notify:unread', dedupe_key: url2 });
            if (res && res.ok) {
                const data = await res.json().catch(() => ({}));
                this.updateNotifyBadge(data && data.unread);
            }
        } catch (_) {
        }

        // 2. DMs
        try {
            const url = `/api/v1/messages/conversations?user_id=${this.state.user.id}`;
            const res = await this.apiRequest('GET', url, undefined, { cancel_key: 'dm:convs', dedupe_key: url });
            if (!res.ok) throw new Error(`GET ${url} ${res.status}`);
            const convs = await res.json();
            const list = document.getElementById('drop_dm_list');
            if (list) {
                if (!convs || convs.length === 0) {
                    list.innerHTML = '<div style="padding:20px; text-align:center; color:#666; font-size:12px;">暂无新私信</div>';
                } else {
                    list.innerHTML = '';
                    convs.slice(0, 5).forEach(c => {
                        const div = document.createElement('div');
                        div.className = 'drop-item';
                        div.innerHTML = `
                            <img src="${c.avatar || '/static/img/default_avatar.svg'}" class="drop-avatar">
                            <div class="drop-content">
                                <div class="drop-name">${c.nickname || c.username}</div>
                                <div class="drop-text">点击查看消息</div>
                            </div>
                        `;
                        try {
                            div.dataset.action = 'openInboxPeer';
                            div.dataset.peerId = String(c.id || '');
                            div.dataset.peerMeta = JSON.stringify({ id: c.id, nickname: c.nickname, username: c.username, avatar: c.avatar, aiseek_id: c.aiseek_id });
                            div.dataset.mode = 'dm';
                        } catch (_) {
                        }
                        list.appendChild(div);
                    });
                }
            }
        } catch(e) {}
    },

    loadNotifications: async function() {
        if (!this.state.user) return;
        const list = document.getElementById('notify_list');
        if (!list) return;

        this.state.notifyCursor = null;
        this.state.notifyLoadingMore = false;
        this._notifyLoadedKeys = {};
        list.innerHTML = '<div style="color:#888; padding:10px 0;">加载中...</div>';

        try {
            if (window.appEmit && window.appEventNames) {
                window.appEmit(window.appEventNames.NOTIFY_OPEN, { surface: 'modal' });
            }
        } catch (_) {
        }

        try {
            const res = await this.apiRequest('GET', `/api/v1/interaction/notifications/${this.state.user.id}?limit=120`);
            const nextCursor = res.headers ? res.headers.get('x-next-cursor') : null;
            const items = await res.json();
            list.innerHTML = '';
            const arr = Array.isArray(items) ? items : [];
            if (arr.length === 0) {
                list.innerHTML = '<div style="color:#888; padding:10px 0;">暂无通知</div>';
                this.state.notifyCursor = null;
                return;
            }
            this.appendNotificationItems(arr);
            this.state.notifyCursor = nextCursor || null;
            this.bindNotifyInfiniteScroll();
            try {
                if (window.appEmit && window.appEventNames) {
                    window.appEmit(window.appEventNames.NOTIFY_LOADED, { surface: 'modal', count: arr.length });
                }
            } catch (_) {
            }
        } catch (_) {
            list.innerHTML = '<div style="color:#888; padding:10px 0;">加载失败</div>';
        }
    },

    bindNotifyInfiniteScroll: function() {
        if (this._notifyScrollBound) return;
        const list = document.getElementById('notify_list');
        if (!list) return;
        const handler = () => {
            if (!this.state.user) return;
            if (!this.state.notifyCursor) return;
            if (this.state.notifyLoadingMore) return;
            const near = (list.scrollTop + list.clientHeight) >= (list.scrollHeight - 160);
            if (!near) return;
            this.loadMoreNotifications();
        };
        this._notifyScrollBound = handler;
        list.addEventListener('scroll', handler);
    },

    loadMoreNotifications: async function() {
        if (!this.state.user) return;
        if (this.state.notifyLoadingMore) return;
        if (!this.state.notifyCursor) return;
        const list = document.getElementById('notify_list');
        if (!list) return;

        this.state.notifyLoadingMore = true;
        try {
            const res = await this.apiRequest('GET', `/api/v1/interaction/notifications/${this.state.user.id}?limit=60&cursor=${encodeURIComponent(this.state.notifyCursor)}`);
            const nextCursor = res.headers ? res.headers.get('x-next-cursor') : null;
            const items = await res.json();
            const arr = Array.isArray(items) ? items : [];
            if (arr.length > 0) {
                this.appendNotificationItems(arr);
                try {
                    if (window.appEmit && window.appEventNames) {
                        window.appEmit(window.appEventNames.NOTIFY_LOADED, { surface: 'modal_more', count: arr.length });
                    }
                } catch (_) {
                }
            }
            this.state.notifyCursor = nextCursor || null;
        } catch (_) {
        } finally {
            this.state.notifyLoadingMore = false;
        }
    },

    appendNotificationItems: function(items) {
        const list = document.getElementById('notify_list_items') || document.getElementById('notify_list');
        if (!list) return;
        const loaded = this._notifyLoadedKeys || {};
        this.appendNotificationItemsInto(list, items, loaded, { surface: 'modal' });
        this._notifyLoadedKeys = loaded;
    },

    appendNotificationItemsInto: function(list, items, loaded, opts = {}) {
        if (!list) return;
        const arr = Array.isArray(items) ? items : [];
        const seen = loaded && typeof loaded === 'object' ? loaded : {};
        const lastReadTs = Number.isFinite(Number(opts.last_read_ts)) ? Number(opts.last_read_ts) : 0;
        const allowCloseModal = opts && opts.allow_close_modal !== false;

        arr.forEach(n => {
            const key = (n && n.type === 'friend_request' && n.request_id) ? `friend_request:${n.request_id}`
                : (n && n.type === 'comment' && n.comment_id) ? `comment:${n.comment_id}`
                : (n && n.type === 'dm' && n.message_id) ? `dm:${n.message_id}`
                : (n && n.type === 'follow' && n.actor && n.actor.id && n.created_at) ? `follow:${n.actor.id}:${n.created_at}`
                : `${n && n.type ? n.type : 'unknown'}:${n && n.created_at ? n.created_at : ''}`;
            if (seen[key]) return;
            seen[key] = true;

            const item = document.createElement('div');
            item.classList.add('notify-card');
            item.style.padding = '12px 12px';
            item.style.display = 'flex';
            item.style.gap = '10px';
            item.style.alignItems = 'center';
            item.style.borderRadius = '16px';
            item.style.border = 'none';
            item.style.background = 'transparent';
            item.style.margin = '10px 6px';

            const createdTs = n && n.created_at ? Number(n.created_at) : 0;
            if (lastReadTs && createdTs && createdTs > lastReadTs) {
                item.style.background = 'transparent';
            }

            const a = n.actor || {};
            const avatar = a.avatar || '/static/img/default_avatar.svg';
            const timeTxt = n && n.created_at ? this.formatRelativeTime(n.created_at) : '';

            const actorName = a.nickname || a.username || (a.id ? ('用户' + a.id) : '');
            let actionLine = n && n.text ? String(n.text || '') : '';
            if (actorName && actionLine.startsWith(actorName)) actionLine = actionLine.slice(actorName.length).trim();
            if (actionLine.startsWith('：') || actionLine.startsWith(':')) actionLine = actionLine.slice(1).trim();
            actionLine = actionLine.replace('点赞了你的视频', '赞了你的视频');
            const firstLine = actorName || (n.text || '');
            const secondLine = actorName ? (actionLine || '') : '';

            let actions = '';
            if (n.type === 'friend_request' && n.status === 'pending') {
                actions = `
                    <button class="btn-primary" style="width:auto; font-size:12px; margin-right:6px;" data-action="call" data-fn="handleFriendRequest" data-args='[${n.request_id}, "accepted"]' data-stop="1">同意</button>
                    <button class="btn-primary" style="width:auto; font-size:12px; background:#333;" data-action="call" data-fn="handleFriendRequest" data-args='[${n.request_id}, "rejected"]' data-stop="1">拒绝</button>
                `;
            } else if (n.type === 'friend_request' && n.status && n.status !== 'pending') {
                actions = `<span style="color:rgba(255,255,255,0.55); font-size:12px;">${n.status === 'accepted' ? '已同意' : '已拒绝'}</span>`;
            }

            const postId = n && n.post_id ? Number(n.post_id) : 0;
            let cover = (n && (n.post_cover_url || n.cover_url || n.post_cover)) ? String(n.post_cover_url || n.cover_url || n.post_cover) : '';
            const vurl = (n && (n.post_video_url || n.video_url)) ? String(n.post_video_url || n.video_url) : '';
            if (cover && cover.indexOf('/static/img/default_cover.jpg') !== -1) cover = '';
            const isVideoThumb = (vurl && !(/\.(jpg|jpeg|png|gif|webp)(\?|#|$)/i.test(vurl))) && !/\.m3u8(\?|#|$)/i.test(vurl);
            const snap = postId ? `/api/v1/media/post-thumb/${postId}?v=2&t=${Math.floor(createdTs || 0)}` : '';
            const thumb = postId ? (
                (snap ? `
                    <img src="${snap}" class="notify-thumb" data-action="callClose" data-fn="openPost" data-args="[${postId}]" data-close="notificationModal" data-stop="1">
                ` : (cover ? `
                    <img src="${cover}" class="notify-thumb" data-action="callClose" data-fn="openPost" data-args="[${postId}]" data-close="notificationModal" data-stop="1">
                ` : (isVideoThumb ? `
                    <video class="notify-thumb" src="${vurl}" muted loop autoplay playsinline webkit-playsinline preload="auto" data-action="callClose" data-fn="openPost" data-args="[${postId}]" data-close="notificationModal" data-stop="1"></video>
                ` : '')))
            ) : '';
            item.innerHTML = `
                <img src="${avatar}" class="notify-avatar">
                <div style="flex:1; min-width:0;">
                    <div class="notify-text">${firstLine || ''}</div>
                    ${secondLine ? `<div class="notify-sub">${secondLine}</div>` : ''}
                    ${n.content ? `<div class="notify-sub">${n.content}</div>` : ''}
                    <div class="notify-time">${timeTxt}</div>
                </div>
                ${thumb ? `<div class="notify-right">${thumb}${actions ? `<div class="notify-actions">${actions}</div>` : ''}</div>` : `<div class="notify-actions">${actions}</div>`}
            `;
            try {
                if (n.type === 'dm' && n.peer_id) {
                    item.dataset.action = 'openInboxPeer';
                    item.dataset.peerId = String(n.peer_id || '');
                    item.dataset.peerMeta = JSON.stringify({ id: a.id, nickname: a.nickname, username: a.username, avatar: a.avatar, aiseek_id: a.aiseek_id });
                    item.dataset.mode = 'dm';
                    if (allowCloseModal) item.dataset.close = 'notificationModal';
                } else if (n.type === 'comment' && n.post_id) {
                    item.dataset.action = 'openPostComments';
                    item.dataset.postId = String(n.post_id || '');
                    if (allowCloseModal) item.dataset.close = 'notificationModal';
                } else if ((n.type === 'like' || n.type === 'favorite' || n.type === 'repost') && n.post_id) {
                    item.dataset.action = allowCloseModal ? 'callClose' : 'call';
                    item.dataset.fn = 'openPost';
                    item.dataset.args = JSON.stringify([Number(n.post_id)]);
                    if (allowCloseModal) item.dataset.close = 'notificationModal';
                } else if (n.type === 'follow' && a.id) {
                    item.dataset.action = allowCloseModal ? 'callClose' : 'call';
                    item.dataset.fn = 'viewUserProfile';
                    item.dataset.args = JSON.stringify([a.id]);
                    if (allowCloseModal) item.dataset.close = 'notificationModal';
                } else if (n.type === 'friend_request' && a.id) {
                    item.dataset.action = 'call';
                    item.dataset.fn = 'viewUserProfile';
                    item.dataset.args = JSON.stringify([a.id]);
                }
            } catch (_) {
            }

            list.appendChild(item);
            try {
                const v = item.querySelector && item.querySelector('video.notify-thumb');
                if (v) {
                    v.muted = true;
                    const kick = () => {
                        try { v.currentTime = Math.max(0.1, Number(v.currentTime || 0)); } catch (_) {}
                        try { v.play().then(() => {}).catch(() => {}); } catch (_) {}
                    };
                    v.addEventListener('loadeddata', kick, { once: true });
                    v.addEventListener('canplay', kick, { once: true });
                    kick();
                }
            } catch (_) {
            }
        });
    },

    handleFriendRequest: async function(reqId, status) {
        try {
            const res = await this.apiRequest('POST', '/api/v1/users/friend-request/handle', { request_id: reqId, status: status });
            if (res.ok) {
                this.loadNotifications();
                const inbox = document.getElementById('page-inbox');
                if (inbox && inbox.classList.contains('active')) this.loadInboxPage();
            }
        } catch (_) {
            alert('操作失败');
        }
    },

    loadUserHoverStats: async function() {
        if (!this.state.user) return;
        if (this._hoverStatsLoading) return;
        const now = Date.now();
        if (this._hoverStatsAt && (now - this._hoverStatsAt) < 15000) return;
        this._hoverStatsLoading = true;
        try {
            const uid = this.state.user.id;
            const urlA = `/api/v1/interaction/likes/${uid}`;
            const urlB = `/api/v1/interaction/favorites/${uid}`;
            const urlC = `/api/v1/posts/user/${uid}`;
            const [likesRes, favRes, worksRes] = await Promise.all([
                this.apiRequest('GET', urlA, undefined, { cancel_key: 'um:likes', dedupe_key: urlA }),
                this.apiRequest('GET', urlB, undefined, { cancel_key: 'um:favs', dedupe_key: urlB }),
                this.apiRequest('GET', urlC, undefined, { cancel_key: 'um:works', dedupe_key: urlC })
            ]);
            const likes = likesRes && likesRes.ok ? await likesRes.json() : [];
            const favs = favRes && favRes.ok ? await favRes.json() : [];
            const works = worksRes && worksRes.ok ? await worksRes.json() : [];

            const likesEl = document.getElementById('umLikes');
            const favEl = document.getElementById('umFavs');
            const worksEl = document.getElementById('umWorks');
            if (likesEl) likesEl.innerText = Array.isArray(likes) ? likes.length : 0;
            if (favEl) favEl.innerText = Array.isArray(favs) ? favs.length : 0;
            if (worksEl) worksEl.innerText = Array.isArray(works) ? works.length : 0;

            this._hoverStatsAt = Date.now();
        } catch (_) {
        } finally {
            this._hoverStatsLoading = false;
        }
    },

    startChat: function(targetUserId, peerMeta) {
        const meta = (peerMeta && typeof peerMeta === 'object')
            ? peerMeta
            : { nickname: peerMeta || ('用户' + targetUserId) };
        const action = { type: 'open_inbox', tab: 'dm', peer_id: targetUserId, peer_meta: meta };
        if (typeof this.ensureAuth === 'function') {
            if (!this.ensureAuth(action)) return;
        } else if (!this.state.user) {
            this.state.pendingAuthAction = action;
            this.openModal('authModal');
            return;
        }
        try { this.state.dmFriendIdsLoadedAt = 0; } catch (_) {}
        this.state.inboxPendingPeer = { id: targetUserId, meta };
        this.openInbox('dm');
        setTimeout(() => {
            try { this.openDMThread(Number(targetUserId), meta); } catch (_) {}
        }, 0);
    },

    dmSearchUsers: async function(query) {
        if (!this.state.user) return;
        const q = String(query || '').trim();
        this.state.dmSearchQuery = q;

        const list = document.getElementById('dm_conv_list');
        if (!list) return;

        if (!q) {
            try { await this.loadDMConversations(); } catch (_) {}
            return;
        }

        list.innerHTML = '<div style="color:#888; padding:10px;">搜索中...</div>';
        try {
            const url = `/api/v1/users/search-user?query=${encodeURIComponent(q)}`;
            const res = await this.apiRequest('GET', url, undefined, { cancel_key: `dm:search:${q}`, dedupe_key: url });
            if (!res.ok) throw new Error('search failed');
            const users = await res.json();
            if (!Array.isArray(users) || users.length === 0) {
                list.innerHTML = '<div style="color:#888; padding:10px;">无结果</div>';
                return;
            }
            list.innerHTML = '';
            users.slice(0, 20).forEach(u => {
                if (!u || !u.id) return;
                const item = document.createElement('div');
                item.classList.add('dm-conv-item');
                item.style.display = '';
                item.style.alignItems = '';
                item.style.justifyContent = '';
                item.style.padding = '';
                item.style.borderRadius = '';
                item.style.cursor = 'pointer';
                item.style.marginBottom = '0';
                item.style.background = 'transparent';
                item.innerHTML = `
                    <img src="${u.avatar || '/static/img/default_avatar.svg'}" style="width:44px; height:44px; border-radius:14px; object-fit:cover;">
                    <div class="dm-meta">
                        <div class="dm-name">${u.nickname || u.username || ('用户'+u.id)}</div>
                    </div>
                `;
                try {
                    item.dataset.action = 'call';
                    item.dataset.fn = 'openDMThread';
                    item.dataset.args = JSON.stringify([u.id, { id: u.id, nickname: u.nickname, username: u.username, avatar: u.avatar, aiseek_id: u.aiseek_id }]);
                } catch (_) {
                }
                list.appendChild(item);
            });
        } catch (_) {
            list.innerHTML = '<div style="color:#888; padding:10px;">搜索失败</div>';
        }
    },

    loadDMConversations: async function() {
        if (!this.state.user) return;

        const list = document.getElementById('dm_conv_list');
        const box = document.getElementById('dm_chat_box');
        const header = document.getElementById('dm_chat_header_name');
        if (list) list.innerHTML = '<div style="color:#888; padding:10px;">加载中...</div>';
        if (box) box.innerHTML = '';
        if (header) header.innerText = '选择一个会话';
        try { this.closeDMMoreMenu(); } catch (_) {}
        try {
            this.state.dmNonFriendSentIds = this.getDmIdSet('dm_nonfriend_once_ids');
        } catch (_) {
        }
        try {
            if (!this.state.dmFriendIdsLoadedAt || (Date.now() - Number(this.state.dmFriendIdsLoadedAt || 0)) > 15000) {
                const url = `/api/v1/users/friends/list?user_id=${this.state.user.id}`;
                const res = await this.apiRequest('GET', url, undefined, { cancel_key: 'dm:friends', dedupe_key: url });
                const arr = res && res.ok ? await res.json() : [];
                const ids = new Set();
                (Array.isArray(arr) ? arr : []).forEach(x => {
                    try {
                        const u = (x && x.friend_user) ? x.friend_user : x;
                        const id = Number(u && u.id ? u.id : 0);
                        if (id) ids.add(id);
                    } catch (_) {
                    }
                });
                this.state.dmFriendIds = ids;
                this.state.dmFriendIdsLoadedAt = Date.now();
            }
        } catch (_) {
        }

        try {
            const url = `/api/v1/messages/conversations?user_id=${this.state.user.id}`;
            const res = await this.apiRequest('GET', url, undefined, { cancel_key: 'dm:convs2', dedupe_key: url });
            const convs = res && res.ok ? await res.json() : [];
            const pinned = this.getDmIdSet('dm_pin_ids');
            const deletedMap = this.getDmIdMap('dm_deleted_map');
            const blocked = this.getDmIdSet('dm_block_ids');
            const filtered = Array.isArray(convs) ? convs.filter(u => {
                const pid = Number(u && u.id ? u.id : 0);
                if (!pid) return false;
                if (blocked.has(pid)) return false;
                try {
                    const delAt = Number(deletedMap && deletedMap[pid] ? deletedMap[pid] : 0);
                    if (delAt) {
                        const lastAt = Number(u && u.last_at ? u.last_at : 0);
                        if (lastAt && lastAt > (delAt / 1000)) {
                            delete deletedMap[pid];
                            this.setDmIdMap('dm_deleted_map', deletedMap);
                            return true;
                        }
                        return false;
                    }
                } catch (_) {
                }
                return true;
            }) : [];
            filtered.sort((a, b) => {
                const pa = pinned.has(Number(a && a.id ? a.id : 0)) ? 1 : 0;
                const pb = pinned.has(Number(b && b.id ? b.id : 0)) ? 1 : 0;
                if (pa !== pb) return pb - pa;
                return Number(b && b.id ? b.id : 0) - Number(a && a.id ? a.id : 0);
            });

            const pending = this.state.inboxPendingPeer;
            if ((!Array.isArray(filtered) || filtered.length === 0) && pending && pending.id) {
                this.state.inboxPendingPeer = null;
                if (list) {
                    list.innerHTML = '';
                    const item = document.createElement('div');
                    item.classList.add('dm-conv-item', 'dm-hover-item', 'active');
                    const meta = pending.meta || { id: Number(pending.id) };
                    item.innerHTML = `
                        <img src="${meta.avatar || '/static/img/default_avatar.svg'}" style="width:44px; height:44px; border-radius:14px; object-fit:cover;">
                        <div class="dm-meta">
                            <div class="dm-name">${meta.nickname || meta.username || ('用户' + pending.id)}</div>
                        </div>
                    `;
                    try {
                        item.dataset.peerId = String(pending.id || '');
                        item.dataset.action = 'call';
                        item.dataset.fn = 'openDMThread';
                        item.dataset.args = JSON.stringify([pending.id, meta]);
                    } catch (_) {
                    }
                    list.appendChild(item);
                }
                this.openDMThread(Number(pending.id), pending.meta || { id: Number(pending.id) });
            } else if (!Array.isArray(filtered) || filtered.length === 0) {
                if (list) list.innerHTML = '<div style="color:#888; padding:10px;">暂无会话</div>';
            } else {
                if (list) list.innerHTML = '';
                filtered.forEach(u => {
                    const item = document.createElement('div');
                    item.classList.add('dm-conv-item');
                    item.style.display = '';
                    item.style.alignItems = '';
                    item.style.justifyContent = '';
                    item.style.padding = '';
                    item.style.borderRadius = '';
                    item.style.cursor = 'pointer';
                    item.classList.add('dm-hover-item');
                    try { item.dataset.peerId = String(u.id || ''); } catch (_) {}
                    item.innerHTML = `
                        <img src="${u.avatar || '/static/img/default_avatar.svg'}" style="width:44px; height:44px; border-radius:14px; object-fit:cover;">
                        <div class="dm-meta">
                            <div class="dm-name">${u.nickname || u.username || ('用户'+u.id)}</div>
                        </div>
                    `;
                    try {
                        item.dataset.action = 'call';
                        item.dataset.fn = 'openDMThread';
                        item.dataset.args = JSON.stringify([u.id, { id: u.id, nickname: u.nickname, username: u.username, avatar: u.avatar, aiseek_id: u.aiseek_id }]);
                    } catch (_) {
                    }
                    list.appendChild(item);
                });

                try {
                    if (pending && pending.id) {
                        this.state.inboxPendingPeer = null;
                        this.openDMThread(Number(pending.id), pending.meta || { id: Number(pending.id) });
                    } else {
                        const first = filtered && filtered[0];
                        if (first && first.id) this.openDMThread(Number(first.id), { id: first.id, nickname: first.nickname, username: first.username, avatar: first.avatar, aiseek_id: first.aiseek_id });
                    }
                } catch (_) {
                }
            }

            if (this.state.dmPollTimer) clearInterval(this.state.dmPollTimer);
            this.state.dmPollTimer = setInterval(() => {
                const modal = document.getElementById('messageModal');
                if (!modal || !modal.classList.contains('active')) return;
                if (!this.state.dmPeerId) return;
                this.loadDMThread(this.state.dmPeerId);
            }, 2500);
        } catch(e) {
            if (list) list.innerHTML = '<div style="color:#888; padding:10px;">加载失败</div>';
        }
    },

    openDMThreadFromInput: function() {
        const input = document.getElementById('dm_new_target');
        if (!input || !input.value) return;
        const id = parseInt(input.value, 10);
        if (isNaN(id)) return alert('请输入用户ID数字');
        input.value = '';
        this.openDMThread(id);
    },

    openDMThread: async function(peerId, peerMeta = null) {
        this.state.dmPeerId = peerId;
        this.state.dmPeerMeta = peerMeta || { id: peerId };
        try { this.dmUndeletePeer(peerId); } catch (_) {}
        try { this.closeDMMoreMenu(); } catch (_) {}
        const header = document.getElementById('dm_chat_header_name');
        if (header) header.innerText = peerMeta ? (peerMeta.nickname || peerMeta.username || ('用户'+peerId)) : ('用户' + peerId);
        try { this.dmUpdateComposerState(); } catch (_) {}
        try {
            const items = document.querySelectorAll('#dm_conv_list .dm-conv-item');
            Array.from(items).forEach((x) => x.classList.toggle('active', String(x.dataset.peerId || '') === String(peerId)));
        } catch (_) {
        }
        await this.loadDMThread(peerId);
    },

    dmIsFriend: function(peerId) {
        try {
            const id = Number(peerId || 0);
            const s = this.state.dmFriendIds;
            return !!(id && s && typeof s.has === 'function' && s.has(id));
        } catch (_) {
            return false;
        }
    },

    dmUpdateComposerState: function() {
        const peerId = Number(this.state.dmPeerId || 0);
        const input = document.getElementById('dm_input');
        const sendBtn = document.getElementById('dm_send_btn');
        const imgBtn = document.getElementById('dm_img_btn');
        if (!input || !sendBtn || !imgBtn) return;
        const isFriend = this.dmIsFriend(peerId);
        const sentOnce = this.state.dmNonFriendSentIds && typeof this.state.dmNonFriendSentIds.has === 'function' ? this.state.dmNonFriendSentIds.has(peerId) : false;
        const canText = isFriend || !sentOnce;
        input.disabled = !canText;
        if (!canText) input.value = '';
        try { sendBtn.classList.toggle('disabled', !canText); } catch (_) {}
        try { imgBtn.classList.toggle('disabled', !isFriend); } catch (_) {}
    },

    dmInputKeydown: function(el, ev) {
        try {
            if (!ev) return;
            if (ev.key !== 'Enter') return;
            if (ev.shiftKey) return;
            ev.preventDefault();
        } catch (_) {
        }
        try { this.sendDMMessage(); } catch (_) {}
    },

    dmInsertEmoji: function() {
        const input = document.getElementById('dm_input');
        if (!input) return;
        try {
            const v = String(input.value || '');
            input.value = v + '😊';
            input.focus();
        } catch (_) {
        }
    },

    dmToggleEmojiPanel: function() {
        const panel = document.getElementById('dm_emoji_panel');
        if (!panel) return;
        try {
            const active = panel.classList.contains('active');
            if (active) {
                panel.classList.remove('active');
                return;
            }
            panel.classList.add('active');
        } catch (_) {
        }
        try { this.dmRenderEmojiPanel(this.state.dmEmojiTab || 'smileys'); } catch (_) {}
    },

    dmRenderEmojiPanel: function(tab) {
        const panel = document.getElementById('dm_emoji_panel');
        if (!panel) return;
        const key = String(tab || 'smileys');
        this.state.dmEmojiTab = key;
        const sets = {
            smileys: '😀 😃 😄 😁 😆 😅 😂 🤣 😊 😇 🙂 🙃 😉 😌 😍 🥰 😘 😗 😙 😚 😋 😛 😜 🤪 😝 🤑 🤗 🤭 🤫 🤔 🤐 🤨 😐 😑 😶 😏 😒 🙄 😬 😮‍💨 😌'.split(' '),
            gestures: '👍 👎 👌 ✌️ 🤞 🤟 🤘 🤙 👊 ✊ 🤛 🤜 👏 🙌 🫶 👐 🤲 🤝 🙏 ✍️ 💪 🦾 🏃‍♂️ 🏃‍♀️ 🧎‍♂️ 🧎‍♀️ 🧠'.split(' '),
            animals: '🐶 🐱 🐭 🐹 🐰 🦊 🐻 🐼 🐨 🐯 🦁 🐮 🐷 🐸 🐵 🙈 🙉 🙊 🐔 🐧 🐦 🐤 🦆 🦉 🦇 🐺 🐗 🐴 🦄 🐝 🐛 🦋 🐌 🐞 🐢 🐍 🦖 🦕'.split(' '),
            food: '🍎 🍐 🍊 🍋 🍌 🍉 🍇 🍓 🫐 🍒 🍑 🥭 🍍 🥥 🥝 🍅 🥑 🥦 🥬 🥒 🌶️ 🧄 🧅 🥔 🍠 🍞 🥐 🥨 🥯 🧀 🍗 🍖 🍔 🍟 🍕 🌭 🥪 🌮 🌯 🥗 🍣 🍱'.split(' '),
            travel: '🚗 🚕 🚙 🚌 🚎 🚓 🚑 🚒 🚐 🛻 🚚 🚛 🚜 🏍️ 🚲 ✈️ 🛫 🛬 🚀 🛰️ 🚁 🚢 🛳️ ⛴️ 🚤 🚉 🚇 🚆 🚄 🚅 🗺️ 🧭 🏝️ 🏖️ 🏕️ 🏜️ 🏟️ 🎡 🎢'.split(' '),
            objects: '⌚ 📱 💻 🖥️ 🖨️ 🖱️ 🎧 🎤 📷 📸 🔦 💡 🔌 🔋 🧯 🔑 🗝️ 💎 🧲 🪜 🧰 🧪 🧫 🧬 📌 📍 ✂️ 🖊️ 🖋️ 🗒️ 📄 📚 🔒 🔓 🔔 🔕 🧿'.split(' '),
        };
        const tabs = [
            { k: 'smileys', t: '表情' },
            { k: 'gestures', t: '手势' },
            { k: 'animals', t: '动物' },
            { k: 'food', t: '食物' },
            { k: 'travel', t: '出行' },
            { k: 'objects', t: '物品' },
        ];
        const arr = Array.isArray(sets[key]) ? sets[key] : sets.smileys;
        const tabHtml = tabs.map(x => `<div class="dm-emoji-tab ${x.k===key?'active':''}" data-action="call" data-fn="dmRenderEmojiPanel" data-args='[${JSON.stringify(x.k)}]' data-stop="1">${x.t}</div>`).join('');
        const gridHtml = arr.map(e => `<div class="dm-emoji-item" data-action="call" data-fn="dmPickEmoji" data-args='[${JSON.stringify(e)}]' data-stop="1">${e}</div>`).join('');
        panel.innerHTML = `<div class="dm-emoji-top"><div class="dm-emoji-tabs">${tabHtml}</div><div class="dm-emoji-tab" data-action="call" data-fn="dmToggleEmojiPanel" data-args="[]" data-stop="1">关闭</div></div><div class="dm-emoji-grid">${gridHtml}</div>`;
    },

    dmPickEmoji: function(emoji) {
        const input = document.getElementById('dm_input');
        if (!input) return;
        const e = String(emoji || '');
        if (!e) return;
        try {
            const start = Number.isFinite(input.selectionStart) ? input.selectionStart : String(input.value || '').length;
            const end = Number.isFinite(input.selectionEnd) ? input.selectionEnd : String(input.value || '').length;
            const v = String(input.value || '');
            input.value = v.slice(0, start) + e + v.slice(end);
            const pos = start + e.length;
            input.setSelectionRange(pos, pos);
            input.focus();
        } catch (_) {
            try {
                input.value = String(input.value || '') + e;
                input.focus();
            } catch (_) {}
        }
        try {
            const panel = document.getElementById('dm_emoji_panel');
            if (panel) panel.classList.remove('active');
        } catch (_) {
        }
    },

    dmPickImage: function() {
        const peerId = Number(this.state.dmPeerId || 0);
        if (!peerId) return;
        if (!this.dmIsFriend(peerId)) {
            try { this.showToast('未成为好友，不能发送图片'); } catch (_) {}
            return;
        }
        const file = document.getElementById('dm_img_file');
        if (!file || typeof file.click !== 'function') return;
        try { this.state.dmFilePickingUntil = Date.now() + 12000; } catch (_) {}
        try {
            const clear = () => {
                try { this.state.dmFilePickingUntil = 0; } catch (_) {}
                try { window.removeEventListener('focus', clear); } catch (_) {}
            };
            window.addEventListener('focus', clear);
        } catch (_) {
        }
        try { file.click(); } catch (_) {}
    },

    dmSendImage: async function(fileInput) {
        if (!this.state.user) return this.openModal('authModal');
        const peerId = Number(this.state.dmPeerId || 0);
        if (!peerId) return;
        if (!this.dmIsFriend(peerId)) {
            try { this.showToast('未成为好友，不能发送图片'); } catch (_) {}
            try { if (fileInput) fileInput.value = ''; } catch (_) {}
            return;
        }
        try { this.dmUndeletePeer(peerId); } catch (_) {}
        try {
            const f = fileInput && fileInput.files && fileInput.files[0] ? fileInput.files[0] : null;
            if (!f) return;
            const fd = new FormData();
            fd.append('file', f);
            const up = await this.apiRequest('POST', '/api/v1/upload/local', fd, { cancel_key: 'dm:upload' });
            const data = up && up.ok ? await up.json() : null;
            const url = data && data.url ? String(data.url || '') : '';
            if (!url) return;
            const content = `[img]${url}`;
            const res = await this.apiRequest('POST', '/api/v1/messages/send', { sender_id: this.state.user.id, receiver_id: peerId, content }, { cancel_key: `dm:sendimg:${peerId}` });
            if (res && res.ok) await this.loadDMThread(peerId);
        } catch (_) {
        } finally {
            try { if (fileInput) fileInput.value = ''; } catch (_) {}
        }
    },

    getDmIdSet: function(key) {
        try {
            const raw = localStorage.getItem(String(key || ''));
            if (!raw) return new Set();
            const arr = JSON.parse(raw);
            if (!Array.isArray(arr)) return new Set();
            return new Set(arr.map(x => Number(x)).filter(x => x && Number.isFinite(x)));
        } catch (_) {
            return new Set();
        }
    },

    getDmIdMap: function(key) {
        try {
            const raw = localStorage.getItem(String(key || ''));
            if (!raw) return {};
            const obj = JSON.parse(raw);
            if (!obj || typeof obj !== 'object') return {};
            return obj;
        } catch (_) {
            return {};
        }
    },

    setDmIdSet: function(key, set) {
        try {
            const arr = Array.from(set || []).map(x => Number(x)).filter(x => x && Number.isFinite(x));
            localStorage.setItem(String(key || ''), JSON.stringify(arr));
        } catch (_) {
        }
    },

    setDmIdMap: function(key, obj) {
        try {
            localStorage.setItem(String(key || ''), JSON.stringify(obj || {}));
        } catch (_) {
        }
    },

    dmUndeletePeer: function(peerId) {
        const pid = Number(peerId || 0);
        if (!pid) return;
        const m = this.getDmIdMap('dm_deleted_map');
        if (m && m[pid]) {
            delete m[pid];
            this.setDmIdMap('dm_deleted_map', m);
        }
    },

    toggleDMMoreMenu: function() {
        const menu = document.getElementById('dm_more_menu');
        if (!menu) return;
        try { menu.classList.toggle('active'); } catch (_) {}
    },

    closeDMMoreMenu: function() {
        const menu = document.getElementById('dm_more_menu');
        if (!menu) return;
        try { menu.classList.remove('active'); } catch (_) {}
    },

    dmToggleDnd: function() {
        const pid = Number(this.state.dmPeerId || 0);
        if (!pid) return;
        const s = this.getDmIdSet('dm_dnd_ids');
        if (s.has(pid)) s.delete(pid);
        else s.add(pid);
        this.setDmIdSet('dm_dnd_ids', s);
        this.closeDMMoreMenu();
        try { this.showToast(s.has(pid) ? '已开启免打扰' : '已关闭免打扰'); } catch (_) {}
    },

    dmTogglePin: function() {
        const pid = Number(this.state.dmPeerId || 0);
        if (!pid) return;
        const s = this.getDmIdSet('dm_pin_ids');
        if (s.has(pid)) s.delete(pid);
        else s.add(pid);
        this.setDmIdSet('dm_pin_ids', s);
        this.closeDMMoreMenu();
        try { this.showToast(s.has(pid) ? '已置顶聊天' : '已取消置顶'); } catch (_) {}
        try { this.loadDMConversations(); } catch (_) {}
    },

    dmDeleteChat: function() {
        const pid = Number(this.state.dmPeerId || 0);
        if (!pid) return;
        const m = this.getDmIdMap('dm_deleted_map');
        m[pid] = Date.now();
        this.setDmIdMap('dm_deleted_map', m);
        this.state.dmPeerId = null;
        this.state.dmPeerMeta = null;
        this.closeDMMoreMenu();
        try {
            const header = document.getElementById('dm_chat_header_name');
            if (header) header.innerText = '选择一个会话';
            const box = document.getElementById('dm_chat_box');
            if (box) box.innerHTML = '';
        } catch (_) {
        }
        try { this.showToast('已删除聊天'); } catch (_) {}
        try { this.loadDMConversations(); } catch (_) {}
    },

    dmReportChat: function() {
        this.closeDMMoreMenu();
        try { this.showToast('已提交举报'); } catch (_) {}
    },

    dmBlockUser: function() {
        const pid = Number(this.state.dmPeerId || 0);
        if (!pid) return;
        const s = this.getDmIdSet('dm_block_ids');
        s.add(pid);
        this.setDmIdSet('dm_block_ids', s);
        this.closeDMMoreMenu();
        try { this.showToast('已拉黑'); } catch (_) {}
        try { this.dmDeleteChat(); } catch (_) {}
    },

    formatRelativeTime: function(tsSec) {
        const t = Number(tsSec || 0);
        if (!t || !Number.isFinite(t)) return '';
        const now = Date.now() / 1000;
        let diff = Math.max(0, now - t);
        const minute = 60;
        const hour = 60 * minute;
        const day = 24 * hour;
        const month = 30 * day;
        const year = 365 * day;
        if (diff < minute) return '1分钟前';
        if (diff < hour) return `${Math.floor(diff / minute)}分钟前`;
        if (diff < day) return `${Math.floor(diff / hour)}小时前`;
        if (diff < month) return `${Math.floor(diff / day)}天前`;
        if (diff < year) return `${Math.floor(diff / month)}个月前`;
        return `${Math.floor(diff / year)}年前`;
    },

    loadDMThread: async function(peerId) {
        if (!this.state.user) return;
        const box = document.getElementById('dm_chat_box');
        if (!box) return;

        try {
            const url = `/api/v1/messages/list?user_id=${this.state.user.id}&other_id=${peerId}`;
            const res = await this.apiRequest('GET', url, undefined, { cancel_key: `dm:thread:${peerId}`, dedupe_key: url });
            if (!res.ok) throw new Error(`GET ${url} ${res.status}`);
            const msgs = await res.json();
            box.innerHTML = '';
            if (!Array.isArray(msgs) || msgs.length === 0) {
                box.innerHTML = '<div style="color:#888; padding:10px; text-align:center;">开始聊天吧</div>';
                return;
            }

            let lastTs = 0;
            msgs.forEach(m => {
                const ts = m.created_at ? new Date(m.created_at).getTime() : 0;
                if (ts && (!lastTs || Math.abs(ts - lastTs) > 5 * 60 * 1000)) {
                    const t = document.createElement('div');
                    t.style.textAlign = 'center';
                    t.style.color = 'rgba(255,255,255,0.45)';
                    t.style.fontSize = '12px';
                    t.style.margin = '10px 0';
                    t.innerText = this.fmtDateTime(m.created_at);
                    box.appendChild(t);
                    lastTs = ts;
                }

                const mine = m.sender_id === this.state.user.id;
                const row = document.createElement('div');
                row.style.display = 'flex';
                row.style.justifyContent = mine ? 'flex-end' : 'flex-start';
                row.style.margin = '8px 0';

                const bubble = document.createElement('div');
                bubble.style.maxWidth = '68%';
                bubble.style.padding = '10px 12px';
                bubble.style.borderRadius = mine ? '16px 16px 6px 16px' : '16px 16px 16px 6px';
                bubble.style.background = mine ? 'rgba(254,44,85,0.95)' : 'rgba(255,255,255,0.10)';
                bubble.style.color = 'white';
                bubble.style.fontSize = '14px';
                bubble.style.lineHeight = '1.5';
                try {
                    const raw = String(m.content || '');
                    if (raw.startsWith('[img]')) {
                        const url = raw.slice(5).trim();
                        const ok = url && (url.startsWith('/static/') || url.startsWith('http://') || url.startsWith('https://'));
                        if (ok) {
                            bubble.style.padding = '8px';
                            const img = document.createElement('img');
                            img.src = url;
                            img.style.display = 'block';
                            img.style.maxWidth = '240px';
                            img.style.maxHeight = '240px';
                            img.style.borderRadius = '12px';
                            img.style.objectFit = 'cover';
                            img.style.cursor = 'pointer';
                            img.addEventListener('click', () => {
                                try { window.open(url, '_blank'); } catch (_) {}
                            });
                            bubble.appendChild(img);
                        } else {
                            bubble.innerText = raw;
                        }
                    } else {
                        bubble.innerText = raw;
                    }
                } catch (_) {
                    bubble.innerText = String(m.content || '');
                }
                row.appendChild(bubble);
                box.appendChild(row);
            });

            box.scrollTop = box.scrollHeight;
        } catch(e) {
            box.innerHTML = '<div style="color:#888; padding:10px;">加载失败</div>';
        }
    },

    sendDMMessage: async function() {
        if (!this.state.user) return this.openModal('authModal');
        if (!this.state.dmPeerId) return;
        const input = document.getElementById('dm_input');
        if (!input || !input.value) return;
        const peerId = Number(this.state.dmPeerId || 0);
        const isFriend = this.dmIsFriend(peerId);
        const sentOnce = this.state.dmNonFriendSentIds && typeof this.state.dmNonFriendSentIds.has === 'function' ? this.state.dmNonFriendSentIds.has(peerId) : false;
        if (!isFriend && sentOnce) {
            try { this.showToast('未成为好友，只能发送一条消息'); } catch (_) {}
            try { this.dmUpdateComposerState(); } catch (_) {}
            return;
        }
        try { this.dmUndeletePeer(peerId); } catch (_) {}
        const content = String(input.value || '');
        input.value = '';

        try {
            const res = await this.apiRequest('POST', '/api/v1/messages/send', { sender_id: this.state.user.id, receiver_id: this.state.dmPeerId, content }, { cancel_key: `dm:send:${peerId}` });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const d = data && (data.detail || data.message) ? (data.detail || data.message) : `发送失败(${res.status})`;
                try { this.showToast(typeof d === 'string' ? d : '发送失败'); } catch (_) {}
                return;
            }
            await this.loadDMThread(this.state.dmPeerId);
            try { this.loadDMConversations(); } catch (_) {}
            if (!isFriend) {
                try {
                    if (!this.state.dmNonFriendSentIds || typeof this.state.dmNonFriendSentIds.add !== 'function') this.state.dmNonFriendSentIds = new Set();
                    this.state.dmNonFriendSentIds.add(peerId);
                    this.setDmIdSet('dm_nonfriend_once_ids', this.state.dmNonFriendSentIds);
                } catch (_) {
                }
                try { this.dmUpdateComposerState(); } catch (_) {}
            }
        } catch(e) {
            const msg = e && e.message ? String(e.message) : '发送失败';
            try { this.showToast(msg); } catch (_) {}
        }
    },

    setInboxNotifyFilter: function(k) {
        const key = k === 'interaction' ? 'interaction' : (k === 'system' ? 'system' : 'all');
        this.state.inboxNotifyFilter = key;
        this.renderInboxNotifications();
    },

    loadInboxNotifications: async function() {
        if (!this.state.user) return;
        const left = document.getElementById('inbox_left_list');
        const right = document.getElementById('inbox_right_panel');
        if (!left || !right) return;

        left.innerHTML = '<div style="padding:20px; text-align:center; color:#666;">加载中...</div>';
        right.innerHTML = '<div style="color:#666; text-align:center; padding:30px;">加载中...</div>';

        const now = Date.now();
        const cacheAt = this.state._inboxNotifyLoadedAt || 0;
        if (this.state._inboxNotifyItems && (now - cacheAt) < 4000) {
            this.renderInboxNotifications();
            return;
        }

        try {
            const [unreadRes, listRes] = await Promise.all([
                this.apiRequest('GET', `/api/v1/interaction/notifications_unread/${this.state.user.id}`, undefined, { cancel_key: 'inbox:notify:unread', dedupe_key: `inbox:notify:unread:${this.state.user.id}` }),
                this.apiRequest('GET', `/api/v1/interaction/notifications/${this.state.user.id}?limit=200`, undefined, { cancel_key: 'inbox:notify:list' })
            ]);
            const unread = unreadRes && unreadRes.ok ? await unreadRes.json() : null;
            const items = listRes && listRes.ok ? await listRes.json() : [];

            this.state._inboxLastReadTs = unread && unread.last_read_ts ? Number(unread.last_read_ts) : 0;
            this.state._inboxNotifyUnread = unread && unread.unread ? Number(unread.unread) : 0;
            this.state._inboxNotifyItems = Array.isArray(items) ? items : [];
            this.state._inboxNotifyLoadedAt = Date.now();
            if (!this.state.inboxNotifyFilter) this.state.inboxNotifyFilter = 'all';
            this.renderInboxNotifications();
        } catch (_) {
            left.innerHTML = '<div style="padding:20px; text-align:center; color:#666;">加载失败</div>';
            right.innerHTML = '<div style="color:#666; text-align:center; padding:30px;">加载失败</div>';
        }
    },

    renderInboxNotifications: function() {
        if (!this.state.user) return;
        const left = document.getElementById('inbox_left_list');
        const right = document.getElementById('inbox_right_panel');
        if (!left || !right) return;

        const items = Array.isArray(this.state._inboxNotifyItems) ? this.state._inboxNotifyItems : [];
        const lastRead = Number.isFinite(Number(this.state._inboxLastReadTs)) ? Number(this.state._inboxLastReadTs) : 0;
        const filter = this.state.inboxNotifyFilter || 'all';
        const q = String(this.state.inboxSearchQuery || '').trim().toLowerCase();

        const classify = (n) => {
            const t = n && n.type ? String(n.type) : '';
            if (t === 'comment' || t === 'follow' || t === 'friend_request' || t === 'dm') return 'interaction';
            return 'system';
        };

        const counts = { all: 0, interaction: 0, system: 0, unread: 0 };
        items.forEach(n => {
            counts.all += 1;
            const c = classify(n);
            counts[c] += 1;
            const ts = n && n.created_at ? Number(n.created_at) : 0;
            if (lastRead && ts && ts > lastRead) counts.unread += 1;
        });

        const mkRow = (id, label, key, badge) => {
            const active = filter === key;
            const bg = active ? 'rgba(255,255,255,0.08)' : 'transparent';
            const color = active ? 'white' : 'rgba(255,255,255,0.82)';
            return `
                <div id="${id}" style="padding:10px 12px; border-radius:12px; cursor:pointer; display:flex; align-items:center; justify-content:space-between; background:${bg}; color:${color};" data-action="call" data-fn="setInboxNotifyFilter" data-args='[${JSON.stringify(key)}]'>
                    <span>${label}</span>
                    <span style="color:rgba(255,255,255,0.55); font-size:12px;">${badge}</span>
                </div>
            `;
        };

        left.innerHTML = `
            <div style="display:flex; flex-direction:column; gap:8px;">
                ${mkRow('inbox_nf_all', '全部通知', 'all', counts.all)}
                ${mkRow('inbox_nf_interaction', '互动通知', 'interaction', counts.interaction)}
                ${mkRow('inbox_nf_system', '系统通知', 'system', counts.system)}
                <div style="height:10px;"></div>
                <div style="color:rgba(255,255,255,0.55); font-size:12px; padding:0 6px;">未读 ${counts.unread}</div>
            </div>
        `;

        const filtered = items.filter(n => {
            const c = classify(n);
            if (filter !== 'all' && c !== filter) return false;
            if (!q) return true;
            const text = `${n && n.text ? n.text : ''} ${n && n.content ? n.content : ''}`.toLowerCase();
            return text.includes(q);
        });

        right.innerHTML = `
            <div id="inbox_notify_items" style="min-height:0;"></div>
        `;
        const list = document.getElementById('inbox_notify_items');
        if (!list) return;
        list.innerHTML = '';
        if (filtered.length === 0) {
            list.innerHTML = '<div style="color:#888; padding:10px;">暂无通知</div>';
            return;
        }
        const loaded = {};
        this.appendNotificationItemsInto(list, filtered, loaded, { last_read_ts: lastRead, allow_close_modal: false });
        this._inboxNotifyLoadedKeys = loaded;
    },

    loadInboxDMConversations: async function() {
        if (!this.state.user) return;
        const left = document.getElementById('inbox_left_list');
        const right = document.getElementById('inbox_right_panel');
        if (!left || !right) return;

        left.innerHTML = '<div style="padding:20px; text-align:center; color:#666;">加载中...</div>';

        try {
            const url = `/api/v1/messages/conversations?user_id=${this.state.user.id}`;
            const res = await this.apiRequest('GET', url, undefined, { cancel_key: 'inbox:dm:convs', dedupe_key: url });
            const convs = res && res.ok ? await res.json() : [];
            this.state._inboxConvs = Array.isArray(convs) ? convs : [];
            this.renderInboxDMConversations();

            const pending = this.state.inboxPendingPeer;
            if (pending && pending.id) {
                this.state.inboxPendingPeer = null;
                this.openInboxDMThread(pending.id, pending.meta || null);
            } else {
                if (!this.state.dmPeerId) {
                    right.innerHTML = '<div style="color:#666; text-align:center; padding:30px;">选择一个会话</div>';
                }
            }

            if (this.state.dmPollTimer) clearInterval(this.state.dmPollTimer);
            this.state.dmPollTimer = setInterval(() => {
                const page = document.getElementById('page-inbox');
                if (!page || !page.classList.contains('active')) return;
                if (this.state.inboxTab !== 'dm') return;
                if (!this.state.dmPeerId) return;
                this.loadInboxDMThread(this.state.dmPeerId);
            }, 2500);
        } catch (_) {
            left.innerHTML = '<div style="padding:20px; text-align:center; color:#666;">加载失败</div>';
        }
    },

    renderInboxDMConversations: function() {
        if (!this.state.user) return;
        const left = document.getElementById('inbox_left_list');
        if (!left) return;
        const q = String(this.state.inboxSearchQuery || '').trim().toLowerCase();
        const convs = Array.isArray(this.state._inboxConvs) ? this.state._inboxConvs : [];
        const arr = q ? convs.filter(u => String(u.nickname || u.username || '').toLowerCase().includes(q)) : convs;

        if (!Array.isArray(arr) || arr.length === 0) {
            left.innerHTML = '<div style="padding:20px; text-align:center; color:#666;">暂无会话</div>';
            return;
        }

        left.innerHTML = '';
        arr.forEach(u => {
            const item = document.createElement('div');
            item.className = `dm-conv-item ${(this.state.dmPeerId && this.state.dmPeerId === u.id) ? 'active' : ''}`;
            item.innerHTML = `
                <img src="${u.avatar || '/static/img/default_avatar.svg'}" style="width:40px; height:40px; border-radius:50%; object-fit:cover;">
                <div style="flex:1; min-width:0;">
                    <div class="dm-conv-name">${u.nickname || u.username || ('用户'+u.id)}</div>
                </div>
            `;
            try {
                item.dataset.action = 'call';
                item.dataset.fn = 'openInboxDMThread';
                item.dataset.args = JSON.stringify([u.id, { id: u.id, nickname: u.nickname, username: u.username, avatar: u.avatar, aiseek_id: u.aiseek_id }]);
            } catch (_) {
            }
            left.appendChild(item);
        });
    },

    openInboxDMThread: async function(peerId, peerMeta = null) {
        if (!this.state.user) return;
        this.state.dmPeerId = peerId;
        const right = document.getElementById('inbox_right_panel');
        if (!right) return;

        const name = peerMeta ? (peerMeta.nickname || peerMeta.username || ('用户' + peerId)) : ('用户' + peerId);
        right.innerHTML = `
            <div class="inbox-chat-header">
                <div id="inbox_dm_chat_header_name" style="font-weight:600;">${name}</div>
                <div></div>
            </div>
            <div id="inbox_dm_chat_box" class="inbox-chat-box"></div>
            <div class="inbox-dm-input">
                <textarea id="inbox_dm_input" class="form-input" placeholder="发送消息..."></textarea>
                <button class="btn-primary" style="width:auto; border-radius:14px; padding:0 18px;" data-action="call" data-fn="sendInboxDMMessage" data-args="[]">发送</button>
            </div>
        `;

        this.renderInboxDMConversations();
        await this.loadInboxDMThread(peerId);
    },

    loadInboxDMThread: async function(peerId) {
        if (!this.state.user) return;
        const box = document.getElementById('inbox_dm_chat_box');
        if (!box) return;

        try {
            const url = `/api/v1/messages/list?user_id=${this.state.user.id}&other_id=${peerId}`;
            const res = await this.apiRequest('GET', url, undefined, { cancel_key: `inbox:dm:thread:${peerId}`, dedupe_key: url });
            const msgs = res && res.ok ? await res.json() : [];
            box.innerHTML = '';
            if (!Array.isArray(msgs) || msgs.length === 0) {
                box.innerHTML = '<div style="color:#888; padding:10px; text-align:center;">开始聊天吧</div>';
                return;
            }

            let lastTs = 0;
            msgs.forEach(m => {
                const ts = m.created_at ? new Date(m.created_at).getTime() : 0;
                if (ts && (!lastTs || Math.abs(ts - lastTs) > 5 * 60 * 1000)) {
                    const t = document.createElement('div');
                    t.className = 'dm-time';
                    t.innerText = this.fmtDateTime(m.created_at);
                    box.appendChild(t);
                    lastTs = ts;
                }

                const mine = m.sender_id === this.state.user.id;
                const row = document.createElement('div');
                row.className = `dm-row ${mine ? 'mine' : ''}`;

                const bubble = document.createElement('div');
                bubble.className = `dm-bubble ${mine ? 'mine' : ''}`;
                bubble.innerText = String(m.content || '');
                row.appendChild(bubble);
                box.appendChild(row);
            });

            box.scrollTop = box.scrollHeight;
        } catch (_) {
            box.innerHTML = '<div style="color:#888; padding:10px;">加载失败</div>';
        }
    },

    sendInboxDMMessage: async function() {
        const action = { type: 'open_inbox', tab: 'dm' };
        if (typeof this.ensureAuth === 'function') {
            if (!this.ensureAuth(action)) return;
        } else if (!this.state.user) {
            this.state.pendingAuthAction = action;
            this.openModal('authModal');
            return;
        }
        if (!this.state.dmPeerId) return;
        const input = document.getElementById('inbox_dm_input');
        if (!input || !input.value) return;
        const content = input.value;
        input.value = '';

        try {
            const res = await this.apiRequest('POST', '/api/v1/messages/send', { sender_id: this.state.user.id, receiver_id: this.state.dmPeerId, content }, { cancel_key: `inbox:dm:send:${Number(this.state.dmPeerId || 0)}` });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const d = data && (data.detail || data.message) ? (data.detail || data.message) : `发送失败(${res.status})`;
                try { this.showToast(typeof d === 'string' ? d : '发送失败'); } catch (_) {}
                return;
            }
            await this.loadInboxDMThread(this.state.dmPeerId);
        } catch(_) {
            try { this.showToast('发送失败'); } catch (_) {}
        }
    },

});
