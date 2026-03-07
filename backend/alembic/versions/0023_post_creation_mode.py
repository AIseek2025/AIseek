"""post creation mode

Revision ID: 0023_post_creation_mode
Revises: 0022_search_pg_indexes
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa


revision = "0023_post_creation_mode"
down_revision = "0022_search_pg_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    try:
        op.add_column("posts", sa.Column("creation_mode", sa.String(length=16), nullable=True, server_default="ai"))
    except Exception:
        return
    try:
        op.execute(
            "UPDATE posts SET creation_mode='manual' "
            "WHERE (source_key LIKE 'uploads/%' OR source_url LIKE '%/uploads/%' OR cover_url LIKE '%/uploads/%' OR images LIKE '%/uploads/%')"
        )
    except Exception:
        pass
    try:
        op.execute("UPDATE posts SET creation_mode='ai' WHERE creation_mode IS NULL OR creation_mode=''")
    except Exception:
        pass
    try:
        op.create_index("ix_posts_creation_mode", "posts", ["creation_mode"])
    except Exception:
        pass


def downgrade() -> None:
    try:
        op.drop_index("ix_posts_creation_mode", table_name="posts")
    except Exception:
        pass
    try:
        op.drop_column("posts", "creation_mode")
    except Exception:
        pass

