Object.assign(window.app, {
    bindAuthHotkeys: function() {
        if (this._authHotkeysBound) return;

        const bind = (id, fn) => {
            const el = document.getElementById(id);
            if (!el) return;
            el.addEventListener('keydown', (e) => {
                if (!e) return;
                if (e.key === 'Enter' || e.keyCode === 13) {
                    e.preventDefault();
                    fn();
                }
            });
        };

        bind('auth_u', () => this.login());
        bind('auth_p', () => this.login());
        bind('reg_u', () => this.register());
        bind('reg_p', () => this.register());
        bind('reg_p2', () => this.register());

        this._authHotkeysBound = true;
    },

    ensureAuth: function(action) {
        if (this.state.user) return true;
        this.state.pendingAuthAction = action || null;
        this.openModal('authModal');
        return false;
    },

    runPendingAuthAction: function() {
        const a = this.state.pendingAuthAction;
        this.state.pendingAuthAction = null;
        if (!a) return;
        if (a.type === 'route' && a.page) {
            this.switchPage(a.page);
            return;
        }
        if (a.type === 'open_inbox') {
            const tab = a.tab === 'dm' ? 'dm' : 'notify';
            this.state.inboxTab = tab;
            if (tab === 'dm') this.openModal('messageModal');
            else this.openModal('notificationModal');
            return;
        }
        if (a.type === 'favorite' && a.postId) {
            const icon = document.querySelector(`#slide-${a.postId} .fa-star`);
            const btn = icon && icon.closest ? icon.closest('.action-item') : null;
            this.toggleFavorite(a.postId, btn);
            return;
        }
        if (a.type === 'like' && a.postId) {
            const icon = document.querySelector(`#slide-${a.postId} .fa-heart`);
            const btn = icon && icon.closest ? icon.closest('.action-item') : null;
            this.toggleLike(a.postId, btn);
            return;
        }
        if (a.type === 'repost' && a.postId) {
            const icon = document.querySelector(`#slide-${a.postId} .fa-retweet`);
            const btn = icon && icon.closest ? icon.closest('.action-item') : null;
            this.toggleRepost(a.postId, btn);
            return;
        }
        if (a.type === 'open_modal' && a.id) {
            this.openModal(a.id);
            return;
        }
    },

    switchAuthTab: function(tab) {
        document.querySelectorAll('.auth-tab').forEach(el => {
            el.classList.remove('active');
            el.style.color = '#888';
            el.style.borderBottom = 'none';
        });
        const active = document.getElementById(`tab-${tab}`);
        active.classList.add('active');
        active.style.color = 'var(--primary-color)';
        active.style.borderBottom = '2px solid var(--primary-color)';
        
        document.getElementById('form-login').style.display = tab === 'login' ? 'block' : 'none';
        document.getElementById('form-register').style.display = tab === 'register' ? 'block' : 'none';
    },

    login: async function() {
        const u = document.getElementById('auth_u').value;
        const p = document.getElementById('auth_p').value;
        if(!u || !p) return alert('请输入用户名和密码');

        const btn = document.querySelector('#form-login button');
        btn.innerText = '登录中...'; btn.disabled = true;

        try {
            const res = await this.apiRequest('POST', '/api/v1/auth/login', { username: u, password: p }, { cancel_key: 'auth:login' });
            
            if (res.ok) {
                const data = await res.json();
                
                // Save token
                localStorage.setItem('token', data.access_token);
                localStorage.setItem('user_id', data.user_id);
                localStorage.setItem('username', data.username);
                
                // Fetch profile
                await this.fetchCurrentUser(data.user_id);
                
                // Add delay to ensure state update
                await new Promise(r => setTimeout(r, 100));

                if (this.state.user) {
                    this.closeModal('authModal');
                    this.updateAuthUI();
                    this.runPendingAuthAction();
                    // alert('登录成功'); // Removed per user request
                } else {
                    console.error("Login failed: State user is null after fetch");
                    alert('登录成功但获取用户信息失败，请尝试刷新页面');
                    location.reload();
                }
            } else {
                const err = await res.json();
                alert('登录失败: ' + (err.detail || '用户名或密码错误'));
            }
        } catch(e) { console.error(e); alert('登录请求错误'); }
        finally { btn.innerText = '登录'; btn.disabled = false; }
    },

    register: async function() {
        const u = document.getElementById('reg_u').value;
        const p = document.getElementById('reg_p').value;
        const p2 = document.getElementById('reg_p2').value;
        
        if(!u || !p) return alert('请输入用户名和密码');
        if(p !== p2) return alert('两次密码输入不一致');
        
        const btn = document.querySelector('#form-register button');
        btn.innerText = '注册中...'; btn.disabled = true;
        
        try {
            const res = await this.apiRequest('POST', '/api/v1/auth/register', { username: u, password: p }, { cancel_key: 'auth:register' });
            
            if (res.ok) {
                // Auto login directly
                const loginRes = await this.apiRequest('POST', '/api/v1/auth/login', { username: u, password: p }, { cancel_key: 'auth:login' });
                
                if (loginRes.ok) {
                    const data = await loginRes.json();
                    
                    // Save token
                    localStorage.setItem('token', data.access_token);
                    localStorage.setItem('user_id', data.user_id);
                    localStorage.setItem('username', data.username);
                    
                    // Fetch profile
                    await this.fetchCurrentUser(data.user_id);
                    
                    // Add delay to ensure state update
                    await new Promise(r => setTimeout(r, 100));

                    if (this.state.user) {
                        this.closeModal('authModal');
                        this.updateAuthUI();
                        this.runPendingAuthAction();
                        alert('注册成功，已为您自动登录');
                    } else {
                        console.error("Login failed: State user is null after fetch");
                        alert('注册成功但获取用户信息失败，请尝试刷新页面');
                        location.reload();
                    }
                } else {
                    alert('注册成功，请手动登录');
                    this.switchAuthTab('login');
                }
            } else {
                const err = await res.json();
                alert('注册失败: ' + (err.detail || '用户名可能已存在'));
            }
        } catch(e) { console.error(e); alert('注册请求错误'); }
        finally { btn.innerText = '立即注册'; btn.disabled = false; }
    },

    logout: function() {
        localStorage.clear();
        location.reload();
    },

});
