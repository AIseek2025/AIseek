Object.assign(window.app, {
    syncPostState: function(postId, patch) {
        const pid = Number(postId || 0);
        if (!pid) return;
        const p = patch && typeof patch === 'object' ? patch : {};

        const updateArr = (arr) => {
            if (!Array.isArray(arr)) return;
            arr.forEach(x => {
                if (!x || Number(x.id || 0) !== pid) return;
                if (p.is_liked !== undefined) x.is_liked = !!p.is_liked;
                if (p.likes_count !== undefined) x.likes_count = Number(p.likes_count) || 0;
                if (p.is_favorited !== undefined) x.is_favorited = !!p.is_favorited;
                if (p.favorites_count !== undefined) x.favorites_count = Number(p.favorites_count) || 0;
            });
        };

        try { updateArr(this.state.recommendPosts); } catch (_) {}

        const slides = document.querySelectorAll(`.video-slide[data-post-id="${pid}"]`);
        slides.forEach(slide => {
            const likeItem = slide.querySelector('.video-actions .action-item[data-fn="toggleLike"]');
            const favItem = slide.querySelector('.video-actions .action-item[data-fn="toggleFavorite"]');

            if (likeItem && (p.is_liked !== undefined || p.likes_count !== undefined)) {
                const icon = likeItem.querySelector('i');
                const txt = likeItem.querySelector('.action-text');
                if (p.is_liked !== undefined && icon) icon.style.color = p.is_liked ? '#fe2c55' : 'var(--text-color)';
                if (p.likes_count !== undefined && txt) txt.innerText = String(Number(p.likes_count) || 0);
            }
            if (favItem && (p.is_favorited !== undefined || p.favorites_count !== undefined)) {
                const icon = favItem.querySelector('i');
                const txt = favItem.querySelector('.action-text');
                if (p.favorites_count !== undefined && txt) txt.innerText = String(Number(p.favorites_count) || 0);
                if (p.is_favorited !== undefined && icon) {
                    icon.classList.toggle('fas', !!p.is_favorited);
                    icon.classList.toggle('far', !p.is_favorited);
                    icon.style.color = p.is_favorited ? '#ffb800' : 'var(--text-color)';
                }
            }
        });
    },

    syncFollowState: function(targetId, isFollowing) {
        const tid = Number(targetId || 0);
        if (!tid) return;
        const following = !!isFollowing;

        const updateArr = (arr) => {
            if (!Array.isArray(arr)) return;
            arr.forEach(x => {
                if (!x) return;
                if (Number(x.user_id || 0) === tid) x.is_following = following;
            });
        };

        try { updateArr(this.state.recommendPosts); } catch (_) {}
        try {
            if (Array.isArray(this.state.followingList)) {
                if (!following) {
                    const before = this.state.followingList.length;
                    this.state.followingList = this.state.followingList.filter(u => Number((u && u.id) || 0) !== tid);
                    if (this.state.currentTab === 'following' && this.state.followingSubtab === 'following' && this.state.followingList.length !== before) {
                        const panel = document.getElementById('following_list_panel');
                        const main = document.getElementById('following_main_panel');
                        if (panel && main) this.renderFriendList(panel, main, this.state.followingList, '关注', true);
                    }
                }
            }
        } catch (_) {
        }

        try {
            const v = this.state.viewingUser && this.state.viewingUser.user ? this.state.viewingUser.user : null;
            if (v && Number(v.id || 0) === tid) this.state.viewingUser.is_following = following;
        } catch (_) {
        }

        document.querySelectorAll(`.follow-plus[data-user-id="${tid}"]`).forEach(el => {
            if (!this.state.user || Number(this.state.user.id || 0) === tid) {
                el.style.display = 'none';
                return;
            }
            el.style.display = following ? 'none' : 'flex';
        });

        try {
            if (window.appEmit) window.appEmit('follow:changed', { target_id: tid, is_following: following });
        } catch (_) {
        }
    },

    toggleLike: async function(postId, btn) {
        if (!this.ensureAuth({ type: 'like', postId })) return;
        try {
            const res = await this.apiRequest('POST', '/api/v1/interaction/like', { post_id: postId, user_id: this.state.user.id }, { cancel_key: `like:${postId}` });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const d = (data && data.detail) ? data.detail : (data && data.message) ? data.message : '操作失败';
                this.toast(typeof d === 'string' ? d : '操作失败');
                return;
            }
            const icon = btn && btn.querySelector ? btn.querySelector('i') : null;
            const txt = btn && btn.querySelector ? btn.querySelector('.action-text') : null;
            
            if (data.status === 'liked') {
                if (icon) icon.style.color = '#fe2c55';
                this.toast('已点赞');
            } else {
                if (icon) icon.style.color = 'var(--text-color)';
                this.toast('已取消点赞');
            }
            const count = Number.isFinite(Number(data.count)) ? Number(data.count) : 0;
            if (txt) txt.innerText = String(count);
            if (window.appInteractions && typeof window.appInteractions.applyPostPatch === 'function') {
                window.appInteractions.applyPostPatch(postId, { is_liked: data.status === 'liked', likes_count: count });
            }
        } catch(e) {
            const msg = e && e.message ? String(e.message) : '操作失败';
            this.toast(msg);
        }
    },

    toggleFavorite: async function(postId, btn) {
        if (!this.ensureAuth({ type: 'favorite', postId })) return;
        try {
            const res = await this.apiRequest('POST', '/api/v1/interaction/favorite', { post_id: postId, user_id: this.state.user.id }, { cancel_key: `fav:${postId}` });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const d = (data && data.detail) ? data.detail : (data && data.message) ? data.message : '操作失败';
                this.toast(typeof d === 'string' ? d : '操作失败');
                return;
            }
            const icon = btn && btn.querySelector ? btn.querySelector('i') : null;
            const txt = btn && btn.querySelector ? btn.querySelector('.action-text') : null;

            const count = Number.isFinite(Number(data.count)) ? Number(data.count) : 0;
            if (txt) txt.innerText = String(count);

            if (data.status === 'favorited') {
                if (icon) {
                    icon.classList.remove('far');
                    icon.classList.add('fas');
                    icon.style.color = '#ffb800';
                }
                this.toast('已收藏');
            } else {
                if (icon) {
                    icon.classList.remove('fas');
                    icon.classList.add('far');
                    icon.style.color = 'var(--text-color)';
                }
                this.toast('已取消收藏');
            }
            if (window.appInteractions && typeof window.appInteractions.applyPostPatch === 'function') {
                window.appInteractions.applyPostPatch(postId, { is_favorited: data.status === 'favorited', favorites_count: count });
            }
        } catch(e) {
            const msg = e && e.message ? String(e.message) : '操作失败';
            this.toast(msg);
        }
    },

    toggleRepost: async function(postId, btn) {
        if (!this.ensureAuth({ type: 'repost', postId })) return;
        try {
            const res = await this.apiRequest('POST', '/api/v1/interaction/repost', { post_id: postId, user_id: this.state.user.id }, { cancel_key: `repost:${postId}` });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const d = (data && data.detail) ? data.detail : (data && data.message) ? data.message : '操作失败';
                this.toast(typeof d === 'string' ? d : '操作失败');
                return;
            }
            const icon = btn && btn.querySelector ? btn.querySelector('i') : null;
            const txt = btn && btn.querySelector ? btn.querySelector('.action-text') : null;
            const count = Number.isFinite(Number(data.count)) ? Number(data.count) : 0;
            if (txt) txt.innerText = String(count);
            const on = String(data.status || '') === 'reposted';
            if (icon) icon.style.color = on ? '#00d4ff' : 'var(--text-color)';
            this.toast(on ? '已转发' : '已取消转发');
            if (window.appInteractions && typeof window.appInteractions.applyPostPatch === 'function') {
                window.appInteractions.applyPostPatch(postId, { is_reposted: on, shares_count: count });
            }
        } catch(e) {
            const msg = e && e.message ? String(e.message) : '操作失败';
            this.toast(msg);
        }
    },

    toggleFollow: async function(targetId, btn) {
        if (!this.state.user) return this.openModal('authModal');
        
        // Optimistic UI Update
        const isProfile = this.state.currentTab === 'profile' && this.state.viewingUser?.user?.id === targetId;
        let profileBtn = null;
        if (isProfile) {
            profileBtn = document.querySelector('#p-header .btn-primary'); // Assuming it's the first button
            if (profileBtn && (profileBtn.innerText === '关注' || profileBtn.innerText === '已关注')) {
                const isFollowing = profileBtn.innerText === '已关注';
                profileBtn.innerText = isFollowing ? '关注' : '已关注';
                profileBtn.style.background = isFollowing ? 'var(--primary-color)' : 'var(--seg-bg-active)';
                profileBtn.style.color = isFollowing ? 'white' : 'var(--text-color)';
            }
        }

        try {
            const res = await this.apiRequest('POST', '/api/v1/users/follow', { user_id: this.state.user.id, target_id: targetId }, { cancel_key: `follow:${targetId}` });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                // Revert optimistic update
                if (profileBtn) {
                    const txt = profileBtn.innerText;
                    profileBtn.innerText = txt === '关注' ? '已关注' : '关注';
                    profileBtn.style.background = txt === '关注' ? 'var(--seg-bg-active)' : 'var(--primary-color)';
                    profileBtn.style.color = txt === '关注' ? 'var(--text-color)' : 'white';
                }
                const d = (data && data.detail) ? data.detail : (data && data.message) ? data.message : '操作失败';
                this.toast(typeof d === 'string' ? d : '操作失败');
                return;
            }
            
            const following = String(data.message || '') === 'Followed';
            if (window.appInteractions && typeof window.appInteractions.applyFollowPatch === 'function') {
                window.appInteractions.applyFollowPatch(targetId, following);
            }
        } catch(e) {
            if (profileBtn) {
                try {
                    const txt = profileBtn.innerText;
                    profileBtn.innerText = txt === '关注' ? '已关注' : '关注';
                    profileBtn.style.background = txt === '关注' ? 'var(--seg-bg-active)' : 'var(--primary-color)';
                    profileBtn.style.color = txt === '关注' ? 'var(--text-color)' : 'white';
                } catch (_) {
                }
            }
            const msg = e && e.message ? String(e.message) : '操作失败';
            this.toast(msg);
        }
    },

    openComments: async function(postId, triggerEl) {
        const prevId = this.state.currentPostId;
        const prevStage = this.state.currentCommentsStageEl || null;

        const anchor = triggerEl && triggerEl.closest ? triggerEl : null;
        const stageFromEl = anchor ? (anchor.closest('.video-stage') || null) : null;

        if (prevId && (prevId !== postId || (prevStage && stageFromEl && prevStage !== stageFromEl))) {
            this._closeCommentsFor(prevId, prevStage);
        }

        this.state.currentPostId = postId;
        this.state.currentCommentsStageEl = stageFromEl || null;

        const els = this.getCommentsEls(postId, stageFromEl);
        if (!els || !els.stage) return;

        els.stage.classList.add('comments-open');
        document.body.classList.add('comments-open');

        this.updateVideoRightInsetFromComments(postId);

        if (els.list) els.list.innerHTML = '<div style="color:#888; text-align:center; padding:20px;">加载中...</div>';
        if (els.countEl) els.countEl.innerText = '...';

        this.clearCommentReply();

        this.state.commentCursor[postId] = null;
        this.state.commentLoadingMore[postId] = false;
        this.state.commentLoadedIds[postId] = {};

        try {
            let url = `/api/v1/interaction/comments/${postId}?limit=80`;
            const res = await this.apiRequest('GET', url);
            const nextCursor = res.headers ? res.headers.get('x-next-cursor') : null;
            const totalStr = res.headers ? res.headers.get('x-total-count') : null;
            const comments = await res.json();

            if (els.countEl) {
                const n = parseInt(String(totalStr || ''), 10);
                els.countEl.innerText = Number.isFinite(n) ? String(n) : (Array.isArray(comments) ? String(comments.length) : '0');
            }
            if (els.list) els.list.innerHTML = '';

            const arr = Array.isArray(comments) ? comments : [];
            if (arr.length === 0) {
                if (els.list) els.list.innerHTML = '<div style="color:#666; text-align:center; padding:40px;">暂无评论，快来抢沙发</div>';
                this.state.commentCursor[postId] = null;
                return;
            }

            if (els.list) {
                els.list.style.textAlign = 'left';
                els.list.style.padding = '6px 0';
            }

            this.state.commentCursor[postId] = nextCursor || null;
            this.appendComments(postId, arr);
            this.bindCommentsInfiniteScroll(postId);
        } catch(e) {
            console.error(e);
            if (els.list) els.list.innerHTML = '<div style="color:#888; text-align:center; padding:20px;">加载失败</div>';
            if (typeof this.toast === 'function') this.toast('评论加载失败');
        }
    },

    appendComments: function(postId, comments) {
        const pid = Number(postId || 0);
        if (!pid) return;
        const els = this.getCommentsEls(pid);
        if (!els || !els.list) return;

        const loaded = this.state.commentLoadedIds[pid] || {};
        const arr = Array.isArray(comments) ? comments : [];
        arr.forEach(c => {
            const cid = c && c.id ? Number(c.id) : 0;
            if (!cid) return;
            if (loaded[cid]) return;
            loaded[cid] = true;

            const item = document.createElement('div');
            item.className = 'comment-item';

            item.style.width = '100%';
            item.style.padding = '8px 12px';
            item.style.display = 'flex';
            item.style.gap = '10px';
            item.style.alignItems = 'flex-start';
            item.style.justifyContent = 'flex-start';
            item.style.textAlign = 'left';

            const avatar = document.createElement('img');
            avatar.className = 'comment-avatar';
            avatar.src = c.user_avatar || '/static/img/default_avatar.svg';
            avatar.style.width = '34px';
            avatar.style.height = '34px';
            avatar.style.borderRadius = '50%';
            avatar.style.objectFit = 'cover';
            avatar.style.flexShrink = '0';
            try {
                avatar.dataset.action = 'openProfileFromComment';
                avatar.dataset.userId = String(c.user_id || '');
            } catch (_) {
            }

            const body = document.createElement('div');
            body.className = 'comment-body';
            body.style.width = '100%';
            body.style.display = 'flex';
            body.style.flexDirection = 'column';
            body.style.alignItems = 'flex-start';
            body.style.textAlign = 'left';

            const user = document.createElement('div');
            user.className = 'comment-user';
            user.textContent = c.user_nickname || '';
            user.style.fontSize = '13px';
            user.style.lineHeight = '1.25';
            user.style.margin = '0';
            user.style.padding = '0';
            try {
                user.dataset.action = 'openProfileFromComment';
                user.dataset.userId = String(c.user_id || '');
            } catch (_) {
            }

            const text = document.createElement('div');
            text.className = 'comment-text';
            text.style.width = '100%';
            text.style.textAlign = 'left';
            text.style.fontSize = '14px';
            text.style.lineHeight = '1.36';
            text.style.margin = '4px 0 0';

            if (c.parent_id && c.reply_to_nickname) {
                const prefix = document.createElement('span');
                prefix.innerText = `回复 @${c.reply_to_nickname} : `;
                prefix.style.color = 'rgba(255,255,255,0.6)';
                text.appendChild(prefix);
            }
            text.appendChild(document.createTextNode(String(c.content || '')));

            const meta = document.createElement('div');
            meta.className = 'comment-meta';
            meta.style.width = '100%';
            meta.style.display = 'flex';
            meta.style.justifyContent = 'flex-start';
            meta.style.gap = '10px';
            meta.style.fontSize = '12px';
            meta.style.margin = '4px 0 0';
            meta.style.lineHeight = '1.25';
            meta.style.textAlign = 'left';

            const metaSpan = document.createElement('span');
            const ago = this.fmtTimeAgo((c.created_at || 0) * 1000);
            const loc = String(c.location || '').trim();
            metaSpan.innerText = loc ? `${ago} · ${loc}` : ago;
            meta.appendChild(metaSpan);

            const actions = document.createElement('div');
            actions.className = 'comment-actions-row';
            actions.style.width = '100%';
            actions.style.display = 'flex';
            actions.style.justifyContent = 'flex-start';
            actions.style.gap = '16px';
            actions.style.marginTop = '6px';
            actions.style.fontSize = '12px';
            actions.style.lineHeight = '1.25';
            actions.style.textAlign = 'left';

            const reply = document.createElement('span');
            reply.innerText = '回复';
            try {
                reply.dataset.action = 'call';
                reply.dataset.fn = 'replyComment';
                reply.dataset.args = JSON.stringify([c.id, c.user_nickname]);
            } catch (_) {
            }

            const like = document.createElement('span');
            like.innerHTML = `<i class="far fa-heart"></i> <span class="c-like-count">${c.likes_count || 0}</span>`;
            try {
                like.dataset.action = 'call';
                like.dataset.fn = 'reactComment';
                like.dataset.args = JSON.stringify([c.id, 'like']);
                like.dataset.passEl = '1';
            } catch (_) {
            }

            const dislikes = c.dislikes_count || 0;
            const dislike = document.createElement('span');
            dislike.innerHTML = `<i class="far fa-thumbs-down"></i> <span class="c-dislike-count">${dislikes}</span>`;
            try {
                dislike.dataset.action = 'call';
                dislike.dataset.fn = 'reactComment';
                dislike.dataset.args = JSON.stringify([c.id, 'dislike']);
                dislike.dataset.passEl = '1';
            } catch (_) {
            }

            actions.appendChild(reply);
            actions.appendChild(like);
            actions.appendChild(dislike);

            body.appendChild(user);
            body.appendChild(text);
            body.appendChild(meta);
            body.appendChild(actions);

            item.appendChild(avatar);
            item.appendChild(body);
            els.list.appendChild(item);
        });
        this.state.commentLoadedIds[pid] = loaded;
    },

    bindCommentsInfiniteScroll: function(postId) {
        const pid = Number(postId || 0);
        if (!pid) return;
        this._commentScrollHandlers = this._commentScrollHandlers || {};
        if (this._commentScrollHandlers[pid]) return;

        const els = this.getCommentsEls(pid);
        if (!els) return;
        const scroller = els.panelInner || els.list;
        if (!scroller) return;

        let lastTick = 0;
        const throttleMs = 120;
        const handler = () => {
            const now = Date.now();
            if (now - lastTick < throttleMs) return;
            lastTick = now;
            if (this.state.currentPostId !== pid) return;
            const cur = this.state.commentCursor[pid];
            if (!cur) return;
            if (this.state.commentLoadingMore[pid]) return;
            const near = (scroller.scrollTop + scroller.clientHeight) >= (scroller.scrollHeight - 160);
            if (!near) return;
            this.loadMoreComments(pid);
        };

        this._commentScrollHandlers[pid] = handler;
        scroller.addEventListener('scroll', handler, { passive: true });
    },

    loadMoreComments: async function(postId) {
        const pid = Number(postId || 0);
        if (!pid) return;
        const cursor = this.state.commentCursor[pid];
        if (!cursor) return;
        if (this.state.commentLoadingMore[pid]) return;
        this.state.commentLoadingMore[pid] = true;

        try {
            const url = `/api/v1/interaction/comments/${pid}?limit=80&cursor=${encodeURIComponent(cursor)}`;
            const res = await this.apiRequest('GET', url);
            const nextCursor = res.headers ? res.headers.get('x-next-cursor') : null;
            const comments = await res.json();
            const arr = Array.isArray(comments) ? comments : [];
            if (arr.length > 0) this.appendComments(pid, arr);
            this.state.commentCursor[pid] = nextCursor || null;
        } catch (_) {
        } finally {
            this.state.commentLoadingMore[pid] = false;
        }
    },

    updateVideoRightInsetFromComments: function(postId) {
        return;
    },

    closeComments: function() {
        const id = this.state.currentPostId;
        const stage = this.state.currentCommentsStageEl || null;
        if (!id) return;
        this._closeCommentsFor(id, stage);
        this.state.currentPostId = null;
        this.state.currentCommentsStageEl = null;
        this.state.commentReplyToId = null;
        this.state.commentReplyToNickname = null;
    },

    _closeCommentsFor: function(postId, stageEl) {
        const els = this.getCommentsEls(postId, stageEl);
        if (els && els.stage) els.stage.classList.remove('comments-open');
        document.body.classList.remove('comments-open');
    },

    getCommentsEls: function(postId, stageEl) {
        const stage = stageEl || document.getElementById(`stage-${postId}`);
        if (!stage) return null;
        const panelInner = stage.querySelector('.comments-side-inner');
        const list = stage.querySelector('.comments-list');
        const countEl = stage.querySelector('.comments-count');
        const replyBar = stage.querySelector('.comments-reply-bar');
        const replyText = stage.querySelector('.comments-reply-text');
        const input = stage.querySelector('.comments-input');
        return { stage, panelInner, list, countEl, replyBar, replyText, input };
    },

    reactComment: async function(commentId, reaction, el) {
        if (!this.state.user) return this.openModal('authModal');
        try {
            const res = await this.apiRequest(
                'POST',
                '/api/v1/interaction/comment/react',
                { comment_id: commentId, user_id: this.state.user.id, reaction },
                { cancel_key: `cmt:react:${commentId}` }
            );
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const d = (data && data.detail) ? data.detail : (data && data.message) ? data.message : '操作失败';
                this.toast(typeof d === 'string' ? d : '操作失败');
                return;
            }

            const row = el ? el.closest('.comment-actions-row') : null;
            if (row) {
                const likeEl = row.querySelector('.c-like-count');
                const dislikeEl = row.querySelector('.c-dislike-count');
                const lc = Number.isFinite(Number(data.likes_count)) ? Number(data.likes_count) : null;
                const dc = Number.isFinite(Number(data.dislikes_count)) ? Number(data.dislikes_count) : null;
                if (likeEl && lc != null) likeEl.innerText = String(lc);
                if (dislikeEl && dc != null) dislikeEl.innerText = String(dc);
            }
        } catch (e) {}
    },

    clearCommentReply: function() {
        this.state.commentReplyToId = null;
        this.state.commentReplyToNickname = null;

        const postId = this.state.currentPostId;
        if (!postId) return;
        const els = this.getCommentsEls(postId);
        if (!els) return;

        if (els.replyBar) els.replyBar.style.display = 'none';
        if (els.replyText) els.replyText.innerText = '';
        if (els.input) els.input.placeholder = '善语结善缘，恶语伤人心';
    },
    
    replyComment: function(id, nickname) {
        this.state.commentReplyToId = id;
        this.state.commentReplyToNickname = nickname;

        const postId = this.state.currentPostId;
        if (!postId) return;
        const els = this.getCommentsEls(postId);
        if (!els) return;

        if (els.replyBar && els.replyText) {
            els.replyBar.style.display = 'flex';
            els.replyText.innerText = `回复 @${nickname}`;
        }
        if (els.input) {
            els.input.placeholder = `回复 @${nickname}...`;
            els.input.focus();
        }
    },
    
    fmtTimeAgo: function(ts) {
        if (!ts) return '';
        const date = new Date(ts);
        const now = new Date();
        const diff = (now - date) / 1000;
        if (diff < 60) return '刚刚';
        if (diff < 3600) return Math.floor(diff/60) + '分钟前';
        if (diff < 86400) return Math.floor(diff/3600) + '小时前';
        return Math.floor(diff/86400) + '天前';
    },

    formatPostDesc: function(text) {
        const s = String(text || '');
        const idx = s.toLowerCase().lastIndexOf('tags:');
        if (idx === -1) return s;
        const head = s.slice(0, idx).trim();
        const tail = s.slice(idx + 5).trim();
        const tags = tail.split(/[\s,，#]+/).filter(Boolean).slice(0, 12);
        const hashtag = tags.map(t => `#${t}`).join(' ');
        return `${head}${hashtag ? ` ${hashtag}` : ''}`.trim();
    },

    sendDanmaku: function(postId, text) {
        if (!text) return;
        const slide = document.getElementById(`slide-${postId}`);
        if (!slide) return;
        const video = slide.querySelector('video');
        const ts = video ? video.currentTime : 0;

        this.spawnDanmaku(slide, text);
        const input = document.getElementById(`dm-input-${postId}`);
        if (input) input.value = '';

        if (this.state.user) {
            this.apiRequest(
                'POST',
                '/api/v1/interaction/danmaku',
                { post_id: postId, user_id: this.state.user.id, content: text, timestamp: ts },
                { cancel_key: `dm:${postId}` }
            ).then(async (res) => {
                if (!res || !res.ok) return;
                this.loadDanmaku(postId, true);
            }).catch(() => {});
        }
    },

    loadDanmaku: async function(postId, force = false) {
        if (!force && Array.isArray(this.state.danmakuCache[postId])) return;
        try {
            const url = `/api/v1/interaction/danmaku/${postId}`;
            const res = await this.apiRequest('GET', url, undefined, { cancel_key: `dm:load:${postId}`, dedupe_key: url });
            const list = await res.json();
            const sorted = Array.isArray(list) ? list.slice().sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0)) : [];
            this.state.danmakuCache[postId] = sorted;
            this.state.danmakuCursor[postId] = 0;
        } catch(e) {
            this.state.danmakuCache[postId] = [];
            this.state.danmakuCursor[postId] = 0;
        }
    },

    tickDanmaku: function(postId, currentTime, slide) {
        const list = this.state.danmakuCache[postId];
        if (!Array.isArray(list) || list.length === 0) return;
        let idx = this.state.danmakuCursor[postId] || 0;
        while (idx < list.length && (list[idx].timestamp || 0) <= currentTime) {
            const content = list[idx].content;
            if (content) this.spawnDanmaku(slide, content);
            idx += 1;
        }
        this.state.danmakuCursor[postId] = idx;
    },

    spawnDanmaku: function(slide, text) {
        const container = slide.querySelector('.video-player-container');
        if (!container) return;
        const dm = document.createElement('div');
        dm.innerText = text;
        dm.style.position = 'absolute';
        dm.style.top = (Math.random() * 28 + 12) + '%';
        dm.style.right = '-100%';
        dm.style.color = 'rgba(255,255,255,0.92)';
        dm.style.fontSize = '16px';
        dm.style.fontWeight = '600';
        dm.style.whiteSpace = 'nowrap';
        dm.style.textShadow = '0 1px 2px rgba(0,0,0,0.6)';
        dm.style.transition = 'transform 8.5s linear';
        dm.style.zIndex = '15';
        container.appendChild(dm);
        requestAnimationFrame(() => {
            dm.style.transform = 'translateX(-2200px)';
        });
        setTimeout(() => dm.remove(), 9000);
    },

    postComment: async function() {
        const postId = this.state.currentPostId;
        if (!postId) return;
        const els = this.getCommentsEls(postId);
        const input = els ? els.input : null;
        const content = input ? String(input.value || '').trim() : '';
        
        if (!content) return;
        if (!this.state.user) return this.openModal('authModal');
        
        try {
            const res = await this.apiRequest(
                'POST',
                '/api/v1/interaction/comment',
                {
                    post_id: postId,
                    user_id: this.state.user.id,
                    content: content,
                    parent_id: this.state.commentReplyToId
                },
                { cancel_key: `cmt:post:${postId}` }
            );
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                const d = (data && data.detail) ? data.detail : (data && data.message) ? data.message : '发送失败';
                this.toast(typeof d === 'string' ? d : '发送失败');
                return;
            }
            input.value = '';
            this.clearCommentReply();
            this.openComments(postId);
        } catch(e) {
            const msg = e && e.message ? String(e.message) : '发送失败';
            this.toast(msg);
        }
    },

});
