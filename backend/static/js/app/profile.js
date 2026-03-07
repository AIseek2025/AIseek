Object.assign(window.app, {
    escapeHtml: function(s) {
        const t = String(s == null ? '' : s);
        return t
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#39;');
    },

    safeImgSrc: function(url) {
        const s = String(url || '').trim();
        if (!s) return '/static/img/default_avatar.svg';
        if (s.startsWith('/') && !s.includes('\\') && !s.includes('\n') && !s.includes('\r')) return s;
        if ((s.startsWith('http://') || s.startsWith('https://')) && !s.includes('"') && !s.includes("'") && !s.includes('\n') && !s.includes('\r')) return s;
        return '/static/img/default_avatar.svg';
    },

    safeCssUrl: function(url) {
        const s = String(url || '').trim();
        if (!s) return '';
        if (!(s.startsWith('http://') || s.startsWith('https://') || s.startsWith('/'))) return '';
        if (s.includes('"') || s.includes("'") || s.includes('\\') || s.includes('\n') || s.includes('\r') || s.includes(')') || s.includes('(')) return '';
        return s;
    },

    safeMediaUrl: function(url) {
        const s = String(url || '').trim();
        if (!s) return '';
        if (!(s.startsWith('http://') || s.startsWith('https://') || s.startsWith('/'))) return '';
        if (s.includes('"') || s.includes("'") || s.includes('\\') || s.includes('\n') || s.includes('\r')) return '';
        return s;
    },

    loadFollowingPage: async function() {
        const panel = document.getElementById('following_list_panel');
        const main = document.getElementById('following_main_panel');
        panel.innerHTML = '<div style="padding:20px; text-align:center; color:#666;">加载中...</div>';
        
        try {
            let url = '';
            if (this.state.followingSubtab === 'following') {
                url = `/api/v1/users/${this.state.user.id}/following`;
            } else {
                url = `/api/v1/users/${this.state.user.id}/followers`;
            }
            const res = await this.apiRequest('GET', url, undefined, { cancel_key: `follow:${this.state.followingSubtab}`, dedupe_key: url });
            if (!res.ok) throw new Error(`GET ${url} ${res.status}`);
            const users = await res.json();
            if (this.state.followingSubtab === 'following') {
                this.state.followingList = users;
                this.renderFriendList(panel, main, users, '关注', true);
            } else {
                this.state.followersList = users;
                this.renderFriendList(panel, main, users, '粉丝', true);
            }
            
        } catch(e) {
            console.error(e);
            panel.innerHTML = '<div style="padding:20px; color:#666;">加载失败</div>';
        }
    },

    switchFollowingSubtab: function(mode) {
        this.state.followingSubtab = mode;
        const a = document.getElementById('subtab_following');
        const b = document.getElementById('subtab_followers');
        if (a && b) {
            a.classList.toggle('active', mode === 'following');
            b.classList.toggle('active', mode === 'followers');
        }
        this.loadFollowingPage();
    },

    loadFriendsPage: async function() {
        const panel = document.getElementById('friends_list_panel');
        const main = document.getElementById('friends_main_panel');
        if (!panel || !main) return;
        panel.innerHTML = '<div style="padding:20px; text-align:center; color:#666;">加载中...</div>';
        main.innerHTML = '<div style="color:var(--text-secondary);">加载中...</div>';
        
        try {
            const url = `/api/v1/users/friends/list?user_id=${this.state.user.id}`;
            const res = await this.apiRequest('GET', url, undefined, { cancel_key: 'friends:list', dedupe_key: url });
            if (!res.ok) throw new Error(`GET ${url} ${res.status}`);
            const friends = await res.json();
            
            // Normalize data structure
            const raw = Array.isArray(friends) ? friends : [];
            this.state.friendsList = raw.map(f => f.friend_user || f).filter(u => u && u.id);
            
            this.renderFriendList(panel, main, this.state.friendsList, '好友', true);
            try {
                setTimeout(() => {
                    try { this.ensureFriendsDefaultOpen(panel, main, this.state.friendsList); } catch (_) {}
                }, 0);
            } catch (_) {
            }
            
        } catch(e) {
            console.error(e);
            panel.innerHTML = '<div style="padding:20px; color:#666;">加载失败</div>';
            main.innerHTML = '<div style="color:var(--text-secondary);">加载失败</div>';
        }
    },

    ensureFriendsDefaultOpenFromUI: function() {
        const panel = document.getElementById('friends_list_panel');
        const main = document.getElementById('friends_main_panel');
        return this.ensureFriendsDefaultOpen(panel, main, this.state.friendsList);
    },

    deletePost: async function(postId, el) {
        const pid = Number(postId || 0) || 0;
        if (!pid) return;
        if (!this.state.user) return this.openModal('authModal');
        const ok = confirm('确定删除该作品吗？');
        if (!ok) return;
        try {
            if (el) { try { el.style.opacity = '0.6'; el.style.pointerEvents = 'none'; } catch (_) {} }
            const url = `/api/v1/posts/${pid}/remove`;
            const res = await this.apiRequest('POST', url, {}, { cancel_key: `post:remove:${pid}` });
            if (!res.ok) {
                this.toast('删除失败');
                return;
            }
            this.toast('已删除');
            try {
                const uid = this.state.viewingUser && this.state.viewingUser.user ? Number(this.state.viewingUser.user.id || 0) : 0;
                if (uid) this.loadProfile(uid);
            } catch (_) {
            }
        } catch (e) {
            const msg = e && e.message ? String(e.message) : '删除失败';
            this.toast(msg);
        } finally {
            if (el) { try { el.style.opacity = ''; el.style.pointerEvents = ''; } catch (_) {} }
        }
    },

    ensureFriendsDefaultOpen: async function(panel, main, list) {
        const p = panel || document.getElementById('friends_list_panel');
        const m = main || document.getElementById('friends_main_panel');
        const arr = Array.isArray(list) ? list : [];
        if (!p || !m) return;
        if (!arr.length) {
            m.innerHTML = '<div style="color:var(--text-secondary);">暂无好友</div>';
            return;
        }
        try {
            if (m.querySelector && m.querySelector('.friend-feed-container')) return;
        } catch (_) {
        }
        const token = String(Date.now()) + ':' + String(Math.random());
        this._friendsAutoOpenToken = token;
        try {
            for (let j = 0; j < 25; j++) {
                if (this._friendsAutoOpenToken !== token) return;
                const page = document.getElementById('page-friends');
                if (page && page.classList && page.classList.contains('active')) break;
                await new Promise(r => setTimeout(r, 60));
            }
            const page2 = document.getElementById('page-friends');
            if (!page2 || !page2.classList || !page2.classList.contains('active')) return;
        } catch (_) {
            return;
        }
        for (let i = 0; i < arr.length; i++) {
            if (this._friendsAutoOpenToken !== token) return;
            const u = arr[i];
            const uid = u && u.id ? Number(u.id) : 0;
            if (!uid) continue;
            try {
                const items = p.querySelectorAll('.friend-item');
                Array.from(items).forEach(x => { try { x.classList.remove('active'); } catch (_) {} });
                const el = p.querySelector(`.friend-item[data-user-id="${uid}"]`);
                if (el) el.classList.add('active');
            } catch (_) {
            }
            const ok = await this.loadUserWorkInMainPanel(uid, m);
            if (ok) return;
        }
        m.innerHTML = '<div style="color:var(--text-secondary);">暂无好友作品</div>';
    },

    renderFriendList: function(panel, main, list, subtext, autoSelectFirst = false) {
        panel.innerHTML = '';
        if (!list || list.length === 0) {
            panel.innerHTML = '<div style="padding:20px; color:#666; text-align:center;">暂无数据</div>';
            return;
        }
        
        list.forEach((u, index) => {
            const item = document.createElement('div');
            item.className = 'friend-item';
            try {
                item.dataset.action = 'selectFriend';
                item.dataset.userId = String(u.id || '');
                item.dataset.main = main && main.id ? `#${main.id}` : '';
                item.dataset.group = panel && panel.id ? `#${panel.id} .friend-item` : '';
            } catch (_) {
            }
            
            const img = document.createElement('img');
            img.className = 'friend-avatar';
            img.src = this.safeImgSrc(u && u.avatar ? String(u.avatar) : '');
            const info = document.createElement('div');
            info.className = 'friend-info';
            const name = document.createElement('div');
            name.className = 'friend-name';
            name.innerText = String((u && (u.nickname || u.username)) || '');
            info.appendChild(name);
            item.appendChild(img);
            item.appendChild(info);
            panel.appendChild(item);
            
            // Auto select first if none selected (optional, maybe distracting if filtering)
            // if (index === 0) item.click();
        });

        if (autoSelectFirst) {
            const first = panel.querySelector('.friend-item');
            if (first) first.click();
        }
    },

    filterFollowPageList: function(query) {
        const q = query.toLowerCase();
        const isFollowers = this.state.followingSubtab === 'followers';
        const source = isFollowers ? this.state.followersList : this.state.followingList;
        const panel = document.getElementById('following_list_panel');
        const main = document.getElementById('following_main_panel');
        const subtext = isFollowers ? '粉丝' : '关注';
        
        if (!source) return;
        
        const filtered = source.filter(u => {
            const name = (u.nickname || u.username || '').toLowerCase();
            const id = String(u.aiseek_id || u.id);
            return name.includes(q) || id.includes(q);
        });
        
        this.renderFriendList(panel, main, filtered, subtext);
    },

    filterFriendsList: function(type, query) {
        const q = query.toLowerCase();
        const source = this.state.friendsList;
        const panel = document.getElementById('friends_list_panel');
        const main = document.getElementById('friends_main_panel');
        const subtext = '好友';
        if (!source) return;
        const filtered = source.filter(u => {
            const name = (u.nickname || u.username || '').toLowerCase();
            const id = String(u.aiseek_id || u.id);
            return name.includes(q) || id.includes(q);
        });
        this.renderFriendList(panel, main, filtered, subtext);
    },

    loadUserWorkInMainPanel: async function(userId, container) {
        const root = (typeof container === 'string') ? document.querySelector(container) : container;
        if (!root) return false;
        root.innerHTML = '<div style="color:var(--text-secondary);">加载作品中...</div>';
        try {
            const viewer = this.state.user ? this.state.user.id : '';
            const url = `/api/v1/posts/user/${userId}${viewer ? `?viewer_id=${viewer}` : ''}`;
            const res = await this.apiRequest('GET', url, undefined, { cancel_key: `profile:userposts:${userId}`, dedupe_key: url });
            if (!res.ok) throw new Error(`GET ${url} ${res.status}`);
            const posts = await res.json();
            
            if (posts.length === 0) {
                root.innerHTML = '<div style="color:var(--text-secondary);">该用户暂无作品</div>';
                return false;
            }
            
            root.innerHTML = `
                <div class="friend-feed-shell">
                    <div class="friend-nav-arrows">
                        <div class="nav-arrow" data-action="call" data-fn="friendFeedPrev" data-args="[]"><i class="fas fa-chevron-up"></i></div>
                        <div class="nav-arrow" data-action="call" data-fn="friendFeedNext" data-args="[]"><i class="fas fa-chevron-down"></i></div>
                    </div>
                    <div class="friend-feed-container" id="friend_feed_${userId}"></div>
                </div>
            `;
            const feed = document.getElementById(`friend_feed_${userId}`);
            this.state.activeFriendFeedId = `friend_feed_${userId}`;

            posts.forEach(post => {
                const slide = document.createElement('div');
                slide.className = 'video-slide';
                slide.id = `slide-${post.id}`;
                slide.dataset.postId = String(post.id);
                slide.innerHTML = this.renderVideoSlide(post, { showNavArrows: false });
                feed.appendChild(slide);
                this.bindVideoEvents(slide, post);
            });

            try { feed.scrollTop = 0; } catch (_) {}
            requestAnimationFrame(() => {
                try { this.initObserverIn(feed); } catch (_) {}
            });
            return true;
            
        } catch(e) {
            console.error(e);
            root.innerHTML = '<div style="color:var(--text-secondary);">加载作品失败</div>';
            return false;
        }
    },

    friendFeedPrev: function() {
        this.scrollActiveFriendFeed(-1);
    },

    friendFeedNext: function() {
        this.scrollActiveFriendFeed(1);
    },

    scrollActiveFriendFeed: function(dir) {
        const id = this.state.activeFriendFeedId;
        if (!id) return;
        const feed = document.getElementById(String(id));
        if (!feed) return;
        const dy = Number(feed.clientHeight || 0) * (Number(dir) || 0);
        if (!dy) return;
        try { feed.scrollBy({ top: dy, left: 0, behavior: 'smooth' }); } catch (_) { feed.scrollTop += dy; }
    },

    openFollowList: async function(type, userId) {
        return this.openFollowModal(type === 'followers' ? 'followers' : 'following', userId, 0, 0);
    },

    openFollowModal: async function(mode, userId, followingCount = 0, followersCount = 0) {
        this.state.followModalUserId = userId;
        this.state.followModalMode = mode;
        this.state.followModalFollowingCount = Number(followingCount) || 0;
        this.state.followModalFollowersCount = Number(followersCount) || 0;
        this.state.followModalFollowingCache = null;
        this.state.followModalFollowersCache = null;

        const c1 = document.getElementById('followCountFollowing');
        const c2 = document.getElementById('followCountFollowers');
        if (c1) c1.innerText = this.state.followModalFollowingCount;
        if (c2) c2.innerText = this.state.followModalFollowersCount;

        const input = document.getElementById('followModalSearch');
        if (input) input.value = '';

        this.openModal('followModal');
        this.switchFollowModalTab(mode);
    },

    switchFollowModalTab: function(mode) {
        this.state.followModalMode = mode;
        const a = document.getElementById('followTabFollowing');
        const b = document.getElementById('followTabFollowers');
        if (a && b) {
            a.classList.toggle('active', mode === 'following');
            b.classList.toggle('active', mode === 'followers');
        }

        const input = document.getElementById('followModalSearch');
        if (input) input.value = '';

        const list = document.getElementById('followList');
        if (list) list.innerHTML = '<div style="color:#666; padding:10px;">加载中...</div>';
        this.loadFollowModalList();
    },

    loadFollowModalList: async function() {
        const userId = this.state.followModalUserId;
        const mode = this.state.followModalMode;
        const list = document.getElementById('followList');
        if (!userId || !list) return;

        const cache = mode === 'followers' ? this.state.followModalFollowersCache : this.state.followModalFollowingCache;
        if (Array.isArray(cache)) {
            this.renderFollowModalList(cache);
            return;
        }

        try {
            const url = mode === 'followers'
              ? `/api/v1/users/${userId}/followers`
              : `/api/v1/users/${userId}/following`;
            const users = await this.apiGetJSON(url, { cancel_key: `followmodal:${mode}:${userId}`, dedupe_key: url, cache_ttl_ms: 8000 });
            const arr = Array.isArray(users) ? users : [];
            if (mode === 'followers') this.state.followModalFollowersCache = arr;
            else this.state.followModalFollowingCache = arr;
            this.renderFollowModalList(arr);
        } catch (e) {
            list.innerHTML = '<div style="color:#666; padding:10px;">加载失败</div>';
        }
    },

    renderFollowModalList: function(users) {
        const list = document.getElementById('followList');
        if (!list) return;
        if (!Array.isArray(users) || users.length === 0) {
            list.innerHTML = '<div style="color:#666; padding:10px;">暂无数据</div>';
            return;
        }
        list.innerHTML = '';
        users.forEach(u => {
            const item = document.createElement('div');
            item.className = 'friend-item';
            try {
                item.dataset.action = 'call';
                item.dataset.fn = 'viewUserProfile';
                item.dataset.args = JSON.stringify([Number(u && u.id ? u.id : 0)]);
            } catch (_) {
            }
            const img = document.createElement('img');
            img.className = 'friend-avatar';
            img.src = this.safeImgSrc(u && u.avatar ? String(u.avatar) : '');
            const info = document.createElement('div');
            info.className = 'friend-info';
            const name = document.createElement('div');
            name.className = 'friend-name';
            name.innerText = String((u && (u.nickname || u.username)) || '');
            info.appendChild(name);
            item.appendChild(img);
            item.appendChild(info);
            if (String(this.state.followModalMode || '') === 'following' && this.state.user && Number(u && u.id) !== Number(this.state.user.id || 0)) {
                const btn = document.createElement('button');
                btn.className = 'btn-secondary';
                btn.style.width = 'auto';
                btn.style.padding = '6px 10px';
                btn.style.borderRadius = '10px';
                btn.innerText = '取关';
                btn.addEventListener('click', async (ev) => {
                    ev.preventDefault();
                    ev.stopPropagation();
                    try {
                        const targetId = Number(u && u.id ? u.id : 0);
                        if (!targetId) return;
                        const res = await this.apiRequest('POST', '/api/v1/users/follow', { user_id: this.state.user.id, target_id: targetId }, { cancel_key: `follow:modal:${targetId}` });
                        const data = await res.json().catch(() => ({}));
                        if (!res.ok) throw new Error((data && (data.detail || data.message)) || '操作失败');
                        if (String(data.message || '') === 'Unfollowed') {
                            try { this.state.followModalFollowingCache = (this.state.followModalFollowingCache || []).filter((x) => Number(x && x.id) !== targetId); } catch (_) {}
                            this.renderFollowModalList(this.state.followModalFollowingCache || []);
                            this.toast('已取关');
                            if (window.appInteractions && typeof window.appInteractions.applyFollowPatch === 'function') {
                                window.appInteractions.applyFollowPatch(targetId, false);
                            }
                        }
                    } catch (e) {
                        this.toast((e && e.message) ? String(e.message) : '取关失败');
                    }
                });
                item.appendChild(btn);
            }
            list.appendChild(item);
        });
    },

    filterFollowModal: function(query) {
        const q = (query || '').toLowerCase();
        const mode = this.state.followModalMode;
        const source = mode === 'followers' ? this.state.followModalFollowersCache : this.state.followModalFollowingCache;
        if (!Array.isArray(source)) return;
        const filtered = source.filter(u => {
            const name = (u.nickname || u.username || '').toLowerCase();
            const id = String(u.aiseek_id || u.id);
            return name.includes(q) || id.includes(q);
        });
        this.renderFollowModalList(filtered);
    },

    loadProfile: async function(userId) {
        const header = document.getElementById('p-header');
        
        try {
            const url = `/api/v1/users/profile/${userId}?current_user_id=${this.state.user ? this.state.user.id : ''}`;
            const res = await this.apiRequest('GET', url, undefined, { cancel_key: `profile:${userId}`, dedupe_key: url });
            if (!res.ok) throw new Error('加载用户失败');
            const profile = await res.json();
            this.state.viewingUser = profile;
            const user = profile.user;
            const bg = (user && user.background) ? user.background : '/static/img/default_bg.svg';
            const safeBg = this.safeCssUrl(bg) || '/static/img/default_bg.svg';
            document.body.style.setProperty('--profile-hero-bg', `url("${safeBg}")`);
            
            const isMe = this.state.user && user && Number(this.state.user.id) === Number(user.id);
            try {
                const worksEl = document.getElementById('p-count-works');
                const n = Number(profile && profile.works_count);
                if (worksEl && Number.isFinite(n)) worksEl.innerText = String(n);
            } catch (_) {
            }

            let actionBtn = '';
            if (isMe) {
                actionBtn = `<i class="fas fa-edit" style="font-size:16px; color:#666; cursor:pointer;" data-action="openEditProfile"></i>`;
            } else {
                const dmMeta = JSON.stringify({ id: user.id, nickname: user.nickname || user.username, username: user.username, avatar: user.avatar, aiseek_id: user.aiseek_id, is_friend: !!profile.is_friend });
                const dmBtn = `<button class="btn-primary" style="width:88px; height:34px; padding:0; background:#333; margin-left:8px; font-size:14px;" data-action="call" data-fn="startChat" data-args='[${user.id}, ${dmMeta}]'>私信</button>`;
                
                const followText = profile.is_following ? '已关注' : '关注';
                const followBg = profile.is_following ? '#333' : '#fe2c55';
                const followBtn = `<button class="btn-primary" style="width:88px; height:34px; padding:0; background:${followBg}; font-size:14px;" data-action="call" data-fn="toggleFollow" data-args='[${user.id}]'>${followText}</button>`;
                
                const shareBtn = `<button class="btn-primary" style="width:34px; height:34px; padding:0; background:#333; margin-left:8px; display:flex; align-items:center; justify-content:center;" data-action="alert" data-message="链接已复制"><i class="fas fa-share"></i></button>`;
                
                actionBtn = `<div style="display:flex; align-items:center;">${followBtn}${dmBtn}${shareBtn}</div>`;
            }
            const safeBanner = this.safeCssUrl(user && user.background ? String(user.background) : '') || '/static/img/default_bg.svg';
            const safeAvatar = this.safeImgSrc(user && user.avatar ? String(user.avatar) : '');
            const safeName = this.escapeHtml((user && (user.nickname || user.username)) ? (user.nickname || user.username) : '');
            const safeBio = this.escapeHtml((user && user.bio) ? user.bio : '暂无简介');
            const safeBirthday = user && user.birthday ? this.escapeHtml(String(user.birthday)) : '';
            const safeLocation = user && user.location ? this.escapeHtml(String(user.location)) : '';
            const genderTxt = user && user.gender === 'male' ? '♂ 男' : (user && user.gender === 'female' ? '♀ 女' : '');
            const metaLine = `${genderTxt ? genderTxt : ''}${safeBirthday ? ` · ${safeBirthday}出生` : ''}${safeLocation ? ` · 📍 ${safeLocation}` : ''}`;
            const repLine = isMe ? `<div class="profile-id" title="信誉分越高，社区互动体验越好">信誉分：<b style="color:rgba(255,255,255,0.9);">${(user.reputation_score==null?100:user.reputation_score)}</b></div>` : '';

            header.innerHTML = `
                <div class="profile-banner" style="background-image:url('${safeBanner}')"></div>
                <div class="profile-header-inner">
                    <img src="${safeAvatar}" class="profile-avatar-lg">
                    <div class="profile-info-box">
                        <div class="profile-name">
                            ${safeName}
                            ${actionBtn}
                        </div>
                        <div class="profile-id">AIseek号：${String(user.aiseek_id || user.id).padStart(10,'0')}</div>
                        ${repLine}
                        <div class="profile-divider"></div>
                        <div class="profile-stats">
                            <div class="stat-item" style="cursor:pointer" data-action="call" data-fn="openFollowModal" data-args='["following", ${user.id}, ${user.following_count||0}, ${user.followers_count||0}]'><span class="stat-num">${user.following_count||0}</span> 关注</div>
                            <div class="stat-item" style="cursor:pointer" data-action="call" data-fn="openFollowModal" data-args='["followers", ${user.id}, ${user.following_count||0}, ${user.followers_count||0}]'><span class="stat-num">${user.followers_count||0}</span> 粉丝</div>
                            <div class="stat-item"><span class="stat-num">${user.likes_received_count||0}</span> 获赞</div>
                        </div>
                        <div class="profile-meta">
                            <div>${metaLine}</div>
                            <div style="margin-top:4px;">${safeBio}</div>
                        </div>
                    </div>
                </div>
            `;
            try {
                const allow = new Set(['works', 'likes', 'favorites', 'history']);
                const pending = allow.has(String(this.state.pendingProfileTab || '')) ? String(this.state.pendingProfileTab) : '';
                const saved = (isMe && allow.has(String(localStorage.getItem('profile_tab') || ''))) ? String(localStorage.getItem('profile_tab') || '') : '';
                const tab = pending || saved || 'works';
                this.state.pendingProfileTab = null;
                this.switchProfileTab(tab);
            } catch (_) {
                this.switchProfileTab('works');
            }

        } catch(e) {
            console.error(e);
            header.innerHTML = '<div style="color:#888; padding:20px;">加载失败</div>';
        }
    },

    switchProfileTab: async function(tab) {
        this.state.currentProfileTab = tab;
        try {
            const allow = new Set(['works', 'likes', 'favorites', 'history']);
            if (allow.has(String(tab || ''))) {
                const uid = this.state.viewingUser && this.state.viewingUser.user ? Number(this.state.viewingUser.user.id || 0) : 0;
                const isMe = this.state.user && uid && Number(this.state.user.id) === uid;
                if (isMe) localStorage.setItem('profile_tab', String(tab));
                const base = isMe ? '#/profile' : (uid ? `#/u/${uid}` : '#/profile');
                history.replaceState(null, '', `${base}?tab=${encodeURIComponent(String(tab))}`);
            }
        } catch (_) {
        }
        const tabEls = document.querySelectorAll('#page-profile .profile-tabs .p-tab');
        tabEls.forEach(el => el.classList.remove('active'));
        // Find correct tab index
        const tabs = ['works', 'likes', 'favorites', 'history'];
        const idx = tabs.indexOf(tab);
        if (idx >= 0) {
            const tabEl = tabEls[idx];
            if (tabEl) tabEl.classList.add('active');
        }
        
        const content = document.getElementById('p-content');
        content.innerHTML = '加载中...';

        try {
            const uid = this.state.viewingUser?.user?.id;
            const isMe = this.state.user && uid && Number(this.state.user.id) === Number(uid);
            if (!isMe && (tab === 'likes' || tab === 'favorites' || tab === 'history')) {
                content.innerHTML = `
                    <div style="display:flex; align-items:center; justify-content:center; height:240px; color:rgba(255,255,255,0.70); flex-direction:column; gap:10px;">
                        <div style="font-size:18px; color:rgba(255,255,255,0.86); font-weight:800;"><i class="fas fa-lock" style="margin-right:8px;"></i>已设为私密</div>
                        <div style="font-size:13px; color:rgba(255,255,255,0.55);">喜欢 / 收藏 / 观看历史仅对本人可见</div>
                    </div>
                `;
                return;
            }
        } catch (_) {
        }
        
        try {
            let url = '';
            const uid = this.state.viewingUser?.user?.id;
            if (tab === 'works') {
                const viewer = this.state.user ? this.state.user.id : '';
                url = `/api/v1/posts/user/${uid}${viewer ? `?viewer_id=${viewer}` : ''}`;
            }
            else if (tab === 'likes') url = `/api/v1/interaction/likes/${uid}`;
            else if (tab === 'favorites') url = `/api/v1/interaction/favorites/${uid}`;
            else if (tab === 'history') url = `/api/v1/interaction/history/${uid}`;
            
            const res = await this.apiRequest('GET', url, undefined, { cancel_key: `profiletab:${tab}:${uid}`, dedupe_key: url });
            if (!res.ok) throw new Error('fetch_failed');
            const posts = await res.json();
            const arr = Array.isArray(posts) ? posts : [];
            content.innerHTML = '';
            
            // Update counts if available
            if(tab === 'works') document.getElementById('p-count-works').innerText = arr.length;
            
            arr.forEach(post => {
                const card = document.createElement('div');
                card.className = 'p-card';
                const isVideo = (post.post_type === 'video') || (post.video_url && !(/\.(jpg|jpeg|png|gif|webp)(\?|#|$)/i.test(post.video_url)));
                const imgUrl = (post.cover_url || (Array.isArray(post.images) && post.images.length > 0 ? post.images[0] : '') || post.video_url || '');
                const hlsUrl = (post && (post.hls_url || (post.video_url && /\.m3u8(\?|#|$)/i.test(post.video_url) ? post.video_url : ''))) || '';
                const mp4Url = (post && (post.mp4_url || (!hlsUrl ? post.video_url : ''))) || '';
                const posterUrl = (post.cover_url || (Array.isArray(post.images) && post.images.length > 0 ? post.images[0] : '') || (post.id ? `/api/v1/media/post-thumb/${post.id}?v=${post.id}` : '') || '');
                const safeHls = this.safeMediaUrl(hlsUrl);
                const safeMp4 = this.safeMediaUrl(mp4Url);
                const safePoster = this.safeImgSrc(posterUrl);
                const safeImg = this.safeImgSrc(imgUrl || '/static/img/default_bg.svg');
                const media = isVideo ? 
                    `<video data-hls="${this.escapeHtml(safeHls)}" data-mp4="${this.escapeHtml(safeMp4)}" poster="${this.escapeHtml(safePoster)}" muted loop playsinline preload="metadata" style="width:100%; height:100%; object-fit:cover;"></video>` : 
                    `<img src="${this.escapeHtml(safeImg)}" style="width:100%; height:100%; object-fit:cover;">`;
                
                const isMe = this.state.user && this.state.viewingUser && this.state.viewingUser.user && Number(this.state.user.id) === Number(this.state.viewingUser.user.id);
                const delBtn = (isMe && tab === 'works') ? `<div class="p-del" data-action="call" data-fn="deletePost" data-args="[${post.id}]" data-pass-el="1" data-stop="1" style="position:absolute; top:5px; right:5px; background:rgba(0,0,0,0.5); color:white; width:24px; height:24px; border-radius:4px; display:flex; align-items:center; justify-content:center; z-index:50; pointer-events:auto;"><i class="fas fa-trash"></i></div>` : '';

                card.innerHTML = `
                    ${media}
                    ${delBtn}
                    <div style="position:absolute; bottom:5px; left:10px; color:var(--text-color); font-size:12px; font-weight:600; text-shadow:0 1px 2px rgba(0,0,0,0.65);">
                        <i class="far fa-heart"></i> ${post.likes_count}
                    </div>
                `;
                try {
                    card.dataset.action = 'call';
                    card.dataset.fn = 'openPost';
                    card.dataset.args = JSON.stringify([post.id]);
                } catch (_) {
                }
                content.appendChild(card);
                try { this.bindAIStatusForCard(post, card); } catch (_) {}
                try {
                    const del = card.querySelector('.p-del');
                    if (del) {
                        del.addEventListener('click', (ev) => {
                            try { ev.preventDefault(); } catch (_) {}
                            try { ev.stopPropagation(); } catch (_) {}
                            try { this.deletePost(post.id, del); } catch (_) {}
                        }, false);
                    }
                } catch (_) {
                }

                if (isVideo) {
                    const v = card.querySelector('video');
                    if (v) {
                        try { v.pause(); } catch (_) {}
                        try {
                            card.dataset.actionMouseover = 'call';
                            card.dataset.fnMouseover = 'profilePreviewPlay';
                            card.dataset.argsMouseover = JSON.stringify([post.id]);
                            card.dataset.passEl = '1';
                            card.dataset.actionMouseout = 'call';
                            card.dataset.fnMouseout = 'profilePreviewStop';
                            card.dataset.argsMouseout = JSON.stringify([post.id]);
                            card.dataset.passEl = '1';
                        } catch (_) {
                        }
                    }
                }
            });
            
            if(arr.length === 0) content.innerHTML = '<div style="color:var(--text-secondary); grid-column:1/-1; text-align:center;">暂无内容</div>';
            
        } catch(e) { console.error(e); content.innerHTML = '加载失败'; }
    },

    bindAIStatusForCard: function(post, card) {
        if (!post || !card) return;
        const st = String(post.status || '');
        const jid = String(post.ai_job_id || '');
        const isMe = this.state.user && this.state.viewingUser && this.state.viewingUser.user && Number(this.state.user.id) === Number(this.state.viewingUser.user.id);
        if (!isMe) return;
        if (!jid || st === 'done') return;
        const badge = document.createElement('div');
        badge.className = 'ai-job-badge';
        badge.dataset.jobId = jid;
        badge.style.pointerEvents = 'auto';
        badge.style.position = 'absolute';
        badge.style.left = '10px';
        badge.style.top = '8px';
        badge.style.right = '10px';
        badge.style.display = 'flex';
        badge.style.alignItems = 'center';
        badge.style.justifyContent = 'space-between';
        badge.style.gap = '10px';
        badge.style.padding = '8px 10px';
        badge.style.borderRadius = '10px';
        badge.style.background = 'rgba(0,0,0,0.55)';
        badge.style.backdropFilter = 'blur(6px)';
        badge.style.color = 'rgba(255,255,255,0.92)';
        badge.style.fontSize = '12px';
        badge.style.fontWeight = '700';
        badge.style.zIndex = '12';
        const left = document.createElement('div');
        left.style.display = 'flex';
        left.style.flexDirection = 'column';
        left.style.gap = '2px';
        const title = document.createElement('div');
        title.className = 'ai-job-title';
        title.innerText = st === 'failed' ? '生成失败' : (st === 'queued' ? '排队中' : '生成中');
        const sub = document.createElement('div');
        sub.className = 'ai-job-msg';
        sub.style.fontWeight = '600';
        sub.style.fontSize = '11px';
        sub.style.color = 'rgba(255,255,255,0.72)';
        sub.innerText = String(post.error_message || '');
        left.appendChild(title);
        left.appendChild(sub);
        const right = document.createElement('div');
        right.style.display = 'flex';
        right.style.alignItems = 'center';
        right.style.gap = '8px';
        right.className = 'ai-job-actions';
        const pct = document.createElement('div');
        pct.className = 'ai-job-pct';
        pct.innerText = '';
        right.appendChild(pct);
        if (st === 'queued' || st === 'processing') {
            const cancel = document.createElement('div');
            cancel.className = 'ai-job-cancel';
            cancel.style.padding = '6px 10px';
            cancel.style.borderRadius = '999px';
            cancel.style.background = 'rgba(255,255,255,0.18)';
            cancel.style.cursor = 'pointer';
            cancel.style.userSelect = 'none';
            cancel.style.pointerEvents = 'auto';
            cancel.innerText = '取消';
            try {
                cancel.dataset.action = 'call';
                cancel.dataset.fn = 'cancelAIJob';
                cancel.dataset.args = JSON.stringify([jid]);
                cancel.dataset.stop = '1';
            } catch (_) {
            }
            try {
                cancel.addEventListener('click', (ev) => {
                    try { ev.preventDefault(); } catch (_) {}
                    try { ev.stopPropagation(); } catch (_) {}
                    try { this.cancelAIJob(jid); } catch (_) {}
                }, false);
            } catch (_) {
            }
            right.appendChild(cancel);
        } else {
            const revise = document.createElement('div');
            revise.style.padding = '6px 10px';
            revise.style.borderRadius = '999px';
            revise.style.background = 'rgba(255,255,255,0.18)';
            revise.style.cursor = 'pointer';
            revise.style.userSelect = 'none';
            revise.style.pointerEvents = 'auto';
            revise.innerText = '改稿';
            try {
                revise.dataset.action = 'call';
                revise.dataset.fn = 'reviseAIJob';
                revise.dataset.args = JSON.stringify([jid]);
                revise.dataset.stop = '1';
            } catch (_) {
            }
            try {
                revise.addEventListener('click', (ev) => {
                    try { ev.preventDefault(); } catch (_) {}
                    try { ev.stopPropagation(); } catch (_) {}
                    try { this.reviseAIJob(jid); } catch (_) {}
                }, false);
            } catch (_) {
            }
            const chat = document.createElement('div');
            chat.style.padding = '6px 10px';
            chat.style.borderRadius = '999px';
            chat.style.background = 'rgba(255,255,255,0.18)';
            chat.style.cursor = 'pointer';
            chat.style.userSelect = 'none';
            chat.style.pointerEvents = 'auto';
            chat.innerText = '沟通';
            try {
                chat.dataset.action = 'call';
                chat.dataset.fn = 'openAIChatModal';
                chat.dataset.args = JSON.stringify([jid]);
                chat.dataset.stop = '1';
            } catch (_) {
            }
            try {
                chat.addEventListener('click', (ev) => {
                    try { ev.preventDefault(); } catch (_) {}
                    try { ev.stopPropagation(); } catch (_) {}
                    try { this.openAIChatModal(jid); } catch (_) {}
                }, false);
            } catch (_) {
            }
            const draft = document.createElement('div');
            draft.style.padding = '6px 10px';
            draft.style.borderRadius = '999px';
            draft.style.background = 'rgba(255,255,255,0.18)';
            draft.style.cursor = 'pointer';
            draft.style.userSelect = 'none';
            draft.style.pointerEvents = 'auto';
            draft.innerText = '脚本';
            try {
                draft.dataset.action = 'call';
                draft.dataset.fn = 'openAIDraftEditor';
                draft.dataset.args = JSON.stringify([jid]);
                draft.dataset.stop = '1';
            } catch (_) {
            }
            try {
                draft.addEventListener('click', (ev) => {
                    try { ev.preventDefault(); } catch (_) {}
                    try { ev.stopPropagation(); } catch (_) {}
                    try { this.openAIDraftEditor(jid); } catch (_) {}
                }, false);
            } catch (_) {
            }
            right.appendChild(chat);
            right.appendChild(revise);
            right.appendChild(draft);
        }
        badge.appendChild(left);
        badge.appendChild(right);
        card.appendChild(badge);
        this.pollAIJobIntoBadge(jid, badge);
    },

    reviseAIJob: async function(jobId) {
        const jid = String(jobId || '');
        const uid = this.state.user ? Number(this.state.user.id || 0) : 0;
        if (!jid || !uid) return;
        let fb = '';
        try {
            fb = String(prompt('请输入二次反馈修改要求（例如：更短、更幽默、强调重点、换风格）', '') || '').trim();
        } catch (_) {
            fb = '';
        }
        if (!fb) return;
        try {
            const url = `/api/v1/ai/jobs/${encodeURIComponent(jid)}/revise`;
            const res = await this.apiRequest('POST', url, { user_id: uid, feedback: fb }, { cancel_key: `ai:revise:${jid}` });
            if (!res.ok) return;
            const data = await res.json().catch(() => null);
            this.toast('已提交改稿');
            try {
                if (data && data.post_id) {
                    if (typeof this.loadProfile === 'function') this.loadProfile(uid);
                }
            } catch (_) {
            }
        } catch (_) {
        }
    },

    openAIDraftEditor: async function(jobId) {
        const jid = String(jobId || '');
        const uid = this.state.user ? Number(this.state.user.id || 0) : 0;
        if (!jid || !uid) return;
        let existing = document.getElementById('ai_draft_editor');
        if (!existing) {
            existing = document.createElement('div');
            existing.id = 'ai_draft_editor';
            existing.style.position = 'fixed';
            existing.style.inset = '0';
            existing.style.background = 'rgba(0,0,0,0.55)';
            existing.style.zIndex = '9999';
            existing.style.display = 'none';
            existing.innerHTML = `
                <div style="position:absolute; left:50%; top:50%; transform:translate(-50%,-50%); width:min(980px, calc(100vw - 32px)); height:min(720px, calc(100vh - 32px)); background:#111; border:1px solid rgba(255,255,255,0.10); border-radius:14px; overflow:hidden; display:flex; flex-direction:column;">
                    <div style="padding:12px 14px; display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid rgba(255,255,255,0.08);">
                        <div style="font-size:13px; font-weight:800; color:rgba(255,255,255,0.92);">AI创作脚本（可编辑）</div>
                        <div style="display:flex; gap:8px; align-items:center;">
                            <div id="ai_draft_history" style="padding:6px 10px; border-radius:999px; background:rgba(255,255,255,0.10); cursor:pointer; user-select:none; color:rgba(255,255,255,0.85); font-weight:800; font-size:12px;">历史</div>
                            <div id="ai_draft_save" style="padding:6px 10px; border-radius:999px; background:rgba(255,255,255,0.16); cursor:pointer; user-select:none; color:rgba(255,255,255,0.92); font-weight:800; font-size:12px;">保存</div>
                            <div id="ai_draft_rerun" style="padding:6px 10px; border-radius:999px; background:rgba(254,44,85,0.85); cursor:pointer; user-select:none; color:white; font-weight:900; font-size:12px;">按脚本重做</div>
                            <div id="ai_draft_close" style="padding:6px 10px; border-radius:999px; background:rgba(255,255,255,0.10); cursor:pointer; user-select:none; color:rgba(255,255,255,0.85); font-weight:800; font-size:12px;">关闭</div>
                        </div>
                    </div>
                    <div style="flex:1; display:flex; flex-direction:column;">
                        <textarea id="ai_draft_text" spellcheck="false" style="flex:1; width:100%; padding:12px 12px; border:0; outline:none; resize:none; background:#0b0b0b; color:rgba(255,255,255,0.88); font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; font-size:12px; line-height:1.5;"></textarea>
                    </div>
                </div>
                <div id="ai_draft_history_panel" style="position:absolute; right:16px; top:16px; width:320px; height:calc(100% - 32px); background:#0e0e0e; border:1px solid rgba(255,255,255,0.10); border-radius:14px; overflow:hidden; display:none; flex-direction:column;">
                    <div style="padding:10px 12px; display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid rgba(255,255,255,0.08);">
                        <div style="font-size:12px; font-weight:900; color:rgba(255,255,255,0.92);">脚本历史</div>
                        <div id="ai_draft_history_close" style="padding:6px 10px; border-radius:999px; background:rgba(255,255,255,0.10); cursor:pointer; user-select:none; color:rgba(255,255,255,0.85); font-weight:800; font-size:12px;">关闭</div>
                    </div>
                    <div id="ai_draft_history_list" style="flex:1; overflow:auto; padding:10px 10px; display:flex; flex-direction:column; gap:8px;"></div>
                </div>
            `;
            document.body.appendChild(existing);
            existing.addEventListener('click', (e) => {
                const t = e && e.target ? e.target : null;
                if (t === existing) existing.style.display = 'none';
            });
            const closeBtn = existing.querySelector('#ai_draft_close');
            if (closeBtn) closeBtn.addEventListener('click', () => { existing.style.display = 'none'; });
        }
        existing.style.display = 'block';
        existing.dataset.jobId = jid;
        try {
            const url = `/api/v1/ai/jobs/${encodeURIComponent(jid)}/draft?user_id=${uid}`;
            const res = await this.apiRequest('GET', url, undefined, { cancel_key: `ai:draft:${jid}`, dedupe_key: url });
            if (!res.ok) return;
            const data = await res.json();
            const txt = existing.querySelector('#ai_draft_text');
            if (txt) txt.value = JSON.stringify(data && data.draft_json ? data.draft_json : {}, null, 2);
        } catch (_) {
        }
        const saveBtn = existing.querySelector('#ai_draft_save');
        const rerunBtn = existing.querySelector('#ai_draft_rerun');
        const histBtn = existing.querySelector('#ai_draft_history');
        const histPanel = existing.querySelector('#ai_draft_history_panel');
        const histClose = existing.querySelector('#ai_draft_history_close');
        const doParse = () => {
            const txt = existing.querySelector('#ai_draft_text');
            const raw = txt ? String(txt.value || '') : '';
            return JSON.parse(raw);
        };
        if (saveBtn) saveBtn.onclick = async () => {
            try {
                const draft = doParse();
                const url = `/api/v1/ai/jobs/${encodeURIComponent(jid)}/draft`;
                const res = await this.apiRequest('POST', url, { user_id: uid, draft_json: draft, source: 'user_edit' }, { cancel_key: `ai:draft:save:${jid}` });
                if (res.ok) this.toast('脚本已保存');
            } catch (e) {
                this.toast('脚本JSON格式不正确');
            }
        };
        if (rerunBtn) rerunBtn.onclick = async () => {
            try {
                const draft = doParse();
                const url = `/api/v1/ai/jobs/${encodeURIComponent(jid)}/rerun`;
                const res = await this.apiRequest('POST', url, { user_id: uid, draft_json: draft, source: 'user_edit' }, { cancel_key: `ai:draft:rerun:${jid}` });
                if (!res.ok) return;
                existing.style.display = 'none';
                this.toast('已按脚本重做');
                try { if (typeof this.loadProfile === 'function') this.loadProfile(uid); } catch (_) {}
            } catch (_) {
                this.toast('脚本JSON格式不正确');
            }
        };
        const metaOf = (d) => {
            const ps = (d && typeof d === 'object') ? d : {};
            const scenes = Array.isArray(ps.scenes) ? ps.scenes : [];
            const cover = (ps.cover && typeof ps.cover === 'object') ? ps.cover : {};
            const music = (ps.music && typeof ps.music === 'object') ? ps.music : {};
            let total = 0;
            scenes.forEach(s => {
                try {
                    const v = Number((s && typeof s === 'object') ? s.duration_sec : 0);
                    if (Number.isFinite(v)) total += v;
                } catch (_) {
                }
            });
            const first = scenes[0] && typeof scenes[0] === 'object' ? String(scenes[0].narration || scenes[0].subtitle || '') : '';
            const last = scenes[scenes.length - 1] && typeof scenes[scenes.length - 1] === 'object' ? String(scenes[scenes.length - 1].narration || scenes[scenes.length - 1].subtitle || '') : '';
            return {
                title: String(cover.title_text || ''),
                mood: String(music.mood || ''),
                scenes: scenes.length,
                total_sec: total,
                first: first.slice(0, 60),
                last: last.slice(0, 60),
            };
        };
        const escHtml = (s) => {
            const t = String(s == null ? '' : s);
            return t
                .replaceAll('&', '&amp;')
                .replaceAll('<', '&lt;')
                .replaceAll('>', '&gt;')
                .replaceAll('"', '&quot;')
                .replaceAll("'", '&#39;');
        };
        const fmtSource = (src) => {
            const s = String(src || '').trim();
            if (!s) return 'unknown';
            if (s === 'user_edit') return '手动保存';
            if (s === 'deepseek') return '初稿';
            if (s === 'chat_ai_done') return 'AI建议';
            if (s === 'draft_loaded') return '脚本重做';
            if (s === 'worker') return '系统写入';
            if (s.startsWith('rollback:')) return `回滚(${s.slice('rollback:'.length)})`;
            if (s.startsWith('chat_ai')) return 'AI建议';
            return s;
        };
        const diffScript = (a, b) => {
            const pa = (a && typeof a === 'object') ? a : {};
            const pb = (b && typeof b === 'object') ? b : {};
            const sa = Array.isArray(pa.scenes) ? pa.scenes : [];
            const sb = Array.isArray(pb.scenes) ? pb.scenes : [];
            const keyOf = (s, i) => {
                try {
                    const v = s && typeof s === 'object' ? (s.idx ?? s.index ?? s.id) : null;
                    const n = Number(v);
                    if (Number.isFinite(n) && n > 0) return n;
                } catch (_) {
                }
                return i + 1;
            };
            const norm = (s) => {
                const o = s && typeof s === 'object' ? s : {};
                return {
                    duration: Number(o.duration_sec || 0) || 0,
                    narration: String(o.narration || ''),
                    subtitle: String(o.subtitle || ''),
                    v: String(o.visual_prompt_en || o.visual_prompt || ''),
                };
            };
            const ma = new Map();
            const mb = new Map();
            sa.forEach((s, i) => { ma.set(keyOf(s, i), norm(s)); });
            sb.forEach((s, i) => { mb.set(keyOf(s, i), norm(s)); });
            const keys = Array.from(new Set([...ma.keys(), ...mb.keys()])).sort((x, y) => x - y);
            const added = [];
            const removed = [];
            const changed = [];
            const detail = [];
            keys.forEach(k => {
                const va = ma.get(k);
                const vb = mb.get(k);
                if (!va && vb) { added.push(k); return; }
                if (va && !vb) { removed.push(k); return; }
                if (!va || !vb) return;
                const diffs = [];
                if (va.duration !== vb.duration) diffs.push(`时长 ${va.duration}s→${vb.duration}s`);
                if (va.narration !== vb.narration) diffs.push('旁白');
                if (va.subtitle !== vb.subtitle) diffs.push('字幕');
                if (va.v !== vb.v) diffs.push('画面提示词');
                if (diffs.length) {
                    changed.push(k);
                    if (detail.length < 18) detail.push(`分镜#${k}：${diffs.join('、')}`);
                }
            });
            const head = [];
            if (added.length) head.push(`新增分镜：${added.length}（${added.slice(0, 10).join(', ')}${added.length > 10 ? '…' : ''}）`);
            if (removed.length) head.push(`删除分镜：${removed.length}（${removed.slice(0, 10).join(', ')}${removed.length > 10 ? '…' : ''}）`);
            if (changed.length) head.push(`修改分镜：${changed.length}（${changed.slice(0, 10).join(', ')}${changed.length > 10 ? '…' : ''}）`);
            return { head, detail, added, removed, changed };
        };
        const mergeScenesByIdx = (curDraft, otherDraft) => {
            const pa = (curDraft && typeof curDraft === 'object') ? curDraft : {};
            const pb = (otherDraft && typeof otherDraft === 'object') ? otherDraft : {};
            const sa = Array.isArray(pa.scenes) ? pa.scenes : [];
            const sb = Array.isArray(pb.scenes) ? pb.scenes : [];
            const keyOf = (s, i) => {
                try {
                    const v = s && typeof s === 'object' ? (s.idx ?? s.index ?? s.id) : null;
                    const n = Number(v);
                    if (Number.isFinite(n) && n > 0) return n;
                } catch (_) {
                }
                return i + 1;
            };
            const normKeep = (s, idx) => {
                const o = s && typeof s === 'object' ? s : {};
                const out = { ...o };
                if (out.idx == null) out.idx = idx;
                return out;
            };
            const ma = new Map();
            const mb = new Map();
            sa.forEach((s, i) => { ma.set(keyOf(s, i), normKeep(s, keyOf(s, i))); });
            sb.forEach((s, i) => { mb.set(keyOf(s, i), normKeep(s, keyOf(s, i))); });
            const keys = Array.from(new Set([...ma.keys(), ...mb.keys()])).sort((x, y) => x - y);
            const out = [];
            keys.forEach(k => {
                const vb = mb.get(k);
                if (vb) out.push(vb);
            });
            return out;
        };
        const showDraftDiff = (title, lines, ctx) => {
            let m = existing.querySelector('#ai_draft_diff_modal');
            if (!m) {
                m = document.createElement('div');
                m.id = 'ai_draft_diff_modal';
                m.style.position = 'absolute';
                m.style.inset = '0';
                m.style.background = 'rgba(0,0,0,0.60)';
                m.style.display = 'none';
                m.style.zIndex = '10000';
                m.innerHTML = `
                    <div style="position:absolute; left:50%; top:50%; transform:translate(-50%,-50%); width:min(720px, calc(100vw - 32px)); max-height:min(70vh, 620px); background:#111; border:1px solid rgba(255,255,255,0.10); border-radius:14px; overflow:hidden; display:flex; flex-direction:column;">
                        <div style="padding:12px 14px; display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid rgba(255,255,255,0.08);">
                            <div id="ai_draft_diff_title" style="font-size:13px; font-weight:900; color:rgba(255,255,255,0.92);">对比</div>
                            <div id="ai_draft_diff_close" style="padding:6px 10px; border-radius:999px; background:rgba(255,255,255,0.10); cursor:pointer; user-select:none; color:rgba(255,255,255,0.85); font-weight:800; font-size:12px;">关闭</div>
                        </div>
                        <div id="ai_draft_diff_body" style="padding:12px 14px; overflow:auto; display:flex; flex-direction:column; gap:8px;"></div>
                        <div id="ai_draft_diff_actions" style="padding:10px 14px; border-top:1px solid rgba(255,255,255,0.08); display:none; gap:8px; align-items:center; justify-content:flex-end;"></div>
                    </div>
                `;
                existing.appendChild(m);
                m.addEventListener('click', (e) => {
                    const t = e && e.target ? e.target : null;
                    if (t === m) m.style.display = 'none';
                });
                const c = m.querySelector('#ai_draft_diff_close');
                if (c) c.addEventListener('click', () => { m.style.display = 'none'; });
            }
            try {
                m._diffCtx = (ctx && typeof ctx === 'object') ? ctx : null;
            } catch (_) {
            }
            const tEl = m.querySelector('#ai_draft_diff_title');
            const bEl = m.querySelector('#ai_draft_diff_body');
            const aEl = m.querySelector('#ai_draft_diff_actions');
            if (tEl) tEl.innerText = String(title || '对比');
            if (bEl) {
                bEl.innerHTML = '';
                const arr = Array.isArray(lines) ? lines : [];
                if (arr.length === 0) {
                    bEl.innerHTML = '<div style="color:rgba(255,255,255,0.70); font-size:12px;">无差异</div>';
                } else {
                    arr.forEach(x => {
                        const it = document.createElement('div');
                        it.style.padding = '10px 10px';
                        it.style.borderRadius = '12px';
                        it.style.border = '1px solid rgba(255,255,255,0.08)';
                        it.style.background = 'rgba(255,255,255,0.04)';
                        it.style.fontSize = '12px';
                        it.style.color = 'rgba(255,255,255,0.88)';
                        it.style.lineHeight = '1.6';
                        it.innerText = String(x || '');
                        bEl.appendChild(it);
                    });
                }
                const hasCtx = ctx && typeof ctx === 'object' && ctx.cur && ctx.other;
                const diff = hasCtx && ctx.diff && typeof ctx.diff === 'object' ? ctx.diff : null;
                if (hasCtx && diff && (Array.isArray(diff.added) || Array.isArray(diff.removed) || Array.isArray(diff.changed))) {
                    const plan = (() => {
                        try {
                            const o = ctx.other && typeof ctx.other === 'object' ? ctx.other : {};
                            const m = o._meta && typeof o._meta === 'object' ? o._meta : {};
                            const p = m.apply_plan && typeof m.apply_plan === 'object' ? m.apply_plan : null;
                            if (!p) return null;
                            const si = Array.isArray(p.scene_idxs) ? p.scene_idxs : [];
                            const fs = Array.isArray(p.fields) ? p.fields : [];
                            const si2 = Array.from(new Set(si.map(x => Number(x)).filter(x => Number.isFinite(x) && x > 0))).sort((a, b) => a - b);
                            const fs2 = Array.from(new Set(fs.map(x => String(x || '').trim()).filter(Boolean)));
                            const sf = Array.isArray(p.scene_fields) ? p.scene_fields : [];
                            const map = new Map();
                            sf.forEach(it => {
                                try {
                                    const idx = Number(it && it.idx);
                                    const fs = Array.isArray(it && it.fields) ? it.fields : [];
                                    const fs3 = Array.from(new Set(fs.map(x => String(x || '').trim()).filter(Boolean)));
                                    const fr = it && typeof it === 'object' && it.field_reasons && typeof it.field_reasons === 'object' ? it.field_reasons : null;
                                    const fr2 = {};
                                    if (fr) {
                                        Object.keys(fr).forEach(k => {
                                            try {
                                                const kk = String(k || '').trim();
                                                const vv = String(fr[k] || '').trim();
                                                if (kk && vv) fr2[kk] = vv;
                                            } catch (_) {
                                            }
                                        });
                                    }
                                    const rr = it && typeof it === 'object' ? String(it.reason || '').trim() : '';
                                    const rt = it && typeof it === 'object' && Array.isArray(it.reason_tags) ? it.reason_tags : [];
                                    const tags = Array.from(new Set(rt.map(x => String(x || '').trim()).filter(Boolean))).slice(0, 5);
                                    if (Number.isFinite(idx) && idx > 0) map.set(idx, { fields: fs3, field_reasons: fr2, reason: rr, reason_tags: tags });
                                } catch (_) {
                                }
                            });
                            return { scene_idxs: si2, fields: fs2, scene_fields: map };
                        } catch (_) {
                            return null;
                        }
                    })();
                    const panel = document.createElement('div');
                    panel.style.padding = '12px 12px';
                    panel.style.borderRadius = '12px';
                    panel.style.border = '1px solid rgba(255,255,255,0.08)';
                    panel.style.background = 'rgba(255,255,255,0.03)';
                    panel.style.display = 'flex';
                    panel.style.flexDirection = 'column';
                    panel.style.gap = '10px';
                    let impact = '';
                    try {
                        const a2 = metaOf(ctx.cur);
                        const b2 = metaOf(ctx.other);
                        const ds = b2.scenes - a2.scenes;
                        const dt = b2.total_sec - a2.total_sec;
                        const sds = ds > 0 ? `+${ds}` : `${ds}`;
                        const sdt = dt > 0 ? `+${dt}` : `${dt}`;
                        const addN = Array.isArray(diff.added) ? diff.added.length : 0;
                        const delN = Array.isArray(diff.removed) ? diff.removed.length : 0;
                        const chN = Array.isArray(diff.changed) ? diff.changed.length : 0;
                        impact = `影响预估：时长${sdt}s，分镜${sds}（+${addN}/-${delN}/改${chN}）`;
                    } catch (_) {
                        impact = '';
                    }
                    panel.innerHTML = `
                        <div style="display:flex; align-items:center; justify-content:space-between; gap:10px;">
                            <div style="font-size:12px; font-weight:900; color:rgba(255,255,255,0.92);">选择性应用（仅分镜）</div>
                            <div style="display:flex; gap:8px; align-items:center;">
                                <div id="ai_draft_sel_rec" style="padding:6px 10px; border-radius:999px; background:rgba(255,255,255,0.12); cursor:pointer; user-select:none; font-weight:800; font-size:12px;">推荐</div>
                                <div id="ai_draft_sel_apply_rec" style="padding:6px 10px; border-radius:999px; background:rgba(254,44,85,0.85); cursor:pointer; user-select:none; color:white; font-weight:900; font-size:12px;">应用推荐</div>
                                <div id="ai_draft_sel_all" style="padding:6px 10px; border-radius:999px; background:rgba(255,255,255,0.12); cursor:pointer; user-select:none; font-weight:800; font-size:12px;">全选</div>
                                <div id="ai_draft_sel_none" style="padding:6px 10px; border-radius:999px; background:rgba(255,255,255,0.12); cursor:pointer; user-select:none; font-weight:800; font-size:12px;">清空</div>
                                <div id="ai_draft_apply_selected" style="padding:6px 10px; border-radius:999px; background:rgba(255,255,255,0.12); cursor:pointer; user-select:none; color:rgba(255,255,255,0.92); font-weight:900; font-size:12px;">应用勾选分镜</div>
                            </div>
                        </div>
                        <div style="font-size:11px; color:rgba(255,255,255,0.55); line-height:1.4;">${escHtml(impact)}</div>
                        <div id="ai_draft_sel_list" style="display:flex; flex-direction:column; gap:8px;"></div>
                    `;
                    bEl.appendChild(panel);

                    const list = panel.querySelector('#ai_draft_sel_list');
                    const keyOf = (s, i) => {
                        try {
                            const v = s && typeof s === 'object' ? (s.idx ?? s.index ?? s.id) : null;
                            const n = Number(v);
                            if (Number.isFinite(n) && n > 0) return n;
                        } catch (_) {
                        }
                        return i + 1;
                    };
                    const mapOf = (ps) => {
                        const p = ps && typeof ps === 'object' ? ps : {};
                        const scenes = Array.isArray(p.scenes) ? p.scenes : [];
                        const m = new Map();
                        scenes.forEach((s, i) => { m.set(keyOf(s, i), s); });
                        return m;
                    };
                    const curMap = mapOf(ctx.cur);
                    const otherMap = mapOf(ctx.other);
                    const uniq = (arr) => Array.from(new Set((Array.isArray(arr) ? arr : []).map(x => Number(x)).filter(x => Number.isFinite(x) && x > 0))).sort((a, b) => a - b);
                    const added = uniq(diff.added);
                    const removed = uniq(diff.removed);
                    const changed = uniq(diff.changed);
                    const allIdx = uniq([].concat(added, removed, changed));
                    if (list) {
                        if (allIdx.length === 0) {
                            list.innerHTML = '<div style="color:rgba(255,255,255,0.55); font-size:12px;">没有可选择的分镜变更</div>';
                        } else {
                            list.innerHTML = '';
                            allIdx.forEach(k => {
                                const row = document.createElement('label');
                                row.style.display = 'flex';
                                row.style.alignItems = 'flex-start';
                                row.style.gap = '10px';
                                row.style.padding = '10px 10px';
                                row.style.borderRadius = '12px';
                                row.style.border = '1px solid rgba(255,255,255,0.08)';
                                row.style.background = 'rgba(255,255,255,0.04)';
                                row.style.cursor = 'pointer';
                                const tag = added.includes(k) ? '新增' : (removed.includes(k) ? '删除' : '修改');
                                const scene = otherMap.get(k) || curMap.get(k) || null;
                                const sObj = scene && typeof scene === 'object' ? scene : {};
                                const summary = String(sObj.narration || sObj.subtitle || '').slice(0, 60);
                                row.innerHTML = `
                                    <input type="checkbox" class="ai_draft_sel_cb" data-idx="${k}" style="margin-top:2px;" />
                                    <div style="flex:1; min-width:0;">
                                        <div style="display:flex; justify-content:space-between; gap:10px; align-items:center;">
                                            <div style="font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; font-size:12px; color:rgba(255,255,255,0.85);">分镜#${k}</div>
                                            <div style="font-size:11px; color:rgba(255,255,255,0.60);">${tag}</div>
                                        </div>
                                        <div style="font-size:12px; color:rgba(255,255,255,0.72); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${escHtml(summary || '（空）')}</div>
                                        ${
                                            tag === '修改'
                                                ? `<div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:8px;">
                                                    <label style="display:flex; gap:6px; align-items:center; font-size:12px; color:rgba(255,255,255,0.72); cursor:pointer;"><input type="checkbox" class="ai_draft_field_cb" data-idx="${k}" data-field="duration_sec" checked>时长</label>
                                                    <label style="display:flex; gap:6px; align-items:center; font-size:12px; color:rgba(255,255,255,0.72); cursor:pointer;"><input type="checkbox" class="ai_draft_field_cb" data-idx="${k}" data-field="narration" checked>旁白</label>
                                                    <label style="display:flex; gap:6px; align-items:center; font-size:12px; color:rgba(255,255,255,0.72); cursor:pointer;"><input type="checkbox" class="ai_draft_field_cb" data-idx="${k}" data-field="subtitle" checked>字幕</label>
                                                    <label style="display:flex; gap:6px; align-items:center; font-size:12px; color:rgba(255,255,255,0.72); cursor:pointer;"><input type="checkbox" class="ai_draft_field_cb" data-idx="${k}" data-field="visual_prompt_en" checked>画面</label>
                                                </div><div class="ai_draft_reason_line" data-idx="${k}" style="margin-top:8px; font-size:11px; color:rgba(255,255,255,0.55); line-height:1.4;"></div>`
                                                : ''
                                        }
                                    </div>
                                `;
                                try {
                                    if (plan && plan.scene_fields && plan.scene_fields.size && plan.scene_fields.has(k)) {
                                        const rec = plan.scene_fields.get(k);
                                        const reasons = rec && rec.field_reasons && typeof rec.field_reasons === 'object' ? rec.field_reasons : {};
                                        const overall = rec && typeof rec.reason === 'string' ? rec.reason : '';
                                        const tags = rec && Array.isArray(rec.reason_tags) ? rec.reason_tags : [];
                                        const line = row.querySelector(`.ai_draft_reason_line[data-idx="${k}"]`);
                                        const parts = [];
                                        if (overall) parts.push(String(overall));
                                        Object.keys(reasons || {}).forEach(f => {
                                            try {
                                                const v = String(reasons[f] || '').trim();
                                                if (v) parts.push(`${f}: ${v}`);
                                            } catch (_) {
                                            }
                                        });
                                        if (line && parts.length) line.innerText = `推荐原因：${parts.slice(0, 3).join('；')}`;
                                        if (line && (!parts.length) && tags.length) line.innerText = `推荐方向：${tags.slice(0, 3).join(' / ')}`;
                                        if (line && parts.length && tags.length) line.innerText = `${line.innerText}（${tags.slice(0, 3).join(' / ')}）`;
                                        const fbs = row.querySelectorAll(`.ai_draft_field_cb[data-idx="${k}"]`);
                                        fbs.forEach(cb => {
                                            try {
                                                const f = String(cb.dataset.field || '');
                                                if (f && reasons && reasons[f]) cb.parentElement.title = String(reasons[f] || '');
                                            } catch (_) {
                                            }
                                        });
                                    }
                                } catch (_) {
                                }
                                list.appendChild(row);
                            });
                        }
                    }
                    const allBtn = panel.querySelector('#ai_draft_sel_all');
                    const noneBtn = panel.querySelector('#ai_draft_sel_none');
                    const recBtn = panel.querySelector('#ai_draft_sel_rec');
                    const applyRecBtn = panel.querySelector('#ai_draft_sel_apply_rec');
                    const applyBtn = panel.querySelector('#ai_draft_apply_selected');
                    const showApplyConfirm = (title, payload, onConfirm) => {
                        let mm = existing.querySelector('#ai_draft_apply_confirm');
                        if (!mm) {
                            mm = document.createElement('div');
                            mm.id = 'ai_draft_apply_confirm';
                            mm.style.position = 'absolute';
                            mm.style.inset = '0';
                            mm.style.background = 'rgba(0,0,0,0.60)';
                            mm.style.display = 'none';
                            mm.style.zIndex = '11000';
                            mm.innerHTML = `
                                <div style="position:absolute; left:50%; top:50%; transform:translate(-50%,-50%); width:min(760px, calc(100vw - 32px)); max-height:min(74vh, 720px); background:#111; border:1px solid rgba(255,255,255,0.10); border-radius:14px; overflow:hidden; display:flex; flex-direction:column;">
                                    <div style="padding:12px 14px; display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid rgba(255,255,255,0.08);">
                                        <div id="ai_draft_apply_confirm_title" style="font-size:13px; font-weight:900; color:rgba(255,255,255,0.92);">确认应用</div>
                                        <div id="ai_draft_apply_confirm_close" style="padding:6px 10px; border-radius:999px; background:rgba(255,255,255,0.10); cursor:pointer; user-select:none; color:rgba(255,255,255,0.85); font-weight:800; font-size:12px;">关闭</div>
                                    </div>
                                    <div id="ai_draft_apply_confirm_body" style="padding:12px 14px; overflow:auto; display:flex; flex-direction:column; gap:8px;"></div>
                                    <div style="padding:10px 14px; border-top:1px solid rgba(255,255,255,0.08); display:flex; justify-content:flex-end; gap:8px;">
                                        <div id="ai_draft_apply_confirm_cancel" style="padding:8px 12px; border-radius:999px; background:rgba(255,255,255,0.14); cursor:pointer; user-select:none; color:rgba(255,255,255,0.92); font-weight:800; font-size:12px;">先不应用</div>
                                        <div id="ai_draft_apply_confirm_ok" style="padding:8px 12px; border-radius:999px; background:rgba(254,44,85,0.85); cursor:pointer; user-select:none; color:white; font-weight:900; font-size:12px;">确认应用</div>
                                    </div>
                                </div>
                            `;
                            existing.appendChild(mm);
                            mm.addEventListener('click', (e) => {
                                const t = e && e.target ? e.target : null;
                                if (t === mm) mm.style.display = 'none';
                            });
                            const close = mm.querySelector('#ai_draft_apply_confirm_close');
                            const cancel = mm.querySelector('#ai_draft_apply_confirm_cancel');
                            if (close) close.addEventListener('click', () => { mm.style.display = 'none'; });
                            if (cancel) cancel.addEventListener('click', () => { mm.style.display = 'none'; });
                        }
                        const tEl = mm.querySelector('#ai_draft_apply_confirm_title');
                        const bEl = mm.querySelector('#ai_draft_apply_confirm_body');
                        if (tEl) tEl.innerText = String(title || '确认应用');
                        if (bEl) {
                            bEl.innerHTML = '';
                            const data = payload && typeof payload === 'object' ? payload : { lines: Array.isArray(payload) ? payload : [] };
                            const arr = Array.isArray(data.lines) ? data.lines : [];
                            const items = Array.isArray(data.items) ? data.items : [];
                            if (!arr.length && !items.length) {
                                bEl.innerHTML = '<div style="color:rgba(255,255,255,0.70); font-size:12px;">无内容</div>';
                            }
                            if (arr.length) {
                                arr.forEach(x => {
                                    const it = document.createElement('div');
                                    it.style.padding = '10px 10px';
                                    it.style.borderRadius = '12px';
                                    it.style.border = '1px solid rgba(255,255,255,0.08)';
                                    it.style.background = 'rgba(255,255,255,0.04)';
                                    it.style.fontSize = '12px';
                                    it.style.color = 'rgba(255,255,255,0.88)';
                                    it.style.lineHeight = '1.6';
                                    it.innerText = String(x || '');
                                    bEl.appendChild(it);
                                });
                            }
                            if (items.length) {
                                const tip = document.createElement('div');
                                tip.style.fontSize = '11px';
                                tip.style.color = 'rgba(255,255,255,0.55)';
                                tip.style.lineHeight = '1.4';
                                tip.innerText = '可在确认前取消分镜或取消某些字段（仅对“修改”分镜有效）';
                                bEl.appendChild(tip);
                                items.forEach(it => {
                                    const idx = Number(it.idx || 0);
                                    if (!Number.isFinite(idx) || idx <= 0) return;
                                    const row = document.createElement('div');
                                    row.style.padding = '10px 10px';
                                    row.style.borderRadius = '12px';
                                    row.style.border = '1px solid rgba(255,255,255,0.08)';
                                    row.style.background = 'rgba(255,255,255,0.04)';
                                    row.style.display = 'flex';
                                    row.style.flexDirection = 'column';
                                    row.style.gap = '8px';
                                    const tag = String(it.tag || '');
                                    const name = String(it.name || '');
                                    const fs = Array.isArray(it.fields) ? it.fields : [];
                                    const durBefore = it.duration_before;
                                    const durAfter = it.duration_after;
                                    const durTxt = (Number.isFinite(Number(durBefore)) && Number.isFinite(Number(durAfter)) && Number(durBefore) !== Number(durAfter))
                                        ? ` 时长${Number(durBefore)}s→${Number(durAfter)}s`
                                        : '';
                                    row.innerHTML = `
                                        <label style="display:flex; gap:10px; align-items:flex-start; cursor:pointer;">
                                            <input type="checkbox" class="ai_apply_item_cb" data-idx="${idx}" ${it.enabled === false ? '' : 'checked'} style="margin-top:2px;" />
                                            <div style="flex:1; min-width:0;">
                                                <div style="display:flex; justify-content:space-between; gap:10px; align-items:center;">
                                                    <div style="font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; font-size:12px; color:rgba(255,255,255,0.88);">分镜#${idx}</div>
                                                    <div style="font-size:11px; color:rgba(255,255,255,0.60);">${escHtml(tag || '')}</div>
                                                </div>
                                                <div style="font-size:12px; color:rgba(255,255,255,0.74); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${escHtml(name || '（空）')}</div>
                                                <div style="font-size:11px; color:rgba(255,255,255,0.55); line-height:1.4;">${escHtml(durTxt)}</div>
                                            </div>
                                        </label>
                                    `;
                                    if (tag === '修改') {
                                        const map = new Set(fs.map(x => String(x || '').trim()).filter(Boolean));
                                        const fields = [
                                            { k: 'duration_sec', t: '时长' },
                                            { k: 'narration', t: '旁白' },
                                            { k: 'subtitle', t: '字幕' },
                                            { k: 'visual_prompt_en', t: '画面' },
                                        ];
                                        const wrap = document.createElement('div');
                                        wrap.style.display = 'flex';
                                        wrap.style.gap = '10px';
                                        wrap.style.flexWrap = 'wrap';
                                        fields.forEach(f0 => {
                                            const lb = document.createElement('label');
                                            lb.style.display = 'flex';
                                            lb.style.gap = '6px';
                                            lb.style.alignItems = 'center';
                                            lb.style.fontSize = '12px';
                                            lb.style.color = 'rgba(255,255,255,0.72)';
                                            lb.style.cursor = 'pointer';
                                            lb.innerHTML = `<input type="checkbox" class="ai_apply_item_field" data-idx="${idx}" data-field="${f0.k}" ${map.has(f0.k) ? 'checked' : ''}>${f0.t}`;
                                            wrap.appendChild(lb);
                                        });
                                        row.appendChild(wrap);

                                        const preview = document.createElement('div');
                                        preview.className = 'ai_apply_preview';
                                        preview.style.display = 'flex';
                                        preview.style.flexDirection = 'column';
                                        preview.style.gap = '8px';
                                        const mkPrev = (k, title, before, after) => {
                                            const b = String(before || '').trim();
                                            const a = String(after || '').trim();
                                            const box = document.createElement('div');
                                            box.className = 'ai_apply_prev';
                                            box.dataset.field = k;
                                            box.style.padding = '10px 10px';
                                            box.style.borderRadius = '12px';
                                            box.style.border = '1px solid rgba(255,255,255,0.08)';
                                            box.style.background = 'rgba(0,0,0,0.18)';
                                            box.style.display = 'none';
                                            box.style.flexDirection = 'column';
                                            box.style.gap = '6px';
                                            const head = document.createElement('div');
                                            head.style.fontSize = '12px';
                                            head.style.fontWeight = '900';
                                            head.style.color = 'rgba(255,255,255,0.92)';
                                            head.innerText = title;
                                            const l1 = document.createElement('div');
                                            l1.style.fontSize = '12px';
                                            l1.style.color = 'rgba(255,255,255,0.72)';
                                            l1.style.lineHeight = '1.6';
                                            l1.innerText = `原：${b || '（空）'}`;
                                            const l2 = document.createElement('div');
                                            l2.style.fontSize = '12px';
                                            l2.style.color = 'rgba(255,255,255,0.88)';
                                            l2.style.lineHeight = '1.6';
                                            l2.innerText = `新：${a || '（空）'}`;
                                            box.appendChild(head);
                                            box.appendChild(l1);
                                            box.appendChild(l2);
                                            return box;
                                        };
                                        preview.appendChild(mkPrev('duration_sec', '时长', `${Number(it.duration_before || 0)}s`, `${Number(it.duration_after || 0)}s`));
                                        preview.appendChild(mkPrev('narration', '旁白', it.narration_before, it.narration_after));
                                        preview.appendChild(mkPrev('subtitle', '字幕', it.subtitle_before, it.subtitle_after));
                                        preview.appendChild(mkPrev('visual_prompt_en', '画面提示词', it.visual_before, it.visual_after));
                                        row.appendChild(preview);

                                        const update = () => {
                                            const enabled = !!row.querySelector('.ai_apply_item_cb')?.checked;
                                            const fbs = row.querySelectorAll('.ai_apply_item_field');
                                            const set = new Set();
                                            fbs.forEach(cb => { try { if (cb.checked) set.add(String(cb.dataset.field || '')); } catch (_) {} });
                                            const blocks = row.querySelectorAll('.ai_apply_prev');
                                            blocks.forEach(bb => {
                                                try {
                                                    const f = String(bb.dataset.field || '');
                                                    const show = enabled && set.has(f);
                                                    bb.style.display = show ? 'flex' : 'none';
                                                } catch (_) {
                                                }
                                            });
                                            try {
                                                preview.style.display = enabled && set.size ? 'flex' : 'none';
                                            } catch (_) {
                                            }
                                        };
                                        try {
                                            const main = row.querySelector('.ai_apply_item_cb');
                                            if (main) main.onchange = update;
                                            const fbs = row.querySelectorAll('.ai_apply_item_field');
                                            fbs.forEach(cb => { try { cb.onchange = update; } catch (_) {} });
                                            update();
                                        } catch (_) {
                                        }
                                    }
                                    bEl.appendChild(row);
                                });
                            }
                        }
                        const ok = mm.querySelector('#ai_draft_apply_confirm_ok');
                        if (ok) ok.onclick = async () => {
                            mm.style.display = 'none';
                            try {
                                const data = payload && typeof payload === 'object' ? payload : null;
                                const items = data && Array.isArray(data.items) ? data.items : [];
                                if (items.length) {
                                    const cbs = mm.querySelectorAll('.ai_apply_item_cb');
                                    cbs.forEach(cb => {
                                        try {
                                            const k = Number(cb.dataset.idx || 0);
                                            const el = panel.querySelector(`.ai_draft_sel_cb[data-idx="${k}"]`);
                                            if (el) el.checked = !!cb.checked;
                                        } catch (_) {
                                        }
                                    });
                                    const fbs = mm.querySelectorAll('.ai_apply_item_field');
                                    fbs.forEach(cb => {
                                        try {
                                            const k = Number(cb.dataset.idx || 0);
                                            const f = String(cb.dataset.field || '');
                                            const el = panel.querySelector(`.ai_draft_field_cb[data-idx="${k}"][data-field="${f}"]`);
                                            if (el) el.checked = !!cb.checked;
                                        } catch (_) {
                                        }
                                    });
                                }
                            } catch (_) {
                            }
                            try { await onConfirm(); } catch (_) {}
                        };
                        mm.style.display = 'block';
                    };
                    const buildSelectionSummary = () => {
                        const txt = existing.querySelector('#ai_draft_text');
                        if (!txt) return null;
                        let cur = null;
                        try { cur = JSON.parse(String(txt.value || '')); } catch (_) { return { err: '当前脚本JSON格式不正确' }; }
                        const curPs = cur && typeof cur === 'object' ? cur : {};
                        const otherPs = ctx.other && typeof ctx.other === 'object' ? ctx.other : {};
                        const curM = mapOf(curPs);
                        const othM = mapOf(otherPs);
                        const changedSet = new Set(changed);
                        const addedSet = new Set(added);
                        const removedSet = new Set(removed);
                        const selected = [];
                        const cbs = panel.querySelectorAll('.ai_draft_sel_cb');
                        cbs.forEach(cb => {
                            try {
                                if (cb.checked) {
                                    const k = Number(cb.dataset.idx || 0);
                                    if (Number.isFinite(k) && k > 0) selected.push(k);
                                }
                            } catch (_) {
                            }
                        });
                        selected.sort((a, b) => a - b);
                        const fieldsFor = (k) => {
                            const out = [];
                            const fbs = panel.querySelectorAll(`.ai_draft_field_cb[data-idx="${k}"]`);
                            fbs.forEach(cb => { try { if (cb.checked) out.push(String(cb.dataset.field || '')); } catch (_) {} });
                            return Array.from(new Set(out.filter(Boolean)));
                        };
                        const sceneTitle = (s) => {
                            const o = s && typeof s === 'object' ? s : {};
                            return String(o.subtitle || o.narration || '').slice(0, 40);
                        };
                        const lineOf = (k) => {
                            const tag = addedSet.has(k) ? '新增' : (removedSet.has(k) ? '删除' : '修改');
                            const fs = fieldsFor(k);
                            const curS = curM.get(k);
                            const othS = othM.get(k);
                            const name = sceneTitle(othS || curS);
                            let extra = '';
                            if (tag === '修改' && fs.includes('duration_sec')) {
                                const a = curS && typeof curS === 'object' ? Number(curS.duration_sec || 0) : 0;
                                const b = othS && typeof othS === 'object' ? Number(othS.duration_sec || 0) : 0;
                                if (Number.isFinite(a) && Number.isFinite(b) && a !== b) extra = ` 时长${a}s→${b}s`;
                            }
                            if (tag === '修改' && fs.length) extra = `${extra} 字段(${fs.join('、')})`;
                            return `分镜#${k} ${tag}${name ? `：${name}` : ''}${extra}`;
                        };
                        const lines = [];
                        if (!selected.length) return { err: '未选择分镜' };
                        lines.push(`将应用分镜：${selected.length} 个`);
                        const metaA = metaOf(curPs);
                        const metaB = metaOf(otherPs);
                        const ds = metaB.scenes - metaA.scenes;
                        const dt = metaB.total_sec - metaA.total_sec;
                        const sds = ds > 0 ? `+${ds}` : `${ds}`;
                        const sdt = dt > 0 ? `+${dt}` : `${dt}`;
                        lines.push(`影响预估：时长${sdt}s，分镜${sds}`);
                        selected.slice(0, 30).forEach(k => { lines.push(lineOf(k)); });
                        if (selected.length > 30) lines.push(`… 还有 ${selected.length - 30} 个分镜`);
                        const hasTitle = (() => {
                            try { return metaA.title !== metaB.title; } catch (_) { return false; }
                        })();
                        const hasMood = (() => {
                            try { return metaA.mood !== metaB.mood; } catch (_) { return false; }
                        })();
                        const warns = [];
                        if (hasTitle) warns.push('提示：标题变更不在“分镜选择性应用”范围内');
                        if (hasMood) warns.push('提示：音乐情绪变更不在“分镜选择性应用”范围内');
                        if (warns.length) lines.push(warns.join('；'));
                        const items = selected.map(k => {
                            const tag = addedSet.has(k) ? '新增' : (removedSet.has(k) ? '删除' : '修改');
                            const fs = fieldsFor(k);
                            const curS = curM.get(k);
                            const othS = othM.get(k);
                            const name = sceneTitle(othS || curS);
                            const a = curS && typeof curS === 'object' ? Number(curS.duration_sec || 0) : 0;
                            const b = othS && typeof othS === 'object' ? Number(othS.duration_sec || 0) : 0;
                            const n1 = curS && typeof curS === 'object' ? String(curS.narration || '') : '';
                            const n2 = othS && typeof othS === 'object' ? String(othS.narration || '') : '';
                            const s1 = curS && typeof curS === 'object' ? String(curS.subtitle || '') : '';
                            const s2 = othS && typeof othS === 'object' ? String(othS.subtitle || '') : '';
                            const v1 = curS && typeof curS === 'object' ? String(curS.visual_prompt_en || curS.visual_prompt || '') : '';
                            const v2 = othS && typeof othS === 'object' ? String(othS.visual_prompt_en || othS.visual_prompt || '') : '';
                            const clip = (x, n) => {
                                try {
                                    const t = String(x || '');
                                    return t.length > n ? (t.slice(0, n) + '…') : t;
                                } catch (_) {
                                    return '';
                                }
                            };
                            return {
                                idx: k,
                                tag,
                                name,
                                fields: fs,
                                duration_before: a,
                                duration_after: b,
                                narration_before: clip(n1, 140),
                                narration_after: clip(n2, 140),
                                subtitle_before: clip(s1, 140),
                                subtitle_after: clip(s2, 140),
                                visual_before: clip(v1, 180),
                                visual_after: clip(v2, 180),
                            };
                        });
                        return { lines, items };
                    };
                    const setAll = (val) => {
                        const cbs = panel.querySelectorAll('.ai_draft_sel_cb');
                        cbs.forEach(cb => { try { cb.checked = !!val; } catch (_) {} });
                        if (val) {
                            const fbs = panel.querySelectorAll('.ai_draft_field_cb');
                            fbs.forEach(cb => { try { cb.checked = true; } catch (_) {} });
                        }
                    };
                    const setRecommended = () => {
                        if (!plan) { this.toast('暂无推荐项'); return; }
                        const set = new Set(plan.scene_idxs || []);
                        const cbs = panel.querySelectorAll('.ai_draft_sel_cb');
                        cbs.forEach(cb => {
                            try {
                                const k = Number(cb.dataset.idx || 0);
                                cb.checked = set.size ? set.has(k) : true;
                            } catch (_) {
                            }
                        });
                        const fs = new Set((plan.fields || []).map(x => String(x || '').trim()).filter(Boolean));
                        const fbs = panel.querySelectorAll('.ai_draft_field_cb');
                        if (fs.size) {
                            fbs.forEach(cb => {
                                try {
                                    const f = String(cb.dataset.field || '');
                                    cb.checked = fs.has(f);
                                } catch (_) {
                                }
                            });
                        }
                        try {
                            if (plan.scene_fields && plan.scene_fields.size) {
                                const allFields = new Set();
                                fbs.forEach(cb => { try { allFields.add(String(cb.dataset.field || '')); } catch (_) {} });
                                const maps = plan.scene_fields;
                                maps.forEach((val, idx) => {
                                    const fs3 = new Set((val && Array.isArray(val.fields) ? val.fields : []).map(x => String(x || '').trim()).filter(Boolean));
                                    if (!fs3.size) return;
                                    allFields.forEach(f => {
                                        const els = panel.querySelectorAll(`.ai_draft_field_cb[data-idx="${idx}"][data-field="${f}"]`);
                                        els.forEach(cb => { try { cb.checked = fs3.has(f); } catch (_) {} });
                                    });
                                });
                            }
                        } catch (_) {
                        }
                    };
                    if (allBtn) allBtn.onclick = () => setAll(true);
                    if (noneBtn) noneBtn.onclick = () => setAll(false);
                    if (recBtn) recBtn.onclick = () => setRecommended();
                    if (applyRecBtn) applyRecBtn.onclick = () => {
                        setRecommended();
                        const s = buildSelectionSummary();
                        if (!s) return;
                        if (s.err) return this.toast(String(s.err));
                        showApplyConfirm('确认应用推荐项', { lines: s.lines || [], items: s.items || [] }, async () => {
                            try { if (applyBtn) applyBtn.click(); } catch (_) {}
                        });
                    };
                    if (applyBtn) applyBtn.onclick = () => {
                        const txt = existing.querySelector('#ai_draft_text');
                        if (!txt) return;
                        let cur = null;
                        try { cur = JSON.parse(String(txt.value || '')); } catch (_) { this.toast('当前脚本JSON格式不正确'); return; }
                        const curPs = cur && typeof cur === 'object' ? cur : {};
                        const otherPs = ctx.other && typeof ctx.other === 'object' ? ctx.other : {};
                        const curM = mapOf(curPs);
                        const othM = mapOf(otherPs);
                        const selected = [];
                        const cbs = panel.querySelectorAll('.ai_draft_sel_cb');
                        cbs.forEach(cb => {
                            try {
                                if (cb.checked) {
                                    const k = Number(cb.dataset.idx || 0);
                                    if (Number.isFinite(k) && k > 0) selected.push(k);
                                }
                            } catch (_) {
                            }
                        });
                        if (selected.length === 0) { this.toast('未选择分镜'); return; }
                        const changedSet = new Set(changed);
                        const addedSet = new Set(added);
                        const removedSet = new Set(removed);
                        const fieldsFor = (k) => {
                            const out = new Set();
                            const fbs = panel.querySelectorAll(`.ai_draft_field_cb[data-idx="${k}"]`);
                            fbs.forEach(cb => { try { if (cb.checked) out.add(String(cb.dataset.field || '')); } catch (_) {} });
                            return out;
                        };
                        selected.forEach(k => {
                            if (removedSet.has(k) && !othM.has(k)) {
                                curM.delete(k);
                                return;
                            }
                            if (addedSet.has(k) && othM.has(k)) {
                                curM.set(k, othM.get(k));
                                return;
                            }
                            if (changedSet.has(k) && othM.has(k)) {
                                const base = curM.has(k) ? curM.get(k) : {};
                                const from = othM.get(k);
                                const b = base && typeof base === 'object' ? { ...base } : {};
                                const f = from && typeof from === 'object' ? from : {};
                                const fs = fieldsFor(k);
                                if (fs.size === 0) {
                                    curM.set(k, f);
                                    return;
                                }
                                fs.forEach(name => {
                                    if (name === 'visual_prompt_en') {
                                        b.visual_prompt_en = f.visual_prompt_en != null ? f.visual_prompt_en : (f.visual_prompt != null ? f.visual_prompt : b.visual_prompt_en);
                                    } else {
                                        b[name] = f[name];
                                    }
                                });
                                curM.set(k, b);
                                return;
                            }
                            if (othM.has(k)) curM.set(k, othM.get(k));
                            else curM.delete(k);
                        });
                        const keys = Array.from(curM.keys()).sort((a, b) => a - b);
                        const outScenes = keys.map(k => {
                            const s = curM.get(k);
                            const o = s && typeof s === 'object' ? { ...s } : {};
                            if (o.idx == null) o.idx = k;
                            return o;
                        });
                        const out = { ...curPs, scenes: outScenes };
                        txt.value = JSON.stringify(out, null, 2);
                        this.toast('已应用勾选分镜（未保存）');
                    };
                    try {
                        if (plan) setRecommended();
                    } catch (_) {
                    }
                }
            }
            if (aEl) {
                const hasCtx = ctx && typeof ctx === 'object' && ctx.cur && ctx.other;
                aEl.style.display = hasCtx ? 'flex' : 'none';
                aEl.innerHTML = '';
                if (hasCtx) {
                    const mkBtn = (label, primary) => {
                        const d = document.createElement('div');
                        d.style.padding = '8px 12px';
                        d.style.borderRadius = '999px';
                        d.style.cursor = 'pointer';
                        d.style.userSelect = 'none';
                        d.style.fontWeight = primary ? '900' : '800';
                        d.style.fontSize = '12px';
                        d.style.color = primary ? 'white' : 'rgba(255,255,255,0.92)';
                        d.style.background = primary ? 'rgba(254,44,85,0.85)' : 'rgba(255,255,255,0.14)';
                        d.innerText = label;
                        return d;
                    };
                    const apply = (mode) => {
                        const txt = existing.querySelector('#ai_draft_text');
                        if (!txt) return;
                        let cur = null;
                        try {
                            cur = JSON.parse(String(txt.value || ''));
                        } catch (_) {
                            this.toast('当前脚本JSON格式不正确');
                            return;
                        }
                        const other = ctx.other;
                        const out = (cur && typeof cur === 'object') ? { ...cur } : {};
                        const oc = other && typeof other === 'object' ? other : {};
                        if (mode === 'title' || mode === 'all') {
                            const c = (out.cover && typeof out.cover === 'object') ? out.cover : {};
                            const c2 = (oc.cover && typeof oc.cover === 'object') ? oc.cover : {};
                            out.cover = { ...c, title_text: String(c2.title_text || '') || String(c.title_text || '') };
                        }
                        if (mode === 'music' || mode === 'all') {
                            const m0 = (out.music && typeof out.music === 'object') ? out.music : {};
                            const m2 = (oc.music && typeof oc.music === 'object') ? oc.music : {};
                            out.music = { ...m0, mood: String(m2.mood || '') || String(m0.mood || '') };
                        }
                        if (mode === 'scenes' || mode === 'all') {
                            out.scenes = mergeScenesByIdx(out, oc);
                        }
                        txt.value = JSON.stringify(out, null, 2);
                        this.toast('已应用到当前脚本（未保存）');
                    };
                    const bAll = mkBtn('应用全部', true);
                    const bScenes = mkBtn('应用分镜', false);
                    const bTitle = mkBtn('应用标题', false);
                    const bMusic = mkBtn('应用音乐', false);
                    bAll.onclick = () => apply('all');
                    bScenes.onclick = () => apply('scenes');
                    bTitle.onclick = () => apply('title');
                    bMusic.onclick = () => apply('music');
                    aEl.appendChild(bAll);
                    aEl.appendChild(bScenes);
                    aEl.appendChild(bTitle);
                    aEl.appendChild(bMusic);
                }
            }
            m.style.display = 'block';
        };
        const loadHistory = async () => {
            if (!histPanel) return;
            const list = existing.querySelector('#ai_draft_history_list');
            if (list) list.innerHTML = '<div style="color:rgba(255,255,255,0.55); font-size:12px;">加载中...</div>';
            try {
                const url = `/api/v1/ai/jobs/${encodeURIComponent(jid)}/draft/history?user_id=${uid}&limit=80`;
                const res = await this.apiRequest('GET', url, undefined, { cancel_key: `ai:draft:hist:${jid}`, dedupe_key: url });
                if (!res.ok) throw new Error('fetch_failed');
                const data = await res.json();
                const items = data && Array.isArray(data.items) ? data.items : [];
                if (!list) return;
                if (items.length === 0) {
                    list.innerHTML = '<div style="color:rgba(255,255,255,0.55); font-size:12px;">暂无历史</div>';
                    return;
                }
                list.innerHTML = '';
                items.forEach(it => {
                    const vid = Number(it.id || 0);
                    const srcRaw = String(it.source || '');
                    const src = fmtSource(srcRaw);
                    const ts = it.created_at ? new Date(it.created_at).toLocaleString() : '';
                    const row = document.createElement('div');
                    row.style.padding = '10px 10px';
                    row.style.borderRadius = '12px';
                    row.style.border = '1px solid rgba(255,255,255,0.08)';
                    row.style.background = 'rgba(255,255,255,0.04)';
                    row.style.display = 'flex';
                    row.style.flexDirection = 'column';
                    row.style.gap = '6px';
                    row.innerHTML = `
                        <div style="display:flex; justify-content:space-between; gap:10px; align-items:center;">
                            <div style="font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; font-size:12px; color:rgba(255,255,255,0.85);">#${vid}</div>
                            <div style="font-size:11px; color:rgba(255,255,255,0.55);">${escHtml(ts)}</div>
                        </div>
                        <div style="font-size:12px; color:rgba(255,255,255,0.72);">${escHtml(src || 'unknown')}</div>
                        <div style="display:flex; gap:8px;">
                            <div class="ai_draft_hist_load" style="padding:6px 10px; border-radius:999px; background:rgba(255,255,255,0.12); cursor:pointer; user-select:none; font-weight:800; font-size:12px;">载入</div>
                            <div class="ai_draft_hist_diff" style="padding:6px 10px; border-radius:999px; background:rgba(255,255,255,0.12); cursor:pointer; user-select:none; font-weight:800; font-size:12px;">对比</div>
                            <div class="ai_draft_hist_rollback" style="padding:6px 10px; border-radius:999px; background:rgba(254,44,85,0.85); cursor:pointer; user-select:none; color:white; font-weight:900; font-size:12px;">回滚</div>
                        </div>
                    `;
                    const loadBtn = row.querySelector('.ai_draft_hist_load');
                    const diffBtn = row.querySelector('.ai_draft_hist_diff');
                    const rbBtn = row.querySelector('.ai_draft_hist_rollback');
                    if (loadBtn) loadBtn.onclick = async () => {
                        try {
                            const url2 = `/api/v1/ai/jobs/${encodeURIComponent(jid)}/draft/history/${vid}?user_id=${uid}`;
                            const res2 = await this.apiRequest('GET', url2, undefined, { cancel_key: `ai:draft:hist:item:${jid}:${vid}`, dedupe_key: url2 });
                            if (!res2.ok) return;
                            const d2 = await res2.json();
                            const txt = existing.querySelector('#ai_draft_text');
                            if (txt) txt.value = JSON.stringify(d2 && d2.draft_json ? d2.draft_json : {}, null, 2);
                            this.toast('已载入该版本');
                        } catch (_) {
                        }
                    };
                    if (diffBtn) diffBtn.onclick = async () => {
                        let cur = null;
                        try {
                            cur = doParse();
                        } catch (_) {
                            this.toast('当前脚本JSON格式不正确');
                            return;
                        }
                        try {
                            const url2 = `/api/v1/ai/jobs/${encodeURIComponent(jid)}/draft/history/${vid}?user_id=${uid}`;
                            const res2 = await this.apiRequest('GET', url2, undefined, { cancel_key: `ai:draft:hist:diff:${jid}:${vid}`, dedupe_key: url2 });
                            if (!res2.ok) return;
                            const d2 = await res2.json();
                            const other = d2 && d2.draft_json ? d2.draft_json : {};
                            const a = metaOf(cur);
                            const b = metaOf(other);
                            const lines = [];
                            if (a.title !== b.title) lines.push(`标题：${a.title || '（空）'} → ${b.title || '（空）'}`);
                            if (a.mood !== b.mood) lines.push(`音乐情绪：${a.mood || '（空）'} → ${b.mood || '（空）'}`);
                            if (a.scenes !== b.scenes) lines.push(`分镜数量：${a.scenes} → ${b.scenes}`);
                            if (a.total_sec !== b.total_sec) lines.push(`预计时长：${a.total_sec}s → ${b.total_sec}s`);
                            if (a.first !== b.first) lines.push(`开场：${a.first || '（空）'} → ${b.first || '（空）'}`);
                            if (a.last !== b.last) lines.push(`结尾：${a.last || '（空）'} → ${b.last || '（空）'}`);
                            const d = diffScript(cur, other);
                            const all = []
                                .concat(lines)
                                .concat(d.head)
                                .concat(d.detail.length ? ['—'] : [])
                                .concat(d.detail);
                            showDraftDiff(`对比当前 vs #${vid}`, all.filter(x => String(x || '').trim() !== ''), { cur, other, diff: d });
                        } catch (_) {
                        }
                    };
                    if (rbBtn) rbBtn.onclick = async () => {
                        try {
                            const url2 = `/api/v1/ai/jobs/${encodeURIComponent(jid)}/draft/history/${vid}?user_id=${uid}`;
                            const res2 = await this.apiRequest('GET', url2, undefined, { cancel_key: `ai:draft:hist:item:${jid}:${vid}`, dedupe_key: url2 });
                            if (!res2.ok) return;
                            const d2 = await res2.json();
                            const draft = d2 && d2.draft_json ? d2.draft_json : {};
                            const url3 = `/api/v1/ai/jobs/${encodeURIComponent(jid)}/draft`;
                            const res3 = await this.apiRequest('POST', url3, { user_id: uid, draft_json: draft, source: `rollback:${vid}` }, { cancel_key: `ai:draft:rollback:${jid}:${vid}` });
                            if (!res3.ok) return;
                            const txt = existing.querySelector('#ai_draft_text');
                            if (txt) txt.value = JSON.stringify(draft, null, 2);
                            this.toast('已回滚并保存');
                            await loadHistory();
                        } catch (_) {
                        }
                    };
                    list.appendChild(row);
                });
            } catch (_) {
                const list = existing.querySelector('#ai_draft_history_list');
                if (list) list.innerHTML = '<div style="color:rgba(255,255,255,0.55); font-size:12px;">加载失败</div>';
            }
        };
        if (histBtn) histBtn.onclick = async () => {
            if (!histPanel) return;
            histPanel.style.display = 'flex';
            await loadHistory();
        };
        if (histClose) histClose.onclick = () => { if (histPanel) histPanel.style.display = 'none'; };
        try {
            existing._openHistory = async () => {
                if (!histPanel) return;
                histPanel.style.display = 'flex';
                await loadHistory();
            };
        } catch (_) {
        }
        try {
            existing._compareVersion = async (vid) => {
                const v = Number(vid || 0);
                if (!Number.isFinite(v) || v <= 0) return;
                const txt = existing.querySelector('#ai_draft_text');
                if (!txt) return;
                let cur = null;
                try {
                    cur = JSON.parse(String(txt.value || ''));
                } catch (_) {
                    this.toast('当前脚本JSON格式不正确');
                    return;
                }
                try {
                    const url2 = `/api/v1/ai/jobs/${encodeURIComponent(jid)}/draft/history/${v}?user_id=${uid}`;
                    const res2 = await this.apiRequest('GET', url2, undefined, { cancel_key: `ai:draft:hist:diff:${jid}:${v}`, dedupe_key: url2 });
                    if (!res2.ok) return;
                    const d2 = await res2.json();
                    const other = d2 && d2.draft_json ? d2.draft_json : {};
                    const a = metaOf(cur);
                    const b = metaOf(other);
                    const lines = [];
                    if (a.title !== b.title) lines.push(`标题：${a.title || '（空）'} → ${b.title || '（空）'}`);
                    if (a.mood !== b.mood) lines.push(`音乐情绪：${a.mood || '（空）'} → ${b.mood || '（空）'}`);
                    if (a.scenes !== b.scenes) lines.push(`分镜数量：${a.scenes} → ${b.scenes}`);
                    if (a.total_sec !== b.total_sec) lines.push(`预计时长：${a.total_sec}s → ${b.total_sec}s`);
                    if (a.first !== b.first) lines.push(`开场：${a.first || '（空）'} → ${b.first || '（空）'}`);
                    if (a.last !== b.last) lines.push(`结尾：${a.last || '（空）'} → ${b.last || '（空）'}`);
                    const d = diffScript(cur, other);
                    const all = []
                        .concat(lines)
                        .concat(d.head)
                        .concat(d.detail.length ? ['—'] : [])
                        .concat(d.detail);
                    showDraftDiff(`对比当前 vs #${v}`, all.filter(x => String(x || '').trim() !== ''), { cur, other, diff: d });
                } catch (_) {
                }
            };
        } catch (_) {
        }
    },

    openAIChatModal: async function(jobId) {
        const jid = String(jobId || '');
        const uid = this.state.user ? Number(this.state.user.id || 0) : 0;
        if (!jid || !uid) return;
        let modal = document.getElementById('ai_chat_modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'ai_chat_modal';
            modal.style.position = 'fixed';
            modal.style.inset = '0';
            modal.style.background = 'rgba(0,0,0,0.55)';
            modal.style.zIndex = '9999';
            modal.style.display = 'none';
            modal.innerHTML = `
                <div style="position:absolute; left:50%; top:50%; transform:translate(-50%,-50%); width:min(980px, calc(100vw - 32px)); height:min(720px, calc(100vh - 32px)); background:#111; border:1px solid rgba(255,255,255,0.10); border-radius:14px; overflow:hidden; display:flex; flex-direction:column;">
                    <div style="padding:12px 14px; display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid rgba(255,255,255,0.08);">
                        <div style="font-size:13px; font-weight:900; color:rgba(255,255,255,0.92);">AI沟通 / 二次修改</div>
                        <div style="display:flex; gap:8px; align-items:center;">
                            <div id="ai_chat_suggest" style="padding:6px 10px; border-radius:999px; background:rgba(255,255,255,0.16); cursor:pointer; user-select:none; color:rgba(255,255,255,0.92); font-weight:900; font-size:12px;">AI建议</div>
                            <div id="ai_chat_submit" style="padding:6px 10px; border-radius:999px; background:rgba(254,44,85,0.85); cursor:pointer; user-select:none; color:white; font-weight:900; font-size:12px;">提交修改</div>
                            <div id="ai_chat_close" style="padding:6px 10px; border-radius:999px; background:rgba(255,255,255,0.10); cursor:pointer; user-select:none; color:rgba(255,255,255,0.85); font-weight:800; font-size:12px;">关闭</div>
                        </div>
                    </div>
                    <div style="flex:1; display:flex; min-height:0;">
                        <div style="flex:1; padding:12px; overflow:auto; display:flex; flex-direction:column; gap:10px;" id="ai_chat_list"></div>
                    </div>
                    <div style="padding:12px; border-top:1px solid rgba(255,255,255,0.08); display:flex; gap:10px; align-items:flex-end;">
                        <textarea id="ai_chat_input" placeholder="对AI说：想改哪里？例如：更短、更幽默、换成科普风、加强转场、修改标题等" style="flex:1; min-height:44px; max-height:140px; padding:10px 10px; border:1px solid rgba(255,255,255,0.12); border-radius:12px; background:#0b0b0b; color:rgba(255,255,255,0.88); outline:none; resize:vertical;"></textarea>
                        <div id="ai_chat_send" style="padding:10px 14px; border-radius:12px; background:rgba(255,255,255,0.16); cursor:pointer; user-select:none; color:rgba(255,255,255,0.92); font-weight:900; font-size:12px;">发送</div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
            modal.addEventListener('click', (e) => {
                const t = e && e.target ? e.target : null;
                if (t === modal) modal.style.display = 'none';
            });
            const closeBtn = modal.querySelector('#ai_chat_close');
            if (closeBtn) closeBtn.addEventListener('click', () => { modal.style.display = 'none'; });
        }
        modal.style.display = 'block';
        modal.dataset.jobId = jid;
        await this._loadAIChat(jid);
        const sendBtn = modal.querySelector('#ai_chat_send');
        if (sendBtn) sendBtn.onclick = async () => { await this.sendAIChatMessage(jid); };
        const suggestBtn = modal.querySelector('#ai_chat_suggest');
        if (suggestBtn) suggestBtn.onclick = async () => { await this.requestAIChatSuggestion(jid); };
        const submitBtn = modal.querySelector('#ai_chat_submit');
        if (submitBtn) submitBtn.onclick = async () => { await this.submitAIChatRevision(jid); };
    },

    _loadAIChat: async function(jobId) {
        const jid = String(jobId || '');
        const uid = this.state.user ? Number(this.state.user.id || 0) : 0;
        const modal = document.getElementById('ai_chat_modal');
        const list = modal ? modal.querySelector('#ai_chat_list') : null;
        if (!jid || !uid || !list) return;
        list.innerHTML = '<div style="color:rgba(255,255,255,0.55); font-size:12px;">加载中...</div>';
        try {
            let pid = 0;
            try {
                const url0 = `/api/v1/ai/jobs/${encodeURIComponent(jid)}?user_id=${uid}`;
                const res0 = await this.apiRequest('GET', url0, undefined, { cancel_key: `ai:job:${jid}`, dedupe_key: url0, cache_ttl_ms: 1200 });
                if (res0 && res0.ok) {
                    const data0 = await res0.json().catch(() => null);
                    pid = data0 && data0.post_id ? Number(data0.post_id || 0) : 0;
                }
            } catch (_) {
                pid = 0;
            }
            const url = pid
                ? `/api/v1/ai/posts/${encodeURIComponent(String(pid))}/chat?user_id=${uid}&limit=200`
                : `/api/v1/ai/jobs/${encodeURIComponent(jid)}/chat?user_id=${uid}&limit=120`;
            const res = await this.apiRequest('GET', url, undefined, { cancel_key: `ai:chat:${jid}`, dedupe_key: url });
            if (!res.ok) throw new Error('fetch_failed');
            const data = await res.json();
            const msgs = data && Array.isArray(data.messages) ? data.messages : [];
            if (msgs.length === 0) {
                list.innerHTML = `
                    <div style="color:rgba(255,255,255,0.70); font-size:12px; line-height:1.6;">
                        - 这里可以记录你的修改想法（不会立刻重做）<br/>
                        - 点“提交修改”才会创建新版本并重新生成<br/>
                        - 也可以去“脚本”里直接编辑分镜再重做
                    </div>
                `;
                return;
            }
            list.innerHTML = '';
            msgs.forEach(m => {
                const role = String(m.role || '');
                const box = document.createElement('div');
                box.style.alignSelf = role === 'user' ? 'flex-end' : 'flex-start';
                box.style.maxWidth = '82%';
                box.style.padding = '10px 12px';
                box.style.borderRadius = '12px';
                box.style.background = role === 'user' ? 'rgba(254,44,85,0.18)' : 'rgba(255,255,255,0.08)';
                box.style.color = 'rgba(255,255,255,0.90)';
                box.style.fontSize = '12px';
                box.style.lineHeight = '1.6';
                if (role === 'assistant') {
                    box.style.display = 'flex';
                    box.style.flexDirection = 'column';
                    box.style.gap = '8px';
                    const t = document.createElement('div');
                    t.innerText = String(m.content || '');
                    box.appendChild(t);
                    const actions = document.createElement('div');
                    actions.style.display = 'flex';
                    actions.style.gap = '8px';
                    actions.style.flexWrap = 'wrap';
                    const mk = (label) => {
                        const b = document.createElement('div');
                        b.style.padding = '6px 10px';
                        b.style.borderRadius = '999px';
                        b.style.background = 'rgba(255,255,255,0.12)';
                        b.style.cursor = 'pointer';
                        b.style.userSelect = 'none';
                        b.style.fontWeight = '800';
                        b.style.fontSize = '12px';
                        b.style.color = 'rgba(255,255,255,0.92)';
                        b.innerText = label;
                        return b;
                    };
                    const openDraft = mk('打开脚本');
                    openDraft.onclick = async () => {
                        try { await this.openAIDraftEditor(jid); } catch (_) {}
                    };
                    const openHistory = mk('打开历史');
                    openHistory.onclick = async () => {
                        try { await this.openAIDraftEditor(jid); } catch (_) {}
                        try {
                            const ed = document.getElementById('ai_draft_editor');
                            if (ed && typeof ed._openHistory === 'function') await ed._openHistory();
                        } catch (_) {
                        }
                    };
                    const compare = mk('对比建议');
                    compare.onclick = async () => {
                        try { await this.openAIDraftEditorCompareLatest(jid); } catch (_) {}
                    };
                    actions.appendChild(openDraft);
                    actions.appendChild(openHistory);
                    actions.appendChild(compare);
                    box.appendChild(actions);
                } else {
                    box.innerText = String(m.content || '');
                }
                list.appendChild(box);
            });
            try { list.scrollTop = list.scrollHeight; } catch (_) {}
        } catch (_) {
            list.innerHTML = '<div style="color:rgba(255,255,255,0.55); font-size:12px;">加载失败</div>';
        }
    },

    sendAIChatMessage: async function(jobId) {
        const jid = String(jobId || '');
        const uid = this.state.user ? Number(this.state.user.id || 0) : 0;
        const modal = document.getElementById('ai_chat_modal');
        const input = modal ? modal.querySelector('#ai_chat_input') : null;
        if (!jid || !uid || !input) return;
        const content = String(input.value || '').trim();
        if (!content) return this.toast('请输入内容');
        const sendBtn = modal ? modal.querySelector('#ai_chat_send') : null;
        const subBtn = modal ? modal.querySelector('#ai_chat_submit') : null;
        const sugBtn = modal ? modal.querySelector('#ai_chat_suggest') : null;
        try {
            if (sendBtn) { sendBtn.style.opacity = '0.6'; sendBtn.style.pointerEvents = 'none'; sendBtn.innerText = '发送中...'; }
            if (subBtn) { subBtn.style.opacity = '0.6'; subBtn.style.pointerEvents = 'none'; }
            if (sugBtn) { sugBtn.style.opacity = '0.6'; sugBtn.style.pointerEvents = 'none'; }
        } catch (_) {
        }
        try {
            const url = `/api/v1/ai/jobs/${encodeURIComponent(jid)}/chat`;
            const res = await this.apiRequest('POST', url, { user_id: uid, content }, { cancel_key: `ai:chat:send:${jid}` });
            if (!res.ok) {
                this.toast('发送失败');
                return;
            }
            input.value = '';
            await this._loadAIChat(jid);
        } catch (_) {
            this.toast('发送失败');
        } finally {
            try {
                if (sendBtn) { sendBtn.style.opacity = ''; sendBtn.style.pointerEvents = ''; sendBtn.innerText = '发送'; }
                if (subBtn) { subBtn.style.opacity = ''; subBtn.style.pointerEvents = ''; }
                if (sugBtn) { sugBtn.style.opacity = ''; sugBtn.style.pointerEvents = ''; }
            } catch (_) {
            }
        }
    },

    requestAIChatSuggestion: async function(jobId) {
        const jid = String(jobId || '');
        const uid = this.state.user ? Number(this.state.user.id || 0) : 0;
        if (!jid || !uid) return;
        const modal = document.getElementById('ai_chat_modal');
        const sendBtn = modal ? modal.querySelector('#ai_chat_send') : null;
        const subBtn = modal ? modal.querySelector('#ai_chat_submit') : null;
        const sugBtn = modal ? modal.querySelector('#ai_chat_suggest') : null;
        try {
            const url = `/api/v1/ai/jobs/${encodeURIComponent(jid)}/chat/ai_suggest`;
            try {
                if (sugBtn) { sugBtn.style.opacity = '0.6'; sugBtn.style.pointerEvents = 'none'; sugBtn.innerText = '生成中...'; }
                if (sendBtn) { sendBtn.style.opacity = '0.6'; sendBtn.style.pointerEvents = 'none'; }
                if (subBtn) { subBtn.style.opacity = '0.6'; subBtn.style.pointerEvents = 'none'; }
            } catch (_) {
            }
            const res = await this.apiRequest('POST', url, { user_id: uid }, { cancel_key: `ai:chat:suggest:${jid}` });
            if (!res.ok) {
                this.toast('请求失败');
                return;
            }
            this.toast('AI正在生成建议…');
            let n = 0;
            const tick = async () => {
                n += 1;
                await this._loadAIChat(jid);
                if (n < 10) setTimeout(tick, 1000);
            };
            setTimeout(tick, 800);
        } catch (_) {
            this.toast('请求失败');
        } finally {
            try {
                if (sugBtn) { sugBtn.style.opacity = ''; sugBtn.style.pointerEvents = ''; sugBtn.innerText = 'AI建议'; }
                if (sendBtn) { sendBtn.style.opacity = ''; sendBtn.style.pointerEvents = ''; }
                if (subBtn) { subBtn.style.opacity = ''; subBtn.style.pointerEvents = ''; }
            } catch (_) {
            }
        }
    },

    openAIDraftEditorCompareLatest: async function(jobId) {
        const jid = String(jobId || '');
        const uid = this.state.user ? Number(this.state.user.id || 0) : 0;
        if (!jid || !uid) return;
        try {
            await this.openAIDraftEditor(jid);
        } catch (_) {
            return;
        }
        let items = [];
        try {
            const url = `/api/v1/ai/jobs/${encodeURIComponent(jid)}/draft/history?user_id=${uid}&limit=80`;
            const res = await this.apiRequest('GET', url, undefined, { cancel_key: `ai:draft:hist:${jid}`, dedupe_key: url });
            if (res && res.ok) {
                const data = await res.json().catch(() => null);
                items = data && Array.isArray(data.items) ? data.items : [];
            }
        } catch (_) {
            items = [];
        }
        const pick = () => {
            for (const it of items) {
                try {
                    const src = String((it && it.source) || '');
                    if (src.startsWith('chat_ai') || src === 'chat_ai_done') return Number(it.id || 0);
                } catch (_) {
                }
            }
            try {
                return Number((items[0] && items[0].id) || 0);
            } catch (_) {
                return 0;
            }
        };
        const vid = pick();
        const ed = document.getElementById('ai_draft_editor');
        if (ed && typeof ed._compareVersion === 'function' && vid > 0) {
            try {
                await ed._compareVersion(vid);
                return;
            } catch (_) {
            }
        }
        this.toast('暂无可对比版本');
    },

    submitAIChatRevision: async function(jobId) {
        const jid = String(jobId || '');
        const uid = this.state.user ? Number(this.state.user.id || 0) : 0;
        if (!jid || !uid) return;
        const modal = document.getElementById('ai_chat_modal');
        const sendBtn = modal ? modal.querySelector('#ai_chat_send') : null;
        const subBtn = modal ? modal.querySelector('#ai_chat_submit') : null;
        const sugBtn = modal ? modal.querySelector('#ai_chat_suggest') : null;
        try {
            const url = `/api/v1/ai/jobs/${encodeURIComponent(jid)}/revise_from_chat`;
            try {
                if (subBtn) { subBtn.style.opacity = '0.6'; subBtn.style.pointerEvents = 'none'; subBtn.innerText = '提交中...'; }
                if (sendBtn) { sendBtn.style.opacity = '0.6'; sendBtn.style.pointerEvents = 'none'; }
                if (sugBtn) { sugBtn.style.opacity = '0.6'; sugBtn.style.pointerEvents = 'none'; }
            } catch (_) {
            }
            const res = await this.apiRequest('POST', url, { user_id: uid }, { cancel_key: `ai:chat:revise:${jid}` });
            if (!res.ok) {
                this.toast('提交失败');
                return;
            }
            const data = await res.json().catch(() => null);
            if (modal) modal.style.display = 'none';
            this.toast('已提交改稿，将生成新版本');
            try {
                if (data && data.post_id) {
                    if (typeof this.loadProfile === 'function') this.loadProfile(uid);
                }
            } catch (_) {
            }
        } catch (_) {
            this.toast('提交失败');
        } finally {
            try {
                if (subBtn) { subBtn.style.opacity = ''; subBtn.style.pointerEvents = ''; subBtn.innerText = '提交修改'; }
                if (sendBtn) { sendBtn.style.opacity = ''; sendBtn.style.pointerEvents = ''; }
                if (sugBtn) { sugBtn.style.opacity = ''; sugBtn.style.pointerEvents = ''; }
            } catch (_) {
            }
        }
    },

    pollAIJobIntoBadge: function(jobId, badgeEl) {
        const jid = String(jobId || '');
        if (!jid || !badgeEl) return;
        try {
            if (window.EventSource && window.__aiseekJobStreamEnabled === true) {
                this.streamAIJobIntoBadge(jid, badgeEl);
                return;
            }
        } catch (_) {
        }
        const key = `ai:job:poll:${jid}`;
        const poll = async () => {
            try {
                const uid = this.state.user ? Number(this.state.user.id || 0) : 0;
                if (!uid) return;
                const url = `/api/v1/ai/jobs/${encodeURIComponent(jid)}?user_id=${uid}`;
                const res = await this.apiRequest('GET', url, undefined, { cancel_key: key, dedupe_key: url });
                if (!res.ok) return;
                const job = await res.json();
                const st = String(job.status || '');
                const pctEl = badgeEl.querySelector('.ai-job-pct');
                const msgEl = badgeEl.querySelector('.ai-job-msg');
                const p = Number(job.progress || 0);
                const stageMsg = String(job.stage_message || '') || String(job.stage || '');
                if (pctEl) pctEl.innerText = (Number.isFinite(p) ? `${Math.max(0, Math.min(100, p))}%` : '');
                if (msgEl) msgEl.innerText = stageMsg || (st === 'failed' ? String(job.error || '') : '');
                if (st === 'done' || st === 'failed' || st === 'cancelled') {
                    try { if (badgeEl._pollTimer) clearInterval(badgeEl._pollTimer); } catch (_) {}
                }
            } catch (_) {
            }
        };
        poll();
        try { if (badgeEl._pollTimer) clearInterval(badgeEl._pollTimer); } catch (_) {}
        badgeEl._pollTimer = setInterval(poll, 2000);
    },

    streamAIJobIntoBadge: function(jobId, badgeEl) {
        const jid = String(jobId || '');
        if (!jid || !badgeEl) return;
        const uid = this.state.user ? Number(this.state.user.id || 0) : 0;
        if (!uid) return;
        try { if (badgeEl._pollTimer) clearInterval(badgeEl._pollTimer); } catch (_) {}
        try { if (badgeEl._evtSource) badgeEl._evtSource.close(); } catch (_) {}
        const url = `/api/v1/ai/jobs/${encodeURIComponent(jid)}/events/stream?user_id=${uid}`;
        let last = 0;
        const es = new EventSource(url);
        badgeEl._evtSource = es;
        const apply = (job) => {
            if (!job || typeof job !== 'object') return;
            const titleEl = badgeEl.querySelector('.ai-job-title');
            const pctEl = badgeEl.querySelector('.ai-job-pct');
            const msgEl = badgeEl.querySelector('.ai-job-msg');
            const actionsEl = badgeEl.querySelector('.ai-job-actions');
            const p = Number(job.progress || 0);
            const stageMsg = String(job.stage_message || '') || String(job.stage || '');
            const st2 = String(job.status || '');
            if (titleEl) titleEl.innerText = st2 === 'failed' ? '生成失败' : (st2 === 'queued' ? '排队中' : (st2 === 'processing' ? '生成中' : (st2 === 'done' ? '已完成' : '')));
            if (pctEl) pctEl.innerText = (Number.isFinite(p) ? `${Math.max(0, Math.min(100, p))}%` : '');
            if (msgEl) msgEl.innerText = stageMsg || (st2 === 'failed' ? String(job.error || '') : '');
        };
        es.addEventListener('ev', (e) => {
            try {
                const data = JSON.parse(String(e.data || '{}'));
                const id = Number(data.id || 0);
                if (id > last) last = id;
                if (String(data.kind || '') === 'progress') {
                    const p = data.payload || {};
                    apply({
                        status: p.status,
                        progress: p.progress,
                        stage: p.stage,
                        stage_message: p.stage_message
                    });
                    if (String(p.status || '') === 'done' || String(p.status || '') === 'failed' || String(p.status || '') === 'cancelled') {
                        try { es.close(); } catch (_) {}
                    }
                }
            } catch (_) {
            }
        });
        es.onerror = () => {
            try { es.close(); } catch (_) {}
            try { badgeEl._evtSource = null; } catch (_) {}
            this.pollAIJobIntoBadge(jid, badgeEl);
        };
        try {
            const url2 = `/api/v1/ai/jobs/${encodeURIComponent(jid)}?user_id=${uid}`;
            this.apiRequest('GET', url2, undefined, { cancel_key: `ai:job:init:${jid}`, dedupe_key: url2 }).then(async (r) => {
                if (!r || !r.ok) return;
                const job = await r.json();
                apply(job || {});
            }).catch(() => {});
        } catch (_) {
        }
    },

    cancelAIJob: async function(jobId) {
        const jid = String(jobId || '');
        if (!jid) return;
        const uid = this.state.user ? Number(this.state.user.id || 0) : 0;
        if (!uid) return this.openModal('authModal');
        try {
            const url = `/api/v1/ai/jobs/${encodeURIComponent(jid)}/cancel`;
            const res = await this.apiRequest('POST', url, { user_id: uid }, { cancel_key: `ai:job:cancel:${jid}` });
            if (!res.ok) return;
            try {
                document.querySelectorAll(`.ai-job-badge[data-job-id="${jid}"]`).forEach(el => {
                    const pctEl = el.querySelector('.ai-job-pct');
                    if (pctEl) pctEl.innerText = '';
                    const msgEl = el.querySelector('.ai-job-msg');
                    if (msgEl) msgEl.innerText = '用户已取消';
                });
            } catch (_) {
            }
        } catch (_) {
        }
    },

    viewUserProfile: function(userId) {
        location.hash = `#/u/${userId}`;
    },

    profilePreviewPlay: function(postId, cardEl) {
        const el = cardEl && cardEl.querySelector ? cardEl : null;
        const v = el ? el.querySelector('video') : null;
        if (!v) return;
        try { if (typeof this.pauseAllVideosExcept === 'function') this.pauseAllVideosExcept(v); } catch (_) {}
        try {
            const post = (typeof this.findPostById === 'function') ? this.findPostById(postId) : null;
            if (post && window.app && typeof window.app.applyPreferredVideoSource === 'function') {
                const r = window.app.applyPreferredVideoSource(v, post, { autoPlay: true });
                if (r && typeof r.catch === 'function') r.catch(() => {});
                return;
            }
        } catch (_) {
        }
        try {
            const src = (v.dataset && (v.dataset.hls || v.dataset.mp4)) ? (v.dataset.hls || v.dataset.mp4) : (v.currentSrc || '');
            if (src && v.src !== src) v.src = src;
            const p = v.play();
            if (p && typeof p.catch === 'function') p.catch(() => {});
        } catch (_) {
        }
    },

    profilePreviewStop: function(postId, cardEl) {
        const el = cardEl && cardEl.querySelector ? cardEl : null;
        const v = el ? el.querySelector('video') : null;
        if (!v) return;
        try { v.pause(); } catch (_) {}
    },

    fillEditForm: function() {
        const u = this.state.user;
        document.getElementById('edit_nickname').value = u.nickname || '';
        document.getElementById('edit_bio').value = u.bio || '';
        document.getElementById('edit_gender').value = u.gender || 'other';
        document.getElementById('edit_birthday').value = u.birthday || '';
        document.getElementById('edit_location').value = u.location || '';
        document.getElementById('edit_avatar_img').src = u.avatar || '/static/img/default_avatar.svg';
        const bg = u.background || '/static/img/default_bg.svg';
        const bgEl = document.getElementById('edit_bg_img');
        if (bgEl) bgEl.src = bg;
        this.bindProfileEditor();
        this.updateNicknameCounter();
    },

    bindProfileEditor: function() {
        if (this._profileEditorBound) return;
        const nick = document.getElementById('edit_nickname');
        if (nick) {
            nick.addEventListener('input', () => this.updateNicknameCounter());
        }
        this._profileEditorBound = true;
    },

    updateNicknameCounter: function() {
        const nick = document.getElementById('edit_nickname');
        const counter = document.getElementById('edit_nickname_counter');
        if (!nick || !counter) return;
        const v = String(nick.value || '');
        const len = [...v].length;
        counter.innerText = `${Math.min(len, 20)}/20`;
        counter.style.color = len > 20 ? 'var(--primary-color)' : 'var(--text-secondary)';
    },

    uploadAvatar: async function(input) {
        if (!input.files[0]) return;
        const formData = new FormData();
        formData.append('file', input.files[0]);
        const res = await this.apiRequest('POST', '/api/v1/upload/avatar', formData, { cancel_key: 'upload:avatar' });
        const data = await res.json();
        if (data.url) {
            document.getElementById('edit_avatar_img').src = data.url;
        }
    },

    uploadBackground: async function(input) {
        if (!input.files[0]) return;
        const formData = new FormData();
        formData.append('file', input.files[0]);
        const res = await this.apiRequest('POST', '/api/v1/upload/background', formData, { cancel_key: 'upload:bg' });
        const data = await res.json();
        if (data.url) {
            const bgEl = document.getElementById('edit_bg_img');
            if (bgEl) bgEl.src = data.url;
        }
    },

    saveProfile: async function() {
        const nickname = String(document.getElementById('edit_nickname').value || '');
        if ([...nickname].length > 20) {
            this.toast('昵称最多20个字符');
            this.updateNicknameCounter();
            return;
        }
        const data = {
            user_id: this.state.user.id,
            nickname,
            bio: document.getElementById('edit_bio').value,
            gender: document.getElementById('edit_gender').value,
            birthday: document.getElementById('edit_birthday').value,
            location: document.getElementById('edit_location').value,
            avatar: document.getElementById('edit_avatar_img').src,
            background: (document.getElementById('edit_bg_img') && document.getElementById('edit_bg_img').src) ? document.getElementById('edit_bg_img').src : null
        };

        try {
            const res = await this.apiRequest('POST', '/api/v1/users/update-profile', data, { cancel_key: `profile:update:${this.state.user.id}` });
            const ret = await res.json().catch(() => ({}));
            if (!res.ok) {
                const msg = ret && (ret.detail || ret.message) ? (ret.detail || ret.message) : '保存失败';
                this.toast(msg);
                return;
            }
            if (ret && ret.status === 'ok' && ret.user) {
                this.state.user = ret.user;
                this.closeModal('editProfileModal');
                this.loadProfile(this.state.user.id);
                this.updateAuthUI();
                this.toast('已保存');
                return;
            }
            this.toast('保存失败');
        } catch(e) {
            this.toast('保存失败');
        }
    },

    changePassword: async function() {
        const oldP = document.getElementById('pwd_old').value;
        const newP = document.getElementById('pwd_new').value;
        if (!oldP || !newP) return alert('请填写完整');
        
        try {
            const res = await this.apiRequest('POST', '/api/v1/users/change-password', { user_id: this.state.user.id, old_password: oldP, new_password: newP }, { cancel_key: `pwd:change:${this.state.user.id}` });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) return alert((data && (data.detail || data.message)) || '修改失败');
            alert(data.message || '已修改');
            this.closeModal('passwordModal');
        } catch(e) { alert('修改失败'); }
    },

    settingsSelect: function(key) {
        if (!this.state.user) return this.openModal('authModal');
        const k = key || 'password';
        this.state.currentSettingsKey = k;
        ['password','account','privacy','notify','home','language','shortcuts','center','theme','background'].forEach(x => {
            const el = document.getElementById(`settings_nav_${x}`);
            if (el) el.classList.toggle('active', x === k);
        });

        const panel = document.getElementById('settings_panel');
        if (!panel) return;

        if (k === 'shortcuts') {
            const lang = this.state.lang === 'en' ? 'en' : 'zh';
            const title = lang === 'en' ? 'Shortcuts' : '快捷键';
            const leftTitle = lang === 'en' ? 'Interaction' : '互动类';
            const rightTitle = lang === 'en' ? 'Playback' : '播放类';
            const interaction = lang === 'en'
                ? [
                    ['Like / Unlike', 'Z'],
                    ['Favorite / Unfavorite', 'C'],
                    ['Follow / Unfollow', 'G'],
                    ['Open Creator Profile', 'F'],
                    ['Comments', 'X'],
                    ['Copy Share Code', 'V'],
                    ['Recommend to Friend', 'P'],
                    ['Not Interested', 'R'],
                ]
                : [
                    ['赞/取消赞', 'Z'],
                    ['收藏/取消收藏', 'C'],
                    ['关注/取消关注', 'G'],
                    ['进入作者主页', 'F'],
                    ['评论', 'X'],
                    ['复制分享口令', 'V'],
                    ['推荐给朋友', 'P'],
                    ['不感兴趣', 'R'],
                ];
            const playback = lang === 'en'
                ? [
                    ['Danmaku On/Off', 'B'],
                    ['Clear Screen', 'J'],
                    ['Autoplay Next', 'K'],
                    ['In-page Fullscreen', 'Y'],
                    ['Fullscreen', 'H'],
                    ['Watch Later', 'L'],
                    ['Picture-in-Picture', 'U'],
                    ['Volume', 'Shift +/-'],
                    ['Page Up/Down', '↑ ↓'],
                    ['Seek', '← →'],
                    ['Play/Pause', 'Space'],
                ]
                : [
                    ['开始/关闭弹幕', 'B'],
                    ['清屏', 'J'],
                    ['自动连播', 'K'],
                    ['网页内全屏', 'Y'],
                    ['全屏', 'H'],
                    ['稍后再看', 'L'],
                    ['小窗模式', 'U'],
                    ['音量调整', 'Shift +/-'],
                    ['上下翻页', '↑ ↓'],
                    ['快进快退', '← →'],
                    ['暂停', '空格'],
                ];
            panel.innerHTML = `
                <h3>${title}</h3>
                <div style="display:flex; gap:18px; align-items:flex-start; color:var(--text-color);">
                    <div style="flex:1; min-width:0;">
                        <div style="font-size:14px; font-weight:600; margin-bottom:10px;">${leftTitle}</div>
                        <div style="display:grid; grid-template-columns: 1fr 120px; gap:8px;">
                            ${interaction.map(x => this.renderShortcutRow(x[0], x[1])).join('')}
                        </div>
                    </div>
                    <div style="flex:1; min-width:0;">
                        <div style="font-size:14px; font-weight:600; margin-bottom:10px;">${rightTitle}</div>
                        <div style="display:grid; grid-template-columns: 1fr 120px; gap:8px;">
                            ${playback.map(x => this.renderShortcutRow(x[0], x[1])).join('')}
                        </div>
                    </div>
                </div>
            `;
            return;
        }

        if (k === 'password') {
            panel.innerHTML = `
                <h3>修改密码</h3>
                <div class="form-group"><input id="settings_pwd_old" type="password" class="form-input" placeholder="旧密码" style="border-radius:12px;"></div>
                <div class="form-group"><input id="settings_pwd_new" type="password" class="form-input" placeholder="新密码" style="border-radius:12px;"></div>
                <div class="form-group"><input id="settings_pwd_new2" type="password" class="form-input" placeholder="再次输入新密码" style="border-radius:12px;"></div>
                <button class="btn-primary" style="border-radius:12px;" data-action="call" data-fn="changePasswordInSettings" data-args="[]">确认修改</button>
                <div style="color:rgba(255,255,255,0.55); font-size:12px; margin-top:10px;">建议使用 8 位以上强密码。</div>
            `;
            return;
        }

        if (k === 'home') {
            const cur = localStorage.getItem('default_home') || 'recommend';
            const lang = this.state.lang === 'en' ? 'en' : 'zh';
            const homeTitle = lang === 'en' ? 'Default Home' : '默认首页';
            const homeDesc = lang === 'en' ? 'Used on startup or when no page specified.' : '启动或无指定页面时默认进入';
            const recLabel = lang === 'en' ? 'Recommend' : '推荐频道';
            const jxLabel = lang === 'en' ? 'Featured' : '精选频道';
            const foLabel = lang === 'en' ? 'Following' : '关注频道';
            panel.innerHTML = `
                <h3>${homeTitle}</h3>
                <div style="color:rgba(255,255,255,0.6); font-size:12px; margin-bottom:12px;">${homeDesc}</div>
                <div style="display:flex; flex-direction:column; gap:10px;">
                    <label style="display:flex; align-items:center; gap:10px; padding:10px 12px; border-radius:12px; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.06); cursor:pointer;">
                        <input type="radio" name="default_home" value="recommend" ${cur==='recommend'?'checked':''} onchange="app.setDefaultHome(this.value)">
                        <span>${recLabel}</span>
                    </label>
                    <label style="display:flex; align-items:center; gap:10px; padding:10px 12px; border-radius:12px; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.06); cursor:pointer;">
                        <input type="radio" name="default_home" value="jingxuan" ${cur==='jingxuan'?'checked':''} onchange="app.setDefaultHome(this.value)">
                        <span>${jxLabel}</span>
                    </label>
                    <label style="display:flex; align-items:center; gap:10px; padding:10px 12px; border-radius:12px; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.06); cursor:pointer;">
                        <input type="radio" name="default_home" value="following" ${cur==='following'?'checked':''} onchange="app.setDefaultHome(this.value)">
                        <span>${foLabel}</span>
                    </label>
                </div>
            `;
            return;
        }

        if (k === 'language') {
            const lang = this.state.lang === 'en' ? 'en' : 'zh';
            const title = lang === 'en' ? 'Language' : '语言选择';
            const zhLabel = lang === 'en' ? 'Chinese' : '中文';
            const enLabel = lang === 'en' ? 'English' : '英文';
            panel.innerHTML = `
                <h3>${title}</h3>
                <div style="display:flex; gap:10px;">
                    <div data-action="call" data-fn="setLanguage" data-args='["zh"]' style="flex:1; text-align:center; padding:12px 12px; border-radius:12px; cursor:pointer; border:1px solid var(--border-color); background:${this.state.lang==='zh'?'var(--seg-bg-active)':'var(--seg-bg)'}; color:var(--text-color);">${zhLabel}</div>
                    <div data-action="call" data-fn="setLanguage" data-args='["en"]' style="flex:1; text-align:center; padding:12px 12px; border-radius:12px; cursor:pointer; border:1px solid var(--border-color); background:${this.state.lang==='en'?'var(--seg-bg-active)':'var(--seg-bg)'}; color:var(--text-color);">${enLabel}</div>
                </div>
            `;
            return;
        }

        if (k === 'privacy') {
            const p1 = localStorage.getItem('privacy_hide_history') === '1';
            const p2 = localStorage.getItem('privacy_hide_likes') === '1';
            panel.innerHTML = `
                <h3>隐私设置</h3>
                <div style="display:flex; flex-direction:column; gap:10px;">
                    <label style="display:flex; align-items:center; justify-content:space-between; padding:12px; border-radius:12px; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.06); cursor:pointer;">
                        <span>隐藏观看历史</span>
                        <input type="checkbox" ${p1?'checked':''} onchange="localStorage.setItem('privacy_hide_history', this.checked?'1':'0')">
                    </label>
                    <label style="display:flex; align-items:center; justify-content:space-between; padding:12px; border-radius:12px; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.06); cursor:pointer;">
                        <span>隐藏我的点赞</span>
                        <input type="checkbox" ${p2?'checked':''} onchange="localStorage.setItem('privacy_hide_likes', this.checked?'1':'0')">
                    </label>
                </div>
            `;
            return;
        }

        if (k === 'notify') {
            const n1 = localStorage.getItem('notify_follow') !== '0';
            const n2 = localStorage.getItem('notify_comment') !== '0';
            const n3 = localStorage.getItem('notify_dm') !== '0';
            panel.innerHTML = `
                <h3>通知设置</h3>
                <div style="display:flex; flex-direction:column; gap:10px;">
                    <label style="display:flex; align-items:center; justify-content:space-between; padding:12px; border-radius:12px; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.06); cursor:pointer;">
                        <span>新关注通知</span>
                        <input type="checkbox" ${n1?'checked':''} onchange="localStorage.setItem('notify_follow', this.checked?'1':'0')">
                    </label>
                    <label style="display:flex; align-items:center; justify-content:space-between; padding:12px; border-radius:12px; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.06); cursor:pointer;">
                        <span>新评论通知</span>
                        <input type="checkbox" ${n2?'checked':''} onchange="localStorage.setItem('notify_comment', this.checked?'1':'0')">
                    </label>
                    <label style="display:flex; align-items:center; justify-content:space-between; padding:12px; border-radius:12px; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.06); cursor:pointer;">
                        <span>新私信通知</span>
                        <input type="checkbox" ${n3?'checked':''} onchange="localStorage.setItem('notify_dm', this.checked?'1':'0')">
                    </label>
                </div>
            `;
            return;
        }

        if (k === 'theme') {
            const cur = this.state.theme === 'light' ? 'light' : 'dark';
            panel.innerHTML = `
                <h3>深浅模式</h3>
                <div style="display:flex; gap:10px;">
                    <div data-action="call" data-fn="setTheme" data-args='["dark"]' style="flex:1; text-align:center; padding:12px 12px; border-radius:12px; cursor:pointer; border:1px solid var(--border-color); background:${cur==='dark'?'var(--seg-bg-active)':'var(--seg-bg)'}; color:var(--text-color);">深色</div>
                    <div data-action="call" data-fn="setTheme" data-args='["light"]' style="flex:1; text-align:center; padding:12px 12px; border-radius:12px; cursor:pointer; border:1px solid var(--border-color); background:${cur==='light'?'var(--seg-bg-active)':'var(--seg-bg)'}; color:var(--text-color);">浅色</div>
                </div>
            `;
            return;
        }

        if (k === 'background') {
            const c = localStorage.getItem('bg_comments_id') || 'default';
            const d = localStorage.getItem('bg_dm_id') || 'default';
            const n = localStorage.getItem('bg_notify_id') || 'default';
            const u = localStorage.getItem('bg_um_id') || 'default';
            const list = (typeof this.getOfficialBackgrounds === 'function') ? this.getOfficialBackgrounds() : [];
            const nameOf = (id) => {
                const hit = Array.isArray(list) ? list.find(x => x && String(x.id) === String(id || 'default')) : null;
                return hit && hit.name ? hit.name : '默认';
            };
            panel.innerHTML = `
                <h3>背景更换</h3>
                <div style="display:flex; flex-direction:column; gap:12px;">
                    <div style="padding:12px; border-radius:12px; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.06); display:flex; align-items:center; justify-content:space-between; gap:12px;">
                        <div style="min-width:0;">
                            <div style="font-weight:800;">评论背景更换</div>
                            <div style="color:rgba(255,255,255,0.55); font-size:12px; margin-top:6px;">当前：${nameOf(c)}</div>
                        </div>
                        <button class="btn-primary" style="border-radius:12px; width:auto;" data-action="call" data-fn="openBgPicker" data-args='["comments"]'>选择</button>
                    </div>
                    <div style="padding:12px; border-radius:12px; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.06); display:flex; align-items:center; justify-content:space-between; gap:12px;">
                        <div style="min-width:0;">
                            <div style="font-weight:800;">私聊背景更换</div>
                            <div style="color:rgba(255,255,255,0.55); font-size:12px; margin-top:6px;">当前：${nameOf(d)}</div>
                        </div>
                        <button class="btn-primary" style="border-radius:12px; width:auto;" data-action="call" data-fn="openBgPicker" data-args='["dm"]'>选择</button>
                    </div>
                    <div style="padding:12px; border-radius:12px; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.06); display:flex; align-items:center; justify-content:space-between; gap:12px;">
                        <div style="min-width:0;">
                            <div style="font-weight:800;">通知背景更换</div>
                            <div style="color:rgba(255,255,255,0.55); font-size:12px; margin-top:6px;">当前：${nameOf(n)}</div>
                        </div>
                        <button class="btn-primary" style="border-radius:12px; width:auto;" data-action="call" data-fn="openBgPicker" data-args='["notify"]'>选择</button>
                    </div>
                    <div style="padding:12px; border-radius:12px; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.06); display:flex; align-items:center; justify-content:space-between; gap:12px;">
                        <div style="min-width:0;">
                            <div style="font-weight:800;">个人背景更换</div>
                            <div style="color:rgba(255,255,255,0.55); font-size:12px; margin-top:6px;">当前：${nameOf(u)}</div>
                        </div>
                        <button class="btn-primary" style="border-radius:12px; width:auto;" data-action="call" data-fn="openBgPicker" data-args='["um"]'>选择</button>
                    </div>
                    <div style="color:rgba(255,255,255,0.55); font-size:12px;">更换后立即生效并保存在本地。</div>
                </div>
            `;
            return;
        }

        if (k === 'center' || k === 'account') {
            const email = (this.state.user && this.state.user.email) ? this.state.user.email : '';
            const phone = (this.state.user && this.state.user.phone) ? this.state.user.phone : '';
            panel.innerHTML = `
                <h3>用户中心</h3>
                <div style="display:flex; flex-direction:column; gap:10px;">
                    <div style="color:rgba(255,255,255,0.55); font-size:12px;">用户名：${this.escapeHtml(this.state.user.username || '')}</div>
                    <div class="form-group"><input id="settings_bind_phone" class="form-input" placeholder="绑定手机号（选填）" style="border-radius:12px;" value="${this.escapeHtml(phone)}"></div>
                    <div class="form-group"><input id="settings_bind_email" class="form-input" placeholder="绑定邮箱（选填）" style="border-radius:12px;" value="${this.escapeHtml(email)}"></div>
                    <div style="display:flex; gap:10px;">
                        <button class="btn-primary" style="border-radius:12px;" data-action="call" data-fn="updateContactInSettings" data-args="[]">保存</button>
                    </div>
                    <div style="color:rgba(255,255,255,0.55); font-size:12px;">绑定后可使用手机号/邮箱登录。</div>
                </div>
            `;
            return;
        }

        panel.innerHTML = `
            <h3>账号管理</h3>
            <div style="color:rgba(255,255,255,0.55); font-size:12px;">用户名：${this.escapeHtml(this.state.user.username || '')}</div>
        `;
    },

    updateContactInSettings: async function() {
        if (!this.state.user) return this.openModal('authModal');
        const phone = (document.getElementById('settings_bind_phone')?.value || '').trim();
        const email = (document.getElementById('settings_bind_email')?.value || '').trim();
        try {
            const res = await this.apiRequest('POST', '/api/v1/users/update-contact', { user_id: this.state.user.id, phone, email }, { cancel_key: `user:contact:${this.state.user.id}` });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) return alert((data && (data.detail || data.message)) || '保存失败');
            this.state.user = data.user || this.state.user;
            this.updateAuthUI();
            this.settingsSelect(this.state.settingsKey === 'account' ? 'account' : 'center');
        } catch (_) {
            alert('保存失败');
        }
    },

    setDefaultHome: function(v) {
        const val = String(v || 'recommend');
        localStorage.setItem('default_home', val);
    },

    openBgPicker: function(kind) {
        const k = kind === 'dm' ? 'dm' : (kind === 'notify' ? 'notify' : (kind === 'um' ? 'um' : 'comments'));
        this.state.bgPickerKind = k;
        this.state.bgPickerSelected = localStorage.getItem(k === 'dm' ? 'bg_dm_id' : (k === 'notify' ? 'bg_notify_id' : (k === 'um' ? 'bg_um_id' : 'bg_comments_id'))) || 'default';
        try {
            const t = document.getElementById('bg_picker_title');
            if (t) t.innerText = k === 'dm' ? '私聊背景更换' : (k === 'notify' ? '通知背景更换' : (k === 'um' ? '个人背景更换' : '评论背景更换'));
        } catch (_) {
        }
        this.renderBgPickerGrid();
        this.openModal('bgPickerModal');
    },

    renderBgPickerGrid: function() {
        const grid = document.getElementById('bg_picker_grid');
        if (!grid) return;
        const list = (typeof this.getOfficialBackgrounds === 'function') ? this.getOfficialBackgrounds() : [];
        const selected = String(this.state.bgPickerSelected || 'default');
        const kind = this.state.bgPickerKind === 'dm' ? 'dm' : (this.state.bgPickerKind === 'notify' ? 'notify' : (this.state.bgPickerKind === 'um' ? 'um' : 'comments'));
        const defaultBg =
            kind === 'dm' ? 'linear-gradient(180deg, rgba(37,38,50,0.98) 0%, rgba(23,24,33,0.98) 100%)' :
            kind === 'notify' ? 'radial-gradient(900px 560px at 18% -12%, rgba(254,44,85,0.34) 0%, rgba(254,44,85,0) 60%), radial-gradient(820px 560px at 104% 0%, rgba(86,92,255,0.24) 0%, rgba(86,92,255,0) 62%), linear-gradient(180deg, rgba(37,38,50,0.98) 0%, rgba(20,21,30,0.98) 100%)' :
            kind === 'um' ? 'radial-gradient(900px 520px at 20% -10%, rgba(254,44,85,0.22) 0%, rgba(254,44,85,0) 55%), radial-gradient(800px 520px at 100% 0%, rgba(86,92,255,0.22) 0%, rgba(86,92,255,0) 60%), linear-gradient(180deg, rgba(37,38,50,0.98) 0%, rgba(23,24,33,0.98) 100%)' :
            'var(--comments-bg)';
        grid.innerHTML = (Array.isArray(list) ? list : []).map((x) => {
            const id = x && x.id ? String(x.id) : 'default';
            const name = x && x.name ? String(x.name) : '';
            const url = x && x.url ? String(x.url) : '';
            const safeUrl = this.safeCssUrl(url);
            const bg = (!safeUrl || id === 'default') ? defaultBg : `url("${safeUrl}")`;
            const tag = id === 'default' ? '<div class="tag">默认</div>' : '';
            return `
                <div class="bg-card ${id===selected?'active':''}" style="background:${bg}; background-size:cover; background-position:center;" data-action="call" data-fn="bgPickerSelect" data-args='[${JSON.stringify(id)}]' data-stop="1">
                    ${tag}
                    <div class="name">${this.escapeHtml(name)}</div>
                </div>
            `;
        }).join('');
    },

    bgPickerSelect: function(id) {
        this.state.bgPickerSelected = String(id || 'default');
        this.renderBgPickerGrid();
    },

    bgPickerConfirm: function() {
        const kind = this.state.bgPickerKind === 'dm' ? 'dm' : (this.state.bgPickerKind === 'notify' ? 'notify' : (this.state.bgPickerKind === 'um' ? 'um' : 'comments'));
        const id = String(this.state.bgPickerSelected || 'default');
        localStorage.setItem(kind === 'dm' ? 'bg_dm_id' : (kind === 'notify' ? 'bg_notify_id' : (kind === 'um' ? 'bg_um_id' : 'bg_comments_id')), id);
        try {
            if (typeof this.applyUserBackgroundPrefs === 'function') this.applyUserBackgroundPrefs();
            else if (typeof this.applyUserBackground === 'function') this.applyUserBackground(kind, id);
        } catch (_) {
        }
        this.closeModal('bgPickerModal');
        try { this.settingsSelect('background'); } catch (_) {}
    },

    changePasswordInSettings: async function() {
        if (!this.state.user) return this.openModal('authModal');
        const oldP = (document.getElementById('settings_pwd_old')?.value || '').trim();
        const newP = (document.getElementById('settings_pwd_new')?.value || '').trim();
        const newP2 = (document.getElementById('settings_pwd_new2')?.value || '').trim();
        if (!oldP || !newP || !newP2) return alert('请填写完整');
        if (newP !== newP2) return alert('两次新密码不一致');
        try {
            const res = await this.apiRequest('POST', '/api/v1/users/change-password', { user_id: this.state.user.id, old_password: oldP, new_password: newP }, { cancel_key: `pwd:change2:${this.state.user.id}` });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) return alert((data && (data.detail || data.message)) || '修改失败');
            alert((data && data.message) || '修改成功');
            document.getElementById('settings_pwd_old').value = '';
            document.getElementById('settings_pwd_new').value = '';
            document.getElementById('settings_pwd_new2').value = '';
        } catch(e) { alert('修改失败'); }
    },

    creatorPickManualFiles: function(input) {
        if (!input.files || input.files.length === 0) return;
        
        // Convert FileList to Array
        this.state.manualFiles = Array.from(input.files);
        this.state.manualPreviewIndex = 0;
        
        this.renderManualPreview();
    },
    
    renderManualPreview: function() {
        const files = this.state.manualFiles;
        const mediaBox = document.getElementById('creator_media');
        const previewTxt = document.getElementById('creator_preview');
        const nav = document.getElementById('creator_nav');
        
        if (!files || files.length === 0) {
            // Reset to upload state
            mediaBox.innerHTML = `
                <div class="creator-media-actions">
                    <button class="c-btn" data-action="click" data-target="#creator_files_manual"><i class="fas fa-upload"></i> 上传图片/视频</button>
                    <button class="c-btn" data-action="call" data-fn="creatorClearManual" data-args="[]"><i class="fas fa-trash"></i> 清空</button>
                </div>
                <div id="creator_preview" style="color:rgba(255,255,255,0.55); font-size:13px;">上传图片/视频后在这里预览</div>
                <div class="creator-nav" id="creator_nav" style="display:none;">
                    <div class="arrow" data-action="call" data-fn="creatorPrev" data-args="[]"><i class="fas fa-chevron-left"></i></div>
                    <div class="arrow" data-action="call" data-fn="creatorNext" data-args="[]"><i class="fas fa-chevron-right"></i></div>
                </div>
                <input id="creator_files_manual" type="file" accept="video/*,image/*" multiple style="display:none" onchange="app.creatorPickManualFiles(this)">
            `;
            this.bindCreatorMediaClick();
            return;
        }

        const currentFile = files[this.state.manualPreviewIndex];
        const url = URL.createObjectURL(currentFile);
        const isVideo = currentFile.type.startsWith('video');
        
        // Keep actions visible
        let html = `
            <div class="creator-media-actions">
                <button class="c-btn" data-action="click" data-target="#creator_files_manual"><i class="fas fa-plus"></i> 继续添加</button>
                <button class="c-btn" data-action="call" data-fn="creatorClearManual" data-args="[]"><i class="fas fa-trash"></i> 清空</button>
                <div class="c-btn" style="background:rgba(0,0,0,0.6); border:none;">${this.state.manualPreviewIndex + 1} / ${files.length}</div>
            </div>
        `;
        
        if (isVideo) {
            html += `<video src="${url}" controls style="width:100%; height:100%; object-fit:contain;"></video>`;
        } else {
            html += `<img src="${url}" style="width:100%; height:100%; object-fit:contain;">`;
        }
        
        // Navigation arrows
        html += `
            <div class="creator-nav" id="creator_nav" style="display:${files.length > 1 ? 'flex' : 'none'};">
                <div class="arrow" data-action="call" data-fn="creatorPrev" data-args="[]"><i class="fas fa-chevron-left"></i></div>
                <div class="arrow" data-action="call" data-fn="creatorNext" data-args="[]"><i class="fas fa-chevron-right"></i></div>
            </div>
        `;
        
        // Re-inject input to allow adding more? Actually better to keep input outside or append.
        // For simplicity, we just re-render innerHTML. Note: existing input element is lost if we overwrite parent.
        // The input is inside .creator-media in HTML structure.
        // Let's preserve the input element by not overwriting it if possible, or re-adding it.
        html += `<input id="creator_files_manual" type="file" accept="video/*,image/*" multiple style="display:none" onchange="app.creatorPickManualFiles(this)">`;

        mediaBox.innerHTML = html;
        this.bindCreatorMediaClick();
    },

    bindCreatorMediaClick: function() {
        const mediaBox = document.getElementById('creator_media');
        if (!mediaBox) return;
        try { mediaBox.dataset.action = 'creatorPick'; } catch (_) {}
    },

    creatorPrev: function() {
        if (!this.state.manualFiles) return;
        if (this.state.manualPreviewIndex > 0) {
            this.state.manualPreviewIndex--;
            this.renderManualPreview();
        }
    },

    creatorNext: function() {
        if (!this.state.manualFiles) return;
        if (this.state.manualPreviewIndex < this.state.manualFiles.length - 1) {
            this.state.manualPreviewIndex++;
            this.renderManualPreview();
        }
    },

    creatorClearManual: function() {
        this.state.manualFiles = [];
        this.state.manualPreviewIndex = 0;
        this.renderManualPreview();
    },

});
