"""indexes and ai jobs

Revision ID: 0001_indexes_and_ai_jobs
Revises:
Create Date: 2026-02-27
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_indexes_and_ai_jobs"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        op.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "username VARCHAR NOT NULL UNIQUE,"
            "email VARCHAR UNIQUE,"
            "phone VARCHAR UNIQUE,"
            "password_hash VARCHAR NOT NULL,"
            "nickname VARCHAR,"
            "avatar VARCHAR,"
            "background VARCHAR,"
            "bio VARCHAR,"
            "gender VARCHAR,"
            "birthday VARCHAR,"
            "location VARCHAR,"
            "aiseek_id VARCHAR UNIQUE,"
            "followers_count INTEGER DEFAULT 0,"
            "following_count INTEGER DEFAULT 0,"
            "likes_received_count INTEGER DEFAULT 0,"
            "is_active BOOLEAN DEFAULT 1,"
            "is_superuser BOOLEAN DEFAULT 0,"
            "settings JSON,"
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP,"
            "updated_at DATETIME"
            ")"
        )
        op.execute(
            "CREATE TABLE IF NOT EXISTS user_personas ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "user_id INTEGER UNIQUE,"
            "tags JSON,"
            "interest_vector JSON,"
            "behavior_log JSON,"
            "updated_at DATETIME,"
            "FOREIGN KEY(user_id) REFERENCES users(id)"
            ")"
        )
        op.execute(
            "CREATE TABLE IF NOT EXISTS posts ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "title VARCHAR,"
            "summary TEXT,"
            "category VARCHAR,"
            "post_type VARCHAR DEFAULT 'video',"
            "video_url VARCHAR,"
            "images JSON,"
            "cover_url VARCHAR,"
            "custom_instructions TEXT,"
            "duration INTEGER,"
            "content_text TEXT,"
            "status VARCHAR DEFAULT 'processing',"
            "views_count INTEGER DEFAULT 0,"
            "likes_count INTEGER DEFAULT 0,"
            "comments_count INTEGER DEFAULT 0,"
            "favorites_count INTEGER DEFAULT 0,"
            "shares_count INTEGER DEFAULT 0,"
            "user_id INTEGER,"
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP,"
            "FOREIGN KEY(user_id) REFERENCES users(id)"
            ")"
        )
        op.execute(
            "CREATE TABLE IF NOT EXISTS comments ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "content TEXT NOT NULL,"
            "user_id INTEGER,"
            "post_id INTEGER,"
            "parent_id INTEGER,"
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP,"
            "FOREIGN KEY(user_id) REFERENCES users(id),"
            "FOREIGN KEY(post_id) REFERENCES posts(id)"
            ")"
        )
        op.execute(
            "CREATE TABLE IF NOT EXISTS comment_reactions ("
            "user_id INTEGER NOT NULL,"
            "comment_id INTEGER NOT NULL,"
            "reaction VARCHAR NOT NULL,"
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP,"
            "PRIMARY KEY(user_id, comment_id)"
            ")"
        )
        op.execute(
            "CREATE TABLE IF NOT EXISTS categories ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "name VARCHAR NOT NULL UNIQUE,"
            "sort_order INTEGER DEFAULT 0,"
            "is_active BOOLEAN DEFAULT 1,"
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        op.execute(
            "CREATE TABLE IF NOT EXISTS interactions ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "user_id INTEGER,"
            "post_id INTEGER,"
            "type VARCHAR NOT NULL,"
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        op.execute(
            "CREATE TABLE IF NOT EXISTS follows ("
            "follower_id INTEGER NOT NULL,"
            "following_id INTEGER NOT NULL,"
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP,"
            "PRIMARY KEY(follower_id, following_id)"
            ")"
        )
        op.execute(
            "CREATE TABLE IF NOT EXISTS messages ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "sender_id INTEGER,"
            "receiver_id INTEGER,"
            "content TEXT NOT NULL,"
            "is_read BOOLEAN DEFAULT 0,"
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        op.execute(
            "CREATE TABLE IF NOT EXISTS danmaku ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "post_id INTEGER,"
            "user_id INTEGER,"
            "content VARCHAR NOT NULL,"
            "timestamp REAL NOT NULL,"
            "color VARCHAR DEFAULT '#FFFFFF',"
            "position INTEGER DEFAULT 0,"
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        op.execute(
            "CREATE TABLE IF NOT EXISTS friend_requests ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "sender_id INTEGER NOT NULL,"
            "receiver_id INTEGER NOT NULL,"
            "status VARCHAR DEFAULT 'pending',"
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
    else:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("username", sa.String(), nullable=False, unique=True, index=True),
            sa.Column("email", sa.String(), unique=True, nullable=True, index=True),
            sa.Column("phone", sa.String(), unique=True, nullable=True, index=True),
            sa.Column("password_hash", sa.String(), nullable=False),
            sa.Column("nickname", sa.String(), nullable=True, index=True),
            sa.Column("avatar", sa.String(), nullable=True),
            sa.Column("background", sa.String(), nullable=True),
            sa.Column("bio", sa.String(), nullable=True),
            sa.Column("gender", sa.String(), nullable=True),
            sa.Column("birthday", sa.String(), nullable=True),
            sa.Column("location", sa.String(), nullable=True),
            sa.Column("aiseek_id", sa.String(), unique=True, nullable=True, index=True),
            sa.Column("followers_count", sa.Integer(), server_default="0"),
            sa.Column("following_count", sa.Integer(), server_default="0"),
            sa.Column("likes_received_count", sa.Integer(), server_default="0"),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
            sa.Column("is_superuser", sa.Boolean(), server_default=sa.text("false")),
            sa.Column("settings", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        for fn in (
            _create_core_postgres_posts,
            _create_core_postgres_comments,
            _create_core_postgres_comment_reactions,
            _create_core_postgres_categories,
            _create_core_postgres_interactions,
            _create_core_postgres_follows,
            _create_core_postgres_messages,
            _create_core_postgres_friend_requests,
            _create_core_postgres_user_personas,
            _create_core_postgres_danmaku,
        ):
            fn()
    if dialect == "sqlite":
        op.execute(
            "CREATE TABLE IF NOT EXISTS ai_jobs ("
            "id VARCHAR PRIMARY KEY,"
            "user_id INTEGER NOT NULL,"
            "status VARCHAR DEFAULT 'queued',"
            "progress INTEGER DEFAULT 0,"
            "result_json JSON,"
            "error TEXT,"
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP,"
            "updated_at DATETIME"
            ")"
        )
    else:
        op.create_table(
            "ai_jobs",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False, index=True),
            sa.Column("status", sa.String(), nullable=False, server_default="queued", index=True),
            sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("result_json", sa.JSON(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )

    op.execute("CREATE INDEX IF NOT EXISTS idx_posts_status_created_id ON posts(status, created_at DESC, id DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_posts_category_created_id ON posts(category, created_at DESC, id DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_posts_user_created_id ON posts(user_id, created_at DESC, id DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_comments_post_created_id ON comments(post_id, created_at DESC, id DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_comments_user_created_id ON comments(user_id, created_at DESC, id DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_interactions_post_type_created ON interactions(post_id, type, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_interactions_user_type_created ON interactions(user_id, type, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_interactions_user_post_type ON interactions(user_id, post_id, type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_messages_receiver_read_created ON messages(receiver_id, is_read, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_friend_requests_receiver_created ON friend_requests(receiver_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_follows_following_created ON follows(following_id, created_at DESC)")


def _create_core_postgres_posts() -> None:
    op.create_table(
        "posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(), nullable=True, index=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("category", sa.String(), nullable=True, index=True),
        sa.Column("post_type", sa.String(), nullable=False, server_default="video", index=True),
        sa.Column("video_url", sa.String(), nullable=True),
        sa.Column("images", sa.JSON(), nullable=True),
        sa.Column("cover_url", sa.String(), nullable=True),
        sa.Column("custom_instructions", sa.Text(), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="processing", index=True),
        sa.Column("views_count", sa.Integer(), server_default="0"),
        sa.Column("likes_count", sa.Integer(), server_default="0"),
        sa.Column("comments_count", sa.Integer(), server_default="0"),
        sa.Column("favorites_count", sa.Integer(), server_default="0"),
        sa.Column("shares_count", sa.Integer(), server_default="0"),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def _create_core_postgres_comments() -> None:
    op.create_table(
        "comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), index=True),
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("posts.id"), index=True),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("comments.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def _create_core_postgres_comment_reactions() -> None:
    op.create_table(
        "comment_reactions",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("comment_id", sa.Integer(), sa.ForeignKey("comments.id"), primary_key=True),
        sa.Column("reaction", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def _create_core_postgres_categories() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), unique=True, nullable=False, index=True),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def _create_core_postgres_interactions() -> None:
    op.create_table(
        "interactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), index=True),
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("posts.id"), index=True),
        sa.Column("type", sa.String(), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def _create_core_postgres_follows() -> None:
    op.create_table(
        "follows",
        sa.Column("follower_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("following_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def _create_core_postgres_messages() -> None:
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id"), index=True),
        sa.Column("receiver_id", sa.Integer(), sa.ForeignKey("users.id"), index=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def _create_core_postgres_friend_requests() -> None:
    op.create_table(
        "friend_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("receiver_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending", index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def _create_core_postgres_user_personas() -> None:
    op.create_table(
        "user_personas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), unique=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("interest_vector", sa.JSON(), nullable=True),
        sa.Column("behavior_log", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def _create_core_postgres_danmaku() -> None:
    op.create_table(
        "danmaku",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("posts.id"), index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("timestamp", sa.Float(), nullable=False),
        sa.Column("color", sa.String(), server_default="#FFFFFF"),
        sa.Column("position", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_posts_status_created_id")
    op.execute("DROP INDEX IF EXISTS idx_posts_category_created_id")
    op.execute("DROP INDEX IF EXISTS idx_posts_user_created_id")
    op.execute("DROP INDEX IF EXISTS idx_comments_post_created_id")
    op.execute("DROP INDEX IF EXISTS idx_comments_user_created_id")
    op.execute("DROP INDEX IF EXISTS idx_interactions_post_type_created")
    op.execute("DROP INDEX IF EXISTS idx_interactions_user_type_created")
    op.execute("DROP INDEX IF EXISTS idx_interactions_user_post_type")
    op.execute("DROP INDEX IF EXISTS idx_messages_receiver_read_created")
    op.execute("DROP INDEX IF EXISTS idx_friend_requests_receiver_created")
    op.execute("DROP INDEX IF EXISTS idx_follows_following_created")
    op.execute("DROP TABLE IF EXISTS ai_jobs")
