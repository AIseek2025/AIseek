"""ai scale indexes

Revision ID: 0016_ai_scale_indexes
Revises: 0015_ai_job_dispatch_retry_fields
Create Date: 2026-03-02
"""

from alembic import op


revision = "0016_ai_scale_indexes"
down_revision = "0015_ai_job_dispatch_retry_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        for stmt in (
            "CREATE INDEX IF NOT EXISTS idx_ai_jobs_user_created_id ON ai_jobs(user_id, created_at, id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_job_messages_job_id_id ON ai_job_messages(job_id, id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_job_draft_versions_job_id_id ON ai_job_draft_versions(job_id, id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_moderation_checks_status_created_id ON ai_moderation_checks(status, created_at, id)",
            "CREATE INDEX IF NOT EXISTS idx_media_assets_post_created_id ON media_assets(post_id, created_at, id)",
        ):
            op.execute(stmt)
        return

    op.create_index("idx_ai_jobs_user_created_id", "ai_jobs", ["user_id", "created_at", "id"])
    op.create_index("idx_ai_job_messages_job_id_id", "ai_job_messages", ["job_id", "id"])
    op.create_index("idx_ai_job_draft_versions_job_id_id", "ai_job_draft_versions", ["job_id", "id"])
    op.create_index("idx_ai_moderation_checks_status_created_id", "ai_moderation_checks", ["status", "created_at", "id"])
    op.create_index("idx_media_assets_post_created_id", "media_assets", ["post_id", "created_at", "id"])
def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        for stmt in (
            "DROP INDEX IF EXISTS idx_media_assets_post_created_id",
            "DROP INDEX IF EXISTS idx_ai_moderation_checks_status_created_id",
            "DROP INDEX IF EXISTS idx_ai_job_draft_versions_job_id_id",
            "DROP INDEX IF EXISTS idx_ai_job_messages_job_id_id",
            "DROP INDEX IF EXISTS idx_ai_jobs_user_created_id",
        ):
            op.execute(stmt)
        return

    for name, table in (
        ("idx_media_assets_post_created_id", "media_assets"),
        ("idx_ai_moderation_checks_status_created_id", "ai_moderation_checks"),
        ("idx_ai_job_draft_versions_job_id_id", "ai_job_draft_versions"),
        ("idx_ai_job_messages_job_id_id", "ai_job_messages"),
        ("idx_ai_jobs_user_created_id", "ai_jobs"),
    ):
        op.drop_index(name, table_name=table)
