"""ai job draft versions

Revision ID: 0014_ai_job_draft_versions
Revises: 0013_ai_job_messages
Create Date: 2026-03-01
"""

from alembic import op
import sqlalchemy as sa


revision = "0014_ai_job_draft_versions"
down_revision = "0013_ai_job_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_job_draft_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("draft_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    for idx, cols in (
        ("idx_ai_draft_job", ["job_id"]),
        ("idx_ai_draft_user", ["user_id"]),
        ("idx_ai_draft_source", ["source"]),
    ):
        try:
            op.create_index(idx, "ai_job_draft_versions", cols)
        except Exception:
            pass


def downgrade() -> None:
    for idx in ("idx_ai_draft_source", "idx_ai_draft_user", "idx_ai_draft_job"):
        try:
            op.drop_index(idx, table_name="ai_job_draft_versions")
        except Exception:
            pass
    try:
        op.drop_table("ai_job_draft_versions")
    except Exception:
        pass

