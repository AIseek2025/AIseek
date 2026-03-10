"""post media fields

Revision ID: 0008_post_media_fields
Revises: 0007_scale_indexes
Create Date: 2026-02-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_post_media_fields"
down_revision = "0007_scale_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        for sql in (
            "ALTER TABLE posts ADD COLUMN source_key VARCHAR",
            "ALTER TABLE posts ADD COLUMN source_url VARCHAR",
            "ALTER TABLE posts ADD COLUMN processed_url VARCHAR",
            "ALTER TABLE posts ADD COLUMN error_message TEXT",
            "ALTER TABLE posts ADD COLUMN status_updated_at DATETIME",
        ):
            op.execute(sql)
        op.execute("CREATE INDEX IF NOT EXISTS idx_posts_source_key ON posts(source_key)")
        return

    # Postgres: Use inspector to check for columns
    inspector = sa.inspect(bind)
    columns = [c['name'] for c in inspector.get_columns('posts')]
    
    if 'source_key' not in columns:
        op.add_column("posts", sa.Column("source_key", sa.String(), nullable=True))
    if 'source_url' not in columns:
        op.add_column("posts", sa.Column("source_url", sa.String(), nullable=True))
    if 'processed_url' not in columns:
        op.add_column("posts", sa.Column("processed_url", sa.String(), nullable=True))
    if 'error_message' not in columns:
        op.add_column("posts", sa.Column("error_message", sa.Text(), nullable=True))
    if 'status_updated_at' not in columns:
        op.add_column("posts", sa.Column("status_updated_at", sa.DateTime(timezone=True), nullable=True))

    op.execute("CREATE INDEX IF NOT EXISTS idx_posts_source_key ON posts(source_key)")


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        op.execute("DROP INDEX IF EXISTS idx_posts_source_key")
        return

    op.drop_index("idx_posts_source_key", table_name="posts")
    for col in ("status_updated_at", "error_message", "processed_url", "source_url", "source_key"):
        op.drop_column("posts", col)
