(function () {
    if (window.appInteractions) return;

    const toInt = (v) => {
        const n = Number(v);
        return Number.isFinite(n) ? n : 0;
    };

    const updatePostInArrays = (app, postId, patch) => {
        const pid = toInt(postId);
        if (!pid) return;
        const p = patch && typeof patch === 'object' ? patch : {};
        const arrs = [];
        try { if (Array.isArray(app.state.recommendPosts)) arrs.push(app.state.recommendPosts); } catch (_) {}

        arrs.forEach((arr) => {
            arr.forEach((x) => {
                if (!x || toInt(x.id) !== pid) return;
                if (p.is_liked !== undefined) x.is_liked = !!p.is_liked;
                if (p.likes_count !== undefined) x.likes_count = toInt(p.likes_count);
                if (p.is_favorited !== undefined) x.is_favorited = !!p.is_favorited;
                if (p.favorites_count !== undefined) x.favorites_count = toInt(p.favorites_count);
            });
        });
    };

    const updatePostInDOM = (postId, patch) => {
        const pid = toInt(postId);
        if (!pid) return;
        const p = patch && typeof patch === 'object' ? patch : {};

        const slides = document.querySelectorAll(`.video-slide[data-post-id="${pid}"]`);
        slides.forEach((slide) => {
            const items = slide.querySelectorAll('.video-actions .action-item');
            const likeItem = items && items.length > 1 ? items[1] : null;
            const favItem = items && items.length > 3 ? items[3] : null;

            if (likeItem && (p.is_liked !== undefined || p.likes_count !== undefined)) {
                const icon = likeItem.querySelector('i');
                const txt = likeItem.querySelector('.action-text');
                if (p.is_liked !== undefined && icon) icon.style.color = p.is_liked ? '#fe2c55' : 'var(--text-color)';
                if (p.likes_count !== undefined && txt) txt.innerText = String(toInt(p.likes_count));
            }

            if (favItem && (p.is_favorited !== undefined || p.favorites_count !== undefined)) {
                const icon = favItem.querySelector('i');
                const txt = favItem.querySelector('.action-text');
                if (p.favorites_count !== undefined && txt) txt.innerText = String(toInt(p.favorites_count));
                if (p.is_favorited !== undefined && icon) {
                    icon.classList.toggle('fas', !!p.is_favorited);
                    icon.classList.toggle('far', !p.is_favorited);
                    icon.style.color = p.is_favorited ? '#ffb800' : 'var(--text-color)';
                }
            }
        });
    };

    const updateFollowInArrays = (app, targetId, isFollowing) => {
        const tid = toInt(targetId);
        if (!tid) return;
        const following = !!isFollowing;
        const arrs = [];
        try { if (Array.isArray(app.state.recommendPosts)) arrs.push(app.state.recommendPosts); } catch (_) {}

        arrs.forEach((arr) => {
            arr.forEach((x) => {
                if (!x) return;
                if (toInt(x.user_id) === tid) x.is_following = following;
            });
        });

        try {
            const v = app.state.viewingUser && app.state.viewingUser.user ? app.state.viewingUser.user : null;
            if (v && toInt(v.id) === tid) app.state.viewingUser.is_following = following;
        } catch (_) {
        }

        try {
            if (Array.isArray(app.state.followingList) && !following) {
                const before = app.state.followingList.length;
                app.state.followingList = app.state.followingList.filter((u) => toInt(u && u.id) !== tid);
                if (app.state.currentTab === 'following' && app.state.followingSubtab === 'following' && app.state.followingList.length !== before) {
                    const panel = document.getElementById('following_list_panel');
                    const main = document.getElementById('following_main_panel');
                    if (panel && main && typeof app.renderFriendList === 'function') {
                        app.renderFriendList(panel, main, app.state.followingList, '关注', true);
                    }
                }
            }
        } catch (_) {
        }
    };

    const updateFollowInDOM = (app, targetId, isFollowing) => {
        const tid = toInt(targetId);
        if (!tid) return;
        const following = !!isFollowing;

        document.querySelectorAll(`.follow-plus[data-user-id="${tid}"]`).forEach((el) => {
            if (!app.state.user || toInt(app.state.user.id) === tid) {
                el.style.display = 'none';
                return;
            }
            el.style.display = following ? 'none' : 'flex';
        });
    };

    const emit = (event, payload) => {
        try {
            if (window.appEmit) window.appEmit(event, payload);
        } catch (_) {
        }
    };

    window.appInteractions = {
        applyPostPatch: (postId, patch) => {
            const app = window.app;
            if (!app || !app.state) return;
            updatePostInArrays(app, postId, patch);
            updatePostInDOM(postId, patch);
            emit('post:changed', { post_id: toInt(postId), patch: patch || {} });
        },
        applyFollowPatch: (targetId, isFollowing) => {
            const app = window.app;
            if (!app || !app.state) return;
            updateFollowInArrays(app, targetId, isFollowing);
            updateFollowInDOM(app, targetId, isFollowing);
            emit('follow:changed', { target_id: toInt(targetId), is_following: !!isFollowing });
        },
    };
})();
