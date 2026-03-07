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
    CREATE TABLE IF NOT EXISTS follow (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        follower_id INTEGER NOT NULL,
        following_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(follower_id, following_id)
    )
    ''')
    
    # 创建好友请求表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS friend_request (
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
