"""ai job dispatch retry fields

Revision ID: 0015_ai_job_dispatch_retry_fields
Revises: 0014_ai_job_draft_versions
Create Date: 2026-03-02
"""

from alembic import op
import sqlalchemy as sa


revision = "0015_ai_job_dispatch_retry_fields"
down_revision = "0014_ai_job_draft_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        for stmt in (
            "ALTER TABLE ai_jobs ADD COLUMN dispatch_attempts INTEGER DEFAULT 0",
            "ALTER TABLE ai_jobs ADD COLUMN last_dispatch_at DATETIME",
            "ALTER TABLE ai_jobs ADD COLUMN next_dispatch_at DATETIME",
            "CREATE INDEX IF NOT EXISTS idx_ai_jobs_dispatch_attempts ON ai_jobs(dispatch_attempts)",
            "CREATE INDEX IF NOT EXISTS idx_ai_jobs_next_dispatch_at ON ai_jobs(next_dispatch_at)",
        ):
            try:
                op.execute(stmt)
            except Exception:
                pass
        return

    for name, col in (
        ("dispatch_attempts", sa.Column("dispatch_attempts", sa.Integer(), nullable=False, server_default="0")),
        ("last_dispatch_at", sa.Column("last_dispatch_at", sa.DateTime(timezone=True), nullable=True)),
        ("next_dispatch_at", sa.Column("next_dispatch_at", sa.DateTime(timezone=True), nullable=True)),
    ):
        try:
            op.add_column("ai_jobs", col)
        except Exception:
            pass

    for idx, cols in (
        ("idx_ai_jobs_dispatch_attempts", ["dispatch_attempts"]),
        ("idx_ai_jobs_next_dispatch_at", ["next_dispatch_at"]),
    ):
        try:
            op.create_index(idx, "ai_jobs", cols)
        except Exception:
            pass


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect != "sqlite":
        for idx in ("idx_ai_jobs_next_dispatch_at", "idx_ai_jobs_dispatch_attempts"):
            try:
                op.drop_index(idx, table_name="ai_jobs")
            except Exception:
                pass
        for col in ("next_dispatch_at", "last_dispatch_at", "dispatch_attempts"):
            try:
                op.drop_column("ai_jobs", col)
            except Exception:
                pass

