"""media assets

Revision ID: 0010_media_assets
Revises: 0009_post_video_dimensions
Create Date: 2026-02-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_media_assets"
down_revision = "0009_post_video_dimensions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "media_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("posts.id"), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("hls_url", sa.String(), nullable=True),
        sa.Column("mp4_url", sa.String(), nullable=True),
        sa.Column("cover_url", sa.String(), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("video_width", sa.Integer(), nullable=True),
        sa.Column("video_height", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    try:
        op.create_index("idx_media_assets_post_id", "media_assets", ["post_id"])
    except Exception:
        pass
    try:
        op.create_index("idx_media_assets_version", "media_assets", ["version"])
    except Exception:
        pass

    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        try:
            op.execute("ALTER TABLE posts ADD COLUMN active_media_asset_id INTEGER")
        except Exception:
            pass
        try:
            op.execute("CREATE INDEX IF NOT EXISTS idx_posts_active_media_asset_id ON posts(active_media_asset_id)")
        except Exception:
            pass
        return

    try:
        op.add_column("posts", sa.Column("active_media_asset_id", sa.Integer(), sa.ForeignKey("media_assets.id"), nullable=True))
    except Exception:
        pass
    try:
        op.create_index("idx_posts_active_media_asset_id", "posts", ["active_media_asset_id"])
    except Exception:
        pass


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect != "sqlite":
        try:
            op.drop_index("idx_posts_active_media_asset_id", table_name="posts")
        except Exception:
            pass
        try:
            op.drop_column("posts", "active_media_asset_id")
        except Exception:
            pass

    try:
        op.drop_index("idx_media_assets_version", table_name="media_assets")
    except Exception:
        pass
    try:
        op.drop_index("idx_media_assets_post_id", table_name="media_assets")
    except Exception:
        pass
    try:
        op.drop_table("media_assets")
    except Exception:
        pass

