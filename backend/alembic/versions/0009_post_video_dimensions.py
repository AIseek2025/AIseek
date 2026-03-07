"""post video dimensions

Revision ID: 0009_post_video_dimensions
Revises: 0008_post_media_fields
Create Date: 2026-02-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_post_video_dimensions"
down_revision = "0008_post_media_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        for sql in (
            "ALTER TABLE posts ADD COLUMN video_width INTEGER",
            "ALTER TABLE posts ADD COLUMN video_height INTEGER",
        ):
            try:
                op.execute(sql)
            except Exception:
                pass
        return

    try:
        op.add_column("posts", sa.Column("video_width", sa.Integer(), nullable=True))
    except Exception:
        pass
    try:
        op.add_column("posts", sa.Column("video_height", sa.Integer(), nullable=True))
    except Exception:
        pass


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        return
    try:
        op.drop_column("posts", "video_height")
    except Exception:
        pass
    try:
        op.drop_column("posts", "video_width")
    except Exception:
        pass

