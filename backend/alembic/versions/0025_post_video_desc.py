"""post video_desc

Revision ID: 0025_post_video_desc
Revises: 0024_download_enabled_default_true
Create Date: 2026-03-15

"""

from alembic import op
import sqlalchemy as sa


revision = "0025_post_video_desc"
down_revision = "0024_download_enabled_default_true"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("posts", sa.Column("video_desc", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("posts", "video_desc")
