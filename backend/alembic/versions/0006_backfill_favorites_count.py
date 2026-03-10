"""backfill favorites count

Revision ID: 0006_backfill_favorites_count
Revises: 0005_post_counters_async
Create Date: 2026-02-27
"""

from alembic import op


revision = "0006_backfill_favorites_count"
down_revision = "0005_post_counters_async"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE posts SET favorites_count = ("
        "SELECT COUNT(1) FROM interactions i WHERE i.post_id = posts.id AND i.type = 'favorite'"
        ")"
    )
def downgrade() -> None:
    pass
