"""constraints counts ab events

Revision ID: 0004_constraints_counts_ab_events
Revises: 0003_notification_event_ts
Create Date: 2026-02-27
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_constraints_counts_ab_events"
down_revision = "0003_notification_event_ts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        cols = [r[1] for r in bind.execute(sa.text("PRAGMA table_info(posts)")).fetchall()]
        if "favorites_count" not in cols:
            op.execute("ALTER TABLE posts ADD COLUMN favorites_count INTEGER DEFAULT 0")
        op.execute("UPDATE posts SET favorites_count = COALESCE(favorites_count, 0)")
        try:
            op.execute(
                "UPDATE posts SET favorites_count = ("
                "SELECT COUNT(1) FROM interactions i WHERE i.post_id = posts.id AND i.type = 'favorite'"
                ")"
            )
        except Exception:
            pass
    else:
        try:
            op.add_column("posts", sa.Column("favorites_count", sa.Integer(), server_default="0", nullable=False))
        except Exception:
            pass

    try:
        op.execute(
            "DELETE FROM interactions WHERE id NOT IN (SELECT MAX(id) FROM interactions GROUP BY user_id, post_id, type)"
        )
    except Exception:
        pass

    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_interactions_user_post_type ON interactions(user_id, post_id, type)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_friend_requests_sender_receiver_status ON friend_requests(sender_id, receiver_id, status)")

    op.execute(
        "CREATE TABLE IF NOT EXISTS notification_reads ("
        "user_id INTEGER PRIMARY KEY,"
        "last_read_ts REAL NOT NULL DEFAULT 0,"
        "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ")"
    )

    op.execute(
        "CREATE TABLE IF NOT EXISTS client_events ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "session_id VARCHAR,"
        "user_id INTEGER,"
        "name VARCHAR NOT NULL,"
        "ts REAL NOT NULL,"
        "tab VARCHAR,"
        "route VARCHAR,"
        "request_id VARCHAR,"
        "data JSON,"
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ")"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_client_events_user_ts ON client_events(user_id, ts DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_client_events_session_ts ON client_events(session_id, ts DESC)")

    op.execute(
        "CREATE TABLE IF NOT EXISTS ab_assignments ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "user_id INTEGER NOT NULL,"
        "experiment VARCHAR NOT NULL,"
        "variant VARCHAR NOT NULL,"
        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        ")"
    )
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_ab_user_experiment ON ab_assignments(user_id, experiment)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_ab_user_experiment")
    op.execute("DROP TABLE IF EXISTS ab_assignments")
    op.execute("DROP INDEX IF EXISTS idx_client_events_user_ts")
    op.execute("DROP INDEX IF EXISTS idx_client_events_session_ts")
    op.execute("DROP TABLE IF EXISTS client_events")
    op.execute("DROP TABLE IF EXISTS notification_reads")
    op.execute("DROP INDEX IF EXISTS uq_friend_requests_sender_receiver_status")
    op.execute("DROP INDEX IF EXISTS uq_interactions_user_post_type")
