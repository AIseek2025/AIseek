"""ai moderation checks

Revision ID: 0012_ai_moderation_checks
Revises: 0011_ai_jobs_phase_a
Create Date: 2026-03-01
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_ai_moderation_checks"
down_revision = "0011_ai_jobs_phase_a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_moderation_checks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("reasons", sa.JSON(), nullable=True),
        sa.Column("appeal", sa.JSON(), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    for idx, cols in (
        ("idx_ai_mod_job_id", ["job_id"]),
        ("idx_ai_mod_user_id", ["user_id"]),
        ("idx_ai_mod_post_id", ["post_id"]),
        ("idx_ai_mod_status", ["status"]),
        ("idx_ai_mod_decided_by", ["decided_by"]),
    ):
        op.create_index(idx, "ai_moderation_checks", cols)
def downgrade() -> None:
    for idx in ("idx_ai_mod_decided_by", "idx_ai_mod_status", "idx_ai_mod_post_id", "idx_ai_mod_user_id", "idx_ai_mod_job_id"):
        op.drop_index(idx, table_name="ai_moderation_checks")
    op.drop_table("ai_moderation_checks")
