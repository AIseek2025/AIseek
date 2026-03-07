"""ai job messages

Revision ID: 0013_ai_job_messages
Revises: 0012_ai_moderation_checks
Create Date: 2026-03-01
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_ai_job_messages"
down_revision = "0012_ai_moderation_checks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_job_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    for idx, cols in (
        ("idx_ai_job_msg_job", ["job_id"]),
        ("idx_ai_job_msg_user", ["user_id"]),
        ("idx_ai_job_msg_role", ["role"]),
    ):
        try:
            op.create_index(idx, "ai_job_messages", cols)
        except Exception:
            pass


def downgrade() -> None:
    for idx in ("idx_ai_job_msg_role", "idx_ai_job_msg_user", "idx_ai_job_msg_job"):
        try:
            op.drop_index(idx, table_name="ai_job_messages")
        except Exception:
            pass
    try:
        op.drop_table("ai_job_messages")
    except Exception:
        pass

