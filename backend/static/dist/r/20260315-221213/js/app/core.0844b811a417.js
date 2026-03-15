const app = {
    state: {
        token: localStorage.getItem('token'),
        user: null, // Current logged in user
        viewingUser: null, // User profile being viewed
        
        // Data
        recommendPosts: [],
        recommendCursor: null,
        recommendLoadingMore: false,
        jingxuanPosts: [],
        profilePosts: [],
        categories: [],
        
        // Global Volume
        globalVolume: 0.5,
        isMuted: false,
        
        // UI
        currentTab: 'recommend', // recommend, jingxuan, profile
        category: 'all',
        currentProfileTab: 'works', // works, likes, favorites
        
        // Upload
        uploadFile: null,
        manualFiles: [],
        manualPreviewIndex: 0,
        aiCoverFile: null,
        aiIllusFiles: [],
        
        // Settings
        autoPlay: true,
        isCleanMode: false,
        
        // Interaction
        currentPostId: null, // For comments
        commentReplyToId: null,
        commentReplyToNickname: null,
        commentCursor: {},
        commentLoadingMore: {},
        commentLoadedIds: {},
        watchRecorded: {},

        danmakuCache: {},
        danmakuCursor: {},

        dmPeerId: null,
        dmPollTimer: null,

        notifyCursor: null,
        notifyLoadingMore: false,

        // Routing
        pinnedPostId: null,
        fullscreenPostId: null,
        activePostId: null,
        floatingPostId: null,

        searchKeyword: '',
        searchMode: 'all',
        searchPosts: [],

        pendingAuthAction: null,
        inboxTab: 'notify',
        inboxNotifyFilter: 'all',
        inboxSearchQuery: '',
        inboxPendingPeer: null,

        // Friends/Follow
        followingList: [],
        followersList: [],
        friendsList: [],
        followingSubtab: 'following',

        followModalUserId: null,
        followModalMode: 'following',
        followModalFollowingCount: 0,
        followModalFollowersCount: 0,
        followModalFollowingCache: null,
        followModalFollowersCache: null,

        aiGenType: null,
        lang: 'zh',
        theme: 'dark',
    },

    // --- Init ---
    langMap: {
        'zh': {
            'recommend': '推荐', 'jingxuan': '精选', 'following': '关注', 'friends': '好友', 'profile': '我的',
            'more': '更多', 'ai_ecommerce': 'AI电商', 'ai_hiring': 'AI招聘', 'settings': '设置',
            'upload': 'AI创作', 'search_ph': '搜索你感兴趣的内容...',
            'login': '登录', 'register': '注册',
            'msg': '私信', 'notify': '通知', 'all_read': '全部已读', 'view_all': '查看全部',
            'follow': '关注', 'followed': '已关注', 'chat': '私信', 'add_friend': '加好友',
            'likes': '获赞', 'fans': '粉丝',
            'works': '作品', 'favs': '收藏', 'history': '观看历史',
            'comprehensive': '综合', 'video': '视频', 'user': '用户', 'live': '直播',
            'filter': '筛选',
            'ai_create': 'AI创作', 'manual_upload': '手动发布'
        },
        'en': {
            'recommend': 'For You', 'jingxuan': 'Featured', 'following': 'Following', 'friends': 'Friends', 'profile': 'Profile',
            'more': 'More', 'ai_ecommerce': 'AI Shop', 'ai_hiring': 'AI Jobs', 'settings': 'Settings',
            'upload': 'AI Create', 'search_ph': 'Search...',
            'login': 'Log in', 'register': 'Sign up',
            'msg': 'Messages', 'notify': 'Inbox', 'all_read': 'Mark all read', 'view_all': 'View all',
            'follow': 'Follow', 'followed': 'Following', 'chat': 'Chat', 'add_friend': 'Add Friend',
            'likes': 'Likes', 'fans': 'Followers',
            'works': 'Posts', 'favs': 'Favorites', 'history': 'History',
            'comprehensive': 'Top', 'video': 'Videos', 'user': 'Users', 'live': 'Live',
            'filter': 'Filter',
            'ai_create': 'AI Create', 'manual_upload': 'Upload'
        }
    },

    t: function(key) {
        const lang = this.state.lang || 'zh';
        return this.langMap[lang][key] || key;
    },

    init: async function() {
        try {
            if (window.appRuntime && typeof window.appRuntime.attach === 'function') {
                window.appRuntime.attach(this);
            }
        } catch (_) {
        }
        const lang = localStorage.getItem('lang');
        if (lang === 'en' || lang === 'zh') this.state.lang = lang;
        const theme = localStorage.getItem('theme');
        if (theme === 'light' || theme === 'dark') this.state.theme = theme;
        
        // Load Global Volume
        const savedVol = localStorage.getItem('global_volume');
        const savedMute = localStorage.getItem('is_muted');
        this.state.globalVolume = savedVol ? parseFloat(savedVol) : 1;
        this.state.isMuted = savedMute === '1';

        this.applyTheme();
        this.applyLanguage();
        try { this.applyUserBackgroundPrefs(); } catch (_) {}
        await this.loadCategories();
        this.updateLayoutVars();
        window.addEventListener('resize', () => {
            clearTimeout(this._layoutTimer);
            this._layoutTimer = setTimeout(() => {
                this.updateLayoutVars();
                try { if (typeof this.clampFloatingPlayer === 'function') this.clampFloatingPlayer(); } catch (_) {}
            }, 120);
        });
        if (!this._globalKeyBound) {
            document.addEventListener('keydown', (e) => this.handleGlobalKeydown(e));
            document.addEventListener('fullscreenchange', () => {
                if (!document.fullscreenElement) this.state.fullscreenPostId = null;
                this.hideAllVolumePops();
            });
            this._globalKeyBound = true;
        }

        const wrap = document.getElementById('avatarWrap');
        if (wrap && !this._avatarMenuBound) {
            this._avatarMenuBound = true;
        }

        // Search Enter Key
        const searchInput = document.querySelector('.search-bar input');
        if (searchInput) {
            searchInput.onkeydown = (e) => {
                if (e.keyCode === 13) this.searchUser();
                if (e.keyCode === 27) {
                    searchInput.value = '';
                    const dd = document.getElementById('search_hot_dropdown');
                    if (dd) dd.classList.remove('active');
                }
            };
        }

        // Check Auth
        if (this.state.token) {
            const uid = localStorage.getItem('user_id');
            if (uid) {
                try {
                    // Fetch fresh user data
                    await this.fetchCurrentUser(uid);
                    this.loadHeaderDropdowns(); // Load dropdown data
                } catch(e) { console.error(e); }
            }
        }
        
        this.updateAuthUI();

        if (typeof this.bindAuthHotkeys === 'function') {
            this.bindAuthHotkeys();
        }
        
        window.onhashchange = () => this.routeFromHash();
        this.routeFromHash();
    },

    switchTab: function(tab, opts = {}) {
        const page = String(tab || '').trim() || 'recommend';
        if (typeof this.switchPage === 'function') {
            return this.switchPage(page, opts);
        }
        if (!opts || !opts.skipHash) {
            try {
                location.hash = `#/${page}`;
            } catch (_) {
            }
        }
        try {
            this.state.currentTab = page;
        } catch (_) {
        }
        try {
            document.querySelectorAll('.page-container').forEach(el => el.classList.remove('active'));
            const target = document.getElementById(`page-${page}`);
            if (target) target.classList.add('active');
        } catch (_) {
        }
        try {
            document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
        } catch (_) {
        }
        try {
            if (typeof this.updateLayoutVars === 'function') this.updateLayoutVars();
        } catch (_) {
        }
    },

    getOfficialBackgrounds: function() {
        return [
            { id: 'default', name: '默认', url: '' },
            { id: 'aurora_red', name: '极光红', url: '/static/img/backgrounds/aurora_red.svg' },
            { id: 'aurora_purple', name: '极光紫', url: '/static/img/backgrounds/aurora_purple.svg' },
            { id: 'mist_blue', name: '雾蓝', url: '/static/img/backgrounds/mist_blue.svg' },
            { id: 'sunset', name: '落日', url: '/static/img/backgrounds/sunset.svg' },
            { id: 'neon_grid', name: '霓虹网格', url: '/static/img/backgrounds/neon_grid.svg' },
            { id: 'starfield', name: '星河', url: '/static/img/backgrounds/starfield.svg' },
            { id: 'mint', name: '薄荷', url: '/static/img/backgrounds/mint.svg' },
        ];
    },

    applyUserBackgroundPrefs: function() {
        try {
            const c = localStorage.getItem('bg_comments_id') || 'default';
            const d = localStorage.getItem('bg_dm_id') || 'default';
            const n = localStorage.getItem('bg_notify_id') || 'default';
            const u = localStorage.getItem('bg_um_id') || 'default';
            this.applyUserBackground('comments', c);
            this.applyUserBackground('dm', d);
            this.applyUserBackground('notify', n);
            this.applyUserBackground('um', u);
        } catch (_) {
        }
    },

    applyUserBackground: function(kind, bgId) {
        const k =
            kind === 'dm' ? 'dm' :
            kind === 'notify' ? 'notify' :
            kind === 'um' ? 'um' :
            'comments';
        const id = String(bgId || 'default');
        const list = this.getOfficialBackgrounds();
        const hit = (Array.isArray(list) ? list.find(x => x && String(x.id) === id) : null) || { id: 'default', url: '' };
        const url = hit && hit.url ? String(hit.url) : '';
        const root = document && document.documentElement ? document.documentElement : null;
        if (!root || !root.style) return;
        const prop =
            k === 'dm' ? '--dm-bg-user' :
            k === 'notify' ? '--notify-bg-user' :
            k === 'um' ? '--um-bg-user' :
            '--comments-bg-user';
        if (!url || id === 'default') root.style.removeProperty(prop);
        else root.style.setProperty(prop, `url("${url}")`);
    },

    applyLanguage: function() {
        const lang = this.state.lang === 'en' ? 'en' : 'zh';
        document.documentElement.lang = lang === 'en' ? 'en' : 'zh-CN';
        
        // Search Placeholder
        const searchInput = document.querySelector('.search-bar input');
        if (searchInput) searchInput.placeholder = this.t('search_ph');

        // Sidebar
        const navs = document.querySelectorAll('.sidebar .nav-item');
        if (navs.length >= 8) {
            navs[0].innerHTML = `<i class="fas fa-home"></i> ${this.t('recommend')}`;
            navs[1].innerHTML = `<i class="fas fa-compass"></i> ${this.t('jingxuan')}`;
            navs[2].innerHTML = `<i class="fas fa-user-friends"></i> ${this.t('following')}`;
            navs[3].innerHTML = `<i class="fas fa-user-check"></i> ${this.t('friends')}`;
            navs[4].innerHTML = `<i class="fas fa-user"></i> ${this.t('profile')}`;
            navs[5].innerHTML = `<i class="fas fa-shopping-bag"></i> ${this.t('ai_ecommerce')}`;
            navs[6].innerHTML = `<i class="fas fa-briefcase"></i> ${this.t('ai_hiring')}`;
            navs[7].innerHTML = `<i class="fas fa-cog"></i> ${this.t('settings')}`;
        }
        const moreTitle = document.querySelector('.sidebar .nav-group-title');
        if (moreTitle) moreTitle.innerText = this.t('more');

        // Upload Button
        const upBtn = document.getElementById('btn_ai_create');
        if (upBtn) upBtn.textContent = `+${this.t('upload')}`;

        // Search Tabs
        const sTabs = document.querySelectorAll('.search-tab');
        if (sTabs.length >= 4) {
            sTabs[0].innerText = this.t('comprehensive');
            sTabs[1].innerText = this.t('video');
            sTabs[2].innerText = this.t('user');
            sTabs[3].innerText = this.t('live');
        }

        // Creator Tabs
        const cTabs = document.querySelectorAll('.creator-tab2');
        if (cTabs.length >= 2) {
            cTabs[0].innerHTML = `<i class="fas fa-robot" style="margin-right:6px;"></i>${this.t('ai_create')}`;
            cTabs[1].innerHTML = `<i class="fas fa-upload" style="margin-right:6px;"></i>${this.t('manual_upload')}`;
        }

        const settingsTitle = document.getElementById('settings_page_title');
        if (settingsTitle) settingsTitle.innerText = lang === 'en' ? 'Settings' : '设置';
        const navMap = {
            password: lang === 'en' ? 'Change Password' : '修改密码',
            account: lang === 'en' ? 'Account' : '账号管理',
            privacy: lang === 'en' ? 'Privacy' : '隐私设置',
            notify: lang === 'en' ? 'Notifications' : '通知设置',
            home: lang === 'en' ? 'Default Home' : '默认首页',
            language: lang === 'en' ? 'Language' : '语言选择',
            shortcuts: lang === 'en' ? 'Shortcuts' : '快捷键',
            center: lang === 'en' ? 'User Center' : '用户中心',
            theme: lang === 'en' ? 'Theme' : '深浅模式',
        };
        Object.keys(navMap).forEach(k => {
            const el = document.querySelector(`#settings_nav_${k} span`);
            if (el) el.innerText = navMap[k];
        });
    },

    applyTheme: function() {
        const t = this.state.theme === 'light' ? 'light' : 'dark';
        document.documentElement.dataset.theme = t;
    },

    setTheme: function(theme) {
        const t = theme === 'light' ? 'light' : 'dark';
        this.state.theme = t;
        localStorage.setItem('theme', t);
        this.applyTheme();
        if (this.state.currentTab === 'settings' && this.state.currentSettingsKey === 'theme') {
            this.settingsSelect('theme');
        }
    },

    setLanguage: function(lang) {
        const v = lang === 'en' ? 'en' : 'zh';
        this.state.lang = v;
        localStorage.setItem('lang', v);
        this.applyLanguage();
        if (this.state.currentTab === 'settings') {
            const k = this.state.currentSettingsKey || 'home';
            this.settingsSelect(k);
        }
    },

    loadCategories: async function() {
        try {
            const arr = await this.apiGetJSON('/api/v1/posts/categories', { cancel_key: 'cats', dedupe_key: '/api/v1/posts/categories', cache_ttl_ms: 60000 });
            this.state.categories = Array.isArray(arr) ? arr.filter(Boolean) : [];
        } catch (_) {
            this.state.categories = [];
        }
        this.populateCategorySelects();
    },

    populateCategorySelects: function() {
        const cats = Array.isArray(this.state.categories) ? this.state.categories : [];
        const ids = ['c_category', 'ai_category'];
        ids.forEach(id => {
            const sel = document.getElementById(id);
            if (!sel) return;
            const first = sel.querySelector('option[value=""]');
            sel.innerHTML = '';
            if (first) sel.appendChild(first);
            else {
                const o = document.createElement('option');
                o.value = '';
                o.innerText = '选择分类（选填）';
                sel.appendChild(o);
            }
            cats.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c;
                opt.innerText = c;
                sel.appendChild(opt);
            });
        });
    },

    updateLayoutVars: function() {
        const root = document.documentElement;
        const parsePx = (v, fallback) => {
            const n = parseFloat(String(v || '').replace('px', '').trim());
            return Number.isFinite(n) ? n : fallback;
        };
        const navbar = document.querySelector('.navbar');
        if (navbar) {
            const h = Math.round(navbar.getBoundingClientRect().height);
            if (h > 0) root.style.setProperty('--header-height', `${h}px`);
        }

        const sidebar = document.querySelector('.sidebar');
        if (sidebar) {
            const w = Math.round(sidebar.getBoundingClientRect().width);
            if (w > 0) root.style.setProperty('--sidebar-width', `${w}px`);
        }

        const content = document.querySelector('.content-area');
        const tabs = document.querySelector('#page-jingxuan .category-tabs');
        if (content) {
            const rect = content.getBoundingClientRect();
            const contentH = Math.round(rect.height);
            const tabsH = tabs ? Math.round(tabs.getBoundingClientRect().height) : 0;
            const base = Math.max(0, contentH - tabsH - 40);
            const featuredH = Math.round(Math.max(480, Math.min(720, base)));
            root.style.setProperty('--jx-featured-h', `${featuredH}px`);
        }
    },

    routeFromHash: async function() {
        const h = (location.hash || '').replace(/^#/, '');
        const parts = h.split('?');
        const path = parts[0] || '';
        this.state.pendingSearchRoute = null;
        try {
            const qs = new URLSearchParams(parts[1] || '');
            const tab = String(qs.get('tab') || '').trim();
            const allow = new Set(['works', 'likes', 'favorites', 'history']);
            if (allow.has(tab)) this.state.pendingProfileTab = tab;
            else this.state.pendingProfileTab = null;
            if (path === '/search') {
                const q = String(qs.get('q') || qs.get('kw') || '').trim();
                const smode = String(qs.get('smode') || qs.get('mode') || 'all').trim();
                let qf = String(qs.get('qf') || qs.get('quality_filter') || '').trim();
                if (!qf) {
                    const lq = String(qs.get('lq') || '').trim();
                    if (lq === '1' || lq.toLowerCase() === 'true') qf = 'cd';
                }
                if (!qf) qf = 'all';
                const qth = Math.round(Number(qs.get('qth') || qs.get('qscore') || 70) || 70);
                const qsort = String(qs.get('qsort') || qs.get('sort') || 'default').trim();
                const svc = String(qs.get('svc') || '').trim();
                const svk = String(qs.get('svk') || '').trim();
                this.state.pendingSearchRoute = { q, smode, qf, qth, qsort, svc, svk };
            }
        } catch (_) {
        }

        if (!path) {
            const def = localStorage.getItem('default_home');
            if (def && ['recommend', 'jingxuan', 'following'].includes(def)) {
                this.switchPage(def, { skipHash: true });
                return;
            }
        }

        if (path.startsWith('/v/')) {
            const idStr = path.replace('/v/', '');
            const postId = parseInt(idStr, 10);
            if (!isNaN(postId)) {
                await this.openPost(postId, { skipHash: true });
                return;
            }
        }

        if (path.startsWith('/u/')) {
            const idStr = path.replace('/u/', '');
            const userId = parseInt(idStr, 10);
            if (!isNaN(userId)) {
                this.switchPage('profile', { skipHash: true, skipProfileLoad: true });
                this.loadProfile(userId);
                return;
            }
        }

        const page = (path.startsWith('/') ? path.slice(1) : path) || 'recommend';
        this.state.pinnedPostId = null;
        this.switchPage(page, { skipHash: true });
    },

    openPost: async function(postId, opts = {}) {
        if (!opts.skipHash) location.hash = `#/v/${postId}`;
        this.state.pinnedPostId = postId;
        this.state.recommendCursor = null;
        this.state.recommendLoadingMore = false;
        const container = document.getElementById('page-recommend');
        document.querySelectorAll('.page-container').forEach(el => el.classList.remove('active'));
        container.classList.add('active');
        
        container.innerHTML = '<div style="color:#888; display:flex; justify-content:center; align-items:center; height:100%;">加载中...</div>';

        try {
            const url = `/api/v1/posts/${postId}${this.state.user ? `?user_id=${this.state.user.id}` : ''}`;
            const res = await this.apiRequest('GET', url, undefined, { cancel_key: `post:${postId}`, dedupe_key: url });
            if (!res.ok) throw new Error('not found');
            const post = await res.json();
            let seq = [post];
            try {
                const jx = Array.isArray(this.state.jingxuanPosts) ? this.state.jingxuanPosts : [];
                const i = jx.findIndex((p) => Number(p && p.id) === Number(post && post.id));
                if (i >= 0) {
                    seq = jx.slice(i).concat(jx.slice(0, i));
                    this.state.recommendIndex = 0;
                    this.state.recommendSource = 'jingxuan';
                } else {
                    this.state.recommendSource = 'feed';
                }
            } catch (_) {
                this.state.recommendSource = 'feed';
            }
            this.state.recommendPosts = seq;
            this.renderRecommendPosts(seq);
            this.state.currentTab = 'recommend';
            document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
            const navs = document.querySelectorAll('.sidebar .nav-item');
            if (navs[0]) navs[0].classList.add('active');
        } catch (e) {
            container.innerHTML = '<div style="color:#888; display:flex; justify-content:center; align-items:center; height:100%;">内容不存在</div>';
        }
    },

    renderRecommendPosts: function(posts) {
        const container = document.getElementById('page-recommend');
        container.innerHTML = '';

        if (!posts || posts.length === 0) {
            container.innerHTML = '<div style="color:#888; display:flex; justify-content:center; align-items:center; height:100%;">暂无推荐视频</div>';
            return;
        }

        posts.forEach(post => {
            const slide = document.createElement('div');
            slide.className = 'video-slide';
            slide.id = `slide-${post.id}`;
            slide.dataset.postId = String(post.id);
            slide.innerHTML = this.renderVideoSlide(post);
            container.appendChild(slide);
            this.bindVideoEvents(slide, post);
        });

        this.initObserver();
    },

    updateAuthUI: function() {
        if (this.state.user) {
            document.getElementById('btnLogin').style.display = 'none';
            document.getElementById('headerAvatar').style.backgroundImage = `url(${this.state.user.avatar || '/static/img/default_avatar.svg'})`;
            this.refreshUserHoverMenu(true);
            try {
                const friends = document.getElementById('page-friends');
                if (friends && friends.classList && friends.classList.contains('active') && typeof this.loadFriendsPage === 'function') {
                    this.loadFriendsPage();
                }
            } catch (_) {
            }
        } else {
            document.getElementById('btnLogin').style.display = 'flex';
            document.getElementById('headerAvatar').style.backgroundImage = '';
            this.refreshUserHoverMenu(true);
        }
    },

    refreshUserHoverMenu: function(syncOnly = false) {
        const u = this.state.user;
        const nameEl = document.getElementById('umName');
        const subEl = document.getElementById('umSub');
        const avatarEl = document.getElementById('umAvatar');
        const f1 = document.getElementById('umFollowing');
        const f2 = document.getElementById('umFollowers');
        const rep = document.getElementById('umRep');
        if (nameEl) nameEl.innerText = u ? (u.nickname || u.username) : '未登录';
        if (subEl) subEl.innerText = u ? `AIseek号：${String(u.aiseek_id || u.id)}` : 'AIseek';
        if (avatarEl) avatarEl.src = u ? (u.avatar || '/static/img/default_avatar.svg') : '/static/img/default_avatar.svg';
        if (f1) f1.innerText = u ? (u.following_count || 0) : 0;
        if (f2) f2.innerText = u ? (u.followers_count || 0) : 0;
        if (rep) rep.innerText = u ? (u.reputation_score == null ? 100 : u.reputation_score) : 100;
        if (syncOnly) return;
    },

    fetchCurrentUser: async function(uid) {
        try {
            const url = `/api/v1/users/profile/${uid}?current_user_id=${uid}`;
            const res = await this.apiRequest('GET', url, undefined, { cancel_key: `me:${uid}`, dedupe_key: url });
            if (res.ok) {
                const data = await res.json();
                this.state.user = data.user;
                localStorage.setItem('user_id', this.state.user.id);
                localStorage.setItem('username', this.state.user.username);
                this.updateAuthUI(); // Update UI immediately
                try {
                    const tab = String(this.state.currentTab || '');
                    if (tab === 'friends' && typeof this.loadFriendsPage === 'function') this.loadFriendsPage();
                    if (tab === 'following' && typeof this.loadFollowingPage === 'function') this.loadFollowingPage();
                    if (tab === 'profile' && typeof this.loadProfile === 'function') this.loadProfile(this.state.user.id);
                } catch (_) {
                }
            } else {
                console.error('Fetch user failed:', res.status);
                // If 404/401, maybe clear token
                if(res.status === 404) this.logout();
            }
        } catch(e) { console.error("Fetch user failed", e); }
    },

};
window.app = app;
