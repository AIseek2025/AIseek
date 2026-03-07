Object.assign(window.app, {
    parseTags: function(raw) {
        const s = String(raw || '');
        const parts = s.split(/[,，]+/).map(x => String(x || '').trim()).filter(Boolean);
        const out = [];
        for (const p0 of parts) {
            const p1 = p0.replace(/^#+/, '').replace(/[\r\n\t]+/g, ' ').replace(/\s{2,}/g, ' ').trim();
            if (!p1) continue;
            out.push(p1);
            if (out.length >= 12) break;
        }
        return out;
    },

    creatorSelectTab: function(tab) {
        const tabManual = document.getElementById('creator_tab_manual');
        const tabAi = document.getElementById('creator_tab_ai');
        if (!tabManual && !tabAi) return;
        // Toggle tabs
        if (tabManual) tabManual.className = `creator-tab2 ${tab === 'manual' ? 'active' : ''}`;
        if (tabAi) tabAi.className = `creator-tab2 ${tab === 'ai' ? 'active' : ''}`;

        const grid = document.querySelector('#page-creator .creator-grid');
        const manualCard = document.getElementById('creator_card_manual');
        const aiReqCard = document.getElementById('creator_card_ai_required');
        const aiOptCard = document.getElementById('creator_card_ai_optional');
        if (grid) grid.classList.toggle('ai-mode', tab === 'ai');
        if (manualCard) manualCard.style.display = tab === 'manual' ? 'block' : 'none';
        if (aiReqCard) aiReqCard.style.display = tab === 'ai' ? 'block' : 'none';
        if (aiOptCard) aiOptCard.style.display = tab === 'ai' ? 'block' : 'none';
        
        // Adjust media area if needed (e.g. AI mode might not need media preview or different one)
        // For now keep media area for manual, maybe hide for AI or show AI progress?
        // User requirement: "AI input long text... upload cover (optional)..."
        // The media area is currently shared. Let's reset it or adapt it.
        const mediaBox = document.getElementById('creator_media');
        if (tab === 'ai') {
             // In AI mode, media box could show "AI Preview" or just static image
             mediaBox.innerHTML = `
                <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%; color:rgba(255,255,255,0.5);">
                    <i class="fas fa-robot" style="font-size:48px; margin-bottom:16px;"></i>
                    <div>AI 创作模式</div>
                    <div style="font-size:12px; margin-top:8px;">填写中间必选项与右侧选填项</div>
                </div>
             `;
        } else {
            // Restore Manual Upload
            // If files exist, render them
            if (this.state.manualFiles && this.state.manualFiles.length > 0) {
                this.renderManualPreview();
            } else {
                this.creatorClearManual();
            }
        }
    },

    setAIGenType: function(type) {
        this.state.aiGenType = type;
        const a = document.getElementById('ai_type_image');
        const b = document.getElementById('ai_type_video');
        if (a && b) {
            a.classList.toggle('active', type === 'image_text');
            b.classList.toggle('active', type === 'video');
        }
    },

    creatorSubmitManual: async function() {
        if (!this.state.manualFiles || this.state.manualFiles.length === 0) return alert('请先上传图片或视频');
        if (!this.state.user) return this.openModal('authModal');

        try {
            if (window.appEmit && window.appEventNames) {
                window.appEmit(window.appEventNames.TASK_STATE, { task: 'creator:manual_submit', status: 'start' });
            }
        } catch (_) {
        }
        
        try {
            // 1. Upload Files
            const fileKeys = [];
            const isVideo = this.state.manualFiles[0].type.startsWith('video');
            
            // Show loading
            const btn = document.querySelector('.creator-actions .btn-primary');
            if(btn) { btn.innerText = '发布中...'; btn.disabled = true; }

            // Upload sequentially
            for (const file of this.state.manualFiles) {
                const formData = new FormData();
                formData.append('file', file);
                
                // Use local upload endpoint
                const res = await this.apiRequest('POST', '/api/v1/upload/local', formData, { cancel_key: 'creator:upload' });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) {
                    const d = data && (data.detail || data.message) ? (data.detail || data.message) : `Upload failed (${res.status})`;
                    throw new Error(typeof d === 'string' ? d : 'Upload failed');
                }
                if (data.key) fileKeys.push(data.key);
            }
            
            if (fileKeys.length === 0) throw new Error('Upload failed');
            
            // 2. Create Post
            const title = document.getElementById('c_title').value;
            const desc = document.getElementById('c_desc').value;
            const category = document.getElementById('c_category').value;
            const tags = document.getElementById('c_tags').value;
            const tagList = this.parseTags(tags);
            const tagText = tagList.map(t => `#${t}`).join(' ');
            
            const payload = {
                user_id: this.state.user.id,
                title: title,
                content: desc + (tagText ? `\n\n${tagText}` : ''),
                category: category,
                post_type: isVideo ? 'video' : 'image_text'
            };
            
            if (isVideo) {
                payload.file_key = fileKeys[0];
            } else {
                payload.images = fileKeys;
            }
            
            const res2 = await this.apiRequest('POST', '/api/v1/posts/create', payload, { cancel_key: 'creator:manual:create' });
            
            if (res2.ok) {
                try {
                    if (window.appEmit && window.appEventNames) {
                        window.appEmit(window.appEventNames.TASK_STATE, { task: 'creator:manual_submit', status: 'success' });
                    }
                } catch (_) {
                }
                this.creatorClearManual();
                this.viewUserProfile(this.state.user.id);
                setTimeout(() => this.switchProfileTab('works'), 0);
            } else {
                const err = await res2.json().catch(() => ({}));
                const d = err && (err.detail || err.message) ? (err.detail || err.message) : '未知错误';
                alert('发布失败: ' + (typeof d === 'string' ? d : JSON.stringify(d)));
                try {
                    if (window.appEmit && window.appEventNames) {
                        window.appEmit(window.appEventNames.TASK_STATE, { task: 'creator:manual_submit', status: 'error' });
                    }
                } catch (_) {
                }
            }
            
        } catch(e) {
            console.error(e);
            alert('发布出错: ' + e.message);
            try {
                if (window.appEmit && window.appEventNames) {
                    window.appEmit(window.appEventNames.TASK_STATE, { task: 'creator:manual_submit', status: 'error' });
                }
            } catch (_) {
            }
        } finally {
            const btn = document.querySelector('.creator-actions .btn-primary');
            if(btn) { btn.innerText = '发布作品'; btn.disabled = false; }
        }
    },

    creatorPickAICover: function(input) {
        this.state.aiCoverFile = (input && input.files && input.files[0]) ? input.files[0] : null;
    },
    
    creatorPickAIIllus: function(input) {
        this.state.aiIllusFiles = (input && input.files) ? Array.from(input.files) : [];
    },

    creatorSubmitAI: async function() {
        if (!this.state.user) return this.openModal('authModal');

        const longText = (document.getElementById('ai_long')?.value || '').trim();
        if (!longText) return alert('请填写长文（必填）');
        if (!this.state.aiGenType) return alert('请选择生成图文或生成视频（必选）');

        const title = (document.getElementById('ai_title')?.value || '').trim();
        const desc = (document.getElementById('ai_desc')?.value || '').trim();
        const tags = (document.getElementById('ai_tags')?.value || '').trim();
        const category = (document.getElementById('ai_category')?.value || '').trim();
        const req = (document.getElementById('ai_req')?.value || '').trim();

        const tagList = this.parseTags(tags);
        const tagText = tagList.map(t => `#${t}`).join(' ');
        const content = longText + (desc ? `\n\n${desc}` : '') + (tagText ? `\n\n${tagText}` : '');

        const btn = event?.target;
        if (btn) { btn.innerText = '提交中...'; btn.disabled = true; }

        try {
            if (window.appEmit && window.appEventNames) {
                window.appEmit(window.appEventNames.TASK_STATE, { task: 'creator:ai_submit', status: 'start' });
            }
        } catch (_) {
        }
        
        try {
            const res = await this.apiRequest('POST', '/api/v1/ai/submit', {
                user_id: this.state.user.id,
                title: title || null,
                content: content,
                category: category || null,
                post_type: this.state.aiGenType,
                custom_instructions: req || null
            }, { cancel_key: 'creator:ai:submit' });
            const data = await res.json().catch(() => ({}));
            
            if (!res.ok) {
                const msg = (data && data.detail) ? data.detail : '提交失败';
                throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
            }
            this.viewUserProfile(this.state.user.id);
            setTimeout(() => this.switchProfileTab('works'), 0);

            try {
                if (window.appEmit && window.appEventNames) {
                    window.appEmit(window.appEventNames.TASK_STATE, { task: 'creator:ai_submit', status: 'success' });
                }
            } catch (_) {
            }
            
        } catch(e) {
            console.error(e);
            alert(e.message || '提交失败');
            try {
                if (window.appEmit && window.appEventNames) {
                    window.appEmit(window.appEventNames.TASK_STATE, { task: 'creator:ai_submit', status: 'error' });
                }
            } catch (_) {
            }
        } finally {
            if (btn) { btn.innerText = '提交AI创作'; btn.disabled = false; }
        }
    },

});
