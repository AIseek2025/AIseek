Object.assign(window.app, {
    switchPage: function(page, opts = {}) {
        // Close comments when switching pages
        try {
            if (typeof this.closeComments === 'function') this.closeComments();
        } catch (_) {
        }

        if (page === 'inbox') {
            const tab = (this.state.inboxTab === 'dm') ? 'dm' : 'notify';
            if (typeof this.openInbox === 'function') this.openInbox(tab);
            return;
        }

        // Auth Guard for Protected Pages
        if (['following', 'friends'].includes(page)) {
            if (!this.state.user) {
                 this.state.pendingAuthAction = { type: 'route', page };
                 this.openModal('authModal');
                 // Don't return here, allow page switch to proceed but user sees empty state or modal
            }
        }

        if (this.state.currentTab && this.state.currentTab !== page) {
            if (['recommend', 'jingxuan'].includes(this.state.currentTab)) {
                try { if (typeof this.pausePageVideos === 'function') this.pausePageVideos(this.state.currentTab); } catch (_) {}
            }
        }

        if (!opts.skipHash) {
            if (page === 'recommend' && this.state.pinnedPostId) location.hash = `#/v/${this.state.pinnedPostId}`;
            else location.hash = `#/${page}`;
        }

        this.state.currentTab = page;

        try {
            if (window.appEmit && window.appEventNames) {
                window.appEmit(window.appEventNames.ROUTE_CHANGE, { tab: page });
            } else if (window.appEvents && typeof window.appEvents.emit === 'function') {
                window.appEvents.emit('route:change', { tab: page, ts: Date.now() });
            }
        } catch (_) {
        }

        document.body.classList.toggle('profile-hero', page === 'profile');
        if (page !== 'profile') document.body.style.setProperty('--profile-hero-bg', 'none');
        
        // Sidebar active state
        document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
        const navs = document.querySelectorAll('.sidebar .nav-item');
        if (page === 'recommend') navs[0].classList.add('active');
        if (page === 'jingxuan') navs[1].classList.add('active');
        if (page === 'following') {
             if(navs[2]) navs[2].classList.add('active');
        }
        if (page === 'friends') {
             if(navs[3]) navs[3].classList.add('active');
        }
        if (page === 'profile') navs[4].classList.add('active'); // Adjust index if needed
        if (page === 'settings') {
             if(navs[7]) navs[7].classList.add('active');
        }
        if (page === 'creator') {
            // 默认进入 AI 创作
            setTimeout(() => this.creatorSelectTab('ai'), 0);
        }

        // Container visibility
        document.querySelectorAll('.page-container').forEach(el => el.classList.remove('active'));
        const targetPage = document.getElementById(`page-${page}`);
        if(targetPage) targetPage.classList.add('active');

        this.updateLayoutVars();

        // Logic
        if (page === 'recommend') {
            if (this.state.pinnedPostId) return this.openPost(this.state.pinnedPostId, { skipHash: true });
            this.loadRecommend();
        }
        if (page === 'jingxuan') this.loadJingxuan();
        if (page === 'following') {
            if (this.state.user) this.loadFollowingPage();
        }
        if (page === 'friends') {
            if (this.state.user) this.loadFriendsPage();
        }
        if (page === 'profile') {
            if (!this.state.user) return this.openModal('authModal');
            if (!opts || !opts.skipProfileLoad) this.loadProfile(this.state.user.id);
        }
        if (page === 'search') {
            // Search logic is handled by searchUser or specific loaders
        }
        if (page === 'settings') {
            this.settingsSelect('password');
        }
    },

    pausePageVideos: function(page) {
        const el = document.getElementById(`page-${page}`);
        if (!el) return;
        el.querySelectorAll('video').forEach(v => {
            try { v.pause(); } catch (_) {}
        });
        if (page === 'jingxuan') this.hideJxPopup();
    },

});
