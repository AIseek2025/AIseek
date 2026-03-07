Object.assign(window.app, {
    openModal: function(id, arg) {
        // Auth Guards
        if (['settingsModal', 'passwordModal', 'creatorModal'].includes(id)) {
            if (!this.state.user) {
                return this.openModal('authModal');
            }
        }
        
        const el = document.getElementById(id);
        if (el) {
            el.classList.add('active'); 
            if (id === 'notificationModal') this.loadNotifications();
            if (id === 'messageModal') this.loadDMConversations();
            // If friend list
            if (id === 'friendListModal') { /* load friends */ }
        } else {
            console.warn(`Modal element not found: ${id}`);
        }
    },
    closeModal: function(id) {
        const el = document.getElementById(id);
        if (el) el.classList.remove('active');
        if (id === 'commentsModal') document.body.classList.remove('comments-open');
        if (id === 'messageModal') {
            if (this.state.dmPollTimer) clearInterval(this.state.dmPollTimer);
            this.state.dmPollTimer = null;
        }
    },

    sharePost: async function(postId) {
        const id = Number(postId || 0);
        if (!id) return;
        const url = `${location.origin}/#/v/${id}`;
        try {
            if (navigator.share) {
                try {
                    await navigator.share({ title: 'AIseek', url });
                    return;
                } catch (_) {
                }
            }
        } catch (_) {
        }
        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(url);
                this.toast('链接已复制');
                return;
            }
        } catch (_) {
        }
        try {
            const ta = document.createElement('textarea');
            ta.value = url;
            ta.style.position = 'fixed';
            ta.style.left = '-9999px';
            ta.style.top = '-9999px';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            ta.remove();
            this.toast('链接已复制');
        } catch (_) {
            this.toast(url);
        }
    },

    downloadPost: async function(postId) {
        const id = Number(postId || 0);
        if (!id) return;
        try {
            const res = await this.apiRequest('GET', `/api/v1/posts/${id}/download`, undefined, { cancel_key: `post:dl:${id}` });
            let data = null;
            try { data = await res.json(); } catch (_) { data = null; }
            if (!res.ok) {
                const d = data && data.detail ? data.detail : (data || '');
                const msg = typeof d === 'string' ? d : '下载不可用';
                if (msg === 'download_disabled') return this.toast('作者未开放下载');
                if (msg === 'not_ready') return this.toast('作品尚未生成完成，暂不可下载');
                if (msg === 'missing_media' || msg === 'missing_mp4') return this.toast('没有可下载的文件');
                this.toast(msg);
                return;
            }
            if (data && data.kind === 'image_text' && Array.isArray(data.files) && data.files.length > 0) {
                const ok = confirm(`将下载${data.files.length}张图片，是否继续？`);
                if (!ok) return;
                data.files.slice(0, 30).forEach((u, i) => {
                    setTimeout(() => {
                        try {
                            const a = document.createElement('a');
                            a.href = String(u);
                            a.target = '_blank';
                            a.rel = 'noopener';
                            a.click();
                        } catch (_) {
                        }
                    }, 160 * i);
                });
                this.toast('已开始下载');
                return;
            }
            const url = data && data.url ? String(data.url) : '';
            if (!url) return this.toast('没有可下载的文件');
            try {
                const a = document.createElement('a');
                a.href = url;
                a.target = '_blank';
                a.rel = 'noopener';
                if (data && data.filename) a.download = String(data.filename);
                document.body.appendChild(a);
                a.click();
                a.remove();
            } catch (_) {
                window.open(url, '_blank');
            }
        } catch (_) {
            this.toast('下载失败');
        }
    },
    deletePost: async function(postId, el) {
        const id = Number(postId || 0) || 0;
        if (!id) return;
        const uid = this.state && this.state.user ? Number(this.state.user.id || 0) : 0;
        if (!uid) return this.openModal('authModal');
        if(!confirm('确定删除吗？')) return;
        try {
            const res = await this.apiRequest('DELETE', `/api/v1/posts/${id}`, undefined, { cancel_key: `post:delete:${id}` });
            if (!res || !res.ok) return this.toast('删除失败');
            try {
                const card = el && el.closest ? el.closest('.p-card') : null;
                if (card && card.parentNode) card.parentNode.removeChild(card);
            } catch (_) {
            }
            try {
                const n = document.querySelectorAll('#p-content .p-card').length;
                const worksEl = document.getElementById('p-count-works');
                if (worksEl) worksEl.innerText = String(n);
            } catch (_) {
            }
            try {
                if (this.state && this.state.viewingUser && this.state.viewingUser.user && Number(this.state.viewingUser.user.id) === uid) {
                    const tab = String(this.state.currentProfileTab || '');
                    if (tab === 'works' && typeof this.switchProfileTab === 'function') {
                        this.switchProfileTab('works');
                    } else {
                        this.loadProfile(uid);
                    }
                } else {
                    this.switchTab('profile');
                }
            } catch (_) {
                this.switchTab('profile');
            }
        } catch(e) {}
    },

    renderShortcutRow: function(label, key) {
        return `
            <div style="display:flex; align-items:center; justify-content:space-between; padding:10px 14px; border-radius:8px; background:rgba(255,255,255,0.05);">
                <span style="font-size:13px; color:rgba(255,255,255,0.8);">${label}</span>
            </div>
            <div style="display:flex; align-items:center; justify-content:center; padding:0 10px; border-radius:8px; background:rgba(255,255,255,0.1); font-family:monospace; font-weight:600; font-size:14px;">
                ${key}
            </div>
        `;
    },

    formatPostDesc: function(text) {
        if (!text) return '';
        return text.length > 60 ? text.slice(0, 60) + '...' : text;
    },

    fmtTimeAgo: function(timestamp) {
        if (!timestamp) return '';
        const now = Date.now();
        const diff = now - timestamp;
        const minute = 60 * 1000;
        const hour = 60 * minute;
        const day = 24 * hour;
        const month = 30 * day;
        const year = 365 * day;

        if (diff < minute) return '刚刚';
        if (diff < hour) return Math.floor(diff / minute) + '分钟前';
        if (diff < day) return Math.floor(diff / hour) + '小时前';
        if (diff < month) return Math.floor(diff / day) + '天前';
        if (diff < year) return Math.floor(diff / month) + '个月前';
        return Math.floor(diff / year) + '年前';
    },

    toast: function(text) {
        const msg = String(text || '').trim();
        if (!msg) return;
        let wrap = document.getElementById('aiseek_toast_wrap');
        if (!wrap) {
            wrap = document.createElement('div');
            wrap.id = 'aiseek_toast_wrap';
            wrap.style.position = 'fixed';
            wrap.style.left = '50%';
            wrap.style.bottom = '22px';
            wrap.style.transform = 'translateX(-50%)';
            wrap.style.zIndex = '9999';
            wrap.style.display = 'flex';
            wrap.style.flexDirection = 'column';
            wrap.style.gap = '10px';
            wrap.style.pointerEvents = 'none';
            document.body.appendChild(wrap);
        }
        const el = document.createElement('div');
        el.style.maxWidth = '72vw';
        el.style.padding = '10px 14px';
        el.style.borderRadius = '12px';
        el.style.background = 'rgba(0,0,0,0.72)';
        el.style.border = '1px solid rgba(255,255,255,0.12)';
        el.style.color = 'rgba(255,255,255,0.92)';
        el.style.fontSize = '13px';
        el.style.fontWeight = '600';
        el.style.boxShadow = '0 12px 48px rgba(0,0,0,0.55)';
        el.style.opacity = '0';
        el.style.transform = 'translateY(8px)';
        el.style.transition = 'opacity 0.18s ease, transform 0.18s ease';
        el.innerText = msg;
        wrap.appendChild(el);
        requestAnimationFrame(() => {
            el.style.opacity = '1';
            el.style.transform = 'translateY(0)';
        });
        setTimeout(() => {
            el.style.opacity = '0';
            el.style.transform = 'translateY(8px)';
            setTimeout(() => {
                try { el.remove(); } catch (_) {}
            }, 220);
        }, 1400);
    },

    showJxPopup: function(post, targetEl) {
        if (this._jxHideTimer) {
            clearTimeout(this._jxHideTimer);
            this._jxHideTimer = null;
        }
        
        if (this._jxPopupPostId === post.id) return;
        this._jxPopupPostId = post.id;

        const isVideo = (post.post_type === 'video') || (post.video_url && !(/\.(jpg|jpeg|png|gif|webp)(\?|#|$)/i.test(post.video_url)));
        if (!isVideo) return;
        this._jxPopupUsingFloating = true;
        try {
            this.openFloatingPlayer(post.id, { preset: 'jx', anchorEl: targetEl, forcePlay: true });
        } catch (_) {
        }
    },

    showJxPopupById: function(postId, targetEl) {
        try {
            if (typeof this.findPostById === 'function') {
                const p = this.findPostById(postId);
                if (p) return this.showJxPopup(p, targetEl);
            }
        } catch (_) {
        }
    },

    hideJxPopup: function() {
        if (this._jxHideTimer) clearTimeout(this._jxHideTimer);
        this._jxHideTimer = setTimeout(() => {
            if (!this._jxPopupUsingFloating) return;
            const wrap = document.getElementById('floating_player');
            if (wrap && typeof wrap.matches === 'function' && wrap.matches(':hover')) return;
            if (Number(this.state.floatingPostId || 0) !== Number(this._jxPopupPostId || 0)) return;
            this.closeFloatingPlayer();
            this._jxPopupPostId = null;
            this._jxPopupUsingFloating = false;
        }, 300); // Small delay to allow moving mouse to popup
    },
    
    toggleJxMute: function(btn) {
        const pop = document.getElementById('jx_hover_popup');
        if (!pop) return;
        const v = pop.querySelector('video');
        if (v) {
            v.muted = !v.muted;
            this.state.isMuted = v.muted;
            localStorage.setItem('is_muted', v.muted ? '1' : '0');
            const i = btn.querySelector('i');
            if (i) i.className = v.muted ? 'fas fa-volume-mute' : 'fas fa-volume-up';
        }
    }
});
