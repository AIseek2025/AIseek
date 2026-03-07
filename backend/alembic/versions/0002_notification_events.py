"""notification events

Revision ID: 0002_notification_events
Revises: 0001_indexes_and_ai_jobs
Create Date: 2026-02-27
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_notification_events"
down_revision = "0001_indexes_and_ai_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        op.execute(
            "CREATE TABLE IF NOT EXISTS notification_events ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "user_id INTEGER NOT NULL,"
            "event_type VARCHAR NOT NULL,"
            "event_key VARCHAR NOT NULL UNIQUE,"
            "payload JSON NOT NULL,"
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
    else:
        op.create_table(
            "notification_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False, index=True),
            sa.Column("event_type", sa.String(), nullable=False, index=True),
            sa.Column("event_key", sa.String(), nullable=False, unique=True, index=True),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    op.execute("CREATE INDEX IF NOT EXISTS idx_notification_events_user_created_id ON notification_events(user_id, created_at DESC, id DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_notification_events_user_created_id")
    op.execute("DROP TABLE IF EXISTS notification_events")
