"""media asset subtitle tracks

Revision ID: 0018_media_asset_subtitle_tracks
Revises: 0017_user_reputation
Create Date: 2026-03-02
"""

from alembic import op
import sqlalchemy as sa


revision = "0018_media_asset_subtitle_tracks"
down_revision = "0017_user_reputation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        try:
            op.execute("ALTER TABLE media_assets ADD COLUMN subtitle_tracks TEXT")
        except Exception:
            pass
        return
    try:
        op.add_column("media_assets", sa.Column("subtitle_tracks", sa.JSON(), nullable=True))
    except Exception:
        pass


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        return
    try:
        op.drop_column("media_assets", "subtitle_tracks")
    except Exception:
        pass

