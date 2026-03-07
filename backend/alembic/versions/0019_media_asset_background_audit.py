"""media asset background audit

Revision ID: 0019_media_asset_background_audit
Revises: 0018_media_asset_subtitle_tracks
Create Date: 2026-03-02
"""

from alembic import op
import sqlalchemy as sa


revision = "0019_media_asset_background_audit"
down_revision = "0018_media_asset_subtitle_tracks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        try:
            op.execute("ALTER TABLE media_assets ADD COLUMN background_audit TEXT")
        except Exception:
            pass
        return
    try:
        op.add_column("media_assets", sa.Column("background_audit", sa.JSON(), nullable=True))
    except Exception:
        pass


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        return
    try:
        op.drop_column("media_assets", "background_audit")
    except Exception:
        pass

