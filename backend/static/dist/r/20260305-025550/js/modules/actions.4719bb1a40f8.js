(function () {
    if (window.__aiseekActionDispatcher) return;
    window.__aiseekActionDispatcher = true;

    const safeJson = (s, fallback) => {
        try {
            if (!s) return fallback;
            return JSON.parse(String(s));
        } catch (_) {
            return fallback;
        }
    };

    const asBool = (v) => String(v || '') === '1' || String(v || '').toLowerCase() === 'true';

    const allow = new Set([
        'switchPage',
        'searchUser',
        'renderSearchDropdown',
        'doSearch',
        'searchPreviewPlay',
        'searchPreviewStop',
        'searchCardTogglePlay',
        'searchCardToggleMute',
        'searchCardSetVolume',
        'searchCardFullscreen',
        'searchCardSeek',
        'openInbox',
        'markAllNotificationsRead',
        'logout',
        'openModal',
        'closeModal',
        'switchProfileTab',
        'switchFollowingSubtab',
        'switchSearchTab',
        'switchInboxTab',
        'hoverInboxEnter',
        'hoverInboxLeave',
        'toggleDMMoreMenu',
        'dmToggleDnd',
        'dmTogglePin',
        'dmDeleteChat',
        'dmReportChat',
        'dmBlockUser',
        'dmInsertEmoji',
        'dmInputKeydown',
        'dmToggleEmojiPanel',
        'dmRenderEmojiPanel',
        'dmPickEmoji',
        'dmPickImage',
        'showJxPopupById',
        'hideJxPopup',
        'dmSearchUsers',
        'switchFollowModalTab',
        'closeSearchPage',
        'creatorSelectTab',
        'creatorClearManual',
        'creatorPrev',
        'creatorNext',
        'creatorSubmitManual',
        'setAIGenType',
        'creatorSubmitAI',
        'cancelAIJob',
        'reviseAIJob',
        'openAIDraftEditor',
        'openAIAppealModal',
        'submitAIAppeal',
        'openAIChatModal',
        'sendAIChatMessage',
        'submitAIChatRevision',
        'requestAIChatSuggestion',
        'settingsSelect',
        'changePasswordInSettings',
        'openBgPicker',
        'renderBgPickerGrid',
        'bgPickerSelect',
        'bgPickerConfirm',
        'login',
        'register',
        'saveProfile',
        'fillEditForm',
        'switchAuthTab',
        'openDMThreadFromInput',
        'sendDMMessage',
        'setInboxNotifyFilter',
        'sendInboxDMMessage',
        'handleFriendRequest',
        'viewUserProfile',
        'openPost',
        'toggleFollow',
        'toggleLike',
        'openComments',
        'toggleFavorite',
        'openFloatingPlayer',
        'sendDanmaku',
        'playPrev',
        'playNext',
        'friendFeedPrev',
        'friendFeedNext',
        'setQuality',
        'closeComments',
        'clearCommentReply',
        'postComment',
        'deletePost',
        'startChat',
        'openFollowModal',
        'setLanguage',
        'setTheme',
        'updateContactInSettings',
        'clearSearchHistory',
        'sendFriendRequest',
        'loadProfile',
        'filterFollowPageList',
        'filterFriendsList',
        'loadUserWorkInMainPanel',
        'openComments',
        'replyComment',
        'reactComment',
        'toggleRepost',
        'sharePost',
        'downloadPost',
        'openDMThread',
        'openInboxDMThread',
        'loadInboxDMThread',
        'togglePlayByPostId',
        'seekByPostId',
        'toggleGlobalMute',
        'toggleFullscreenByPostId',
        'setPlaybackSpeedByEl',
        'toggleAutoPlay',
        'toggleCleanMode',
        'handleStageClick',
        'handleStageDblClick',
        'floatingTogglePlay',
        'floatingToggleMute',
        'floatingClose',
        'floatingToggleFullscreen',
        'floatingClick',
        'floatingDblClick',
        'toggleFloatingPlayerSize',
        'floatingToggleSize',
        'setJingxuanCategory',
        'switchTab',
        'adminLogout',
        'adminLogin',
        'loadUsers',
        'loadContent',
        'loadAITasks',
        'loadAudit',
        'adminReviewDecision',
        'switchTab',
        'adminLogout',
        'adminLogin',
        'loadUsers',
        'loadContent',
        'loadAITasks',
        'loadAudit',
        'loadSystem',
        'loadAssetReleases',
        'activateAssetRelease',
        'loadAssetsRollout',
        'saveAssetsRollout',
        'runAssetsRolloutGuard',
        'loadFeedRecallConfig',
        'saveFeedRecallConfig',
        'exportWorkerCallbackSamples',
        'exportWorkerCallbackAlerts',
        'saveWorkerCallbackThresholds',
        'ackWorkerCallbackAlert',
        'ackFilteredWorkerCallbackAlerts',
        'ackTodayWorkerCallbackAlerts',
        'adminBanUser',
        'adminUnbanUser',
        'adminSetReputation',
        'adminBulkBanUsers',
        'adminRemovePost',
        'adminDeletePost',
        'adminBulkRemove',
        'loadUserHoverStats',
        'showJxPopupById',
        'hideJxPopup',
        'profilePreviewPlay',
        'profilePreviewStop',
        'setGlobalVolumeFromEl',
        'seekStartByPostId',
        'seekMoveByPostId',
        'seekEndByPostId',
        'seekCancelByPostId',
        'floatingDragStart',
        'floatingDragMove',
        'floatingDragEnd',
        'floatingDragCancel',
        'floatingSeekStart',
        'floatingSeekMove',
        'floatingSeekEnd',
        'floatingSeekCancel',
        'floatingResizeStart',
        'floatingResizeMove',
        'floatingResizeEnd',
        'floatingResizeCancel',
        'clampFloatingPlayer'
    ]);

    const emit = (name, payload) => {
        try {
            if (window.appEmit) window.appEmit(name, payload || {});
            else if (window.appEvents && typeof window.appEvents.emit === 'function') window.appEvents.emit(String(name || ''), payload || {});
        } catch (_) {
        }
    };

    const callApp = (fn, args) => {
        const app = window.app;
        if (!app) return;
        const name = String(fn || '');
        if (!name || !allow.has(name)) return;
        const f = app[name];
        if (typeof f !== 'function') return;
        return f.apply(app, Array.isArray(args) ? args : []);
    };

    const actions = {
        call: (el, ev) => {
            const type = ev && ev.type ? String(ev.type) : '';
            const cap = type ? (type[0].toUpperCase() + type.slice(1)) : '';
            const fnKey = cap ? `fn${cap}` : 'fn';
            const argsKey = cap ? `args${cap}` : 'args';
            const passElKey = cap ? `passEl${cap}` : 'passEl';
            const passValueKey = cap ? `passValue${cap}` : 'passValue';
            const passEventKey = cap ? `passEvent${cap}` : 'passEvent';

            const fn = el.dataset[fnKey] || el.dataset.fn;
            let args = safeJson(el.dataset[argsKey] || el.dataset.args, []);
            if (!Array.isArray(args)) args = [args];
            if (asBool(el.dataset[passElKey]) || asBool(el.dataset.passEl)) {
                const pos = String(el.dataset.elPos || 'end');
                if (pos === '0' || pos === 'start') args.unshift(el);
                else args.push(el);
            }
            if (asBool(el.dataset[passValueKey]) || asBool(el.dataset.passValue)) {
                try { args.push(el.value); } catch (_) { args.push(undefined); }
            }
            if (asBool(el.dataset[passEventKey]) || asBool(el.dataset.passEvent)) args.push(ev);
            return callApp(fn, args);
        },
        click: (el) => {
            const sel = String(el.dataset.target || '');
            if (!sel) return;
            const t = document.querySelector(sel);
            if (t && typeof t.click === 'function') t.click();
        },
        alert: (el) => {
            try { alert(String(el.dataset.message || '')); } catch (_) {}
        },
        profileTab: (el) => {
            const tab = String(el.dataset.tab || '');
            callApp('switchPage', ['profile']);
            setTimeout(() => {
                try { callApp('switchProfileTab', [tab]); } catch (_) {}
            }, 0);
        },
        openEditProfile: () => {
            callApp('openModal', ['editProfileModal']);
            setTimeout(() => {
                try { callApp('fillEditForm', []); } catch (_) {}
            }, 0);
        },
        selectFriend: (el) => {
            const uid = Number(el.dataset.userId || 0);
            const mainSel = String(el.dataset.main || '');
            if (!uid || !mainSel) return;
            try {
                const groupSel = String(el.dataset.group || '');
                const items = groupSel ? document.querySelectorAll(groupSel) : (el.parentElement ? el.parentElement.querySelectorAll('.friend-item') : []);
                Array.from(items).forEach((x) => {
                    try { x.classList.remove('active'); } catch (_) {}
                });
                el.classList.add('active');
            } catch (_) {
            }
            const main = document.querySelector(mainSel);
            if (!main) return;
            return callApp('loadUserWorkInMainPanel', [uid, main]);
        },
        openInboxPeer: (el) => {
            const app = window.app;
            if (!app || !app.state) return;
            const pid = Number(el.dataset.peerId || 0);
            if (!pid) return;
            const mode = String(el.dataset.mode || 'dm');
            const meta = safeJson(el.dataset.peerMeta, null);
            try { app.state.inboxPendingPeer = { id: pid, meta: meta || { id: pid } }; } catch (_) {}
            callApp('openInbox', [mode]);
            const close = String(el.dataset.close || '');
            if (close) callApp('closeModal', [close]);
        },
        callClose: (el, ev) => {
            const r = actions.call(el, ev);
            const close = String(el.dataset.close || '');
            if (close) callApp('closeModal', [close]);
            return r;
        },
        openPostComments: (el) => {
            const pid = Number(el.dataset.postId || 0);
            if (!pid) return;
            const close = String(el.dataset.close || '');
            if (close) callApp('closeModal', [close]);
            callApp('openPost', [pid]);
            setTimeout(() => {
                try { callApp('openComments', [pid]); } catch (_) {}
            }, 300);
        },
        openProfileFromComment: (el) => {
            const uid = Number(el.dataset.userId || 0);
            if (!uid) return;
            try { callApp('closeComments', []); } catch (_) {}
            return callApp('viewUserProfile', [uid]);
        },
        creatorPick: (el, ev) => {
            const app = window.app;
            if (!app) return;
            const target = ev && ev.target ? ev.target : null;
            if (target && target.closest && (target.closest('.creator-media-actions') || target.closest('.creator-nav'))) return;
            const manualTab = document.getElementById('creator_tab_manual');
            if (manualTab && !manualTab.classList.contains('active')) return;
            const input = document.getElementById('creator_files_manual');
            if (input && typeof input.click === 'function') input.click();
        },
        modalBg: (el) => {
            const id = el && el.id ? String(el.id) : '';
            if (!id) return;
            return callApp('closeModal', [id]);
        },
        floatingToggleSize: () => callApp('toggleFloatingPlayerSize', []),
        floatingClick: () => {},
        floatingDblClick: () => callApp('floatingTogglePlay', []),
        stageClick: (el, ev) => {
            const pid = Number(el.dataset.postId || 0);
            if (!pid) return;
            return callApp('handleStageClick', [pid]);
        },
        stageDblClick: (el, ev) => {
            const pid = Number(el.dataset.postId || 0);
            if (!pid) return;
            return callApp('handleStageDblClick', [pid]);
        },
        stop: () => {}
    };

    const dispatch = (ev, key) => {
        try {
            const t = ev && ev.target ? ev.target : null;
            if (!t || !t.closest) return;
            const attr = key === 'click' ? 'data-action' : `data-action-${key}`;
            const el = t.closest(`[${attr}]`);
            if (!el) return;
            if (el.hasAttribute('disabled') || asBool(el.dataset.disabled)) return;

            const prevent = asBool(el.dataset.prevent);
            const actName = key === 'click' ? String(el.dataset.action || '') : String(el.dataset[`action${key[0].toUpperCase() + key.slice(1)}`] || '');
            const isStopAction = actName === 'stop';
            const stop = asBool(el.dataset.stop) || isStopAction;
            const kc = el.dataset.keyCode ? Number(el.dataset.keyCode) : 0;
            const k = el.dataset.key ? String(el.dataset.key) : '';
            if (key === 'mouseover' || key === 'mouseout') {
                const rel = ev && ev.relatedTarget ? ev.relatedTarget : null;
                if (rel && el.contains && el.contains(rel)) return;
            }
            if (key !== 'click') {
                if (kc && Number(ev && ev.keyCode) !== kc) return;
                if (k && String(ev && ev.key) !== k) return;
                if (asBool(el.dataset.noShift) && !!(ev && ev.shiftKey)) return;
            }
            if (prevent) ev.preventDefault();
            if (stop && !isStopAction) ev.stopPropagation();

            const name = actName;
            const fn = actions[name];
            if (typeof fn !== 'function') return;
            const r = fn(el, ev);
            emit('ui:action', { action: name, fn: el.dataset.fn || null });
            return true;
        } catch (e) {
            try {
                if (window.appRuntime && typeof window.appRuntime.reportError === 'function') {
                    window.appRuntime.reportError('ui:action', e, {});
                } else {
                    emit('ui:error', { kind: 'ui:action', message: String((e && e.message) || e || 'error') });
                }
            } catch (_) {
            }
        }
    };

    document.addEventListener('click', (ev) => {
        const handled = dispatch(ev, 'click');
        if (handled) return;
        try {
            const t = ev && ev.target ? ev.target : null;
            if (!t || !t.classList) return;
            if (!t.classList.contains('modal')) return;
            if (!t.id) return;
            callApp('closeModal', [String(t.id)]);
        } catch (_) {
        }
    }, true);
    document.addEventListener('keyup', (ev) => dispatch(ev, 'keyup'), true);
    document.addEventListener('keydown', (ev) => dispatch(ev, 'keydown'), true);
    document.addEventListener('change', (ev) => dispatch(ev, 'change'), true);
    document.addEventListener('input', (ev) => dispatch(ev, 'input'), true);
    document.addEventListener('dblclick', (ev) => dispatch(ev, 'dblclick'), true);
    document.addEventListener('mouseover', (ev) => dispatch(ev, 'mouseover'), true);
    document.addEventListener('mouseout', (ev) => dispatch(ev, 'mouseout'), true);
    document.addEventListener('pointerdown', (ev) => {
        dispatch(ev, 'pointerdown');
        try {
            const app = window.app;
            if (!app || !app.state) return;
            const t = ev && ev.target ? ev.target : null;

            try {
                if (!t || !(t.closest && t.closest('.vol-btn')) || !t) {
                    if (typeof app.hideAllVolumePops === 'function') app.hideAllVolumePops();
                }
            } catch (_) {
            }

            try {
                const dd = document.getElementById('search_hot_dropdown');
                if (dd && dd.classList && dd.classList.contains('active')) {
                    const inSearch = t && t.closest && (t.closest('#search_hot_dropdown') || t.closest('.search-bar'));
                    if (!inSearch) dd.classList.remove('active');
                }
            } catch (_) {
            }

            try {
                if (app.state.currentPostId && document.body.classList.contains('comments-open')) {
                    const stage = document.getElementById(`stage-${app.state.currentPostId}`);
                    const inStage = stage && t && t.closest && t.closest('.video-stage') === stage;
                    if (!inStage && typeof app.closeComments === 'function') app.closeComments();
                }
            } catch (_) {
            }
        } catch (_) {
        }
    }, true);
    document.addEventListener('pointermove', (ev) => dispatch(ev, 'pointermove'), true);
    document.addEventListener('pointerup', (ev) => dispatch(ev, 'pointerup'), true);
    document.addEventListener('pointercancel', (ev) => dispatch(ev, 'pointercancel'), true);
})();
