"""notification event ts

Revision ID: 0003_notification_event_ts
Revises: 0002_notification_events
Create Date: 2026-02-27
"""

from alembic import op


revision = "0003_notification_event_ts"
down_revision = "0002_notification_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE notification_events ADD COLUMN created_at_ts REAL")
    op.execute("UPDATE notification_events SET created_at_ts = CAST(strftime('%s', created_at) AS REAL) WHERE created_at_ts IS NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_notification_events_user_ts_id ON notification_events(user_id, created_at_ts DESC, id DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_notification_events_user_ts_id")
