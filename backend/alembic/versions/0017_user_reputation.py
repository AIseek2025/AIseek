"""user reputation

Revision ID: 0017_user_reputation
Revises: 0016_ai_scale_indexes
Create Date: 2026-03-02
"""

from alembic import op
import sqlalchemy as sa


revision = "0017_user_reputation"
down_revision = "0016_ai_scale_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    try:
        op.add_column("users", sa.Column("reputation_score", sa.Integer(), nullable=True, server_default="100"))
    except Exception:
        pass
    try:
        op.add_column("users", sa.Column("reputation_updated_at", sa.DateTime(timezone=True), nullable=True))
    except Exception:
        pass
    try:
        op.add_column("users", sa.Column("submit_banned_until", sa.DateTime(timezone=True), nullable=True))
    except Exception:
        pass
    try:
        op.execute("UPDATE users SET reputation_score=100 WHERE reputation_score IS NULL")
    except Exception:
        pass

    try:
        op.create_table(
            "user_reputation_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False, index=True),
            sa.Column("post_id", sa.Integer(), nullable=True, index=True),
            sa.Column("delta", sa.Integer(), nullable=False),
            sa.Column("score_after", sa.Integer(), nullable=False),
            sa.Column("reasons", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    except Exception:
        pass
    try:
        op.create_index("idx_user_reputation_events_user_created_id", "user_reputation_events", ["user_id", "created_at", "id"])
    except Exception:
        pass


def downgrade() -> None:
    try:
        op.drop_index("idx_user_reputation_events_user_created_id", table_name="user_reputation_events")
    except Exception:
        pass
    try:
        op.drop_table("user_reputation_events")
    except Exception:
        pass
    try:
        op.drop_column("users", "submit_banned_until")
    except Exception:
        pass
    try:
        op.drop_column("users", "reputation_updated_at")
    except Exception:
        pass
    try:
        op.drop_column("users", "reputation_score")
    except Exception:
        pass
