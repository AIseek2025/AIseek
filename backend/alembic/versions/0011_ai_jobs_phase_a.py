"""ai jobs phase a

Revision ID: 0011_ai_jobs_phase_a
Revises: 0010_media_assets
Create Date: 2026-03-01
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_ai_jobs_phase_a"
down_revision = "0010_media_assets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        for stmt in (
            "ALTER TABLE posts ADD COLUMN ai_job_id VARCHAR",
            "CREATE INDEX IF NOT EXISTS idx_posts_ai_job_id ON posts(ai_job_id)",
            "ALTER TABLE ai_jobs ADD COLUMN post_id INTEGER",
            "ALTER TABLE ai_jobs ADD COLUMN kind VARCHAR",
            "ALTER TABLE ai_jobs ADD COLUMN stage VARCHAR",
            "ALTER TABLE ai_jobs ADD COLUMN stage_message TEXT",
            "ALTER TABLE ai_jobs ADD COLUMN input_json JSON",
            "ALTER TABLE ai_jobs ADD COLUMN draft_json JSON",
            "ALTER TABLE ai_jobs ADD COLUMN worker_task_id VARCHAR",
            "ALTER TABLE ai_jobs ADD COLUMN cancelled_at DATETIME",
            "CREATE INDEX IF NOT EXISTS idx_ai_jobs_post_id ON ai_jobs(post_id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_jobs_kind ON ai_jobs(kind)",
            "CREATE INDEX IF NOT EXISTS idx_ai_jobs_stage ON ai_jobs(stage)",
            "CREATE INDEX IF NOT EXISTS idx_ai_jobs_worker_task_id ON ai_jobs(worker_task_id)",
        ):
            try:
                op.execute(stmt)
            except Exception:
                pass
        return

    try:
        op.add_column("posts", sa.Column("ai_job_id", sa.String(), nullable=True))
    except Exception:
        pass
    try:
        op.create_index("idx_posts_ai_job_id", "posts", ["ai_job_id"])
    except Exception:
        pass

    for name, col in (
        ("post_id", sa.Column("post_id", sa.Integer(), nullable=True)),
        ("kind", sa.Column("kind", sa.String(), nullable=True)),
        ("stage", sa.Column("stage", sa.String(), nullable=True)),
        ("stage_message", sa.Column("stage_message", sa.Text(), nullable=True)),
        ("input_json", sa.Column("input_json", sa.JSON(), nullable=True)),
        ("draft_json", sa.Column("draft_json", sa.JSON(), nullable=True)),
        ("worker_task_id", sa.Column("worker_task_id", sa.String(), nullable=True)),
        ("cancelled_at", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True)),
    ):
        try:
            op.add_column("ai_jobs", col)
        except Exception:
            pass

    for idx, cols in (
        ("idx_ai_jobs_post_id", ["post_id"]),
        ("idx_ai_jobs_kind", ["kind"]),
        ("idx_ai_jobs_stage", ["stage"]),
        ("idx_ai_jobs_worker_task_id", ["worker_task_id"]),
    ):
        try:
            op.create_index(idx, "ai_jobs", cols)
        except Exception:
            pass


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect != "sqlite":
        for idx, table in (
            ("idx_ai_jobs_worker_task_id", "ai_jobs"),
            ("idx_ai_jobs_stage", "ai_jobs"),
            ("idx_ai_jobs_kind", "ai_jobs"),
            ("idx_ai_jobs_post_id", "ai_jobs"),
            ("idx_posts_ai_job_id", "posts"),
        ):
            try:
                op.drop_index(idx, table_name=table)
            except Exception:
                pass
        for col in ("cancelled_at", "worker_task_id", "draft_json", "input_json", "stage_message", "stage", "kind", "post_id"):
            try:
                op.drop_column("ai_jobs", col)
            except Exception:
                pass
        try:
            op.drop_column("posts", "ai_job_id")
        except Exception:
            pass
