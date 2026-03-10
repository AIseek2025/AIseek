"""search pg indexes

Revision ID: 0022_search_pg_indexes
Revises: 0021_es_reindex_jobs
Create Date: 2026-03-04
"""

from alembic import op


revision = "0022_search_pg_indexes"
down_revision = "0021_es_reindex_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect != "postgresql":
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_posts_search_tsv "
        "ON posts USING GIN (to_tsvector('simple', coalesce(title,'') || ' ' || coalesce(content_text,'')))"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_posts_category_trgm ON posts USING GIN (category gin_trgm_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_nickname_trgm ON users USING GIN (nickname gin_trgm_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_username_trgm ON users USING GIN (username gin_trgm_ops)")
def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_users_username_trgm")
    op.execute("DROP INDEX IF EXISTS ix_users_nickname_trgm")
    op.execute("DROP INDEX IF EXISTS ix_posts_category_trgm")
    op.execute("DROP INDEX IF EXISTS ix_posts_search_tsv")
