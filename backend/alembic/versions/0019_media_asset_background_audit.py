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
        op.execute("ALTER TABLE media_assets ADD COLUMN background_audit TEXT")
        return
    op.add_column("media_assets", sa.Column("background_audit", sa.JSON(), nullable=True))
def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        return
    op.drop_column("media_assets", "background_audit")
