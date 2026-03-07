"""post download settings

Revision ID: 0020_post_download_settings
Revises: 0019_media_asset_background_audit
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa


revision = "0020_post_download_settings"
down_revision = "0019_media_asset_background_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        try:
            op.execute("ALTER TABLE posts ADD COLUMN download_enabled INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            op.execute("ALTER TABLE posts ADD COLUMN downloads_count INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            op.execute("CREATE INDEX IF NOT EXISTS ix_posts_download_enabled ON posts (download_enabled)")
        except Exception:
            pass
        return
    try:
        op.add_column("posts", sa.Column("download_enabled", sa.Boolean(), nullable=True))
    except Exception:
        pass
    try:
        op.add_column("posts", sa.Column("downloads_count", sa.Integer(), nullable=True))
    except Exception:
        pass
    try:
        op.create_index("ix_posts_download_enabled", "posts", ["download_enabled"])
    except Exception:
        pass


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        return
    try:
        op.drop_index("ix_posts_download_enabled", table_name="posts")
    except Exception:
        pass
    try:
        op.drop_column("posts", "downloads_count")
    except Exception:
        pass
    try:
        op.drop_column("posts", "download_enabled")
    except Exception:
        pass
