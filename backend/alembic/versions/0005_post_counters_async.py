"""post counters async

Revision ID: 0005_post_counters_async
Revises: 0004_constraints_counts_ab_events
Create Date: 2026-02-27
"""

from alembic import op


revision = "0005_post_counters_async"
down_revision = "0004_constraints_counts_ab_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TABLE IF NOT EXISTS post_counters ("
        "post_id INTEGER PRIMARY KEY,"
        "likes_count INTEGER DEFAULT 0,"
        "favorites_count INTEGER DEFAULT 0,"
        "comments_count INTEGER DEFAULT 0,"
        "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ")"
    )

    op.execute(
        "CREATE TABLE IF NOT EXISTS post_counter_events ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "post_id INTEGER NOT NULL,"
        "counter VARCHAR NOT NULL,"
        "delta INTEGER NOT NULL,"
        "event_key VARCHAR NOT NULL UNIQUE,"
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ")"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_post_counter_events_post ON post_counter_events(post_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_post_counter_events_counter ON post_counter_events(counter)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_post_counter_events_post")
    op.execute("DROP INDEX IF EXISTS idx_post_counter_events_counter")
    op.execute("DROP TABLE IF EXISTS post_counter_events")
    op.execute("DROP TABLE IF EXISTS post_counters")
