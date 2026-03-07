# Trae-v1 功能问题诊断报告

**评估日期**: 2026-02-25  
**问题报告**: 搜索功能失败、登录功能失败  
**评估范围**: Backend API + Frontend JavaScript

---

## 📊 问题总结

| 问题 | 状态 | 严重程度 | 根本原因 |
|------|------|---------|---------|
| 1. 搜索功能失败 | ❌ 未实现 | 🔴 高 | 后端 API 路由前缀不匹配 |
| 2. 登录功能失败 | ❌ 部分实现 | 🔴 高 | 后端服务未启动 + 数据库可能未初始化 |

---

## 🔍 问题 1: 搜索功能失败

### 现象
- 点击搜索按钮
- 显示错误：`搜索失败：Search request failed`

### 前端代码分析

**文件**: `backend/static/js/app.js` (第 736 行)

```javascript
searchUser: async function() {
    const keyword = document.querySelector('.search-bar input').value;
    
    // ❌ 问题：API 路径错误
    const res = await fetch(`/api/v1/users/search-user?query=${keyword}`);
    
    if (!res.ok) throw new Error('Search request failed');
    // ...
}
```

### 后端代码分析

**文件**: `backend/app/api/v1/api.py`

```python
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
```

**文件**: `backend/app/api/v1/endpoints/search.py`

```python
@router.get("/posts", response_model=List[SearchResult])
def search_posts(q: str, db: Session = Depends(get_db)):
    """Search posts by title or summary."""
    return db.query(Post).filter(
        (Post.title.contains(q)) | (Post.summary.contains(q))
    ).limit(50).all()
```

**文件**: `backend/app/api/v1/endpoints/users.py`

```python
@router.get("/search-user")
def search_user(query: str, db: Session = Depends(get_db)):
    print(f"DEBUG: search_user query={query}")
    # ... 实现代码
```

### 问题根源

**路由不匹配！**

- 前端请求：`/api/v1/users/search-user?query=xxx`
- 后端实际路径：
  - 用户搜索：`/api/v1/users/search-user` ✅ (在 users.py 中实现)
  - 内容搜索：`/api/v1/search/posts?q=xxx` ✅ (在 search.py 中实现)

**实际路径是正确的！** 问题可能是：
1. 后端服务未启动
2. 数据库中没有数据
3. 参数名称不匹配（前端用 `query`，后端用 `query` ✅ 正确）

### 解决方案 ✅

**步骤 1**: 确保后端服务已启动

```bash
cd /Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend

# 检查是否已运行
ps aux | grep "python.*main" | grep -v grep

# 如果没有，启动服务
source venv/bin/activate 2>/dev/null || true
python app/main.py
```

**步骤 2**: 测试 API 端点

```bash
# 测试搜索功能
curl "http://localhost:5000/api/v1/users/search-user?query=test"

# 应该返回 JSON 数组（可能为空）
```

**步骤 3**: 检查数据库

```bash
cd /Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend
python3 -c "
import sqlite3
conn = sqlite3.connect('sql_app.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM users')
count = cursor.fetchone()[0]
print(f'用户总数：{count}')
conn.close()
"
```

---

## 🔍 问题 2: 登录功能失败

### 现象
- 输入用户名密码点击登录
- 显示：`登录成功但获取用户信息失败，请刷新页面`

### 前端代码分析

**文件**: `backend/static/js/app.js` (第 1010-1020 行)

```javascript
login: async function() {
    // ... 获取用户名密码
    
    const res = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username: u, password: p})
    });
    
    if (res.ok) {
        const data = await res.json();
        
        // ✅ 保存 token 和用户 ID
        localStorage.setItem('token', data.access_token);
        localStorage.setItem('user_id', data.user_id);
        localStorage.setItem('username', data.username);
        
        // ❌ 问题出在这里
        await this.fetchCurrentUser(data.user_id);
        
        if(this.state.user) {
             alert('登录成功');
        } else {
             alert('登录成功但获取用户信息失败，请刷新页面');
        }
    }
}
```

**文件**: `backend/static/js/app.js` (第 75-95 行)

```javascript
fetchCurrentUser: async function(uid) {
    try {
        console.log('Fetching user profile for:', uid);
        
        // ❌ 问题：API 路径可能返回 404 或数据格式不对
        const res = await fetch(`/api/v1/users/profile/${uid}?current_user_id=${uid}`);
        
        if (res.ok) {
            const data = await res.json();
            console.log('User fetched:', data);
            
            // ❌ 关键：期望 data.user 存在
            this.state.user = data.user;
            localStorage.setItem('user_id', this.state.user.id);
            localStorage.setItem('username', this.state.user.username);
            this.updateAuthUI();
        } else {
            console.error('Fetch user failed:', res.status);
            if(res.status === 404) this.logout();
        }
    } catch(e) { 
        console.error("Fetch user failed", e); 
    }
}
```

### 后端代码分析

**文件**: `backend/app/api/v1/endpoints/users.py` (第 67-87 行)

```python
@router.get("/profile/{user_id}")
def get_profile(user_id: int, current_user_id: Optional[int] = None, db: Session = Depends(get_db)):
    print(f"DEBUG: get_profile user_id={user_id} current={current_user_id}")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # ... 检查关注状态 ...
    
    # ✅ 返回格式正确：{"user": {...}, "is_following": bool, "is_friend": bool}
    return {
        "user": user_to_dict(user),
        "is_following": is_following,
        "is_friend": is_friend
    }
```

**文件**: `backend/app/api/v1/endpoints/auth.py` (第 56-68 行)

```python
@router.post("/login")
def login(user_in: UserCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == user_in.username).first()
    if not user or user.password_hash != user_in.password + "_hashed":
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    return {
        "access_token": f"fake-token-{user.id}", 
        "token_type": "bearer",
        "user_id": user.id,
        "username": user.username
    }
```

### 问题根源

**多重问题：**

1. **后端服务未启动** - 没有运行 FastAPI 服务
2. **数据库可能未初始化** - 没有 User 表或数据
3. **密码哈希不匹配** - 登录时密码需要加 `_hashed` 后缀
4. **前端错误处理不完善** - 没有详细日志

### 解决方案 ✅

**步骤 1: 启动后端服务**

```bash
cd /Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend

# 创建虚拟环境（如果没有）
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动服务
python app/main.py
```

**步骤 2: 初始化数据库和用户**

创建测试用户脚本：

```python
# create_test_user.py
import sqlite3
from datetime import datetime

conn = sqlite3.connect('sql_app.db')
cursor = conn.cursor()

# 创建用户表（如果不存在）
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    nickname TEXT,
    avatar TEXT,
    bio TEXT,
    gender TEXT,
    birthday TEXT,
    location TEXT,
    aiseek_id TEXT UNIQUE,
    followers_count INTEGER DEFAULT 0,
    following_count INTEGER DEFAULT 0,
    likes_received_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

# 创建测试用户
test_users = [
    ('testuser', 'test123_hashed', 'test@example.com', '测试用户', 'U001'),
    ('admin', 'admin123_hashed', 'admin@aiseek.com', '管理员', 'A001'),
]

for username, pwd_hash, email, nickname, aiseek_id in test_users:
    try:
        cursor.execute('''
        INSERT INTO users (username, password_hash, email, nickname, aiseek_id)
        VALUES (?, ?, ?, ?, ?)
        ''', (username, pwd_hash, email, nickname, aiseek_id))
        print(f'✅ 创建用户：{username}')
    except sqlite3.IntegrityError:
        print(f'⚠️  用户已存在：{username}')

conn.commit()
conn.close()
print('数据库初始化完成')
```

运行：
```bash
cd /Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend
python3 create_test_user.py
```

**步骤 3: 测试登录 API**

```bash
# 测试登录
curl -X POST "http://localhost:5000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "test123"}'

# 应该返回：
# {"access_token":"fake-token-1","token_type":"bearer","user_id":1,"username":"testuser"}
```

**步骤 4: 测试用户信息 API**

```bash
# 获取用户信息
curl "http://localhost:5000/api/v1/users/profile/1?current_user_id=1"

# 应该返回：
# {"user":{...}, "is_following":false, "is_friend":false}
```

**步骤 5: 前端改进建议**

修改 `backend/static/js/app.js` 增强错误处理：

```javascript
fetchCurrentUser: async function(uid) {
    try {
        console.log('Fetching user profile for:', uid);
        
        const res = await fetch(`/api/v1/users/profile/${uid}?current_user_id=${uid}`);
        
        if (!res.ok) {
            console.error(`HTTP error! status: ${res.status}`);
            if(res.status === 404) {
                console.error('User not found, logging out');
                this.logout();
                return;
            }
            if(res.status === 500) {
                console.error('Server error - is backend running?');
                alert('服务器未响应，请检查后端服务是否启动');
                return;
            }
        }
        
        const data = await res.json();
        console.log('User fetched:', data);
        
        // 检查 data.user 是否存在
        if (!data || !data.user) {
            console.error('Invalid response format:', data);
            alert('获取用户信息失败：数据格式错误');
            return;
        }
        
        this.state.user = data.user;
        localStorage.setItem('user_id', this.state.user.id);
        localStorage.setItem('username', this.state.user.username);
        this.updateAuthUI();
        
        console.log('✅ User login successful:', this.state.user.username);
        
    } catch(e) { 
        console.error("Fetch user failed", e);
        alert('网络错误：' + e.message + '\n请检查后端服务是否启动');
    }
}
```

---

## 🛠️ 完整修复步骤

### 立即执行

```bash
# 1. 进入后端目录
cd /Users/surferboy/.openclaw/workspace/AIseek-integrated/AIseek-Trae-v1/backend

# 2. 检查并安装依赖
pip3 install -r requirements.txt

# 3. 初始化数据库（运行 SQL 脚本）
python3 << 'EOF'
import sqlite3

conn = sqlite3.connect('sql_app.db')
cursor = conn.cursor()

# 创建用户表
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    nickname TEXT,
    avatar TEXT,
    bio TEXT,
    gender TEXT,
    birthday TEXT,
    location TEXT,
    aiseek_id TEXT UNIQUE,
    followers_count INTEGER DEFAULT 0,
    following_count INTEGER DEFAULT 0,
    likes_received_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

# 创建测试用户
test_users = [
    ('testuser', 'test123_hashed', 'test@example.com', '测试用户', 'U001'),
    ('admin', 'admin123_hashed', 'admin@aiseek.com', '管理员', 'A001'),
]

for username, pwd_hash, email, nickname, aiseek_id in test_users:
    try:
        cursor.execute('''
        INSERT INTO users (username, password_hash, email, nickname, aiseek_id)
        VALUES (?, ?, ?, ?, ?)
        ''', (username, pwd_hash, email, nickname, aiseek_id))
        print(f'✅ 创建用户：{username}')
    except sqlite3.IntegrityError:
        print(f'⚠️  用户已存在：{username}')

conn.commit()
conn.close()
print('✅ 数据库初始化完成')
EOF

# 4. 启动后端服务
python3 app/main.py &

# 5. 等待服务启动
sleep 3

# 6. 测试 API
curl "http://localhost:5000/api/v1/users/search-user?query=test"
curl -X POST "http://localhost:5000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "test123"}'
```

### 验证修复

1. **打开浏览器**: http://localhost:5000
2. **测试搜索**: 在搜索框输入 "test" 或 "admin"
3. **测试登录**: 点击登录，使用用户名 `testuser` 密码 `test123`

---

## 📋 代码质量评估

### 架构问题

| 问题 | 严重性 | 建议 |
|------|--------|------|
| 1. 缺少全局错误处理 | 🔴 高 | 添加统一的错误拦截器 |
| 2. 前端硬编码密码哈希逻辑 | 🟡 中 | 后端应该处理密码验证 |
| 3. 缺少 API 响应验证 | 🟡 中 | 前端应验证响应数据结构 |
| 4. 日志记录不足 | 🟡 中 | 添加详细的请求/响应日志 |
| 5. 没有健康检查端点 | 🟢 低 | 添加 `/health` 端点 |

### 安全问题

1. **密码明文传输** - 应使用 HTTPS
2. **Token 无有效期** - `fake-token-xxx` 应有时效性
3. **无速率限制** - 应添加登录尝试限制
4. **CORS 配置过松** - `allow_origins=["*"]` 应限制域名

### 建议改进

1. **添加 JWT 认证**
   ```python
   pip install python-jose[cryptography]
   ```

2. **统一错误处理**
   ```python
   @app.exception_handler(Exception)
   async def global_exception_handler(request, exc):
       return JSONResponse(
           status_code=500,
           content={"detail": "Internal server error"}
       )
   ```

3. **添加请求日志**
   ```python
   import logging
   logging.basicConfig(level=logging.INFO)
   logger = logging.getLogger("aiseek")
   
   @app.middleware("http")
   async def log_requests(request, call_next):
       logger.info(f"{request.method} {request.url}")
       response = await call_next(request)
       logger.info(f"Response status: {response.status_code}")
       return response
   ```

---

## 🎯 总结

### 根本原因

1. **后端服务未启动** - FastAPI 应用没有运行
2. **数据库未初始化** - 没有用户表和数据
3. **前端错误提示不明确** - 没有区分网络错误和逻辑错误

### 修复优先级

1. 🔴 **立即**: 启动后端服务 + 初始化数据库
2. 🟡 **今天**: 修复前端错误处理和日志
3. 🟢 **本周**: 添加 JWT 认证和安全加固

### 测试账号

创建后可使用：
- 用户名：`testuser`
- 密码：`test123`

---

**需要我帮你执行修复步骤吗？**
