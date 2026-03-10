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
        op.execute(
            "UPDATE posts SET favorites_count = ("
            "SELECT COUNT(1) FROM interactions i WHERE i.post_id = posts.id AND i.type = 'favorite'"
            ")"
        )
    else:
        # Use inspector to check if column exists to avoid transaction abort in Postgres
        # inspector = sa.inspect(bind)
        # columns = [c['name'] for c in inspector.get_columns('posts')]
        # if 'favorites_count' not in columns:
        #     op.add_column("posts", sa.Column("favorites_count", sa.Integer(), server_default="0", nullable=False))
        pass

    # For interactions deduplication, execute in a way that handles potential transaction issues if previous commands failed (though they shouldn't now)
    # try:
    #     op.execute(
    #         "DELETE FROM interactions WHERE id NOT IN (SELECT MAX(id) FROM interactions GROUP BY user_id, post_id, type)"
    #     )
    # except Exception:
    #     pass

    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_interactions_user_post_type ON interactions(user_id, post_id, type)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_friend_requests_sender_receiver_status ON friend_requests(sender_id, receiver_id, status)")

    ts_type = "DATETIME" if dialect == "sqlite" else "TIMESTAMP"
    pk_type = "INTEGER PRIMARY KEY AUTOINCREMENT" if dialect == "sqlite" else "SERIAL PRIMARY KEY"

    op.execute(
        f"CREATE TABLE IF NOT EXISTS notification_reads ("
        f"user_id INTEGER PRIMARY KEY,"
        f"last_read_ts REAL NOT NULL DEFAULT 0,"
        f"updated_at {ts_type} DEFAULT CURRENT_TIMESTAMP"
        f")"
    )

    op.execute(
        f"CREATE TABLE IF NOT EXISTS client_events ("
        f"id {pk_type},"
        f"session_id VARCHAR,"
        f"user_id INTEGER,"
        f"name VARCHAR NOT NULL,"
        f"ts REAL NOT NULL,"
        f"tab VARCHAR,"
        f"route VARCHAR,"
        f"request_id VARCHAR,"
        f"data JSON,"
        f"created_at {ts_type} DEFAULT CURRENT_TIMESTAMP"
        f")"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_client_events_user_ts ON client_events(user_id, ts DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_client_events_session_ts ON client_events(session_id, ts DESC)")

    op.execute(
        f"CREATE TABLE IF NOT EXISTS ab_assignments ("
        f"id {pk_type},"
        f"user_id INTEGER NOT NULL,"
        f"experiment VARCHAR NOT NULL,"
        f"variant VARCHAR NOT NULL,"
        f"created_at {ts_type} DEFAULT CURRENT_TIMESTAMP"
        f")"
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
