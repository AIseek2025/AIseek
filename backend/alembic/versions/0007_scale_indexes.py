"""scale indexes

Revision ID: 0007_scale_indexes
Revises: 0006_backfill_favorites_count
Create Date: 2026-02-28
"""

from alembic import op


revision = "0007_scale_indexes"
down_revision = "0006_backfill_favorites_count"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        op.execute("CREATE INDEX IF NOT EXISTS idx_posts_status_created_id ON posts(status, created_at, id)")
        op.execute("CREATE INDEX IF NOT EXISTS idx_posts_category_created_id ON posts(category, created_at, id)")

        op.execute("CREATE INDEX IF NOT EXISTS idx_comments_post_created_id ON comments(post_id, created_at, id)")

        op.execute("CREATE INDEX IF NOT EXISTS idx_messages_receiver_created_id ON messages(receiver_id, created_at, id)")
        op.execute("CREATE INDEX IF NOT EXISTS idx_messages_sender_created_id ON messages(sender_id, created_at, id)")

        op.execute("CREATE INDEX IF NOT EXISTS idx_follows_follower_created_following ON follows(follower_id, created_at, following_id)")
        op.execute("CREATE INDEX IF NOT EXISTS idx_follows_following_created_follower ON follows(following_id, created_at, follower_id)")

        op.execute("CREATE INDEX IF NOT EXISTS idx_interactions_user_type_created_id ON interactions(user_id, type, created_at, id)")
        op.execute("CREATE INDEX IF NOT EXISTS idx_interactions_post_type_created_id ON interactions(post_id, type, created_at, id)")
    else:
        try:
            op.create_index("idx_posts_status_created_id", "posts", ["status", "created_at", "id"])
        except Exception:
            pass
        try:
            op.create_index("idx_posts_category_created_id", "posts", ["category", "created_at", "id"])
        except Exception:
            pass

        try:
            op.create_index("idx_comments_post_created_id", "comments", ["post_id", "created_at", "id"])
        except Exception:
            pass

        try:
            op.create_index("idx_messages_receiver_created_id", "messages", ["receiver_id", "created_at", "id"])
        except Exception:
            pass
        try:
            op.create_index("idx_messages_sender_created_id", "messages", ["sender_id", "created_at", "id"])
        except Exception:
            pass

        try:
            op.create_index("idx_follows_follower_created_following", "follows", ["follower_id", "created_at", "following_id"])
        except Exception:
            pass
        try:
            op.create_index("idx_follows_following_created_follower", "follows", ["following_id", "created_at", "follower_id"])
        except Exception:
            pass

        try:
            op.create_index("idx_interactions_user_type_created_id", "interactions", ["user_id", "type", "created_at", "id"])
        except Exception:
            pass
        try:
            op.create_index("idx_interactions_post_type_created_id", "interactions", ["post_id", "type", "created_at", "id"])
        except Exception:
            pass


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        op.execute("DROP INDEX IF EXISTS idx_posts_status_created_id")
        op.execute("DROP INDEX IF EXISTS idx_posts_category_created_id")

        op.execute("DROP INDEX IF EXISTS idx_comments_post_created_id")

        op.execute("DROP INDEX IF EXISTS idx_messages_receiver_created_id")
        op.execute("DROP INDEX IF EXISTS idx_messages_sender_created_id")

        op.execute("DROP INDEX IF EXISTS idx_follows_follower_created_following")
        op.execute("DROP INDEX IF EXISTS idx_follows_following_created_follower")

        op.execute("DROP INDEX IF EXISTS idx_interactions_user_type_created_id")
        op.execute("DROP INDEX IF EXISTS idx_interactions_post_type_created_id")
    else:
        for name, table in (
            ("idx_posts_status_created_id", "posts"),
            ("idx_posts_category_created_id", "posts"),
            ("idx_comments_post_created_id", "comments"),
            ("idx_messages_receiver_created_id", "messages"),
            ("idx_messages_sender_created_id", "messages"),
            ("idx_follows_follower_created_following", "follows"),
            ("idx_follows_following_created_follower", "follows"),
            ("idx_interactions_user_type_created_id", "interactions"),
            ("idx_interactions_post_type_created_id", "interactions"),
        ):
            try:
                op.drop_index(name, table_name=table)
            except Exception:
                pass

