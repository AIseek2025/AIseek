"""es reindex jobs

Revision ID: 0021_es_reindex_jobs
Revises: 0020_post_download_settings
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa


revision = "0021_es_reindex_jobs"
down_revision = "0020_post_download_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    try:
        op.create_table(
            "es_reindex_jobs",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("alias", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=True),
            sa.Column("new_index", sa.String(), nullable=True),
            sa.Column("ok", sa.Integer(), nullable=True),
            sa.Column("total", sa.Integer(), nullable=True),
            sa.Column("cancelled", sa.Boolean(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
    except Exception:
        return
    try:
        op.create_index("ix_es_reindex_jobs_alias", "es_reindex_jobs", ["alias"])
    except Exception:
        pass
    try:
        op.create_index("ix_es_reindex_jobs_status", "es_reindex_jobs", ["status"])
    except Exception:
        pass
    try:
        op.create_index("ix_es_reindex_jobs_created_at", "es_reindex_jobs", ["created_at"])
    except Exception:
        pass


def downgrade() -> None:
    try:
        op.drop_index("ix_es_reindex_jobs_created_at", table_name="es_reindex_jobs")
    except Exception:
        pass
    try:
        op.drop_index("ix_es_reindex_jobs_status", table_name="es_reindex_jobs")
    except Exception:
        pass
    try:
        op.drop_index("ix_es_reindex_jobs_alias", table_name="es_reindex_jobs")
    except Exception:
        pass
    try:
        op.drop_table("es_reindex_jobs")
    except Exception:
        pass
