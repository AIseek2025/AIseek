#!/usr/bin/env python3
"""
初始化数据库和测试用户
"""
import sqlite3
from datetime import datetime

DB_PATH = 'sql_app.db'

def init_database():
    conn = sqlite3.connect(DB_PATH)
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
    
    # 创建关注表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS follows (
        follower_id INTEGER NOT NULL,
        following_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (follower_id, following_id)
    )
    ''')
    
    # 创建好友请求表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS friend_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER NOT NULL,
        receiver_id INTEGER NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 创建帖子表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT,
        summary TEXT,
        content TEXT,
        post_type TEXT DEFAULT 'video',
        video_url TEXT,
        images TEXT,
        category TEXT,
        status TEXT DEFAULT 'pending',
        error TEXT,
        likes_count INTEGER DEFAULT 0,
        comments_count INTEGER DEFAULT 0,
        shares_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 创建互动表 (likes, favorites, etc.)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS interactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        post_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 创建消息表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER NOT NULL,
        receiver_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 创建分类表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        sort_order INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1
    )
    ''')
    
    # 创建评论表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        post_id INTEGER,
        parent_id INTEGER,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # === 创建关键索引 (修复超时问题) ===
    # interactions 表索引 - 用于 decorate_flags 查询
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS ix_interactions_user_post_type 
    ON interactions (user_id, post_id, type)
    ''')
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS ix_interactions_user_id 
    ON interactions (user_id)
    ''')
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS ix_interactions_post_id 
    ON interactions (post_id)
    ''')
    
    # follows 表索引
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS ix_follows_follower_id 
    ON follows (follower_id)
    ''')
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS ix_follows_following_id 
    ON follows (following_id)
    ''')
    
    # posts 表索引
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS ix_posts_user_id 
    ON posts (user_id)
    ''')
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS ix_posts_status 
    ON posts (status)
    ''')
    
    # messages 表索引
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS ix_messages_sender_receiver 
    ON messages (sender_id, receiver_id)
    ''')
    
    # comments 表索引
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS ix_comments_post_id 
    ON comments (post_id)
    ''')
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS ix_comments_user_id 
    ON comments (user_id)
    ''')
    
    # 创建测试用户
    test_users = [
        ('testuser', 'test123_hashed', 'test@example.com', '测试用户', 'U001'),
        ('admin', 'admin123_hashed', 'admin@aiseek.com', '管理员', 'A001'),
        ('demo', 'demo123_hashed', 'demo@aiseek.com', '演示账号', 'D001'),
    ]
    
    print('📦 初始化数据库...')
    for username, pwd_hash, email, nickname, aiseek_id in test_users:
        try:
            cursor.execute('''
            INSERT INTO users (username, password_hash, email, nickname, aiseek_id)
            VALUES (?, ?, ?, ?, ?)
            ''', (username, pwd_hash, email, nickname, aiseek_id))
            print(f'✅ 创建用户：{username} (密码：{pwd_hash.replace("_hashed", "")})')
        except sqlite3.IntegrityError:
            print(f'⚠️  用户已存在：{username}')
    
    # 插入初始分类数据
    categories = ['AI', 'Programming', 'Ecommerce', 'Marketing', 'Multimodal', 'Robots']
    for i, cat in enumerate(categories):
        try:
            cursor.execute('''
            INSERT INTO categories (name, sort_order, is_active)
            VALUES (?, ?, ?)
            ''', (cat, i, 1))
        except sqlite3.IntegrityError:
            pass
    
    # 插入一个测试帖子 (用于 smoke test)
    try:
        cursor.execute('''
        INSERT INTO posts (user_id, title, summary, content, post_type, category, status, likes_count, comments_count)
        VALUES (1, 'Test Post', 'A test post for CI', 'Test content', 'video', 'AI', 'done', 0, 0)
        ''')
        print('✅ 创建测试帖子：id=1')
    except sqlite3.IntegrityError:
        pass
    
    conn.commit()
    conn.close()
    print('✅ 数据库初始化完成')
    print('')
    print('📝 测试账号:')
    print('  1. 用户名：testuser  密码：test123')
    print('  2. 用户名：admin     密码：admin123')
    print('  3. 用户名：demo      密码：demo123')

if __name__ == '__main__':
    init_database()
