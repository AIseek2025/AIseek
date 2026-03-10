"""download enabled default true

Revision ID: 0024_download_enabled_default_true
Revises: 0023_post_creation_mode
Create Date: 2026-03-04
"""

from alembic import op


revision = "0024_download_enabled_default_true"
down_revision = "0023_post_creation_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        op.execute("UPDATE posts SET download_enabled=1 WHERE download_enabled IS NULL OR download_enabled=0")
    else:
        op.execute("UPDATE posts SET download_enabled=TRUE WHERE download_enabled IS NULL OR download_enabled=FALSE")
def downgrade() -> None:
    return

